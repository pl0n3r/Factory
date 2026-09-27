from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "codeql-evidence.yml"


class CodeqlEvidenceWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_codeql_evidence_is_read_only_and_pinned(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertNotIn("security-events: write", self.text)
        self.assertIn("github/codeql-action/init@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2", self.text)
        self.assertIn("github/codeql-action/analyze@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2", self.text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_codeql_evidence_keeps_sarif_local_and_fails_closed(self) -> None:
        self.assertIn("languages: actions", self.text)
        self.assertIn("output: codeql-results", self.text)
        self.assertIn("upload: never", self.text)
        self.assertIn("upload-database: false", self.text)
        self.assertIn("--fail-severity 7.0", self.text)
        self.assertIn("--require-zero-rule actions/cache-poisoning/poisonable-step", self.text)
        self.assertIn("if-no-files-found: error", self.text)
        self.assertIn("retention-days: 3", self.text)

    def test_codeql_evidence_runs_on_pr_and_exact_main_push(self) -> None:
        self.assertIn("pull_request:", self.text)
        self.assertIn('      - "actions/**"', self.text)
        self.assertIn("push:", self.text)
        self.assertIn("branches: [main]", self.text)
        self.assertNotIn("workflow_dispatch", self.text)


if __name__ == "__main__":
    unittest.main()
