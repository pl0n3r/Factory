import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = (ROOT / ".github/workflows/politica.yml").read_text()
TEMPLATE = (ROOT / "template/.github/workflows/politica.yml").read_text()


class T(unittest.TestCase):
    def test_observed_reviews_and_canonical_policy(self):
        self.assertIn("pr_number:", W)
        self.assertNotIn("review_rounds:", W)
        self.assertIn("/pulls/$PR/reviews", W)
        self.assertIn("python3 .factory/scripts/politica_kit.py", W)
        self.assertNotIn("--file", W)

    def test_required_reviewer_context_is_read_only_and_event_bounded(self):
        self.assertIn("required_review_bot:", W)
        self.assertIn("pull_request|pull_request_review", W)
        self.assertIn("REQUIRED_REVIEW_BOT:", W)
        self.assertIn("HEAD_SHA:", W)
        self.assertIn("contents: read", W)
        self.assertIn("pull-requests: read", W)
        self.assertNotIn("pull_request_target", W)
        self.assertNotIn("issue_comment", W)
        self.assertNotIn("secrets:", W)
        self.assertNotIn("contents: write", W)
        self.assertNotIn("pull-requests: write", W)

    def test_template_rechecks_policy_on_review_events(self):
        self.assertIn("pull_request:", TEMPLATE)
        self.assertIn("types: [opened, synchronize, reopened, edited]", TEMPLATE)
        self.assertIn("pull_request_review:", TEMPLATE)
        self.assertIn("types: [submitted, dismissed]", TEMPLATE)
        self.assertIn('required_review_bot: ""', TEMPLATE)
        self.assertNotIn("pull_request_target", TEMPLATE)
        self.assertNotIn("issue_comment", TEMPLATE)
        self.assertNotIn("secrets:", TEMPLATE)

