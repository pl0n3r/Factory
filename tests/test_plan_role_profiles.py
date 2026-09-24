"""Contrato documental: perfiles profesionales completos son obligatorios."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "PLAN-AGENTES.md"


class PlanRoleProfileTests(unittest.TestCase):
    """Fija la decisión del dueño sobre perfiles profesionales."""

    @classmethod
    def setUpClass(cls):
        cls.plan = PLAN.read_text(encoding="utf-8")

    def test_full_role_profiles_are_required(self):
        required = (
            "En todos los repos (factory, Condor, GrindFlow, BRVTAL)",
            "perfil completo",
            "agentes/roles/",
            "completa su checklist en el PR",
            "Etiqueta el Issue y el PR con cada rol asumido",
            "rol: <rol>",
            "role: <role>",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.plan)


if __name__ == "__main__":
    unittest.main()
