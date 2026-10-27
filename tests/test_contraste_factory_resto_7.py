#!/usr/bin/env python3
"""Factory #1575: inventario contrastado por fila, fail-closed ante evidencia incompleta."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/contraste-factory_resto_7.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
TICK = chr(96)
SOURCES = {
    "docs/sonar-superseded-ce.md": 9,
    "docs/tanda1-handoff.md": 10,
    "docs/unattended-handoff-consumer-pack.md": 24,
    "docs/unattended-kill-switch.md": 20,
    "docs/unattended-safe-mode-drill.md": 28,
    "docs/unattended-state-source.md": 18,
}
PR = re.compile(r"https://github\.com/pl0n3r/Factory/pull/([1-9][0-9]*)(?=[)#?\s]|$)")
KNOWN_MERGED = {1047, 804, 771, 760, 778}


def cells(line: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<!\\)\|", line)[1:-1]]


def rows(path: Path, width: int) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not any(line.startswith("| " + TICK + name + ":L") for name in SOURCES):
            continue
        data = cells(line)
        if len(data) != width or not data[0].startswith(TICK):
            raise AssertionError("Formato inválido del censo")
        key = data[0].strip(TICK)
        if key in output:
            raise AssertionError("Unidad duplicada: " + key)
        output[key] = data
    return output


def validate_gap(row: list[str]) -> None:
    if row[2] != "SIN_COBERTURA":
        return
    if "https://github.com/pl0n3r/Factory/issues/" not in row[-1]:
        raise AssertionError("SIN_COBERTURA requiere hoja canónica auténtica")
    raise AssertionError("La hoja nueva exige verificación autenticada")


class ContrasteTests(unittest.TestCase):
    def test_cada_fila_tiene_veredicto(self) -> None:
        contrast = rows(DOC, 7)
        original = rows(MATRIX, 5)
        self.assertEqual(len(contrast), 109)
        self.assertEqual(set(contrast), set(original))
        self.assertEqual(Counter(key.split(":L")[0] for key in contrast),
                         Counter(SOURCES))
        self.assertEqual(Counter(row[2] for row in contrast.values()),
                         {"NO_VERIFICABLE": 109})
        for path in SOURCES:
            self.assertTrue((ROOT / path).is_file())
        for key, row in contrast.items():
            self.assertGreater(len(row[1]), 10, key)
            self.assertGreater(len(row[6]), 35, key)

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        for key, row in rows(DOC, 7).items():
            with self.subTest(key=key):
                code, proof, evidence = row[3:6]
                if row[2] == "CUBIERTO":
                    self.assertNotIn("—", (code, proof, evidence))
                if code == "—":
                    self.assertEqual((proof, evidence), ("—", "—"))
                    continue
                self.assertTrue((ROOT / code.strip(TICK)).is_file())
                self.assertTrue((ROOT / proof.strip(TICK)).is_file())
                prs = PR.findall(evidence)
                self.assertEqual(len(prs), 1)
                self.assertIn(int(prs[0]), KNOWN_MERGED)
        # A fake covered row without proof cannot satisfy this contract.
        with self.assertRaises(AssertionError):
            validate_covered(["", "", "CUBIERTO", "—", "—", "—", ""])

    def test_faltante_tiene_issue(self) -> None:
        for row in rows(DOC, 7).values():
            validate_gap(row)
        with self.assertRaisesRegex(AssertionError, "hoja canónica"):
            validate_gap(["", "", "SIN_COBERTURA", "—", "—", "—", "sin hoja"])
        self.assertIn("No se inventaron Issues", DOC.read_text(encoding="utf-8"))

    def test_matriz_actualizada(self) -> None:
        matrix_text = MATRIX.read_text(encoding="utf-8")
        self.assertIn("## Contraste Factory, bloque 7 (#1575)", matrix_text)
        self.assertIn("main@8088e66c2366f2483d5229fc6fda8718f1ab46a0", matrix_text)
        in_matrix = rows(MATRIX, 5)
        in_doc = rows(DOC, 7)
        self.assertEqual(set(in_matrix), set(in_doc))
        for key, row in in_doc.items():
            with self.subTest(key=key):
                self.assertEqual(row[2], in_matrix[key][2])
                self.assertIn("[#1575](contraste-factory_resto_7.md)", in_matrix[key][3])
                self.assertEqual(in_matrix[key][2], "NO_VERIFICABLE")


def validate_covered(row: list[str]) -> None:
    if row[2] == "CUBIERTO" and (
        row[3] == "—" or row[4] == "—" or len(PR.findall(row[5])) != 1
    ):
        raise AssertionError("CUBIERTO sin código, prueba y PR")


if __name__ == "__main__":
    unittest.main()
