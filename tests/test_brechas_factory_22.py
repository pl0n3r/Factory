#!/usr/bin/env python3
"""Factory #1640: 16 offline, fail-closed Feedback Mesh and Fitness contracts.

LOCAL_CONTRACT proves deterministic synthetic behavior only, not a remote PR
state, actual promotion, CI, release, #248 AC-09 or production.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
import unittest

from evolution.constitution import PROTECTED_INVARIANTS
from evolution.fitness import FitnessError, compare_fitness

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
FEEDBACK_DOC = ROOT / "docs/feedback-mesh-e2e.md"
FITNESS_DOC = ROOT / "docs/fitness-engine.md"
MANIFEST = ROOT / "feedback/data/feedback-mesh-e2e.json"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
CLAUSES = {
    "docs/feedback-mesh-e2e.md:L9-U1": "Factory PR #253",
    "docs/feedback-mesh-e2e.md:L33-U1": "falla cerrado si un ref",
    "docs/feedback-mesh-e2e.md:L39-U1": "No satisface por sí solo",
    "docs/fitness-engine.md:L20-U1": "direction",
    "docs/fitness-engine.md:L30-U1": "Fitness informa el bloqueo",
    "docs/fitness-engine.md:L37-U1": "improved",
    "docs/fitness-engine.md:L38-U1": "equal",
    "docs/fitness-engine.md:L39-U1": "regressed",
    "docs/fitness-engine.md:L40-U1": "unknown",
    "docs/fitness-engine.md:L50-U1": "blocked",
    "docs/fitness-engine.md:L51-U1": "inconclusive",
    "docs/fitness-engine.md:L52-U1": "mixed",
    "docs/fitness-engine.md:L53-U1": "improved",
    "docs/fitness-engine.md:L54-U1": "equal",
    "docs/fitness-engine.md:L56-U1": "can_claim_improvement",
    "docs/fitness-engine.md:L62-U1": "números no finitos",
}
_TICK = chr(96)
_ID = re.compile(r"^\|\s*" + re.escape(_TICK)
                 + r"(?P<key>docs/(?:feedback-mesh-e2e|fitness-engine)\.md:L\d+-U\d+)"
                 + re.escape(_TICK) + r"\s*\|")


def rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Require all 16 census rows, once each, without fabricated promotion."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matrix missing")
    found = {}
    for line in raw.splitlines():
        match = _ID.match(line)
        if not match or match["key"] not in CLAUSES:
            continue
        key = match["key"]
        if key in found:
            raise ValueError("UNKNOWN: duplicate " + key)
        cells = tuple(cell.strip() for cell in line.strip(" | ").split(" | "))
        if (len(cells) != 5 or cells[0] != f"{_TICK}{key}{_TICK}"
                or CLAUSES[key].casefold() not in cells[1].casefold()
                or cells[2] != "NO_VERIFICABLE"
                or "No se confirmó test + PR fusionado" not in cells[3]
                or "contraste #1570" not in cells[4]):
            raise ValueError("UNKNOWN: malformed/promoted " + key)
        found[key] = cells
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: missing rows " + str(sorted(set(CLAUSES) - set(found))))
    return found


def metric(value, direction="higher"):
    return {"value": value, "direction": direction}


def baseline(**extra):
    return {**{name: metric(1) for name in PROTECTED_INVARIANTS}, **extra}


def compare(changes, extra=None):
    original = baseline(**(extra or {}))
    target = deepcopy(original)
    target.update(changes)
    return compare_fitness(baseline=original, candidate=target)


def mesh_validator():
    """Load the existing behavioral validator, not a duplicate implementation."""
    spec = spec_from_file_location(
        "factory_feedback_mesh_1640", ROOT / "tests/test_feedback_mesh_e2e.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("UNKNOWN: mesh contract absent")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_manifest


# Acceptance loader removes its temporary import paths before running each test.
# Import the existing validator while the root is still on sys.path.
_MESH_VALIDATOR = mesh_validator()


def rejects(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except (ValueError, FitnessError, TypeError):
        return True
    return False


def evidence() -> dict[str, bool]:
    """Exercise real fitness implementation and existing mesh manifest validator."""
    validate = _MESH_VALIDATOR
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate(manifest)
    refs = {(r["repo"], r["pr"]): r for r in manifest["evidence"]}
    factory253 = refs[("pl0n3r/Factory", 253)]
    mesh_checks = {
        "L9-U1": (factory253["state"] == "merged"
                  and factory253["merge_sha"] == "34409905f874b118b973ec316041467534fe2cd6"),
        "L33-U1": False,
        "L39-U1": (manifest["decision"] == {
            "status": "reject", "reason": "insufficient_evidence",
            "promotion_executed": False
        } and manifest["stable_policy"]["changed"] is False),
    }
    open_with_merge = deepcopy(manifest)
    open_with_merge["evidence"][1]["merge_sha"] = "a" * 40
    merged_without_sha = deepcopy(manifest)
    merged_without_sha["evidence"][0]["merge_sha"] = None
    forged_promotion = deepcopy(manifest)
    forged_promotion["decision"]["promotion_executed"] = True
    mesh_checks["L33-U1"] = (rejects(validate, open_with_merge)
                             and rejects(validate, merged_without_sha))
    mesh_checks["L39-U1"] &= rejects(validate, forged_promotion)

    improved = compare({"cost": metric(8, "lower")}, {"cost": metric(10, "lower")})
    equal = compare({})
    regressed = compare({"cost": metric(12, "lower")}, {"cost": metric(10, "lower")})
    missing = compare_fitness(
        baseline=baseline(cost=metric(10, "lower")), candidate=baseline()
    )
    blocked = compare(
        {"security": metric(0.9), "cost": metric(8, "lower")},
        {"cost": metric(10, "lower")}
    )
    mixed = compare(
        {"cost": metric(12, "lower"), "throughput": metric(105)},
        {"cost": metric(10, "lower"), "throughput": metric(100)}
    )
    wrong_direction = rejects(
        compare_fitness,
        baseline=baseline(cost=metric(10, "lower")),
        candidate=baseline(cost=metric(9, "higher"))
    )
    nonfinite = all(rejects(
        compare_fitness,
        baseline=baseline(cost=metric(10, "lower")),
        candidate=baseline(cost=metric(v, "lower"))
    ) for v in (float("inf"), float("-inf"), float("nan")))
    ordered = baseline(cost=metric(10, "lower"))
    reordered = dict(reversed(tuple(ordered.items())))
    first = compare_fitness(
        baseline=ordered, candidate=baseline(cost=metric(8, "lower"))
    )
    second = compare_fitness(
        baseline=reordered, candidate=baseline(cost=metric(8, "lower"))
    )

    fitness_checks = {
        "L20-U1": (wrong_direction
                   and missing["dimensions"]["cost"]["candidate"] is None
                   and missing["dimensions"]["cost"]["delta"] is None),
        "L30-U1": (blocked["claim"] == "blocked"
                   and blocked["can_claim_improvement"] is False),
        "L37-U1": improved["dimensions"]["cost"]["status"] == "improved",
        "L38-U1": equal["dimensions"]["security"]["status"] == "equal",
        "L39-U1": regressed["dimensions"]["cost"]["status"] == "regressed",
        "L40-U1": missing["dimensions"]["cost"]["status"] == "unknown",
        "L50-U1": (blocked["claim"] == "blocked"
                   and blocked["protected_regressions"] == ["security"]),
        "L51-U1": (missing["claim"] == "inconclusive"
                   and "cost" in missing["missing_dimensions"]),
        "L52-U1": mixed["claim"] == "mixed",
        "L53-U1": improved["claim"] == "improved",
        "L54-U1": equal["claim"] == "equal",
        "L56-U1": (improved["can_claim_improvement"] is True
                   and all(not v["can_claim_improvement"] for v
                           in (equal, regressed, missing, blocked, mixed))),
        "L62-U1": (nonfinite and first == second
                   and re.fullmatch(r"[0-9a-f]{64}", first["fingerprint"]) is not None),
    }
    result = {"docs/feedback-mesh-e2e.md:" + k: v
              for k, v in mesh_checks.items()}
    result.update({"docs/fitness-engine.md:" + k: v
                   for k, v in fitness_checks.items()})
    return result


def verdict(matrix, checked, source_texts):
    """Untrusted, missing or ambiguous input cannot become operational green."""
    results = {key: {"local": UNKNOWN, "full_scope": UNKNOWN,
                     "ci": UNKNOWN, "production": UNKNOWN} for key in CLAUSES}
    try:
        rows(matrix)
    except ValueError:
        return results
    if (type(checked) is not dict or set(checked) != set(CLAUSES)
            or any(type(v) is not bool for v in checked.values())
            or type(source_texts) is not dict
            or set(source_texts) != {"feedback", "fitness"}
            or any(type(v) is not str or not v for v in source_texts.values())):
        return results
    for key, good in checked.items():
        source = (source_texts["feedback"] if "feedback-mesh" in key
                  else source_texts["fitness"])
        if good and CLAUSES[key] in source:
            results[key]["local"] = LOCAL
    return results


class BrechasFactory22Tests(unittest.TestCase):
    def test_contrato_principal(self):
        table = MATRIX.read_text(encoding="utf-8")
        docs = {"feedback": FEEDBACK_DOC.read_text(encoding="utf-8"),
                "fitness": FITNESS_DOC.read_text(encoding="utf-8")}
        checked = evidence()
        self.assertEqual(set(CLAUSES), set(rows(table)))
        self.assertEqual(set(CLAUSES), set(checked))
        result = verdict(table, checked, docs)
        for key in CLAUSES:
            with self.subTest(clause=key):
                self.assertTrue(checked[key], key)
                self.assertEqual(LOCAL, result[key]["local"])

    def test_falla_cerrado(self):
        table = MATRIX.read_text(encoding="utf-8")
        docs = {"feedback": FEEDBACK_DOC.read_text(encoding="utf-8"),
                "fitness": FITNESS_DOC.read_text(encoding="utf-8")}
        checked = evidence()
        first = next(line for line in table.splitlines()
                     if line.startswith("| " + _TICK
                                        + "docs/fitness-engine.md:L20-U1" + _TICK + " |"))
        for damaged in (table + "\n" + first, table.replace(first, ""),
                        table.replace(first, first.replace("NO_VERIFICABLE", "CUBIERTO")),
                        table + "\n" + first.replace(" |", "    |", 1)):
            with self.assertRaisesRegex(ValueError, "UNKNOWN"):
                rows(damaged)
        for bad in (None, {}, {"ci": True}):
            self.assertTrue(all(v["local"] == UNKNOWN
                                for v in verdict(table, bad, docs).values()))
        wrong = {**checked, "docs/fitness-engine.md:L37-U1": None}
        self.assertTrue(all(v["local"] == UNKNOWN
                            for v in verdict(table, wrong, docs).values()))
        self.assertEqual(UNKNOWN, verdict(table, checked, {})[
            "docs/feedback-mesh-e2e.md:L33-U1"]["local"])

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = {alias.name.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.Import) for alias in node.names}
        names |= {node.module.split(".")[0] for node in ast.walk(tree)
                  if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(names & {
            "requests", "httpx", "socket", "urllib", "pymysql", "playwright"
        })
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual("review-efficiency-insufficient-evidence",
                         json.loads(MANIFEST.read_text(encoding="utf-8"))["scenario"])

    def test_estados_unknown_explicitos(self):
        result = verdict(MATRIX.read_text(encoding="utf-8"), evidence(), {
            "feedback": FEEDBACK_DOC.read_text(encoding="utf-8"),
            "fitness": FITNESS_DOC.read_text(encoding="utf-8"),
        })
        for key in CLAUSES:
            with self.subTest(clause=key):
                self.assertEqual(UNKNOWN, result[key]["full_scope"])
                self.assertEqual(UNKNOWN, result[key]["ci"])
                self.assertEqual(UNKNOWN, result[key]["production"])
        self.assertEqual(UNKNOWN, verdict("", evidence(), {})[
            "docs/feedback-mesh-e2e.md:L39-U1"]["local"])


if __name__ == "__main__":
    unittest.main()
