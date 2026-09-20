#!/usr/bin/env python3
"""Generate Challenges/Check.lean for a given problem_id.

The Check.lean file checks the following about the submission:

1. *Signature.* `Submission.challenge_N` has the exact canonical type from
   `Challenges/challenge_NN.lean` (with the canonical parameter `r`
   substituted by `Submission.r` for non-universal problems). If the
   theorem has the wrong signature, `lake build Challenges.Check` fails
   with a type error. Closes the `theorem challenge_N : True := trivial`
   bypass.

2. *Axioms.* `Submission.challenge_N` transitively depends only on Lean's
   three foundational axioms (`propext`, `Classical.choice`, `Quot.sound`).
   Any other axiom — `sorryAx`, user-declared axioms, anything reached via
   the kernel — causes the build to fail. Closes bypasses that slip past
   the textual `sorry`/`axiom` greps (most notably `theorem ... := sorryAx _ _`,
   which the source-level grep `(^|[^[:alnum:]_])sorry([^[:alnum:]_]|$)`
   does not match because `sorryAx` is followed by `A`).

3. *Explicit data (Challenge 2).* `Submission.L` reduces to finite matroid
   data, including every ground-set and independent-set entry. A list
   specified only through classical choice does not meet this requirement.

The CLI also exports the checked parameter to `.lake/verified-parameter.json`.
CI consumes it only after a successful build, replacing the issue's claimed
parameter before duplicate checks and leaderboard publication.

Usage:
    python3 generate_check.py --problem challenge_1 --output Challenges/Check.lean
"""
from __future__ import annotations

import argparse
import json
import re
import sys


# Per-problem check templates. Each maps from problem_id (as it appears in
# the issue dropdown / GitHub issue) to a complete Lean file. The check
#
#   1. imports `Challenges.challenge_NN` to bring helper definitions
#      (Minor, hadwigerNumber, IsGFRepresentable, etc.) into scope, and
#   2. imports `Challenges.Submission` to access the user's proof, and
#   3. writes an `example` whose type is the canonical theorem signature
#      with `r` substituted by `Submission.r`, body `Submission.challenge_N`.
#
# If `Submission.challenge_N` has the wrong type, the application fails to
# typecheck and `lake build Challenges.Check` exits non-zero.

CHECKS: dict[str, str] = {
    # ─── Parametrized challenges ──────────────────────────────────────
    "challenge_1": r"""
import Challenges.challenge_01
import Challenges.Submission

example : statement_01 Submission.r :=
  Submission.challenge_1
""",
    "challenge_2": r"""
import Challenges.challenge_02
import Challenges.Submission

universe u

example : statement_02.{u} Submission.r Submission.L :=
  Submission.challenge_2
""",
    "challenge_3": r"""
import Challenges.challenge_03
import Challenges.Submission

example : statement_03 Submission.r :=
  Submission.challenge_3
""",
    "challenge_4": r"""
import Challenges.challenge_04
import Challenges.Submission

example : statement_04 Submission.r :=
  Submission.challenge_4
""",
    "challenge_5": r"""
import Challenges.challenge_05
import Challenges.Submission

example : statement_05 Submission.r :=
  Submission.challenge_5
""",
    "challenge_6": r"""
import Challenges.challenge_06
import Challenges.Submission

example : statement_06 Submission.r :=
  Submission.challenge_6
""",
    "challenge_7": r"""
import Challenges.challenge_07
import Challenges.Submission

example : statement_07 Submission.r :=
  Submission.challenge_7
""",
    "challenge_8": r"""
import Challenges.challenge_08
import Challenges.Submission

universe u

example : statement_08.{u} Submission.r :=
  Submission.challenge_8
""",
    "challenge_9": r"""
import Challenges.challenge_09
import Challenges.Submission

universe u

example : statement_09.{u} Submission.r :=
  Submission.challenge_9
""",
    "challenge_10": r"""
import Challenges.challenge_10
import Challenges.Submission

example :
    statement_10.{u, v}
      (Submission.r : Ordinal.{v}) :=
  Submission.challenge_10
""",

    # ─── Universal challenges (∀r built into the theorem) ──────────────
    "challenge_1_univ": r"""
import Challenges.challenge_01_univ
import Challenges.Submission

example : ∀ r : ℕ, statement_01 r :=
  Submission.challenge_1
""",
    # challenge_2 has no _univ slot: its universal form is the
    # Geelen–Gerards–Whittle THEOREM, and the explicit-list challenge is the
    # single (parametrized) statement.
    "challenge_3_univ": r"""
import Challenges.challenge_03_univ
import Challenges.Submission

example : ∀ r : ℕ, statement_03 r :=
  Submission.challenge_3
""",
    "challenge_4_univ": r"""
import Challenges.challenge_04_univ
import Challenges.Submission

example : ∀ r : ℕ, statement_04 r :=
  Submission.challenge_4
""",
    "challenge_5_univ": r"""
import Challenges.challenge_05_univ
import Challenges.Submission

example : ∀ r : ℕ, statement_05 r :=
  Submission.challenge_5
""",
    "challenge_6_univ": r"""
import Challenges.challenge_06_univ
import Challenges.Submission

example : ∀ r : Ordinal, statement_06 r :=
  Submission.challenge_6
""",
    "challenge_7_univ": r"""
import Challenges.challenge_07_univ
import Challenges.Submission

example : ∀ r : ℕ, statement_07 r :=
  Submission.challenge_7
""",
    "challenge_8_univ": r"""
import Challenges.challenge_08_univ
import Challenges.Submission

universe u

example : ∀ r : ℕ, statement_08.{u} r :=
  Submission.challenge_8
""",
    "challenge_9_univ": r"""
import Challenges.challenge_09_univ
import Challenges.Submission

universe u

example : ∀ r : ℕ, statement_09.{u} r :=
  Submission.challenge_9
""",
    "challenge_10_univ": r"""
import Challenges.challenge_10_univ
import Challenges.Submission

universe u v

example : ∀ r : Ordinal.{v}, statement_10.{u, v} r :=
  Submission.challenge_10
""",

    # ─── Universal challenges, disprove direction ─────────────────────
    # The submitter exhibits a counterexample to the universal claim.
    # challenge_2 deliberately has no disprove slot: its universal form is
    # the Geelen–Gerards–Whittle THEOREM, so the negation is unwinnable.
    "challenge_1_disprove": r"""
import Challenges.challenge_01_disprove
import Challenges.Submission

example : ¬ ∀ r : ℕ, statement_01 r :=
  Submission.challenge_1
""",
    "challenge_3_disprove": r"""
import Challenges.challenge_03_disprove
import Challenges.Submission

example : ¬ ∀ r : ℕ, statement_03 r :=
  Submission.challenge_3
""",
    "challenge_4_disprove": r"""
import Challenges.challenge_04_disprove
import Challenges.Submission

example : ¬ ∀ r : ℕ, statement_04 r :=
  Submission.challenge_4
""",
    "challenge_5_disprove": r"""
import Challenges.challenge_05_disprove
import Challenges.Submission

example : ¬ ∀ r : ℕ, statement_05 r :=
  Submission.challenge_5
""",
    "challenge_6_disprove": r"""
import Challenges.challenge_06_disprove
import Challenges.Submission

example : ¬ ∀ r : Ordinal, statement_06 r :=
  Submission.challenge_6
""",
    "challenge_7_disprove": r"""
import Challenges.challenge_07_disprove
import Challenges.Submission

example : ¬ ∀ r : ℕ, statement_07 r :=
  Submission.challenge_7
""",
    "challenge_8_disprove": r"""
import Challenges.challenge_08_disprove
import Challenges.Submission

universe u

example : ¬ ∀ r : ℕ, statement_08.{u} r :=
  Submission.challenge_8
""",
    "challenge_9_disprove": r"""
import Challenges.challenge_09_disprove
import Challenges.Submission

universe u

example : ¬ ∀ r : ℕ, statement_09.{u} r :=
  Submission.challenge_9
""",
    "challenge_10_disprove": r"""
import Challenges.challenge_10_disprove
import Challenges.Submission

universe u v

example : ¬ ∀ r : Ordinal.{v}, statement_10.{u, v} r :=
  Submission.challenge_10
""",
}


# ─── Axiom-check appendix ─────────────────────────────────────────────────
#
# A custom `elab` command that fails the build if the named declaration
# transitively depends on anything outside Lean's three foundational axioms.
# Uses `Lean.collectAxioms`, the same primitive that backs `#print axioms`.
#
# Two pieces are emitted:
#   - `import Lean` (must go *above* the canonical/Submission imports so it
#     stays in the file's import block).
#   - the elaborator definition + the actual invocation, appended after the
#     `example` so the signature check runs first and the axiom check sees
#     a fully-elaborated `Submission.challenge_N`.

AXIOM_CHECK_IMPORT = "import Lean\n"

AXIOM_CHECK_TAIL = r"""
section AxiomCheck
open Lean Elab Command

/-- Build-time check that `n` transitively depends only on Lean's three
foundational axioms. Mirrors `#print axioms` but turns any non-permitted
axiom into a build error instead of stdout output.

Uses `Lean.collectAxioms`, the public function (Lean 4.30, in
`Lean/Util/CollectAxioms.lean`) that backs `#print axioms`. It returns
the axiom array directly via any monad with `MonadEnv`, so calling it
inside `CommandElabM` is straightforward. -/
elab "#assert_canonical_axioms " n:ident : command => do
  let name := n.getId
  unless ((← getEnv).find? name).isSome do
    throwError m!"`{name}` is not defined; cannot check axioms."
  let axs ← Lean.collectAxioms name
  let permitted : List Lean.Name :=
    [``propext, ``Classical.choice, ``Quot.sound]
  for ax in axs do
    unless permitted.contains ax do
      throwError m!"Submission depends on non-permitted axiom `{ax}`.\n\
        Only Lean's foundational axioms \
        (propext, Classical.choice, Quot.sound) are allowed."

end AxiomCheck

-- Suppress Mathlib's `hashCommand` linter (enabled via lakefile's
-- `weak.linter.mathlibStandardSet`) just for this invocation, so the build
-- log stays clean. The linter warns about `#`-commands in library code; we
-- legitimately want one here.
set_option linter.hashCommand false in
#assert_canonical_axioms Submission.challenge_%N%
"""


# Reduce the data using Lean's logical definitions, never compiled evaluation:
# `implemented_by` must not substitute different contents. Proof fields can
# use classical reasoning; only the finite data itself must be concrete.
MATROID_DATA_CHECK = r"""

namespace ExplicitMatroidData
open Lean Meta Elab Command

private def constructorArgs (e : Expr) (name : Name) (arity : Nat) : MetaM (Array Expr) := do
  let e ← withTransparency .all (whnf e)
  unless e.isAppOfArity name arity do
    throwError "Submission.L must reduce to explicit finite matroid data."
  return e.getAppArgs

private partial def checkList (checkEntry : Expr → MetaM Unit) (e : Expr) : MetaM Unit := do
  let e ← withTransparency .all (whnf e)
  if e.isAppOfArity ``List.nil 1 then
    return
  let args ← constructorArgs e ``List.cons 3
  checkEntry args[1]!
  checkList checkEntry args[2]!

private def checkFinset (checkEntry : Expr → MetaM Unit) (e : Expr) : MetaM Unit := do
  let args ← constructorArgs e ``Finset.mk 3
  let quotient ← constructorArgs args[1]! ``Quot.mk 3
  checkList checkEntry quotient[2]!

private partial def checkNat (e : Expr) : MetaM Unit := do
  let e ← withTransparency .all (whnf e)
  if (getRawNatValue? e).isSome || e.isConstOf ``Nat.zero then return
  let args ← constructorArgs e ``Nat.succ 1
  checkNat args[0]!

private def checkMatroid (e : Expr) : MetaM Unit := do
  let args ← constructorArgs e ``FinMatroid.mk 2
  checkFinset checkNat args[0]!
  checkFinset (checkFinset checkNat) args[1]!

elab "#assert_explicit_matroid_data" : command => do
  liftTermElabM do
    checkFinset checkMatroid (← mkConstWithFreshMVarLevels `Submission.L)

end ExplicitMatroidData

set_option linter.hashCommand false in
#assert_explicit_matroid_data
"""


# Consumed only when the entire signature, axiom, and data check succeeds.
# Natural parameters are reduced, not pretty-printed (e.g. 1 + 2 becomes 3).
# Ordinals have no general numeric normal form: expand submission definitions
# and retain the resulting Lean expression, e.g. Ordinal.omega0 + 1.
PARAMETER_REPORT = r"""

open Lean Meta Elab Command in
elab "#export_verified_parameter" : command => do
  let parameter ← liftTermElabM do
    let r ← mkConstWithFreshMVarLevels `Submission.r
    if (← whnf (← inferType r)).isConstOf ``Nat then
      let some n ← getNatValue? (← withTransparency .all (whnf r))
        | throwError "Submission.r must reduce to a concrete natural number for the leaderboard."
      return toString n
    else
      let env ← getEnv
      let value ← deltaExpand r fun name =>
        (`Submission).isPrefixOf name || match env.getModuleIdxFor? name with
        | some i =>
          let moduleName := env.header.moduleNames[i]!
          (`Submission).isPrefixOf moduleName || moduleName == `%MODULE%
        | none => false
      return (← withOptions (fun opts =>
        opts.setBool `pp.fullNames true |>.setBool `pp.universes false
          |>.set `pp.maxDepth (10000 : Nat) |>.set `pp.maxSteps (100000 : Nat))
        (ppExpr value)).pretty
  IO.FS.writeFile ".lake/verified-parameter.json" <|
    (Json.mkObj [("problem_id", Json.str %PROBLEM%),
                 ("parameter", Json.str parameter)]).compress

set_option linter.hashCommand false in
#export_verified_parameter
"""


def parameter_report(problem: str, submission_module: str) -> str:
    if problem.endswith(("_univ", "_disprove")):
        report = json.dumps({"problem_id": problem, "parameter": "universal"})
        return '\nrun_cmd Lean.Elab.Command.liftTermElabM do\n' + (
            '  IO.FS.writeFile ".lake/verified-parameter.json" '
            + json.dumps(report) + '\n'
        )
    return PARAMETER_REPORT.replace("%MODULE%", submission_module).replace(
        "%PROBLEM%", json.dumps(problem)
    )


def problem_number(problem_id: str) -> int:
    """Extract the leading numeric component of a problem id.

    `challenge_1` -> 1, `challenge_10_disprove` -> 10. The user's
    theorem is always named `Submission.challenge_<N>` regardless of the
    univ/disprove suffix, because the suffix only selects which canonical
    file we pin the signature against.
    """
    m = re.match(r"^challenge_(\d+)(?:_univ|_disprove)?$", problem_id)
    if not m:
        sys.exit(f"Cannot extract problem number from {problem_id!r}")
    return int(m.group(1))


def render_check(problem: str, submission_module: str, *, report_parameter: bool = False) -> str:
    """Assemble the complete Check.lean body for `problem`, importing the
    user's proof from `submission_module`. Raises KeyError for unknown ids.

    Every template hardcodes `import Challenges.Submission` — rewrite to
    the caller-supplied module so the same templates serve both submission
    flows. We deliberately match the import line as a literal, not a regex,
    so a stray occurrence in an `example` body would not be touched.
    Use `.replace`, not `.format`, for the tail because it contains Lean's
    `m!"...{ax}..."` interpolation — `.format` would try to substitute the
    Lean braces and crash."""
    template = CHECKS[problem].replace(
        "import Challenges.Submission",
        f"import {submission_module}",
    )
    n = problem_number(problem)
    return (
        AXIOM_CHECK_IMPORT
        + template.lstrip("\n")
        + AXIOM_CHECK_TAIL.replace("%N%", str(n))
        + (MATROID_DATA_CHECK if problem == "challenge_2" else "")
        + (parameter_report(problem, submission_module) if report_parameter else "")
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--problem", required=True,
                   help="problem id, e.g. challenge_1 or challenge_3_univ")
    p.add_argument("--output", required=True,
                   help="path to write Check.lean")
    p.add_argument("--submission-module",
                   default="Submission.Main",
                   help="Lean module that defines `Submission.challenge_N`. "
                        "`Submission.Main` for the repo flow (the user's Lake "
                        "lib spliced in at the project root).")
    args = p.parse_args()

    if args.problem not in CHECKS:
        sys.exit(f"Unknown problem id: {args.problem!r}. "
                 f"Known: {', '.join(sorted(CHECKS))}")

    body = render_check(args.problem, args.submission_module, report_parameter=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"Wrote signature + axiom check for {args.problem} to "
          f"{args.output} ({len(body)} bytes, "
          f"submission-module={args.submission_module})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
