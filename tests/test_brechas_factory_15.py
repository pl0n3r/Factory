#!/usr/bin/env python3
"""Factory #1633: 16 synthetic DoD Compiler and agent-evaluation evidence gaps.

Local contract evidence does not prove an actual scan, release, live metrics,
production readiness or an independently reconciled coverage matrix.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from intelligence.dod_compiler import (
    FACTORY_INVARIANTS, SAFE_FALLBACK, DodCompilerError, compile_done_contract,
)
from intelligence.project_dna import (
    ProjectDnaError, discover_project_dna, validate_project_dna,
)
from metricas.evaluar_agentes import (
    ValidationError, aggregate, load_records, validate_record,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
DOD = "docs/dod-compiler.md"
EVAL = "docs/evaluacion-agentes.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
CLAUSES = {
    "docs/dod-compiler.md:L38-U1": (DOD, "seguridad: scan + casos negativos;"),
    "docs/dod-compiler.md:L39-U1": (DOD, "riesgo medio/alto: plan de rollback"),
    "docs/dod-compiler.md:L39-U2": (DOD, "riesgo alto añade smoke exact-SHA."),
    "docs/dod-compiler.md:L48-U1": (DOD, "`safe-fallback` y exige, además de las invariantes:"),
    "docs/dod-compiler.md:L5-U1": (DOD, "solo produce requisitos verificables por máquina a partir de la tarea"),
    "docs/dod-compiler.md:L50-U1": (DOD, "suite completa;"),
    "docs/dod-compiler.md:L51-U1": (DOD, "análisis estático;"),
    "docs/dod-compiler.md:L52-U1": (DOD, "security scan;"),
    "docs/dod-compiler.md:L53-U1": (DOD, "rollback plan;"),
    "docs/dod-compiler.md:L54-U1": (DOD, "completar contexto antes de promoción."),
    "docs/dod-compiler.md:L56-U1": (DOD, "Así, ignorancia nunca equivale a menos evidencia."),
    "docs/dod-compiler.md:L6-U1": (DOD, "Project DNA validado."),
    "docs/evaluacion-agentes.md:L13-U1": (EVAL, "El validador rechaza campos desconocidos, duplicados por `task_id`"),
    "docs/evaluacion-agentes.md:L17-U1": (EVAL, "Una configuración solo entra al ranking al alcanzar la muestra mínima."),
    "docs/evaluacion-agentes.md:L19-U1": (EVAL, "mayor tasa de éxito;"),
    "docs/evaluacion-agentes.md:L20-U1": (EVAL, "menos incidentes posteriores por tarea;"),
}


def read_sources() -> dict[str, str]:
    return {path: (ROOT / path).read_text(encoding="utf-8") for path in (MATRIX, DOD, EVAL)}


def matrix_rows(raw: object) -> dict[str, str]:
    """Reject missing, duplicated, modified and artificially promoted rows."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matrix unavailable")
    result = {}
    for key, (_, phrase) in CLAUSES.items():
        matches = [s for s in raw.splitlines() if s.startswith("| `" + key + "` |")]
        if len(matches) != 1:
            raise ValueError("UNKNOWN: duplicate/missing " + key)
        fields = [x.strip() for x in matches[0].strip("|").split("|")]
        if (len(fields) != 5 or fields[0] != "`" + key + "`"
                or phrase.casefold() not in fields[1].casefold()
                or fields[2] != "NO_VERIFICABLE"
                or "No se confirmó test + PR fusionado" not in fields[3]
                or not fields[4]):
            raise ValueError("UNKNOWN: invalid evidence " + key)
        result[key] = fields[1]
    if set(result) != set(CLAUSES):
        raise ValueError("UNKNOWN: incomplete matrix")
    return result


def source_matches(key: str, docs: object) -> bool:
    if key not in CLAUSES or type(docs) is not dict:
        return False
    path, phrase = CLAUSES[key]
    source = docs.get(path)
    if type(source) is not str:
        return False
    lines = source.splitlines()
    try:
        number = int(key.split(":L", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return False
    return 1 <= number <= len(lines) and phrase.casefold() in lines[number - 1].casefold()


def dna() -> dict[str, object]:
    return discover_project_dna(
        paths=["package.json", ".github/workflows/ci.yml", "vercel.json",
               "database/schema.sql", ".sentryclirc"],
        manifests={"package.json": {"dependencies": {
            "fastify": "^5", "@sentry/node": "^9",
        }}},
        capabilities=["api", "web"],
    )


def task(kind: str, risk: str, surfaces: list[str] | None = None) -> dict[str, object]:
    return {
        "id": "factory#1633", "title": "synthetic proof",
        "change_type": kind, "surfaces": ["api"] if surfaces is None else surfaces,
        "risk": risk,
    }


def record(n: int, model: str = "alpha", **changes: object) -> dict[str, object]:
    fixture: dict[str, object] = {
        "task_id": f"factory#{n}", "task_type": "backend", "agent": "synthetic",
        "model": model, "prompt_id": "fixture", "roles": ["qa"],
        "success": True, "merged_first_try": True, "commits": 1,
        "review_rounds": 1, "rework_commits": 0, "incidents_after": 0,
        "completed_at": "2026-09-24T12:00:00Z",
        "tokens_input": 50, "tokens_output": 20,
    }
    fixture.update(changes)
    return fixture


def proof() -> dict[str, bool]:
    """Execute real pure functions and negative cases; never simulate a passing CI."""
    project = dna()
    valid_dna = validate_project_dna(project)
    invalid_dna = deepcopy(project)
    invalid_dna["fingerprint"] = "0" * 64
    try:
        validate_project_dna(invalid_dna)
    except ProjectDnaError:
        rejects_tampered_dna = True
    else:
        rejects_tampered_dna = False

    security = compile_done_contract(project_dna=project, task=task("security", "low"))
    medium = compile_done_contract(project_dna=project, task=task("docs", "medium"))
    high = compile_done_contract(project_dna=project, task=task("security", "high"))
    unknown = compile_done_contract(
        project_dna=discover_project_dna(paths=["README.md"]),
        task=task("unknown", "unknown", []),
    )
    unknown_dna = compile_done_contract(
        project_dna=discover_project_dna(paths=["README.md"]), task=task("docs", "low"),
    )
    inv = [dict(x) for x in FACTORY_INVARIANTS]
    fallback = [dict(x) for x in SAFE_FALLBACK]

    def contains(contract: dict, kind: str, target: str) -> bool:
        return {"kind": kind, "target": target} in contract["evidence"]

    def machine(contract: dict) -> bool:
        return all(
            set(item) == {"kind", "target"} and item["kind"] in ("check", "test")
            and ":" in item["target"] and not item["target"].endswith(":")
            for item in contract["evidence"]
        )

    try:
        compile_done_contract(
            project_dna=project,
            task={**task("docs", "low"), "unknown": "synthetic"},
        )
    except DodCompilerError:
        rejects_unknown_task = True
    else:
        rejects_unknown_task = False

    def rejects_metric(**changes: object) -> bool:
        try:
            validate_record(record(900, **changes), "synthetic")
        except ValidationError:
            return True
        return False

    with TemporaryDirectory(prefix="factory-1633-") as directory:
        path = Path(directory) / "evidence.jsonl"
        path.write_text("\n".join(json.dumps(record(1)) for _ in range(2)),
                        encoding="utf-8")
        try:
            load_records([path])
        except ValidationError:
            duplicate_rejected = True
        else:
            duplicate_rejected = False

    sparse = aggregate([validate_record(record(1), "synthetic")], min_samples=2)
    sparse_backend = sparse["task_types"]["backend"]
    successes = [
        validate_record(record(1, model="alpha", success=False), "synthetic"),
        validate_record(record(2, model="alpha"), "synthetic"),
        validate_record(record(3, model="beta"), "synthetic"),
        validate_record(record(4, model="beta"), "synthetic"),
    ]
    success_ranks = aggregate(successes, min_samples=2)["task_types"]["backend"]
    incident_cases = [
        validate_record(record(5, model="alpha"), "synthetic"),
        validate_record(record(6, model="alpha"), "synthetic"),
        validate_record(record(7, model="beta", incidents_after=1), "synthetic"),
        validate_record(record(8, model="beta", incidents_after=1), "synthetic"),
    ]
    incident_ranks = aggregate(incident_cases, min_samples=2)["task_types"]["backend"]
    return {
        "docs/dod-compiler.md:L38-U1": (
            contains(security, "check", "security:scan")
            and contains(security, "test", "security:negative-cases")),
        "docs/dod-compiler.md:L39-U1": (
            contains(medium, "check", "rollback:plan")
            and contains(high, "check", "rollback:plan")),
        "docs/dod-compiler.md:L39-U2": contains(high, "check", "smoke:exact-sha"),
        "docs/dod-compiler.md:L48-U1": (
            unknown["profile"] == "safe-fallback"
            and not unknown["context_complete"]
            and unknown_dna["profile"] == "safe-fallback"),
        "docs/dod-compiler.md:L5-U1": (
            all(machine(c) for c in (security, medium, high, unknown))
            and rejects_unknown_task and len(security["fingerprint"]) == 64),
        "docs/dod-compiler.md:L50-U1": contains(unknown, "test", "tests:full-suite"),
        "docs/dod-compiler.md:L51-U1": contains(unknown, "check", "static:analysis"),
        "docs/dod-compiler.md:L52-U1": contains(unknown, "check", "security:scan"),
        "docs/dod-compiler.md:L53-U1": contains(unknown, "check", "rollback:plan"),
        "docs/dod-compiler.md:L54-U1": contains(unknown, "check", "context:complete-before-promotion"),
        "docs/dod-compiler.md:L56-U1": (
            all(x in unknown["evidence"] for x in fallback + inv)
            and all(x in unknown_dna["evidence"] for x in fallback + inv)),
        "docs/dod-compiler.md:L6-U1": (
            valid_dna["fingerprint"] == security["project_dna_fingerprint"]
            and rejects_tampered_dna),
        "docs/evaluacion-agentes.md:L13-U1": (
            duplicate_rejected and rejects_metric(unexpected="fixture")
            and rejects_metric(commits=-1)
            and rejects_metric(completed_at="2026-09-24T12:00:00")
            and rejects_metric(review_rounds=4)),
        "docs/evaluacion-agentes.md:L17-U1": (
            sparse_backend["recommendation"] is None
            and sparse_backend["configurations"][0]["rank"] is None
            and sparse_backend["configurations"][0]["sample_status"] == "insufficient_data"
            and success_ranks["recommendation"] is not None),
        "docs/evaluacion-agentes.md:L19-U1": (
            success_ranks["configurations"][0]["configuration"]["model"] == "beta"
            and success_ranks["configurations"][0]["success_rate"] == 1.0
            and success_ranks["recommendation"]["model"] == "beta"),
        "docs/evaluacion-agentes.md:L20-U1": (
            incident_ranks["configurations"][0]["configuration"]["model"] == "alpha"
            and incident_ranks["configurations"][0]["incidents_per_task"] == 0.0
            and incident_ranks["recommendation"]["model"] == "alpha"),
    }


def assess(docs: object, checks: object) -> dict[str, str]:
    states = dict.fromkeys(CLAUSES, UNKNOWN)
    if type(docs) is not dict or type(checks) is not dict:
        return states
    try:
        matrix_rows(docs.get(MATRIX))
    except ValueError:
        return states
    if (set(docs) != {MATRIX, DOD, EVAL} or set(checks) != set(CLAUSES)
            or not all(source_matches(k, docs) for k in CLAUSES)
            or any(type(v) is not bool for v in checks.values())):
        return states
    for key in CLAUSES:
        if checks[key]:
            states[key] = LOCAL
    return states


class BrechasFactory15Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs, observed = read_sources(), proof()
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(matrix_rows(docs[MATRIX])))
        self.assertEqual(set(CLAUSES), set(observed))
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertTrue(source_matches(key, docs))
                self.assertIs(observed[key], True)
                self.assertEqual(LOCAL, assess(docs, observed)[key])

    def test_falla_cerrado(self) -> None:
        docs, observed = read_sources(), proof()
        for key in CLAUSES:
            row = next(s for s in docs[MATRIX].splitlines()
                       if s.startswith("| `" + key + "` |"))
            for bad in (docs[MATRIX].replace(row, "", 1),
                        docs[MATRIX] + "\n" + row,
                        docs[MATRIX].replace(row, row.replace("NO_VERIFICABLE",
                                                            "CUBIERTO", 1), 1)):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(bad)
                self.assertEqual({UNKNOWN}, set(assess({**docs, MATRIX: bad}, observed).values()))
        for key in CLAUSES:
            self.assertEqual(UNKNOWN, assess(docs, {**observed, key: None})[key])
        self.assertEqual({UNKNOWN}, set(assess({}, observed).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))
        self.assertEqual({UNKNOWN}, set(assess({**docs, DOD: ""}, observed).values()))
        self.assertEqual({UNKNOWN}, set(assess({**docs, EVAL: "corrupted"}, observed).values()))

    def test_sin_datos_reales(self) -> None:
        module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {alias.name.split(".")[0] for node in ast.walk(module)
                   if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(module)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {"requests", "urllib", "socket", "httpx",
                                    "subprocess", "pymysql", "selenium"})
        example = record(42)
        self.assertEqual("synthetic", example["agent"])
        self.assertEqual("fixture", example["prompt_id"])
        self.assertFalse(any("@" in str(value) for value in example.values()))

    def test_estados_unknown_explicitos(self) -> None:
        docs, observed = read_sources(), proof()
        self.assertEqual({LOCAL}, set(assess(docs, observed).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {**observed, "production": True}).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {**observed, "CI": "success"}).values()))
        for key in CLAUSES:
            self.assertEqual(UNKNOWN, assess(docs, {**observed, key: False})[key])
        self.assertNotIn("VALIDATED_IN_PRODUCTION", assess(docs, observed).values())


if __name__ == "__main__":
    unittest.main()
