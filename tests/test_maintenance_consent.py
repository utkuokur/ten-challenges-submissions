"""Check opt-in permission and its retention in the audit record."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import archive_submission
from maintenance_consent import ACKNOWLEDGEMENTS_TEXT, CONSENT_TEXT, POLICY_VERSION, read_consent
import write_metadata


class MaintenanceConsentTests(unittest.TestCase):
    def test_checked_permission_records_exact_terms_and_author(self):
        for marker in ("x", "X"):
            body = f"### Acknowledgements\n\n- [{marker}] {ACKNOWLEDGEMENTS_TEXT}\n"
            self.assertEqual(read_consent(body, "submitter"), {
                "policy_version": POLICY_VERSION, "permission": CONSENT_TEXT,
                "issue_author": "submitter",
            })

    def test_missing_unchecked_or_changed_permission_is_rejected(self):
        for body in (f"### Acknowledgements\n- [x] {CONSENT_TEXT}", "", f"### Acknowledgements\n- [ ] {ACKNOWLEDGEMENTS_TEXT}",
                     f"### Other field\n- [x] {ACKNOWLEDGEMENTS_TEXT}",
                     "### Acknowledgements\n- [x] I authorize publication of my proof."):
            with self.subTest(body=body), self.assertRaises(ValueError):
                read_consent(body, "submitter")

    def test_both_forms_require_the_terms_the_parser_recognizes(self):
        for name in ("submit-specific.yml", "submit-universal.yml"):
            text = (ROOT / ".github/ISSUE_TEMPLATE" / name).read_text()
            self.assertEqual(text.split("    id: acknowledgements\n", 1)[1].count("- label:"), 1)
            self.assertIn(f"- label: {ACKNOWLEDGEMENTS_TEXT}\n          required: true", text)
        self.assertIn(CONSENT_TEXT, (ROOT / "docs/maintenance-policy.md").read_text())

    def test_consent_survives_metadata_and_archive(self):
        consent = read_consent(f"### Acknowledgements\n- [x] {ACKNOWLEDGEMENTS_TEXT}", "submitter")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = root / "metadata.json"
            env = {
                "ISSUE": "1", "PROBLEM_ID": "challenge_6", "PARAMETER": "0",
                "CLAIM": "prove", "NICKNAME": "submitter", "MODULE": "challenge_06",
                "REPO_URL": "https://github.com/submitter/proof", "REPO_REF": "main",
                "SUBMISSION_KIND": "github_repo", "SUBMISSION_REPO": "submitter/proof",
                "SUBMISSION_REF": "a" * 40, "SUBMISSION_PUBLIC": "false",
                "MAINTENANCE_CONSENT": json.dumps(consent),
            }
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(write_metadata.main([str(metadata)]), 0)
            self.assertEqual(json.loads(metadata.read_text())["maintenance_consent"], consent)
            source = root / "source.tar.gz"
            source.write_bytes(b"test submission archive")
            recipients = root / "recipients.txt"
            recipients.write_text("test-recipient\n")

            def fake_age(command, **kwargs):
                Path(command[command.index("--output") + 1]).write_bytes(
                    b"age-encryption.org/v1\ntest ciphertext\n"
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            args = argparse.Namespace(source_tar=source, metadata=metadata,
                                      recipients=recipients, output_dir=root / "out")
            with patch.object(archive_submission.subprocess, "run", side_effect=fake_age):
                self.assertEqual(archive_submission._encrypt(args), 0)
            sidecar = json.loads((args.output_dir / "sidecar.partial.json").read_text())
            self.assertEqual(sidecar["maintenance_consent"], consent)
            self.assertFalse(sidecar["submission_public"])


if __name__ == "__main__":
    unittest.main()
