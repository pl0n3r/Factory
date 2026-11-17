"""Regresión del alcance A7: código de referencia no acredita operación viva."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
A7 = ROOT / "docs" / "auditoria-autonomia" / "10-orq-local.md"
B1 = ROOT / "docs" / "auditoria-autonomia" / "07-causa-raiz.md"
SOURCE = "https://github.com/pl0n3r/ControlBot/blob/c87d56cb11e54bed244d1bd79fb4773ae9e43edf/tools/orquestador-local/orq.py"


class OrqSourceDocTests(unittest.TestCase):
    def test_source_and_runtime_distinction(self):
        a7 = A7.read_text(encoding="utf-8")
        b1 = B1.read_text(encoding="utf-8")
        self.assertIn(SOURCE, a7)
        self.assertIn(SOURCE, b1)
        self.assertIn("prototipo de referencia no desplegado", a7)
        self.assertIn("NO DEMOSTRADOS", a7)
        self.assertIn("NO DEMOSTRADA", b1)
        self.assertIn("404", a7)
        self.assertNotIn("Sin código ni logs del orquestador", a7)
        self.assertNotIn("sin código ni eventos correlacionados", b1)

    def test_reference_not_live_authority(self):
        a7 = A7.read_text(encoding="utf-8")
        self.assertIn("PLANNER.max_active=99", a7)
        self.assertIn("X-Agent-Key", a7)
        self.assertIn("D-061", a7)
        self.assertIn("FactoryRunner #465", a7)
        self.assertIn("NO DEMOSTRADO", a7)


if __name__ == "__main__":
    unittest.main()
