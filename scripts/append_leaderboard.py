#!/usr/bin/env python3
"""Append a single entry to site-data/leaderboard.json.

Schema matches what the React app at automated_compile/src/App.tsx reads:

    { "entries": [
        { "rank": int,
          "nickname": str,
          "name": str,             # may be ""
          "problem": str,          # e.g. "challenge_1" or "challenge_1_univ"
          "claim": str,            # "prove" | "disprove"
          "parameter": str,        # e.g. "5" or "universal"
          "bound": str,            # challenge_2 only: the certified bound B
          "date": str,             # ISO-8601 UTC, second precision
          "issue": int,            # issue number on the submissions repo
          "source_url": str,       # public proof URL; "" for private submissions
          "submission_public": bool }, # whether the source was public at eval time
        ... ] }

Rank follows the largest existing rank. Repeated recording of the same
issue/result is a no-op; a competing issue cannot take an occupied place.
Challenge 2 records pairs (r, B): a pair already implied by an earlier entry
through monotonicity (r' >= r and B' <= B) is rejected as a duplicate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from dataclasses import dataclass

from ordinal_parameters import display_cnf, parse_cnf


BOUNDED_COUNT = "challenge_2"


def covers(entry: dict, parameter: str, bound: str) -> bool:
    """Whether a recorded Challenge 2 entry already implies the pair (r, B).

    The statement is monotone: a proof at (r', B') gives every (r, B) with
    r <= r' and B >= B'. Such a pair adds nothing and is not recorded."""
    try:
        return int(entry["parameter"]) >= int(parameter) and int(entry["bound"]) <= int(bound)
    except (KeyError, TypeError, ValueError):
        return False


@dataclass(frozen=True)
class Decision:
    status: str  # added, existing, duplicate, or conflict
    entry: dict


def decide(data: dict, metadata: dict) -> Decision:
    """Inspect the latest board without changing it."""
    entries = data["entries"]
    if not isinstance(entries, list):
        raise ValueError("Malformed leaderboard: entries must be a list")
    problem = metadata["problem_id"]
    bounded = problem == BOUNDED_COUNT
    if bounded:
        bound = metadata.get("bound")
        if not isinstance(bound, str) or not bound.isdecimal():
            raise ValueError("Challenge 2 entries need a verified natural-number bound B")
    key = (problem, metadata["parameter"], metadata.get("bound") if bounded else None)
    for entry in entries:
        if entry["issue"] == metadata["issue"]:
            same = (entry["problem"], entry["parameter"],
                    entry.get("bound") if bounded else None) == key
            same = same and entry["claim"] == metadata["claim"]
            return Decision("existing" if same else "conflict", entry)
    for entry in entries:
        if entry["problem"] != problem:
            continue
        if bounded:
            if covers(entry, metadata["parameter"], metadata["bound"]):
                return Decision("duplicate", entry)
        elif entry["parameter"] == metadata["parameter"]:
            return Decision("duplicate", entry)
    public = metadata["submission_public"]
    if not isinstance(public, bool):
        raise ValueError("submission_public must be a boolean")
    ordinal_fields = {}
    if metadata["problem_id"] in ("challenge_6", "challenge_10") and "ordinal_cnf" in metadata:
        if display_cnf(parse_cnf(metadata["ordinal_cnf"])) != metadata["parameter"]:
            raise ValueError("Ordinal parameter and normal form disagree")
        ordinal_fields["ordinal_cnf"] = metadata["ordinal_cnf"]
    return Decision("added", {
        "rank": max((entry["rank"] for entry in entries), default=0) + 1,
        "nickname": metadata["nickname"],
        "name": metadata.get("name", ""),
        "problem": metadata["problem_id"],
        "claim": metadata["claim"],
        "parameter": metadata["parameter"],
        "date": dt.datetime.now(tz=dt.timezone.utc)
                  .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "issue": metadata["issue"],
        "source_url": metadata.get("source_url", "") if public else "",
        "submission_public": public,
        **ordinal_fields,
        **({"bound": metadata["bound"]} if bounded else {}),
    })


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--leaderboard", required=True,
                   help="path to leaderboard.json")
    p.add_argument("--nickname", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--problem", required=True)
    p.add_argument("--claim", required=True)
    p.add_argument("--parameter", required=True)
    p.add_argument("--bound", default=None,
                   help="challenge_2 only: the verified bound B")
    p.add_argument("--issue", required=True, type=int)
    # Optional: a private submission has no publishable source link, so
    # the leaderboard entry carries an empty source_url for it.
    p.add_argument("--source-url", default="")
    p.add_argument("--submission-public", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="whether the submission source was public at "
                        "evaluation time. Private submissions omit source_url.")
    args = p.parse_args()

    path = pathlib.Path(args.leaderboard)
    if path.exists() and path.stat().st_size > 0:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "entries" not in data or not isinstance(data["entries"], list):
            sys.exit(f"{path}: malformed leaderboard, missing entries[]")
    else:
        data = {"entries": []}
        path.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "nickname": args.nickname,
        "name": args.name,
        "problem_id": args.problem,
        "claim": args.claim,
        "parameter": args.parameter,
        **({"bound": args.bound} if args.bound is not None else {}),
        "issue": args.issue,
        "source_url": args.source_url,
        "submission_public": args.submission_public,
    }
    decision = decide(data, metadata)
    if decision.status == "existing":
        print(f"Issue #{args.issue} is already recorded")
        return 0
    if decision.status != "added":
        print(f"Not added: {decision.status}, issue #{decision.entry['issue']}")
        return 1
    entry = decision.entry
    data["entries"].append(entry)

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Appended entry #{entry['rank']} to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
