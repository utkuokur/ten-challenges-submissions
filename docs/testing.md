# Local submission checks

Run against a checkout of the canonical challenge repository:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/shim_drift_check.py --project ../ten-challenges
python3 tests/integration_verified_parameter.py --project ../ten-challenges
python3 tests/integration_ordinal_parameters.py --project ../ten-challenges
python3 tests/integration_submission_smoke.py --project ../ten-challenges
```

The smoke suite compiles separate submission modules and the production
signature/axiom checker. Successful fixtures cover Challenges 1, 8, and 10,
including a helper module, a computed parameter, and an ordinal parameter.
Rejected fixtures cover incorrect statements, parameters and directions,
extra assumptions, restricted universes, placeholder proofs, and direct or
indirect dependencies on unapproved axioms. Accepted results also exercise
parameter extraction and duplicate detection.

The smoke suite also runs Challenge 2's explicit-data gate independently of
the excluded-minor correctness proof. These data fixtures accept literal and
computed lists, allow classical reasoning in proof fields, and reject data
hidden behind choice at every nesting level. They also check that compiled
implementation overrides cannot replace the logical data. Run just this part
with `python3 tests/integration_explicit_matroids.py --project ../ten-challenges`.

The fixtures are small boundary cases, not new mathematical results. They
exercise the local verifier and metadata handling; they do not test GitHub
authentication, private-repository fetching, encryption, deployment, or
containment of arbitrary code executed by Lean elaborators.

The tests never open issues, call the archive/record jobs, or write the real
leaderboard. Temporary sources and parameter reports are deleted afterward.
The suite also checks that the real leaderboard bytes remain unchanged.
Use `--cases NAME ...` on the smoke script to rerun selected cases.

Both repositories' shim-drift workflows run the smoke suite automatically.

The Python unit suite also checks submission ordering, duplicate rejection,
one-attempt recording failures, and recovery of interrupted notifications.
These tests use fake GitHub responses and temporary local Git repositories;
they do not alter the real leaderboard or create issues. The recording policy
is described in [recording.md](recording.md).

The ordinal integration suite compiles real Lean expressions using Mathlib's
normal ordinal notation. It checks addition, multiplication, natural and ordinal
powers, nested powers, exact large coefficients, aliases, noncommutativity, and
duplicate detection. Unrecognized expressions and customized arithmetic must
not acquire an automatic comparison key. The website's `npm run test:ordinals`
checks normal-form ordering and its fallback for unsupported expressions.
