import json
import tempfile
import unittest
from pathlib import Path
from scripts.politica_kit import PolicyError, count_review_rounds, load_policy, validate_rounds

class T(unittest.TestCase):
    def test_rounds_0_3_4_and_deduplication(self):
        self.assertEqual(count_review_rounds([]), 0)
        three = [
            json.dumps({"id": i, "user": {"type": "Bot", "login": "review-bot"}})
            for i in (1, 2, 3)
        ]
        self.assertEqual(count_review_rounds(three), 3)
        self.assertEqual(count_review_rounds(three + [three[-1]]), 3)
        validate_rounds(3, 3)
        with self.assertRaises(PolicyError):
            validate_rounds(4, 3)

    def test_policy_is_confined_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"version": 1, "review_round_limit": 3, "decisions": []}
            (root / "decisiones.yml").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_policy(Path("decisiones.yml"), root=root)["version"], 1)
            with self.assertRaises(PolicyError):
                load_policy(Path("../decisiones.yml"), root=root)
