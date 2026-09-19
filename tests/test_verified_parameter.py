"""Regression checks for proof-derived leaderboard parameters."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from generate_check import parameter_report, render_check
from verified_metadata import resolve_metadata


class VerifiedParameterTests(unittest.TestCase):
    def test_claim_100_proof_3_records_3(self):
        metadata = {"problem_id": "challenge_8", "parameter": "100"}
        report = {"problem_id": "challenge_8", "parameter": "3"}
        # A previous result for the *claimed* parameter must not reject this proof.
        board = {"entries": [{"problem": "challenge_8", "parameter": "100"}]}
        result = resolve_metadata(metadata, report, board)
        self.assertEqual(result["parameter"], "3")
        self.assertEqual(result["claimed_parameter"], "100")

    def test_duplicate_uses_proved_parameter(self):
        with self.assertRaisesRegex(ValueError, "r = 3 has already been settled"):
            resolve_metadata(
                {"problem_id": "challenge_8", "parameter": "100"},
                {"problem_id": "challenge_8", "parameter": "3"},
                {"entries": [{"problem": "challenge_8", "parameter": "3", "issue": 7}]},
            )

    def test_invalid_report_never_falls_back_to_claim(self):
        for report in ({}, {"problem_id": "challenge_1", "parameter": "3"},
                       {"problem_id": "challenge_8", "parameter": "not a number"}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                resolve_metadata({"problem_id": "challenge_8", "parameter": "100"}, report, {})

    def test_ordinal_expression_and_universal(self):
        for problem, parameter in (("challenge_6", "Ordinal.omega0 + 1"),
                                   ("challenge_10", "0"),
                                   ("challenge_8_univ", "universal"),
                                   ("challenge_8_disprove", "universal")):
            with self.subTest(problem=problem):
                result = resolve_metadata(
                    {"problem_id": problem, "parameter": "ignored"},
                    {"problem_id": problem, "parameter": parameter}, {},
                )
                self.assertEqual(result["parameter"], parameter)

    def test_generator_reports_after_signature_and_axiom_checks(self):
        source = render_check("challenge_8", "Submission.Main", report_parameter=True)
        self.assertLess(source.index("example :"), source.index("#export_verified_parameter"))
        self.assertLess(source.index("#assert_canonical_axioms Submission.challenge_8"),
                        source.index("#export_verified_parameter"))
        self.assertNotIn("Submission.r", parameter_report("challenge_8_univ", "Submission.Main"))

    def test_cli_updates_metadata_used_by_leaderboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = root / "metadata.json"
            report = root / "report.json"
            metadata.write_text(json.dumps({"problem_id": "challenge_8", "parameter": "100"}))
            report.write_text(json.dumps({"problem_id": "challenge_8", "parameter": "3"}))
            subprocess.run([sys.executable, str(SCRIPTS / "verified_metadata.py"),
                            "--metadata", str(metadata), "--report", str(report),
                            "--leaderboard", str(root / "leaderboard.json")], check=True)
            self.assertEqual(json.loads(metadata.read_text())["parameter"], "3")
            report.unlink()
            proc = subprocess.run([sys.executable, str(SCRIPTS / "verified_metadata.py"),
                                   "--metadata", str(metadata), "--report", str(report),
                                   "--leaderboard", str(root / "leaderboard.json")],
                                  capture_output=True)
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
