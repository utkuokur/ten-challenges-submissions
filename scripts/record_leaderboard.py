#!/usr/bin/env python3
"""Make one save attempt for a checked result.

Run only in a disposable, trusted recorder checkout, never the build runner.
The caller serializes recording and supplies verified metadata in issue order.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from append_leaderboard import Decision, decide


class RecordingError(RuntimeError):
    """The remote leaderboard does not confirm a successful recording."""


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], check=check,
                          capture_output=True, text=True)


def refresh(root: Path) -> dict:
    git(root, "fetch", "origin", "main")
    git(root, "reset", "--hard", "origin/main")
    return json.loads((root / "site-data/leaderboard.json").read_text())


def save_entry(root: Path, metadata: dict) -> Decision:
    """Check the current board, then push once. The caller closes failures."""
    try:
        data = refresh(root)
        decision = decide(data, metadata)
        if decision.status != "added":
            return decision
        data["entries"].append(decision.entry)
        (root / "site-data/leaderboard.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        git(root, "add", "site-data/leaderboard.json")
        git(root, "commit", "-m", f"leaderboard: issue #{metadata['issue']}")
        git(root, "push", "origin", "HEAD:main")
        return decision
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        # Do not include metadata or subprocess output in public error messages.
        raise RecordingError("Could not confirm the leaderboard update.") from exc
