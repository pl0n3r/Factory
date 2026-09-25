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

        forbidden = ("pull_request_target", "workflow_run", "issue_comment")
        ci = self.text("ci.yml")
        guard = ci[ci.index("Rechazar eventos privilegiados"):ci.index("  preflight:")]
        for event in forbidden:
            self.assertNotIn(f"{event})", guard)

    def test_guard_allows_current_non_privileged_events(self) -> None:
        ci = self.text("ci.yml")
        self.assertIn("pull_request|push|merge_group", ci)
        for name in ("preview.yml", "aceptacion.yml"):
            text = self.text(name)
            self.assertIn('[[ "$EVENT_NAME" == "pull_request" ]]', text)
        deploy = self.text("deploy.yml")
        self.assertIn("workflow_dispatch|push)", deploy)

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
