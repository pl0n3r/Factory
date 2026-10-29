#!/usr/bin/env python3
"""Factory #1634: synthetic agent metrics and evolution contracts, never live evidence."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evolution.constitution import EXPECTED_LIFECYCLE
from evolution.engine import EvolutionEngine
from evolution.models import EvolutionError
from metricas.evaluar_agentes import (
    DEFAULT_DATA_DIR, DEFAULT_OUTPUT_DIR, REQUIRED, ValidationError,
    aggregate, load_records, render_markdown, validate_record,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
EVAL = "docs/evaluacion-agentes.md"
EVOLUTION = "docs/evolution-engine.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
TICK = chr(96)
CLAUSES = {
    "docs/evaluacion-agentes.md:L21-U1": (EVAL, "mayor tasa de integración a la primera"),
    "docs/evaluacion-agentes.md:L22-U1": (EVAL, "menos commits de retrabajo"),
    "docs/evaluacion-agentes.md:L23-U1": (EVAL, "menos rondas de revisión"),
    "docs/evaluacion-agentes.md:L24-U1": (EVAL, "menos tokens cuando el dato existe"),
    "docs/evaluacion-agentes.md:L26-U1": (EVAL, "Solo se publica una recomendación"),
    "docs/evaluacion-agentes.md:L26-U2": (EVAL, "Tokens solo desempatan"),
    "docs/evaluacion-agentes.md:L26-U3": (EVAL, "telemetría parcial queda como"),
    "docs/evaluacion-agentes.md:L30-U1": (EVAL, "evalúa **el mes UTC anterior"),
    "docs/evaluacion-agentes.md:L32-U1": (EVAL, "lee únicamente"),
    "docs/evaluacion-agentes.md:L32-U2": (EVAL, "no acepta rutas arbitrarias"),
    "docs/evaluacion-agentes.md:L32-U3": (EVAL, "Con cero datos del periodo"),
    "docs/evaluacion-agentes.md:L34-U1": (EVAL, "de forma automática al cerrar una tarea"),
    "docs/evaluacion-agentes.md:L7-U1": (EVAL, "Campos obligatorios:"),
    "docs/evolution-engine.md:L10-U1": (EVOLUTION, "observe → remember → learn"),
    "docs/evolution-engine.md:L12-U1": (EVOLUTION, "Solo se admite la transición"),
    "docs/evolution-engine.md:L20-U1": (EVOLUTION, "generation"),
}
# These gaps need real authenticated workflow/consumer evidence, not fixtures.
UNOBSERVED = {
    "docs/evaluacion-agentes.md:L30-U1": "monthly workflow runtime not observed",
    "docs/evaluacion-agentes.md:L34-U1": "consumer automatic adoption not observed",
}


def documents() -> dict[str, str]:
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in (MATRIX, EVAL, EVOLUTION)}


def matrix_rows(raw: object) -> dict[str, str]:
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: missing matrix")
    found = {}
    for line in raw.splitlines():
        line = line.lstrip()
        for key, (_path, phrase) in CLAUSES.items():
            if not line.startswith("| " + TICK + key + TICK + " |"):
                continue
            if key in found:
                raise ValueError("UNKNOWN: duplicate " + key)
            cells = [part.strip() for part in line.strip("|").split("|")]
            if (len(cells) != 5 or cells[0] != TICK + key + TICK
                    or phrase.casefold() not in cells[1].casefold()
                    or cells[2] != "NO_VERIFICABLE"
                    or "No se confirmó test + PR fusionado" not in cells[3]
                    or "[contraste #1570]" not in cells[4]):
                raise ValueError("UNKNOWN: invalid evidence " + key)
            found[key] = cells[1]
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: incomplete matrix")
    return found


def source_matches(key: str, docs: object) -> bool:
    if key not in CLAUSES or type(docs) is not dict:
        return False
    path, phrase = CLAUSES[key]
    source = docs.get(path)
    if type(source) is not str:
        return False
    try:
        line = int(key.split(":L", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return False
    lines = source.splitlines()
    return 1 <= line <= len(lines) and phrase.casefold() in lines[line - 1].casefold()


def record(n: int, model: str = "alpha", **changes: object) -> dict[str, object]:
    data = {
        "task_id": f"factory#{n}", "task_type": "backend",
        "agent": "synthetic", "model": model, "prompt_id": "fixture",
        "roles": ["qa"], "success": True, "merged_first_try": True,
        "commits": 1, "review_rounds": 1, "rework_commits": 0,
        "incidents_after": 0, "completed_at": "2026-09-24T12:00:00Z",
        "tokens_input": 40, "tokens_output": 20,
    }
    data.update(changes)
    return data


def ranking(alpha: dict[str, object], beta: dict[str, object]) -> dict:
    records = [validate_record(record(i, model=m, **changes), "synthetic")
               for i, m, changes in (
                   (101, "alpha", alpha), (102, "alpha", alpha),
                   (103, "beta", beta), (104, "beta", beta),
               )]
    return aggregate(records, min_samples=2)["task_types"]["backend"]


def best(report: dict) -> str | None:
    choice = report["recommendation"]
    return choice["model"] if choice else None


def metric(report: dict, model: str, key: str) -> object:
    return next(row[key] for row in report["configurations"]
                if row["configuration"]["model"] == model)


def rejects_metric(data: dict) -> bool:
    try:
        validate_record(data, "synthetic")
    except ValidationError:
        return True
    return False


def rejects_transition(engine: EvolutionEngine, stage: str) -> bool:
    try:
        engine.transition(stage, reason="negative", evidence=["synthetic"])
    except EvolutionError:
        return True
    return False


def proof() -> dict[str, bool | None]:
    prefix = "docs/evaluacion-agentes.md:"
    first = ranking({"merged_first_try": False}, {"merged_first_try": True})
    rework = ranking({"rework_commits": 3}, {"rework_commits": 0})
    reviews = ranking({"review_rounds": 2}, {"review_rounds": 0})
    tokens = ranking({"tokens_input": 100}, {"tokens_input": 10})
    tied = ranking({}, {})
    missing_tokens = ranking({}, {"tokens_output": None})
    sparse = aggregate([validate_record(record(200), "synthetic")],
                       min_samples=2)["task_types"]["backend"]
    with TemporaryDirectory(prefix="factory-1634-") as directory:
        path = Path(directory) / "synthetic.jsonl"
        path.write_text(json.dumps(record(300)) + "\n", encoding="utf-8")
        empty = load_records([path], allow_empty=True, month="2026-10")
    empty_report = aggregate(empty, min_samples=2)
    source = (ROOT / "metricas/evaluar_agentes.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    flags = {node.args[0].value for node in ast.walk(main)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "add_argument"
             and node.args and isinstance(node.args[0], ast.Constant)
             and isinstance(node.args[0].value, str)}
    required = set(validate_record(record(301), "synthetic"))
    missing_rejected = all(
        rejects_metric({k: v for k, v in record(302).items() if k != field})
        for field in REQUIRED
    )
    candidate = {
        "version": 1,
        "changes": [{"path": "evolution_state.heuristics.synthetic",
                     "operation": "add", "value": {"status": "candidate"}}],
        "evidence": ["factory#1634:synthetic"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }
    engine = EvolutionEngine(candidate, reason="synthetic", evidence=["test:1634"])
    initial = engine.current
    jump_rejected = rejects_transition(engine, "learn")
    unknown_rejected = rejects_transition(engine, "unknown")
    for stage in engine.lifecycle[1:3]:
        engine.transition(stage, reason="stage", evidence=["test:" + stage])
    history = engine.history

    return {
        prefix + "L21-U1": best(first) == "beta" and metric(first, "beta", "first_merge_rate") == 1.0,
        prefix + "L22-U1": best(rework) == "beta" and metric(rework, "beta", "rework_commits_avg") == 0,
        prefix + "L23-U1": best(reviews) == "beta" and metric(reviews, "beta", "review_rounds_avg") == 0,
        prefix + "L24-U1": best(tokens) == "beta" and metric(tokens, "beta", "tokens_avg") == 30,
        prefix + "L26-U1": (best(first) == "beta" and tied["recommendation"] is None
                            and sparse["recommendation"] is None),
        prefix + "L26-U2": (best(tokens) == "beta" and tied["recommendation"] is None),
        prefix + "L26-U3": (missing_tokens["recommendation"] is None
                            and metric(missing_tokens, "beta", "tokens_avg") is None
                            and metric(missing_tokens, "beta", "tokens_complete_samples") == 0),
        prefix + "L30-U1": None,
        prefix + "L32-U1": (DEFAULT_DATA_DIR == ROOT / "metricas" / "datos"
                            and DEFAULT_OUTPUT_DIR == ROOT / "artifacts"),
        prefix + "L32-U2": flags == {"--month", "--min-samples", "--allow-empty"},
        prefix + "L32-U3": (empty == [] and empty_report["records"] == 0
                            and not empty_report["task_types"]
                            and "No hay datos suficientes" in render_markdown(empty_report)),
        prefix + "L34-U1": None,
        prefix + "L7-U1": missing_rejected and REQUIRED <= required,
        "docs/evolution-engine.md:L10-U1": engine.lifecycle == tuple(EXPECTED_LIFECYCLE),
        "docs/evolution-engine.md:L12-U1": (jump_rejected and unknown_rejected
                                          and [x.stage for x in history] == list(EXPECTED_LIFECYCLE[:3])),
        "docs/evolution-engine.md:L20-U1": (initial.generation == 0
                                          and [x.generation for x in history] == [0, 1, 2]
                                          and [x.parent_generation for x in history] == [None, 0, 1]),
    }


def assess(docs: object, observed: object) -> dict[str, str]:
    result = dict.fromkeys(CLAUSES, UNKNOWN)
    if type(docs) is not dict or type(observed) is not dict:
        return result
    try:
        matrix_rows(docs.get(MATRIX))
    except ValueError:
        return result
    if (set(docs) != {MATRIX, EVAL, EVOLUTION}
            or set(observed) != set(CLAUSES)
            or not all(source_matches(key, docs) for key in CLAUSES)
            or any(type(v) not in (bool, type(None)) for v in observed.values())):
        return result
    for key in CLAUSES:
        if observed[key] is True and key not in UNOBSERVED:
            result[key] = LOCAL
    return result


class BrechasFactory16Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs, observed = documents(), proof()
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(matrix_rows(docs[MATRIX])))
        self.assertEqual(set(CLAUSES), set(observed))
        self.assertEqual(set(UNOBSERVED), {k for k, v in observed.items() if v is None})
        states = assess(docs, observed)
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertTrue(source_matches(key, docs))
                if key in UNOBSERVED:
                    self.assertEqual(UNKNOWN, states[key], UNOBSERVED[key])
                else:
                    self.assertIs(observed[key], True)
                    self.assertEqual(LOCAL, states[key])

    def test_falla_cerrado(self) -> None:
        docs, observed = documents(), proof()
        for key in CLAUSES:
            row = next(s for s in docs[MATRIX].splitlines()
                       if s.startswith("| " + TICK + key + TICK + " |"))
            for bad in (docs[MATRIX].replace(row, "", 1),
                        docs[MATRIX] + "\n" + row,
                        docs[MATRIX].replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1)):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(bad)
                self.assertEqual({UNKNOWN}, set(assess({**docs, MATRIX: bad}, observed).values()))
        self.assertEqual({UNKNOWN}, set(assess({}, observed).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))
        for key in CLAUSES:
            self.assertEqual(UNKNOWN, assess(docs, {**observed, key: "success"})[key])
        self.assertEqual({UNKNOWN}, set(assess({**docs, EVAL: "invalid"}, observed).values()))
        self.assertEqual({UNKNOWN}, set(assess({**docs, EVOLUTION: "invalid"}, observed).values()))

    def test_sin_datos_reales(self) -> None:
        parsed = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {alias.name.split(".")[0] for node in ast.walk(parsed)
                   if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(parsed)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {"requests", "urllib", "socket", "subprocess",
                                    "httpx", "selenium", "pymysql"})
        fixture = record(99)
        self.assertEqual("synthetic", fixture["agent"])
        self.assertEqual("fixture", fixture["prompt_id"])
        self.assertFalse(any("@" in str(v) for v in fixture.values()))

    def test_estados_unknown_explicitos(self) -> None:
        docs, observed = documents(), proof()
        states = assess(docs, observed)
        self.assertEqual(set(UNOBSERVED), {k for k, v in states.items() if v == UNKNOWN})
        self.assertEqual({UNKNOWN}, set(assess(docs, {**observed, "production": True}).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {**observed, "CI": "success"}).values()))
        for key in CLAUSES:
            self.assertEqual(UNKNOWN, assess(docs, {**observed, key: False})[key])
        self.assertNotIn("VALIDATED_IN_PRODUCTION", states.values())


if __name__ == "__main__":
    unittest.main()
