# ten-challenges-submissions

Submission queue and leaderboard for the
[ten-challenges](https://github.com/TenChallenges/ten-challenges) parametrized
problem set.

## How to submit

There are two submission forms, picked from the chooser screen by what
you're settling:

- **[Submit a proof for a specific r](../../issues/new?template=submit-specific.yml)** —
  you've shown the theorem holds at one concrete value of `r`. You
  pick the problem and the value of `r`.
- **[Submit a proof of the universal conjecture](../../issues/new?template=submit-universal.yml)** —
  you've settled the ∀r form, either by proving it or by exhibiting a
  counterexample. You pick the problem and whether you're proving or
  disproving.

Either way, you submit a **GitHub repository URL** (a single field on
the form). Your repo — public, or **private** with the
`ten-challenges-bot` App installed (see "Keeping your proof private"
below) — must contain:

```
Submission/
  Main.lean        # defines `r` and `theorem challenge_N` inside `namespace Submission`
  <Helper>.lean    # optional; imported as `import Submission.<Helper>`
```

A single-file proof is just a repo with everything in `Main.lean`. CI
shallow-clones the `main` branch, runs the content checks (strips
comments, rejects bare `sorry` / `axiom` declarations) over every file
under `Submission/`, splices the directory into the canonical checkout
as a sibling Lake lib of `Challenges`, and builds.

The build generates a per-problem `Challenges/Check.lean` that
(1) pins `Submission.challenge_N` to the canonical signature
(substituting `Submission.r` for `r`), and (2) asserts via
`Lean.collectAxioms` that the proof only depends on Lean's three
foundational axioms (`propext`, `Classical.choice`, `Quot.sound`). If
either check fails, the issue is closed with a generic reason (the full
build log stays in the maintainer-visible workflow run, not in the
issue). On success, an entry is appended to `site-data/leaderboard.json`
— **your proof source itself is never published** (see below).

The submission forms also request permission for future compatibility edits.
See the [maintenance policy](docs/maintenance-policy.md) for its scope and the
procedure for Lean and library upgrades.

## Keeping your proof private

You can keep your proof source hidden from other contestants while still
appearing on the leaderboard:

1. Host your proof in a **private** GitHub repo.
2. Install the **`ten-challenges-bot`** GitHub App on that repo so the CI
   can clone it: **<https://github.com/apps/ten-challenges-bot>**.
3. **Verify the install** After
   installing, go to your repo's **Settings → GitHub Apps** (or
   <https://github.com/settings/installations>). `ten-challenges-bot` should
   be listed, and if you chose **"Only select repositories"** during install,
   your submission repo must be ticked under its *Repository access*. The app
   needs only **Contents: Read** — nothing else.

If CI replies *"Could not clone the (private) repo …"*, the App isn't
installed on (or granted access to) that repo. Fix the access above and
**re-open the issue** to retry. Public repos don't need the App at all — CI
clones them anonymously.

What is and isn't visible:

- **Other contestants** see only your leaderboard row (nickname, name,
  problem, claim, parameter). For a private submission `source_url` is
  empty — there is no link to your code.
- **You** keep your code in your own private repo.
- **Maintainers** can see it: the CI reads it to verify the proof, and an
  age-encrypted copy is retained in a private audit repo, decryptable
  only by the maintainers listed in
  [`.audit/recipients.txt`](.audit/recipients.txt). This is the cost of
  server-side verification — see [`docs/security-model.md`](docs/security-model.md), which also
  documents the limits of this confidentiality (it is best-effort).

Once any submission has settled a given (problem, r) pair, later
submissions for the same pair are rejected — both directions are
mathematically closed at that point. (Two submissions for the same `r`
arriving within minutes of each other can both land; we credit ties.)

AI-assisted, human, or hybrid proofs are all fine — we don't ask how
the proof was produced.

## Repository layout

```
.audit/
  recipients.txt           # age recipients for the encrypted audit archive
  README.md
.github/
  ISSUE_TEMPLATE/
    config.yml             # disable blank issues
    submit-specific.yml    # specific-r submission form
    submit-universal.yml   # universal (∀r) submission form
  workflows/
    submission.yml         # evaluate → archive → record → notify
    validate-recipients.yml # lints .audit/recipients.txt
docs/
  audit-archive.md         # encrypted-archive design + decryption
  ci-secrets.md            # GitHub Apps, audit repo, one-time setup
  security-model.md        # confidentiality / threat model
scripts/
  append_leaderboard.py    # appends one entry to site-data/leaderboard.json
  archive_submission.py    # age-encrypts source + pushes to the private audit repo
  generate_check.py        # per-problem signature + axiom shim
site-data/
  leaderboard.json         # public leaderboard; consumed by the React UI
```

Accepted proofs are **no longer** committed in plaintext here. Instead an
age-encrypted copy of every evaluated submission is pushed to the private
`utkuokur/ten-challenges-audit` repo (see `docs/audit-archive.md`).

## Schema of `site-data/leaderboard.json`

```jsonc
{
  "entries": [
    {
      "rank": 1,
      "nickname": "lean_enjoyer",
      "name": "",                // optional, may be ""
      "problem": "challenge_1",  // or "challenge_1_univ" etc
      "claim": "prove",          // or "disprove"
      "parameter": "5",          // or "universal" for ∀r challenges
      "date": "2026-05-30T12:34:56Z",
      "issue": 42,
      "source_url": "https://github.com/me/my-proofs/tree/main",
      "submission_public": true   // false for private submissions; source_url is then ""
    }
  ]
}
```

> The React frontend should treat an empty `source_url` as "no source
> link" (private submission) rather than rendering a broken link.

The React frontend at
[utkuokur/lean-challenge/automated_compile](https://github.com/utkuokur/lean-challenge/tree/universal-challenges/automated_compile)
fetches this file directly via
`raw.githubusercontent.com/.../site-data/leaderboard.json` and renders
the table.

## Required setup and secrets

Private submissions + the encrypted audit archive need one-time setup
beyond the default `GITHUB_TOKEN`. The full checklist is in
[`docs/ci-secrets.md`](docs/ci-secrets.md); in brief:

- **`ten-challenges-bot`** GitHub App (Contents: Read, installable on any
  account) — lets CI clone private submission repos. Secrets:
  `LEAN_CHALLENGE_BOT_APP_ID`, `LEAN_CHALLENGE_BOT_PRIVATE_KEY`.
- **`ten-challenges-archiver`** GitHub App (Contents: R/W, on this
  account only) — pushes the encrypted archive. Secrets:
  `LEAN_CHALLENGE_ARCHIVER_APP_ID`, `LEAN_CHALLENGE_ARCHIVER_PRIVATE_KEY`.
- a **private `utkuokur/ten-challenges-audit`** repo, and at least one
  age recipient public key in `.audit/recipients.txt`.

The default `GITHUB_TOKEN` still covers the leaderboard commit
(`contents: write`) and issue comment/close (`issues: write`) in the
`record` job — no recorder App or PAT is needed because this repo has no
branch protection and hosts its own leaderboard.

**Until the setup above is complete the pipeline is intentionally down**
(the encrypt step fails on an empty recipients file, and `record` is
gated on a successful archive).
