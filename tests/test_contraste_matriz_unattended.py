#!/usr/bin/env python3
"""Factory #1565: regresiones de contraste normativo unattended."""
from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/contraste-matriz-unattended.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
SOURCES = ("docs/unattended-safe-mode.md", "docs/unattended-runtime-guards.md",
           "docs/unattended-daily-summary.md", "docs/unattended-watchdog.md",
           "docs/unattended-watchdog-runtime.md")
OLD_COUNTS = (53, 44, 38, 34, 32)
EXPECTED = {f"{path}:B{i:02d}" for path in SOURCES for i in range(1, 5)}
MERGED = {747: "073b46e8e0a0bd81b081f0b6a678e2681a088d68",
          754: "e1509bfe9d133d0dda58ecb3f898201d5ccdc53e",
          786: "2964992a8833e10627e353132c24358ecce99de9",
          789: "6c69a6cfd594ce5ba7617e2b0c22257045b2e477",
          750: "a06303d528c9c2065b9f14829c6a7489a6c96529",
          911: "b233504ec6c03449a37677353bac59a24e88efac"}
ALLOWED = {"CUBIERTO", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA", "NO_VERIFICABLE"}
TICK = chr(96)

PR_LINK = re.compile(
    r"https://github\.com/pl0n3r/Factory/pull/([1-9][0-9]*)(?=[)#?\s]|$)"
)


def pr_numbers(text: str) -> list[int]:
    """Read complete PR numbers from canonical links, never numeric prefixes."""
    return [int(value) for value in PR_LINK.findall(text)]


def rows():
    found = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| " + TICK + "docs/unattended-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 8:
            raise AssertionError("Se requieren ocho columnas")
        key = cells[0].strip(TICK)
        if ":B" not in key:
            continue
        if key in found or cells[3] not in ALLOWED:
            raise AssertionError("ID duplicado o veredicto inválido: " + key)
        if cells[1] != TICK + key.rsplit(":B", 1)[0] + TICK:
            raise AssertionError("Fuente/ID inconsistentes")
        found[key] = cells
    return found

def assert_gap_has_issue(row):
    if row[3] != "SIN_COBERTURA":
        return
    marker = re.search(r"https://github\.com/pl0n3r/Factory/issues/(\d+)", row[7])
    if marker is None or int(marker.group(1)) in {1082, 1565}:
        raise AssertionError("SIN_COBERTURA sin hoja canónica real")
    raise AssertionError("Hoja nueva requiere comprobación autenticada y registro")

class ContrasteTests(unittest.TestCase):
    def test_cada_documento_tiene_veredicto(self):
        data = rows()
        self.assertEqual(set(data), EXPECTED)
        self.assertEqual(Counter(row[3] for row in data.values()),
                         Counter({"CUBIERTO": 15, "NO_VERIFICABLE": 5}))
        for source in SOURCES:
            self.assertTrue((ROOT / source).is_file())
            self.assertEqual(len([x for x in data if x.startswith(source + ":B")]), 4)
        self.assertIn("F1G eliminó su cron", DOC.read_text(encoding="utf-8"))

    def test_cubierto_enlaza_prueba_existente(self):
        for key, row in rows().items():
            if row[3] != "CUBIERTO":
                self.assertEqual(row[6], "—")
                self.assertGreater(len(row[7]), 30)
                continue
            with self.subTest(key=key):
                code, proof, ref = row[4], row[5], row[6]
                self.assertTrue(code.startswith(TICK + "scripts/"))
                self.assertTrue(proof.startswith(TICK + "tests/"))
                self.assertTrue((ROOT / code.strip(TICK)).is_file())
                self.assertTrue((ROOT / proof.strip(TICK)).is_file())
                matches = pr_numbers(ref)
                self.assertEqual(len(matches), 1)
                number = matches[0]
                self.assertIn(number, MERGED)
                self.assertIn(MERGED[number], ref)

    def test_faltante_tiene_issue(self):
        for row in rows().values():
            assert_gap_has_issue(row)
        with self.assertRaisesRegex(AssertionError, "hoja canónica"):
            assert_gap_has_issue(["", "", "", "SIN_COBERTURA", "—", "—", "—", "#1082"])
        self.assertIn("No se abrió ninguna hoja", DOC.read_text(encoding="utf-8"))

    def test_procedencia_b02_b03_exact_sha(self):
        """Una prueba documental nunca debe atribuir evidencia a un PR anterior."""
        matrix_lines = MATRIX.read_text(encoding="utf-8").splitlines()
        provenances = {
            "docs/unattended-runtime-guards.md:B02":
                (750, "a06303d528c9c2065b9f14829c6a7489a6c96529",
                 747, "073b46e8e0a0bd81b081f0b6a678e2681a088d68"),
            "docs/unattended-daily-summary.md:B03":
                (911, "b233504ec6c03449a37677353bac59a24e88efac",
                 789, "6c69a6cfd594ce5ba7617e2b0c22257045b2e477"),
        }
        for key, (number, sha, old_number, old_sha) in provenances.items():
            with self.subTest(row=key):
                row = rows()[key]
                self.assertEqual(row[3], "CUBIERTO")
                self.assertEqual(pr_numbers(row[6]), [number])
                self.assertIn(sha, row[6])
                self.assertNotIn(old_number, pr_numbers(row[6]))
                self.assertNotIn(old_sha, row[6])
                matching = [line for line in matrix_lines
                            if line.startswith("| " + TICK + key + TICK + " |")]
                self.assertEqual(len(matching), 1)
                self.assertEqual(pr_numbers(matching[0]), [number])
                self.assertIn(sha, matching[0])
                self.assertNotIn(old_number, pr_numbers(matching[0]))
                self.assertNotIn(old_sha, matching[0])

    def test_rechaza_pr_con_sufijo(self):
        """Ni 7500 ni 9110 se confunden con el único PR permitido."""
        for expected in (750, 911):
            with self.subTest(expected=expected):
                original = f"https://github.com/pl0n3r/Factory/pull/{expected}"
                false_match = f"https://github.com/pl0n3r/Factory/pull/{expected}0"
                self.assertEqual(pr_numbers(f"[PR]({original})"), [expected])
                self.assertEqual(pr_numbers(f"[PR]({false_match})"), [expected * 10])
                self.assertNotEqual(pr_numbers(f"[PR]({false_match})"), [expected])
                self.assertNotEqual(
                    pr_numbers(f"[PR]({original}), [otro]({false_match})"),
                    [expected],
                )

    def test_matriz_actualizada(self):
        text = MATRIX.read_text(encoding="utf-8")
        lines = text.splitlines()
        for source, count in zip(SOURCES, OLD_COUNTS):
            self.assertIn("| " + TICK + source + TICK + " | " + str(count) + " |", text)
            self.assertFalse(any(x.startswith("| " + TICK + source + ":L") for x in lines))
        for key, row in rows().items():
            with self.subTest(key=key):
                matches = [x for x in lines if x.startswith("| " + TICK + key + TICK + " |")]
                self.assertEqual(len(matches), 1)
                self.assertIn("| " + row[3] + " |", matches[0])
                self.assertIn("contraste-matriz-unattended.md", matches[0])
                if row[3] == "CUBIERTO":
                    ref = pr_numbers(row[6])
                    self.assertEqual(len(ref), 1)
                    self.assertEqual(pr_numbers(matches[0]), ref)
        self.assertIn("## Contraste de comportamientos #1565", text)

if __name__ == "__main__":
    unittest.main()
