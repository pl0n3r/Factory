#!/usr/bin/env python3
"""Factory #1571: QA del contraste por unidad histórica."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
CONTRAST = ROOT / "docs/contraste-factory_resto_3.md"
SOURCES = {
    "issue-contract-preflight": 8, "knowledge-lifecycle": 27,
    "knowledge-operations-e2e": 9, "knowledge-operations": 22,
    "knowledge-postmortem": 12, "knowledge-selection": 3,
    "label-color-sync": 22, "lease-phase-a-artifact-qa": 8,
    "lista-salida-produccion": 16, "living-software-operational-e2e": 22,
    "memoria-institucional": 11, "observador-reservas-consumidor": 22,
}
STATES = {"CUBIERTO", "NO_VERIFICABLE", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA"}
BACKTICK = chr(96)
ROW = re.compile(r"^\| " + BACKTICK + r"(?P<id>docs/(?P<source>[^:]+)\.md:L\d+-U\d+)" + BACKTICK + r" \|")
ISSUE = re.compile(r"https://github\.com/pl0n3r/Factory/issues/[1-9]\d*")


def read_rows(text: str, *, contrast: bool) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    expected = 6 if contrast else 5
    for line in text.splitlines():
        match = ROW.match(line)
        if match is None or match["source"] not in SOURCES:
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) != expected or any(not c for c in cells):
            raise ValueError("Fila incompleta: " + match["id"])
        if cells[2] not in STATES:
            raise ValueError("Veredicto inválido: " + match["id"])
        if match["id"] in result:
            raise ValueError("Fila repetida: " + match["id"])
        result[match["id"]] = cells
    return result


class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mtext = MATRIX.read_text(encoding="utf-8")
        cls.ctext = CONTRAST.read_text(encoding="utf-8")
        cls.mrows = read_rows(cls.mtext, contrast=False)
        cls.crows = read_rows(cls.ctext, contrast=True)

    def test_cada_fila_tiene_veredicto(self) -> None:
        self.assertEqual(len(self.crows), 182)
        self.assertEqual(set(self.crows), set(self.mrows))
        self.assertEqual(
            Counter(key.split(":", 1)[0].removeprefix("docs/").removesuffix(".md")
                    for key in self.crows),
            Counter(SOURCES),
        )
        for key, cells in self.crows.items():
            with self.subTest(key=key):
                src = key.split(":", 1)[0]
                self.assertTrue((ROOT / src).is_file())
                self.assertIn("[fuente](" + src.removeprefix("docs/") + ")", cells[5])
                self.assertEqual(cells[1], self.mrows[key][1])
                self.assertEqual(cells[2], self.mrows[key][2])
                self.assertIn("sin aserción exacta", cells[5].lower())

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        # No promover candidatos a CUBIERTO sin triple evidencia exacta y VERIFIED.
        self.assertEqual({k for k, v in self.crows.items() if v[2] == "CUBIERTO"}, set())
        for key, row in self.crows.items():
            for candidate in (row[3], row[4]):
                if candidate == "—":
                    continue
                patt = (BACKTICK + r"([A-Za-z0-9_./-]+)" + BACKTICK
                        + r"(?: \(candidata\))?")
                match = re.fullmatch(patt, candidate)
                self.assertIsNotNone(match, key)
                self.assertTrue((ROOT / match[1]).is_file(), key)

    def test_faltante_tiene_issue(self) -> None:
        self.assertEqual(Counter(v[2] for v in self.crows.values()),
                         Counter({"NO_VERIFICABLE": 182}))
        for key, row in self.crows.items():
            if row[2] == "SIN_COBERTURA":
                self.assertRegex(row[5], ISSUE, key)
        original = next(line for line in self.ctext.splitlines() if ROW.match(line))
        altered = self.ctext.replace(original, original.replace("NO_VERIFICABLE", "FICTICIO"), 1)
        with self.assertRaisesRegex(ValueError, "Veredicto inválido"):
            read_rows(altered, contrast=True)
        with self.assertRaisesRegex(ValueError, "Fila repetida"):
            read_rows(self.ctext + "\n" + original, contrast=True)

    def test_matriz_actualizada(self) -> None:
        self.assertIn("## Contraste Factory, bloque 3 (#1571)", self.mtext)
        self.assertEqual(self.mtext.count("## Filas de cobertura"), 1)
        self.assertEqual(len(self.mrows), 182)
        for key, row in self.mrows.items():
            with self.subTest(key=key):
                self.assertEqual(row[2], "NO_VERIFICABLE")
                self.assertEqual(row[3].count("contraste-factory_resto_3.md"), 1)
                self.assertEqual(row[4], "—")
                self.assertEqual(row[1], self.crows[key][1])
        self.assertIn("| TOTAL | 182 |", self.ctext)
        self.assertIn("## Resumen verificable", self.mtext)


if __name__ == "__main__":
    unittest.main()
