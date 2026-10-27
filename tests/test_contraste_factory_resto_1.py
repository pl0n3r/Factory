#!/usr/bin/env python3
"""Contrato de contraste, Factory #1569: 176 filas, evidencia y fuente exacta."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
CONTRASTE = ROOT / "docs/contraste-factory_resto_1.md"
SOURCES = ["ISSUE-1080", "ISSUE-1082", "ISSUE-1382", "ISSUE-304", "ISSUE-305", "docs/aceptacion-ejecutable.md", "docs/adaptive-orchestration.md", "docs/ai-gateway.md", "docs/autonomy-engine.md", "docs/capability-authority.md", "docs/context-compiler.md", "docs/conversacion-agentes.md", "docs/coordinacion-pr-validation.md", "docs/costos-presupuestos.md"]
STATES = {"CUBIERTO", "NO_VERIFICABLE", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA"}

def rows(document: str) -> dict[str, dict[str, str]]:
    result = {}
    for line in document.splitlines():
        match = re.match(r"^\\| \\x60([^\\x60]+)\\x60 \\| ", line)
        if not match or not any(match[1].startswith(src + ":") for src in SOURCES):
            continue
        columns = [c.strip() for c in re.split(r"(?<!\\\\)\\|", line)]
        if match[1] in result or len(columns) < 7:
            raise ValueError("Fila duplicada o incompleta")
        status = next((c for c in columns if c in STATES), None)
        if status is None:
            raise ValueError("Estado ausente")
        result[match[1]] = {"line": line, "state": status}
    return result

class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.doc = CONTRASTE.read_text(encoding="utf-8")
        cls.source_rows = rows(cls.matrix)
        cls.verdicts = rows(cls.doc)

    def test_cada_fila_tiene_veredicto(self):
        self.assertEqual(len(self.source_rows), 176)
        self.assertEqual(set(self.verdicts), set(self.source_rows))
        self.assertEqual(Counter(i.split(":")[0] for i in self.source_rows),
                         Counter(i.split(":")[0] for i in self.verdicts))
        for key, info in self.verdicts.items():
            self.assertIn(info["state"], STATES)
            self.assertIn("fuente", info["line"].lower(), key)

    def test_cubierto_enlaza_prueba_existente(self):
        for key, info in self.verdicts.items():
            if info["state"] != "CUBIERTO":
                continue
            self.assertRegex(info["line"], r"tests/[^\\x60]+\\.py::[A-Za-z_]+::test_[A-Za-z_]+")
            test = re.search(r"(tests/[^\\x60]+\\.py)::([A-Za-z_]+)::(test_[A-Za-z_]+)", info["line"])
            self.assertIsNotNone(test, key)
            path = ROOT / test[1]
            self.assertTrue(path.is_file(), key)
            self.assertRegex(path.read_text(encoding="utf-8"), r"def\\s+" + test[3] + r"\\(")
            self.assertRegex(info["line"], r"github\\.com/pl0n3r/Factory/pull/\\d+")
        self.assertIn("NO_VERIFICABLE", self.doc)

    def test_faltante_tiene_issue(self):
        for key, info in self.verdicts.items():
            if info["state"] == "SIN_COBERTURA":
                self.assertRegex(info["line"], r"github\\.com/pl0n3r/Factory/issues/\\d+")
                self.assertNotIn("issues/1569", info["line"])
        # Regresión negativa: no se acepta un estado arbitrario.
        with self.assertRaises(ValueError):
            rows("| \\x60ISSUE-304:AC-01\\x60 | Ficticio | SIN_PRUEBA | --- | --- | --- |")

    def test_matriz_actualizada(self):
        self.assertEqual(set(self.verdicts), set(self.source_rows))
        for key, verdict in self.verdicts.items():
            source = self.source_rows[key]
            self.assertEqual(source["state"], verdict["state"], key)
            self.assertIn("contraste-factory_resto_1.md", source["line"], key)
        self.assertIn("## Contraste de filas Factory, bloque 1 (#1569)", self.matrix)
        self.assertIn("main@8088e66c2366f2483d5229fc6fda8718f1ab46a0", self.matrix)

if __name__ == "__main__":
    unittest.main()
