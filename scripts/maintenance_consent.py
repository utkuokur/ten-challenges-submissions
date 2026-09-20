"""Capture the explicit compatibility-maintenance permission in an issue form."""
import re

POLICY_VERSION = "2026-09-21"
CONSENT_TEXT = (
    "I authorize the competition maintainers to retain "
    "and modify copies of my submission solely for compatibility with future Lean "
    "and library versions, preserving authorship, the mathematical claim, and its "
    "public or private status."
)
ACKNOWLEDGEMENTS_TEXT = (
    "I understand the CI will shallow-clone the repository above and run `lake build`. "
    "I understand my nickname, name, problem, claim, and parameter will be published "
    "on the public leaderboard. I understand that an encrypted copy of my submission "
    "source is retained indefinitely in a private audit repository, decryptable only "
    "by the maintainers, for soundness auditing and compatibility maintenance. "
    + CONSENT_TEXT
)


def read_consent(body: str, issue_author: str) -> dict:
    field = re.search(r"^### Acknowledgements\s*\n(.*?)(?=^### |\Z)", body, re.M | re.S)
    if not field or not re.search(
        r"^- \[[xX]\] " + re.escape(ACKNOWLEDGEMENTS_TEXT) + r"\s*$", field[1], re.M
    ):
        raise ValueError("Please check the compatibility-maintenance permission in the submission form.")
    return {"policy_version": POLICY_VERSION, "permission": CONSENT_TEXT,
            "issue_author": issue_author}
