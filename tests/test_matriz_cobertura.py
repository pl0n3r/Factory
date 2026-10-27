#!/usr/bin/env python3
"""Contrato ejecutable de la matriz de cobertura Factory #1550."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "docs" / "matriz-cobertura.md"
STATES = {"CUBIERTO", "EN_CURSO", "SIN_COBERTURA", "DESCARTADO", "NO_VERIFICABLE"}
EPIC_CRITERIA = {304: 12, 305: 12, 1080: 4, 1082: 4, 1296: 0, 1382: 7}
ISSUE_LINK = re.compile(r"https://github\.com/pl0n3r/Factory/issues/(\d+)")


def rows_from_markdown(text: str) -> list[dict[str, str]]:
    if text.count("## Filas de cobertura") != 1:
        raise ValueError("Tabla principal duplicada o ausente")
    section = text.split("## Filas de cobertura", 1)[1]
    if "## Producción y mejoras pendientes" not in section:
        raise ValueError("Falta la sección de límites productivos")
    section = section.split("## Producción y mejoras pendientes", 1)[0]
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith(("| ID/fuente", "| ---")):
            continue
        parts = [p.strip() for p in re.split(r"(?<!\\)\|", line)]
        if len(parts) != 7 or parts[0] or parts[-1]:
            raise ValueError("La fila no tiene cinco columnas")
        source, description, state, evidence, issue = parts[1:-1]
        if not all([source, description, state, evidence, issue]):
            raise ValueError("Celda vacía")
        if not source.startswith(chr(96)) or not source.endswith(chr(96)):
            raise ValueError("ID sin backticks")
        source = source[1:-1]
        if source in seen:
            raise ValueError("Identificador duplicado: " + source)
        seen.add(source)
        if state not in STATES:
            raise ValueError("Estado desconocido: " + state)
        if "https://github.com/" not in evidence or not ISSUE_LINK.search(issue):
            raise ValueError("Evidencia/Issue no verificables")
        if state == "CUBIERTO" and not (
            "github.com/pl0n3r/Factory/pull/" in evidence
            and ("scripts/" in evidence or "tests/" in evidence)
        ):
            raise ValueError("Cobertura sin código/prueba y PR fusionado")
        output.append({"id": source, "state": state, "issue": issue})
    if not output:
        raise ValueError("Tabla de cobertura vacía")
    return output


def normative_ids(path: Path) -> set[str]:
    """Una fila por documento y encabezado ## / ### fuera de bloques de código."""
    name = path.relative_to(ROOT).as_posix()
    ids = {f"{name}:L1"}
    in_fence = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith((chr(96) * 3, "~~~")):
            in_fence = not in_fence
        elif not in_fence and re.match(r"^#{2,3}\s+.+", line):
            ids.add(f"{name}:L{line_number}")
    return ids


class MatrizCoberturaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = FILE.read_text(encoding="utf-8")
        cls.rows = rows_from_markdown(cls.text)
        cls.by_id = {row["id"]: row for row in cls.rows}

    def test_cubre_todas_las_fuentes(self) -> None:
        expected = normative_ids(ROOT / "AGENTES.md")
        documents = sorted(
            p for p in (ROOT / "docs").glob("*.md") if p != FILE
        )
        self.assertGreaterEqual(len(documents), 100)
        for doc in documents:
            expected.update(normative_ids(doc))
        for number, count in EPIC_CRITERIA.items():
            expected.add(f"ISSUE-{number}:GENERAL")
            expected.update(
                f"ISSUE-{number}:AC-{i:02d}" for i in range(1, count + 1)
            )
        self.assertEqual(set(self.by_id), expected)
        self.assertEqual("CUBIERTO", self.by_id["docs/orquestador.md:L117"]["state"])

    def test_sin_cobertura_tiene_issue(self) -> None:
        for row in self.rows:
            if row["state"] == "SIN_COBERTURA":
                self.assertRegex(row["issue"], ISSUE_LINK)
                self.assertNotIn("/issues/1550", row["issue"])
        bad = (
            "## Filas de cobertura\n"
            "| " + chr(96) + "fake" + chr(96)
            + " | requisito | SIN_COBERTURA | [Fuente](https://github.com/test) "
            "| sin issue |\n"
            "## Producción y mejoras pendientes\n"
        )
        with self.assertRaises(ValueError):
            rows_from_markdown(bad)

    def test_formato_y_estados(self) -> None:
        self.assertGreater(len(self.rows), 100)
        self.assertEqual(len(self.by_id), len(self.rows))
        good = (
            "| " + chr(96) + "fake" + chr(96)
            + " | requisito | EN_CURSO | [Fuente](https://github.com/test) "
            "| [#1550](https://github.com/pl0n3r/Factory/issues/1550) |\n"
        )
        with self.assertRaises(ValueError):
            rows_from_markdown(
                "## Filas de cobertura\n" + good.replace("EN_CURSO", "INVENTADO")
                + "## Producción y mejoras pendientes"
            )
        with self.assertRaises(ValueError):
            rows_from_markdown(
                "## Filas de cobertura\n" + good + good
                + "## Producción y mejoras pendientes"
            )

    def test_resumen_por_estado(self) -> None:
        counts = Counter(row["state"] for row in self.rows)
        summary = self.text.split("## Resumen verificable", 1)[1]
        for state in STATES:
            match = re.search(rf"^\| {state} \| (\d+) \|$", summary, re.MULTILINE)
            self.assertIsNotNone(match, state)
            self.assertEqual(int(match.group(1)), counts[state])
        total = re.search(r"^\| TOTAL \| (\d+) \|$", summary, re.MULTILINE)
        self.assertIsNotNone(total)
        self.assertEqual(int(total.group(1)), len(self.rows))
        pct = re.search(
            r"\*\*Porcentaje CUBIERTO:\*\* (\d+\.\d{2})% \((\d+)/(\d+)\)\.",
            summary,
        )
        self.assertIsNotNone(pct)
        self.assertEqual(int(pct.group(2)), counts["CUBIERTO"])
        self.assertEqual(int(pct.group(3)), len(self.rows))
        self.assertEqual(
            float(pct.group(1)),
            round(100 * counts["CUBIERTO"] / len(self.rows), 2),
        )


if __name__ == "__main__":
    unittest.main()
