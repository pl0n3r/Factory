#!/usr/bin/env python3
"""Criterios AC-01..04 de Factory#1551, evidencia fail-closed de go-live."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "lista-salida-produccion.md"
STATES = {"LISTO", "EN_CURSO", "SIN_COBERTURA", "DEL_DUEÑO", "NO_APLICA"}
AREAS = {
    "Respaldos y restauración", "Monitoreo y alertas", "Dominios, DNS y TLS",
    "Secretos y accesos", "Costos y límites", "Privacidad y legal de lanzamiento",
    "Soporte y operación diaria", "Migración de datos",
    "Reversión y apagado de emergencia", "Seguridad y pruebas",
    "Accesibilidad y rendimiento", "Smoke de producción",
    "Continuidad de proveedores",
}
ROW_PATTERN = re.compile(
    r"^\|\s*([^|]+)\|\s*(FSP-\d{2})\s+—\s+([^|]+)"
    r"\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|$",
    re.MULTILINE,
)


class ListaSalidaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = DOC.read_text(encoding="utf-8")
        cls.rows = [
            {"area": area.strip(), "id": ident, "requirement": requirement.strip(),
             "status": status.strip().strip(chr(96)), "evidence": evidence.strip(),
             "issue": issue.strip()}
            for area, ident, requirement, status, evidence, issue
            in ROW_PATTERN.findall(cls.text)
        ]

    def test_cubre_todo_el_alcance(self) -> None:
        self.assertEqual(AREAS, {r["area"] for r in self.rows})
        self.assertGreaterEqual(len(self.rows), 50)
        for area in AREAS:
            with self.subTest(area=area):
                self.assertGreaterEqual(sum(r["area"] == area for r in self.rows), 3)
        for token in (
            "3-2-1-1-0", "restauración", "GitHub", "ChatGPT",
            "DNS", "TLS", "secretos", "gasto", "privacidad",
            "soporte", "migraciones", "rollback", "apagado",
            "seguridad", "accesibilidad", "carga", "smoke",
        ):
            with self.subTest(keyword=token):
                self.assertIn(token.casefold(), self.text.casefold())

    def test_sin_cobertura_tiene_issue(self) -> None:
        gaps = [r for r in self.rows if r["status"] == "SIN_COBERTURA"]
        self.assertGreaterEqual(len(gaps), 1)
        for row in gaps:
            with self.subTest(id=row["id"]):
                self.assertRegex(row["issue"], r"^#\d+$")
                self.assertRegex(row["evidence"], r"Hoja canónica #\d+")
                self.assertNotIn(row["issue"], {"#1", "#1082", "#304", "#305"})
        self.assertEqual({"#1553"}, {r["issue"] for r in gaps})
        self.assertIn("https://github.com/pl0n3r/Factory/issues/1553", self.text)

    def test_formato_y_estados(self) -> None:
        self.assertIn("| Área | ID / requisito | Estado | Evidencia y condición | Issue |", self.text)
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)), "Duplicación de ID de requisito")
        self.assertEqual([f"FSP-{i:02d}" for i in range(1, len(ids) + 1)], ids)
        expected_lines = [
            line for line in self.text.splitlines()
            if re.match(r"^\|[^|]+\|\s*FSP-\d{2}", line)
        ]
        self.assertEqual(len(expected_lines), len(self.rows), "Fila truncada")
        for row in self.rows:
            with self.subTest(id=row["id"]):
                self.assertIn(row["area"], AREAS)
                self.assertIn(row["status"], STATES)
                self.assertTrue(row["requirement"])
                self.assertGreater(len(row["evidence"]), 45)
                if row["status"] == "LISTO":
                    self.assertTrue(any(t in row["evidence"] for t in
                        ("tests/", "seguridad/test_", "metricas/test_")))
                    self.assertIn("main@", row["evidence"])
                if row["status"] == "EN_CURSO":
                    self.assertRegex(row["issue"], r"^#\d+$")
                    self.assertNotIn(row["issue"], {"#1", "#1082", "#304", "#305"})
                if row["status"] == "DEL_DUEÑO":
                    self.assertIn("OWNER", row["evidence"])
                if row["status"] == "NO_APLICA":
                    self.assertIn("NO_APLICA al runtime", row["evidence"])

    def test_resumen_final(self) -> None:
        counts = Counter(r["status"] for r in self.rows)
        for state in STATES:
            self.assertIn(f"| {state} | {counts[state]} |", self.text)
        self.assertIn(f"| **TOTAL** | **{len(self.rows)}** |", self.text)
        self.assertIn("Hojas canónicas nuevas creadas por esta auditoría: 1", self.text)
        self.assertIn("## Qué impide go-live hoy", self.text)
        for evidence in ("#305", "D-066", "OWNER", "Factory@v1", "#1553"):
            self.assertIn(evidence, self.text)


if __name__ == "__main__":
    unittest.main()
