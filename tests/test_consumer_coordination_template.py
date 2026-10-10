import json
import os
import subprocess
import sys
import tempfile
import textwrap
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


def preflight_python() -> str:
    block = job_block(text(), "preflight_comentario", "comentario")
    shell = textwrap.dedent(block.split("run: |", 1)[1])
    return shell.split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]


def routes_comment(body: str) -> bool:
    """Ejecuta el clasificador real embebido en el workflow, sin red ni shell."""
    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / "github_output"
        event_file = Path(temp) / "event.json"
        event_file.write_text(json.dumps({"comment": {"body": body}}), encoding="utf-8")
        env = {**os.environ, "GITHUB_EVENT_PATH": str(event_file),
               "GITHUB_OUTPUT": str(output)}
        env.pop("COMMENT_BODY", None)
        result = subprocess.run(
            [sys.executable, "-c", preflight_python()],
            env=env, capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        if result.stdout or result.stderr:
            raise AssertionError("El preflight no debe registrar el comentario")
        return output.read_text(encoding="utf-8") == "route=true\n"


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
        coordinator.configure_profile("es")
        self.assertEqual(coordinator.parse_comment_command(" \n/tomar\t"), ("tomar", None))
        self.assertTrue(routes_comment(" \n/tomar\t"))
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_comment_command("comentario ordinario")
        self.assertFalse(routes_comment("comentario ordinario"))

    def test_embedded_commands_in_prose_are_skipped_without_red_jobs(self):
        for body in (
            "No ejecuté /tomar",
            "El ejemplo /renovar-contrato UUID es textual",
            "  Ejemplo: /liberar-forzado  ",
            "Estado del QA: /transferir UUID citado solamente",
            "texto\n/tomar",
            "texto que contiene /adoptar-contrato-huerfana",
            "",
        ):
            with self.subTest(body=body):
                self.assertFalse(routes_comment(body))
        comment = job_block(text(), "comentario", "etiqueta")
        self.assertNotIn("contains(github.event.comment.body", comment)
        self.assertIn("needs.preflight_comentario.outputs.route == 'true'", comment)

    def test_event_comment_body_is_not_logged_or_executed(self):
        # Se ejecuta el Python real del YAML; el comentario no va en el shell.
        cases = (
            ("No ejecuté /tomar;\n$(echo should-not-run)", False),
            ("/tomar $(echo should-not-run)", True),
            ('/renovar-contrato "$(echo should-not-run)"', True),
            ("/tomar\n$(touch /tmp/coord-no-exec)", True),
        )
        for body, expected_route in cases:
            with self.subTest(body=body):
                self.assertEqual(routes_comment(body), expected_route)
        preflight = job_block(text(), "preflight_comentario", "comentario")
        self.assertNotIn("COMMENT_BODY", preflight)
        self.assertNotIn("github.event.comment.body", preflight)

    def test_trimmed_real_commands_route_and_malformed_fail_closed(self):
        coordinator.configure_profile("es")
        uuid = "efd30204-fc16-4dca-8534-aa6e4d35bc57"
        accepted = (
            ("/tomar", ("tomar", None)),
            ("\n /tomar \t", ("tomar", None)),
            ("/liberar-forzado", ("liberar-forzado", None)),
            ("/adoptar-contrato-huerfana", ("adoptar-contrato-huerfana", None)),
            ("/liberar " + uuid, ("liberar", uuid)),
            ("/transferir " + uuid.upper(), ("transferir", uuid)),
            ("/migrar-contrato " + uuid, ("migrar-contrato", uuid)),
            ("/renovar-contrato \t" + uuid.upper(), ("renovar-contrato", uuid)),
        )
        for body, parsed in accepted:
            with self.subTest(body=body):
                self.assertTrue(routes_comment(body))
                self.assertEqual(coordinator.parse_comment_command(body), parsed)
        for body in (
            "/tomar no-es-comando-valido",
            "/tomar\ntexto",
            "/liberar",
            "/renovar-contrato NO-UUID",
            "/migrar-contrato",
            "/transferir texto",
            "/adoptar-contrato-huerfana argumento",
        ):
            with self.subTest(malformed=body):
                self.assertTrue(routes_comment(body))
                with self.assertRaises(coordinator.CoordinationError):
                    coordinator.parse_comment_command(body)
        self.assertFalse(routes_comment("/tomarlo"))
        self.assertFalse(routes_comment("/renovar-contrato-ejemplo"))

    def test_comment_routing_preserves_permissions_and_pr_guard(self):
        value = text()
        preflight = job_block(value, "preflight_comentario", "comentario")
        comment = job_block(value, "comentario", "etiqueta")
        for block in (preflight, comment):
            self.assertIn("github.event_name == 'issue_comment'", block)
            self.assertIn("github.event.issue.pull_request == null", block)
            self.assertIn(
                "github.event.sender.login == github.event.comment.user.login",
                block,
            )
        self.assertIn("permissions:\n      contents: read", preflight)
        self.assertIn("timeout-minutes: 2", preflight)
        self.assertIn('os.environ["GITHUB_EVENT_PATH"]', preflight)
        self.assertNotIn("COMMENT_BODY", preflight)
        self.assertNotIn("github.event.comment.body", preflight)
        self.assertNotIn("echo ${{ github.event.comment.body }}", preflight)
        self.assertIn("uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1", comment)
        for scope in ("contents", "issues", "pull-requests", "checks"):
            self.assertIn(f"      {scope}: write", comment)
        concurrency = value.split("concurrency:", 1)[1].split("jobs:", 1)[0]
        self.assertIn("group: coordinacion-${{ github.repository }}", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)
        self.assertIn("queue: max", concurrency)
        for event in ("schedule:", "workflow_dispatch:", "pull_request:",
                      "issues:", "issue_comment:"):
            self.assertIn(event, value)

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
