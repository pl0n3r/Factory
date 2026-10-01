import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sonar.yml"
PINNED_SCANNER_SHA = "d209202bc7d53ff1cc128f7f907dac145c9d6ae9"
PROJECT_KEY = "pl0n3r_factory"


class SonarCiAnalysisWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_pinned_minimal_and_fail_closed(self):
        text = self.text
        self.assertIn("pull_request:", text)
        self.assertIn("push:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertGreaterEqual(text.count("branches: [main]"), 2)
        self.assertIn(
            "(github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main')",
            text,
        )
        self.assertIn("permissions:\n  contents: read", text)
        self.assertNotRegex(
            text,
            r"(?m)^\s+(checks|issues|pull-requests|actions):\s+write\s*$",
        )
        self.assertIn("fetch-depth: 0", text)
        self.assertIn(
            f"uses: SonarSource/sonarqube-scan-action@{PINNED_SCANNER_SHA}",
            text,
        )
        self.assertIn("vars.SONAR_CI_ENABLED == 'true'", text)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", text)
        self.assertIn("github.event.pull_request.draft == false", text)
        self.assertNotIn("pull_request_target:", text)

    def test_coverage_report_is_wired_into_scanner(self):
        text = self.text
        self.assertIn(f"-Dsonar.projectKey={PROJECT_KEY}", text)
        self.assertIn(
            "-Dsonar.python.coverage.reportPaths=build/coverage/python.xml",
            text,
        )
        self.assertIn("python3 scripts/generate_coverage.py", text)
        self.assertIn("coverage==7.16.2", text)
        self.assertIn("-Dsonar.qualitygate.wait=true", text)
        self.assertIn("-Dsonar.qualitygate.timeout=300", text)

    def test_product_sources_are_explicit_and_tests_are_separate(self):
        text = self.text
        self.assertIn(
            "-Dsonar.sources="
            "evolution,intelligence,knowledge,lab,lecciones,metricas,performance,"
            "portfolio,producto,quality,readme,recovery,scripts,seguridad",
            text,
        )
        self.assertIn("-Dsonar.tests=tests", text)
        self.assertNotIn("-Dsonar.sources=tests", text)

    def test_coverage_published_gate_queries_sonar_fail_closed(self):
        text = self.text
        self.assertIn("name: Sonar Coverage = published", text)
        self.assertIn("/api/measures/component?", text)
        self.assertIn('"metricKeys": "coverage,lines_to_cover,uncovered_lines"', text)
        self.assertIn('params["pullRequest"] = pull_request', text)
        self.assertIn('params["branch"] = "main"', text)
        self.assertIn('"coverage" not in measures', text)
        self.assertIn('"lines_to_cover" not in measures', text)
        self.assertIn("if lines_to_cover <= 0:", text)
        self.assertIn('"Authorization": f"Bearer {token}"', text)

    def test_coverage_published_gate_is_required_after_scanner(self):
        text = self.text
        start = text.index("  coverage-published:")
        end = text.index("  analysis-method:", start)
        section = text[start:end]
        self.assertIn("needs: sonar", section)
        self.assertIn("needs.sonar.result == 'success'", section)
        self.assertIn("vars.SONAR_CI_ENABLED == 'true'", section)
        self.assertIn("secrets.SONAR_TOKEN", section)
        self.assertIn("timeout-minutes: 2", section)

    def test_token_is_secret_only_and_analysis_method_depends_on_scanner(self):
        text = self.text
        self.assertGreaterEqual(text.count("secrets.SONAR_TOKEN"), 2)
        self.assertNotIn("-Dsonar.token=", text)
        self.assertNotRegex(
            text,
            r"(?i)SONAR_TOKEN:\s*['\"]?[A-Za-z0-9_-]{20,}",
        )
        self.assertIn("name: SonarQube Cloud Analysis Method = CI-based", text)
        self.assertIn("needs: sonar", text)
        self.assertIn('[[ "$SONAR_RESULT" == "success" ]]', text)


if __name__ == "__main__":
    unittest.main()
