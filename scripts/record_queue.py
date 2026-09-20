#!/usr/bin/env python3
"""Drain checked submissions in issue-opening order, with one save per issue.

Only the trusted Record submissions workflow runs this, under one concurrency
group. A wake-up handles the whole queue: coalescing wake-ups loses no results.
An earlier unfinished evaluation pauses recording without occupying a runner.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from append_leaderboard import Decision
from record_leaderboard import RecordingError, refresh, save_entry

MARKER = "<!-- ten-challenges-recording:v1 -->"
BOT_ID = 41898282  # github-actions[bot]
RESULT = re.compile(r"<!-- recording-result:(completed|not_planned) -->")


class APIError(RuntimeError):
    pass


class GitHub:
    def __init__(self, repository: str):
        self.prefix = f"repos/{repository}/"

    def request(self, route: str, *, method: str = "GET", data=None, raw=False):
        command = ["gh", "api", self.prefix + route, "--method", method]
        payload = None
        if data is not None:
            command += ["--input", "-"]
            payload = json.dumps(data).encode()
        result = subprocess.run(command, input=payload, capture_output=True)
        if result.returncode:
            raise APIError("GitHub could not complete the recording request.")
        return result.stdout if raw else json.loads(result.stdout or b"null")

    def items(self, route: str, key: str | None = None):
        separator = "&" if "?" in route else "?"
        page = 1
        while True:
            data = self.request(f"{route}{separator}per_page=100&page={page}")
            items = data[key] if key else data
            yield from items
            if len(items) < 100:
                break
            page += 1

    def metadata(self, run: dict) -> dict:
        name = f"submission-metadata-{run['run_attempt']}"
        artifacts = list(self.items(f"actions/runs/{run['id']}/artifacts", "artifacts"))
        matches = [a for a in artifacts if a["name"] == name and not a["expired"]]
        if len(matches) != 1:
            raise RecordingError("Verified metadata is missing or expired.")
        archive = self.request(f"actions/artifacts/{matches[0]['id']}/zip", raw=True)
        if len(archive) > 2_000_000:
            raise RecordingError("Verified metadata is too large.")
        # Read only this data file; never extract or execute artifact contents.
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            info = z.getinfo("metadata.json")
            if info.file_size > 1_000_000:
                raise RecordingError("Verified metadata is too large.")
            return json.loads(z.read(info))


def submission_issues(api: GitHub) -> list[dict]:
    issues = [i for i in api.items("issues?state=open&sort=created&direction=asc")
              if "pull_request" not in i and "### Problem" in (i.get("body") or "")]
    # GitHub issue timestamps have second precision; issue number breaks ties.
    return sorted(issues, key=lambda i: (i["created_at"], i["number"]))


def evaluation_runs(api: GitHub, issues: list[dict]) -> dict[int, dict]:
    wanted = {f"Submission #{i['number']}": i["number"] for i in issues}
    found = {}
    for run in api.items("actions/workflows/submission.yml/runs", "workflow_runs"):
        number = wanted.get(run["display_title"])
        if number is None or run["event"] != "issues":
            continue
        if number not in found or run["id"] > found[number]["id"]:
            found[number] = run
    return found


def recording_comment(api: GitHub, number: int) -> dict | None:
    return next((c for c in api.items(f"issues/{number}/comments")
                 if c["user"]["id"] == BOT_ID and MARKER in c["body"]), None)


def finish(api: GitHub, number: int, comment: dict, message: str, *, accepted=False):
    reason = "completed" if accepted else "not_planned"
    body = f"{MARKER}\n<!-- recording-result:{reason} -->\n{message}"
    api.request(f"issues/comments/{comment['id']}", method="PATCH", data={"body": body})
    api.request(f"issues/{number}", method="PATCH",
                data={"state": "closed", "state_reason": reason})


def finish_decision(api: GitHub, number: int, comment: dict, decision: Decision):
    if decision.status in ("added", "existing"):
        finish(api, number, comment,
               "✅ Build succeeded — your result is on the leaderboard. "
               "An encrypted copy of your submission was archived for audit.", accepted=True)
    elif decision.status == "duplicate":
        finish(api, number, comment,
               f"❌ Duplicate: this result was already recorded for issue "
               f"#{decision.entry['issue']}. This issue is closed.")
    else:
        finish(api, number, comment,
               "❌ This issue already has a different result on the leaderboard. "
               "Please open a new issue for a different submission.")


def finish_recording_error(api: GitHub, number: int, comment: dict):
    # A failed push response can mean either no save or a lost confirmation.
    finish(api, number, comment,
           "⚠️ A connection or recording problem prevented confirmation of the "
           "leaderboard update. This issue is closed. Please check the leaderboard; "
           "if your result is missing, open a new issue to submit again.")


def resume_notification(api: GitHub, root: Path, number: int, comment: dict):
    """Recover a notification after interruption, never make another save."""
    if result := RESULT.search(comment["body"]):
        api.request(f"issues/{number}", method="PATCH",
                    data={"state": "closed", "state_reason": result[1]})
        return
    try:
        entries = refresh(root)["entries"]
        own = next((e for e in entries if e["issue"] == number), None)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        own = None
    if own:
        finish_decision(api, number, comment, Decision("existing", own))
    else:
        finish_recording_error(api, number, comment)


def drain(api: GitHub, root: Path, save=save_entry) -> bool:
    """Return false if a completed evaluation could not be recorded."""
    issues = submission_issues(api)
    runs = evaluation_runs(api, issues) if issues else {}
    ok = True
    for issue in issues:
        number = issue["number"]
        # A previous invocation may have saved but failed to notify/close.
        if comment := recording_comment(api, number):
            resume_notification(api, root, number, comment)
            continue
        if any(e["event"] == "reopened" for e in api.items(f"issues/{number}/events")):
            comment = api.request(f"issues/{number}/comments", method="POST",
                                  data={"body": MARKER})
            finish(api, number, comment,
                   "This issue is closed. Please open a new issue to submit again.")
            continue
        run = runs.get(number)
        if run is None or run["status"] != "completed":
            print(f"Waiting for the evaluation of issue #{number}.")
            break
        # Recheck: the author/maintainer may have withdrawn it during evaluation.
        if api.request(f"issues/{number}")["state"] != "open":
            continue
        # This durable marker is written BEFORE attempting a save. If this
        # runner is interrupted, a later wake-up may finish the notification,
        # but cannot make another save attempt for the same issue.
        comment = api.request(f"issues/{number}/comments", method="POST",
                              data={"body": f"{MARKER}\nProcessing the submission result."})
        try:
            jobs = {j["name"]: j["conclusion"] for j in api.items(
                f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs")}
            if jobs.get("evaluate") != "success" or jobs.get("archive") != "success":
                finish(api, number, comment,
                       "❌ Evaluation or archival did not complete successfully. "
                       "This issue is closed; please open a new issue to submit again.")
                ok = False
                continue
            metadata = api.metadata(run)
            if metadata.get("issue") != number:
                raise RecordingError("Metadata does not match the submission issue.")
            decision = save(root, metadata)
        except (APIError, RecordingError, OSError, ValueError, KeyError,
                TypeError, zipfile.BadZipFile):
            finish_recording_error(api, number, comment)
            ok = False
            continue
        finish_decision(api, number, comment, decision)
    return ok


def main() -> int:
    api = GitHub(os.environ["GITHUB_REPOSITORY"])
    try:
        return 0 if drain(api, Path.cwd()) else 1
    except (APIError, OSError, ValueError, KeyError, TypeError):
        # If GitHub's issue API itself is down we cannot comment/close yet.
        # The durable marker prevents another save on a later recorder run.
        print("Recording stopped: GitHub could not complete the queue or issue update.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
