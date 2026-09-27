#!/usr/bin/env python3
import unittest

from scripts.adaptive_replan import decide_replan


def base_snapshot():
    """Construye un snapshot fresh mínimo y válido para tests."""
    return {
        "version": 1,
        "source": "controlbot-runtime",
        "observed_at": "2026-09-27T23:30:00Z",
        "sessions": [
            {
                "session_id": "s1",
                "agent_id": "a1",
                "project": "factory",
                "repo": "pl0n3r/Factory",
                "work_item": "Factory#281",
                "issue_ref": "#281",
                "pr_ref": None,
                "state": "working",
                "assignment": "adaptive-replan",
                "claims": ["scripts/adaptive_replan.py"],
                "capabilities": ["python"],
                "heartbeat_at": "2026-09-27T23:29:30Z",
                "freshness": "fresh",
                "generation": 1,
                "attempt": 1,
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


def event(event_type, subject="factory", state="changed", evidence="issue:281"):
    """Construye un evento de replan válido para tests."""
    return {
        "event_type": event_type,
        "subject": subject,
        "state": state,
        "evidence_ref": evidence,
    }


class AdaptiveReplanTests(unittest.TestCase):
    def test_presence_join_leave_stale_and_recovery_trigger_deterministic_replan(self):
        """AC-01: cambios materiales de presencia/capacidad disparan replan."""
        for event_type in ("session_join", "session_leave", "presence_changed", "capacity_changed"):
            with self.subTest(event_type=event_type):
                decision = decide_replan(
                    base_snapshot(),
                    [event(event_type)],
                    active_work_safe=False,
                    active_work_ready=True,
                )
                self.assertEqual(decision.action, "replan")
                self.assertIn("presence_or_capacity_changed", decision.reasons)

        stale = base_snapshot()
        stale["sessions"][0]["freshness"] = "stale"
        decision = decide_replan(
            stale,
            [event("presence_changed", state="stale")],
            active_work_safe=True,
            active_work_ready=True,
        )
        self.assertEqual(decision.action, "fail_closed")

    def test_equivalent_events_are_coalesced_idempotently(self):
        """AC-02: duplicados equivalentes no crean dos unidades lógicas."""
        duplicate = event("capacity_changed")
        first = decide_replan(
            base_snapshot(),
            [duplicate, duplicate],
            active_work_safe=False,
            active_work_ready=True,
        )
        second = decide_replan(
            base_snapshot(),
            [duplicate],
            active_work_safe=False,
            active_work_ready=True,
        )
        self.assertEqual(first.coalesced_events, 1)
        self.assertEqual(first.event_fingerprint, second.event_fingerprint)
        self.assertEqual(first.action, second.action)

    def test_incident_replans_immediately_and_unknown_fails_closed(self):
        """AC-03: incident/health replanean; evidencia unknown falla cerrado."""
        incident = decide_replan(
            base_snapshot(),
            [event("incident_changed", state="open")],
            active_work_safe=True,
            active_work_ready=True,
        )
        self.assertEqual(incident.action, "replan")
        self.assertIn("immediate_operational_replan", incident.reasons)

        unknown = base_snapshot()
        unknown["capacity"]["freshness"] = "unknown"
        result = decide_replan(
            unknown,
            [event("health_changed")],
            active_work_safe=True,
            active_work_ready=True,
        )
        self.assertEqual(result.action, "fail_closed")

        for event_type in ("health_changed", "incident_changed"):
            for state in ("unknown", "stale"):
                with self.subTest(event_type=event_type, state=state):
                    untrusted = decide_replan(
                        base_snapshot(),
                        [event(event_type, state=state)],
                        active_work_safe=True,
                        active_work_ready=True,
                    )
                    self.assertEqual(untrusted.action, "fail_closed")
                    self.assertIn(
                        f"event_{state}:{event_type}:factory",
                        untrusted.reasons,
                    )

    def test_safe_active_work_preserves_continuity(self):
        """AC-04: una mejora marginal de capacidad no migra trabajo seguro."""
        decision = decide_replan(
            base_snapshot(),
            [event("capacity_changed", state="more_free")],
            active_work_safe=True,
            active_work_ready=True,
        )
        self.assertEqual(decision.action, "keep")
        self.assertIn("continuity_preserved", decision.reasons)

    def test_readiness_changes_produce_reproducible_ordered_causes(self):
        """AC-05: cambios de readiness generan causas estables y ordenadas."""
        events = [
            event("claim_changed", subject="scripts/a.py"),
            event("dependency_changed", subject="#280"),
            event("reservation_changed", subject="#281"),
        ]
        first = decide_replan(
            base_snapshot(),
            events,
            active_work_safe=True,
            active_work_ready=True,
        )
        second = decide_replan(
            base_snapshot(),
            list(reversed(events)),
            active_work_safe=True,
            active_work_ready=True,
        )
        self.assertEqual(first.action, "replan")
        self.assertEqual(first.reasons, second.reasons)
        self.assertEqual(first.event_fingerprint, second.event_fingerprint)

    def test_owner_decision_never_bypasses_readiness(self):
        """AC-06: decisión resuelta no convierte por sí sola trabajo no-ready."""
        blocked = decide_replan(
            base_snapshot(),
            [event("owner_decision_resolved")],
            active_work_safe=True,
            active_work_ready=True,
            owner_decision_target_ready=False,
        )
        self.assertEqual(blocked.action, "keep")
        self.assertIn("owner_decision_target_not_ready", blocked.reasons)

        ready = decide_replan(
            base_snapshot(),
            [event("owner_decision_resolved")],
            active_work_safe=False,
            active_work_ready=True,
            owner_decision_target_ready=True,
        )
        self.assertEqual(ready.action, "replan")

    def test_output_is_attributable_without_parallel_runtime_state(self):
        """AC-07: salida incluye fingerprints y no requiere estado persistido."""
        decision = decide_replan(
            base_snapshot(),
            [event("workitem_changed", subject="Factory#281")],
            active_work_safe=False,
            active_work_ready=False,
            readiness_changed=True,
        )
        self.assertEqual(len(decision.snapshot_fingerprint), 64)
        self.assertEqual(len(decision.event_fingerprint), 64)
        self.assertEqual(decision.coalesced_events, 1)
        self.assertEqual(decision.action, "replan")


if __name__ == "__main__":
    unittest.main()
