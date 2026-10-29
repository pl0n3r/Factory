#!/usr/bin/env python3
"""Factory #1629: evidencia offline de 16 brechas sin declarar cumplimiento real."""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
LOCAL = "DOCUMENTED_GAP"
COORD = "docs/coordinacion-pr-validation.md"
COST = "docs/costos-presupuestos.md"
LEGAL = "docs/cumplimiento-datos-licencias.md"
MATRIX = "docs/matriz-cobertura.md"
CONTRAST = "docs/contraste-factory_resto_1.md"
COORD_CODE = "scripts/coordinar_trabajo.py"
COORD_TEST = "tests/test_coordinacion_reusable_contract.py"
COST_CODE = "metricas/costos.py"
COST_TEST = "metricas/test_costos.py"
LEGAL_CODE = "seguridad/cumplimiento.py"
LEGAL_TEST = "seguridad/test_cumplimiento.py"

# (ruta, ancla, frase de la clausula, modulo, prueba, metodo)
CASES = {
    COORD + ":L5-U1": (COORD, 5, "La coordinación valida cada PR mientras está abierto", COORD_CODE, COORD_TEST, "test_merged_pr_validation_is_neutral"),
    COORD + ":L52-U1": (COORD, 52, "La reversión es un revert", COORD_CODE, COORD_TEST, "test_merged_pr_validation_is_neutral"),
    COORD + ":L8-U1": (COORD, 8, "Closes #N", COORD_CODE, COORD_TEST, "test_merged_pr_validation_is_neutral"),
    COORD + ":L9-U1": (COORD, 9, "volver a exigir entonces que el Issue siga abierto", COORD_CODE, COORD_TEST, "test_merged_pr_validation_is_neutral"),
    COST + ":L13-U1": (COST, 13, "Mientras tokens, minutos de CI", COST_CODE, COST_TEST, "test_declared_usage_never_reports_verified_ok"),
    COST + ":L15-U1": (COST, 15, "ok", COST_CODE, COST_TEST, "test_declared_usage_never_reports_verified_ok"),
    COST + ":L15-U2": (COST, 15, "telemetría actual no se emite", COST_CODE, COST_TEST, "test_declared_usage_never_reports_verified_ok"),
    COST + ":L16-U1": (COST, 16, "warning", COST_CODE, COST_TEST, "test_near_limit_warns_and_over_limit_soft_blocks"),
    COST + ":L17-U1": (COST, 17, "soft-block", COST_CODE, COST_TEST, "test_near_limit_warns_and_over_limit_soft_blocks"),
    COST + ":L19-U1": (COST, 19, "marker malformado falla cerrado", COST_CODE, COST_TEST, "test_invalid_usage_fails_closed"),
    COST + ":L19-U2": (COST, 19, "unverified:", COST_CODE, COST_TEST, "test_declared_usage_never_reports_verified_ok"),
    COST + ":L19-U3": (COST, 19, "no se confunde una estimación con costo observado", COST_CODE, COST_TEST, "test_declared_usage_never_reports_verified_ok"),
    COST + ":L27-U1": (COST, 27, "run_id", COST_CODE, COST_TEST, "test_ci_trend_rejects_duplicate_run_ids"),
    COST + ":L29-U1": (COST, 29, "F1F no acredita ningún informe mensual", COST_CODE, COST_TEST, "test_ci_trend_rejects_duplicate_run_ids"),
    COST + ":L5-U1": (COST, 5, "El agente que abre un PR declara únicamente métricas", COST_CODE, COST_TEST, "test_declared_usage_never_reports_verified_ok"),
    LEGAL + ":L15-U1": (LEGAL, 15, "exige siete referencias", LEGAL_CODE, LEGAL_TEST, "test_missing_legal_review_fails"),
}
FILES = {MATRIX, CONTRAST}
for info in CASES.values():
    FILES.update((info[0], info[3], info[4]))
REQUIRED = frozenset(("privacy_policy", "terms", "processing_register", "rights_channel",
                      "retention_schedule", "vendor_review", "legal_review"))

def rows_from_matrix(source: str) -> dict:
    rows = {}
    for line in source.splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(x.strip().strip(chr(96)) for x in line.strip("|").split("|"))
        if not cells or cells[0] not in CASES:
            continue
        if len(cells) != 5 or cells[0] in rows:
            raise ValueError("UNKNOWN: filas duplicadas o truncadas")
        rows[cells[0]] = cells
    if set(rows) != set(CASES):
        raise ValueError("UNKNOWN: filas incompletas")
    return rows

def verifying_method(code: str, name: str) -> bool:
    hit = re.search(r"\bdef\s+" + re.escape(name) + r"\s*\(", code)
    if not hit:
        return False
    end = re.search(r"(?m)^\s+def\s+test_", code[hit.end():])
    excerpt = code[hit.end():hit.end() + end.start()] if end else code[hit.end():]
    return "self.assert" in excerpt or "self.fail(" in excerpt

def inspect(identifier: str, rows: dict, sources: dict) -> dict:
    status = {"contract": UNKNOWN, "ci": UNKNOWN, "production": UNKNOWN,
              "legal": UNKNOWN}
    if identifier not in CASES:
        return status
    row = rows.get(identifier)
    if not isinstance(row, tuple) or len(row) != 5 or row[2] != "NO_VERIFICABLE":
        return status
    if not ("Contraste #1569" in row[3] or
            "No se confirmó test + PR fusionado" in row[3]):
        return status
    doc, line, phrase, module, test, method = CASES[identifier]
    lines = sources.get(doc, "").splitlines()
    vicinity = "\n".join(lines[max(line - 2, 0):line + 1])
    if not phrase.lower() in vicinity.lower():
        return status
    if not verifying_method(sources.get(test, ""), method):
        return status
    source = sources.get(module, "")
    if doc == COORD and "def validate_pull(" not in source:
        return status
    if doc == COST and "def evaluate_pr(" not in source:
        return status
    if doc == LEGAL and "def validate_privacy(" not in source:
        return status
    if doc != LEGAL:
        phrase = "| " + chr(96) + identifier + chr(96) + " |"
        if sources.get(CONTRAST, "").count(phrase) != 1:
            return status
    status["contract"] = LOCAL
    return status

def pr_validation(pr: object, issue_open: object, lease: object) -> str:
    if pr == "merged":
        return "NEUTRAL_POST_MERGE"
    if pr == "open" and issue_open is True and lease is True:
        return "OPEN_VALID"
    return UNKNOWN

def cost_decision(measures: object, run_ids: object = ()) -> str:
    if (type(measures) is not dict or not measures or type(run_ids) is not tuple
            or any(type(x) is not int for x in run_ids)
            or len(run_ids) != len(set(run_ids))):
        return UNKNOWN
    ratios = []
    modes = []
    for item in measures.values():
        if (type(item) is not tuple or len(item) != 2 or
                type(item[0]) not in (int, float) or
                item[0] < 0 or item[0] > 10000 or
                item[1] not in ("observed", "declared")):
            return UNKNOWN
        ratios.append(item[0])
        modes.append(item[1])
    if any(n > 1 for n in ratios):
        return "soft-block"
    return "ok" if all(m == "observed" for m in modes) and max(ratios) < .8 else "warning"

def legal_references(refs: object) -> str:
    if type(refs) is not dict or set(refs) != REQUIRED:
        return UNKNOWN
    if not all(type(ref) is str and
               re.fullmatch(r"ref:[a-z][a-z0-9_]{1,40}", ref)
               for ref in refs.values()):
        return UNKNOWN
    return "DOCUMENTED_NOT_LEGALLY_APPROVED"

class BrechasFactory11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = {p: (ROOT / p).read_text(encoding="utf-8") for p in FILES}
        cls.rows = rows_from_matrix(cls.sources[MATRIX])

    def test_contrato_principal(self) -> None:
        self.assertEqual(len(CASES), 16)
        for identifier in CASES:
            with self.subTest(identifier=identifier):
                self.assertEqual(inspect(identifier, self.rows, self.sources)["contract"], LOCAL)
        self.assertEqual(pr_validation("merged", False, False), "NEUTRAL_POST_MERGE")
        self.assertEqual(pr_validation("open", True, True), "OPEN_VALID")
        self.assertEqual(cost_decision({"ci": (.8, "observed")}), "warning")
        self.assertEqual(cost_decision({"ci": (1.01, "observed")}), "soft-block")
        self.assertEqual(cost_decision({"ci": (.3, "declared")}), "warning")
        refs = {key: "ref:synthetic_" + str(i) for i, key in enumerate(sorted(REQUIRED))}
        self.assertEqual(legal_references(refs), "DOCUMENTED_NOT_LEGALLY_APPROVED")

    def test_falla_cerrado(self) -> None:
        for identifier in CASES:
            with self.subTest(identifier=identifier):
                missing = dict(self.rows)
                del missing[identifier]
                self.assertEqual(inspect(identifier, missing, self.sources)["contract"], UNKNOWN)
                changed = dict(self.rows)
                changed[identifier] = (identifier, "sin evidencia", "CUBIERTO", "", "")
                self.assertEqual(inspect(identifier, changed, self.sources)["contract"], UNKNOWN)
                path = CASES[identifier][0]
                self.assertEqual(inspect(identifier, self.rows, {**self.sources, path: ""})["contract"], UNKNOWN)
                test = CASES[identifier][4]
                self.assertEqual(inspect(identifier, self.rows, {**self.sources, test: ""})["contract"], UNKNOWN)
        first = "| " + chr(96) + next(iter(CASES)) + chr(96) + " |"
        row = next(line for line in self.sources[MATRIX].splitlines() if line.startswith(first))
        with self.assertRaises(ValueError):
            rows_from_matrix(self.sources[MATRIX] + "\n" + row)
        self.assertEqual(pr_validation("open", False, True), UNKNOWN)
        self.assertEqual(pr_validation("closed", False, True), UNKNOWN)
        self.assertEqual(cost_decision({}, ()), UNKNOWN)
        self.assertEqual(cost_decision({"ci": (.2, "declared")}, (5, 5)), UNKNOWN)
        self.assertEqual(legal_references({"terms": "ref:demo"}), UNKNOWN)

    def test_sin_datos_reales(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^(?:import|from)\s+(?:requests|socket|urllib|subprocess|httpx)\b")
        self.assertNotRegex(source, r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----")
        self.assertNotRegex(source, r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
        self.assertEqual(set(self.sources), FILES)
        for path in FILES:
            self.assertFalse(Path(path).is_absolute())

    def test_estados_unknown_explicitos(self) -> None:
        for identifier in CASES:
            with self.subTest(identifier=identifier):
                result = inspect(identifier, self.rows, self.sources)
                self.assertEqual((result["ci"], result["production"], result["legal"]),
                                 (UNKNOWN, UNKNOWN, UNKNOWN))
                self.assertEqual(self.rows[identifier][2], "NO_VERIFICABLE")
        self.assertEqual(legal_references(None), UNKNOWN)
        self.assertEqual(pr_validation("unknown", False, True), UNKNOWN)

if __name__ == "__main__":
    unittest.main()
