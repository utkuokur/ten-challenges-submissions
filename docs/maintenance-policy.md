# Proof compatibility maintenance

Policy version: 2026-09-20.

The submission form asks you to confirm:

> I have the necessary rights to authorize the competition maintainers to retain and modify copies of my submission solely for compatibility with future Lean and library versions, preserving authorship, the mathematical claim, and its public or private status.

This permission covers compatibility changes such as updated imports, renamed
lemmas, and adapted proof scripts. It does not transfer ownership or authorize
changing the mathematical claim, publishing a private proof, or relicensing
third-party code. Existing license and attribution requirements still apply.
Maintainers work on copies; this permission does not grant write access to your
repository. Compatibility maintenance is best-effort, not a guarantee that every
proof can be ported.

For new submissions, the checked acknowledgement, policy version, and issue
author are retained with the audit record. This permission does not apply
retroactively: before porting an older submission, obtain the author's permission
or establish that its existing license permits the intended changes.

## Upgrade procedure

1. Keep a fixed, announced Lean toolchain and dependency manifest for each
   competition round. An older toolchain does not invalidate a checked proof.
2. Preserve the original submitted source and its accepted result. Before
   changing the environment, retain the canonical repository commit,
   `lean-toolchain`, and `lake-manifest.json` used for that result. For existing
   records, recover these from the original evaluation run before porting.
3. Upgrade Lean and dependencies together on a separate branch. Port authorized
   copies of accepted submissions and rerun the signature and axiom checks.
   Review universe parameters and mathematical definitions as well as whether
   the files compile.
4. Record the compatibility edits and their environment separately from the
   original submission. Preserve the original author, credit, and privacy status;
   a failed port does not cancel an earlier accepted result.
5. Announce a successful upgrade before using it for new submissions. Keep a
   tagged copy of the old environment available for reproducing earlier results.
