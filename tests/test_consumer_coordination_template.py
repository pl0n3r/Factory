import unittest
from pathlib import Path

from scripts import coordinar_trabajo as coordinator

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template" / ".github" / "workflows" / "coordinacion.yml"


def text():
    return TEMPLATE.read_text(encoding="utf-8")


def job_block(value: str, name: str, next_name: str | None = None) -> str:
    tail = value.split(f"  {name}:", 1)[1]
    return tail.split(f"  {next_name}:", 1)[0] if next_name else tail


class ConsumerCoordinationTemplateTests(unittest.TestCase):
    def test_pr_updates_revalidate(self):
        value = text()
        self.assertIn(
            "types: [opened, reopened, synchronize, edited, ready_for_review, converted_to_draft, closed]",
            value,
        )
        pr = job_block(value, "pr", "validar-pr")
        validate = job_block(value, "validar-pr", "issue")
        self.assertIn("github.event_name == 'pull_request'", pr)
        self.assertIn("operation: pr", pr)
        self.assertIn("github.event_name == 'pull_request'", validate)
        self.assertIn("operation: validate", validate)

    def test_merged_pr_does_not_revalidate(self):
        """AC-03: merge se salta; cierre sin merge conserva la ruta de validación."""
        value = text()
        gate = job_block(value, "validar-pr-evento", "validar-pr")
        validate = job_block(value, "validar-pr", "issue")
        self.assertIn("github.event_name == 'pull_request'", gate)
        self.assertIn("github.event.pull_request.merged != true", gate)
        self.assertNotIn("github.event.action != 'closed'", gate)
        self.assertIn("if: github.event_name == 'pull_request'", validate)
        self.assertIn("needs: validar-pr-evento", validate)
        self.assertIn("operation: validate", validate)
        self.assertIn(
            "types: [opened, reopened, synchronize, edited, ready_for_review, converted_to_draft, closed]",
            value,
        )

    def test_consumer_coordination_is_repository_serialized_without_dropping_pending_runs(self):
        value = text()
        concurrency = value.split("concurrency:", 1)[1].split("jobs:", 1)[0]
        self.assertIn("group: coordinacion-${{ github.repository }}", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)
        self.assertIn("queue: max", concurrency)
        self.assertNotIn("github.event.issue.number", concurrency)
        self.assertNotIn("github.run_id", concurrency)

    def test_comment_routing_matches_parser_whitespace_fail_closed(self):
        value = text()
        comment = job_block(value, "comentario", "etiqueta")
        self.assertIn("github.event_name == 'issue_comment'", comment)
        self.assertIn("github.event.sender.login == github.event.comment.user.login", comment)
        self.assertIn("github.event.comment.body == '/tomar'", comment)
        self.assertIn("startsWith(github.event.comment.body, '/renovar-contrato ')", comment)
        self.assertIn("contains(github.event.comment.body, '/tomar')", comment)
        self.assertIn("contains(github.event.comment.body, '/renovar-contrato ')", comment)
        coordinator.configure_profile("es")
        self.assertEqual(coordinator.parse_comment_command(" \n/tomar\t"), ("tomar", None))
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_comment_command("comentario ordinario")

    def test_all_routes_keep_expected_events_conditions_and_operations(self):
        value = text()
        for event in ("schedule:", "workflow_dispatch:", "pull_request:", "issues:", "issue_comment:"):
            self.assertIn(event, value)

        routes = (
            ("comentario", "etiqueta", "operation: comment"),
            ("etiqueta", "pr", "operation: label"),
            ("pr", "validar-pr", "operation: pr"),
            ("validar-pr", "issue", "operation: validate"),
            ("issue", "sweep", "operation: issue"),
            ("sweep", None, "operation: sweep"),
        )
        for name, next_name, operation in routes:
            with self.subTest(route=name):
                block = job_block(value, name, next_name)
                self.assertIn("uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1", block)
                self.assertIn(operation, block)

        self.assertIn("github.event.label.name == 'estado: reservado'", job_block(value, "etiqueta", "pr"))
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", job_block(value, "pr", "validar-pr"))
        self.assertIn("require_reservation: true", job_block(value, "validar-pr", "issue"))
        self.assertIn("github.event.action == 'closed'", job_block(value, "issue", "sweep"))
        self.assertIn("github.event_name == 'schedule'", job_block(value, "sweep"))


if __name__ == "__main__":
    unittest.main()
