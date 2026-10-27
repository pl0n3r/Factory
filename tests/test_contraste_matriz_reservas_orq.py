"""Factory #1563: contrato de contraste por comportamiento, nunca por fragmentos."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRAST = ROOT / "docs/contraste-matriz-datos_arq.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
SOURCES = (
    "docs/liberacion-automatica-de-reservas.md",
    "docs/orquestador.md",
    "docs/automerge-construccion.md",
    "docs/no-work-dedup.md",
)
COUNTS = dict(zip(SOURCES, (86, 65, 39, 33)))
BEHAVIORS = dict(zip(SOURCES, (4, 4, 3, 3)))
ALLOWED = {"CUBIERTO", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA", "NO_VERIFICABLE"}
MERGED = {
    1515: "1072b8b26582d4285f4b8215ce5098548b4a03d8",
    1414: "67994aafbb5d2ce0e802dcb65a3dd1b1d46bd425",
}
COVERED = {
    "docs/liberacion-automatica-de-reservas.md:B03": (
        "scripts/lease_auto_release_integration.py",
        "tests/test_lease_hypothetical_action_preview.py", 1515
    ),
    "docs/orquestador.md:B03": (
        "scripts/coordinar_trabajo.py", "tests/test_coordinar_trabajo.py", 1414
    ),
}
ROW = re.compile(r"^\| `(docs/[^\x60]+:B\d{2})` \|")
ID = re.compile(r"^docs/(.+)\.md:B(\d{2})$")


def contrast_rows(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if match is None:
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            raise AssertionError("La fila de contraste debe tener ocho columnas")
        key = cells[0].strip("`")
        if key in result:
            raise AssertionError("ID de comportamiento duplicado: " + key)
        if cells[3] not in ALLOWED or not all(cells[:4]):
            raise AssertionError("Veredicto ausente o inválido: " + key)
        source = key.rsplit(":B", 1)[0]
        if cells[1] != f"`{source}`":
            raise AssertionError("Fuente del comportamiento no coincide con ID")
        result[key] = cells
    return result


def check_uncovered(row: list[str]) -> None:
    if row[3] != "SIN_COBERTURA":
        return
    # No basta nombrar un épico u otro ID: se exige hoja real registrada y
    # materializada por evidencia autenticada en una futura ampliación.
    raise AssertionError("SIN_COBERTURA sin hoja canónica auténtica verificada")


class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = CONTRAST.read_text(encoding="utf-8")
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.rows = contrast_rows(cls.doc)

    def test_cada_documento_tiene_veredicto(self) -> None:
        self.assertEqual(len(self.rows), sum(BEHAVIORS.values()))
        actual_sources = {key.rsplit(":B", 1)[0] for key in self.rows}
        self.assertEqual(actual_sources, set(SOURCES), "Fuente no declarada")
        for source, expected_count in BEHAVIORS.items():
            keys = [key for key in self.rows if key.startswith(source + ":B")]
            with self.subTest(source=source):
                self.assertEqual(len(keys), expected_count)
                self.assertEqual(
                    sorted(int(ID.fullmatch(key).group(2)) for key in keys),
                    list(range(1, expected_count + 1)),
                )
                self.assertTrue((ROOT / source).is_file())
        self.assertEqual(
            Counter(cells[3] for cells in self.rows.values()),
            Counter({"CUBIERTO": 2, "NO_VERIFICABLE": 12}),
        )

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        actual = {key for key, row in self.rows.items() if row[3] == "CUBIERTO"}
        self.assertEqual(actual, set(COVERED), "Cobertura ampliada sin prueba externa")
        for key in actual:
            with self.subTest(key=key):
                row = self.rows[key]
                implementation, test, pr = COVERED[key]
                self.assertTrue((ROOT / implementation).is_file())
                self.assertTrue((ROOT / test).is_file())
                self.assertIn(f"`{implementation}`", row[4])
                self.assertIn(f"`{test}`", row[5])
                self.assertIn(f"/pull/{pr}", row[6])
                self.assertIn(MERGED[pr], row[6])
        for key, row in self.rows.items():
            if row[3] == "NO_VERIFICABLE":
                self.assertEqual(row[6], "—", "Una prueba parcial no simula PR fusionado")
                self.assertGreater(len(row[7]), 25)

    def test_faltante_tiene_issue(self) -> None:
        for row in self.rows.values():
            check_uncovered(row)
        # Regresión negativa: NO_VERIFICABLE no es permiso de crear una hoja
        # supuesta; un futuro SIN_COBERTURA sin issue autentificado falla.
        with self.assertRaisesRegex(AssertionError, "hoja canónica"):
            check_uncovered(["", "", "", "SIN_COBERTURA", "—", "—", "—", "#1082"])
        self.assertIn("ninguna ausencia del runtime fue demostrada", self.doc)
        self.assertIn("sin atribuir pruebas inexistentes", self.doc)

    def test_matriz_actualizada(self) -> None:
        fragment_lines = [
            line for line in self.matrix.splitlines()
            if line.startswith("| `docs/") and any(
                line.startswith(f"| `{source}:L") for source in SOURCES
            )
        ]
        self.assertEqual(fragment_lines, [], "Persisten unidades fragmentarias del corte")
        for key, row in self.rows.items():
            with self.subTest(key=key):
                marker = f"| `{key}` |"
                matches = [line for line in self.matrix.splitlines() if line.startswith(marker)]
                self.assertEqual(len(matches), 1)
                self.assertIn(f"| {row[3]} |", matches[0])
        for source, count in COUNTS.items():
            # Los conteos originales siguen auditables: snapshot #1550.
            self.assertIn(f"| `{source}` | {count} |", self.matrix)
        self.assertEqual(self.matrix.count("## Filas de cobertura"), 1)
        self.assertIn("## Contraste de comportamientos #1563", self.matrix)


if __name__ == "__main__":
    unittest.main()
