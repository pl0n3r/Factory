#!/usr/bin/env python3
"""Regresión offline de 174 cláusulas del contraste Factory #1572."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
DOCUMENT = ROOT / "docs/contraste-factory_resto_4.md"
SOURCES = (
    "organizational-complexity", "performance-brvtal",
    "performance-ci-professional-report", "performance-ci-suite-benchmark",
    "performance-classification", "performance-classifier",
    "performance-contract", "performance-detection",
    "performance-engineering", "performance-github-actions-ci",
    "performance-grindflow", "performance-remediation",
    "performance-team-compiler-bridge", "portfolio-signals",
    "pr-label-governance",
)
STATES = {"CUBIERTO", "NO_VERIFICABLE", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA"}

def rows(document: str) -> dict[str, dict[str, str]]:
    out = {}
    tick = chr(96)
    prefix = re.compile(r"^\| " + tick + r"([^" + tick + r"]+)" + tick + r" \| ")
    for line in document.splitlines():
        matched = prefix.match(line)
        if not matched:
            continue
        key = matched[1]
        if not any(key.startswith("docs/" + source + ".md:") for source in SOURCES):
            continue
        if key in out:
            raise ValueError("Requisito duplicado: " + key)
        fields = [item.strip() for item in re.split(r"(?<!\\)\|", line)]
        state = next((item for item in fields if item in STATES), None)
        if state is None or len(fields) < 7:
            raise ValueError("Fila inválida: " + key)
        out[key] = {"state": state, "line": line}
    return out

def validate_missing(key: str, line: str) -> None:
    if "github.com/pl0n3r/Factory/issues/" not in line or "issues/1572" in line:
        raise ValueError("SIN_COBERTURA sin hoja creada: " + key)

class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.document = DOCUMENT.read_text(encoding="utf-8")
        cls.expected = rows(cls.matrix)
        cls.actual = rows(cls.document)

    def test_cada_fila_tiene_veredicto(self):
        self.assertEqual(len(self.expected), 174)
        self.assertEqual(set(self.expected), set(self.actual))
        self.assertEqual(
            Counter(k.split(":")[0] for k in self.expected),
            Counter(k.split(":")[0] for k in self.actual),
        )
        for key, row in self.actual.items():
            self.assertIn(row["state"], STATES, key)
            self.assertRegex(row["line"], r"\[fuente\]\([^)]+\.md\)")

    def test_cubierto_enlaza_prueba_existente(self):
        present = 0
        for key, row in self.actual.items():
            if row["state"] != "CUBIERTO":
                continue
            present += 1
            test = re.search(
                r"(tests/[\w/.-]+\.py)::([A-Za-z_]\w*)::(test_[A-Za-z_]\w*)",
                row["line"],
            )
            self.assertIsNotNone(test, key)
            path = ROOT / test[1]
            self.assertTrue(path.is_file(), key)
            self.assertIn(
                "def " + test[3] + "(", path.read_text(encoding="utf-8"), key
            )
            self.assertRegex(row["line"], r"github\.com/pl0n3r/Factory/pull/\d+")
            self.assertRegex(row["line"], r"[0-9a-f]{12,40}")
        self.assertGreaterEqual(present, 1)

    def test_faltante_tiene_issue(self):
        for key, row in self.actual.items():
            if row["state"] == "SIN_COBERTURA":
                validate_missing(key, row["line"])
        with self.assertRaises(ValueError):
            validate_missing("fake", "Sin issue")
        with self.assertRaises(ValueError):
            duplicate = "| " + chr(96) + "docs/performance-contract.md:L9-U1" + chr(96) + " | a | NO_VERIFICABLE | b | c | d |"
            rows(duplicate + "\n" + duplicate)

    def test_matriz_actualizada(self):
        self.assertEqual(set(self.expected), set(self.actual))
        for key, row in self.actual.items():
            original = self.expected[key]
            self.assertEqual(original["state"], row["state"], key)
            if key == "docs/performance-remediation.md:L25-U3":
                self.assertIn("PR #1548", original["line"])
            else:
                self.assertIn("contraste-factory_resto_4.md", original["line"], key)
        self.assertIn("## Contraste Factory, bloque 4 (#1572)", self.matrix)
        self.assertIn("main@8088e66c2366f2483d5229fc6fda8718f1ab46a0", self.matrix)

if __name__ == "__main__":
    unittest.main()
