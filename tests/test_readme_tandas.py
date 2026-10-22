"""Estado de tandas verificado en ESTADO.md y PLAN-AGENTES.md."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
ESTADO = (ROOT / "ESTADO.md").read_text(encoding="utf-8")
ARCHIVE = (ROOT / "docs/archivo/plan-agentes-tandas-1-2.md").read_text(encoding="utf-8")


class ReadmeTandasTests(unittest.TestCase):
    def test_tanda_2_status_is_visible(self):
        self.assertIn("- **TANDA 2:** COMPLETADA", ESTADO)
        for item in ("Condor#192", "GrindFlow#129", "brvtal#630", "FactoryRunner#1"):
            self.assertIn(item, ESTADO)
        self.assertNotIn("### Estado de las tandas", README)

    def test_tanda_3_requires_all_tanda_2_epics(self):
        self.assertIn("TANDA 3 solo figura ACTIVA cuando los cuatro épicos canónicos", ESTADO)
        self.assertIn("cerrados, con razón `completed`", ESTADO)
        self.assertIn("**Gate de tanda antes de prioridades:**", PLAN)

    def test_tanda_3_priority_and_fronts_are_visible(self):
        for value in ("Issue abierto de incidente", "prioridad: crítica", "prioridad: alta", "media"):
            self.assertIn(value, PLAN)
        for value in ("Condor", "GrindFlow", "BRVTAL", "FactoryRunner"):
            self.assertIn(value, ARCHIVE)

    def test_roadmap_contains_tanda_3(self):
        self.assertIn("- **TANDA 3:** ACTIVA", ESTADO)
        self.assertIn("## TANDA 3: desarrollo normal", PLAN)
        self.assertNotIn("🔒 Bloqueada hasta completar", README)

    def test_governance_summary_does_not_drift(self):
        self.assertIn("PLAN-AGENTES.md", README)
        self.assertIn("Cola automática canónica:** Factory, Condor, GrindFlow", PLAN)
        self.assertIn("ControlBot, AutoFactory y FactoryRunner", PLAN)


if __name__ == "__main__":
    unittest.main()
