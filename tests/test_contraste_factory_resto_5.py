#!/usr/bin/env python3
"""Regresión de 181 requisitos: bloque 5 Factory #1573."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/contraste-factory_resto_5.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
SOURCES = {
    "preview-preproduccion": 12,
    "principios-construccion": 31,
    "project-dna": 13,
    "provisioning": 16,
    "puertas-humanas-lenguaje-simple": 15,
    "quality-contract": 8,
    "quality-engineering": 7,
    "quality-gates": 4,
    "quality-project-dna": 10,
    "quality-regression": 21,
    "quality-sonar-watch": 23,
    "quality-sonar": 21,
}
BT = chr(96)
ROW = re.compile(r"^\| " + BT + r"(docs/([^:]+)\.md:L\d+-U\d+)" + BT + r" \|")
VALID = {"CUBIERTO", "NO_VERIFICABLE", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA"}


def parsed(text: str, *, detail: bool) -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if not match or match[2] not in SOURCES:
            continue
        cells = tuple(v.strip() for v in re.split(r"(?<!\\)\|", line)[1:-1])
        if len(cells) != (6 if detail else 5) or any(not v for v in cells):
            raise ValueError("Fila inválida: " + match[1])
        if cells[2] not in VALID:
            raise ValueError("Estado inventado: " + match[1])
        if match[1] in found:
            raise ValueError("Fila duplicada: " + match[1])
        found[match[1]] = cells
    return found


class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = DOC.read_text(encoding="utf-8")
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.details = parsed(cls.report, detail=True)
        cls.rows = parsed(cls.matrix, detail=False)

    def test_cada_fila_tiene_veredicto(self) -> None:
        self.assertEqual(len(self.details), 181)
        self.assertEqual(set(self.details), set(self.rows))
        totals: dict[str, int] = defaultdict(int)
        for key, item in self.details.items():
            name = key.split(":", 1)[0]
            totals[name.removeprefix("docs/").removesuffix(".md")] += 1
            with self.subTest(key=key):
                self.assertTrue((ROOT / name).is_file())
                self.assertEqual(item[1:3], self.rows[key][1:3])
                self.assertIn("[fuente](" + name.removeprefix("docs/") + ")", item[5])
        self.assertEqual(dict(totals), SOURCES)

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        # Nadie puede promover cobertura sin test exacto y PR histórico atribuido.
        for key, item in self.details.items():
            with self.subTest(key=key):
                self.assertEqual(item[2], "NO_VERIFICABLE")
                self.assertIn("aserción exacta y PR MERGED", item[5])
                pat = BT + r"(tests/[A-Za-z0-9_./-]+\.py)" + BT + r" \(candidata\)"
                test = re.fullmatch(pat, item[4])
                self.assertIsNotNone(test)
                self.assertTrue((ROOT / test[1]).is_file())
                if item[3] != "—":
                    path = item[3].strip(BT)
                    self.assertEqual(item[3], BT + path + BT)
                    self.assertTrue((ROOT / path).is_file())

    def test_faltante_tiene_issue(self) -> None:
        self.assertFalse(any(item[2] == "SIN_COBERTURA" for item in self.details.values()))
        example = next(line for line in self.report.splitlines() if ROW.match(line))
        bad_state = self.report.replace(example, example.replace("NO_VERIFICABLE", "SIN_PRUEBA"))
        with self.assertRaisesRegex(ValueError, "Estado inventado"):
            parsed(bad_state, detail=True)
        with self.assertRaisesRegex(ValueError, "Fila duplicada"):
            parsed(self.report + "\n" + example, detail=True)
        self.assertIn("| SIN_COBERTURA | 0 |", self.report)

    def test_matriz_actualizada(self) -> None:
        self.assertIn("## Contraste Factory, bloque 5 (#1573)", self.matrix)
        self.assertEqual(self.matrix.count("## Filas de cobertura"), 1)
        self.assertEqual(len(self.rows), 181)
        for key, row in self.rows.items():
            with self.subTest(key=key):
                self.assertEqual(row[2], "NO_VERIFICABLE")
                self.assertEqual(row[3].count("contraste-factory_resto_5.md"), 1)
                self.assertEqual(row[4], "—")
        self.assertIn("| TOTAL | 181 |", self.report)


if __name__ == "__main__":
    unittest.main()
