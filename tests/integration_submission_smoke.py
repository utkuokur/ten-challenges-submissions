#!/usr/bin/env python3
"""Local submission acceptance/rejection tests; never call GitHub or publish records.

Usage: python3 tests/integration_submission_smoke.py --project ../ten-challenges

Each case compiles separate Submission modules, then the production signature,
axiom, and parameter checks. All modules, reports, and logs live in a temporary
directory. This tests the Lean verifier and metadata handling, not the GitHub
fetch/encryption jobs or isolation against arbitrary elaborator code.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from generate_check import render_check
from shim_drift_check import canonical_module
from verified_metadata import resolve_metadata
from integration_explicit_matroids import run_checks as run_matroid_data_checks

FIXTURES = Path(__file__).parent / "fixtures" / "submission_smoke"
RYSER = (FIXTURES / "ryser_one.lean").read_text()
RYSER_PROOF = """  intro V _ H h
  exact (Nat.not_succ_le_self 1 h).elim"""


@dataclass
class Case:
    name: str
    problem: str
    source: str
    parameter: str | None = None
    rejection: str | None = None
    content_rejection: bool = False
    helpers: dict[str, str] = field(default_factory=dict)


def cases() -> list[Case]:
    bad_axiom = "non-permitted axiom"
    return [
        Case("hadwiger_zero", "challenge_1",
             (FIXTURES / "hadwiger_zero.lean").read_text(), parameter="0"),
        Case("ryser_one_claim_100", "challenge_8", RYSER, parameter="1"),
        Case("ryser_zero", "challenge_8", RYSER.replace("ℕ := 1", "ℕ := 0").replace(
            RYSER_PROOF, "  intro V _ H h\n  exact (Nat.not_succ_le_zero 1 h).elim"),
             parameter="0"),
        Case("ordinal_zero", "challenge_10",
             (FIXTURES / "ordinal_zero.lean").read_text(), parameter="0"),
        Case("computed_parameter_helper", "challenge_8",
             RYSER.replace("import Challenges.challenge_08",
                           "import Challenges.challenge_08\nimport Submission.Helper")
                  .replace("ℕ := 1", "ℕ := helperParameter"), parameter="1",
             helpers={"Helper": "namespace Submission\ndef helperParameter : Nat := 2 - 1\nend Submission\n"}),
        Case("compiled_parameter_override", "challenge_8",
             RYSER.replace("def r : ℕ := 1",
                           "def inflated : ℕ := 100\n@[implemented_by inflated] def r : ℕ := 1"),
             parameter="1"),
        Case("wrong_theorem_type", "challenge_8",
             RYSER.replace("statement_08.{u} r := by\n" + RYSER_PROOF,
                           "True := True.intro"), rejection="Type mismatch"),
        Case("shadow_statement", "challenge_8",
             RYSER.replace("def r : ℕ := 1", "def r : ℕ := 100\ndef statement_08 (_ : ℕ) : Prop := True")
                  .replace("statement_08.{u} r := by\n" + RYSER_PROOF,
                           "statement_08 r := True.intro"), rejection="Type mismatch"),
        Case("wrong_proved_parameter", "challenge_8",
             RYSER.replace("ℕ := 1", "ℕ := 100").replace("statement_08.{u} r", "statement_08.{u} 1"),
             rejection="Type mismatch"),
        Case("extra_assumption", "challenge_8",
             RYSER.replace("theorem challenge_8 : statement_08.{u} r := by\n" + RYSER_PROOF,
                           "theorem challenge_8 (h : False) : statement_08.{u} r := h.elim"),
             rejection="Type mismatch"),
        Case("restricted_universe", "challenge_8", RYSER.replace("statement_08.{u}", "statement_08.{0}"),
             rejection="Type mismatch"),
        Case("specific_as_universal", "challenge_8_univ", RYSER, rejection="Type mismatch"),
        Case("proof_as_disproof", "challenge_8_disprove", RYSER, rejection="Type mismatch"),
        Case("placeholder", "challenge_8", RYSER.replace(RYSER_PROOF, "  sorry"),
             rejection=bad_axiom, content_rejection=True),
        Case("direct_sorryAx", "challenge_8", RYSER.replace(RYSER_PROOF, "  exact sorryAx _ false"),
             rejection=bad_axiom),
        Case("declared_axiom", "challenge_8",
             RYSER.replace("theorem challenge_8", "axiom fake : False\n\ntheorem challenge_8")
                  .replace(RYSER_PROOF, "  exact fake.elim"),
             rejection=bad_axiom, content_rejection=True),
        Case("helper_axiom", "challenge_8",
             RYSER.replace("import Challenges.challenge_08",
                           "import Challenges.challenge_08\nimport Submission.Helper")
                  .replace(RYSER_PROOF, "  exact fake.elim"),
             rejection=bad_axiom, content_rejection=True,
             helpers={"Helper": "namespace Submission\naxiom fake : False\nend Submission\n"}),
        Case("indirect_sorryAx", "challenge_8",
             RYSER.replace("import Challenges.challenge_08",
                           "import Challenges.challenge_08\nimport Submission.Helper")
                  .replace(RYSER_PROOF, "  exact fake.elim"), rejection=bad_axiom,
             helpers={"Helper": "namespace Submission\ntheorem fake : False := sorryAx _ false\nend Submission\n"}),
        Case("canonical_placeholder_reuse", "challenge_8",
             RYSER.replace("def r : ℕ := 1", "def r : ℕ := _root_.r")
                  .replace(RYSER_PROOF, "  exact _root_.challenge_8"), rejection=bad_axiom),
    ]


def run_case(project: Path, root: Path, case: Case, lean_path: str) -> None:
    root.mkdir()
    submission = root / "Submission"
    submission.mkdir()
    for name, source in {**case.helpers, "Main": case.source}.items():
        (submission / f"{name}.lean").write_text(source)
    report = root / "report.json"
    check = render_check(case.problem, "Submission.Main", report_parameter=True)
    (root / "Check.lean").write_text(check.replace(".lake/verified-parameter.json", str(report)))

    content = subprocess.run(
        [sys.executable, str(SCRIPTS / "content_checks.py"), str(submission)],
        capture_output=True, text=True, check=False, timeout=30)
    assert (content.returncode != 0) == case.content_rejection, content.stdout + content.stderr

    # Even fixtures stopped by the lexical filter also exercise the axiom
    # backstop. Every fixture must compile before the verifier rejects it.
    # Put this case first: the project may already have a compiled
    # Submission.Main from another local test or the user's scaffold.
    env = {**os.environ, "LEAN_PATH": str(root) + os.pathsep + lean_path}
    for name in [*case.helpers, "Main"]:
        path = submission / f"{name}.lean"
        proc = subprocess.run(
            ["lean", f"--root={root}", "-o", str(path.with_suffix(".olean")), str(path)],
            cwd=project, env=env, capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, f"Fixture did not compile: {proc.stdout}{proc.stderr}"

    proc = subprocess.run(
        ["lean", f"--root={root}", str(root / "Check.lean")],
        cwd=project, env=env, capture_output=True, text=True, timeout=900)
    output = proc.stdout + proc.stderr
    (root / "check.log").write_text(output)
    if case.rejection:
        assert proc.returncode != 0, "Verifier accepted an invalid submission"
        assert case.rejection.lower() in output.lower(), output
        return
    assert proc.returncode == 0, output
    checked = json.loads(report.read_text())
    assert checked == {"problem_id": case.problem, "parameter": case.parameter}, checked
    metadata = resolve_metadata({"problem_id": case.problem, "parameter": "100"}, checked, {"entries": []})
    assert metadata["parameter"] == case.parameter, metadata
    try:
        resolve_metadata(metadata, checked, {"entries": [{
            "problem": case.problem, "parameter": case.parameter, "issue": 0}]})
    except ValueError as exc:
        assert "already been settled" in str(exc), exc
    else:
        raise AssertionError("Duplicate verified parameter was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--cases", nargs="*", help="Optional subset of case names")
    args = parser.parse_args()
    project = args.project.resolve()
    selected = cases()
    if args.cases:
        unknown = set(args.cases) - {case.name for case in selected}
        if unknown:
            parser.error(f"Unknown cases: {sorted(unknown)}")
        selected = [case for case in selected if case.name in args.cases]
    modules = sorted({"Challenges." + canonical_module(case.problem) for case in selected})
    subprocess.run(["lake", "build", *modules], cwd=project, check=True)
    lean_path = subprocess.check_output(
        ["lake", "env", "printenv", "LEAN_PATH"], cwd=project, text=True).strip()
    board = SCRIPTS.parent / "site-data" / "leaderboard.json"
    before = board.read_bytes()
    failures = []
    with tempfile.TemporaryDirectory(prefix="submission-smoke-") as tmp:
        for case in selected:
            try:
                run_case(project, Path(tmp) / case.name, case, lean_path)
            except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
                failures.append(case.name)
                print(f"FAIL {case.name}: {exc}", flush=True)
            else:
                outcome = "rejected" if case.rejection else f"accepted with r={case.parameter}"
                print(f"PASS {case.name}: {outcome}", flush=True)
    if not args.cases:
        run_matroid_data_checks(project)
    assert board.read_bytes() == before, "The real leaderboard changed during smoke tests"
    print(f"{len(selected) - len(failures)}/{len(selected)} smoke tests passed; leaderboard unchanged.")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
