"""Contratos de documentación para el cierre de TANDA 1."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
HANDOFF = ROOT / "docs" / "tanda1-handoff.md"


class ReadmeTanda1Tests(unittest.TestCase):
    """Evita que el estado público de Factory vuelva a quedar obsoleto."""

    @classmethod
    def setUpClass(cls):
        """Carga README y handoff una sola vez."""
        cls.readme = README.read_text(encoding="utf-8")
        cls.handoff = HANDOFF.read_text(encoding="utf-8")

    def test_completed_foundation_is_current(self):
        """AC-01: la base completada y el bloqueo de TANDA 1 son explícitos."""
        for value in (
            "Kit base reusable y template (#1) | ✅ Hecho",
            "Roles, orquestación, aceptación, métricas, producto, costos y memoria (#2–#8) | ✅ Hecho",
            "Entornos previos a producción (#11) | ✅ Hecho",
            "Arranque del repositorio (#14) | ✅ Hecho",
            "TANDA 1 está técnicamente avanzada y bloqueada por evidencia externa/material",
        ):
            self.assertIn(value, self.readme)
        self.assertNotIn(
            "la madurez #2–#12 y la publicación `v1.0.0` siguen pendientes",
            self.readme,
        )

    def test_remaining_human_gates_are_explicit(self):
        """AC-02: #9, #10 y #12 concentran los blockers restantes del épico."""
        for value in (
            "Puerta humana de notificación (#9) | ⛔ Bloqueado",
            "Resiliencia del dueño (#10) | ⛔ Bloqueado",
            "Cumplimiento legal y de datos (#12) | ⛔ Bloqueado",
            "Épico de madurez (#13) | ⛔ Bloqueado por #9, #10 y #12",
        ):
            self.assertIn(value, self.readme)

    def test_handoff_fails_closed(self):
        """AC-03: el handoff nombra la evidencia faltante sin fabricarla."""
        for value in (
            "confirmar externamente",
            "CI, deploy y observer",
            "referencia vigente a política de privacidad",
            "revisión jurídica humana",
            "snapshot npm reproducible",
            "cubre el inventario de licencias de #12",
            "no publicado y no autorizado",
            "Default seguro",
        ):
            self.assertIn(value, self.handoff)

    def test_release_bootstrap_and_tanda2_links(self):
        """AC-04: README enlaza bootstrap y mantiene adopción en TANDA 2."""
        self.assertIn("[guía de bootstrap](docs/release-bootstrap.md)", self.readme)
        self.assertIn(
            "Adopción en Condor, GrindFlow y BRVTAL | ⏳ TANDA 2",
            self.readme,
        )
        self.assertIn("[release-bootstrap.md](release-bootstrap.md)", self.handoff)


if __name__ == "__main__":
    unittest.main()
