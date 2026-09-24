import unittest
from pathlib import Path

W = (Path(__file__).resolve().parents[1] / ".github/workflows/politica.yml").read_text()

class T(unittest.TestCase):
    def test_observed_reviews_and_canonical_policy(self):
        self.assertIn("pr_number:", W)
        self.assertNotIn("review_rounds:", W)
        self.assertIn("/pulls/$PR/reviews", W)
        self.assertIn("python3 .factory/scripts/politica_kit.py", W)
        self.assertNotIn("--file", W)
