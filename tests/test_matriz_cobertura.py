#!/usr/bin/env python3
"""Aceptación ejecutable del censo de requisitos Factory #1550."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
BASE_SHA = "9c12107bd64ef4bbc45b3baf4f961a6ce6f14664"
STATES = {"CUBIERTO", "EN_CURSO", "SIN_COBERTURA", "DESCARTADO", "NO_VERIFICABLE"}
EPIC_AC = {304: 12, 305: 12, 1080: 4, 1082: 4, 1296: 0, 1382: 7}
ISSUE = re.compile(r"https://github\.com/pl0n3r/Factory/issues/(\d+)")
MODAL = re.compile(
    r"(debe|deben|deberá|requier|exig|obligat|prohib|nunca|solo|únicamente|"
    r"siempre|must|shall|fail.closed|falla cerr|no se|no puede|no acepta|"
    r"se rechaza|no autoriza|permite|valida|verifica|cierra|bloque|garantiza|"
    r"ningún|ninguna|al menos)", re.IGNORECASE
)
# Autenticación de estos PR MERGED y paths comprobada en GitHub al crear el corte.
VERIFIED = {
    "docs/orquestador.md:L121-U1":
        (1414, "67994aafbb5d", "scripts/coordinar_trabajo.py",
         "tests/test_coordinar_trabajo.py"),
    "docs/performance-remediation.md:L25-U3":
        (1548, "9c12107bd64e", "performance/remediation.py",
         "tests/test_performance_remediation.py"),
    "docs/liberacion-automatica-de-reservas.md:L181-U1":
        (1515, "1072b8b26582", "scripts/lease_auto_release_integration.py",
         "tests/test_lease_hypothetical_action_preview.py"),
    "docs/recovery-status.md:L13-U1":
        (1528, "465bc1e711ea", "recovery/status.py",
         "tests/test_recovery_status.py"),
}


def normative_units(path: Path) -> dict[str, str]:
    """Una unidad identificable por cláusula, no por título o README."""
    name = path.relative_to(ROOT).as_posix()
    output = {}
    fence = False
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"^\s*(\x60{3}|~{3})", line):
            fence = not fence
            continue
        if fence or re.match(r"^\s*(#|\||<!--|</|<details|<summary)", line):
            continue
        value = re.sub(r"^>\s*", "", line.strip())
        bullet = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.*)$", value)
        if bullet:
            value = bullet.group(1)
        if not value or re.match(r"^\[[^\]]+\]\(#[^)]+\)", value):
            continue
        unit = 0
        for piece in re.split(r";\s+|(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ])", value):
            piece = piece.strip()
            if len(piece) < 12 or (not bullet and not MODAL.search(piece)):
                continue
            unit += 1
            output[f"{name}:L{line_no}-U{unit}"] = piece
    return output


def parse_rows(doc: str) -> list[dict[str, str]]:
    if doc.count("## Filas de cobertura") != 1:
        raise ValueError("Sección de requisitos ausente o duplicada")
    part = doc.split("## Filas de cobertura", 1)[1]
    if "## Producción y mejoras pendientes" not in part:
        raise ValueError("La tabla no está delimitada")
    part = part.split("## Producción y mejoras pendientes", 1)[0]
    found, used = [], set()
    for line in part.splitlines():
        if not line.startswith("| ") or line.startswith(("| ID de requisito", "| ---")):
            continue
        values = [v.strip() for v in re.split(r"(?<!\\)\|", line)]
        if len(values) != 7 or values[0] or values[-1]:
            raise ValueError("Fila sin cinco columnas")
        key, desc, state, evidence, issue = values[1:-1]
        if not all((key, desc, state, evidence, issue)):
            raise ValueError("Celda vacía")
        if not (key.startswith(chr(96)) and key.endswith(chr(96))):
            raise ValueError("ID sin formato literal")
        key = key[1:-1]
        if key in used:
            raise ValueError("Requisito duplicado: " + key)
        used.add(key)
        if state not in STATES:
            raise ValueError("Estado inválido: " + state)
        found.append(dict(id=key, state=state, desc=desc,
                          evidence=evidence, issue=issue))
    if not found:
        raise ValueError("No hay requisitos")
    return found


def new_leaf_registry(doc: str) -> set[int]:
    part = doc.split("## Registro de hojas SIN_COBERTURA", 1)[1]
    part = part.split("## Resumen verificable", 1)[0]
    result = set()
    for line in part.splitlines():
        if line.startswith("| [#"):
            matches = ISSUE.findall(line)
            if len(matches) != 1:
                raise ValueError("Hoja no canónica")
            result.add(int(matches[0]))
    return result


def check_statuses(rows: list[dict[str, str]], registry: set[int]) -> None:
    for item in rows:
        state, issue, evidence, key = (
            item["state"], item["issue"], item["evidence"], item["id"]
        )
        if state == "SIN_COBERTURA":
            linked = [int(x) for x in ISSUE.findall(issue)]
            if len(linked) != 1 or linked[0] not in registry or linked[0] == 1550:
                raise ValueError("SIN_COBERTURA sin hoja real registrada")
        elif state == "EN_CURSO":
            if ("Épico" in issue or "EPIC" in issue or
                    not ISSUE.search(issue)):
                raise ValueError("Un épico no prueba que el trabajo sea ejecutable")
        elif state == "CUBIERTO":
            info = VERIFIED.get(key)
            if info is None:
                raise ValueError("Cobertura sin verificación externa")
            pr, merge_sha, code, test = info
            if (f"/pull/{pr}" not in evidence or merge_sha not in evidence or
                    code not in evidence or test not in evidence or
                    not (ROOT / code).is_file() or not (ROOT / test).is_file()):
                raise ValueError("CUBIERTO sin código, test o PR fusionado pertinente")


def inventory(doc: str) -> dict[str, int]:
    section = doc.split("## Inventario de fuentes", 1)[1]
    section = section.split("## Filas de cobertura", 1)[0]
    pattern = re.compile(
        r"^\| " + chr(96) + r"([^" + chr(96) + r"]+)" +
        chr(96) + r" \| (\d+) \|$"
    )
    result = {}
    for line in section.splitlines():
        match = pattern.fullmatch(line)
        if match:
            result[match.group(1)] = int(match.group(2))
    return result


class MatrizCoberturaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = MATRIX.read_text(encoding="utf-8")
        cls.rows = parse_rows(cls.doc)

    def test_cubre_todas_las_fuentes(self) -> None:
        expected, census = {}, {}
        docs = sorted(p for p in (ROOT / "docs").glob("*.md") if p != MATRIX)
        self.assertEqual(len(docs), 102)
        for path in [*docs, ROOT / "AGENTES.md"]:
            items = normative_units(path)
            census[path.relative_to(ROOT).as_posix()] = len(items)
            expected.update(items)
        self.assertEqual(census, inventory(self.doc))
        for epic, count in EPIC_AC.items():
            for n in range(1, count + 1):
                expected[f"ISSUE-{epic}:AC-{n:02d}"] = "Epic AC"
        actual = {row["id"] for row in self.rows}
        self.assertEqual(actual, set(expected))
        self.assertIn("AGENTES.md:L34-U2", expected)
        self.assertNotEqual(actual - {"AGENTES.md:L34-U2"}, set(expected))

    def test_sin_cobertura_tiene_issue(self) -> None:
        registry = new_leaf_registry(self.doc)
        check_statuses(self.rows, registry)
        actual = {r["id"] for r in self.rows if r["state"] == "CUBIERTO"}
        self.assertEqual(actual, set(VERIFIED))
        fake = [dict(self.rows[0], state="SIN_COBERTURA",
                     issue="[Épico #304](https://github.com/pl0n3r/Factory/issues/304)")]
        with self.assertRaises(ValueError):
            check_statuses(fake, registry)

    def test_formato_y_estados(self) -> None:
        self.assertGreater(len(self.rows), 100)
        first = next(line for line in self.doc.splitlines()
                     if line.startswith("| " + chr(96) + "docs/"))
        with self.assertRaises(ValueError):
            parse_rows("## Filas de cobertura\n" +
                       first.replace("NO_VERIFICABLE", "IMAGINARIO", 1) +
                       "\n## Producción y mejoras pendientes")
        with self.assertRaises(ValueError):
            parse_rows("## Filas de cobertura\n" + first + "\n" + first +
                       "\n## Producción y mejoras pendientes")

    def test_resumen_por_estado(self) -> None:
        counts = Counter(row["state"] for row in self.rows)
        part = self.doc.split("## Resumen verificable", 1)[1]
        for state in STATES:
            match = re.search(rf"^\| {state} \| (\d+) \|$", part, re.MULTILINE)
            self.assertIsNotNone(match)
            self.assertEqual(int(match.group(1)), counts[state])
        total = re.search(r"^\| TOTAL \| (\d+) \|$", part, re.MULTILINE)
        self.assertIsNotNone(total)
        self.assertEqual(int(total.group(1)), len(self.rows))
        pct = re.search(
            r"\*\*Porcentaje CUBIERTO:\*\* (\d+\.\d{2})% \((\d+)/(\d+)\)\.",
            part
        )
        self.assertIsNotNone(pct)
        self.assertEqual(int(pct.group(2)), counts["CUBIERTO"])
        self.assertEqual(int(pct.group(3)), len(self.rows))
        self.assertEqual(float(pct.group(1)),
                         round(100 * counts["CUBIERTO"] / len(self.rows), 2))
        new = re.search(r"\*\*Hojas nuevas creadas:\*\* (\d+)\.", part)
        self.assertIsNotNone(new)
        self.assertEqual(int(new.group(1)), len(new_leaf_registry(self.doc)))
        self.assertIn("main@" + BASE_SHA, self.doc)


if __name__ == "__main__":
    unittest.main()
