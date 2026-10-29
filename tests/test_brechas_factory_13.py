#!/usr/bin/env python3
"""Factory #1631: sixteen derived-view gaps with fail-closed synthetic contracts.

LOCAL_CONTRACT never asserts live operation, an external SHA, or product readiness.
"""
from __future__ import annotations
import ast
import json
from pathlib import Path
import unittest

from intelligence.derived_views import (
    DerivedViewSpec, DerivedViewError, DerivedViewDriftError,
    render_markdown_table, check_drift, replace_delimited_block,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
SOURCE = "docs/derived-views.md"
MANIFEST = "config/derived_views.json"
REGRESSION = "tests/test_readme_tandas.py"
Q = chr(96)
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
CLAUSES = {
    "docs/derived-views.md:L14-U1": (14, "drift_check"),
    "docs/derived-views.md:L18-U1": (18, "función pura: sin red, reloj, aleatoriedad"),
    "docs/derived-views.md:L18-U2": (18, "exactamente los mismos bytes"),
    "docs/derived-views.md:L24-U1": (24, "falla cerrado ante cualquier diferencia"),
    "docs/derived-views.md:L24-U2": (24, "No se debe “arreglar” la fuente"),
    "docs/derived-views.md:L28-U1": (28, "comprobar claims concretos"),
    "docs/derived-views.md:L28-U2": (28, "evita inventar una extracción estructurada"),
    "docs/derived-views.md:L3-U1": (3, "nunca es una fuente de verdad"),
    "docs/derived-views.md:L3-U2": (3, "solo materializa o verifica"),
    "docs/derived-views.md:L34-U1": (34, "no debe convertir el README en fuente de verdad"),
    "docs/derived-views.md:L38-U1": (38, "Identifique la fuente canónica"),
    "docs/derived-views.md:L39-U1": (39, "Registre la vista en el manifiesto"),
    "docs/derived-views.md:L40-U1": (40, "solo si puede demostrar determinismo"),
    "docs/derived-views.md:L40-U2": (40, "de lo contrario use"),
    "docs/derived-views.md:L41-U1": (41, "Añada un drift check determinista"),
    "docs/derived-views.md:L42-U1": (42, "Documente el límite y la reversión"),
}


def parse_matrix(raw: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(raw, str) or not raw:
        raise ValueError("UNKNOWN: matriz ilegible")
    result = {}
    for line in raw.splitlines():
        if not any(line.startswith(f"| {Q}{key}{Q} |") for key in CLAUSES):
            continue
        parts = tuple(piece.strip() for piece in line.strip("|").split("|"))
        if (len(parts) != 5 or parts[0] in result
                or parts[2] != "NO_VERIFICABLE" or not parts[3] or not parts[4]):
            raise ValueError("UNKNOWN: fila ambigua")
        result[parts[0]] = parts
    if set(result) != {f"{Q}{key}{Q}" for key in CLAUSES}:
        raise ValueError("UNKNOWN: falta una fila")
    return {key: result[f"{Q}{key}{Q}"] for key in CLAUSES}


def source_clause(key: str, source: object) -> bool:
    if key not in CLAUSES or not isinstance(source, str):
        return False
    line_no, phrase = CLAUSES[key]
    lines = source.splitlines()
    return line_no <= len(lines) and phrase.casefold() in lines[line_no-1].casefold()


def inspect(key: str, matrix: object, source: object, manifest: object) -> dict[str, str]:
    result = {"code": UNKNOWN, "production": UNKNOWN, "authority": UNKNOWN}
    if (key not in CLAUSES or not isinstance(matrix, dict)
            or key not in matrix or not source_clause(key, source)):
        return result
    row = matrix[key]
    if (len(row) != 5 or row[0] != f"{Q}{key}{Q}"
            or row[2] != "NO_VERIFICABLE"
            or "No se confirmó test + PR fusionado" not in row[3]):
        return result
    try:
        data = json.loads(manifest) if isinstance(manifest, str) else None
        if not isinstance(data, dict) or data.get("version") != 1:
            return result
        items = data.get("views")
        if not isinstance(items, list) or not items:
            return result
        views = [DerivedViewSpec(**v) for v in items]
        for view in views:
            view.validate()
        if len({view.view_id for view in views}) != len(views):
            return result
    except (ValueError, TypeError, DerivedViewError):
        return result
    result["code"] = LOCAL
    return result


class BrechasFactory13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {
            key: (ROOT / key).read_text(encoding="utf-8")
            for key in (MATRIX, SOURCE, MANIFEST, REGRESSION)
        }
        cls.rows = parse_matrix(cls.sources[MATRIX])

    def test_contrato_principal(self):
        """AC-01: exact 16 clauses and exercised local primitives."""
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(self.rows))
        for key in CLAUSES:
            with self.subTest(clause=key):
                self.assertTrue(source_clause(key, self.sources[SOURCE]))
                self.assertEqual(LOCAL, inspect(
                    key, self.rows, self.sources[SOURCE], self.sources[MANIFEST]
                )["code"])
        fixtures = [{"id": "z", "text": "a|b"}, {"id": "a", "text": "ok"}]
        expected = render_markdown_table(fixtures, ("id", "text"), sort_by="id")
        self.assertEqual(expected, render_markdown_table(
            fixtures[::-1], ("id", "text"), sort_by="id"))
        self.assertIn(r"a\|b", expected)
        self.assertTrue(expected.endswith("\n"))
        check_drift(expected, expected)
        self.assertEqual("start\nnew\nend", replace_delimited_block(
            "start\nold\nend", start_marker="start", end_marker="end",
            content="new"))
        specs = json.loads(self.sources[MANIFEST])["views"]
        regression = next(s for s in specs
                          if s["view_id"] == "factory.readme.tandas")
        self.assertEqual("regression", regression["mode"])
        self.assertIsNone(regression["generator"])
        self.assertIn("PLAN-AGENTES.md", regression["source"])
        self.assertIn("test_readme_tandas.py", regression["drift_check"])
        self.assertIn("test_governance_summary_does_not_drift",
                      self.sources[REGRESSION])

    def test_falla_cerrado(self):
        """AC-02: missing, mutated, duplicated and forged evidence => UNKNOWN."""
        for key in CLAUSES:
            with self.subTest(clause=key):
                missing = dict(self.rows)
                del missing[key]
                self.assertEqual(UNKNOWN, inspect(
                    key, missing, self.sources[SOURCE], self.sources[MANIFEST]
                )["code"])
                broken = self.sources[SOURCE].replace(CLAUSES[key][1],
                                                      "UNVERIFIED", 1)
                self.assertEqual(UNKNOWN, inspect(
                    key, self.rows, broken, self.sources[MANIFEST])["code"])
                fake = dict(self.rows)
                row = list(fake[key])
                row[2] = "CUBIERTO"
                fake[key] = tuple(row)
                self.assertEqual(UNKNOWN, inspect(
                    key, fake, self.sources[SOURCE], self.sources[MANIFEST]
                )["code"])
        first = next(line for line in self.sources[MATRIX].splitlines()
                     if line.startswith(f"| {Q}docs/derived-views.md:L14-U1{Q} |"))
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            parse_matrix(self.sources[MATRIX] + "\n" + first)
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            parse_matrix(self.sources[MATRIX].replace(first, ""))
        self.assertEqual(UNKNOWN, inspect(
            next(iter(CLAUSES)), self.rows, self.sources[SOURCE], "{broken"
        )["code"])
        with self.assertRaises(DerivedViewDriftError):
            check_drift("expected\n", "expected")
        with self.assertRaises(DerivedViewError):
            DerivedViewSpec("bad", "README", "README", "regression",
                            None, "tests/guard.py").validate()
        with self.assertRaises(DerivedViewError):
            DerivedViewSpec("bad", "source", "view", "generated",
                            None, "tests/guard.py").validate()

    def test_sin_datos_reales(self):
        """AC-03: no network, credential access, subprocess or personal data."""
        own = Path(__file__).read_text(encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(own)):
            if isinstance(node, ast.Import):
                imports.update(n.name.split(".")[0] for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertLessEqual(imports, {
            "__future__", "ast", "json", "pathlib", "unittest", "intelligence"})
        self.assertEqual(set(self.sources), {MATRIX, SOURCE, MANIFEST, REGRESSION})
        for path in self.sources:
            self.assertTrue((ROOT / path).is_file())
            self.assertFalse(Path(path).is_absolute())

    def test_estados_unknown_explicitos(self):
        """AC-04: no synthetic signals can authorize CI, source or production."""
        for key in CLAUSES:
            with self.subTest(clause=key):
                result = inspect(key, self.rows,
                                 self.sources[SOURCE], self.sources[MANIFEST])
                self.assertEqual(UNKNOWN, result["production"])
                self.assertEqual(UNKNOWN, result["authority"])
        fake = json.loads(self.sources[MANIFEST])
        fake["views"].append(dict(fake["views"][0]))
        first = next(iter(CLAUSES))
        self.assertEqual(UNKNOWN, inspect(
            first, self.rows, self.sources[SOURCE], json.dumps(fake))["code"])
        fake["views"][-1]["view_id"] = "other"
        fake["views"][-1]["source"] = fake["views"][-1]["view"]
        self.assertEqual(UNKNOWN, inspect(
            first, self.rows, self.sources[SOURCE], json.dumps(fake))["code"])


if __name__ == "__main__":
    unittest.main()
