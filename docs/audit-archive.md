# Audit archive

Adapted from `leanprover/lean-eval-submissions`'s `docs/audit-archive.md`.

## Why

A private-repo submission exists only in the submitter's account; if they
delete the repo, rotate a tag, or rewrite history, the exact bytes the CI
evaluated are gone. That defeats post-hoc auditability — a soundness
question about an older accepted proof would have no recoverable artifact.

The archive makes every evaluated submission recoverable indefinitely,
while keeping the source bytes inaccessible to anyone outside a small
maintainer set. It is the mechanism that lets *maintainers* still see a
submission's source while *other contestants* cannot.

## Design

One encrypted tarball plus one unencrypted JSON sidecar are pushed to the
**private** `utkuokur/ten-challenges-audit` repository per submission,
immediately after evaluation.

```
audit/
  YYYY/
    MM/
      issue{N}-{problem}-{param}.tar.age   # age-encrypted gzipped tar of source
      issue{N}-{problem}-{param}.json      # sidecar (issue, problem, verdict, digests)
```

The submission-issue number is globally unique in this repo, so it alone
makes the path unique; `{problem}` and `{param}` are appended for
human-readability. The tarball is the same `source.tar.gz` the evaluator
saw: the evaluated `Submission/` tree from the submitted repo.

For submissions made under the [maintenance policy](maintenance-policy.md), the
sidecar also records the checked compatibility permission, its policy version,
and the GitHub issue author. Older records without that permission are not
automatically authorized for maintenance.

Encryption uses [`age`](https://github.com/FiloSottile/age) with the
recipients in [`.audit/recipients.txt`](../.audit/recipients.txt). The
sidecar records the SHA-256 of both the plaintext tar and the ciphertext
so an operator can verify integrity at decrypt time (against the
plaintext digest) and without decrypting (against the ciphertext digest).

## Workflow integration

Two pieces inside `submission.yml`:

1. **Size cap + encrypt**, in the `evaluate` job, right after fetch and
   *before* the expensive `lake build`. The fetched `source.tar.gz` is
   rejected if it exceeds 10 MiB. Otherwise `scripts/archive_submission.py
   encrypt` runs `age --recipients-file .audit/recipients.txt` over the
   tar and uploads only the **ciphertext + sidecar** as an artifact. The
   plaintext is read for evaluation in this same job but never crosses
   the job boundary.

2. **Archive job**, runs after `evaluate` on a fresh runner (the
   write-capable archiver token must never be co-resident with untrusted
   Lean). It mints an installation token for the `ten-challenges-archiver`
   App (scoped only to `ten-challenges-audit`), merges in the build
   verdict (`pass`/`fail`), and uploads both objects via the GitHub
   Contents API. **`record` (the leaderboard updater) is gated on this
   job succeeding**, so a leaderboard entry always implies a durable
   encrypted archive of the source.

The Contents API upload is **idempotent**: a rerun that re-encounters an
existing object at the predicted path compares Git blob SHAs and treats a
match as success; a mismatch fails hard as an operator-investigatable
collision.

## Threat model

The thing the design defends against: **the source bytes of any private
submission leaking out of the maintainer set.**

- **Public-repo artifacts are downloadable by any authenticated user** —
  which is why the plaintext source is *never* uploaded as an artifact
  (only the ciphertext is, and that is useless without a recipient
  private key), and why fetch + build share one job (see `security-model.md`).
- **Runners that elaborate untrusted Lean can be compromised.** The
  archiver App's write token is minted only in the `archive` job, on a
  separate runner that never touched the submitted source.
- **App permission scoping.** `ten-challenges-archiver` has Contents:
  write only on `ten-challenges-audit`. `ten-challenges-bot` (which
  reads contributor repos) stays Contents: Read only.

### Not in the threat model

- **Recipient-private-key custody is the recipient's problem.** Lose
  every private key and the corresponding archived entries become
  permanently undecryptable.
- **Anonymity.** Submissions are not anonymous — the issue, the
  leaderboard row, and the sidecar all carry the nickname. The archive's
  guarantee is about *source bytes*, not participation.

## Adding or removing recipients

Edit `.audit/recipients.txt` via PR. The `validate-recipients.yml`
workflow lints each line by encrypting a fixture to it; a malformed line
cannot reach `main`. Once merged, every subsequent submission is
encrypted to the new recipient set. Pre-existing ciphertexts retain the
recipient set they were encrypted with — re-encrypting historical entries
is a manual operation requiring decryption first.

## Decryption procedure

```bash
# 1. Install age.
brew install age            # or: apt install age, or cargo install rage

# 2. Decrypt with one of the private keys whose public half is in
#    recipients.txt (SSH key or age key both work).
age -d -i ~/.ssh/id_ed25519 \
  -o /tmp/source.tar.gz \
  audit/2026/06/issue42-challenge_1-5.tar.age

# 3. Verify against the sidecar's plaintext digest.
sha256sum /tmp/source.tar.gz   # match sidecar.sha256_plaintext_tar

# 4. Extract.
mkdir /tmp/source && tar -xzf /tmp/source.tar.gz -C /tmp/source
```

Do a decrypt drill periodically (annually is plenty) so recipient private
keys are known to still exist on a reachable device.

## Size cap

The 10 MiB cap is on the compressed gzipped tar of the fetched source.
The archive is permanent, so the cap keeps it bounded; current
submissions are well under 1 MiB. A submission over the cap is rejected
at the workflow level — the issue is commented and closed, no evaluation
runs, and no audit entry is created.
