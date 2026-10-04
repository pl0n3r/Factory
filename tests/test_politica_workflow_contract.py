import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = (ROOT / ".github/workflows/politica.yml").read_text()
COMMENT_W = (ROOT / ".github/workflows/politica-comentario.yml").read_text()
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
        self.assertLess(W.index("factory-policy.json?ref=$CURRENT_BASE"), W.index("actions/checkout@"))
        self.assertLess(W.index("Validar evento, PR, HEAD y policy base antes de checkout"), W.index("actions/checkout@"))

    def test_template_policy_is_versioned_read_only_and_event_bounded(self):
        policy = json.loads(TEMPLATE_POLICY)
        self.assertEqual(policy, {"version": 1, "required_review_bot": None})
        self.assertIn("pull_request_review:", TEMPLATE)
        self.assertIn("issue_comment:", TEMPLATE)
        self.assertIn("required_review_bot:", TEMPLATE)
        self.assertIn("contents: read", W)
        self.assertIn("pull-requests: read", W)
        self.assertNotIn("issues: write", W)
        self.assertNotIn("checks: read", W)
        policy_job = TEMPLATE.split("  politica:\n", 1)[1].split(
            "\n  politica-comentario:",
            1,
        )[0]
        self.assertNotIn("permissions:", policy_job)
        for forbidden in ("contents: write", "pull-requests: write", "secrets:"):
            self.assertNotIn(forbidden, W + COMMENT_W + TEMPLATE)
        self.assertNotIn("issues: write", COMMENT_W)
        for event in ("pull_request_target:", "workflow_run:", "check_run:", "repository_dispatch:"):
            self.assertNotIn(event, W + COMMENT_W + TEMPLATE)

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
        self.assertIn("issue_comment:", TEMPLATE)
        self.assertIn("types: [created, edited]", TEMPLATE)
        self.assertIn("github.event_name == 'pull_request' || github.event_name == 'pull_request_review'", TEMPLATE)
        self.assertIn("github.event.issue.pull_request != null", TEMPLATE)
        self.assertNotIn("pull_request_target", TEMPLATE)

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

    def test_comment_revalidation_never_executes_consumer_code(self):
        self.assertIn("repository: pl0n3r/factory", COMMENT_W)
        self.assertIn("path: .factory", COMMENT_W)
        self.assertIn("python3 .factory/scripts/politica_kit.py", COMMENT_W)
        self.assertIn("repos/$HEAD_REPO/contents/decisiones.yml?ref=$CURRENT_HEAD", COMMENT_W)
        self.assertNotIn("repository: ${{ github.repository }}", COMMENT_W)
        self.assertLess(COMMENT_W.index("Validar evento, PR, comentario y policy base antes de checkout"), COMMENT_W.index("actions/checkout@"))

    def test_comment_revalidation_supports_bootstrap_reviewer_input(self):
        self.assertIn('required_review_bot: {required: false, type: string, default: ""}', COMMENT_W)
        self.assertIn('CALLER_REQUIRED_REVIEW_BOT: ${{ inputs.required_review_bot }}', COMMENT_W)
        self.assertEqual(TEMPLATE.count('required_review_bot: ""'), 2)
        self.assertIn('EFFECTIVE_REQUIRED="$CALLER_REQUIRED_REVIEW_BOT"', COMMENT_W)
        self.assertIn('echo "BASE_POLICY_FILE="', COMMENT_W)

    def test_comment_revalidation_preserves_monotonic_base_reviewer(self):
        self.assertIn('BASE_REQUIRED="$(jq -r', COMMENT_W)
        self.assertIn('if [[ -n "$BASE_REQUIRED" ]]', COMMENT_W)
        self.assertIn('"$CALLER_REQUIRED_REVIEW_BOT" == "$BASE_REQUIRED"', COMMENT_W)
        self.assertIn("Caller no puede cambiar reviewer-bot de BASE", COMMENT_W)
        self.assertIn('EFFECTIVE_REQUIRED="$BASE_REQUIRED"', COMMENT_W)

    def test_comment_revalidation_filters_non_pr_and_wrong_actor(self):
        self.assertIn("github.event.issue.pull_request != null", TEMPLATE)
        self.assertIn('EVENT_IS_PR: ${{ github.event.issue.pull_request != null }}', COMMENT_W)
        self.assertIn('COMMENT_TYPE="$(jq -r', COMMENT_W)
        self.assertIn('COMMENT_LOGIN="$(jq -r', COMMENT_W)
        self.assertIn('if [[ "$COMMENT_TYPE" != "Bot" ]]', COMMENT_W)
        self.assertIn('if [[ -z "$EFFECTIVE_REQUIRED" || "$COMMENT_LOGIN" != "$EFFECTIVE_REQUIRED" ]]', COMMENT_W)
        self.assertIn('echo "RELEVANT=false"', COMMENT_W)

    def test_comment_revalidation_delegates_reviewer_resolution_to_policy_kit(self):
        self.assertIn('args=(--required-review-bot "$CALLER_REQUIRED_REVIEW_BOT"', COMMENT_W)
        self.assertIn('[[ -z "${BASE_POLICY_FILE:-}" ]] || args+=(--base-policy-file "$BASE_POLICY_FILE")', COMMENT_W)
        self.assertIn('python3 .factory/scripts/politica_kit.py "${args[@]}"', COMMENT_W)
        self.assertNotIn('--required-review-bot "$EFFECTIVE_REQUIRED"', COMMENT_W)

    def test_comment_revalidation_materializes_exact_head_success_check(self):
        self.assertIn("CHECK_NAME: Factory policy / Validar decisiones y límite de revisión", COMMENT_W)
        self.assertIn('CONCLUSION="success"', COMMENT_W)
        self.assertIn('"repos/$REPOSITORY/check-runs"', COMMENT_W)
        self.assertIn('--arg head_sha "$PR_HEAD_SHA"', COMMENT_W)
        self.assertIn('head_sha:$head_sha', COMMENT_W)

    def test_comment_revalidation_keeps_invalid_required_bot_evidence_failed(self):
        self.assertIn('CONCLUSION="failure"', COMMENT_W)
        self.assertIn('if (( POLICY_STATUS != 0 )); then', COMMENT_W)
        self.assertIn('--comments-file "$COMMENTS_FILE"', COMMENT_W)
        self.assertIn('--base-policy-file "$BASE_POLICY_FILE"', COMMENT_W)

    def test_comment_revalidation_rechecks_head_before_check_publish(self):
        self.assertIn('PR_JSON_FINAL="$(gh api "repos/$REPOSITORY/pulls/$PR")"', COMMENT_W)
        self.assertIn('"$FINAL_HEAD" != "$PR_HEAD_SHA"', COMMENT_W)
        self.assertIn('"$FINAL_BASE" != "$PR_BASE_SHA"', COMMENT_W)
        self.assertIn('"$FINAL_HEAD_REPO" != "$PR_HEAD_REPO"', COMMENT_W)
        self.assertIn('"$FINAL_BASE_REPO" != "$PR_BASE_REPO"', COMMENT_W)
        self.assertLess(COMMENT_W.index("PR_JSON_FINAL="), COMMENT_W.index("check-runs"))

    def test_comment_revalidation_permissions_are_minimal(self):
        self.assertIn("checks: write", COMMENT_W)
        self.assertIn("contents: read", COMMENT_W)
        self.assertIn("pull-requests: read", COMMENT_W)
        self.assertIn("issues: read", COMMENT_W)
        self.assertIn("checks: write", TEMPLATE)
        for forbidden in ("contents: write", "pull-requests: write", "issues: write", "secrets:"):
            self.assertNotIn(forbidden, COMMENT_W)
        self.assertNotIn("pull_request_target", COMMENT_W)


class PoliticaWorkflowContractTests(unittest.TestCase):
    def test_rate_limit_fallback_keeps_legacy_caller_permissions(self):
        self.assertIn(
            "permissions:\n  contents: read\n  pull-requests: read\njobs:",
            W,
        )
        policy_job = W.split("  politica:\n", 1)[1].split(
            "\n    runs-on:",
            1,
        )[0]
        self.assertNotIn("permissions:", policy_job)
        self.assertNotIn("issues: write", W)
        self.assertNotIn("checks: read", W)

    def test_rate_limit_fallback_reads_public_checks_without_token(self):
        start = W.index(
            'checks_url="https://api.github.com/repos/$REPOSITORY/'
            'commits/$PR_HEAD_SHA/check-runs?per_page=100"'
        )
        end = W.index('owner="${REPOSITORY%%/*}"', start)
        checks_transport = W[start:end]

        self.assertIn("curl --silent --show-error --location", checks_transport)
        self.assertIn(
            "X-GitHub-Api-Version: 2022-11-28",
            checks_transport,
        )
        self.assertIn("--write-out '%{http_code}'", checks_transport)
        self.assertIn(
            '[[ "$checks_status" == "200" ]]',
            checks_transport,
        )
        self.assertIn(
            "Payload público de check-runs excede el tamaño permitido",
            checks_transport,
        )
        self.assertIn(
            'and (.check_runs | type == "array")',
            checks_transport,
        )
        self.assertIn(".total_count <= 100", checks_transport)
        self.assertNotIn("Authorization:", checks_transport)
        self.assertNotIn("GH_TOKEN", checks_transport)
        self.assertNotIn("gh api", checks_transport)

    def test_rate_limit_fallback_audit_is_read_only(self):
        self.assertIn("datos.yml?ref=$PR_BASE_SHA", W)
        self.assertIn("commits/$PR_HEAD_SHA", W)
        self.assertIn("HEAD_COMMITTED_AT", W)
        self.assertIn('--head-committed-at "$HEAD_COMMITTED_AT"', W)
        self.assertIn("reviewThreads(first:100)", W)
        self.assertIn("comments(first:100){pageInfo{hasNextPage}", W)
        self.assertIn('--checks-file "$checks_file"', W)
        self.assertIn('--threads-file "$threads_file"', W)
        self.assertIn("rate_limit_comment_id", W)
        self.assertIn("rate_limit_created_at", W)
        self.assertIn("GITHUB_STEP_SUMMARY", W)
        self.assertIn("::notice title=Reviewer rate-limit fallback::", W)
        self.assertIn("#issuecomment-$retry_id", W)
        self.assertNotIn("factory-reviewer-rate-limit-fallback", W)
        self.assertNotIn("--method PATCH", W)
        self.assertNotIn("--method POST", W)
        self.assertNotIn("issues: write", W)

    def test_template_policy_caller_stays_legacy_compatible(self):
        policy_job = TEMPLATE.split("  politica:\n", 1)[1].split(
            "\n  politica-comentario:",
            1,
        )[0]
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/politica.yml@v1",
            policy_job,
        )
        self.assertNotIn("permissions:", policy_job)
        self.assertIn(
            "permissions:\n  contents: read\n  pull-requests: read",
            TEMPLATE,
        )
        self.assertNotIn("issues: write", policy_job)
        self.assertNotIn("checks: read", policy_job)

    def test_fallback_still_preserves_exact_head_and_bounded_evidence(self):
        self.assertIn("phase_args=()", W)
        self.assertIn('phase_args=(--phase-file "$phase_file")', W)
        self.assertIn('"${phase_args[@]}"', W)
        self.assertIn("check-runs?per_page=100", W)
        self.assertIn(
            '(( $(wc -c < "$checks_file") <= MAX_EVIDENCE_BYTES ))',
            W,
        )
        self.assertIn(
            '(( $(wc -c < "$threads_file") <= MAX_EVIDENCE_BYTES ))',
            W,
        )


if __name__ == "__main__":
    unittest.main()
