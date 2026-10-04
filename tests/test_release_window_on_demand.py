#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unittest

from scripts.release_window import _render_gate, plan_request
from seguridad.decision_respuesta import materialize_decision

MAIN_SHA = "a" * 40
OLD_SHA = "b" * 40
CHECKS = [
    {"name": "CI factory", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Sonar CI-based", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Evidencia CodeQL", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Vigilar startup_failure de reusables publicados", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
    {"name": "Compatibilidad de consumidores", "status": "completed", "conclusion": "success", "head_sha": MAIN_SHA},
]

def gate_row(number: int, sha: str, state: str = "open") -> dict:
    rendered = _render_gate("1.0.28", sha, "2026-10-04T19:00:00+00:00", source_issue=number)
    return {
        "issue": {
            "number": number,
            "state": state,
            "title": rendered["title"],
            "body": rendered["body"],
        },
        "comments": [],
    }

class ReleaseWindowOnDemandTests(unittest.TestCase):
    def test_push_to_main_never_opens_or_rearms_a_release_gate_without_owner_request(self):
        result = plan_request({
            "now": "2026-10-04T19:00:00Z",
            "main_sha": MAIN_SHA,
            "version": "1.0.28",
            "owner_requested": False,
            "actor": "pl0n3r",
            "checks": CHECKS,
            "gates": [],
        })
        self.assertEqual(result["action"], "rejected")
        self.assertEqual(result["reason"], "owner_request_required")

    def test_owner_request_opens_single_gate_on_current_head_with_revalidated_evidence(self):
        result = plan_request({
            "now": "2026-10-04T19:00:00Z",
            "main_sha": MAIN_SHA,
            "version": "1.0.28",
            "owner_requested": True,
            "actor": "pl0n3r",
            "checks": CHECKS,
            "gates": [],
        })
        self.assertEqual(result["action"], "create_gate")
        self.assertEqual(result["sha"], MAIN_SHA)
        self.assertEqual(result["version"], "1.0.28")
        self.assertEqual(result["supersede_issues"], [])

    def test_non_owner_or_inexact_request_is_ignored_and_older_gates_are_superseded_silently(self):
        gates = [gate_row(900, OLD_SHA)]
        rejected = plan_request({
            "now": "2026-10-04T19:00:00Z",
            "main_sha": MAIN_SHA,
            "version": "1.0.28",
            "owner_requested": True,
            "actor": "someone-else",
            "checks": CHECKS,
            "gates": gates,
        })
        self.assertEqual(rejected["action"], "rejected")
        result = plan_request({
            "now": "2026-10-04T19:00:00Z",
            "main_sha": MAIN_SHA,
            "version": "1.0.28",
            "owner_requested": True,
            "actor": "pl0n3r",
            "checks": CHECKS,
            "gates": gates,
        })
        self.assertEqual(result["action"], "create_gate")
        self.assertEqual(result["supersede_issues"], [900])
        self.assertNotIn("decision", result["reason"])

    def test_owner_decision_is_not_lost_to_concurrency_cancel_or_prior_reconciliation(self):
        rendered = _render_gate("1.0.28", MAIN_SHA, "2026-10-04T19:00:00+00:00", source_issue=900)
        marker = rendered["body"]
        gate_marker = marker.split("<!-- factory-human-gate ", 1)[1].split(" -->", 1)[0]
        gate_sha = hashlib.sha256(json.dumps(json.loads(gate_marker), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()
        issue = {
            "number": 901,
            "state": "open",
            "body": rendered["body"],
            "labels": [{"name": "decisión: dueño"}],
        }
        comments = []
        events = {"repository": {"full_name": "pl0n3r/Factory"}, "issue": issue,
                  "comment": {"body": "/decidir A", "author_association": "OWNER",
                              "user": {"type": "User", "login": "pl0n3r"}}}
        class FakeAPI:
            def __init__(self):
                self.issue = dict(issue)
                self.comments = comments
                self.closed = False
            def __call__(self, method, path, payload=None):
                if path == "repos/pl0n3r/Factory/issues/901":
                    return {**self.issue, "comments": self.comments}
                if path == "repos/pl0n3r/Factory/issues/901/comments?per_page=100":
                    return self.comments
                if path == "repos/pl0n3r/Factory/issues?state=all&per_page=100":
                    return [self.issue]
                if method == "POST" and path == "repos/pl0n3r/Factory/issues/901/comments":
                    self.comments.append({"user": {"login": "github-actions[bot]"}, "body": payload["body"]})
                    return {}
                if method == "PATCH" and path == "repos/pl0n3r/Factory/issues/901":
                    self.issue.update(payload)
                    return {}
                return {}
        api = FakeAPI()
        self.assertTrue(materialize_decision(events, api, "pl0n3r/Factory"))
        self.assertEqual(api.issue["state"], "closed")
        self.assertTrue(any("factory-human-decision" in c["body"] for c in api.comments))
        api.issue["state"] = "open"
        api.issue["labels"] = [{"name": "decisión: dueño"}]
        events["comment"]["body"] = "/decidir A"
        self.assertTrue(materialize_decision(events, api, "pl0n3r/Factory"))

if __name__ == "__main__":
    unittest.main()
