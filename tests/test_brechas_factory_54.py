#!/usr/bin/env python3
"""Factory #1672: sixteen scoped Quality DNA / Regression witnesses.

Only local repository validators and synthetic fixtures are used. External
GitHub provenance, live decisions and production status remain UNKNOWN.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import unittest

from intelligence.project_dna import (
    ProjectDnaError, _fingerprint_payload, attach_quality_contract,
    discover_project_dna, validate_project_dna,
)
from quality.contract import quality_contract_fingerprint
from quality.regression import QualityRegressionError, analyze_regression

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
DNA = "docs/quality-project-dna.md"
REG = "docs/quality-regression.md"
SCHEMA = "intelligence/project_dna.schema.json"
FILES = (MATRIX, DNA, REG, SCHEMA)
UNKNOWN, LOCAL = "UNKNOWN", "LOCAL_SYNTHETIC_ONLY"
CLOCK = "2026-09-28T23:00:00Z"
CLAUSES = {
    "docs/quality-project-dna.md:L19-U1": (DNA, "Si no se aporta explícitamente"),
    "docs/quality-project-dna.md:L20-U1": (DNA, "attach_quality_contract()"),
    "docs/quality-project-dna.md:L21-U1": (DNA, "validate_project_dna()"),
    "docs/quality-project-dna.md:L22-U1": (DNA, "namespace general"),
    "docs/quality-project-dna.md:L24-U1": (DNA, "solo declara qué contrato"),
    "docs/quality-project-dna.md:L9-U1": (DNA, "La extensión contiene únicamente:"),
    "docs/quality-regression.md:L10-U1": (REG, "after"),
    "docs/quality-regression.md:L11-U1": (REG, "regression_test_ref"),
    "docs/quality-regression.md:L12-U1": (REG, "causa raíz y prevención"),
    "docs/quality-regression.md:L18-U1": (REG, "Un fallo se considera reproducido"),
    "docs/quality-regression.md:L18-U2": (REG, "Cualquier muestra con"),
    "docs/quality-regression.md:L20-U1": (REG, "Un fix solo queda verificado"),
    "docs/quality-regression.md:L22-U1": (REG, "el fallo"),
    "docs/quality-regression.md:L23-U1": (REG, "after"),
    "docs/quality-regression.md:L24-U1": (REG, "regression_test_ref"),
    "docs/quality-regression.md:L25-U1": (REG, "evidencia temporal"),
}
UNITS = tuple(CLAUSES)

def sources():
    return {path: (ROOT / path).read_text(encoding="utf-8") for path in FILES}

def rows(raw):
    if type(raw) is not str or not raw.strip():
        raise ValueError("UNKNOWN: missing matrix")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| "):
            continue
        parts = tuple(x.strip() for x in line.strip("|").split(" | "))
        if len(parts) != 5:
            continue
        key = parts[0].strip(chr(96) + " ")
        if key not in CLAUSES:
            continue
        if (key in found or parts[0] != chr(96) + key + chr(96)
                or parts[2] != "NO_VERIFICABLE"
                or not parts[1] or "Contraste #1573" not in parts[3]
                or parts[4] != "—"):
            raise ValueError("UNKNOWN: duplicate/promoted " + key)
        found[key] = parts
    if set(found) != set(UNITS):
        raise ValueError("UNKNOWN: missing/ambiguous units")
    return found

def contract():
    return {
        "version": 1, "project": "factory",
        "surfaces": [{"id": "admin", "criticality": "high",
                      "required_gates": ["contract", "security", "unit"]}],
        "invariants": ["authorization", "no-secret-logging"],
        "compatibility": {"runtimes": ["python-3"], "browsers": [], "devices": []},
        "accessibility": {"target": "NOT_APPLICABLE"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {"required": True, "source_ref": "pl0n3r/Factory#306"},
        "evidence_freshness_seconds": 3600,
        "dimensions": {
            "performance": {"required": True, "source_ref": "pl0n3r/Factory#304"},
            "recovery": {"required": True, "source_ref": "pl0n3r/Factory#305"},
        },
    }

def observation():
    return {
        "version": 1, "regression_id": "quality-regression-001",
        "project": "pl0n3r/Factory", "surface": "quality-regression",
        "signature": "quality gate oscillates",
        "occurred_at": "2026-09-28T20:00:00Z",
        "source": "pl0n3r/Factory#346",
        "root_cause": "Unstable signal was trusted.",
        "prevention": "Require reproduced failure and clean after.",
        "before": {"runs": 3, "failures": 3, "evidence_ref": "ci://quality/before",
                   "observed_at": "2026-09-28T20:10:00Z"},
        "after": {"runs": 3, "failures": 0, "evidence_ref": "ci://quality/after",
                  "observed_at": "2026-09-28T20:20:00Z"},
        "regression_test_ref": "tests/test_quality_regression.py::QualityRegressionTests",
    }

def rejects(func, value):
    try:
        func(value)
    except (ProjectDnaError, QualityRegressionError):
        return True
    return False

def dna_evidence(schema):
    plain = discover_project_dna(paths=["package.json", ".github/workflows/ci.yml"])
    qc = contract()
    attached = attach_quality_contract(
        plain, source_ref="pl0n3r/Factory#343", contract=qc
    )
    ref = attached["extensions"]["quality_contract"]
    bad_dna = copy.deepcopy(plain)
    bad_dna["version"] = 2
    bad_qc = copy.deepcopy(qc)
    bad_qc["unexpected"] = True
    def invalid_attach(dna, value):
        return rejects(lambda x: attach_quality_contract(
            x, source_ref="pl0n3r/Factory#343", contract=value
        ), dna)
    shape_rejected = []
    for bad in ({"unexpected": True}, {"version": 2},
                {"source_ref": "invalid ref"}, {"fingerprint": "broken"}):
        candidate = copy.deepcopy(attached)
        candidate["extensions"]["quality_contract"].update(bad)
        candidate["fingerprint"] = _fingerprint_payload(candidate)
        shape_rejected.append(rejects(validate_project_dna, candidate))
    open_ext = copy.deepcopy(attached)
    open_ext["extensions"]["future_plugin"] = {"enabled": True}
    open_ext["fingerprint"] = _fingerprint_payload(open_ext)
    schema_ref = schema["$defs"]["qualityContractRef"]
    return {
        "docs/quality-project-dna.md:L19-U1":
            plain["extensions"] == {}
            and discover_project_dna(paths=["composer.json"])["extensions"] == {},
        "docs/quality-project-dna.md:L20-U1":
            invalid_attach(bad_dna, qc) and invalid_attach(plain, bad_qc)
            and attached["fingerprint"] != plain["fingerprint"]
            and attached["fingerprint"] == _fingerprint_payload(attached),
        "docs/quality-project-dna.md:L21-U1":
            all(shape_rejected) and schema_ref["additionalProperties"] is False
            and set(schema_ref["required"]) == {"version", "source_ref", "fingerprint"},
        "docs/quality-project-dna.md:L22-U1":
            validate_project_dna(open_ext) == open_ext
            and schema["properties"]["extensions"]["additionalProperties"] is True,
        "docs/quality-project-dna.md:L24-U1":
            set(ref) == {"version", "source_ref", "fingerprint"}
            and "required_gates" not in json.dumps(attached)
            and attached["stack"] == ["node"],
        "docs/quality-project-dna.md:L9-U1":
            ref == {"version": 1, "source_ref": "pl0n3r/Factory#343",
                    "fingerprint": quality_contract_fingerprint(qc)}
            and "surfaces" not in ref and "invariants" not in ref,
    }

def regression_evidence():
    original = observation()
    def evaluate(value):
        return analyze_regression(value, evaluated_at=CLOCK)
    def altered(before=None, after=None, ref="original"):
        result = copy.deepcopy(original)
        if before:
            result["before"].update(before)
        if after:
            result["after"].update(after)
        if ref != "original":
            result["regression_test_ref"] = ref
        return result
    good = evaluate(original)
    flaky_before = evaluate(altered(before={"failures": 1}))
    flaky_after = evaluate(altered(after={"failures": 1}))
    single = evaluate(altered(before={"runs": 1, "failures": 1}))
    no_ref = evaluate(altered(ref=None))
    dirty = evaluate(altered(after={"failures": 3}))
    bad = {}
    mutators = {
        "after_missing": lambda x: x["after"].pop("observed_at"),
        "after_extra": lambda x: x["after"].update({"extra": 1}),
        "cause_missing": lambda x: x.pop("root_cause"),
        "prevention_missing": lambda x: x.pop("prevention"),
        "future": lambda x: x["after"].update({"observed_at": "2999-01-01T00:00:00Z"}),
        "reversed": lambda x: x["after"].update({"observed_at": "2026-09-28T20:01:00Z"}),
        "invalid_ref": lambda x: x.update({"source": "not a github ref"}),
        "impossible": lambda x: x["before"].update({"failures": 4}),
        "extra": lambda x: x.update({"unrecognized": True}),
    }
    for name, mutator in mutators.items():
        candidate = copy.deepcopy(original)
        mutator(candidate)
        bad[name] = rejects(evaluate, candidate)
    verified = (good["classification"] == "VERIFIED"
                and good["reproduced"] is True
                and good["pass_evidence_eligible"] is True
                and good["guardrail_material"] is not None)
    negative = all(not x["pass_evidence_eligible"]
                   and x["guardrail_material"] is None
                   for x in (flaky_before, flaky_after, single, no_ref, dirty))
    return {
        "docs/quality-regression.md:L10-U1":
            bad["after_missing"] and bad["after_extra"]
            and "ci://quality/after" in good["provenance"],
        "docs/quality-regression.md:L11-U1":
            original["regression_test_ref"] in good["provenance"]
            and no_ref["guardrail_material"] is None,
        "docs/quality-regression.md:L12-U1":
            bad["cause_missing"] and bad["prevention_missing"]
            and good["guardrail_material"]["why"] == original["root_cause"]
            and good["guardrail_material"]["prevention"] == original["prevention"],
        "docs/quality-regression.md:L18-U1":
            good["reproduced"] is True and single["reproduced"] is False,
        "docs/quality-regression.md:L18-U2":
            flaky_before["classification"] == flaky_after["classification"] == "FLAKY"
            and flaky_before["flaky"] and flaky_after["flaky"] and negative,
        "docs/quality-regression.md:L20-U1": verified and negative,
        "docs/quality-regression.md:L22-U1":
            good["reproduced"] is True and single["pass_evidence_eligible"] is False,
        "docs/quality-regression.md:L23-U1":
            good["pass_evidence_eligible"] is True
            and dirty["pass_evidence_eligible"] is False,
        "docs/quality-regression.md:L24-U1":
            no_ref["pass_evidence_eligible"] is False
            and good["pass_evidence_eligible"] is True,
        "docs/quality-regression.md:L25-U1":
            verified and all(bad.values())
            and {"pl0n3r/Factory#346", "ci://quality/before",
                 "ci://quality/after"} <= set(good["provenance"]),
    }

def assess(data):
    if type(data) is not dict or set(data) != set(FILES):
        return {key: UNKNOWN for key in UNITS}
    if any(type(s) is not str or not s.strip() for s in data.values()):
        return {key: UNKNOWN for key in UNITS}
    try:
        present = rows(data[MATRIX])
        behaviors = {**dna_evidence(json.loads(data[SCHEMA])),
                     **regression_evidence()}
    except (ValueError, KeyError, TypeError, ProjectDnaError, QualityRegressionError):
        return {key: UNKNOWN for key in UNITS}
    return {key: LOCAL if (key in present and anchor in data[path]
                           and behaviors.get(key) is True) else UNKNOWN
            for key, (path, anchor) in CLAUSES.items()}

def operational_status(_key, _evidence=None):
    return UNKNOWN

class BrechasFactory54Tests(unittest.TestCase):
    def test_contrato_principal(self):
        data = sources()
        self.assertEqual(set(UNITS), set(rows(data[MATRIX])))
        result = assess(data)
        self.assertEqual(set(UNITS), set(result))
        for key in UNITS:
            with self.subTest(unit=key):
                self.assertEqual("NO_VERIFICABLE", rows(data[MATRIX])[key][2])
                self.assertEqual(LOCAL, result[key])

    def test_falla_cerrado(self):
        data = sources()
        for key, (source, anchor) in CLAUSES.items():
            with self.subTest(unit=key):
                row = next(line for line in data[MATRIX].splitlines()
                           if line.startswith("| " + chr(96) + key + chr(96) + " |"))
                for corruption in (
                    data[MATRIX].replace(row, "", 1),
                    data[MATRIX] + "\n" + row,
                    data[MATRIX].replace(row, row.replace(
                        "NO_VERIFICABLE", "CUBIERTO", 1), 1),
                ):
                    self.assertEqual(UNKNOWN, assess({**data, MATRIX: corruption})[key])
                self.assertEqual(UNKNOWN, assess({
                    **data, source: data[source].replace(anchor, "")
                })[key])
        for invalid in (None, {}, {**data, SCHEMA: "{}"},
                        {**data, MATRIX: ""}):
            self.assertEqual({UNKNOWN}, set(assess(invalid).values()))
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            rows("")

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.Import) for a in node.names}
        names |= {node.module.split(".")[0] for node in ast.walk(tree)
                  if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(names & {"requests", "urllib", "httpx", "socket",
                                  "subprocess", "selenium", "playwright", "pymysql"})
        self.assertEqual(set(FILES), set(sources()))
        self.assertEqual("pl0n3r/Factory", observation()["project"])
        self.assertNotIn("api_key", json.dumps(observation()))
        self.assertEqual(UNKNOWN, operational_status("ci", {"success": True}))

    def test_estados_unknown_explicitos(self):
        self.assertEqual({LOCAL}, set(assess(sources()).values()))
        for key in UNITS:
            for claim in (None, {}, {"ci": "success"}, {"owner": "approved"},
                          {"production": "PASS"}, {"github": "merged"}):
                self.assertEqual(UNKNOWN, operational_status(key, claim))
        self.assertEqual({UNKNOWN}, set(assess({
            **sources(), REG: ""
        }).values()))

if __name__ == "__main__":
    unittest.main()
