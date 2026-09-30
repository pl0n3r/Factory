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
        self.assertIn("github.event.pull_request.head.sha", W)
        self.assertIn('CURRENT_HEAD="$(gh api "repos/$REPOSITORY/pulls/$INPUT_PR"', W)
        self.assertLess(W.index("Validar evento, PR y HEAD antes de checkout"), W.index("actions/checkout@"))
        self.assertIn("contents: read", W)
        self.assertIn("pull-requests: read", W)
        for forbidden in ("contents: write", "pull-requests: write", "issues: write", "secrets:"):
            self.assertNotIn(forbidden, W)
        for event in ("pull_request_target", "issue_comment", "workflow_run", "check_run", "repository_dispatch"):
            self.assertNotIn(event, W)

    def test_template_rechecks_policy_on_review_events(self):
        self.assertIn("pull_request_review:", TEMPLATE)
        self.assertIn("types: [submitted, dismissed]", TEMPLATE)
        self.assertIn("required_review_bot:", TEMPLATE)
        self.assertIn("pull_request:", TEMPLATE)
        self.assertNotIn("pull_request_target", TEMPLATE)
        self.assertNotIn("issue_comment", TEMPLATE)

if __name__ == "__main__":
    unittest.main()
