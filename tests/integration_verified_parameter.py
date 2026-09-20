#!/usr/bin/env python3
"""Compile real Lean checks and verify the reported leaderboard parameters."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_check import parameter_report, render_check
from verified_metadata import resolve_metadata

FIXTURE = """
import Mathlib.SetTheory.Ordinal.Notation

namespace Submission
def r : Nat := 1
theorem challenge_8 : statement_08 r := by
  intro V _ H h
  exact (Nat.not_succ_le_self 1 h).elim

def naturalThree : Nat := 1 + 2
noncomputable def baseOrdinal : Ordinal := Ordinal.omega0
noncomputable def ordinalParameter : Ordinal := baseOrdinal + 1
end Submission
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    project = parser.parse_args().project.resolve()
    subprocess.run(["lake", "build", "Challenges.challenge_08",
                    "Mathlib.SetTheory.Ordinal.Notation"], cwd=project, check=True)
    with tempfile.TemporaryDirectory(prefix="verified-parameter-") as tmp:
        root = Path(tmp)
        source = render_check("challenge_8", "Submission.Main", report_parameter=True)
        source = source.replace("import Submission.Main", FIXTURE)
        source = source.replace(".lake/verified-parameter.json", str(root / "checked.json"))
        for name, problem, declaration in (
            ("natural", "challenge_8", "naturalThree"),
            ("ordinal", "challenge_6", "ordinalParameter"),
            ("universal", "challenge_8_univ", None),
        ):
            extra = parameter_report(problem, "Submission.Main")
            if declaration:
                extra = extra.replace("`Submission.r", "`Submission." + declaration)
            extra = extra.replace("#export_verified_parameter", "#export_parameter_" + name)
            extra = extra.replace(".lake/verified-parameter.json", str(root / f"{name}.json"))
            source += extra
        path = root / "ParameterCheck.lean"
        path.write_text(source)
        proc = subprocess.run(["lake", "env", "lean", str(path)], cwd=project,
                              capture_output=True, text=True, timeout=900)
        if proc.returncode:
            sys.exit(proc.stdout + proc.stderr)
        assert json.loads((root / "checked.json").read_text())["parameter"] == "1"
        natural = json.loads((root / "natural.json").read_text())
        assert natural["parameter"] == "3"
        metadata = resolve_metadata(
            {"problem_id": "challenge_8", "parameter": "100"}, natural, {}
        )
        assert metadata["parameter"] == "3"
        ordinal = json.loads((root / "ordinal.json").read_text())["parameter"]
        assert "Submission" not in ordinal and "baseOrdinal" not in ordinal, ordinal
        assert "omega0" in ordinal or "ω" in ordinal, ordinal
        assert json.loads((root / "universal.json").read_text())["parameter"] == "universal"
        print(f"PASS: checked r=1; claim 100 / computed 1+2 records 3; ordinal {ordinal}; universal.",
              flush=True)

        bad_sources = {
            "wrong_type": source.replace(
                "theorem challenge_8 : statement_08 r := by\n"
                "  intro V _ H h\n  exact (Nat.not_succ_le_self 1 h).elim",
                "theorem challenge_8 : True := True.intro",
            ),
            "unproved": source.replace("exact (Nat.not_succ_le_self 1 h).elim", "sorry"),
        }
        for name, bad_source in bad_sources.items():
            path = root / f"{name}.lean"
            path.write_text(bad_source)
            proc = subprocess.run(["lake", "env", "lean", str(path)], cwd=project,
                                  capture_output=True, text=True, timeout=900)
            assert proc.returncode != 0, f"Accepted {name}"
            if name == "unproved":
                assert "non-permitted axiom `sorryAx`" in proc.stdout + proc.stderr
            else:
                assert "Type mismatch" in proc.stdout + proc.stderr
            print(f"PASS: {name} rejected before metadata can be used.", flush=True)


if __name__ == "__main__":
    main()
