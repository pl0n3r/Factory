#!/usr/bin/env python3
"""Factory #1641: 16 synthetic Fitness and Growth/Pruning gap contracts.

Local behavior is not proof of actual promotion, live metrics, a merged PR,
remote CI, protected operations or production. The matrix stays read-only.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import re
import unittest

from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from evolution.fitness import FitnessError, compare_fitness
from evolution.growth import (
    GrowthError, canonical_capability, compile_growth_candidate,
    detect_capability_gap,
)
from evolution.pruning import (
    PruningError, compile_pruning_candidate, evaluate_pruning,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
FITNESS = ROOT / "docs/fitness-engine.md"
GROWTH = ROOT / "docs/growth-pruning.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
TICK = chr(96)

CLAUSES = {
    "docs/fitness-engine.md:L69-U1": "Solo compara evidencia entregada explícitamente.",
    "docs/fitness-engine.md:L75-U1": "reversibility",
    "docs/growth-pruning.md:L10-U1": "Solo normaliza",
    "docs/growth-pruning.md:L20-U1": "capacidad requerida",
    "docs/growth-pruning.md:L21-U1": "valor esperado",
    "docs/growth-pruning.md:L22-U1": "fingerprint del gap",
    "docs/growth-pruning.md:L23-U1": "evidencia origen",
    "docs/growth-pruning.md:L24-U1": "rollback reversible",
    "docs/growth-pruning.md:L30-U1": "evaluate_pruning()",
    "docs/growth-pruning.md:L33-U1": "edad >= 90 días",
    "docs/growth-pruning.md:L34-U1": "valor <= 0.25",
    "docs/growth-pruning.md:L35-U1": "al menos 2 referencias de evidencia",
    "docs/growth-pruning.md:L37-U1": "eligible=true",
    "docs/growth-pruning.md:L43-U1": "parent fingerprint",
    "docs/growth-pruning.md:L44-U1": "fingerprint de la evaluación",
    "docs/growth-pruning.md:L46-U1": "history_preserved=true",
}
IDENTIFIER = re.compile(
    r"^\| " + re.escape(TICK)
    + r"(?P<id>docs/(?:fitness-engine|growth-pruning)\.md:L\d+-U\d+)"
    + re.escape(TICK) + r" \|"
)


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """The exactly 16 identified rows must remain real, unique and unpromoted."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: missing matrix")
    found = {}
    for line in raw.splitlines():
        matched = IDENTIFIER.match(line)
        if matched is None or matched["id"] not in CLAUSES:
            continue
        key = matched["id"]
        if key in found:
            raise ValueError("UNKNOWN: duplicate " + key)
        cols = tuple(part.strip() for part in line.strip(" | ").split(" | "))
        if (len(cols) != 5 or cols[0] != TICK + key + TICK
                or cols[2] != "NO_VERIFICABLE"
                or "No se confirmó test + PR fusionado" not in cols[3]
                or "contraste #1570" not in cols[4]
                or CLAUSES[key].casefold() not in cols[1].casefold()):
            raise ValueError("UNKNOWN: malformed or promoted " + key)
        found[key] = cols
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: missing rows " + str(sorted(set(CLAUSES) - set(found))))
    return found


def metric(value, direction="higher"):
    return {"value": value, "direction": direction}


def fitness_vector(**extra):
    return {**{name: metric(1) for name in PROTECTED_INVARIANTS}, **extra}


def rejects(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except (FitnessError, GrowthError, PruningError, TypeError, ValueError):
        return True
    return False


def growth_inputs():
    return {
        "required_capability": "Analítica, CRÍTICA!",
        "available_capabilities": ["risk compiler", "fitness engine"],
        "evidence": ["synthetic:source-b", "synthetic:source-a", "synthetic:source-a"],
        "expected_value": "Detectar brecha en un escenario sintético.",
    }


def prune_inputs():
    return {
        "capability": "legacy formatter",
        "usage_count": 1,
        "age_days": 90,
        "value_score": 0.25,
        "evidence": ["synthetic:ref-b", "synthetic:ref-a"],
        "parent_fingerprint": "a" * 64,
    }


def behavioral_evidence() -> dict[str, bool]:
    """Run the actual pure implementations, never a duplicate fake algorithm."""
    base = fitness_vector(cost=metric(10, "lower"))
    candidate = deepcopy(base)
    candidate["cost"] = metric(8, "lower")
    first = compare_fitness(baseline=base, candidate=candidate)
    same = compare_fitness(baseline=deepcopy(base), candidate=deepcopy(candidate))
    changed = deepcopy(candidate)
    changed["cost"] = metric(9, "lower")
    different = compare_fitness(baseline=base, candidate=changed)
    unknown = compare_fitness(
        baseline={"cost": metric(10, "lower")},
        candidate={"cost": metric(8, "lower")},
    )
    fitness_only_explicit = (
        first == same and first["fingerprint"] != different["fingerprint"]
        and base["cost"]["value"] == 10 and candidate["cost"]["value"] == 8
        and set(first["dimensions"]) == set(base) | set(PROTECTED_INVARIANTS)
        and all(unknown["dimensions"][name]["status"] == "unknown"
                and unknown["dimensions"][name]["baseline"] is None
                and unknown["dimensions"][name]["candidate"] is None
                for name in PROTECTED_INVARIANTS)
        and unknown["claim"] == "inconclusive"
        and not unknown["can_claim_improvement"]
    )

    guard = compare_fitness(
        baseline={"reversibility": metric(1), "authority": metric(1),
                  "latency": metric(10, "lower")},
        candidate={"reversibility": metric(0), "authority": metric(0),
                   "latency": metric(5, "lower")},
    )
    protected = (
        {"reversibility", "authority"}.issubset(PROTECTED_INVARIANTS)
        and guard["claim"] == "blocked"
        and guard["protected_regressions"] == ["authority", "reversibility"]
        and all(guard["dimensions"][name]["protected"]
                for name in ("reversibility", "authority"))
        and not guard["can_claim_improvement"]
        and rejects(
            compare_fitness,
            baseline={"reversibility": metric(1), "authority": metric(1)},
            candidate={"reversibility": metric(0), "authority": metric(0)},
            protected_dimensions=["reversibility", "authority"],
        )
    )

    data = growth_inputs()
    gap = detect_capability_gap(
        required_capability=data["required_capability"],
        available_capabilities=data["available_capabilities"],
    )
    growth = compile_growth_candidate(gap=gap, **data)
    value = growth["candidate"]["changes"][0]["value"]
    reuse = detect_capability_gap(
        required_capability=data["required_capability"],
        available_capabilities=["ÁNALÍTICA CRITICA", "risk compiler"],
    )
    semantic_distinction = detect_capability_gap(
        required_capability="reports", available_capabilities=["informes"]
    )
    normalization = (
        canonical_capability("  ÁNALÍTICA, crítica!!!  ") == "analitica-critica"
        and gap["required"] == "analitica-critica"
        and gap["gap"] is True and reuse["gap"] is False
        and reuse["reuse"] == "ÁNALÍTICA CRITICA"
        and semantic_distinction["gap"] is True
        and compile_growth_candidate(
            gap=reuse,
            required_capability=data["required_capability"],
            available_capabilities=["ÁNALÍTICA CRITICA", "risk compiler"],
            evidence=data["evidence"], expected_value=data["expected_value"],
        ) is None
    )
    growth_checks = {
        "L10-U1": normalization,
        "L20-U1": (
            growth["capability"] == "analitica-critica"
            and value["capability"] == gap["required"]
            and growth["candidate"]["changes"][0]["operation"] == "add"
        ),
        "L21-U1": (
            value["expected_value"] == data["expected_value"]
            and growth["expected_value"] == data["expected_value"]
        ),
        "L22-U1": (
            growth["lineage"]["gap_fingerprint"] == gap["fingerprint"]
            and value["lineage"]["gap_fingerprint"] == gap["fingerprint"]
            and re.fullmatch(r"[0-9a-f]{64}", gap["fingerprint"]) is not None
        ),
        "L23-U1": (
            value["lineage"]["evidence"] ==
            ["synthetic:source-a", "synthetic:source-b"]
            and growth["candidate"]["evidence"] ==
            ["synthetic:source-a", "synthetic:source-b"]
        ),
        "L24-U1": (
            growth["candidate"]["rollback"] ==
            {"reversible": True, "strategy": "revert"}
            and validate_candidate(growth["candidate"]) ==
            growth["candidate_fingerprint"]
        ),
    }

    source = prune_inputs()
    evaluation = evaluate_pruning(**source)
    pruning = compile_pruning_candidate(evaluation, **source)
    artifact = pruning["candidate"]["changes"][0]["value"]
    lowered = []
    for change in ({"usage_count": 2}, {"age_days": 89},
                   {"value_score": 0.251}, {"evidence": ["synthetic:ref-a"]},
                   {"evidence": ["synthetic:ref-a", "synthetic:ref-a"]}):
        kwargs = {**source, **change}
        item = evaluate_pruning(**kwargs)
        lowered.append((item, compile_pruning_candidate(item, **kwargs)))
    usage_failed, age_failed, score_failed, refs_failed, duplicate_failed = lowered
    fresh = evaluate_pruning(**{**source, "age_days": 91})
    no_forgery = rejects(
        compile_pruning_candidate, {**evaluation, "eligible": False}, **source
    )
    no_forgery &= rejects(
        compile_pruning_candidate, evaluation,
        **{**source, "age_days": 91},
    )
    criteria = evaluation["criteria"]
    prune_checks = {
        "L30-U1": (
            evaluation["metrics"] == {"usage_count": 1, "age_days": 90,
                                      "value_score": 0.25}
            and criteria["usage_low"]
            and not usage_failed[0]["criteria"]["usage_low"]
            and not usage_failed[0]["eligible"]
            and rejects(evaluate_pruning, **{**source, "usage_count": None})
            and rejects(evaluate_pruning, **{**source, "value_score": float("nan")})
        ),
        "L33-U1": (
            criteria["old_enough"] and not age_failed[0]["criteria"]["old_enough"]
            and not age_failed[0]["eligible"] and fresh["eligible"]
        ),
        "L34-U1": (
            criteria["value_low"] and not score_failed[0]["criteria"]["value_low"]
            and not score_failed[0]["eligible"]
        ),
        "L35-U1": (
            evaluation["evidence"] == ["synthetic:ref-a", "synthetic:ref-b"]
            and not refs_failed[0]["eligible"]
            and not duplicate_failed[0]["eligible"]
        ),
        "L37-U1": (
            evaluation["eligible"] is True
            and all(not item["eligible"] and output is None
                    for item, output in lowered)
            and no_forgery
            and rejects(evaluate_pruning, **{**source, "protected": True})
            and rejects(evaluate_pruning, **{**source, "capability": "authority"})
        ),
        "L43-U1": (
            evaluation["lineage"]["parent_fingerprint"] == source["parent_fingerprint"]
            and pruning["lineage"]["parent_fingerprint"] == source["parent_fingerprint"]
            and artifact["lineage"]["parent_fingerprint"] == source["parent_fingerprint"]
        ),
        "L44-U1": (
            re.fullmatch(r"[0-9a-f]{64}", evaluation["fingerprint"]) is not None
            and pruning["lineage"]["evaluation_fingerprint"] == evaluation["fingerprint"]
            and artifact["lineage"]["evaluation_fingerprint"] == evaluation["fingerprint"]
        ),
        "L46-U1": (
            evaluation["lineage"]["history_preserved"] is True
            and pruning["lineage"]["history_preserved"] is True
            and artifact["lineage"]["history_preserved"] is True
            and artifact["status"] == "prune-candidate"
            and pruning["candidate"]["changes"][0]["operation"] == "add"
            and pruning["candidate"]["rollback"] ==
            {"reversible": True, "strategy": "restore_baseline"}
            and validate_candidate(pruning["candidate"]) ==
            pruning["candidate_fingerprint"]
        ),
    }
    result = {
        "docs/fitness-engine.md:L69-U1": fitness_only_explicit,
        "docs/fitness-engine.md:L75-U1": protected,
    }
    result.update({"docs/growth-pruning.md:" + key: value
                   for key, value in {**growth_checks, **prune_checks}.items()})
    return result


def verdict(raw: object, checked: object, docs: object) -> dict[str, dict[str, str]]:
    """No untrusted or partial input may manufacture remote/operational proof."""
    result = {
        key: {"local": UNKNOWN, "full_scope": UNKNOWN,
              "ci": UNKNOWN, "production": UNKNOWN}
        for key in CLAUSES
    }
    try:
        matrix_rows(raw)
    except ValueError:
        return result
    if (type(checked) is not dict or set(checked) != set(CLAUSES)
            or any(type(value) is not bool for value in checked.values())
            or type(docs) is not dict or set(docs) != {"fitness", "growth"}
            or any(type(value) is not str or not value for value in docs.values())):
        return result
    for key, ok in checked.items():
        doc = docs["fitness"] if "fitness-engine" in key else docs["growth"]
        if ok and CLAUSES[key] in doc:
            result[key]["local"] = LOCAL
    return result


class BrechasFactory23Tests(unittest.TestCase):
    def test_contrato_principal(self):
        raw = MATRIX.read_text(encoding="utf-8")
        docs = {"fitness": FITNESS.read_text(encoding="utf-8"),
                "growth": GROWTH.read_text(encoding="utf-8")}
        evidence = behavioral_evidence()
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(matrix_rows(raw)))
        self.assertEqual(set(CLAUSES), set(evidence))
        for key, status in verdict(raw, evidence, docs).items():
            with self.subTest(row=key):
                self.assertTrue(evidence[key], key)
                self.assertEqual(LOCAL, status["local"])
                self.assertEqual(UNKNOWN, status["full_scope"])

    def test_falla_cerrado(self):
        raw = MATRIX.read_text(encoding="utf-8")
        docs = {"fitness": FITNESS.read_text(encoding="utf-8"),
                "growth": GROWTH.read_text(encoding="utf-8")}
        evidence = behavioral_evidence()
        row = next(x for x in raw.splitlines()
                   if x.startswith("| " + TICK +
                                   "docs/growth-pruning.md:L37-U1" + TICK + " |"))
        for damaged in (
            raw.replace(row, "", 1), raw + "\n" + row,
            raw.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            raw.replace(row, row.replace("contraste #1570", "contraste #999"), 1),
        ):
            with self.subTest(case=damaged[-40:]):
                with self.assertRaisesRegex(ValueError, "UNKNOWN"):
                    matrix_rows(damaged)
                self.assertTrue(all(value["local"] == UNKNOWN
                                    for value in verdict(damaged, evidence, docs).values()))
        for invalid in (None, {}, {"ci": "success"}, {**evidence, "extra": True}):
            self.assertTrue(all(value["local"] == UNKNOWN
                                for value in verdict(raw, invalid, docs).values()))
        self.assertEqual(UNKNOWN, verdict(raw, evidence, {})[
            "docs/growth-pruning.md:L37-U1"]["local"])
        self.assertEqual(UNKNOWN, verdict(raw, {
            **evidence, "docs/growth-pruning.md:L37-U1": None
        }, docs)["docs/growth-pruning.md:L37-U1"]["local"])
        self.assertTrue(rejects(detect_capability_gap,
                                required_capability="", available_capabilities=[]))
        self.assertTrue(rejects(evaluate_pruning, **{
            **prune_inputs(), "parent_fingerprint": "bad"
        }))
        self.assertTrue(rejects(compile_growth_candidate,
            gap={"gap": True}, **growth_inputs()))
        self.assertTrue(rejects(compile_pruning_candidate,
            {"eligible": True}, **prune_inputs()))

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {a.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for a in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {
            "requests", "httpx", "socket", "urllib", "subprocess",
            "pymysql", "playwright", "os"
        })
        self.assertTrue(MATRIX.is_file() and FITNESS.is_file() and GROWTH.is_file())
        self.assertTrue(all(type(v) is bool for v in behavioral_evidence().values()))
        self.assertTrue(all(x.startswith("synthetic:") for x in
                            growth_inputs()["evidence"] + prune_inputs()["evidence"]))

    def test_estados_unknown_explicitos(self):
        result = verdict(
            MATRIX.read_text(encoding="utf-8"), behavioral_evidence(),
            {"fitness": FITNESS.read_text(encoding="utf-8"),
             "growth": GROWTH.read_text(encoding="utf-8")},
        )
        for key, status in result.items():
            with self.subTest(row=key):
                self.assertEqual(LOCAL, status["local"])
                self.assertEqual(UNKNOWN, status["full_scope"])
                self.assertEqual(UNKNOWN, status["ci"])
                self.assertEqual(UNKNOWN, status["production"])
        self.assertTrue(all(v["local"] == UNKNOWN
                            for v in verdict("", {}, {}).values()))


if __name__ == "__main__":
    unittest.main()
