import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = (ROOT / ".github/workflows/politica.yml").read_text()
TEMPLATE = (ROOT / "template/.github/workflows/politica.yml").read_text()
TEMPLATE_POLICY_PATH = ROOT / "template/.github/factory-policy.json"
TEMPLATE_POLICY = TEMPLATE_POLICY_PATH.read_text()


class T(unittest.TestCase):
    def test_policy_script_remains_executable(self):
        self.assertTrue((ROOT / "scripts/politica_kit.py").stat().st_mode & 0o111)

    def test_observed_reviews_and_canonical_policy(self):
        self.assertIn("pr_number:", W)
        self.assertNotIn("review_rounds:", W)
        self.assertIn("/pulls/$PR/reviews", W)
        self.assertIn("python3 .factory/scripts/politica_kit.py", W)
        self.assertNotIn("--file", W)

    def test_required_reviewer_policy_is_loaded_from_base_sha_before_candidate_checkout(self):
        self.assertIn("github.event.pull_request.base.sha", W)
        self.assertIn("factory-policy.json?ref=$CURRENT_BASE", W)
        self.assertIn("application/vnd.github.raw+json", W)
        self.assertIn("BASE_POLICY_FILE", W)
        self.assertLess(
            W.index("factory-policy.json?ref=$CURRENT_BASE"),
            W.index("actions/checkout@"),
        )
        self.assertLess(
            W.index("Validar evento, PR, HEAD y policy base antes de checkout"),
            W.index("actions/checkout@"),
        )

    def test_template_policy_is_versioned_read_only_and_event_bounded(self):
        policy = json.loads(TEMPLATE_POLICY)
        self.assertEqual(policy, {"version": 1, "required_review_bot": None})
        self.assertIn("pull_request_review:", TEMPLATE)
        self.assertIn("types: [submitted, dismissed]", TEMPLATE)
        self.assertIn("required_review_bot:", TEMPLATE)
        self.assertIn("contents: read", W)
        self.assertIn("pull-requests: read", W)
        for forbidden in ("contents: write", "pull-requests: write", "issues: write", "secrets:"):
            self.assertNotIn(forbidden, W)
        for event in ("pull_request_target", "issue_comment", "workflow_run", "check_run", "repository_dispatch"):
            self.assertNotIn(event, W + TEMPLATE)

    def test_candidate_caller_cannot_disable_base_required_reviewer(self):
        self.assertIn('CURRENT_BASE="$(jq -r', W)
        self.assertIn('[[ "$CURRENT_BASE" == "$EVENT_BASE" ]]', W)
        self.assertIn("--base-policy-file", W)
        self.assertIn('required_review_bot: ""', TEMPLATE)
        self.assertNotIn("factory-policy.json?ref=$PR_HEAD_SHA", W)

    def test_required_reviewer_context_is_read_only_and_event_bounded(self):
        self.assertIn("required_review_bot:", W)
        self.assertIn("pull_request|pull_request_review", W)
        self.assertIn("github.event.pull_request.head.sha", W)
        self.assertIn('CURRENT_HEAD="$(jq -r', W)

    def test_template_rechecks_policy_on_review_events(self):
        self.assertIn("pull_request_review:", TEMPLATE)
        self.assertIn("types: [submitted, dismissed]", TEMPLATE)
        self.assertIn("pull_request:", TEMPLATE)
        self.assertNotIn("pull_request_target", TEMPLATE)
        self.assertNotIn("issue_comment", TEMPLATE)

    def test_required_reviewer_comments_are_read_only_bounded_and_exact_pr(self):
        self.assertIn('issues/$PR/comments?per_page=100', W)
        self.assertIn('--comments-file "$comments_file"', W)
        self.assertIn('MAX_EVIDENCE_BYTES: "2000000"', W)
        self.assertIn('comments_bytes="$(wc -c < "$comments_file")"', W)
        self.assertIn('(( comments_bytes <= MAX_EVIDENCE_BYTES ))', W)
        self.assertIn('PR_JSON="$(gh api "repos/$REPOSITORY/pulls/$INPUT_PR")"', W)
        self.assertIn('[[ "$CURRENT_HEAD" == "$EVENT_HEAD" ]]', W)
        self.assertIn('[[ "$CURRENT_BASE" == "$EVENT_BASE" ]]', W)
        self.assertNotIn("issues: write", W)
        self.assertNotIn("issue_comment", W)


if __name__ == "__main__":
    unittest.main()
