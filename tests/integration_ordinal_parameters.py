#!/usr/bin/env python3
"""Check actual Lean ordinal expressions; no issues, network, or leaderboard writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_check import parameter_report
from ordinal_parameters import parse_cnf
from verified_metadata import resolve_metadata


CASES = {
    "sum": ("ω + ω", "ω*2"),
    "twice": ("ω * 2", "ω*2"),
    "left_two": ("2 * ω", "ω"),
    "absorbed": ("1 + ω", "ω"),
    "successor": ("ω + 1", "ω + 1"),
    "square_nat": ("ω ^ (2 : Nat)", "ω^(2)"),
    "square_ord": ("ω ^ (2 : Ordinal)", "ω^(2)"),
    "square_mul": ("ω * ω", "ω^(2)"),
    "finite_pow_limit": ("(2 : Ordinal) ^ ω", "ω"),
    "successor_square": ("(ω + 1) ^ (2 : Ordinal)", "ω^(2) + ω + 1"),
    "successor_limit": ("(ω + 1) ^ ω", "ω^(ω)"),
    "power_sum": ("ω ^ (ω + 1)", "ω^(ω + 1)"),
    "power_product": ("ω ^ ω * ω", "ω^(ω + 1)"),
    "zero_zero": ("(0 : Ordinal) ^ (0 : Ordinal)", "1"),
    "zero_limit": ("(0 : Ordinal) ^ ω", "0"),
    "one_limit": ("(1 : Ordinal) ^ ω", "1"),
    "nested": ("ω ^ (ω ^ ω)", "ω^(ω^(ω))"),
    "sum_absorption": ("(ω ^ (2 : Ordinal) + ω * 3 + 4) + (ω * 2 + 1)", "ω^(2) + ω*5 + 1"),
    "right_product": ("(ω + 1) * 2", "ω*2 + 1"),
    "natural_cast": ("((2 + 3 : Nat) : Ordinal)", "5"),
    "alias": ("base + base", "ω*2"),
    "large_finite": ("(9007199254740993 : Ordinal) + 1", "9007199254740994"),
    "uncountable": ("(Cardinal.aleph 1).ord", None),
    "custom_numeral": ("@OfNat.ofNat Ordinal 5 ⟨ω⟩", None),
    "custom_add": ("@HAdd.hAdd Ordinal.{0} Ordinal.{0} Ordinal.{0} ⟨fun _ _ => ω⟩ ω ω", None),
    "custom_power": ("@HPow.hPow Ordinal.{0} Ordinal.{0} Ordinal.{0} ⟨fun _ _ => ω⟩ ω 2", None),
    "bounded_power": ("(ω + 1) ^ (1000000 : Ordinal)", None),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    project = parser.parse_args().project.resolve()
    subprocess.run(["lake", "build", "Mathlib.SetTheory.Ordinal.Notation",
                    "Mathlib.SetTheory.Cardinal.Aleph"], cwd=project, check=True)
    board = Path(__file__).resolve().parents[1] / "site-data/leaderboard.json"
    before = board.read_bytes()
    with tempfile.TemporaryDirectory(prefix="ordinal-parameters-") as tmp:
        root = Path(tmp)
        source = ("import Mathlib.SetTheory.Ordinal.Notation\n"
                  "import Mathlib.SetTheory.Cardinal.Aleph\nimport Lean\nopen Ordinal\n")
        source += "namespace Submission\nnoncomputable def base : Ordinal := ω\n"
        for name, (term, _) in CASES.items():
            source += f"noncomputable def r_{name} : Ordinal := {term}\n"
        source += "end Submission\n"
        for name in CASES:
            report = parameter_report("challenge_6", "Submission.Main")
            report = report.replace("`Submission.r", f"`Submission.r_{name}")
            report = report.replace("#export_verified_parameter", f"#export_ordinal_{name}")
            source += report.replace(".lake/verified-parameter.json", str(root / f"{name}.json"))
        path = root / "Ordinals.lean"
        path.write_text(source)
        result = subprocess.run(["lake", "env", "lean", str(path)], cwd=project,
                                capture_output=True, text=True, timeout=900)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        reports = {}
        for name, (_, expected) in CASES.items():
            report = json.loads((root / f"{name}.json").read_text())
            reports[name] = report
            if expected is None:
                assert "ordinal_cnf" not in report, (name, report)
            else:
                assert report["parameter"] == expected, (name, report)
                parse_cnf(report["ordinal_cnf"])
            resolve_metadata({"problem_id": "challenge_6", "parameter": "ignored"}, report, {})
        assert reports["sum"] == reports["twice"] == reports["alias"]
        assert reports["square_nat"] == reports["square_ord"] == reports["square_mul"]
        assert reports["power_sum"] == reports["power_product"]
        chain = ["zero_limit", "zero_zero", "natural_cast", "large_finite", "left_two",
                 "successor", "sum", "square_ord", "successor_limit", "power_sum", "nested"]
        values = [parse_cnf(reports[name]["ordinal_cnf"]) for name in chain]
        assert all(a < b for a, b in zip(values, values[1:])), values
        try:
            resolve_metadata({"problem_id": "challenge_6", "parameter": "ignored"},
                             reports["twice"], {"entries": [{"problem": "challenge_6",
                              "parameter": reports["sum"]["parameter"], "issue": 1}]})
        except ValueError as exc:
            assert "already been settled" in str(exc)
        else:
            raise AssertionError("Equivalent ordinal was not rejected as a duplicate")
        assert board.read_bytes() == before, "Real leaderboard changed"
        print(f"PASS: {len(CASES)} Lean ordinal fixtures, ordering, and duplicate detection.")


if __name__ == "__main__":
    main()
