import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AcceptanceWorkflowContractTests(unittest.TestCase):
    def test_reusable_waits_long_enough_for_slow_required_checks(self):
        reusable = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")
        acceptance = reusable.split("  acceptance:\n", 1)[1]
        timeout_minutes = int(
            re.search(r"timeout-minutes: ([0-9]+)", acceptance).group(1)
        )
        max_attempts = int(re.search(r"max_attempts=([0-9]+)", acceptance).group(1))
        wait_seconds = int(re.search(r"wait_seconds=([0-9]+)", acceptance).group(1))
        wait_budget = (max_attempts - 1) * wait_seconds

        self.assertGreaterEqual(wait_budget, 20 * 60)
        self.assertLess(wait_budget, timeout_minutes * 60)
        self.assertIn('commits/$SHA/check-runs?per_page=100', reusable)
        self.assertIn("Checks requeridos no quedaron terminales dentro del límite.", reusable)

    def test_reusable_uses_low_frequency_bounded_check_polling(self):
        reusable = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")
        max_attempts = int(re.search(r"max_attempts=([0-9]+)", reusable).group(1))
        wait_seconds = int(re.search(r"wait_seconds=([0-9]+)", reusable).group(1))

        self.assertGreaterEqual(wait_seconds, 30)
        self.assertLessEqual(max_attempts, 50)
        self.assertIn("attempt == max_attempts", reusable)
        self.assertIn('sleep "$wait_seconds"', reusable)

    def test_terminal_acceptance_errors_still_abort_without_retry(self):
        reusable = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")
        terminal_guard = 'if [[ "$readiness_rc" != "3" ]]; then'
        terminal_exit = 'exit "$readiness_rc"'
        pending_limit = "if (( attempt == max_attempts )); then"

        self.assertIn(terminal_guard, reusable)
        self.assertIn(terminal_exit, reusable)
        self.assertLess(reusable.index(terminal_guard), reusable.index(pending_limit))
        self.assertLess(reusable.index(terminal_guard), reusable.index(terminal_exit))

    def test_readiness_does_not_repeat_contract_tests(self):
        reusable = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")
        checks_only = "python3 .factory/scripts/aceptacion_kit.py --checks-only"
        final = "python3 .factory/scripts/aceptacion_kit.py < /tmp/acceptance.json"
        self.assertEqual(reusable.count(checks_only), 1)
        self.assertEqual(reusable.count(final), 1)
        self.assertLess(reusable.index(checks_only), reusable.index(final))
        loop_start = reusable.index('for attempt in $(seq 1 "$max_attempts"); do')
        loop_end = reusable.index("          done", loop_start)
        self.assertLess(loop_start, reusable.index(checks_only))
        self.assertLess(reusable.index(checks_only), loop_end)
        self.assertGreater(reusable.index(final), loop_end)

    def test_documentation_explains_bounded_wait_without_reruns(self):
        doc = (ROOT / "docs/aceptacion-ejecutable.md").read_text(encoding="utf-8")

        self.assertIn("20 minutos", doc)
        self.assertIn("60 segundos", doc)
        self.assertIn("no vuelve a ejecutar", doc)
        self.assertIn("fallo terminal", doc)

    def test_issue_form_and_required_gate_are_wired(self):
        ci = (ROOT / ".github/workflows/factory-ci.yml").read_text(encoding="utf-8")
        form = (ROOT / ".github/ISSUE_TEMPLATE/trabajo.yml").read_text(encoding="utf-8")
        config = (ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text(encoding="utf-8")
        reusable = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")
        wrapper = (ROOT / "template/.github/workflows/aceptacion.yml").read_text(encoding="utf-8")

        self.assertIn("name: Criterios de aceptación", ci)
        self.assertIn("needs: [workflows, scripts, coordinacion]", ci)
        self.assertIn("needs: [workflows, scripts, coordinacion, acceptance]", ci)
        self.assertIn("scripts/aceptacion_kit.py", ci)
        self.assertIn("checks: read", ci)

        for label in (
            "label: Contexto",
            "label: Alcance",
            "label: Fuera de alcance",
            "label: Criterios de aceptación",
            "label: Contrato ejecutable",
        ):
            self.assertIn(label, form)
        self.assertIn("blank_issues_enabled: false", config)

        self.assertIn("workflow_call:", reusable)
        self.assertIn("name: Criterios de aceptación", reusable)
        self.assertIn("checks: read", reusable)
        for workflow in (ci, reusable):
            self.assertIn("acceptance_sha256", workflow)
            self.assertIn("require_pin:true", workflow)
            self.assertIn("comments?per_page=100", workflow)
            self.assertIn("latest_reservation", workflow)
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/aceptacion.yml@v1",
            wrapper,
        )


if __name__ == "__main__":
    unittest.main()
