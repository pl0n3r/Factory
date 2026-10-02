#!/usr/bin/env python3
"""Regresiones del Tramo 4C: watchdog, STATE freshness y resumen diario."""
from pathlib import Path
import copy
import unittest

from scripts.unattended_global_idle import CANONICAL_REPOSITORIES, evaluate_global_idle_snapshot
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import evaluate_unattended_watchdog


def guard(action="ALLOW", pause=False):
    return GuardDecision(action, "unchanged", pause, ("guard-test",), "a" * 64)


def presence():
    return {
        "version": 1,
        "source": "controlbot-runtime",
        "observed_at": "2026-10-02T01:00:00Z",
        "sessions": [
            {
                "session_id": "session-1",
                "agent_id": "agent-1",
                "project": "factory",
                "repo": "pl0n3r/Factory",
                "work_item": "Factory#745",
                "issue_ref": "#745",
                "pr_ref": None,
                "state": "working",
                "assignment": "watchdog",
                "claims": ["scripts/unattended_watchdog.py"],
                "capabilities": ["python"],
                "heartbeat_at": "2026-10-02T00:59:30Z",
                "freshness": "fresh",
                "generation": 1,
                "attempt": 1,
                "safe_point": True,
                "preemptibility": "preemptible",
            }
        ],
        "capacity": {
            "known_slots": 1,
            "eligible_free_slots": 0,
            "degraded_slots": 0,
            "freshness": "fresh",
        },
    }


def state(**changes):
    value = {
        "work_identity": "pl0n3r/Factory#745",
        "repository": "pl0n3r/Factory",
        "branch": "trabajo/issue-745",
        "head_sha": "d" * 40,
        "reservation_id": "reservation-745",
        "risk": "medium",
        "severity": "S3",
        "evidence": ["Factory#745", "main@da3d522"],
        "last_state": "implementing",
        "next_action": "run acceptance tests",
        "blockers": [],
        "updated_at": "2026-10-02T00:58:00Z",
    }
    value.update(changes)
    return value


def config(**changes):
    value = {
        "ready_without_dispatch_minutes": 10,
        "reservation_stale_minutes": 15,
        "state_stale_minutes": 20,
    }
    value.update(changes)
    return value


def evidence(**changes):
    value = {
        "now": "2026-10-02T01:00:00Z",
        "presence": presence(),
        "work_ready": False,
        "ready_since": None,
        "next_dispatch_planned": True,
        "reservation": {
            "active": True,
            "work_identity": "pl0n3r/Factory#745",
            "updated_at": "2026-10-02T00:58:30Z",
            "freshness": "fresh",
        },
        "state": state(),
        "incidents": [],
        "already_alerted_fingerprints": [],
        "active_fronts": ["Factory#745"],
        "human_gates": [],
        "integrated": ["Factory#752"],
        "reverted": [],
        "next_actions": ["finish 4C"],
    }
    value.update(changes)
    return value


def proven_global_idle():
    return evaluate_global_idle_snapshot(
        {
            "version": 1,
            "repositories": [
                {
                    "repository": repository,
                    "freshness": "fresh",
                    "ready": False,
                    "reserved": False,
                    "reviewing": False,
                    "ambiguous": False,
                    "source_ref": f"github:{repository}#inventory",
                }
                for repository in CANONICAL_REPOSITORIES
            ],
        }
    )


def idle_presence():
    return {
        "version": 1,
        "source": "factory-github-inventory",
        "observed_at": "2026-10-02T01:00:00Z",
        "sessions": [],
        "capacity": {
            "known_slots": 0,
            "eligible_free_slots": 0,
            "degraded_slots": 0,
            "freshness": "unknown",
        },
    }


def idle_state():
    return state(
        work_identity="pl0n3r/Factory#idle",
        branch=None,
        head_sha=None,
        reservation_id=None,
        risk="low",
        severity="S3",
        evidence=["github_inventory:no_active_work_items"],
        last_state="idle",
        next_action="re-run dispatcher when canonical work appears",
        blockers=[],
        updated_at="2026-10-02T01:00:00Z",
    )


class UnattendedWatchdogTests(unittest.TestCase):
    def test_proven_global_idle_does_not_emit_presence_insufficient_or_block_idle_by_itself(self):
        result = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                presence=idle_presence(),
                reservation=None,
                state=idle_state(),
                active_fronts=[],
                next_dispatch_planned=False,
                global_idle=proven_global_idle(),
            ),
        )
        self.assertEqual(result.action, "ALLOW")
        self.assertNotIn(
            "presence_insufficient",
            {item.code for item in result.incidents},
        )
        self.assertFalse(result.daily_summary.incidents)

    def test_idle_unknown_capacity_does_not_emit_presence_incident_without_capacity_demand(self):
        result = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                presence=idle_presence(),
                reservation=None,
                state=idle_state(),
                active_fronts=[],
                next_dispatch_planned=False,
                global_idle=proven_global_idle(),
            ),
        )
        self.assertEqual(result.action, "ALLOW")
        self.assertNotIn(
            "presence_insufficient",
            {item.code for item in result.incidents},
        )
        self.assertFalse(any(item.severity == "UNKNOWN" for item in result.incidents))

    def test_unknown_presence_still_blocks_when_global_idle_is_unproven_or_work_is_active(self):
        base = dict(
            presence=idle_presence(),
            reservation=None,
            state=idle_state(),
            active_fronts=[],
            next_dispatch_planned=False,
        )
        unproven = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(**base),
        )
        self.assertEqual(unproven.action, "BLOCKED")
        self.assertIn(
            "presence_insufficient",
            {item.code for item in unproven.incidents},
        )

        active = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                **{
                    **base,
                    "active_fronts": ["pl0n3r/Factory#823"],
                    "global_idle": proven_global_idle(),
                }
            ),
        )
        self.assertEqual(active.action, "BLOCKED")
        self.assertIn(
            "presence_insufficient",
            {item.code for item in active.incidents},
        )

    def test_unknown_presence_still_blocks_when_ready_reserved_active_or_non_idle(self):
        proof = proven_global_idle()
        base = {
            "presence": idle_presence(),
            "reservation": None,
            "state": idle_state(),
            "active_fronts": [],
            "next_dispatch_planned": False,
            "global_idle": proof,
        }
        cases = {
            "ready": {
                "work_ready": True,
                "ready_since": "2026-10-02T00:59:00Z",
            },
            "reserved": {
                "reservation": {
                    "active": True,
                    "work_identity": "pl0n3r/Factory#824",
                    "updated_at": "2026-10-02T00:59:00Z",
                    "freshness": "fresh",
                },
            },
            "active": {"active_fronts": ["pl0n3r/Factory#824"]},
            "non_idle": {"state": idle_state() | {"last_state": "reviewing"}},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                result = evaluate_unattended_watchdog(
                    guard(),
                    config(),
                    evidence(**{**base, **changes}),
                )
                self.assertEqual(result.action, "BLOCKED")
                self.assertIn(
                    "presence_insufficient",
                    {item.code for item in result.incidents},
                )

    def test_global_idle_exception_requires_every_safety_condition(self):
        forged = {
            "version": 1,
            "idle_global": True,
            "reasons": [],
            "provenance": [f"fake/repo-{index}:source:fresh" for index in range(7)],
        }
        invalid = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                presence=idle_presence(),
                reservation=None,
                state=idle_state(),
                active_fronts=[],
                next_dispatch_planned=False,
                global_idle=forged,
            ),
        )
        self.assertEqual(invalid.action, "BLOCKED")
        self.assertIn("invalid_global_idle", invalid.daily_summary.blockers)

        proof = proven_global_idle()
        reported = {
            "incident_id": "idle-check",
            "severity": "S3",
            "source": "health",
            "updated_at": "2026-10-02T00:59:00Z",
            "freshness": "fresh",
        }
        nonempty_presence = idle_presence()
        nonempty_presence["capacity"]["known_slots"] = 1

        cases = {
            "work_ready": {
                "work_ready": True,
                "ready_since": "2026-10-02T00:59:00Z",
            },
            "next_dispatch_planned": {"next_dispatch_planned": True},
            "reservation": {
                "reservation": {
                    "active": False,
                    "work_identity": "pl0n3r/Factory#idle",
                    "updated_at": "2026-10-02T00:59:00Z",
                    "freshness": "fresh",
                }
            },
            "active_front": {"active_fronts": ["pl0n3r/Factory#823"]},
            "reported_incident": {"incidents": [reported]},
            "non_idle_identity": {
                "state": idle_state() | {"work_identity": "pl0n3r/Factory#823"}
            },
            "non_idle_state": {
                "state": idle_state() | {"last_state": "reviewing"}
            },
            "stale_state": {
                "state": idle_state() | {"updated_at": "2026-10-02T00:30:00Z"}
            },
            "state_blocker": {
                "state": idle_state() | {"blockers": ["blocked"]}
            },
            "nonempty_presence": {"presence": nonempty_presence},
        }
        base = {
            "presence": idle_presence(),
            "reservation": None,
            "state": idle_state(),
            "active_fronts": [],
            "next_dispatch_planned": False,
            "global_idle": proof,
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                payload = {**base, **changes}
                result = evaluate_unattended_watchdog(
                    guard(),
                    config(),
                    evidence(**payload),
                )
                self.assertEqual(result.action, "BLOCKED")
                self.assertIn(
                    "presence_insufficient",
                    {item.code for item in result.incidents},
                )

    def test_presence_unknown_stale_or_missing_heartbeat_never_counts_as_healthy_progress(self):
        cases = []
        stale = presence()
        stale["sessions"][0]["freshness"] = "stale"
        cases.append(stale)

        unknown = presence()
        unknown["sessions"][0]["freshness"] = "unknown"
        cases.append(unknown)

        missing = presence()
        missing["sessions"][0]["heartbeat_at"] = None
        cases.append(missing)

        capacity_unknown = presence()
        capacity_unknown["capacity"]["freshness"] = "unknown"
        cases.append(capacity_unknown)

        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                result = evaluate_unattended_watchdog(
                    guard(), config(), evidence(presence=snapshot)
                )
                self.assertEqual(result.action, "BLOCKED")
                self.assertIn(
                    "UNKNOWN:presence_insufficient",
                    result.daily_summary.incidents,
                )

        malformed = presence()
        malformed[7] = "invalid-key"
        malformed_result = evaluate_unattended_watchdog(
            guard(), config(), evidence(presence=malformed)
        )
        self.assertEqual(malformed_result.action, "BLOCKED")
        self.assertIn("invalid_presence", malformed_result.daily_summary.blockers)

    def test_ready_without_dispatch_and_stale_reservation_require_explicit_thresholds(self):
        invalid = config()
        del invalid["ready_without_dispatch_minutes"]
        blocked = evaluate_unattended_watchdog(guard(), invalid, evidence())
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertIn("invalid_config_shape", blocked.daily_summary.blockers)

        result = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                work_ready=True,
                ready_since="2026-10-02T00:40:00Z",
                next_dispatch_planned=False,
                reservation={
                    "active": True,
                    "work_identity": "pl0n3r/Factory#745",
                    "updated_at": "2026-10-02T00:30:00Z",
                    "freshness": "stale",
                },
            ),
        )
        codes = {item.code for item in result.incidents}
        self.assertIn("ready_without_dispatch", codes)
        self.assertIn("reservation_without_progress", codes)
        self.assertEqual(result.action, "BLOCKED")
        self.assertEqual(result.authority, "unchanged")

        inconsistent = evaluate_unattended_watchdog(
            guard("ALLOW", True),
            config(),
            evidence(
                work_ready=True,
                ready_since="2026-10-02T00:40:00Z",
                next_dispatch_planned=False,
                reservation=None,
            ),
        )
        self.assertEqual(
            (inconsistent.action, inconsistent.authority),
            ("BLOCKED", "unchanged"),
        )
        self.assertIn(
            "invalid_guard_pause_contract",
            inconsistent.daily_summary.blockers,
        )

    def test_incident_fingerprint_is_idempotent_and_changes_with_material_evidence(self):
        payload = evidence(
            work_ready=True,
            ready_since="2026-10-02T00:40:00Z",
            next_dispatch_planned=False,
        )
        first = evaluate_unattended_watchdog(guard(), config(), payload)
        incident = next(item for item in first.incidents if item.code == "ready_without_dispatch")
        self.assertFalse(incident.repeated)
        self.assertIn(incident.fingerprint, first.new_alert_fingerprints)

        second_payload = copy.deepcopy(payload)
        second_payload["already_alerted_fingerprints"] = [incident.fingerprint]
        second = evaluate_unattended_watchdog(guard(), config(), second_payload)
        repeated = next(item for item in second.incidents if item.code == "ready_without_dispatch")
        self.assertTrue(repeated.repeated)
        self.assertNotIn(repeated.fingerprint, second.new_alert_fingerprints)

        changed = copy.deepcopy(payload)
        changed["ready_since"] = "2026-10-02T00:35:00Z"
        third = evaluate_unattended_watchdog(guard(), config(), changed)
        changed_incident = next(item for item in third.incidents if item.code == "ready_without_dispatch")
        self.assertNotEqual(incident.fingerprint, changed_incident.fingerprint)

        degraded_presence = presence()
        degraded_presence["sessions"][0]["freshness"] = "stale"
        first_presence = evaluate_unattended_watchdog(
            guard(), config(), evidence(presence=degraded_presence)
        )
        presence_incident = next(
            item for item in first_presence.incidents
            if item.code == "presence_insufficient"
        )

        same_degradation = copy.deepcopy(degraded_presence)
        same_degradation["observed_at"] = "2026-10-02T01:05:00Z"
        repeated_presence = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                presence=same_degradation,
                already_alerted_fingerprints=[presence_incident.fingerprint],
            ),
        )
        repeated_incident = next(
            item for item in repeated_presence.incidents
            if item.code == "presence_insufficient"
        )
        self.assertEqual(presence_incident.fingerprint, repeated_incident.fingerprint)
        self.assertTrue(repeated_incident.repeated)

        materially_changed = copy.deepcopy(same_degradation)
        materially_changed["sessions"][0]["freshness"] = "unknown"
        changed_presence = evaluate_unattended_watchdog(
            guard(), config(), evidence(presence=materially_changed)
        )
        changed_presence_incident = next(
            item for item in changed_presence.incidents
            if item.code == "presence_insufficient"
        )
        self.assertNotEqual(
            presence_incident.fingerprint,
            changed_presence_incident.fingerprint,
        )

        unknown_presence = presence()
        unknown_presence["sessions"][0]["freshness"] = "unknown"
        presence_first = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                now="2026-10-02T01:05:00Z",
                presence=unknown_presence,
                reservation=None,
            ),
        )
        presence_incident = next(
            item for item in presence_first.incidents if item.code == "presence_insufficient"
        )

        later_presence = copy.deepcopy(unknown_presence)
        later_presence["observed_at"] = "2026-10-02T01:04:00Z"
        presence_second = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                now="2026-10-02T01:05:00Z",
                presence=later_presence,
                reservation=None,
                already_alerted_fingerprints=[presence_incident.fingerprint],
            ),
        )
        repeated_presence = next(
            item for item in presence_second.incidents if item.code == "presence_insufficient"
        )
        self.assertEqual(presence_incident.fingerprint, repeated_presence.fingerprint)
        self.assertTrue(repeated_presence.repeated)

        changed_presence = copy.deepcopy(later_presence)
        changed_presence["sessions"][0]["freshness"] = "stale"
        presence_third = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                now="2026-10-02T01:05:00Z",
                presence=changed_presence,
                reservation=None,
            ),
        )
        materially_changed = next(
            item for item in presence_third.incidents if item.code == "presence_insufficient"
        )
        self.assertNotEqual(presence_incident.fingerprint, materially_changed.fingerprint)

    def test_state_contract_is_closed_freshness_aware_and_secret_free(self):
        minimal = state()
        for optional in ("branch", "head_sha", "reservation_id"):
            minimal.pop(optional)
        accepted = evaluate_unattended_watchdog(
            guard(), config(), evidence(state=minimal)
        )
        self.assertNotEqual(accepted.action, "BLOCKED")

        stale = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(state=state(updated_at="2026-10-02T00:30:00Z")),
        )
        self.assertIn("S3:state_stale", stale.daily_summary.incidents)

        invalid_states = []
        unknown = state()
        unknown["surprise"] = "x"
        invalid_states.append(unknown)

        future = state(updated_at="2026-10-02T01:01:00Z")
        invalid_states.append(future)

        secret = state()
        secret["evidence"] = ["token=TOP-SECRET"]
        invalid_states.append(secret)

        pii = state()
        pii["blockers"] = ["contact user@example.com"]
        invalid_states.append(pii)

        for payload in invalid_states:
            with self.subTest(payload=payload):
                result = evaluate_unattended_watchdog(
                    guard(), config(), evidence(state=payload)
                )
                self.assertEqual(result.action, "BLOCKED")
                self.assertTrue(any(item.severity == "UNKNOWN" for item in result.incidents))

        unknown_risk = evaluate_unattended_watchdog(
            guard(), config(), evidence(state=state(risk="UNKNOWN"))
        )
        self.assertEqual(unknown_risk.action, "BLOCKED")
        self.assertIn("UNKNOWN:state_risk_unknown", unknown_risk.daily_summary.incidents)

        minimal_state = state()
        for optional in ("branch", "head_sha", "reservation_id"):
            del minimal_state[optional]
        minimal = evaluate_unattended_watchdog(
            guard(), config(), evidence(state=minimal_state, reservation=None)
        )
        self.assertEqual((minimal.action, minimal.authority), ("ALLOW", "unchanged"))
        self.assertEqual(minimal.daily_summary.state_freshness, "fresh")

    def test_guard_decision_is_consumed_without_recalculation_or_authority_expansion(self):
        healthy = evidence(reservation=None)
        allowed = evaluate_unattended_watchdog(guard("ALLOW", False), config(), healthy)
        self.assertEqual((allowed.action, allowed.authority), ("ALLOW", "unchanged"))

        paused = evaluate_unattended_watchdog(guard("PAUSE", True), config(), healthy)
        self.assertEqual((paused.action, paused.authority), ("PAUSE", "unchanged"))

        blocked = evaluate_unattended_watchdog(guard("BLOCKED", False), config(), healthy)
        self.assertEqual((blocked.action, blocked.authority), ("BLOCKED", "unchanged"))

        incident_payload = evidence(
            reservation=None,
            work_ready=True,
            ready_since="2026-10-02T00:40:00Z",
            next_dispatch_planned=False,
        )
        no_pause_authority = evaluate_unattended_watchdog(
            guard("ALLOW", False), config(), incident_payload
        )
        self.assertEqual(
            (no_pause_authority.action, no_pause_authority.authority),
            ("BLOCKED", "unchanged"),
        )

    def test_invalid_watchdog_inputs_fail_closed_without_side_effects(self):
        invalid_guard = evaluate_unattended_watchdog(object(), config(), evidence())
        self.assertEqual((invalid_guard.action, invalid_guard.authority), ("BLOCKED", "unchanged"))
        self.assertIn("invalid_guard_decision", invalid_guard.daily_summary.blockers)

        bad_authority = GuardDecision("ALLOW", "expanded", False, (), "b" * 64)
        invalid_contract = evaluate_unattended_watchdog(bad_authority, config(), evidence())
        self.assertEqual(invalid_contract.action, "BLOCKED")
        self.assertIn("invalid_guard_contract", invalid_contract.daily_summary.blockers)

        bad_pause = GuardDecision("ALLOW", "unchanged", True, ("test",), "b" * 64)
        invalid_pause = evaluate_unattended_watchdog(bad_pause, config(), evidence())
        self.assertEqual(invalid_pause.action, "BLOCKED")
        self.assertIn("invalid_guard_pause_contract", invalid_pause.daily_summary.blockers)

        bad_evidence = GuardDecision("ALLOW", "unchanged", False, (), "not-a-fingerprint")
        invalid_guard_evidence = evaluate_unattended_watchdog(
            bad_evidence, config(), evidence()
        )
        self.assertEqual(invalid_guard_evidence.action, "BLOCKED")
        self.assertIn(
            "invalid_guard_evidence_contract",
            invalid_guard_evidence.daily_summary.blockers,
        )

        invalid_evidence = evaluate_unattended_watchdog(guard(), config(), [])
        self.assertEqual(invalid_evidence.action, "BLOCKED")
        self.assertIn("invalid_evidence", invalid_evidence.daily_summary.blockers)

        for bad_config in (
            config(ready_without_dispatch_minutes=0),
            config(reservation_stale_minutes=True),
        ):
            with self.subTest(config=bad_config):
                result = evaluate_unattended_watchdog(guard(), bad_config, evidence())
                self.assertEqual(result.action, "BLOCKED")

        mismatch = evidence(
            reservation={
                "active": True,
                "work_identity": "pl0n3r/Factory#other",
                "updated_at": "2026-10-02T00:58:30Z",
                "freshness": "fresh",
            }
        )
        mismatch_result = evaluate_unattended_watchdog(guard(), config(), mismatch)
        self.assertEqual(mismatch_result.action, "BLOCKED")
        self.assertIn("reservation_state_identity_mismatch", mismatch_result.daily_summary.blockers)

        missing_ready_since = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(work_ready=True, ready_since=None, next_dispatch_planned=False),
        )
        self.assertEqual(missing_ready_since.action, "BLOCKED")
        self.assertIn("missing_ready_since", missing_ready_since.daily_summary.blockers)

        invalid_alert = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(already_alerted_fingerprints=["not-a-sha256"]),
        )
        self.assertEqual(invalid_alert.action, "BLOCKED")
        self.assertIn("invalid_alert_fingerprint", invalid_alert.daily_summary.blockers)

    def test_daily_summary_is_deterministic_and_only_s1_s2_interrupt_owner(self):
        def with_incident(severity):
            return evidence(
                reservation=None,
                incidents=[
                    {
                        "incident_id": f"incident-{severity}",
                        "severity": severity,
                        "source": "health",
                        "updated_at": "2026-10-02T00:59:00Z",
                        "freshness": "fresh",
                    }
                ],
                active_fronts=["B", "A"],
                human_gates=["gate-b", "gate-a"],
                next_actions=["next-b", "next-a"],
            )

        for severity, expected in (("S1", True), ("S2", True), ("S3", False), ("UNKNOWN", False)):
            with self.subTest(severity=severity):
                payload = with_incident(severity)
                first = evaluate_unattended_watchdog(guard(), config(), payload)
                second = evaluate_unattended_watchdog(guard(), config(), copy.deepcopy(payload))
                self.assertEqual(first, second)
                self.assertEqual(first.interrupt_owner, expected)
                self.assertEqual(first.daily_summary.active_fronts, ("A", "B"))
                self.assertEqual(first.daily_summary.human_gates, ("gate-a", "gate-b"))
                self.assertIn(f"{severity}:reported:incident-{severity}", first.daily_summary.incidents)

        state_s1 = evaluate_unattended_watchdog(
            guard(), config(), evidence(reservation=None, state=state(severity="S1"))
        )
        self.assertTrue(state_s1.interrupt_owner)
        self.assertIn("S1:state_severity", state_s1.daily_summary.incidents)

        state_s2 = evaluate_unattended_watchdog(
            guard(), config(), evidence(reservation=None, state=state(severity="S2"))
        )
        self.assertTrue(state_s2.interrupt_owner)
        self.assertIn("S2:state_severity", state_s2.daily_summary.incidents)

        stale_s1 = evaluate_unattended_watchdog(
            guard(),
            config(),
            evidence(
                reservation=None,
                state=state(severity="S1", updated_at="2026-10-02T00:30:00Z"),
            ),
        )
        self.assertFalse(stale_s1.interrupt_owner)
        self.assertIn("S3:state_stale", stale_s1.daily_summary.incidents)
        self.assertIn("UNKNOWN:state_severity", stale_s1.daily_summary.incidents)
        self.assertEqual(stale_s1.action, "BLOCKED")

        source = Path("scripts/unattended_watchdog.py").read_text(encoding="utf-8")
        for forbidden in (
            "import requests",
            "import subprocess",
            "import socket",
            "import urllib",
            "import httpx",
            "schedule.",
            "cron",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
