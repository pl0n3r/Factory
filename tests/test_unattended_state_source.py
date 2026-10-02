#!/usr/bin/env python3
"""Regresiones de la fuente canónica STATE/Presence Factory#775."""
from __future__ import annotations

from pathlib import Path
import copy
import json
import unittest

from scripts.unattended_state_source import project_state_presence

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-02T04:10:00Z"
RID = "11111111-2222-4333-8444-555555555555"
HEAD = "a" * 40


def comment(user, body, at="2026-10-02T04:09:00Z"):
    return {"user": {"login": user}, "body": body, "created_at": at, "updated_at": at}


def reservation(active=True, at="2026-10-02T04:09:00Z", **changes):
    payload = {
        "version": 3,
        "owner": "pl0n3r",
        "reservation_id": RID,
        "branch": "trabajo/issue-775",
        "active": active,
        "reason": "tomar" if active else "liberar",
        "acceptance_sha256": "b" * 64,
        "task_marker_sha256": "c" * 64,
        "task_paths": ["scripts/unattended_state_source.py"],
        "task_depends_on": [745, 767],
    }
    payload.update(changes)
    return comment(
        "github-actions[bot]",
        f"<!-- condor-reserva {json.dumps(payload, separators=(',', ':'))} -->",
        at,
    )


def state_payload(**changes):
    value = {
        "work_identity": "pl0n3r/Factory#775",
        "repository": "pl0n3r/Factory",
        "branch": "trabajo/issue-775",
        "head_sha": HEAD,
        "reservation_id": RID,
        "risk": "medium",
        "severity": "S3",
        "evidence": ["Factory#775", f"head@{HEAD}"],
        "last_state": "implementing",
        "next_action": "run acceptance",
        "blockers": [],
        "updated_at": "2026-10-02T04:08:30Z",
    }
    value.update(changes)
    return value


def state_comment(state=None, *, user="pl0n3r", at="2026-10-02T04:09:00Z"):
    payload = {"version": 1, "state": state or state_payload()}
    return comment(
        user,
        f"<!-- factory-state {json.dumps(payload, separators=(',', ':'))} -->",
        at,
    )


def project(comments, **changes):
    args = {
        "repository": "pl0n3r/Factory",
        "issue_number": 775,
        "comments": comments,
        "now": NOW,
        "state_stale_minutes": 20,
        "reservation_stale_minutes": 15,
        "branch_head_sha": HEAD,
    }
    args.update(changes)
    return project_state_presence(**args)


class UnattendedStateSourceTests(unittest.TestCase):
    def test_state_marker_is_closed_bound_and_secret_free(self):
        result = project([reservation(), state_comment()])
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.authority, "unchanged")
        self.assertEqual(result.reservation_id, RID)
        self.assertEqual(result.state["work_identity"], "pl0n3r/Factory#775")
        self.assertEqual(result.state["reservation_id"], RID)
        self.assertEqual(result.state["head_sha"], HEAD)
        self.assertEqual(result.state["freshness"], "fresh")

    def test_presence_never_invents_heartbeat_or_capacity(self):
        result = project([reservation(), state_comment()])
        presence = result.presence
        self.assertEqual(presence["source"], "factory-state-github")
        self.assertEqual(presence["sessions"], [])
        self.assertEqual(
            presence["capacity"],
            {
                "known_slots": 0,
                "eligible_free_slots": 0,
                "degraded_slots": 0,
                "freshness": "unknown",
            },
        )
        self.assertIn("presence_heartbeat_unavailable", result.reasons)
        self.assertIn("presence_capacity_unknown", result.reasons)

    def test_invalid_or_incoherent_sources_fail_closed(self):
        cases = []
        duplicated = (
            '<!-- factory-state {"version":1,"state":{}} -->'
            '<!-- factory-state {"version":1,"state":{}} -->'
        )
        cases.append([reservation(), comment("pl0n3r", duplicated)])
        cases.append([reservation(), state_comment(state_payload(repository="pl0n3r/Condor"))])
        cases.append([reservation(), state_comment(state_payload(reservation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"))])
        cases.append([reservation(), state_comment(state_payload(head_sha="d" * 40))])
        cases.append([reservation(), state_comment(state_payload(evidence=["token=TOP-SECRET"]))])
        cases.append([reservation(), state_comment(state_payload(blockers=["contact user@example.com"]))])
        cases.append([reservation(), state_comment(state_payload(updated_at="2026-10-02T04:11:00Z"))])
        cases.append([reservation(), state_comment(user="someone-else")])
        cases.append([reservation(version=2), state_comment()])
        cases.append([reservation(acceptance_sha256="bad"), state_comment()])
        cases.append([reservation(task_marker_sha256="bad"), state_comment()])
        cases.append([reservation(task_paths=["x", "x"]), state_comment()])
        cases.append([reservation(task_depends_on=[745, 745]), state_comment()])
        cases.append([reservation(surprise="x"), state_comment()])

        for payload in cases:
            with self.subTest(payload=payload):
                result = project(payload)
                self.assertIn(result.status, {"BLOCKED", "UNKNOWN"})
                self.assertEqual(result.authority, "unchanged")
                self.assertNotEqual(result.status, "READY")

    def test_plan_requires_machine_readable_state_at_handoff(self):
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertIn("factory-state", plan)
        self.assertIn("handoff/checkpoint", plan)
        self.assertIn("evidencia derivada", plan)
        self.assertIn("nunca inventes heartbeat/capacidad", plan)

    def test_source_regression_matrix(self):
        valid = project([reservation(), state_comment()])
        self.assertEqual(valid.status, "READY")

        missing = project([reservation()])
        self.assertEqual(missing.status, "UNKNOWN")
        self.assertIn("state_marker_unavailable", missing.reasons)

        stale_lease = project([
            reservation(at="2026-10-02T03:40:00Z"),
            state_comment(at="2026-10-02T03:40:30Z"),
        ])
        self.assertEqual(stale_lease.status, "UNKNOWN")
        self.assertIn("reservation_stale", stale_lease.reasons)

        stale_state = project([
            reservation(),
            state_comment(state_payload(updated_at="2026-10-02T03:30:00Z")),
        ])
        self.assertEqual(stale_state.status, "READY")
        self.assertEqual(stale_state.state["freshness"], "stale")
        self.assertIn("state_stale", stale_state.reasons)

        released = project([reservation(), state_comment(), reservation(active=False)])
        self.assertEqual(released.status, "UNKNOWN")
        self.assertIsNone(released.state)

        changed = copy.deepcopy(state_payload())
        changed["updated_at"] = "2026-10-02T03:30:00Z"
        self.assertNotEqual(
            valid.state["freshness"],
            project([reservation(), state_comment(changed)]).state["freshness"],
        )


if __name__ == "__main__":
    unittest.main()
