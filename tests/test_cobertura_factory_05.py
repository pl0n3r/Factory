"""Factory #1796: cobertura conductual offline para contratos de diagnóstico/autonomía.

Ejecuta los evaluadores REALES del kit con fixtures ficticios. Las cláusulas
históricas, de límites arquitectónicos o publicación real se clasifican B/C
en el PR y el Issue; esto NO acredita despliegues, tags, auditoría histórica,
seguridad de infraestructura, consumo real de Actions ni integración live.
La prueba deliberadamente NO lee docs/matriz-cobertura*.md.
"""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from functools import lru_cache
import socket
import unittest
from unittest.mock import patch

from evolution.autonomy import (
    AUTHORITY_FINGERPRINT, AUTONOMY_LEVELS, AutonomyEngine,
    AutonomyError, CapabilityScope,
)
from evolution.fitness import compare_fitness
from intelligence.project_dna import discover_project_dna
from intelligence.risk_compiler import compile_risk
from scripts.automerge_construccion import evaluate

HEAD = "a" * 40
BASE = "b" * 40

OFFLINE = frozenset((
    "docs/automerge-construccion.md:B01",
    "docs/automerge-construccion.md:B02",
    "docs/automerge-construccion.md:B03",
    "docs/autonomy-engine.md:L17-U1",
    "docs/autonomy-engine.md:L19-U1",
    "docs/autonomy-engine.md:L20-U1",
    "docs/autonomy-engine.md:L21-U1",
    "docs/autonomy-engine.md:L22-U1",
    "docs/autonomy-engine.md:L24-U1",
    "docs/autonomy-engine.md:L28-U1",
    "docs/autonomy-engine.md:L31-U1",
    "docs/autonomy-engine.md:L32-U1",
    "docs/autonomy-engine.md:L34-U1",
    "docs/capability-authority.md:L16-U1",
))
WORLD = {
    "docs/arquitectura-tecnica.md:B03":
        "B: cadena real de publicación/rollback y autorización de mover v1",
    "docs/auditoria-pre-v1.md:B02":
        "B: mitigar trust-root/bootstrap y verificar puerta humana exact-SHA",
    "docs/auditoria-pre-v1.md:B04":
        "B: medir tráfico real de coordinación y costo de GitHub Actions",
}
POLICY = {
    "docs/arquitectura-tecnica.md:B04":
        "C: fronteras arquitectónicas entre planos y consumidores, no un test aislado",
    "docs/auditoria-pre-v1.md:B01":
        "C: alcance histórico de auditoría v1.0.0, no certificación actual",
    "docs/auditoria-pre-v1.md:B03":
        "C: obligación de cadena de integridad criptográfica de dependencias externas",
}

def diagnostic():
    """Snapshot completo, puramente sintético; nunca solicita ni fusiona PR."""
    return {
        "phase": "construccion", "kill_switch": "RUNNING",
        "head_sha": HEAD, "observed_head_sha": HEAD,
        "base_sha": BASE, "main_sha": BASE,
        "draft": False, "mergeable": True, "behind_by": 0,
        "required_checks": [
            {"name": "Validar", "conclusion": "success", "head_sha": HEAD}
        ],
        "gates": {
            name: {"conclusion": "success", "head_sha": HEAD}
            for name in ("acceptance", "coordination", "security")
        },
        "reviews": [{
            "author": "synthetic-qa", "state": "COMMENTED",
            "head_sha": HEAD, "trusted": True,
        }],
        "author": "synthetic-developer", "blocking_threads": 0,
        "paths": ["tests/synthetic_coverage.py"],
        "freeze_active": False, "human_gate_required": False,
        "inventory_complete": True, "api_remaining": 40,
        "api_minimum": 20,
        "observed_at": "2026-10-29T12:00:00Z",
        "expires_at": "2026-10-29T12:05:00Z",
        "now": "2026-10-29T12:02:00Z",
        "quality_evidence": [
            {"source": source, "head_sha": HEAD, "complete": True}
            for source in ("sonarcloud", "codeql", "coderabbit")
        ],
        "quality_findings": [],
        "hard_gates": {
            "spend": False, "real_data": False, "deploy": False,
            "release": False, "move_v1": False, "go_live": False,
            "destructive": False, "reservation_v3": True,
            "branch_protection": True,
        },
        "commit_count": 0, "review_rounds": 0,
        "quality_debt_cleared_for_live": False,
    }


@lru_cache(maxsize=1)
def fitness():
    protected = {
        key: {"value": 1.0, "direction": "higher"}
        for key in ("security", "privacy", "traceability", "reversibility", "authority")
    }
    baseline = {**protected, "reliability": {"value": 0.90, "direction": "higher"}}
    candidate = copy.deepcopy(baseline)
    candidate["reliability"]["value"] = 0.95
    return {
        "baseline": baseline, "candidate": candidate,
        "protected_dimensions": None,
        "result": compare_fitness(baseline=baseline, candidate=candidate),
    }


@lru_cache(maxsize=2)
def risk(level="low"):
    change_type = {"low": "docs", "high": "security"}[level]
    surface = {"low": "docs", "high": "auth"}[level]
    dna = discover_project_dna(
        paths=[
            "package.json", ".github/workflows/ci.yml", "vercel.json",
            "database/schema.sql", ".sentryclirc",
        ],
        manifests={"package.json": {
            "dependencies": {"fastify": "^5", "@sentry/node": "^9"}
        }},
        capabilities=["api", "auth"],
    )
    task = {
        "id": "synthetic-risk-" + level,
        "title": "synthetic " + level,
        "change_type": change_type,
        "surfaces": [surface],
        "signals": {
            "production": False, "destructive": False, "migration": False,
            "touches_auth": level == "high", "external_integration": False,
        },
    }
    return {
        "project_dna": dna, "task": task,
        "result": compile_risk(project_dna=dna, task=task),
    }


def promoted():
    engine = AutonomyEngine(
        CapabilityScope("synthetic-capability", "operational"),
        reason="fixture start", evidence=["fixture:init"],
    )
    original = engine.authority
    levels = [engine.current.level]
    for _ in AUTONOMY_LEVELS[1:]:
        engine.promote(
            fitness=fitness(), risk=risk(),
            reason="synthetic verified evidence",
            evidence=["fixture:fitness", "fixture:risk"],
        )
        levels.append(engine.current.level)
    return engine, original, tuple(levels)


class CoberturaFactory05Tests(unittest.TestCase):
    """Tres AC de ejecución real; no se simula el comportamiento a probar."""

    def test_contrato_principal(self):
        self.assertEqual(len(OFFLINE | WORLD.keys() | POLICY.keys()), 20)
        self.assertFalse((OFFLINE & WORLD.keys()) | (OFFLINE & POLICY.keys())
                         | (WORLD.keys() & POLICY.keys()))

        snapshot = diagnostic()
        unchanged = copy.deepcopy(snapshot)
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("network forbidden")):
            decision = evaluate(snapshot)
        self.assertEqual(decision.public(), {
            "eligible": True, "reason": "eligible_diagnostic_only",
        })
        self.assertEqual(snapshot, unchanged)

        cases = {}
        cases["docs/automerge-construccion.md:B01"] = (
            decision.eligible and snapshot == unchanged
        )
        invalid_ci = diagnostic()
        invalid_ci["required_checks"][0]["conclusion"] = "failure"
        invalid_sha = diagnostic()
        invalid_sha["observed_head_sha"] = "c" * 40
        severe = diagnostic()
        severe["quality_findings"] = [{
            "source": "sonarcloud", "severity": "critical",
            "category": "security", "on_new_code": True, "open": True,
        }]
        cases["docs/automerge-construccion.md:B02"] = all(
            not evaluate(item).eligible
            for item in (invalid_ci, invalid_sha, severe)
        )
        cases["docs/automerge-construccion.md:B03"] = all(
            not evaluate({**diagnostic(), **change}).eligible
            for change in (
                {"freeze_active": True},
                {"phase": "live"},
                {"hard_gates": {**diagnostic()["hard_gates"], "move_v1": True}},
                {"hard_gates": {**diagnostic()["hard_gates"], "deploy": True}},
            )
        )

        engine, original, levels = promoted()
        before_failure = engine.history
        fit, low = fitness()["result"], risk()["result"]
        cases["docs/autonomy-engine.md:L17-U1"] = (
            levels == AUTONOMY_LEVELS and len(before_failure) == len(levels)
        )
        confidence = fit["confidence"]
        cases["docs/autonomy-engine.md:L19-U1"] = (
            confidence["comparable"] == confidence["total"]
            and confidence["total"] > 0
            and not fit["missing_dimensions"]
            and not fit["protected_regressions"]
        )
        cases["docs/autonomy-engine.md:L20-U1"] = (
            fit["claim"] in ("equal", "improved")
        )
        cases["docs/autonomy-engine.md:L21-U1"] = (
            low["context_complete"] is True
            and not low["unknown_critical_signals"]
        )
        cases["docs/autonomy-engine.md:L22-U1"] = (
            all(len(x.evidence) >= 1 for x in engine.history)
        )

        high_engine = AutonomyEngine(
            "synthetic-high", reason="init", evidence=["fixture:init"],
        )
        for _ in range(3):
            high_engine.promote(
                fitness=fitness(), risk=risk(),
                reason="fixture", evidence=["fixture:valid"],
            )
        with self.assertRaisesRegex(AutonomyError, "riesgo high"):
            high_engine.promote(
                fitness=fitness(), risk=risk("high"),
                reason="attempt autonomous", evidence=["fixture:risk"],
            )
        cases["docs/autonomy-engine.md:L24-U1"] = (
            high_engine.current.level == "supervised"
        )
        minor = engine.record_failure(
            "minor", reason="synthetic minor", evidence=["fixture:incident"],
        )
        major = engine.record_failure(
            "major", reason="synthetic major", evidence=["fixture:incident"],
        )
        critical = engine.record_failure(
            "critical", reason="synthetic critical", evidence=["fixture:incident"],
        )
        cases["docs/autonomy-engine.md:L28-U1"] = (
            [minor.action, major.action, critical.action] ==
            ["downgrade:minor", "downgrade:major", "downgrade:critical"]
        )
        cases["docs/autonomy-engine.md:L31-U1"] = (
            major.previous_level == "supervised" and major.level == "propose"
        )
        cases["docs/autonomy-engine.md:L32-U1"] = critical.level == "observe"
        cases["docs/autonomy-engine.md:L34-U1"] = (
            len(before_failure) == 5 and len(engine.history) == 8
            and engine.history[:5] == before_failure
            and all(record.sequence == i
                    for i, record in enumerate(engine.history))
        )
        cases["docs/capability-authority.md:L16-U1"] = (
            original == engine.authority
            and engine.authority["external_permissions_added"] == []
            and all(x.authority_fingerprint == AUTHORITY_FINGERPRINT
                    for x in engine.history)
        )
        self.assertEqual(set(cases), OFFLINE)
        for identifier, observed in cases.items():
            with self.subTest(contract=identifier):
                self.assertIs(observed, True)

    def test_falla_cerrado(self):
        for change in (
            {"required_checks": []},
            {"inventory_complete": False},
            {"quality_evidence": []},
            {"hard_gates": {}},
            {"api_remaining": 0},
            {"observed_at": None},
            {"kill_switch": "PAUSED"},
            {"behind_by": 1},
        ):
            with self.subTest(diagnostic=change):
                self.assertFalse(evaluate({**diagnostic(), **change}).eligible)
        self.assertFalse(evaluate(None).eligible)
        self.assertFalse(evaluate({}).eligible)

        for invalid in ([], [""], "str", None):
            with self.subTest(empty_evidence=repr(invalid)):
                with self.assertRaises(AutonomyError):
                    AutonomyEngine("fixture", reason="init", evidence=invalid)
        for klass in ("money", "legal", "personal_data", "irreversible_delete"):
            with self.subTest(forbidden=klass):
                restricted = AutonomyEngine(
                    CapabilityScope("fixture", klass),
                    reason="init", evidence=["fixture:init"],
                )
                with self.assertRaisesRegex(AutonomyError, "prohibida"):
                    restricted.promote(
                        fitness=fitness(), risk=risk(),
                        reason="unauthorized", evidence=["fixture:invalid"],
                    )
                self.assertEqual(restricted.current.level, "observe")
                self.assertEqual(len(restricted.history), 1)

        for envelope in ("fitness", "risk"):
            with self.subTest(tampered=envelope):
                payload = copy.deepcopy(fitness() if envelope == "fitness" else risk())
                payload["result"]["fingerprint"] = "0" * 64
                arguments = {"fitness": fitness(), "risk": risk()}
                arguments[envelope] = payload
                engine = AutonomyEngine(
                    "fixture", reason="init", evidence=["fixture:init"],
                )
                with self.assertRaises(AutonomyError):
                    engine.promote(
                        **arguments, reason="tampered", evidence=["fixture"],
                    )
                self.assertEqual(len(engine.history), 1)

        engine, _, _ = promoted()
        with self.assertRaises(AutonomyError):
            engine.record_failure("unknown", reason="invalid",
                                  evidence=["fixture:incident"])
        with self.assertRaises(FrozenInstanceError):
            engine.history[0].level = "autonomous"
        self.assertEqual(engine.current.level, "autonomous")

    def test_sin_datos_reales(self):
        self.assertEqual(len(OFFLINE), 14)
        self.assertEqual(len(WORLD), 3)
        self.assertEqual(len(POLICY), 3)
        for identifier, reason in {**WORLD, **POLICY}.items():
            with self.subTest(clause=identifier):
                self.assertTrue(reason.startswith(("B:", "C:")))
                self.assertNotIn(identifier, OFFLINE)
        self.assertEqual(set(diagnostic()["hard_gates"]),
                         {"spend", "real_data", "deploy", "release", "move_v1",
                          "go_live", "destructive", "reservation_v3",
                          "branch_protection"})
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("network forbidden")):
            self.assertTrue(evaluate(diagnostic()).eligible)
            self.assertEqual(promoted()[0].current.level, "autonomous")
        self.assertEqual(diagnostic()["hard_gates"]["real_data"], False)
        self.assertEqual(diagnostic()["hard_gates"]["deploy"], False)


if __name__ == "__main__":
    unittest.main()
