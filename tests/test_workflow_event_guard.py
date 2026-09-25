from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class WorkflowEventGuardTests(unittest.TestCase):
    def text(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_code_executing_reusables_guard_privileged_events_before_checkout(self) -> None:
        guarded = {
            "ci.yml": "Rechazar eventos privilegiados",
            "preview.yml": "Rechazar eventos privilegiados",
            "aceptacion.yml": "Rechazar eventos privilegiados",
            "deploy.yml": "Validar contexto de despliegue",
            "release.yml": "Validar contexto confiable",
            "observar.yml": "Validar contexto confiable",
        }
        for name, marker in guarded.items():
            with self.subTest(workflow=name):
                text = self.text(name)
                self.assertIn(marker, text)
                self.assertIn("actions/checkout@", text)
                self.assertLess(text.index(marker), text.index("actions/checkout@"))

        for name in ("ci.yml", "preview.yml", "aceptacion.yml"):
            text = self.text(name)
            self.assertIn("permissions: {}", text)
            self.assertIn("needs: event_guard", text)
            cache_lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip().startswith("cache-mode:")
            ]
            self.assertEqual(cache_lines, ["cache-mode: read"])

        forbidden = ("pull_request_target", "workflow_run", "issue_comment")
        ci = self.text("ci.yml")
        guard = ci[ci.index("Rechazar eventos privilegiados"):ci.index("  preflight:")]
        for event in forbidden:
            self.assertNotIn(f"{event})", guard)

    def test_consumer_commands_use_cache_sanitizing_factory_runner(self) -> None:
        ci = self.text("ci.yml")
        self.assertIn(".factory/scripts/consumer_ci.py composer-validate", ci)
        self.assertIn(".factory/scripts/consumer_ci.py php-contract", ci)
        self.assertIn(".factory/scripts/consumer_ci.py node-test-build", ci)
        self.assertNotIn("composer validate --strict", ci)
        self.assertNotIn("npm test --if-present", ci)
        runner = (ROOT / "scripts" / "consumer_ci.py").read_text(encoding="utf-8")
        retry = (ROOT / "scripts" / "ci_retry.py").read_text(encoding="utf-8")
        for key in (
            "ACTIONS_CACHE_URL",
            "ACTIONS_RUNTIME_TOKEN",
            "ACTIONS_RESULTS_URL",
            "ACTIONS_CACHE_SERVICE_V2",
        ):
            self.assertIn(key, runner)
            self.assertIn(key, retry)
        self.assertIn("env=sanitized_environment()", runner)
        self.assertIn("env=environment", retry)

    def test_factory_lint_only_ignores_actionlint_cache_mode_parser_gap(self) -> None:
        workflow = self.text("factory-ci.yml")
        self.assertIn(
            """-ignore 'unexpected key "cache-mode" for "workflow" section'""",
            workflow,
        )
        self.assertNotIn("-ignore 'cache-mode'", workflow)

    def test_guard_allows_current_non_privileged_events(self) -> None:
        ci = self.text("ci.yml")
        self.assertIn("pull_request|push|merge_group", ci)
        self.assertIn(
            "if: github.event_name == 'pull_request' || github.event_name == 'merge_group'",
            ci,
        )
        self.assertNotIn(
            "if: github.event_name == 'pull_request' || github.event_name == 'push' || github.event_name == 'merge_group'\n    runs-on: ubuntu-latest\n    timeout-minutes: 20",
            ci,
        )
        for name in ("preview.yml", "aceptacion.yml"):
            text = self.text(name)
            self.assertIn('[[ "$EVENT_NAME" == "pull_request" ]]', text)
        deploy = self.text("deploy.yml")
        self.assertIn("workflow_dispatch|push)", deploy)

    def test_write_capable_push_does_not_run_consumer_php_or_node(self) -> None:
        ci = self.text("ci.yml")
        php = ci[ci.index("  php:"):ci.index("  node:")]
        node = ci[ci.index("  node:"):ci.index("  validar:")]
        self.assertIn("pull_request", php)
        self.assertIn("merge_group", php)
        self.assertNotIn("github.event_name == 'push'", php)
        self.assertIn("pull_request", node)
        self.assertIn("merge_group", node)
        self.assertNotIn("github.event_name == 'push'", node)

    def test_docs_define_event_contract(self) -> None:
        agents = (ROOT / "AGENTES.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "arquitectura-tecnica.md").read_text(encoding="utf-8")
        for text in (agents, architecture):
            self.assertIn("pull_request_target", text)
            self.assertIn("workflow_run", text)
            self.assertIn("issue_comment", text)
            self.assertIn("pull_request", text)
            self.assertIn("push", text)


if __name__ == "__main__":
    unittest.main()
