#!/usr/bin/env python3
import unittest

from scripts.adaptive_fencing import evaluate_fencing


def base_snapshot():
    """Construye un PresenceSnapshot fresh y determinista."""
    return {
        "version": 1,
        "source": "controlbot-runtime",
        "observed_at": "2026-09-27T23:35:00Z",
        "sessions": [
            {
                "session_id": "s1",
                "agent_id": "a1",
                "project": "factory",
                "repo": "pl0n3r/Factory",
                "work_item": "Factory#282",
                "issue_ref": "#282",
                "pr_ref": None,
                "state": "working",
                "assignment": "adaptive-fencing",
                "claims": ["scripts/adaptive_fencing.py"],
                "capabilities": ["python"],
                "heartbeat_at": "2026-09-27T23:34:30Z",
                "freshness": "fresh",
                "generation": 4,
                "attempt": 2,
                "safe_point": True,
                "preemptibility": "preemptible",
            }
        ],
        "capacity": {
            "known_slots": 2,
            "eligible_free_slots": 1,
            "degraded_slots": 0,
            "freshness": "fresh",
        },
    }


def event(event_type="capacity_changed", state="changed", subject="factory"):
    """Construye un evento válido del contrato #281."""
    return {
        "event_type": event_type,
        "subject": subject,
        "state": state,
        "evidence_ref": "issue:282",
    }


def envelope(
    event_payload=None,
    *,
    generation=4,
    attempt=2,
):
    """Envuelve un evento con la identidad fenced del intento."""
    return {
        "event": event_payload or event(),
        "generation": generation,
        "attempt": attempt,
    }


def evaluate(events, **overrides):
    """Evalúa fencing con un contexto seguro por defecto."""
    kwargs = {
        "current_generation": 4,
        "current_attempt": 2,
        "cooldown_seconds": 60,
        "elapsed_since_replan": 60,
        "active_work_safe": False,
        "active_work_ready": True,
        "safe_point": True,
        "preemptibility": "preemptible",
        "authority_valid": True,
        "readiness_valid": True,
    }
    kwargs.update(overrides)
    return evaluate_fencing(base_snapshot(), events, **kwargs)


class AdaptiveFencingTests(unittest.TestCase):
    def test_stale_generation_fails_closed(self):
        """AC-01: generaciones anteriores no alteran el intento vigente."""
        decision = evaluate([envelope(generation=3)])

        self.assertEqual(decision.action, "fail_closed")
        self.assertFalse(decision.pause_allowed)
        self.assertEqual(decision.generation, 4)
        self.assertEqual(decision.attempt, 2)
        self.assertIn("stale_generation:3<4", decision.reasons)

    def test_equivalent_events_share_fingerprint_and_do_not_duplicate(self):
        """AC-02: envelopes equivalentes coalescen a una unidad lógica."""
        duplicate = envelope()
        first = evaluate([duplicate, duplicate])
        second = evaluate([duplicate])

        self.assertEqual(first.coalesced_events, 1)
        self.assertEqual(first.event_fingerprint, second.event_fingerprint)
        self.assertEqual(first.action, second.action)

    def test_noncritical_rebalance_respects_cooldown(self):
        """AC-03: cooldown retiene un rebalance no crítico antes de vencer."""
        decision = evaluate(
            [envelope(event("capacity_changed", state="more_free"))],
            cooldown_seconds=60,
            elapsed_since_replan=10,
        )

        self.assertEqual(decision.action, "keep")
        self.assertFalse(decision.pause_allowed)
        self.assertIn("cooldown_active:50", decision.reasons)

    def test_valid_health_or_incident_can_bypass_cooldown(self):
        """AC-04: health/incident válido bypass cooldown, no authority/readiness."""
        for event_type in ("health_changed", "incident_changed"):
            with self.subTest(event_type=event_type):
                decision = evaluate(
                    [envelope(event(event_type, state="degraded"))],
                    cooldown_seconds=300,
                    elapsed_since_replan=0,
                )
                self.assertEqual(decision.action, "replan")
                self.assertNotIn("cooldown_active:300", decision.reasons)

        denied = evaluate(
            [envelope(event("health_changed", state="degraded"))],
            cooldown_seconds=300,
            elapsed_since_replan=0,
            authority_valid=False,
        )
        self.assertEqual(denied.action, "fail_closed")
        self.assertIn("authority_invalid", denied.reasons)

    def test_safe_active_work_preserves_continuity(self):
        """AC-05: mejora marginal no migra trabajo activo seguro."""
        decision = evaluate(
            [envelope(event("capacity_changed", state="more_free"))],
            active_work_safe=True,
            active_work_ready=True,
        )

        self.assertEqual(decision.action, "keep")
        self.assertFalse(decision.pause_allowed)
        self.assertIn("continuity_preserved", decision.reasons)

    def test_non_preemptible_or_unsafe_point_never_auto_pauses(self):
        """AC-06: sin preemptibility o safe point nunca se habilita pausa."""
        cases = (
            (True, "non_preemptible", "pause_blocked_non_preemptible"),
            (False, "preemptible", "pause_blocked_unsafe_point"),
        )
        for safe_point, preemptibility, reason in cases:
            with self.subTest(safe_point=safe_point, preemptibility=preemptibility):
                decision = evaluate(
                    [envelope(event("incident_changed", state="open"))],
                    safe_point=safe_point,
                    preemptibility=preemptibility,
                )
                self.assertEqual(decision.action, "replan")
                self.assertFalse(decision.pause_allowed)
                self.assertIn(reason, decision.reasons)

    def test_fencing_output_is_deterministic_and_attributable(self):
        """AC-07: salida preserva generation/fingerprints/reasons estables."""
        events = [
            envelope(event("dependency_changed", subject="#281")),
            envelope(event("claim_changed", subject="scripts/a.py")),
        ]
        first = evaluate(events, readiness_changed=True)
        second = evaluate(list(reversed(events)), readiness_changed=True)

        self.assertEqual(first, second)
        self.assertEqual(first.generation, 4)
        self.assertEqual(first.attempt, 2)
        self.assertEqual(len(first.snapshot_fingerprint), 64)
        self.assertEqual(len(first.event_fingerprint), 64)
        self.assertEqual(first.reasons, tuple(sorted(first.reasons)))


if __name__ == "__main__":
    unittest.main()
