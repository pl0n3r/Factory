#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import release_window as rw


ROOT = Path(__file__).resolve().parents[1]
OLD_SHA = "4" * 40
NEW_SHA = "5" * 40
NOW = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)


def gate_row(
    *,
    number: int,
    body: str,
    state: str = "open",
    comments: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "issue": {
            "number": number,
            "state": state,
            "title": f"gate {number}",
            "body": body,
            "updated_at": "2026-10-03T09:55:00Z",
        },
        "comments": comments or [],
    }


def approved_comment(body: str) -> dict[str, object]:
    parsed = rw._gate_from_body(body)
    assert parsed is not None
    gate, _, _ = parsed
    payload = {
        "gate_sha256": rw._gate_fingerprint(gate),
        "option": "A",
        "version": 2,
    }
    return {
        "user": {"login": "github-actions[bot]"},
        "body": (
            "<!-- factory-human-decision "
            + json.dumps(payload, separators=(",", ":"), sort_keys=True)
            + " -->"
        ),
    }


class ReleaseWindowTests(unittest.TestCase):
    def test_active_window_blocks_normal_merges_and_allows_only_explicit_critical_repair(self) -> None:
        rendered = rw._render_gate(
            "1.0.23",
            OLD_SHA,
            NOW,
            source_issue=918,
        )
        rows = [gate_row(number=922, body=rendered["body"])]

        for pr_number in (1001, 1002):
            result = rw.check_pull_request({
                "now": "2026-10-03T10:10:00Z",
                "gates": rows,
                "pr": {"number": pr_number, "body": ""},
                "work_issue": {
                    "number": pr_number,
                    "state": "open",
                    "labels": [{"name": "prioridad: alta"}],
                },
            })
            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason"], "factory_release_window_active")
            self.assertEqual(result["gate_issue"], 922)

        exception = (
            '<!-- factory-release-freeze-exception '
            '{"version":1,"reason":"critical-repair","issue":921} -->'
        )
        allowed = rw.check_pull_request({
            "now": "2026-10-03T10:10:00Z",
            "gates": rows,
            "pr": {"number": 1003, "body": exception},
            "work_issue": {
                "number": 921,
                "state": "open",
                "labels": [{"name": "prioridad: crítica"}],
            },
        })
        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["reason"], "critical_repair_exception")

        wrong_issue = rw.check_pull_request({
            "now": "2026-10-03T10:10:00Z",
            "gates": rows,
            "pr": {"number": 1004, "body": exception},
            "work_issue": {
                "number": 999,
                "state": "open",
                "labels": [{"name": "prioridad: crítica"}],
            },
        })
        self.assertFalse(wrong_issue["allowed"])

        expired = rw.check_pull_request({
            "now": "2026-10-03T11:01:00Z",
            "gates": rows,
            "pr": {"number": 1005, "body": ""},
            "work_issue": {
                "number": 1005,
                "state": "open",
                "labels": [{"name": "prioridad: alta"}],
            },
        })
        self.assertTrue(expired["allowed"])
        self.assertEqual(expired["reason"], "no_active_release_window")

    def test_stale_approved_sha_rearms_current_head_without_reusing_decision(self) -> None:
        old = rw._render_gate("1.0.23", OLD_SHA, NOW, source_issue=900)
        old_row = gate_row(
            number=918,
            body=old["body"],
            state="closed",
            comments=[approved_comment(old["body"])],
        )

        planned = rw.plan_rearm({
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
            "gates": [old_row],
        })
        self.assertEqual(planned["action"], "create_gate")
        self.assertEqual(planned["source_issue"], 918)
        self.assertEqual(planned["source_sha"], OLD_SHA)
        self.assertEqual(planned["sha"], NEW_SHA)
        self.assertIn(f"main@{NEW_SHA}", planned["body"])
        self.assertIn('"safe_default":"B"', planned["body"])
        self.assertNotIn("factory-human-decision", planned["body"])
        self.assertNotIn("/decidir A", planned["body"])

        new_row = gate_row(number=922, body=planned["body"], state="open")
        repeated = rw.plan_rearm({
            "now": "2026-10-03T10:21:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
            "gates": [old_row, new_row],
        })
        self.assertEqual(
            repeated,
            {"action": "none", "reason": "current_head_already_has_gate"},
        )

    def test_workflow_rearms_on_push_and_marks_only_successful_release_execution(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "release-window.yml"
        ).read_text(encoding="utf-8")
        factory_ci = (
            ROOT / ".github" / "workflows" / "factory-ci.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("push:", workflow)
        self.assertIn("workflow_run:", workflow)
        self.assertIn("Release Factory v1.x", workflow)
        self.assertIn("python3 scripts/release_window.py push", workflow)
        self.assertIn("python3 scripts/release_window.py workflow-run", workflow)
        self.assertIn("issues: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("factory-release-executed", workflow)
        self.assertIn("factory-release-rearm", workflow)

        self.assertIn("release_window:", factory_ci)
        self.assertIn("issues: read", factory_ci)
        self.assertIn("pull-requests: read", factory_ci)
        self.assertIn("python3 scripts/release_window.py pr-check", factory_ci)
        self.assertIn("release_window", factory_ci.split("validar:", 1)[1])


if __name__ == "__main__":
    unittest.main()
