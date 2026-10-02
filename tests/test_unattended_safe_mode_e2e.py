#!/usr/bin/env python3
"""Simulacro E2E controlado del modo desatendido seguro (Tramo 4D)."""
from __future__ import annotations

import copy
import inspect
import unittest

from scripts.adaptive_fencing import FencingDecision
from scripts.unattended_guards import evaluate_unattended_guards
from scripts.unattended_watchdog import evaluate_unattended_watchdog


def fencing(action="keep", pause_allowed=False):
    return FencingDecision(
        action,
        pause_allowed,
        7,
        1,
        "a" * 64,
        "b" * 64,
        1,
        ("synthetic-drill",),
    )


def guard_config(**changes):
    value = {
        "global_pause": False,
        "breakers": {
            "health": {
                "scope": "repo",
                "subject": "pl0n3r/Factory",
                "threshold": 3,
            }
        },
        "ceilings": {
            "usage": 100,
            "cost": 50.0,
            "parallelism": 2,
        },
    }
    value.update(changes)
    return value


def guard_evidence(**changes):
    value = {
        "breakers": {
            "health": {
                "consecutive_failures": 0,
                "fresh": True,
                "consistent": True,
            }
        },
        "risk": "low",
        "second_pass": False,
        "sensitive": {
            "go_live": False,
            "spend": False,
            "irreversible": False,
            "real_data": False,
        },
        "production_change": False,
        "backup_required": False,
        "backup_verified": None,
    }
    value.update(changes)
    return value


def measurements(**changes):
    value = {
        "usage": 10,
        "cost": 5.0,
        "parallelism": 1,
    }
    value.update(changes)
    return value


def presence():
    return {
        "version": 1,
        "source": "synthetic-drill",
        "observed_at": "2026-10-02T02:00:00Z",
        "sessions": [
            {
                "session_id": "drill-session",
                "agent_id": "drill-agent",
                "project": "factory",
                "repo": "pl0n3r/Factory",
                "work_item": "Factory#746",
                "issue_ref": "#746",
                "pr_ref": None,
                "state": "working",
                "assignment": "safe-mode-drill",
                "claims": [
                    "tests/test_unattended_safe_mode_e2e.py",
                    "docs/unattended-safe-mode-drill.md",
                ],
                "capabilities": ["python"],
                "heartbeat_at": "2026-10-02T01:59:30Z",
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
        "work_identity": "pl0n3r/Factory#746",
        "repository": "pl0n3r/Factory",
        "branch": "trabajo/issue-746",
        "head_sha": "e" * 40,
        "reservation_id": "reservation-746",
        "risk": "medium",
        "severity": "S3",
        "evidence": ["Factory#746", "synthetic-drill"],
        "last_state": "drill-running",
        "next_action": "evaluate synthetic evidence",
        "blockers": [],
        "updated_at": "2026-10-02T01:58:00Z",
    }
    value.update(changes)
    return value


def watchdog_config(**changes):
    value = {
        "ready_without_dispatch_minutes": 10,
        "reservation_stale_minutes": 15,
        "state_stale_minutes": 20,
    }
    value.update(changes)
    return value


def watchdog_evidence(**changes):
    value = {
        "now": "2026-10-02T02:00:00Z",
        "presence": presence(),
        "work_ready": False,
        "ready_since": None,
        "next_dispatch_planned": True,
        "reservation": {
            "active": True,
            "work_identity": "pl0n3r/Factory#746",
            "updated_at": "2026-10-02T01:58:30Z",
            "freshness": "fresh",
        },
        "state": state(),
        "incidents": [],
        "already_alerted_fingerprints": [],
        "active_fronts": ["Factory#746"],
        "human_gates": [],
        "integrated": ["Factory#745"],
        "reverted": [],
        "next_actions": ["complete controlled drill"],
    }
    value.update(changes)
    return value


def run_pipeline(
    *,
    fence=None,
    guard_cfg=None,
    guard_ev=None,
    measured=None,
    watch_cfg=None,
    watch_ev=None,
):
    guard = evaluate_unattended_guards(
        fence if fence is not None else fencing(),
        guard_cfg if guard_cfg is not None else guard_config(),
        guard_ev if guard_ev is not None else guard_evidence(),
        measured if measured is not None else measurements(),
    )
    watchdog = evaluate_unattended_watchdog(
        guard,
        watch_cfg if watch_cfg is not None else watchdog_config(),
        watch_ev if watch_ev is not None else watchdog_evidence(),
    )
    return guard, watchdog


def smoke_incident(severity="S1", freshness="fresh"):
    return {
        "incident_id": "synthetic-smoke-red",
        "severity": severity,
        "source": "synthetic-smoke",
        "updated_at": "2026-10-02T01:59:00Z",
        "freshness": freshness,
    }


class UnattendedSafeModeE2ETests(unittest.TestCase):
    def test_healthy_baseline_stays_allowed_without_false_alerts(self):
        guard, watchdog = run_pipeline(
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(reservation_id=None),
            )
        )

        self.assertEqual(
            (guard.action, guard.pause_allowed, guard.authority),
            ("ALLOW", False, "unchanged"),
        )
        self.assertEqual(
            (watchdog.action, watchdog.authority, watchdog.interrupt_owner),
            ("ALLOW", "unchanged", False),
        )
        self.assertEqual(watchdog.incidents, ())
        self.assertEqual(watchdog.new_alert_fingerprints, ())
        self.assertEqual(watchdog.daily_summary.state_freshness, "fresh")

    def test_pause_breaker_and_ceilings_stop_new_work_without_expanding_authority(self):
        cases = (
            (
                guard_config(global_pause=True),
                guard_evidence(),
                measurements(),
                "global_pause_active",
            ),
            (
                guard_config(),
                guard_evidence(
                    breakers={
                        "health": {
                            "consecutive_failures": 3,
                            "fresh": True,
                            "consistent": True,
                        }
                    }
                ),
                measurements(),
                "circuit_breaker_open",
            ),
            (
                guard_config(),
                guard_evidence(),
                measurements(cost=75.0),
                "cost_ceiling_exceeded",
            ),
        )

        for config, evidence, measured, reason in cases:
            with self.subTest(reason=reason):
                guard, watchdog = run_pipeline(
                    fence=fencing("replan", True),
                    guard_cfg=config,
                    guard_ev=evidence,
                    measured=measured,
                    watch_ev=watchdog_evidence(
                        reservation=None,
                        state=state(reservation_id=None),
                    ),
                )
                self.assertEqual(
                    (guard.action, guard.pause_allowed, guard.authority),
                    ("PAUSE", True, "unchanged"),
                )
                self.assertIn(reason, guard.reasons)
                self.assertEqual(
                    (watchdog.action, watchdog.authority),
                    ("PAUSE", "unchanged"),
                )

        blocked, watchdog = run_pipeline(
            fence=fencing("keep", False),
            guard_cfg=guard_config(global_pause=True),
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(reservation_id=None),
            ),
        )
        self.assertEqual(
            (blocked.action, blocked.pause_allowed, blocked.authority),
            ("BLOCKED", False, "unchanged"),
        )
        self.assertIn("adaptive_pause_not_allowed", blocked.reasons)
        self.assertEqual(watchdog.action, "BLOCKED")

    def test_stale_state_idle_dispatch_and_stalled_reservation_are_idempotently_reported(self):
        degraded_presence = presence()
        degraded_presence["sessions"][0]["freshness"] = "unknown"

        payload = watchdog_evidence(
            presence=degraded_presence,
            work_ready=True,
            ready_since="2026-10-02T01:30:00Z",
            next_dispatch_planned=False,
            reservation={
                "active": True,
                "work_identity": "pl0n3r/Factory#746",
                "updated_at": "2026-10-02T01:20:00Z",
                "freshness": "stale",
            },
            state=state(updated_at="2026-10-02T01:20:00Z"),
        )
        guard, first = run_pipeline(watch_ev=payload)
        self.assertEqual(guard.action, "ALLOW")
        self.assertEqual(first.action, "BLOCKED")

        codes = {incident.code for incident in first.incidents}
        self.assertTrue(
            {
                "presence_insufficient",
                "ready_without_dispatch",
                "reservation_without_progress",
                "state_stale",
            }.issubset(codes)
        )
        self.assertEqual(first.daily_summary.state_freshness, "stale")
        self.assertIn("S3:ready_without_dispatch", first.daily_summary.incidents)
        self.assertIn("S3:reservation_without_progress", first.daily_summary.incidents)
        self.assertIn("S3:state_stale", first.daily_summary.incidents)
        self.assertIn("UNKNOWN:presence_insufficient", first.daily_summary.incidents)

        repeated_payload = copy.deepcopy(payload)
        repeated_payload["already_alerted_fingerprints"] = list(
            first.new_alert_fingerprints
        )
        _, second = run_pipeline(watch_ev=repeated_payload)
        self.assertEqual(second.new_alert_fingerprints, ())
        self.assertTrue(second.incidents)
        self.assertTrue(all(incident.repeated for incident in second.incidents))

    def test_sustained_red_smoke_prefers_reversible_rollback_or_fail_closed_stop(self):
        # Camino reversible ya autorizado: 4B está en PAUSE canónico y la
        # intención de rollback llega solo como evidencia sintética preexistente.
        authorized_guard, authorized_watchdog = run_pipeline(
            fence=fencing("replan", True),
            guard_cfg=guard_config(global_pause=True),
            guard_ev=guard_evidence(
                production_change=True,
                backup_required=True,
                backup_verified=True,
            ),
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(
                    reservation_id=None,
                    evidence=[
                        "synthetic-smoke-red",
                        "rollback-authorized",
                        "exact-sha",
                        "backup-verified",
                    ],
                    next_action="rollback reversible already authorized at exact SHA",
                    severity="S1",
                ),
                incidents=[smoke_incident("S1", "fresh")],
                next_actions=[
                    "rollback reversible already authorized at exact SHA"
                ],
            ),
        )
        self.assertEqual(
            (authorized_guard.action, authorized_guard.pause_allowed),
            ("PAUSE", True),
        )
        self.assertEqual(
            (authorized_watchdog.action, authorized_watchdog.authority),
            ("PAUSE", "unchanged"),
        )
        self.assertTrue(authorized_watchdog.interrupt_owner)
        self.assertIn(
            "rollback reversible already authorized at exact SHA",
            authorized_watchdog.daily_summary.next_actions,
        )

        backup_blocked, backup_watchdog = run_pipeline(
            guard_ev=guard_evidence(
                production_change=True,
                backup_required=True,
                backup_verified=False,
            ),
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(
                    reservation_id=None,
                    next_action="stop and escalate: backup not verified",
                ),
                incidents=[smoke_incident("S1", "fresh")],
                next_actions=["stop and escalate: backup not verified"],
            ),
        )
        self.assertEqual(backup_blocked.action, "BLOCKED")
        self.assertIn("required_backup_not_verified", backup_blocked.reasons)
        self.assertEqual(
            (backup_watchdog.action, backup_watchdog.authority),
            ("BLOCKED", "unchanged"),
        )
        self.assertIn(
            "stop and escalate: backup not verified",
            backup_watchdog.daily_summary.next_actions,
        )

        destructive_flags = {
            "go_live": False,
            "spend": False,
            "irreversible": True,
            "real_data": False,
        }
        destructive_guard, destructive_watchdog = run_pipeline(
            guard_ev=guard_evidence(sensitive=destructive_flags),
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(
                    reservation_id=None,
                    next_action="stop and escalate: destructive authority",
                ),
                incidents=[smoke_incident("S1", "fresh")],
                next_actions=["stop and escalate: destructive authority"],
            ),
        )
        self.assertEqual(destructive_guard.action, "BLOCKED")
        self.assertIn(
            "sensitive_authority_not_granted",
            destructive_guard.reasons,
        )
        self.assertEqual(destructive_watchdog.action, "BLOCKED")
        self.assertIn(
            "stop and escalate: destructive authority",
            destructive_watchdog.daily_summary.next_actions,
        )

        unknown_guard, unknown_watchdog = run_pipeline(
            guard_ev=guard_evidence(risk="UNKNOWN"),
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(
                    reservation_id=None,
                    next_action="stop and escalate: authority unknown",
                ),
                incidents=[smoke_incident("UNKNOWN", "fresh")],
                next_actions=["stop and escalate: authority unknown"],
            ),
        )
        self.assertEqual(unknown_guard.action, "BLOCKED")
        self.assertIn("risk_unknown", unknown_guard.reasons)
        self.assertEqual(unknown_watchdog.action, "BLOCKED")
        self.assertFalse(unknown_watchdog.interrupt_owner)
        self.assertIn(
            "stop and escalate: authority unknown",
            unknown_watchdog.daily_summary.next_actions,
        )

    def test_only_s1_s2_interrupt_owner_and_unknown_stays_fail_closed(self):
        for severity, expected_interrupt in (
            ("S1", True),
            ("S2", True),
            ("S3", False),
            ("UNKNOWN", False),
        ):
            with self.subTest(severity=severity):
                payload = watchdog_evidence(
                    reservation=None,
                    state=state(reservation_id=None),
                    incidents=[
                        {
                            "incident_id": f"synthetic-{severity}",
                            "severity": severity,
                            "source": "synthetic-smoke",
                            "updated_at": "2026-10-02T01:59:00Z",
                            "freshness": "fresh",
                        }
                    ],
                )
                _, watchdog = run_pipeline(watch_ev=payload)
                self.assertEqual(
                    watchdog.interrupt_owner,
                    expected_interrupt,
                )
                self.assertIn(
                    f"{severity}:reported:synthetic-{severity}",
                    watchdog.daily_summary.incidents,
                )
                if severity == "UNKNOWN":
                    self.assertEqual(watchdog.action, "BLOCKED")

        stale_s1 = watchdog_evidence(
            reservation=None,
            state=state(
                reservation_id=None,
                severity="S1",
                updated_at="2026-10-02T01:20:00Z",
            ),
        )
        _, stale = run_pipeline(watch_ev=stale_s1)
        self.assertFalse(stale.interrupt_owner)
        self.assertEqual(stale.action, "BLOCKED")
        self.assertIn("S3:state_stale", stale.daily_summary.incidents)
        self.assertIn("UNKNOWN:state_severity", stale.daily_summary.incidents)

    def test_sensitive_authority_boundaries_remain_closed_and_external_io_free(self):
        for sensitive in ("go_live", "spend", "irreversible", "real_data"):
            flags = {
                "go_live": False,
                "spend": False,
                "irreversible": False,
                "real_data": False,
            }
            flags[sensitive] = True
            with self.subTest(sensitive=sensitive):
                guard = evaluate_unattended_guards(
                    fencing(),
                    guard_config(),
                    guard_evidence(sensitive=flags),
                    measurements(),
                )
                self.assertEqual(
                    (guard.action, guard.authority),
                    ("BLOCKED", "unchanged"),
                )
                self.assertIn(
                    "sensitive_authority_not_granted",
                    guard.reasons,
                )

        no_backup = evaluate_unattended_guards(
            fencing(),
            guard_config(),
            guard_evidence(
                production_change=True,
                backup_required=True,
                backup_verified=None,
            ),
            measurements(),
        )
        self.assertEqual(no_backup.action, "BLOCKED")
        self.assertIn(
            "required_backup_not_verified",
            no_backup.reasons,
        )

        source = (
            inspect.getsource(evaluate_unattended_guards)
            + inspect.getsource(evaluate_unattended_watchdog)
        )
        for forbidden in (
            "requests.",
            "subprocess.",
            "socket.",
            "urllib.",
            "httpx.",
            "github.",
            "schedule.",
            "cron",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
