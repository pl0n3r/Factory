#!/usr/bin/env python3
from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from scripts.release_window import _render_gate, plan_request
from seguridad.decision_respuesta import materialize_decision
from seguridad.test_decision_respuesta import (
    FakeAPI as DecisionFakeAPI,
    event as decision_event,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/release-window.yml").read_text(encoding="utf-8")
SECURITY = (ROOT / ".github/workflows/seguridad.yml").read_text(encoding="utf-8")

MAIN_SHA = "a" * 40
OLD_SHA = "b" * 40
VERSION = "1.0.28"
CHECKS = [
    {"name": "CI factory", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Sonar CI-based", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Evidencia CodeQL", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Unattended Watchdog", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Compatibilidad de consumidores", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
]


def gate_row(
    number: int,
    sha: str,
    state: str = "open",
    *,
    automated: bool = True,
) -> dict:
    rendered = _render_gate(
        VERSION,
        sha,
        datetime.fromisoformat("2026-10-04T19:00:00+00:00"),
        source_issue=800,
    )
    body = rendered["body"]
    if not automated:
        body = "\n".join(
            line
            for line in body.splitlines()
            if "factory-release-window" not in line
            and "factory-release-rearm" not in line
        )
    return {
        "issue": {
            "number": number,
            "state": state,
            "title": rendered["title"],
            "body": body,
            "updated_at": "2026-10-04T19:00:00Z",
            "author_association": "NONE" if automated else "OWNER",
            "user": {
                "login": "github-actions[bot]" if automated else "pl0n3r",
                "type": "Bot" if automated else "User",
            },
        },
        "comments": [],
    }


HISTORY = [gate_row(800, OLD_SHA, state="closed", automated=False)]


def request_payload(**changes) -> dict:
    payload = {
        "now": "2026-10-04T19:00:00Z",
        "main_sha": MAIN_SHA,
        "version": VERSION,
        "candidate_version": VERSION,
        "owner_requested": True,
        "actor": "pl0n3r",
        "owner": "pl0n3r",
        "workflows": CHECKS,
        "gates": list(HISTORY),
    }
    payload.update(changes)
    return payload


class ReleaseWindowOnDemandTests(unittest.TestCase):
    def test_push_to_main_never_opens_or_rearms_a_release_gate_without_owner_request(self):
        result = plan_request(request_payload(owner_requested=False))
        self.assertEqual(
            result,
            {"action": "rejected", "reason": "owner_request_required"},
        )
        trigger = WORKFLOW.split("permissions:", 1)[0]
        self.assertNotIn("\n  push:\n", trigger)
        self.assertIn("workflow_dispatch:", trigger)
        self.assertIn("workflow_run:", trigger)
        self.assertNotIn("scripts/release_window.py push", WORKFLOW)

    def test_owner_request_opens_single_gate_on_current_head_with_revalidated_evidence(self):
        result = plan_request(request_payload())
        self.assertEqual(result["action"], "create_gate")
        self.assertEqual(result["reason"], "owner_requested")
        self.assertEqual(result["sha"], MAIN_SHA)
        self.assertEqual(result["version"], VERSION)
        self.assertEqual(result["source_issue"], 800)
        self.assertEqual(result["supersede_issues"], [])
        self.assertIn("python3 -m scripts.reusable_release_preflight", WORKFLOW)
        self.assertIn("Unattended Watchdog", (ROOT / "scripts/release_window.py").read_text(encoding="utf-8"))

    def test_non_owner_or_inexact_request_is_ignored_and_older_gates_are_superseded_silently(self):
        stale = gate_row(900, OLD_SHA)
        gates = HISTORY + [stale]

        rejected = plan_request(request_payload(actor="someone-else", gates=gates))
        self.assertEqual(rejected["reason"], "owner_request_required")

        inexact = plan_request(
            request_payload(version="1.0.29", gates=gates)
        )
        self.assertEqual(inexact["reason"], "version_mismatch")

        result = plan_request(request_payload(gates=gates))
        self.assertEqual(result["action"], "create_gate")
        self.assertEqual(result["supersede_issues"], [900])
        self.assertIn("state_reason=not_planned", WORKFLOW)
        self.assertIn(
            "labels/decisi%C3%B3n%3A%20due%C3%B1o",
            WORKFLOW,
        )
        self.assertNotIn("@$OWNER", WORKFLOW)
        self.assertNotIn('[[ "$ACTOR" == "$OWNER" ]]', WORKFLOW)
        rejected_branch = WORKFLOW.split("            rejected)", 1)[1].split(
            "            create_gate)", 1
        )[0]
        self.assertIn("::notice::Solicitud de release ignorada", rejected_branch)
        self.assertNotIn("exit 1", rejected_branch)

    def test_owner_decision_is_not_lost_to_concurrency_cancel_or_prior_reconciliation(self):
        rendered = _render_gate(
            VERSION,
            MAIN_SHA,
            datetime.fromisoformat("2026-10-04T19:00:00+00:00"),
            source_issue=800,
        )
        decision = decision_event(
            command="/decidir A",
            issue_body=rendered["body"],
        )
        api = DecisionFakeAPI(
            body=rendered["body"],
            crash_after_evidence_once=True,
        )

        with self.assertRaises(RuntimeError):
            materialize_decision(decision, api, "pl0n3r/Factory")
        self.assertTrue(
            materialize_decision(decision, api, "pl0n3r/Factory")
        )
        self.assertEqual(api.issue["state"], "closed")
        evidence = [
            item for item in api.comments
            if item["body"].startswith("<!-- factory-human-decision ")
        ]
        self.assertEqual(len(evidence), 1)

        self.assertIn("human-gate-{0}", SECURITY)
        self.assertIn("cancel-in-progress: false", SECURITY)
        self.assertIn("canonical=true", SECURITY)
        self.assertIn("decision_materialized=true", SECURITY)

    def test_missing_exact_main_evidence_fails_closed(self):
        reduced = [
            check for check in CHECKS
            if check["name"] != "Compatibilidad de consumidores"
        ]
        result = plan_request(request_payload(workflows=reduced))
        self.assertEqual(result["action"], "rejected")
        self.assertEqual(result["reason"], "revalidation_required")
        self.assertEqual(
            result["missing_checks"],
            ["Compatibilidad de consumidores"],
        )


if __name__ == "__main__":
    unittest.main()
