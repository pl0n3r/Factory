#!/usr/bin/env python3
"""Regresiones del runtime programado del watchdog desatendido."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.unattended_watchdog_runtime import evaluate_runtime, parse_owned_alert

ROOT = Path(__file__).resolve().parents[1]


def guard():
    return {
        "action": "ALLOW",
        "authority": "unchanged",
        "pause_allowed": False,
        "reasons": ["guard-test"],
        "evidence_fingerprint": "a" * 64,
    }


def presence(*, freshness="fresh"):
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
                "work_item": "Factory#769",
                "issue_ref": "#769",
                "pr_ref": None,
                "state": "working",
                "assignment": "watchdog-runtime",
                "claims": ["scripts/unattended_watchdog_runtime.py"],
                "capabilities": ["python"],
                "heartbeat_at": "2026-10-02T00:59:30Z",
                "freshness": freshness,
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
            "freshness": freshness,
        },
    }


def state():
    return {
        "work_identity": "pl0n3r/Factory#769",
        "repository": "pl0n3r/Factory",
        "branch": "trabajo/issue-769",
        "head_sha": "d" * 40,
        "reservation_id": "reservation-769",
        "risk": "medium",
        "severity": "S3",
        "evidence": ["Factory#769", "main@abde4ba"],
        "last_state": "implementing",
        "next_action": "run runtime acceptance",
        "blockers": [],
        "updated_at": "2026-10-02T00:58:00Z",
    }


def evidence(**changes):
    value = {
        "now": "2026-10-02T01:00:00Z",
        "presence": presence(),
        "work_ready": False,
        "ready_since": None,
        "next_dispatch_planned": True,
        "reservation": None,
        "state": state(),
        "incidents": [],
        "already_alerted_fingerprints": [],
        "active_fronts": ["Factory#769"],
        "human_gates": [],
        "integrated": ["Factory#767"],
        "reverted": [],
        "next_actions": ["finish watchdog runtime"],
    }
    value.update(changes)
    return value


def config():
    return {
        "ready_without_dispatch_minutes": 10,
        "reservation_stale_minutes": 15,
        "state_stale_minutes": 20,
    }


class UnattendedWatchdogRuntimeTests(unittest.TestCase):
    def test_workflow_is_scheduled_manual_and_minimally_privileged(self):
        workflow = (
            ROOT / ".github" / "workflows" / "unattended-watchdog.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("cron: '*/15 * * * *'", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("timeout-minutes: 5", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("workflow_run", workflow)
        runtime = (ROOT / "scripts" / "unattended_watchdog_runtime.py").read_text(encoding="utf-8")
        self.assertIn("evaluate_unattended_kill_switch(client.get_issue(767))", runtime)
        self.assertIn('"state": "all"', runtime)
        self.assertIn('"labels": self._labels(spec)', runtime)

    def test_versioned_thresholds_are_closed_and_explicit(self):
        path = ROOT / "config" / "unattended-watchdog.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            payload,
            {
                "ready_without_dispatch_minutes": 10,
                "reservation_stale_minutes": 15,
                "state_stale_minutes": 20,
            },
        )

    def test_alert_plan_is_idempotent_and_closes_when_resolved(self):
        incident_evidence = evidence(
            work_ready=True,
            ready_since="2026-10-02T00:40:00Z",
            next_dispatch_planned=False,
        )
        first_decision, first = evaluate_runtime(
            config(), guard(), incident_evidence, {}
        )
        self.assertEqual(first_decision.action, "BLOCKED")
        self.assertEqual(len(first.create), 1)
        fingerprint = first.create[0].fingerprint

        repeated_decision, repeated = evaluate_runtime(
            config(), guard(), incident_evidence, {fingerprint: 123}
        )
        self.assertEqual(repeated_decision.action, "BLOCKED")
        self.assertEqual(repeated.create, ())
        self.assertEqual(repeated.reopen, ())
        self.assertEqual(repeated.close, ())

        closed_decision, closed_repeat = evaluate_runtime(
            config(),
            guard(),
            incident_evidence,
            {fingerprint: {"number": 123, "state": "closed"}},
        )
        self.assertEqual(closed_decision.action, "BLOCKED")
        self.assertEqual(closed_repeat.create, ())
        self.assertEqual(
            tuple(number for number, _ in closed_repeat.reopen),
            (123,),
        )

        resolved_decision, resolved = evaluate_runtime(
            config(), guard(), evidence(), {fingerprint: 123}
        )
        self.assertEqual(resolved_decision.action, "ALLOW")
        self.assertEqual(resolved.create, ())
        self.assertEqual(resolved.close, (123,))

    def test_missing_invalid_or_unknown_input_fails_closed_explicitly(self):
        cases = (
            (None, guard(), evidence()),
            ({**config(), "extra": 1}, guard(), evidence()),
            (
                config(),
                guard(),
                evidence(presence=presence(freshness="unknown")),
            ),
            (config(), None, evidence()),
            (config(), guard(), None),
        )
        for cfg, guard_payload, evidence_payload in cases:
            with self.subTest(
                cfg=cfg, guard_payload=guard_payload, evidence=evidence_payload
            ):
                decision, plan = evaluate_runtime(
                    cfg, guard_payload, evidence_payload, {}
                )
                self.assertEqual(decision.action, "BLOCKED")
                self.assertEqual(plan.authority, "unchanged")
                self.assertGreaterEqual(len(plan.create), 1)
                self.assertEqual(plan.reopen, ())
                self.assertEqual(plan.close, ())

    def test_runtime_cases_cover_valid_missing_invalid_repeat_and_resolution(self):
        fingerprint = "b" * 64
        owned = {
            "number": 9,
            "title": f"[AUTO][WATCHDOG] S3 {fingerprint[:12]}",
            "body": (
                '<!-- factory-unattended-watchdog-alert '
                f'{{"fingerprint":"{fingerprint}","version":1}} -->'
            ),
            "user": {"login": "github-actions[bot]"},
        }
        self.assertEqual(parse_owned_alert(owned), (fingerprint, 9, "open"))
        self.assertIsNone(parse_owned_alert({**owned, "user": {"login": "other"}}))
        self.assertIsNone(
            parse_owned_alert({**owned, "body": owned["body"] + "\n" + owned["body"]})
        )
        self.assertIsNone(
            parse_owned_alert(
                {
                    **owned,
                    "body": (
                        '<!-- factory-unattended-watchdog-alert '
                        f'{{"version":true,"fingerprint":"{fingerprint}"}} -->'
                    ),
                }
            )
        )

        valid_decision, valid = evaluate_runtime(
            config(), guard(), evidence(), {}
        )
        self.assertEqual(valid_decision.action, "ALLOW")
        self.assertEqual((valid.create, valid.reopen, valid.close), ((), (), ()))

        invalid_decision, invalid = evaluate_runtime(
            {"ready_without_dispatch_minutes": 0},
            guard(),
            evidence(),
            {},
        )
        self.assertEqual(invalid_decision.action, "BLOCKED")
        self.assertEqual(len(invalid.create), 1)

        incident_evidence = evidence(
            work_ready=True,
            ready_since="2026-10-02T00:40:00Z",
            next_dispatch_planned=False,
        )
        _, new_plan = evaluate_runtime(
            config(), guard(), incident_evidence, {}
        )
        fingerprint = new_plan.create[0].fingerprint
        _, repeated = evaluate_runtime(
            config(), guard(), incident_evidence, {fingerprint: 77}
        )
        self.assertEqual(repeated.create, ())
        _, resolved = evaluate_runtime(
            config(), guard(), evidence(), {fingerprint: 77}
        )
        self.assertEqual(resolved.close, (77,))


if __name__ == "__main__":
    unittest.main()
