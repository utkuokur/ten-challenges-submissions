#!/usr/bin/env python3
"""Use the checked Lean parameter for the leaderboard, never the issue's claim."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ordinal_parameters import display_cnf, parse_cnf


def resolve_metadata(metadata: dict, report: dict, leaderboard: dict) -> dict:
    problem = metadata["problem_id"]
    if report.get("problem_id") != problem:
        raise ValueError("The verified parameter report is for a different problem.")
    parameter = report.get("parameter")
    if not isinstance(parameter, str) or not parameter.strip():
        raise ValueError("The build did not report a verified parameter.")
    parameter = " ".join(parameter.split())
    if problem.endswith(("_univ", "_disprove")):
        if parameter != "universal":
            raise ValueError("Expected a universal submission.")
    elif problem not in ("challenge_6", "challenge_10"):
        if not parameter.isascii() or not parameter.isdecimal():
            raise ValueError("The verified parameter must be a natural number.")
        parameter = parameter.lstrip("0") or "0"
    elif parameter == "universal":
        raise ValueError("Expected an ordinal parameter.")
    ordinal_fields = {}
    if problem in ("challenge_6", "challenge_10") and "ordinal_cnf" in report:
        normal = parse_cnf(report["ordinal_cnf"])
        if display_cnf(normal) != parameter:
            raise ValueError("The ordinal display does not match its normal form.")
        ordinal_fields["ordinal_cnf"] = report["ordinal_cnf"]
    for entry in leaderboard.get("entries", []):
        if entry.get("problem") == problem and entry.get("parameter") == parameter:
            raise ValueError(
                f"Challenge {problem} at r = {parameter} has already been settled "
                f"by issue #{entry.get('issue', '?')}."
            )
    result = {**metadata, "claimed_parameter": metadata["parameter"], "parameter": parameter}
    # Only the checked report can supply a comparison key. Do not retain a
    # claimed/stale key from the issue metadata when normalization is absent.
    result.pop("ordinal_cnf", None)
    return {**result, **ordinal_fields}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--leaderboard", type=Path, required=True)
    args = parser.parse_args()
    try:
        leaderboard = json.loads(args.leaderboard.read_text()) if args.leaderboard.exists() else {}
        result = resolve_metadata(
            json.loads(args.metadata.read_text()), json.loads(args.report.read_text()), leaderboard
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    args.metadata.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
