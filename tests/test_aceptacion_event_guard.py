"""Factory #1327: el guard de contexto es el primer paso del check requerido.

Ejercita el Bash real aislado, sin tokens, red ni acceso a GitHub.
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/aceptacion.yml"


class AcceptanceEventGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.jobs = cls.source.split("\njobs:\n", 1)[1]
        cls.acceptance = cls.jobs.split("  acceptance:\n", 1)[1]
        begin = cls.acceptance.index("      - name: Rechazar eventos privilegiados\n")
        end = cls.acceptance.index("      - name: Validar contexto PR\n", begin)
        cls.guard_step = cls.acceptance[begin:end]
        run_line = cls.guard_step.split("        run: |\n", 1)[1]
        cls.guard_script = "\n".join(
            line.removeprefix("          ") for line in run_line.splitlines()
        ) + "\n"

    def test_reusable_has_one_acceptance_job_with_guard_first(self):
        jobs = re.findall(r"(?m)^  ([a-z_]+):\s*$", self.jobs)
        self.assertEqual(jobs, ["acceptance"])
        steps = re.findall(r"(?m)^      - name: ([^\n]+)$", self.acceptance)
        self.assertGreater(len(steps), 3)
        self.assertEqual(steps[0], "Rechazar eventos privilegiados")
        self.assertEqual(steps[1], "Validar contexto PR")
        self.assertIn("name: Criterios de aceptación", self.acceptance)
        self.assertNotIn("needs: event_guard", self.acceptance)
        self.assertNotIn("  event_guard:", self.jobs)

    def execute_guard(self, event, script=None):
        return subprocess.run(
            ["bash", "-c", script or self.guard_script],
            env={**os.environ, "EVENT_NAME": event},
            text=True,
            capture_output=True,
            check=False,
        )

    def test_non_pr_event_fails_explicitly_not_skipped(self):
        self.assertNotIn("if: github.event_name == 'pull_request'", self.acceptance)
        good = self.execute_guard("pull_request")
        self.assertEqual(good.returncode, 0, good.stderr)
        for event in ("workflow_dispatch", "pull_request_target", "issues", "issue_comment", ""):
            with self.subTest(event=event):
                bad = self.execute_guard(event)
                self.assertNotEqual(bad.returncode, 0)
                self.assertIn("::error::Aceptación solo acepta pull_request", bad.stdout)
        mutated = self.guard_script.replace(
            '[[ "$EVENT_NAME" == "pull_request" ]]', "true"
        )
        self.assertNotEqual(mutated, self.guard_script)
        self.assertEqual(self.execute_guard("workflow_dispatch", mutated).returncode, 0)

    def test_required_permissions_context_and_polling_unchanged(self):
        self.assertIn("workflow_call:", self.source)
        self.assertIn("permissions: {}", self.source)
        self.assertIn("timeout-minutes: 25", self.acceptance)
        self.assertIn(
            "    permissions:\n      contents: read\n      issues: read\n      checks: read",
            self.acceptance,
        )
        for protected in (
            "Validar contexto PR",
            "Descargar candidato",
            "Descargar kit publicado",
            "Construir contexto de aceptación",
            "latest_reservation",
            "acceptance_sha256",
            "require_pin:true",
            "max_attempts=21",
            "wait_seconds=60",
            "readiness_rc",
            'if [[ "$readiness_rc" != "3" ]]; then',
            "Checks requeridos no quedaron terminales dentro del límite.",
            "python3 .factory/scripts/aceptacion_kit.py --checks-only",
            "python3 .factory/scripts/aceptacion_kit.py < /tmp/acceptance.json",
        ):
            self.assertIn(protected, self.acceptance)
        self.assertLess(
            self.acceptance.index("Rechazar eventos privilegiados"),
            self.acceptance.index("Validar contexto PR"),
        )


if __name__ == "__main__":
    unittest.main()
