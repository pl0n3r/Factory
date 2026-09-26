"""Contrato documental para la transición global TANDA 2 → TANDA 3."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


class ReadmeTandasTests(unittest.TestCase):
    """Evita que el estado público de las tandas vuelva a quedar obsoleto."""

    @classmethod
    def setUpClass(cls):
        cls.readme = README.read_text(encoding="utf-8")

    def test_tanda_2_status_is_visible(self):
        self.assertIn("### Estado de las tandas", self.readme)
        for value in (
            "| Condor | #192 | ✅ Completado |",
            "| GrindFlow | #129 | 🚧 Pendiente / bloqueado |",
            "| BRVTAL | #630 | 🚧 Pendiente / bloqueado |",
            "| FactoryRunner | #1 | 🚧 Pendiente / bloqueado |",
        ):
            self.assertIn(value, self.readme)

    def test_tanda_3_requires_all_tanda_2_epics(self):
        self.assertIn(
            "TANDA 2 termina **solo cuando los cuatro épicos canónicos estén cerrados como completados**.",
            self.readme,
        )
        self.assertIn(
            "mientras cualquiera de esos cuatro épicos siga abierto, TANDA 3 no comienza globalmente",
            self.readme,
        )

    def test_tanda_3_priority_and_fronts_are_visible(self):
        self.assertIn(
            "**incidente de producción → crítica → alta → media**",
            self.readme,
        )
        for value in (
            "**Condor:** pedidos, e-commerce, stock y recuperación de cuenta.",
            "**GrindFlow:** recuperación de cuenta y continuación del roadmap.",
            "**BRVTAL:** recuperación de cuenta y pendientes de producto.",
            "**FactoryRunner:** identity/heartbeat → órdenes/eventos → adapters programáticos → browser execution.",
        ):
            self.assertIn(value, self.readme)

    def test_roadmap_contains_tanda_3(self):
        self.assertIn(
            "| 6 | TANDA 3 · desarrollo normal | 🔒 Bloqueada hasta completar los cuatro épicos de TANDA 2 |",
            self.readme,
        )

    def test_governance_summary_does_not_drift(self):
        self.assertIn("PLAN-AGENTES.md) sigue siendo la fuente de verdad.", self.readme)
        self.assertIn("ControlBot y AutoFactory:** solo en modo dirigido", self.readme)


if __name__ == "__main__":
    unittest.main()
