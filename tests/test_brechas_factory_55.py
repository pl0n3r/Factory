"""Factory #1673: 16 regression/Sonar Watch units; offline != live."""
from __future__ import annotations
from copy import deepcopy
import ast
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from quality.regression import (
    QualityRegressionError, analyze_regression, compile_regression_guardrail_candidates,
)
from lecciones.memoria import validate_lesson

ROOT = Path(__file__).resolve().parents[1]
MATRIX, REG, WATCH = ("docs/matriz-cobertura.md",
                      "docs/quality-regression.md", "docs/quality-sonar-watch.md")
REG_CODE, SONAR_CODE = "quality/regression.py", "quality/sonar.py"
SONAR_SCRIPT, CONFIG = "scripts/sonar-watch.py", "quality/sonar-watch-config.json"
FILES = (MATRIX, REG, WATCH, REG_CODE, SONAR_CODE, SONAR_SCRIPT, CONFIG)
NOW, UNKNOWN, LOCAL = "2026-09-28T23:00:00Z", "UNKNOWN", "CONTRATO_LOCAL"
BT = chr(96)
IDS = (
    "docs/quality-regression.md:L27-U1", "docs/quality-regression.md:L27-U2",
    "docs/quality-regression.md:L31-U1", "docs/quality-regression.md:L31-U2",
    "docs/quality-regression.md:L33-U1", "docs/quality-regression.md:L37-U1",
    "docs/quality-regression.md:L38-U1", "docs/quality-regression.md:L39-U1",
    "docs/quality-regression.md:L40-U1", "docs/quality-regression.md:L41-U1",
    "docs/quality-regression.md:L9-U1",
    "docs/quality-sonar-watch.md:L22-U1", "docs/quality-sonar-watch.md:L24-U1",
    "docs/quality-sonar-watch.md:L3-U1", "docs/quality-sonar-watch.md:L3-U2",
    "docs/quality-sonar-watch.md:L3-U3",
)
EXTERNAL = {
    "docs/quality-regression.md:L37-U1", "docs/quality-regression.md:L38-U1",
    "docs/quality-regression.md:L39-U1", "docs/quality-sonar-watch.md:L24-U1",
    "docs/quality-sonar-watch.md:L3-U2",
}
ANCHORS = {
    "L27-U1": "Solo en ese caso se genera una lesson",
    "L27-U2": "Una observación no verificada conserva",
    "L31-U1": "Dos o más lessons verificadas",
    "L31-U2": "Este módulo solo expone el candidato",
    "L33-U1": "No se crea un Immune/Guardrail Engine paralelo",
    "L37-U1": "Quality Health y proyección",
    "L38-U1": "Clasificación/corrección operativa",
    "L39-U1": "El E2E transversal",
    "L40-U1": "Este módulo no modifica Performance ni Recovery",
    "L41-U1": "No existe autoridad para ejecutar fixes",
    "L9-U1": "before",
    "L22-U1": "no requieren reinterpretar observación runtime",
    "L24-U1": "Migrar",
    "L3-U1": "Sonar Watch no se ejecuta automáticamente",
    "L3-U2": "no se refrescan automáticamente",
    "L3-U3": "El motor offline",
}

def sources():
    return {p: (ROOT / p).read_text(encoding="utf-8") for p in FILES}

def rows(data):
    if type(data) is not dict or set(data) != set(FILES) or any(
        type(data[p]) is not str or not data[p] for p in FILES
    ):
        raise ValueError("UNKNOWN: incomplete sources")
    result = {}
    for line in data[MATRIX].splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(x.strip() for x in re.split(r"(?<!\\)\|", line)[1:-1])
        if not cells:
            continue
        unit = cells[0].strip(BT)
        if unit not in IDS:
            continue
        if (unit in result or len(cells) != 5 or cells[0] != BT + unit + BT
                or not cells[1] or cells[2] != "NO_VERIFICABLE"
                or "Contraste #1573" not in cells[3]
                or "faltan aserción exacta y PR MERGED" not in cells[3]
                or cells[4] != "—"):
            raise ValueError("UNKNOWN: invalid or duplicate row " + unit)
        result[unit] = cells
    if set(result) != set(IDS):
        raise ValueError("UNKNOWN: missing rows")
    return result

def source_clause(unit, data):
    if type(unit) is not str or unit not in IDS or type(data) is not dict:
        return False
    match = re.fullmatch(
        r"(docs/quality-(?:regression|sonar-watch)\.md):L(\d+)-U\d+", unit)
    if not match or type(data.get(match[1])) is not str:
        return False
    n = int(match[2])
    lines = data[match[1]].splitlines()
    return bool(0 < n <= len(lines) and ANCHORS[unit.rsplit(":", 1)[1]].casefold()
                in lines[n - 1].casefold())

def observation(*, source="pl0n3r/Factory#346", ident="regression-qa-001",
                before=3, after=0, test="tests/test_quality_regression.py"):
    return {
        "version": 1, "regression_id": ident, "project": "pl0n3r/Factory",
        "surface": "quality-regression", "signature": "repeated CI drift",
        "occurred_at": "2026-09-28T20:00:00Z", "source": source,
        "root_cause": "Repeated drift", "prevention": "Deterministic guard",
        "before": {"runs": 3, "failures": before, "evidence_ref": "ci://qa/before",
                   "observed_at": "2026-09-28T20:10:00Z"},
        "after": {"runs": 3, "failures": after, "evidence_ref": "ci://qa/after",
                  "observed_at": "2026-09-28T20:20:00Z"},
        "regression_test_ref": test,
    }

def rejects(item):
    try:
        analyze_regression(item, evaluated_at="2026-09-28T23:00:00Z")
    except QualityRegressionError:
        return True
    return False

def watch_module():
    spec = importlib.util.spec_from_file_location(
        "factory_1673_watch", ROOT / SONAR_SCRIPT)
    if not spec or not spec.loader:
        raise ValueError("UNKNOWN: missing source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def evidence(data):
    base = observation()
    copy = deepcopy(base)
    good = analyze_regression(base, evaluated_at=NOW)
    flaky = analyze_regression(observation(before=1), evaluated_at=NOW)
    dirty = analyze_regression(observation(after=2), evaluated_at=NOW)
    without_test = analyze_regression(observation(test=None), evaluated_at=NOW)
    second = observation(source="pl0n3r/Factory#349", ident="regression-qa-002")
    candidate = compile_regression_guardrail_candidates(
        [base, second], evaluated_at=NOW)
    bad = observation()
    bad["before"]["runs"] = 0
    future = observation()
    future["after"]["observed_at"] = "2999-01-01T00:00:00Z"
    secret = observation()
    secret["root_cause"] = "token=never-echo"
    config = json.loads(data[CONFIG])
    watch = watch_module()
    with patch.object(watch, "urlopen", side_effect=AssertionError("network")) as url:
        method = watch.SonarApi.analysis_method_from_settings({
            "settings": [{"key": "sonar.autoscan.enabled", "value": "false"}]})
        url.assert_not_called()
    policies = {x["project"]: x for x in config["projects"]}
    tree = ast.parse(data[REG_CODE])
    imports = {x.module for x in ast.walk(tree)
               if isinstance(x, ast.ImportFrom)}
    pure = not any(x in imports for x in ("subprocess", "urllib.request", "requests"))
    local = {
        "L27-U1": good["classification"] == "VERIFIED" and
                  validate_lesson(good["guardrail_material"], "qa")["source"] == base["source"],
        "L27-U2": flaky["classification"] == "FLAKY" and all(
            x["guardrail_material"] is None and not x["pass_evidence_eligible"]
            for x in (flaky, dirty, without_test)),
        "L31-U1": len(candidate) == 1 and candidate[0]["occurrences"] == 2 and
                  candidate[0]["sources"] == ["pl0n3r/Factory#346", "pl0n3r/Factory#349"],
        "L31-U2": len(candidate) == 1 and
                  candidate[0]["candidate"]["changes"][0]["value"]["status"] == "candidate"
                  and copy == base,
        "L33-U1": pure and "create_issue" not in data[REG_CODE],
        "L37-U1": False,
        "L38-U1": False,
        "L39-U1": False,
        "L40-U1": pure and "performance" not in imports and "recovery" not in imports,
        "L41-U1": pure and "promote_policy" not in data[REG_CODE] and
                  "execute_actions" not in good,
        "L9-U1": set(base["before"]) ==
                  {"runs", "failures", "evidence_ref", "observed_at"} and
                  {"ci://qa/before", "ci://qa/after"} <= set(good["provenance"]) and
                  rejects(bad) and rejects(future) and rejects(secret),
        "L22-U1": config["version"] == 1 and method == "ci" and
                  policies["factory"]["contract"]["sonar"]["analysis_method"] == "ci",
        "L24-U1": False,
        "L3-U1": not (ROOT / ".github/workflows/sonar-watch.yml").exists(),
        "L3-U2": False,
        "L3-U3": not (ROOT / ".github/workflows/sonar-watch.yml").exists() and
                  "def run_live" in data[SONAR_SCRIPT] and
                  "normalize_sonar_snapshot" in data[SONAR_CODE] and method == "ci",
    }
    return {unit: bool(local[unit.rsplit(":", 1)[1]]) for unit in IDS}

def verdict(unit, data, proof):
    if type(unit) is not str or unit not in IDS or type(proof) is not dict:
        return UNKNOWN
    try:
        if not source_clause(unit, data) or rows(data)[unit][2] != "NO_VERIFICABLE":
            return UNKNOWN
    except (ValueError, TypeError, KeyError):
        return UNKNOWN
    return LOCAL if proof.get(unit) is True else UNKNOWN

def operational_status(_unit, _claim=None):
    return UNKNOWN

class BrechasFactory55Tests(unittest.TestCase):
    def test_contrato_principal(self):
        data = sources()
        proof = evidence(data)
        self.assertEqual(set(rows(data)), set(IDS))
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertTrue(source_clause(unit, data))
                self.assertEqual(verdict(unit, data, proof),
                                 UNKNOWN if unit in EXTERNAL else LOCAL)

    def test_falla_cerrado(self):
        data = sources()
        proof = evidence(data)
        for unit in IDS:
            with self.subTest(unit=unit):
                line = next(x for x in data[MATRIX].splitlines()
                            if x.startswith("| " + BT + unit + BT + " |"))
                for changed in (
                    data[MATRIX].replace(line, "", 1),
                    data[MATRIX] + "\n" + line,
                    data[MATRIX].replace(line, line.replace(
                        "NO_VERIFICABLE", "CUBIERTO", 1), 1),
                ):
                    self.assertEqual(verdict(unit, {**data, MATRIX: changed}, proof),
                                     UNKNOWN)
                path = unit.split(":")[0]
                n = int(unit.split(":L")[1].split("-")[0])
                lines = data[path].splitlines()
                lines[n - 1] = "untrusted"
                self.assertEqual(verdict(unit, {**data, path: "\n".join(lines)}, proof),
                                 UNKNOWN)
                self.assertEqual(verdict(unit, data, {}), UNKNOWN)
        self.assertEqual(verdict("invalid", data, proof), UNKNOWN)
        self.assertEqual(verdict(IDS[0], None, proof), UNKNOWN)
        for invalid in (None, {}, {**observation(), "extra": True}):
            self.assertTrue(rejects(invalid))

    def test_sin_datos_reales(self):
        data = sources()
        self.assertEqual(set(data), set(FILES))
        for name in FILES:
            self.assertFalse(Path(name).is_absolute())
            self.assertNotIn("..", Path(name).parts)
        self.assertNotIn("token=", json.dumps(observation()))
        self.assertEqual(operational_status(IDS[0], {"authorization": True}), UNKNOWN)

    def test_estados_unknown_explicitos(self):
        data = sources()
        proof = evidence(data)
        for unit in IDS:
            with self.subTest(unit=unit):
                for claim in (None, {}, {"ci": "success", "sha": "a" * 40},
                              {"owner": True}, {"live": "GREEN"}):
                    self.assertEqual(operational_status(unit, claim), UNKNOWN)
                self.assertEqual(verdict(unit, data, proof),
                                 UNKNOWN if unit in EXTERNAL else LOCAL)

if __name__ == "__main__":
    unittest.main()
