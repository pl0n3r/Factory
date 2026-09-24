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
        for value in (
            "TANDA 1 está cerrada",
            "Privacidad como código (#54) | ✅ Cerrado",
            "Publicación `v1.0.0` | ✅ Publicado + self-test en verde",
            "Adopción en Condor, GrindFlow y BRVTAL | 🚧 TANDA 2 en curso",
        ):
            self.assertIn(value, self.readme)

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
        for value in (
            "puerta `factory-release`",
            "canal `v1` solo cambia",
            "release protegido `v1.x`",
        ):
            self.assertIn(value, self.readme)
        self.assertIn("no mover `v1` ni publicar un release nuevo sin la puerta correspondiente", self.handoff)

if __name__ == "__main__":
    unittest.main()
