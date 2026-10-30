"""Factory #1795: tests offline del comportamiento del código existente.

A: aceptación checks-only / contrato / plantilla, Presence, Replan, Fencing,
Dispatcher V2 y AI Gateway/feedback. B/C quedan razonados en PR/Issue.
No consulta docs/matriz-cobertura*, producción ni servicios externos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import socket
import unittest
from unittest.mock import patch

from scripts.aceptacion_kit import (
    AcceptanceError, CheckPending, Criterion, parse_contract,
    validate_payload, verify_checks_only,
)
from scripts.adaptive_fencing import FencingContext, evaluate_fencing
from scripts.adaptive_replan import decide_replan
from scripts.dispatcher_v2 import (
    Candidate, adapt_candidates_for_adaptive, classify_readiness,
)
from scripts.presence_contract import classify_presence
from intelligence.ai_gateway import AIGatewayError, execute_capability, route_capability
from producto.feedback import validate_execution_feedback

ROOT = Path(__file__).resolve().parents[1]
FAKE_TIME = "2026-09-27T23:35:00Z"


def snapshot():
    return {
        "version": 1, "source": "controlbot-runtime", "observed_at": FAKE_TIME,
        "sessions": [{
            "session_id": "fixture-session", "agent_id": "fixture-agent",
            "project": "fixture", "repo": "pl0n3r/Factory",
            "work_item": "Factory#fixture", "issue_ref": "#fixture",
            "pr_ref": None, "state": "working", "assignment": "fixture",
            "claims": ["tests/fixture.py"], "capabilities": ["python"],
            "heartbeat_at": "2026-09-27T23:34:30Z", "freshness": "fresh",
            "generation": 4, "attempt": 2, "safe_point": True,
            "preemptibility": "preemptible",
        }],
        "capacity": {"known_slots": 2, "eligible_free_slots": 1,
                     "degraded_slots": 0, "freshness": "fresh"},
    }


def event(kind="capacity_changed", state="changed"):
    return {"event_type": kind, "subject": "fixture", "state": state,
            "evidence_ref": "fixture:local"}


def envelope(kind="capacity_changed", *, generation=4, attempt=2):
    return {"event": event(kind), "generation": generation, "attempt": attempt}


def fenced(*events, **overrides):
    values = {
        "current_generation": 4, "current_attempt": 2,
        "cooldown_seconds": 60, "elapsed_since_replan": 60,
        "active_work_safe": False, "active_work_ready": True,
        "safe_point": True, "preemptibility": "preemptible",
        "authority_valid": True, "readiness_valid": True,
    }
    values.update(overrides)
    return evaluate_fencing(snapshot(), list(events), FencingContext(**values))


def work():
    return {
        "work_id": "work-fixture", "origin_mode": "automatic",
        "origin_system": "factory", "group_id": "group-fixture",
        "work_type": "engineering", "requested_capabilities": ["coding"],
        "required_roles": ["ingenieria-software"], "authority_level": "standard",
        "producer_ref": "fixture:work", "priority_class": "high",
        "depends_on": [], "claims": ["tests/fixture.py"],
        "policy_ref": "fixture:policy", "evidence_refs": ["fixture:origin"],
        "idempotency_key": "fixture-idempotency", "venture_id": "fixture-venture",
        "project_id": "fixture-project", "repository_ref": "pl0n3r/Factory",
        "budget_ref": "fixture:budget",
    }


def policy(**changes):
    value = {"max_cost": 2.0, "data_classification": "internal",
             "min_quality": 70, "min_security": 80,
             "allowed_providers": ["manual", "codex"], "max_attempts": 2}
    value.update(changes)
    return value


def adapter(**changes):
    value = {
        "provider": "manual", "model": "fixture-model",
        "executor": "fixture-executor", "kind": "manual",
        "capabilities": ["coding"], "authority_levels": ["standard"],
        "data_level": "internal", "cost": 0.25, "quality": 85,
        "security": 90, "latency_ms": 20, "outcome": "success",
        "governed": True, "workspace": None,
    }
    value.update(changes)
    return value


def acceptance_body():
    marker = {"version": 1, "criteria": [{
        "id": "AC-01", "kind": "test",
        "target": "tests/test_cobertura_factory_04.py::CoberturaFactory04Tests::test_falla_cerrado",
    }]}
    return "\n".join([
        "### Contexto", "Fixture ejecutable.",
        "### Alcance", "Validar comportamiento.",
        "### Fuera de alcance", "No hay red.",
        "### Criterios de aceptación", "- [ ] [AC-01] Ejecutar un test local.",
        "### Contrato ejecutable",
        "<!-- factory-acceptance " + json.dumps(marker, separators=(",", ":")) + " -->",
    ])


class CoberturaFactory04Tests(unittest.TestCase):
    def test_contrato_principal(self):
        # aceptacion L61: el preflight solo mira checks, jamás ejecuta kind=test.
        body = acceptance_body()
        with patch("scripts.aceptacion_kit.run_named_test",
                   side_effect=AssertionError("kind=test ejecutado en preflight")):
            result = validate_payload(
                {"issue": {"body": body}, "checks": {"check_runs": []}},
                checks_only=True,
            )
        self.assertEqual(result, {"checks_only": True, "criteria": 1, "verified": []})
        self.assertEqual([row.id for row in parse_contract(body)], ["AC-01"])

        # aceptacion L67: Issue Form y check del contrato real, sin blank Issues.
        form = (ROOT / ".github/ISSUE_TEMPLATE/trabajo.yml").read_text(encoding="utf-8")
        config = (ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text(encoding="utf-8")
        for title in ("Contexto", "Alcance", "Fuera de alcance",
                      "Criterios de aceptación", "Contrato ejecutable"):
            self.assertIn("label: " + title, form)
        self.assertGreaterEqual(form.count("required: true"), 5)
        self.assertIn("blank_issues_enabled: false", config)

        # aceptacion L8: el green genérico no suplanta evidencia de un criterio.
        self.assertEqual(verify_checks_only([], {"check_runs": []}), [])
        with self.assertRaises((CheckPending, AcceptanceError)):
            verify_checks_only([Criterion("AC-02", "check", "Specific E2E fixture")],
                               {"check_runs": []})

        # adaptive L12: heartbeat/freshness explícitos y slots frescos.
        presence = classify_presence(snapshot())
        self.assertEqual(presence.active_sessions, 1)
        self.assertEqual(presence.eligible_free_slots, 1)
        self.assertIn("idle_capacity", presence.classifications)

        # adaptive L33: keep/replan puros; readiness cambiante fuerza replan.
        self.assertEqual(decide_replan(snapshot(), [], active_work_safe=True,
            active_work_ready=True).action, "keep")
        changed = decide_replan(snapshot(), [event("workitem_changed")],
            active_work_safe=False, active_work_ready=True)
        self.assertEqual((changed.action, changed.coalesced_events), ("replan", 1))

        # adaptive L41: generation/attempt exactos antes de replan.
        self.assertEqual(fenced(envelope("workitem_changed")).action, "replan")
        self.assertEqual(fenced(envelope("workitem_changed", generation=3)).action, "fail_closed")
        self.assertEqual(fenced(envelope("workitem_changed", attempt=3)).action, "fail_closed")

        # adaptive L47: cooldown retiene replan no crítico, no health válido.
        self.assertEqual(fenced(envelope(), elapsed_since_replan=0).action, "keep")
        self.assertEqual(fenced(envelope("health_changed"),
            elapsed_since_replan=0).action, "replan")

        # adaptive L49: pausa solo preemptible + safe_point.
        self.assertTrue(fenced(envelope("workitem_changed")).pause_allowed)
        self.assertFalse(fenced(envelope("workitem_changed"),
            safe_point=False).pause_allowed)
        self.assertFalse(fenced(envelope("workitem_changed"),
            preemptibility="non_preemptible").pause_allowed)

        # adaptive L63/L67: señales se traducen a readiness/metadata de Dispatcher.
        candidate = Candidate(key="Factory#fixture",
                              metadata={"repository_ref": "pl0n3r/Factory"})
        good = adapt_candidates_for_adaptive([candidate], presence=presence,
            fencing=fenced(envelope("workitem_changed")), replan_action="replan")[0]
        self.assertEqual(good.metadata["adaptive"]["generation"], 4)
        self.assertTrue(classify_readiness(good).ready)
        unknown = snapshot()
        unknown["capacity"]["freshness"] = "unknown"
        bad = adapt_candidates_for_adaptive([candidate],
            presence=classify_presence(unknown),
            fencing=fenced(envelope("workitem_changed", generation=3)),
            replan_action="fail_closed")[0]
        self.assertFalse(classify_readiness(bad).ready)
        self.assertIn("adaptive_presence_unknown", bad.external_readiness_reasons)
        self.assertIn("adaptive_fencing_invalid", bad.external_readiness_reasons)

        # AI Gateway L13: provider/model/executor/costo/evidencia + feedback validado.
        result = execute_capability(work(), capability="coding", policy=policy(),
            adapters=[adapter()], observed_at=FAKE_TIME)
        self.assertEqual((result["provider"], result["model"], result["executor"]),
            ("manual", "fixture-model", "fixture-executor"))
        self.assertEqual((result["venture_id"], result["project_id"]),
            ("fixture-venture", "fixture-project"))
        self.assertEqual(result["actual_cost"], 0.25)
        self.assertTrue(result["evidence_refs"])
        feedback = validate_execution_feedback(result["feedback"], work(),
            now=datetime(2026, 9, 27, 23, 36, tzinfo=timezone.utc))
        self.assertEqual(feedback["status"], "success")

        # AI Gateway L15: un adapter Codex requiere gobierno y workspace exacto.
        codex = adapter(provider="codex", kind="codex", executor="fixture-codex",
                        workspace="pl0n3r/Factory")
        routed = route_capability(work(), capability="coding", policy=policy(),
                                  adapters=[codex])
        self.assertEqual(routed["eligible"][0].kind, "codex")

    def test_falla_cerrado(self):
        # Contrato ausente y check específico sin prueba no generan éxito.
        with self.assertRaises(AcceptanceError):
            parse_contract("### Contexto\nSin contrato.")
        with self.assertRaises((CheckPending, AcceptanceError)):
            verify_checks_only([Criterion("AC-01", "check", "Missing fixture")],
                               {"check_runs": []})

        # Presence stale/unknown elimina capacidad atribuible.
        stale = snapshot()
        stale["sessions"][0]["freshness"] = "stale"
        self.assertIn("unknown", classify_presence(stale).classifications)
        self.assertEqual(classify_presence(stale).eligible_free_slots, 0)
        unknown = snapshot()
        unknown["capacity"]["freshness"] = "unknown"
        self.assertEqual(classify_presence(unknown).classifications, ("unknown",))
        self.assertEqual(classify_presence(unknown).eligible_free_slots, 0)

        # Evento UNKNOWN, fence inválido y autoridad ausente.
        self.assertEqual(decide_replan(snapshot(), [event(state="unknown")],
            active_work_safe=True, active_work_ready=True).action, "fail_closed")
        self.assertFalse(fenced(envelope(generation=99)).pause_allowed)
        self.assertEqual(fenced(envelope("workitem_changed"),
            authority_valid=None).action, "fail_closed")

        # Gate de costo, permisos, governance y material sensible.
        with self.assertRaisesRegex(AIGatewayError, "budget-blocked"):
            route_capability(work(), capability="coding", policy=policy(max_cost=0.01),
                             adapters=[adapter()])
        with self.assertRaisesRegex(AIGatewayError, "authority-not-allowed"):
            route_capability({**work(), "authority_level": "production-write"},
                             capability="coding", policy=policy(), adapters=[adapter()])
        with self.assertRaisesRegex(AIGatewayError, "codex-outside-factory"):
            route_capability(work(), capability="coding", policy=policy(),
                adapters=[adapter(provider="codex", kind="codex", governed=False,
                                  workspace="pl0n3r/Factory")])
        with self.assertRaisesRegex(AIGatewayError, "secret-field-not-allowed"):
            route_capability({**work(), "api_key": "fixture-not-a-secret"},
                             capability="coding", policy=policy(), adapters=[adapter()])

    def test_sin_datos_reales(self):
        # Evidencia determinista; no se necesita red, proveedor ni PII.
        with patch("socket.create_connection",
                   side_effect=AssertionError("red prohibida")):
            result = execute_capability(work(), capability="coding",
                policy=policy(), adapters=[adapter()], observed_at=FAKE_TIME)
            self.assertEqual(result["status"], "success")
            self.assertEqual(classify_presence(snapshot()).active_sessions, 1)
            self.assertEqual(fenced().action, "keep")
        self.assertEqual(result["kind"], "manual")
        self.assertFalse(any(k in result for k in ("password", "token", "api_key")))


if __name__ == "__main__":
    unittest.main()
