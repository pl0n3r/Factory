"""Contratos de documentación para el cierre de TANDA 1 y mantenimiento v1."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
HANDOFF = ROOT / "docs" / "tanda1-handoff.md"

class ReadmeTanda1Tests(unittest.TestCase):
    """Evita que el estado público de Factory vuelva a quedar obsoleto."""

    @classmethod
    def setUpClass(cls):
        cls.readme = README.read_text(encoding="utf-8")
        cls.handoff = HANDOFF.read_text(encoding="utf-8")

    def test_tanda1_and_first_release_are_closed(self):
        for value in ("Estado: **CERRADA**", "#54: privacidad como código cerrada",
                      "`v1.0.0`: GitHub Release publicada", "TANDA 1 global: completada",
                      "## TANDA 2 · EN CURSO"):
            self.assertIn(value, self.handoff)
        self.assertIn("PLAN-AGENTES.md", self.readme)
        self.assertNotIn("TANDA 1 está cerrada", self.readme)

    def test_tanda2_includes_factoryrunner(self):
        self.assertIn("Condor#192, GrindFlow#129, brvtal#630 y FactoryRunner#1", self.handoff)
        self.assertIn("PLAN-AGENTES.md", self.readme)

    def test_stale_pre_release_state_is_absent(self):
        for value in (
            "TANDA 1 sigue abierta",
            "`v1` y `v1.0.0` todavía no están publicados",
            "Privacidad como código (#54) | ⛔ En curso",
            "Publicación `v1.0.0` | ⏸️",
        ):
            self.assertNotIn(value, self.readme)

    def test_handoff_is_archived_as_closed(self):
        for value in (
            "Estado: **CERRADA**",
            "`v1.0.0`: GitHub Release publicada",
            "## TANDA 2 · EN CURSO",
            "factory-release",
            "[release-bootstrap.md](release-bootstrap.md)",
        ):
            self.assertIn(value, self.handoff)

    def test_release_maintenance_boundary_is_documented(self):
        for value in ("puerta humana `factory-release`",
                      "Un cambio en `main` no modifica por sí solo",
                      "no mover `v1` ni publicar un release nuevo sin la puerta correspondiente"):
            self.assertIn(value, self.handoff)
        self.assertIn("docs/release-bootstrap.md", self.readme)

if __name__ == "__main__":
    unittest.main()
