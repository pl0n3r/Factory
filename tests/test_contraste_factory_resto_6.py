#!/usr/bin/env python3
"""Factory #1574: aceptación del contraste de 187 unidades sin sobreafirmar."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
CONTRAST = ROOT / "docs/contraste-factory_resto_6.md"
SOURCES = (
    "docs/reconciliacion-issues-20261024.md",
    "docs/recovery-adapters.md", "docs/recovery-contract.md",
    "docs/recovery-drill.md", "docs/recovery-e2e.md",
    "docs/recovery-pipeline.md", "docs/recovery-status.md",
    "docs/release-runbook.md", "docs/resiliencia-fabrica.md",
    "docs/retroalimentacion-producto.md", "docs/reusable-permission-compat.md",
    "docs/reusable-release-rollback.md", "docs/risk-compiler.md",
    "docs/roles-profesionales.md",
)
STATES = {"CUBIERTO", "NO_VERIFICABLE", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA"}
COVERED = "docs/recovery-status.md:L13-U1"


def rows(text: str, *, contrast: bool) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = re.match(r"^\| `([^`]+:L\d+-U\d+)` \|", line)
        if match is None or not any(
            match[1].startswith(source + ":") for source in SOURCES
        ):
            continue
        cells = [item.strip() for item in re.split(r"(?<!\\)\|", line)]
        if len(cells) != (8 if contrast else 7):
            raise ValueError("Fila incompleta " + match[1])
        value = cells[1:-1]
        if match[1] in found:
            raise ValueError("Fila duplicada " + match[1])
        if value[2] not in STATES:
            raise ValueError("Veredicto ausente " + match[1])
        found[match[1]] = value
    return found


class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix_text = MATRIX.read_text(encoding="utf-8")
        cls.doc_text = CONTRAST.read_text(encoding="utf-8")
        cls.matrix = rows(cls.matrix_text, contrast=False)
        cls.doc = rows(cls.doc_text, contrast=True)

    def test_cada_fila_tiene_veredicto(self) -> None:
        self.assertEqual(len(self.matrix), 187)
        self.assertEqual(set(self.matrix), set(self.doc))
        self.assertEqual(len(SOURCES), 14)
        for key, value in self.doc.items():
            with self.subTest(key=key):
                source = key.split(":L", 1)[0]
                self.assertTrue((ROOT / source).is_file())
                self.assertIn("[fuente](" + source.removeprefix("docs/") + ")", value[5])
                self.assertEqual(value[2], self.matrix[key][2])
                self.assertTrue(value[1])

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        covered = {key for key, value in self.doc.items() if value[2] == "CUBIERTO"}
        self.assertEqual(covered, {COVERED})
        for key in covered:
            value = self.doc[key]
            self.assertEqual(value[3], "`recovery/status.py`")
            self.assertIn("`tests/test_recovery_status.py`", value[4])
            self.assertTrue((ROOT / "recovery/status.py").is_file())
            self.assertTrue((ROOT / "tests/test_recovery_status.py").is_file())
            self.assertIn("/pull/1528", value[5])
            self.assertIn("465bc1e711ea", value[5])
            self.assertIn("VERIFIED", value[5])
            self.assertIn("/pull/1528", self.matrix[key][3])
        for key, value in self.doc.items():
            if value[2] != "NO_VERIFICABLE":
                continue
            self.assertIn("(candidata)", value[4], key)
            self.assertIn("sin aserción exacta", value[5], key)
            test = value[4].split("`")[1]
            self.assertTrue((ROOT / test).is_file(), key)
            if value[3] != "—":
                self.assertTrue((ROOT / value[3].strip("`")).is_file(), key)

    def test_faltante_tiene_issue(self) -> None:
        for key, value in self.doc.items():
            if value[2] == "SIN_COBERTURA":
                self.assertRegex(value[5], r"github\.com/pl0n3r/Factory/issues/\d+", key)
        self.assertEqual(Counter(value[2] for value in self.doc.values()),
                         Counter({"CUBIERTO": 1, "NO_VERIFICABLE": 186}))
        # Un estado inventado o duplicado nunca equivale a cobertura.
        with self.assertRaisesRegex(ValueError, "Veredicto ausente"):
            rows("| `docs/recovery-drill.md:L99-U1` | x | FABRICADO | — | — |",
                 contrast=False)

    def test_matriz_actualizada(self) -> None:
        self.assertEqual(set(self.doc), set(self.matrix))
        for key, value in self.matrix.items():
            with self.subTest(key=key):
                self.assertEqual(value[2], self.doc[key][2])
                self.assertEqual(value[3].count("contraste-factory_resto_6.md"), 1)
        self.assertIn("## Contraste Factory, bloque 6 (#1574)", self.matrix_text)
        self.assertEqual(self.matrix_text.count("## Filas de cobertura"), 1)
        self.assertIn("main@8088e66c2366f2483d5229fc6fda8718f1ab46a0",
                      self.matrix_text)
        with self.assertRaisesRegex(ValueError, "Fila duplicada"):
            duplicate = "| `docs/recovery-drill.md:L1-U1` | x | NO_VERIFICABLE | — | — |"
            rows(duplicate + "\n" + duplicate, contrast=False)


if __name__ == "__main__":
    unittest.main()
