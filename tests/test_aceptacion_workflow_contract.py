import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AcceptanceWorkflowContractTests(unittest.TestCase):
    def test_reusable_waits_boundedly_for_required_checks(self):
        reusable = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")
        self.assertIn("max_attempts=12", reusable)
        self.assertIn("wait_seconds=10", reusable)
        self.assertIn('commits/$SHA/check-runs?per_page=100', reusable)
        self.assertIn('[[ "$readiness_rc" != "3" ]]', reusable)
        self.assertIn("attempt == max_attempts", reusable)
        self.assertIn('sleep "$wait_seconds"', reusable)
        self.assertIn("Checks requeridos no quedaron terminales dentro del límite.", reusable)

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
