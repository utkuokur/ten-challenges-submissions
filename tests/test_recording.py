"""Exercise ordered recording without GitHub requests or real leaderboard writes."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from append_leaderboard import decide
import record_leaderboard as recorder
from record_queue import APIError, BOT_ID, GitHub, MARKER, drain


def metadata(number=1, problem="challenge_8", parameter="3", public=False):
    return {"issue": number, "problem_id": problem, "parameter": parameter,
            "claim": "prove", "nickname": "Tester", "name": "", "module": "challenge_08",
            "submission_public": public, "source_url": "https://github.com/private/proof"}


class LocalGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.remote = root / "remote.git"
        self.work = root / "recorder"
        self.other = root / "maintainer"
        self.command("git", "init", "--bare", str(self.remote))
        self.command("git", "clone", str(self.remote), str(self.work))
        self.configure(self.work)
        self.command("git", "-C", str(self.work), "checkout", "-b", "main")
        (self.work / "site-data").mkdir()
        self.write_board({"entries": []})
        self.command("git", "-C", str(self.work), "add", ".")
        self.command("git", "-C", str(self.work), "commit", "-m", "initial")
        self.command("git", "-C", str(self.work), "push", "origin", "main")
        self.command("git", "clone", "--branch", "main", str(self.remote), str(self.other))
        self.configure(self.other)

    def command(self, *args):
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout

    def configure(self, root):
        for name, value in (("user.name", "Test"), ("user.email", "test@example.invalid"),
                            ("commit.gpgsign", "false")):
            self.command("git", "-C", str(root), "config", name, value)

    def write_board(self, data, root=None):
        ((root or self.work) / "site-data/leaderboard.json").write_text(json.dumps(data))

    def remote_board(self):
        return json.loads(self.command("git", "--git-dir", str(self.remote),
                                       "show", "main:site-data/leaderboard.json"))

    def test_sequential_different_challenges_both_recorded(self):
        first = recorder.save_entry(self.work, metadata())
        second = recorder.save_entry(self.work, metadata(2, "challenge_1", "4", True))
        self.assertEqual((first.status, second.status), ("added", "added"))
        entries = self.remote_board()["entries"]
        self.assertEqual([e["rank"] for e in entries], [1, 2])
        self.assertEqual(entries[0]["source_url"], "")
        self.assertTrue(entries[1]["source_url"])

    def test_same_parameter_second_rejected_and_same_issue_idempotent(self):
        recorder.save_entry(self.work, metadata())
        self.assertEqual(recorder.save_entry(self.work, metadata(2)).status, "duplicate")
        self.assertEqual(recorder.save_entry(self.work, metadata()).status, "existing")
        self.assertEqual(recorder.save_entry(self.work, metadata(parameter="4")).status, "conflict")
        self.assertEqual(len(self.remote_board()["entries"]), 1)

    def test_latest_board_checked_and_deleted_rank_not_reused(self):
        entry = decide({"entries": []}, metadata(8)).entry
        entry["rank"] = 19
        self.write_board({"entries": [entry]}, self.other)
        self.command("git", "-C", str(self.other), "commit", "-am", "concurrent record")
        self.command("git", "-C", str(self.other), "push", "origin", "main")
        self.assertEqual(recorder.save_entry(self.work, metadata(9)).status, "duplicate")
        added = recorder.save_entry(self.work, metadata(10, parameter="4"))
        self.assertEqual(added.entry["rank"], 20)

    def test_rejected_push_is_not_retried(self):
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        with patch.object(recorder, "git", wraps=recorder.git) as calls:
            with self.assertRaises(recorder.RecordingError):
                recorder.save_entry(self.work, metadata())
        self.assertEqual(sum(c.args[1] == "push" for c in calls.call_args_list), 1)
        self.assertEqual(self.remote_board(), {"entries": []})

    def test_competing_commit_causes_one_failed_attempt_without_overwrite(self):
        original = recorder.git
        def racing_git(root, *args, **kwargs):
            if args[0] == "push":
                (self.other / "note.txt").write_text("maintainer update")
                self.command("git", "-C", str(self.other), "add", "note.txt")
                self.command("git", "-C", str(self.other), "commit", "-m", "new head")
                self.command("git", "-C", str(self.other), "push", "origin", "main")
            return original(root, *args, **kwargs)
        with patch.object(recorder, "git", side_effect=racing_git) as calls:
            with self.assertRaises(recorder.RecordingError):
                recorder.save_entry(self.work, metadata())
        self.assertEqual(sum(c.args[1] == "push" for c in calls.call_args_list), 1)
        self.assertEqual(self.remote_board(), {"entries": []})

    def test_lost_push_confirmation_cannot_let_next_issue_duplicate_saved_result(self):
        original = recorder.git
        def lost_response(root, *args, **kwargs):
            result = original(root, *args, **kwargs)
            if args[0] == "push":
                raise subprocess.CalledProcessError(1, ["git", *args])
            return result
        with patch.object(recorder, "git", side_effect=lost_response) as calls:
            with self.assertRaises(recorder.RecordingError):
                recorder.save_entry(self.work, metadata())
        self.assertEqual(sum(c.args[1] == "push" for c in calls.call_args_list), 1)
        self.assertEqual(recorder.save_entry(self.work, metadata(2)).status, "duplicate")
        self.assertEqual([e["issue"] for e in self.remote_board()["entries"]], [1])

    def test_fetch_reset_and_commit_failures_do_not_push(self):
        for failure in ("fetch", "reset", "commit"):
            with self.subTest(failure=failure):
                original = recorder.git
                def failing_git(root, *args, **kwargs):
                    if args[0] == failure:
                        raise subprocess.CalledProcessError(1, ["git", *args])
                    return original(root, *args, **kwargs)
                with patch.object(recorder, "git", side_effect=failing_git) as calls:
                    with self.assertRaises(recorder.RecordingError):
                        recorder.save_entry(self.work, metadata())
                self.assertFalse(any(c.args[1] == "push" for c in calls.call_args_list))
        self.assertEqual(self.remote_board(), {"entries": []})


class FakeGitHub:
    def __init__(self):
        self.issues = {}
        self.runs = {}
        self.comments = {}
        self.events = {}
        self.jobs = {}
        self.proofs = {}
        self.close_fails = False

    def add(self, number, *, status="completed", problem="challenge_8", parameter="3"):
        self.issues[number] = {"number": number, "body": "### Problem\nChallenge 8",
                               "created_at": f"2026-09-20T10:00:{number:02d}Z", "state": "open"}
        self.runs[number] = {"id": number, "display_title": f"Submission #{number}",
                             "event": "issues", "run_attempt": 1, "status": status}
        self.jobs[number] = [{"name": "evaluate", "conclusion": "success"},
                             {"name": "archive", "conclusion": "success"}]
        self.proofs[number] = metadata(number, problem, parameter)
        self.comments[number] = []
        self.events[number] = []

    def items(self, route, key=None):
        if route.startswith("issues?"):
            return [i for i in self.issues.values() if i["state"] == "open"]
        if route == "actions/workflows/submission.yml/runs":
            return list(reversed(list(self.runs.values())))
        if route.startswith("issues/"):
            _, number, kind = route.split("/")
            return getattr(self, kind)[int(number)]
        if route.startswith("actions/runs/") and route.endswith("/jobs"):
            return self.jobs[int(route.split("/")[2])]
        raise AssertionError(route)

    def request(self, route, *, method="GET", data=None):
        if route.startswith("issues/comments/"):
            comment_id = int(route.split("/")[-1])
            comment = next(c for cs in self.comments.values() for c in cs if c["id"] == comment_id)
            comment.update(data)
            return copy.deepcopy(comment)
        parts = route.split("/")
        number = int(parts[1])
        if parts[-1] == "comments":
            comment = {"id": number * 100 + len(self.comments[number]),
                       "user": {"id": BOT_ID}, **data}
            self.comments[number].append(comment)
            return copy.deepcopy(comment)
        if method == "PATCH":
            if self.close_fails:
                raise APIError("Offline")
            self.issues[number].update(data)
        return copy.deepcopy(self.issues[number])

    def metadata(self, run):
        return copy.deepcopy(self.proofs[run["id"]])


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHub()
        self.board = {"entries": []}
        self.saved = []

    def save(self, root, proof):
        self.saved.append(proof["issue"])
        decision = decide(self.board, proof)
        if decision.status == "added":
            self.board["entries"].append(decision.entry)
        return decision

    def drain(self):
        return drain(self.api, Path("unused"), self.save)

    def test_later_completion_waits_for_earlier_issue_then_both_different_problems_save(self):
        self.api.add(2, problem="challenge_1")
        self.api.add(1, status="in_progress")
        self.assertTrue(self.drain())
        self.assertEqual(self.saved, [])
        self.api.runs[1]["status"] = "completed"
        self.assertTrue(self.drain())
        self.assertEqual(self.saved, [1, 2])
        self.assertEqual(len(self.board["entries"]), 2)
        self.assertTrue(all(i["state"] == "closed" for i in self.api.issues.values()))

    def test_same_parameter_earlier_wins_and_later_gets_duplicate(self):
        self.api.add(2)
        self.api.add(1)
        self.assertTrue(self.drain())
        self.assertEqual(self.saved, [1, 2])
        self.assertEqual([e["issue"] for e in self.board["entries"]], [1])
        self.assertIn("Duplicate", self.api.comments[2][-1]["body"])
        self.assertIn("#1", self.api.comments[2][-1]["body"])
        self.assertEqual(self.api.issues[2]["state_reason"], "not_planned")

    def test_same_challenge_different_parameters_both_recorded(self):
        self.api.add(2, parameter="4")
        self.api.add(1)
        self.assertTrue(self.drain())
        self.assertEqual([e["parameter"] for e in self.board["entries"]], ["3", "4"])

    def test_same_second_tie_uses_issue_number(self):
        self.api.add(2)
        self.api.add(1)
        self.api.issues[2]["created_at"] = self.api.issues[1]["created_at"]
        self.drain()
        self.assertEqual(self.saved, [1, 2])

    def test_missing_run_waits_and_closed_or_non_submission_issues_do_not_block(self):
        self.api.add(1)
        self.api.add(2)
        del self.api.runs[1]
        self.drain()
        self.assertEqual(self.saved, [])
        self.api.issues[1]["state"] = "closed"
        self.api.add(3)
        self.api.issues[3]["body"] = "General question"
        self.drain()
        self.assertEqual(self.saved, [2])

    def test_connection_failure_closes_once_and_next_issue_can_succeed(self):
        self.api.add(1)
        self.api.add(2)
        calls = []
        def fail_first(root, proof):
            calls.append(proof["issue"])
            if proof["issue"] == 1:
                raise recorder.RecordingError("Connection failure")
            return self.save(root, proof)
        self.assertFalse(drain(self.api, Path("unused"), fail_first))
        self.assertEqual(calls, [1, 2])
        self.assertIn("connection or recording problem", self.api.comments[1][-1]["body"])
        self.assertEqual(self.api.issues[1]["state"], "closed")
        self.assertEqual([e["issue"] for e in self.board["entries"]], [2])
        self.assertTrue(drain(self.api, Path("unused"), fail_first))
        self.assertEqual(calls, [1, 2])

    def test_archive_failure_and_wrong_metadata_cannot_record(self):
        for invalid in ("archive", "metadata"):
            with self.subTest(invalid=invalid):
                self.api = FakeGitHub()
                self.api.add(1)
                if invalid == "archive":
                    self.api.jobs[1][1]["conclusion"] = "failure"
                else:
                    self.api.proofs[1]["issue"] = 900
                self.assertFalse(self.drain())
                self.assertEqual(self.saved, [])
                self.assertEqual(self.api.issues[1]["state"], "closed")

    def test_failed_earlier_evaluation_does_not_block_later_valid_submission(self):
        self.api.add(1)
        self.api.add(2)
        self.api.jobs[1][0]["conclusion"] = "failure"
        self.assertFalse(self.drain())
        self.assertEqual(self.saved, [2])
        self.assertEqual([e["issue"] for e in self.board["entries"]], [2])
        self.assertEqual(self.api.issues[1]["state"], "closed")

    def test_reopening_requires_new_issue_without_another_save(self):
        self.api.add(1)
        self.api.events[1] = [{"event": "reopened"}]
        self.drain()
        self.assertEqual(self.saved, [])
        self.assertEqual(self.api.issues[1]["state"], "closed")
        self.assertIn("new issue", self.api.comments[1][-1]["body"])

    def test_interrupted_notification_is_recovered_without_another_save(self):
        self.api.add(1)
        self.api.close_fails = True
        with self.assertRaises(APIError):
            self.drain()
        self.api.close_fails = False
        self.drain()
        self.assertEqual(self.saved, [1])
        self.assertEqual(self.api.issues[1]["state"], "closed")

    def test_interrupted_attempt_never_saves_again_whether_save_arrived_or_not(self):
        for arrived in (False, True):
            with self.subTest(arrived=arrived):
                self.api = FakeGitHub()
                self.api.add(1)
                self.api.request("issues/1/comments", method="POST", data={"body": MARKER})
                board = {"entries": [decide({"entries": []}, metadata()).entry] if arrived else []}
                with patch("record_queue.refresh", return_value=board):
                    self.drain()
                self.assertEqual(self.saved, [])
                self.assertEqual(self.api.issues[1]["state_reason"],
                                 "completed" if arrived else "not_planned")

    def test_user_cannot_forge_attempt_marker(self):
        self.api.add(1)
        self.api.comments[1] = [{"id": 12, "user": {"id": 123}, "body": MARKER}]
        self.drain()
        self.assertEqual(self.saved, [1])


class ArtifactTests(unittest.TestCase):
    def test_reads_only_current_attempt_metadata_without_extracting_files(self):
        api = GitHub("example/submissions")
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("metadata.json", json.dumps(metadata()))
            z.writestr("../malicious.py", "do not execute")
        artifacts = [{"id": 10, "name": "submission-metadata-1", "expired": False},
                     {"id": 20, "name": "submission-metadata-2", "expired": False}]
        with patch.object(api, "items", return_value=artifacts), \
             patch.object(api, "request", return_value=archive.getvalue()) as request:
            self.assertEqual(api.metadata({"id": 99, "run_attempt": 2}), metadata())
            request.assert_called_once_with("actions/artifacts/20/zip", raw=True)

    def test_old_or_expired_artifact_is_not_accepted(self):
        api = GitHub("example/submissions")
        for artifact in ({"id": 10, "name": "submission-metadata-1", "expired": False},
                         {"id": 20, "name": "submission-metadata-2", "expired": True}):
            with self.subTest(artifact=artifact), patch.object(api, "items", return_value=[artifact]):
                with self.assertRaises(recorder.RecordingError):
                    api.metadata({"id": 99, "run_attempt": 2})


if __name__ == "__main__":
    unittest.main()
