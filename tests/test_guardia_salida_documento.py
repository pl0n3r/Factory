#!/usr/bin/env python3
"""Contratos offline: evidencia parcial del OWNER no implica FSP-09/26 LISTO."""
from __future__ import annotations

from pathlib import Path
import unittest

DOC = Path(__file__).resolve().parents[1] / "docs" / "lista-salida-produccion.md"


class GuardiaSalidaDocumentoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        text = DOC.read_text(encoding="utf-8")
        cls.rows = {}
        for line in text.splitlines():
            if not line.startswith("| ") or "FSP-" not in line:
                continue
            fields = [part.strip() for part in line.strip("|").split("|")]
            if len(fields) != 5 or " — " not in fields[1]:
                continue
            ident = fields[1].split(" — ", 1)[0]
            cls.rows[ident] = {
                "area": fields[0],
                "status": fields[2].strip("`"),
                "evidence": fields[3],
                "issue": fields[4],
            }

    def test_fsp09_owner_parcial_y_pendientes(self) -> None:
        row = self.rows["FSP-09"]
        self.assertEqual("Monitoreo y alertas", row["area"])
        self.assertEqual("DEL_DUEÑO", row["status"])
        self.assertEqual("#1864", row["issue"])
        evidence = row["evidence"]
        for token in ("OWNER", "#6525360811", "pl0n3r",
                      "único guardia provisional", "incidente queda registrado",
                      "Horario", "canal", "escalamiento", "pendientes"):
            with self.subTest(token=token):
                self.assertIn(token, evidence)
        self.assertNotIn("No existe confirmación de la persona operadora", evidence)

    def test_fsp26_responsable_y_sla_pendiente(self) -> None:
        row = self.rows["FSP-26"]
        self.assertEqual("Soporte y operación diaria", row["area"])
        self.assertEqual("DEL_DUEÑO", row["status"])
        self.assertEqual("#1867", row["issue"])
        evidence = row["evidence"]
        for token in ("OWNER", "#6525361202", "pl0n3r",
                      "responsable nominal de soporte", "horario", "canal",
                      "live", "SLA", "no están acreditados"):
            with self.subTest(token=token):
                self.assertIn(token, evidence)
        self.assertNotIn("No existe persona", evidence)

    def test_no_se_declara_live_ni_cobertura(self) -> None:
        for ident in ("FSP-09", "FSP-26"):
            with self.subTest(ident=ident):
                row = self.rows[ident]
                self.assertEqual("DEL_DUEÑO", row["status"])
                self.assertIn("Exige decisión y recibo auténtico del OWNER",
                              row["evidence"])
                self.assertIn("No se declara ejecución o go-live", row["evidence"])
                self.assertNotIn("cobertura 24/7 acreditada", row["evidence"])
                self.assertNotIn("alertas recibidas y verificadas", row["evidence"])


if __name__ == "__main__":
    unittest.main()
