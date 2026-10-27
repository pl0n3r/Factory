"""Factory #1564: aceptación offline del contraste de comportamientos."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/contraste-matriz-living_runner.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
SOURCES = ["docs/factory-living-software.md","docs/factoryrunner-execution-plane.md","docs/dieta-factory.md","docs/factory-lab.md"]
FRAGMENTS = {"docs/factory-living-software.md":84,"docs/factoryrunner-execution-plane.md":63,"docs/dieta-factory.md":59,"docs/factory-lab.md":35}
EXPECTED = {"docs/factory-living-software.md":6,"docs/factoryrunner-execution-plane.md":6,"docs/dieta-factory.md":5,"docs/factory-lab.md":6}
COVERED = {
  "docs/factory-living-software.md:B01": [
    "evolution/constitution.py",
    "tests/test_living_constitution.py",
    199,
    "445f41ca3858ba1726d6013d996763a68f5c05a4"
  ],
  "docs/factory-living-software.md:B02": [
    "evolution/constitution.py",
    "tests/test_living_constitution.py",
    199,
    "445f41ca3858ba1726d6013d996763a68f5c05a4"
  ],
  "docs/factory-living-software.md:B03": [
    "evolution/constitution.py",
    "tests/test_living_constitution.py",
    199,
    "445f41ca3858ba1726d6013d996763a68f5c05a4"
  ],
  "docs/factory-living-software.md:B04": [
    "evolution/constitution.py",
    "tests/test_living_constitution.py",
    199,
    "445f41ca3858ba1726d6013d996763a68f5c05a4"
  ],
  "docs/dieta-factory.md:B02": [
    ".github/workflows/factory-ci.yml",
    "tests/test_dieta_fase1a.py",
    1304,
    "2e20aef7fd8b019c677acec37e18d711341662cc"
  ],
  "docs/dieta-factory.md:B03": [
    ".github/workflows/factory-ci.yml",
    "tests/test_factory_lab_contract.py",
    1304,
    "2e20aef7fd8b019c677acec37e18d711341662cc"
  ],
  "docs/factory-lab.md:B01": [
    "lab/factory_lab.py",
    "tests/test_factory_lab_contract.py",
    210,
    "be8c5776e716d5115f2e9040e73ab1ecfd464851"
  ],
  "docs/factory-lab.md:B02": [
    "lab/factory_lab.py",
    "tests/test_factory_lab_contract.py",
    210,
    "be8c5776e716d5115f2e9040e73ab1ecfd464851"
  ],
  "docs/factory-lab.md:B03": [
    "lab/experiment_evidence.py",
    "tests/test_experiment_evidence.py",
    291,
    "3e6b1640a780b94fd21ab99d4f17be18f3ca1d44"
  ],
  "docs/factory-lab.md:B04": [
    "lab/factory_lab.py",
    "tests/test_factory_lab_contract.py",
    219,
    "5f22c659288bd2013213a234f61eae285d7f8ed3"
  ]
}
ALLOWED = {"CUBIERTO", "NO_VERIFICABLE", "NO_APLICA", "DESCARTADO", "SIN_COBERTURA"}

def rows_of(text: str) -> dict[str, list[str]]:
    result = {}
    for line in text.splitlines():
        if not line.startswith("| " + chr(96) + "docs/") or ":B" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 8:
            raise AssertionError("Fila sin ocho columnas")
        key = cells[0].strip(chr(96))
        if key in result or cells[0] != f"{chr(96)}{key}{chr(96)}":
            raise AssertionError("ID sin autoridad o duplicado")
        source = key.rsplit(":B", 1)[0]
        if source not in SOURCES or cells[1] != f"{chr(96)}{source}{chr(96)}":
            raise AssertionError("Fuente no autorizada")
        if cells[3] not in ALLOWED or not cells[2] or not cells[7]:
            raise AssertionError("Veredicto o razón ausentes")
        result[key] = cells
    return result

class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.rows = rows_of(cls.doc)

    def test_cada_documento_tiene_veredicto(self) -> None:
        self.assertEqual(len(self.rows), sum(EXPECTED.values()))
        self.assertEqual({k.rsplit(":B", 1)[0] for k in self.rows}, set(SOURCES))
        self.assertEqual(Counter(row[3] for row in self.rows.values()),
                         Counter({"CUBIERTO": 10, "NO_VERIFICABLE": 12, "NO_APLICA": 1}))
        for source, count in EXPECTED.items():
            with self.subTest(source=source):
                indices = sorted(int(k.rsplit(":B", 1)[1]) for k in self.rows
                                 if k.startswith(source + ":B"))
                self.assertEqual(indices, list(range(1, count + 1)))
                self.assertTrue((ROOT / source).is_file())
                self.assertIn(f"| {chr(96)}{source}{chr(96)} | {FRAGMENTS[source]} |", self.matrix)

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        actual = {key for key, row in self.rows.items() if row[3] == "CUBIERTO"}
        self.assertEqual(actual, set(COVERED))
        for key, (code, test, pr, sha) in COVERED.items():
            with self.subTest(key=key):
                row = self.rows[key]
                self.assertTrue((ROOT / code).is_file(), code)
                self.assertTrue((ROOT / test).is_file(), test)
                self.assertIn(code, row[4])
                self.assertIn(test, row[5])
                self.assertIn(f"https://github.com/pl0n3r/Factory/pull/{pr}", row[6])
                self.assertIn(sha, row[6])
        for row in self.rows.values():
            if row[3] != "CUBIERTO":
                self.assertEqual(row[6], "—")
                self.assertGreater(len(row[7]), 39)

    def test_faltante_tiene_issue(self) -> None:
        self.assertFalse(any(row[3] == "SIN_COBERTURA" for row in self.rows.values()))
        self.assertIn("No se crean hojas", self.doc)
        with self.assertRaisesRegex(AssertionError, "hoja canónica"):
            self.assert_missing(["", "", "", "SIN_COBERTURA", "—", "—", "—", "#1082"])

    @staticmethod
    def assert_missing(row: list[str]) -> None:
        if row[3] == "SIN_COBERTURA":
            raise AssertionError("SIN_COBERTURA sin hoja canónica")

    def test_matriz_actualizada(self) -> None:
        for source in SOURCES:
            self.assertFalse(any(line.startswith("| " + chr(96) + source + ":L")
                                 for line in self.matrix.splitlines()))
        for key, row in self.rows.items():
            with self.subTest(key=key):
                found = [line for line in self.matrix.splitlines()
                         if line.startswith("| " + chr(96) + key + chr(96) + " |")]
                self.assertEqual(len(found), 1)
                self.assertIn(f"| {row[3]} |", found[0])
                if row[3] == "CUBIERTO":
                    self.assertIn(f"/pull/{COVERED[key][2]}", found[0])
        self.assertIn("## Contraste de comportamientos #1564", self.matrix)
        body = self.matrix.split("## Filas de cobertura", 1)[1].split(
            "## Producción y mejoras pendientes", 1)[0]
        live = [line for line in body.splitlines() if line.startswith("| " + chr(96))]
        counts = Counter(status for line in live
                         for status in ("CUBIERTO", "NO_VERIFICABLE", "NO_APLICA",
                                        "SIN_COBERTURA", "EN_CURSO", "DESCARTADO")
                         if f"| {status} |" in line)
        self.assertGreater(len(live), len(self.rows))
        for state, count in counts.items():
            self.assertIn(f"| {state} | {count} |", self.matrix)
        self.assertIn(f"| TOTAL | {len(live)} |", self.matrix)
        pct = f"{100 * counts['CUBIERTO'] / len(live):.2f}%"
        self.assertIn(f"**Porcentaje CUBIERTO:** {pct}", self.matrix)

if __name__ == "__main__":
    unittest.main()
