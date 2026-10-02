import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "template" / ".github" / "workflows" / "seguridad.yml"


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def job_block(value: str, name: str, next_name: str | None = None) -> str:
    tail = value.split(f"  {name}:", 1)[1]
    return tail.split(f"  {next_name}:", 1)[0] if next_name else tail


class TemplateSecurityWorkflowContractTests(unittest.TestCase):
    def test_issue_comment_routes_only_exact_owner_decision_commands(self):
        value = text()
        block = job_block(value, "materializar-respuesta", "sincronizar-decision")
        self.assertIn("issue_comment:", value)
        self.assertIn("types: [created]", value)
        self.assertIn("github.event.issue.pull_request == null", block)
        self.assertIn("github.event.issue.state == 'open'", block)
        self.assertIn("github.event.comment.author_association == 'OWNER'", block)
        self.assertIn("github.event.comment.user.type != 'Bot'", block)
        for option in "ABCD":
            self.assertIn(f"github.event.comment.body == '/decidir {option}'", block)
        self.assertNotIn("startsWith(github.event.comment.body, '/decidir ')", block)
        self.assertNotIn("contains(github.event.comment.body, '/decidir ')", block)

    def test_consumer_never_checks_out_or_executes_consumer_code(self):
        value = text()
        checkouts = value.split("uses: actions/checkout@")[1:]
        self.assertEqual(len(checkouts), 2)
        for checkout in checkouts:
            block = checkout.split("\n\n", 1)[0]
            self.assertIn("repository: pl0n3r/factory", block)
            self.assertIn("ref: v1", block)
            self.assertIn("path: .factory", block)
            self.assertIn("persist-credentials: false", block)
        self.assertNotRegex(value, r"(?m)^\s*run:.*(?:composer|npm|phpunit|tests/)")

    def test_issue_events_route_valid_gates_with_minimal_permissions(self):
        value = text()
        block = job_block(value, "sincronizar-decision")
        self.assertIn("issues:", value)
        self.assertIn("types: [opened, edited, reopened]", value)
        self.assertIn("OWNER|MEMBER|COLLABORATOR", block)
        self.assertIn("contents: read", block)
        self.assertIn("issues: write", block)
        self.assertNotIn("contents: write", block)
        self.assertNotIn("pull-requests: write", block)
        self.assertNotIn("checks: write", block)
        self.assertIn("decisión: dueño", block)

    def test_materialization_uses_versioned_factory_security_scripts(self):
        value = text()
        block = job_block(value, "materializar-respuesta", "sincronizar-decision")
        self.assertIn("repository: pl0n3r/factory", block)
        self.assertIn("ref: v1", block)
        self.assertIn("PYTHONPATH=.factory/seguridad", block)
        self.assertIn(".factory/seguridad/sincronizar_puerta.py valid", block)
        self.assertIn(".factory/seguridad/decision_respuesta.py", block)
        self.assertIn('steps.gate_sync.outputs.canonical == \'true\'', block)


if __name__ == "__main__":
    unittest.main()
