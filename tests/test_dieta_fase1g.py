"""F1G: la baja del resumen accesorio no reduce vigilancia ni motor offline."""
from pathlib import Path
import unittest

from scripts.unattended_daily_summary import publish_once

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "unattended-watchdog.yml"
RUNBOOK = ROOT / "docs" / "unattended-watchdog-runtime.md"


class OfflineSummaryClient:
    """Fake en memoria; no construye transporte ni usa credenciales."""
    def __init__(self):
        self.comments = []
        self.writes = []

    def list_issue_comments(self, _issue):
        return list(self.comments)

    def _request(self, method, path, payload):
        self.writes.append((method, path, payload))
        self.comments.append({
            "user": {"login": "github-actions[bot]"},
            "body": payload["body"],
        })
        return {"ok": True}


class DietaFase1GTests(unittest.TestCase):
    def test_only_daily_summary_job_removed_and_watchdog_survives(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("\n  watchdog:\n"), 1)
        self.assertNotIn("\n  daily-summary:", workflow)
        self.assertNotIn("cron: '0 13 * * *'", workflow)
        self.assertNotIn("python3 -m scripts.unattended_daily_summary", workflow)
        self.assertIn("name: Vigilar actividad desatendida", workflow)
        self.assertIn("python3 -m scripts.unattended_watchdog_runtime", workflow)
        self.assertIn("timeout-minutes: 5", workflow)
        self.assertIn("issues: write", workflow)

    def test_watchdog_remains_fail_closed_and_quarter_hour(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("cron: '*/15 * * * *'"), 1)
        self.assertEqual(workflow.count("\n    - cron:"), 1)
        for source in ("push:", "- main", "schedule:", "workflow_dispatch:",
                       "github.repository == 'pl0n3r/Factory'",
                       "github.ref == 'refs/heads/main'",
                       "github.event_name == 'push'",
                       "github.event_name == 'schedule'",
                       "github.event_name == 'workflow_dispatch'",
                       "group: unattended-watchdog-${{ github.repository_id }}",
                       "cancel-in-progress: false", "contents: read",
                       "persist-credentials: false"):
            with self.subTest(source=source):
                self.assertIn(source, workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("workflow_run", workflow)
        runtime = (ROOT / "scripts/unattended_watchdog_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("evaluate_unattended_kill_switch(client.get_issue(767))",
                      runtime)
        self.assertIn("if switch.global_pause:", runtime)

    def test_offline_daily_summary_remains_idempotent_without_trigger(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("scripts.unattended_daily_summary", workflow)
        script = ROOT / "scripts" / "unattended_daily_summary.py"
        self.assertTrue(script.is_file())
        body = ('<!-- factory-unattended-daily-summary '
                '{"local_date":"2026-10-13","version":1} -->\n'
                '## Resumen diario Factory offline')
        fake = OfflineSummaryClient()
        self.assertTrue(publish_once(fake, local_date="2026-10-13", body=body))
        self.assertFalse(publish_once(fake, local_date="2026-10-13", body=body))
        self.assertEqual(len(fake.writes), 1)
        self.assertEqual(fake.writes[0][0], "POST")
        self.assertIn("/repos/pl0n3r/Factory/issues/", fake.writes[0][1])

    def test_document_loss_and_exact_rollback(self):
        runbook = RUNBOOK.read_text(encoding="utf-8")
        for required in ("Factory #1296", "#1336", "08:00 Bogotá",
                         "deja de", "32 antes y 32 después",
                         "Rollback exclusivo F1G",
                         "0 13 * * *", "## Reversión",
                         "Factory#815", "*/15 * * * *",
                         "watchdog", "publish_once", "#767"):
            with self.subTest(required=required):
                self.assertIn(required, runbook)
        self.assertIn("sin revertir", runbook)
        self.assertNotIn("El job `daily-summary` sigue restringido",
                         runbook)


if __name__ == "__main__":
    unittest.main()
