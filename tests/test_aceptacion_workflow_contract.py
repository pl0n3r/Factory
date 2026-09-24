import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AcceptanceWorkflowContractTests(unittest.TestCase):
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
            self.assertIn("comments?per_page=100", workflow)
            self.assertIn("latest_reservation", workflow)
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/aceptacion.yml@v1",
            wrapper,
        )


if __name__ == "__main__":
    unittest.main()
