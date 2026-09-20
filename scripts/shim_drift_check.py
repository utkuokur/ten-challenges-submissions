#!/usr/bin/env python3
"""Detect drift between the canonical challenge statements
(TenChallenges/ten-challenges) and the signature-shim templates in
generate_check.py.

The two repos hold the same theorem signatures in two places: the canonical
`Challenges/challenge_NN*.lean` files, and the `CHECKS` templates here. They
must move in lockstep; this script fails loudly when they don't.

For every problem id in CHECKS, the script

1. writes a mock submission module into the canonical checkout that simply
   re-exports the canonical (sorry-backed) theorem::

       import Challenges.challenge_NN
       namespace Submission
       def r := _root_.r                       -- parametrized problems only
       def L := _root_.L                       -- challenge_2 only
       def challenge_N := @_root_.challenge_N  -- canonical qualified name
       end Submission

   The defs carry no type ascriptions, so `Submission.challenge_N` has
   *exactly* the canonical theorem's type, with `Submission.r` (and `L`)
   definitionally equal to the canonical parameters. The `@` keeps Lean from
   eagerly instantiating leading implicit binders. The shim's `example`
   therefore typechecks iff the template's signature agrees with the
   canonical statement — which is precisely the drift property.

2. generates Check.lean from the template (the same `render_check` code
   path CI uses), and

3. runs `lake build` on it. Expected outcome: the axiom gate rejects
   `sorryAx` (the canonical theorem is sorry-backed by design). For
   Challenge 2, the data gate must also reject the canonical placeholder
   `L`. Any other error means the template has drifted from the canon.
   A successful build is impossible and reported as a gate failure.

Usage (from a checkout of ten-challenges-submissions, with the canonical
repo checked out next to it)::

    python3 scripts/shim_drift_check.py --project ../lean-challenges \
        [--problems challenge_1 challenge_9_univ ...]
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from generate_check import CHECKS, problem_number, render_check  # noqa: E402


def canonical_name(problem_id: str) -> str:
    """Fully qualified name of the canonical theorem for `problem_id`.

    Since the July 2026 naming harmonization, every canonical theorem is
    root-level and named exactly like its problem id: `challenge_N`,
    `challenge_N_univ`, `challenge_N_disprove` (no `ChallengeNN`/`Disprove`
    namespaces). A wrong entry here fails loudly in step 1 as an unknown
    identifier — update this function if a canonical theorem ever moves."""
    return f"_root_.{problem_id}"


def mock_defs(problem_id: str) -> list[str]:
    """Submitter-parameter defs the mock must re-export."""
    if problem_id.endswith(("_univ", "_disprove")):
        return []
    defs = ["def r := _root_.r"]
    if problem_id == "challenge_2":
        # challenge_2 solvers also exhibit the excluded-minor list `L`. The
        # prime-power witnesses `p`/`m` are existentially bound inside the
        # statement (explicit-list form), so there are no top-level defs to
        # re-export for them.
        defs += ["def L := _root_.L"]
    return defs


def canonical_module(problem_id: str) -> str:
    n = problem_number(problem_id)
    suffix = problem_id.removeprefix(f"challenge_{n}")
    return f"challenge_{n:02d}{suffix}"


def run_one(project: pathlib.Path, problem_id: str) -> tuple[bool, str]:
    """Returns (passed, detail)."""
    n = problem_number(problem_id)
    module = canonical_module(problem_id)
    sub = project / "Challenges" / f"DriftSub_{problem_id}.lean"
    chk = project / "Challenges" / f"DriftCheck_{problem_id}.lean"

    lines = [f"import Challenges.{module}", "", "namespace Submission", ""]
    lines += mock_defs(problem_id)
    lines += [f"def challenge_{n} := @{canonical_name(problem_id)}",
              "", "end Submission", ""]
    sub.write_text("\n".join(lines), encoding="utf-8")
    chk.write_text(
        render_check(problem_id, f"Challenges.DriftSub_{problem_id}"),
        encoding="utf-8")

    try:
        proc = subprocess.run(
            ["lake", "build", f"Challenges.DriftCheck_{problem_id}"],
            cwd=project, capture_output=True, text=True, timeout=5400)
        out = proc.stdout + proc.stderr
        # Lake's trailer lines are not diagnostics; everything else marked
        # `error:` is.
        real_errors = [
            ln for ln in out.splitlines()
            if "error:" in ln
            and "Lean exited with code" not in ln
            and "build failed" not in ln
        ]
        if proc.returncode == 0:
            return False, ("shim built successfully — impossible for a "
                           "sorry-backed canonical theorem; the axiom gate "
                           "is broken")
        if not real_errors:
            return False, ("build failed with no diagnostic (infrastructure "
                           "problem?); last output:\n"
                           + "\n".join(out.splitlines()[-15:]))
        expected = ["non-permitted axiom `sorryAx`"]
        if problem_id == "challenge_2":
            expected.append("Submission.L must reduce to explicit finite matroid data.")
        bad = [ln for ln in real_errors
               if not any(message in ln for message in expected)]
        if bad:
            return False, ("template drifted from the canonical statement "
                           "(or the mock failed to elaborate):\n"
                           + "\n".join(bad[:10]))
        missing = [message for message in expected
                   if not any(message in ln for ln in real_errors)]
        if missing:
            return False, "expected rejection missing: " + "; ".join(missing)
        return True, "signature matches (placeholder gates reject, as designed)"
    finally:
        sub.unlink(missing_ok=True)
        chk.unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True,
                   help="path to a checkout of TenChallenges/ten-challenges")
    p.add_argument("--problems", nargs="*", default=sorted(CHECKS),
                   help="subset of problem ids (default: all)")
    args = p.parse_args()
    project = pathlib.Path(args.project).resolve()
    if not (project / "Challenges").is_dir():
        sys.exit(f"{project} does not look like a lean-challenges checkout")

    unknown = [pid for pid in args.problems if pid not in CHECKS]
    if unknown:
        sys.exit(f"Unknown problem ids: {unknown}")

    failures: list[str] = []
    for pid in args.problems:
        ok, detail = run_one(project, pid)
        status = "PASS " if ok else "DRIFT"
        print(f"[{status}] {pid}: {detail}", flush=True)
        if not ok:
            failures.append(pid)

    print()
    if failures:
        print(f"{len(failures)}/{len(args.problems)} shim(s) out of sync: "
              f"{', '.join(failures)}")
        print("Update the matching CHECKS template(s) in "
              "scripts/generate_check.py (or fix canonical_name/mock_defs "
              "in this script if a theorem or parameter moved).")
        return 1
    print(f"All {len(args.problems)} shim(s) in sync with the canon.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
