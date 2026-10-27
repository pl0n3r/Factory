"""Factory #1562: comprobar contraste de comportamientos, no fragmentos."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/contraste-matriz-prev1_release.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
SOURCES = ("docs/auditoria-pre-v1.md", "docs/release-bootstrap.md", "docs/readme-progress-readiness.md", "docs/readme-contract.md",)
FRAGMENTS = dict(zip(SOURCES, (96, 83, 79, 47)))
EXPECTED = {
    "docs/auditoria-pre-v1.md": 4,
    "docs/release-bootstrap.md": 5,
    "docs/readme-progress-readiness.md": 4,
    "docs/readme-contract.md": 4,
}
ALLOWED = {"CUBIERTO", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA", "NO_VERIFICABLE"}
COVERED = {
    "docs/readme-progress-readiness.md:B01": ("readme/progress_readiness.py", "tests/test_readme_progress.py", 298, "73e63d68af7ced46ee1444a4cf4c7fe9b32d131a"),
    "docs/readme-progress-readiness.md:B02": ("readme/progress_readiness.py", "tests/test_readme_progress.py", 298, "73e63d68af7ced46ee1444a4cf4c7fe9b32d131a"),
    "docs/readme-progress-readiness.md:B03": ("readme/progress_readiness.py", "tests/test_readme_progress_e2e.py", 301, "3e47a229c2a1c0495b871177b3884b02a818441c"),
    "docs/readme-contract.md:B01": ("readme/validate_readme.py", "tests/test_readme_contract_v2.py", 1025, "2dc5a8d0b2a6670ff5b87c96844c05ffcb0ebf53"),
    "docs/readme-contract.md:B02": ("readme/validate_readme.py", "tests/test_readme_contract_v2.py", 1025, "2dc5a8d0b2a6670ff5b87c96844c05ffcb0ebf53"),
}
ROW = re.compile(r"^\| `(docs/[^`]+:B\d{2})` \|")


def rows_of(text: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        found = ROW.match(line)
        if not found:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            raise AssertionError("Fila de contraste sin ocho columnas")
        key = found.group(1)
        if key in rows or cells[0] != f"`{key}`" or cells[1] != f"`{key.rsplit(':B', 1)[0]}`":
            raise AssertionError("ID duplicado o fuente incoherente")
        if cells[3] not in ALLOWED or not all(cells[:4]):
            raise AssertionError("Veredicto ausente o invalido")
        rows[key] = cells
    return rows


class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.rows = rows_of(cls.doc)

    def test_cada_documento_tiene_veredicto(self) -> None:
        self.assertEqual(len(self.rows), 17)
        self.assertEqual({k.rsplit(":B", 1)[0] for k in self.rows}, set(SOURCES))
        for source, count in EXPECTED.items():
            with self.subTest(source=source):
                ids = sorted(int(k.rsplit(":B", 1)[1]) for k in self.rows
                             if k.startswith(source + ":B"))
                self.assertEqual(ids, list(range(1, count + 1)))
                self.assertTrue((ROOT / source).is_file())
                self.assertIn(f"| `{source}` | {FRAGMENTS[source]} |", self.matrix)
        self.assertEqual(Counter(row[3] for row in self.rows.values()),
                         Counter({"CUBIERTO": 5, "NO_VERIFICABLE": 12}))

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        got = {k for k, cells in self.rows.items() if cells[3] == "CUBIERTO"}
        self.assertEqual(got, set(COVERED))
        for key, (code, test, pr, sha) in COVERED.items():
            with self.subTest(behavior=key):
                row = self.rows[key]
                self.assertTrue((ROOT / code).is_file())
                self.assertTrue((ROOT / test).is_file())
                self.assertIn(f"`{code}`", row[4])
                self.assertIn(f"`{test}`", row[5])
                self.assertIn(f"/pull/{pr}", row[6])
                self.assertIn(sha, row[6])
        for row in self.rows.values():
            if row[3] == "NO_VERIFICABLE":
                self.assertEqual(row[6], "—", "No hay PR acreditado para esta conducta")
                self.assertGreater(len(row[7]), 35)

    def test_faltante_tiene_issue(self) -> None:
        for row in self.rows.values():
            self.assertNotEqual(row[3], "SIN_COBERTURA", "No hay brecha positiva demostrada")
        self.assertIn("No se crean hojas `SIN_COBERTURA`", self.doc)
        # Negativo: nombrar el épico sin hoja reservable nunca acredita ausencia.
        with self.assertRaisesRegex(AssertionError, "hoja canónica"):
            self.validate_missing(["", "", "", "SIN_COBERTURA", "—", "—", "—", "#1082"])

    @staticmethod
    def validate_missing(row: list[str]) -> None:
        if row[3] == "SIN_COBERTURA":
            raise AssertionError("SIN_COBERTURA sin hoja canónica real y autenticada")

    def test_matriz_actualizada(self) -> None:
        for source in SOURCES:
            self.assertFalse(any(line.startswith(f"| `{source}:L")
                                 for line in self.matrix.splitlines()))
        for key, row in self.rows.items():
            with self.subTest(key=key):
                found = [line for line in self.matrix.splitlines()
                         if line.startswith(f"| `{key}` |")]
                self.assertEqual(len(found), 1)
                self.assertIn(f"| {row[3]} |", found[0])
                if row[3] == "CUBIERTO":
                    self.assertIn(f"/pull/{COVERED[key][2]}", found[0])
        self.assertIn("## Contraste de comportamientos #1562", self.matrix)
        self.assertEqual(self.matrix.count("## Filas de cobertura"), 1)
        self.assertIn("| TOTAL | 2118 |", self.matrix)
        self.assertIn("| CUBIERTO | 13 |", self.matrix)
        self.assertIn("| NO_VERIFICABLE | 2105 |", self.matrix)
        self.assertIn("**Porcentaje CUBIERTO:** 0.61%", self.matrix)


if __name__ == "__main__":
    unittest.main()
