"""Prueba que el template expone la guía de vistas derivadas."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DOC = ROOT / "template" / "docs" / "derived-views.md"


class TemplateDerivedViewsTests(unittest.TestCase):
    def test_template_exposes_contract(self):
        text = TEMPLATE_DOC.read_text(encoding="utf-8")
        for value in (
            "fuente canónica",
            "vista derivada",
            "generated",
            "regression",
            "drift check",
            "falle cerrado",
        ):
            self.assertIn(value, text)

    def test_template_does_not_promote_views_to_authority(self):
        text = TEMPLATE_DOC.read_text(encoding="utf-8")
        self.assertIn("no debe ser una fuente de verdad", text)


if __name__ == "__main__":
    unittest.main()
