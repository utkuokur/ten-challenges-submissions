"""Checks for the normal-form data passed from Lean to the leaderboard."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from append_leaderboard import decide
from ordinal_parameters import display_cnf, parse_cnf
from verified_metadata import resolve_metadata

ONE = [[[], "1"]]
OMEGA = [[ONE, "1"]]
TWICE = [[ONE, "2"]]


class OrdinalParameterTests(unittest.TestCase):
    def test_normal_forms_compare_mathematically(self):
        chain = [[], ONE, [[[], "9007199254740993"]], OMEGA,
                 [[ONE, "1"], [[], "1"]], TWICE, [[[[[], "2"]], "1"]], [[OMEGA, "1"]]]
        parsed = [parse_cnf(c) for c in chain]
        self.assertTrue(all(a < b for a, b in zip(parsed, parsed[1:])))
        self.assertEqual(display_cnf(parse_cnf(TWICE)), "ω*2")

    def test_invalid_normal_forms_are_rejected(self):
        for value in (None, {}, [[[], "0"]], [[[], "01"]], [[[], 3]],
                      [[[], "-1"]], [[[], "١"]], [[[], "2"], [ONE, "1"]],
                      [[ONE, "1"], [ONE, "2"]]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_cnf(value)

    def test_only_verified_keys_survive_and_must_match_display(self):
        metadata = {"problem_id": "challenge_6", "parameter": "100", "ordinal_cnf": ONE}
        checked = {"problem_id": "challenge_6", "parameter": "ω*2", "ordinal_cnf": TWICE}
        result = resolve_metadata(metadata, checked, {})
        self.assertEqual(result["ordinal_cnf"], TWICE)
        self.assertEqual(result["claimed_parameter"], "100")
        self.assertNotIn("ordinal_cnf", resolve_metadata(metadata, {
            "problem_id": "challenge_6", "parameter": "Ordinal.omega 1"}, {}))
        with self.assertRaises(ValueError):
            resolve_metadata(metadata, {**checked, "parameter": "ω"}, {})

    def test_record_keeps_key_and_duplicate_does_not_consume_another_rank(self):
        metadata = {"issue": 1, "problem_id": "challenge_10", "parameter": "ω*2",
                    "ordinal_cnf": TWICE, "claim": "prove", "nickname": "Test",
                    "submission_public": False}
        first = decide({"entries": []}, metadata)
        self.assertEqual(first.entry["ordinal_cnf"], TWICE)
        duplicate = decide({"entries": [first.entry]}, {**metadata, "issue": 2})
        self.assertEqual(duplicate.status, "duplicate")


if __name__ == "__main__":
    unittest.main()
