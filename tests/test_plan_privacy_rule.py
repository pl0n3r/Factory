"""Contrato durable de privacidad documentada en PLAN-AGENTES.md."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "PLAN-AGENTES.md"


class PlanPrivacyRuleTests(unittest.TestCase):
    """Evita que se pierda la regla temporal de documentación de datos."""

    @classmethod
    def setUpClass(cls):
        """Carga el plan una sola vez."""
        cls.plan = PLAN.read_text(encoding="utf-8")

    def test_personal_data_rule_is_documented(self):
        """AC-01: la regla cubre documentación, puerta legal y go-live."""
        required = (
            "**Datos personales siempre documentados**",
            "Ley 1581",
            "`datos.yml`",
            "**en el mismo PR**",
            "regenera los documentos",
            "factory#54",
            "cambia una finalidad",
            "dato sensible",
            "proveedor nuevo recibe datos",
            "puerta `legal`",
            "[COMPLETAR POR EL DUEÑO]",
            "puerta `go-live`",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.plan)


if __name__ == "__main__":
    unittest.main()
