"""Factory #1651: 16 brechas operacionales con evidencia sintética y UNKNOWN."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from evolution.constitution import PROTECTED_INVARIANTS
from lab.factory_lab import evaluate_shadow

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "docs/living-software-operational-e2e.md"
UNKNOWN = "UNKNOWN"
LINES = (22, 23, 24, 26, 28, 42, 43, 44, 45, 55, 59, 60, 61, 62, 63, 64)
UNITS = tuple(f"{SOURCE}:L{n}-U1" for n in LINES)
GAPS = {
    55: "UNKNOWN: falta evidencia para generalización futura",
    59: "UNKNOWN: manifiesto no audita todos los Engines y servicios",
    61: "UNKNOWN: shadow no certifica legal, gasto o PII global",
    62: "UNKNOWN: no se comprobó el diff completo de #330",
    63: "UNKNOWN: stable_mutation=false no prueba diff del coordinador",
}
RUNS = (36507015627, 36507097760, 36507219161, 36507269422)


def load():
    return json.loads((ROOT / "feedback/data/living-software-operational-e2e.json")
                      .read_text(encoding="utf-8"))


def duration(row):
    a = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
    b = datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00"))
    return int((b - a).total_seconds())


def candidate(data):
    return {
        "version": 1,
        "changes": [{"path": "evolution_state.heuristics.reservation_readiness_preflight",
                     "operation": "add", "value": {
                         "checks": ["acceptance_contract", "status_available",
                                    "factory_plan_task"],
                         "mode": "preflight", "scope": "issue_reservation"}}],
        "evidence": ["pl0n3r/Factory#247", *data["origin"]["provenance"]],
        "rollback": {"reversible": True,
                     "strategy": data["shadow_candidate"]["rollback"]},
    }


def vectors(data):
    protected = {key: {"value": 1.0, "direction": "higher"}
                 for key in PROTECTED_INVARIANTS}
    before, after = dict(protected), dict(protected)
    before["coordination_seconds"] = {
        "value": data["complexity"]["before_coordination_seconds"],
        "direction": "lower"}
    after["coordination_seconds"] = {
        "value": data["complexity"]["after_coordination_seconds"],
        "direction": "lower"}
    before["reservation_attempts"] = {"value": 3, "direction": "lower"}
    after["reservation_attempts"] = {"value": 1, "direction": "lower"}
    return before, after


def assess(data, doc):
    """Solo evidencia acotada produce True; la ausente/ambigua produce UNKNOWN."""
    unknown = {unit: UNKNOWN for unit in UNITS}
    if not isinstance(data, dict) or not isinstance(doc, str) or not doc:
        return unknown
    try:
        rows = data["coordination_attempts"]
        if not isinstance(rows, list) or len(rows) != 4:
            return unknown
        if [r["run_id"] for r in rows] != list(RUNS):
            return unknown
        if [r["duration_seconds"] for r in rows] != [duration(r) for r in rows]:
            return unknown
        if data["origin"]["provenance"] != [f"run:{n}" for n in RUNS]:
            return unknown
        if [r["effect"] for r in rows] != [
            "acceptance_contract_rejected",
            "no_reservation_missing_available_state",
            "unplanned_parallel_work_rejected", "reservation_created",
        ]:
            return unknown
        before, after = vectors(data)
        shadow_data = data["shadow_candidate"]
        shadow = evaluate_shadow(
            stable_sha=shadow_data["stable_sha"],
            candidate_sha=shadow_data["candidate_sha"],
            stable_metrics=before, candidate_metrics=after,
            constitution_candidate=candidate(data),
        )
        decision = data["decision"]
        complexity = data["complexity"]
        posterior = data["posterior_execution"]
        checks = {
            22: set(PROTECTED_INVARIANTS) == {
                "security", "privacy", "traceability", "reversibility", "authority"
            } and shadow["fitness"]["protected_regressions"] == [],
            23: before["coordination_seconds"]["value"] >
                after["coordination_seconds"]["value"],
            24: before["reservation_attempts"]["value"] == 3
                and after["reservation_attempts"]["value"] == 1
                and rows[-1]["effect"] == "reservation_created",
            26: shadow["mode"] == "shadow"
                and shadow["mutation_allowed"] is False
                and shadow["external_writes"] == []
                and shadow_data["external_writes"] == []
                and shadow_data["rollback"] == "restore_baseline",
            28: decision["stable_mutation"] is False
                and decision["status"] == "adopted_bounded_scenario"
                and "No se modifica automáticamente" in doc,
            42: [r["duration_seconds"] for r in rows[:3]] == [7, 20, 8]
                and complexity["before_coordination_seconds"] == 35,
            43: rows[-1]["duration_seconds"] == 27
                and complexity["after_coordination_seconds"] == 27,
            44: posterior["pr_ci_run"] == 36507555400
                and posterior["pr_ci_duration_seconds"] == 29
                and complexity["useful_execution_seconds"] == 29,
            45: all(before[key] == after[key] for key in PROTECTED_INVARIANTS)
                and shadow["fitness"]["protected_regressions"] == [],
            55: False,
            59: False,
            60: decision["authority_expanded"] is False
                and shadow["promotion"]["execution"] == "not-performed",
            61: False,
            62: False,
            63: False,
            64: complexity["comparison_scope"] == "factory-247-reservation-readiness"
                and decision["scope"] == "issue-247-readiness-procedure"
                and "sin afirmar causalidad fuera del escenario #247" in doc,
        }
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return unknown
    return {f"{SOURCE}:L{n}-U1": True if checks[n] is True else UNKNOWN
            for n in LINES}


class BrechasFactory33Tests(unittest.TestCase):
    def test_contrato_principal(self):
        doc = (ROOT / SOURCE).read_text(encoding="utf-8")
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        verdicts = assess(load(), doc)
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(verdicts), set(UNITS))
        self.assertEqual(set(GAPS), set(LINES) - {
            22, 23, 24, 26, 28, 42, 43, 44, 45, 60, 64})
        for line in LINES:
            unit = f"{SOURCE}:L{line}-U1"
            with self.subTest(unit=unit):
                self.assertIn(chr(96) + unit + chr(96), matrix)
                if line in GAPS:
                    self.assertEqual(verdicts[unit], UNKNOWN)
                    self.assertTrue(GAPS[line].startswith("UNKNOWN:"))
                else:
                    self.assertIs(verdicts[unit], True, unit)

    def test_falla_cerrado(self):
        data = load()
        doc = (ROOT / SOURCE).read_text(encoding="utf-8")
        for case in (None, {}, {"coordination_attempts": []}):
            self.assertEqual(set(assess(case, doc).values()), {UNKNOWN})
        for path, value in (
            (("coordination_attempts", 0, "duration_seconds"), 999),
            (("coordination_attempts", 3, "effect"), "reservation_missing"),
            (("shadow_candidate", "external_writes"), ["synthetic-write"]),
            (("shadow_candidate", "stable_sha"), "invalid"),
            (("origin", "provenance"), []),
        ):
            changed = copy.deepcopy(data)
            cursor = changed
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            with self.subTest(path=path):
                self.assertIn(UNKNOWN, assess(changed, doc).values())

    def test_sin_datos_reales(self):
        data = load()
        self.assertEqual(data["origin"]["issue"], 247)
        self.assertEqual(data["shadow_candidate"]["external_writes"], [])
        self.assertFalse(data["decision"]["authority_expanded"])
        self.assertFalse(data["decision"]["stable_mutation"])
        self.assertNotIn("password", data)
        self.assertNotIn("token", data)

    def test_estados_unknown_explicitos(self):
        data = load()
        doc = (ROOT / SOURCE).read_text(encoding="utf-8")
        self.assertEqual(set(assess(data, "").values()), {UNKNOWN})
        self.assertEqual(set(assess(data, None).values()), {UNKNOWN})
        for line, why in GAPS.items():
            self.assertEqual(assess(data, doc)[f"{SOURCE}:L{line}-U1"], UNKNOWN)
            self.assertTrue(why.startswith("UNKNOWN:"))
        changed = copy.deepcopy(data)
        del changed["complexity"]["after_coordination_seconds"]
        self.assertEqual(set(assess(changed, doc).values()), {UNKNOWN})


if __name__ == "__main__":
    unittest.main()
