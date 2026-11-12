"""Regresión fail-closed para pruebas citadas por filas de cobertura."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "matriz-cobertura.md"
ROW_RE = re.compile(r"^\|\s*\x60([^\x60]+)\x60\s*\|")
TEST_RE = re.compile(r"(?<![\w/])tests/test_[A-Za-z0-9_-]+\.py\b")
PERFORMANCE_IDS = (
    "docs/performance-engineering.md:L11-U1",
    "docs/performance-engineering.md:L12-U1",
    "docs/performance-engineering.md:L13-U1",
    "docs/performance-engineering.md:L14-U1",
    "docs/performance-engineering.md:L16-U1",
    "docs/performance-engineering.md:L20-U1",
)


def rows_from_matrix(content: str) -> list[tuple[int, str, str]]:
    """Ignora cabeceras y extrae únicamente filas identificadas."""
    rows: list[tuple[int, str, str]] = []
    for number, line in enumerate(content.splitlines(), 1):
        match = ROW_RE.match(line)
        if match:
            rows.append((number, match.group(1), line))
    return rows


def nonexistent_references(content: str, root: Path) -> list[str]:
    """Rechaza cualquier ruta de test Python citada por una fila e inexistente."""
    missing: list[str] = []
    for line_number, requirement, row in rows_from_matrix(content):
        for relative in sorted(set(TEST_RE.findall(row))):
            if not (root / relative).is_file():
                missing.append(f"{requirement} (línea {line_number}): {relative}")
    return missing


class MatrizPruebasExistenTests(unittest.TestCase):
    def test_criterio_principal(self) -> None:
        """El estado de las filas no exime de verificar archivos referenciados."""
        content = MATRIX.read_text(encoding="utf-8")
        rows = rows_from_matrix(content)
        self.assertTrue(rows, "Matriz sin filas")
        self.assertTrue(
            any(TEST_RE.search(row) for _, _, row in rows),
            "No se encontraron referencias verificables: prueba vacía",
        )
        self.assertEqual(
            [], nonexistent_references(content, ROOT),
            "Existen referencias a ficheros de prueba ausentes",
        )

    def test_detecta_faltante_y_admite_archivo_real(self) -> None:
        """La regresión pasa de RED a GREEN solo cuando el archivo existe."""
        row = "| \x60demo:L1-U1\x60 | brecha | NO_VERIFICABLE | tests/test_ausente.py |"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(1, len(nonexistent_references(row, root)))
            file = root / "tests" / "test_ausente.py"
            file.parent.mkdir(parents=True)
            file.write_text("def test_ejemplo(): assert True\n", encoding="utf-8")
            self.assertEqual([], nonexistent_references(row, root))

    def test_seis_filas_performance_sin_promocion(self) -> None:
        """Las seis filas permanecen no verificables, sin ruta candidata falsa."""
        by_id = {
            identifier: row
            for _, identifier, row in rows_from_matrix(MATRIX.read_text(encoding="utf-8"))
        }
        for identifier in PERFORMANCE_IDS:
            with self.subTest(requirement=identifier):
                self.assertIn(identifier, by_id)
                row = by_id[identifier]
                self.assertIn("| NO_VERIFICABLE |", row)
                self.assertNotIn("tests/test_performance_status.py", row)


if __name__ == "__main__":
    unittest.main()
