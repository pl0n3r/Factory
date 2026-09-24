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
        cls.readme = README.read_text(encoding="utf-8")
        cls.handoff = HANDOFF.read_text(encoding="utf-8")

    def test_completed_foundation_is_current(self):
        for value in (
            "Kit base reusable y template (#1) | ✅ Hecho",
            "Roles, orquestación, aceptación, métricas, producto, costos y memoria (#2–#8) | ✅ Hecho",
            "Entornos previos a producción (#11) | ✅ Hecho",
            "Arranque del repositorio (#14) | ✅ Hecho",
        ):
            self.assertIn(value, self.readme)

    def test_closed_historical_gates_are_current(self):
        for value in (
            "Puerta humana de notificación (#9) | ✅ Cerrado",
            "Resiliencia del dueño (#10) | ✅ Cerrado",
            "Cumplimiento técnico legal/datos (#12) | ✅ Cerrado",
            "#9, #10 y #12 están cerrados",
            "Épico de madurez (#13) | ⛔ Bloqueado únicamente por #54",
        ):
            self.assertIn(value, self.readme)

    def test_handoff_tracks_current_privacy_contract(self):
        for value in (
            "### #54 — privacidad como código · EN CURSO",
            "tres a seis documentos",
            "Quedan exactamente dos condiciones para cerrar #54",
            "Primera ejecución/reporte real del auditor semanal",
            "#71/#78",
            "#74/#75",
            "dry-run sanitizado equivalente",
        ):
            self.assertIn(value, self.handoff)

    def test_stale_blocker_regression_is_rejected(self):
        stale = (
            "Puerta humana de notificación (#9) | ⛔ Bloqueado",
            "Resiliencia del dueño (#10) | ⛔ Bloqueado",
            "Cumplimiento legal y de datos (#12) | ⛔ Bloqueado",
            "Épico de madurez (#13) | ⛔ Bloqueado por #9, #10 y #12",
            "Permanecen abiertos #9, #10 y #12",
        )
        for value in stale:
            self.assertNotIn(value, self.readme)
        self.assertIn(
            "Privacidad como código (#54) | ⛔ En curso",
            self.readme,
        )

    def test_release_bootstrap_and_tanda2_links(self):
        self.assertIn("[guía de bootstrap](docs/release-bootstrap.md)", self.readme)
        self.assertIn(
            "Adopción en Condor, GrindFlow y BRVTAL | ⏳ TANDA 2",
            self.readme,
        )
        self.assertIn("[release-bootstrap.md](release-bootstrap.md)", self.handoff)


if __name__ == "__main__":
    unittest.main()
