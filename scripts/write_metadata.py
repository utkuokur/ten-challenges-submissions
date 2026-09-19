#!/usr/bin/env python3
"""Write the frozen submission metadata.json from environment variables.

Usage:
    write_metadata.py <output-path>

Reads ISSUE, PROBLEM_ID, PARAMETER, CLAIM, NICKNAME, NAME, MODULE,
REPO_URL, REPO_REF, SUBMISSION_KIND, SUBMISSION_REPO, SUBMISSION_REF,
SUBMISSION_PUBLIC from the environment and serializes them to JSON.
MAINTENANCE_CONSENT optionally contains the captured permission as JSON.
Reading from the environment (rather than `${{ }}` interpolation
into the workflow script) and serializing with json.dumps keeps
user-controlled fields escaped, not injected.

This metadata is consumed by `archive_submission.py encrypt` (audit
sidecar) and by the `record` job (leaderboard entry).
"""

from __future__ import annotations

import json
import os
import sys


def main(argv):
    if len(argv) != 1:
        print("usage: write_metadata.py <output-path>", file=sys.stderr)
        return 2
    out_path = argv[0]

    src = os.environ["REPO_URL"] + "/tree/" + os.environ["REPO_REF"]

    data = {
        "issue": int(os.environ["ISSUE"]),
        "problem_id": os.environ["PROBLEM_ID"],
        "parameter": os.environ["PARAMETER"],
        "claim": os.environ["CLAIM"],
        "nickname": os.environ["NICKNAME"],
        "name": os.environ.get("NAME", ""),
        "module": os.environ["MODULE"],
        "submission_kind": os.environ["SUBMISSION_KIND"],
        "submission_repo": os.environ["SUBMISSION_REPO"],
        "submission_ref": os.environ.get("SUBMISSION_REF", ""),
        "submission_public": os.environ["SUBMISSION_PUBLIC"] == "true",
        "source_url": src,
    }
    if consent := os.environ.get("MAINTENANCE_CONSENT"):
        data["maintenance_consent"] = json.loads(consent)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
