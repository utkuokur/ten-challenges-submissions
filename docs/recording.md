# Recording submissions

Proofs are evaluated in parallel. The separate **Record submissions** workflow
handles leaderboard writes one at a time, in issue-opening order. It wakes
when an evaluation finishes, an issue closes/reopens, or a maintainer manually
runs it. Every invocation considers the whole open queue; replacing a pending
wake-up cannot lose an individual result.

An earlier unfinished evaluation pauses recording. The recorder exits instead
of holding a runner while waiting. When that evaluation finishes, another
invocation handles it and any later ready results. GitHub's second-resolution
opening timestamp determines priority, with issue number breaking ties.

Only successful evaluation and archival jobs from the current run attempt,
with that attempt's verified metadata artifact, permit recording. No source
or executable artifact is downloaded to the recorder. The write-capable
recorder checks out trusted `main`, never the submission or an artifact's code.

For each issue, the recorder reads the current remote leaderboard and checks
for a duplicate. An existing result for the same issue is a no-op; a different
issue for the same problem and parameter is rejected. Challenge 2 records
pairs `(r, B)`: a new pair is rejected when an earlier entry has `r' >= r` and
`B' <= B`, since monotonicity already implies it; a new result must raise `r`
or lower `B` for the same `r`. New ranks follow the
largest existing rank, including when older entries have been deleted. Private
repository links are omitted from the public entry.

For Challenges 6 and 10, the Lean parameter reporter normalizes the standard
notation built from natural numbers, omega, addition, multiplication, and
exponentiation. It uses Mathlib's `NONote` arithmetic, after checking that each
elaborated operation is the standard ordinal operation. Equivalent supported
expressions have the same display and therefore the same duplicate key (for
example, omega + omega and omega * 2). A structured `ordinal_cnf` field also lets
the website compare these values exactly, without floating-point conversion.
The overall leaderboard follows recording order. Challenge tabs display larger
natural numbers or recognized ordinals first, with universal results at the top
and recording order breaking ties. Unsupported ordinal values appear in a
separate unranked group, in recording order; placing them there does not assert
that they are smaller. Displayed ranks are positions within the ranked group
of that tab; the stored recording ranks remain unchanged.
The ordinal challenge summaries show “latest r”: the most recently recorded
proved parameter, whether or not it has a supported comparison key. A universal
proof is displayed as “all r”. Natural-number summaries show the largest proved
parameter.

Other ordinals remain accepted and retain their Lean expression for manual
comparison. Resource limits also fall back to that display: expression and
normal-form depth are capped at 128, the normal form at 4096 terms (including
exponents), coefficient binary logarithms at 4096, and
the finite tail of an exponent at 1024. These are reporting limits, not changes
to the challenge statements. Existing entries without a normal form are not
silently reinterpreted or assumed to be smaller.

There is **one save attempt and no automatic save retry**. A durable bot comment
marks the attempt before saving. On success the comment is updated and the
issue closed. A duplicate is closed with its earlier issue number. A recording
or connection failure is closed with an explanation and instructions to check
the leaderboard and, if necessary, open a new issue. A failed push response can
also mean the save arrived but its confirmation did not; the message does not
incorrectly assert that the result is absent.

If the runner stops or GitHub's issue API is unavailable, posting or closing
cannot finish immediately. A later recorder invocation can finish the comment
and closure, but the attempt marker prevents a second save. Maintainers can use
**Run workflow** for this recovery. Reopened issues are closed again; contestants
must start a new issue to receive another evaluation and a new place in line.

The old per-evaluation record job must not run alongside this recorder. Deploy
while no submission evaluations are active. The local tests exercise the queue,
Git operations, and notification recovery without sending any GitHub requests.
