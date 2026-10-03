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

    def test_legacy_release_gates_without_window_marker_are_ignored(self) -> None:
        legacy = (
            '<!-- factory-human-gate '
            '{"category":"factory-release","context":"Factory v1.0.22 main@'
            + OLD_SHA
            + '"} -->'
        )
        self.assertEqual(
            rw.gate_records([gate_row(number=901, body=legacy, state="closed")]),
            [],
        )

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
        self.assertIn("Responde explícitamente `/decidir A` o `/decidir B`.", planned["body"])

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
        coordination = factory_ci.split("  coordinacion:", 1)[1].split("  acceptance:", 1)[0]
        self.assertIn("needs: [release_window]", coordination)
        self.assertIn("needs: [workflows, scripts, coordinacion, acceptance]", factory_ci)


    def test_execution_marks_only_approved_exact_sha_and_becomes_idempotent(self) -> None:
        rendered = rw._render_gate("1.0.23", OLD_SHA, NOW, source_issue=900)
        approved = approved_comment(rendered["body"])
        row = gate_row(
            number=918,
            body=rendered["body"],
            state="closed",
            comments=[approved],
        )

        self.assertEqual(
            rw.plan_execution({"conclusion": "failure"}),
            {"action": "none", "reason": "release_run_not_successful"},
        )
        self.assertEqual(
            rw.plan_execution({
                "conclusion": "success",
                "now": "2026-10-03T10:30:00Z",
                "head_sha": NEW_SHA,
                "run_id": 12345,
                "gates": [row],
            }),
            {"action": "none", "reason": "no_approved_gate_for_run_sha"},
        )

        before = rw.approved_unexecuted({"gates": [row]})
        self.assertEqual(before["issue"], 918)
        self.assertEqual(before["sha"], OLD_SHA)

        marked = rw.plan_execution({
            "conclusion": "success",
            "now": "2026-10-03T10:30:00Z",
            "head_sha": OLD_SHA,
            "run_id": 12345,
            "gates": [row],
        })
        self.assertEqual(marked["action"], "mark_executed")
        self.assertEqual(marked["issue"], 918)
        self.assertIn(OLD_SHA, marked["comment"])
        self.assertIn('"run_id":12345', marked["comment"])

        executed_row = gate_row(
            number=918,
            body=rendered["body"],
            state="closed",
            comments=[
                approved,
                {
                    "user": {"login": "github-actions[bot]"},
                    "body": marked["comment"],
                },
            ],
        )
        self.assertEqual(
            rw.plan_execution({
                "conclusion": "success",
                "now": "2026-10-03T10:31:00Z",
                "head_sha": OLD_SHA,
                "run_id": 12346,
                "gates": [executed_row],
            }),
            {"action": "none", "reason": "execution_already_recorded"},
        )
        self.assertIsNone(rw.approved_unexecuted({"gates": [executed_row]}))

    def test_rearm_noops_without_eligible_stale_approval(self) -> None:
        base = {
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
        }
        self.assertEqual(
            rw.plan_rearm({**base, "gates": []}),
            {"action": "none", "reason": "no_prior_release_gate"},
        )

        rendered = rw._render_gate("1.0.23", OLD_SHA, NOW, source_issue=900)
        closed_unapproved = gate_row(number=918, body=rendered["body"], state="closed")
        self.assertEqual(
            rw.plan_rearm({**base, "gates": [closed_unapproved]}),
            {"action": "none", "reason": "latest_gate_not_approved"},
        )

        approved = approved_comment(rendered["body"])
        execution = {
            "version": 1,
            "sha": OLD_SHA,
            "run_id": 9876,
            "executed_at": "2026-10-03T10:05:00Z",
        }
        executed = gate_row(
            number=918,
            body=rendered["body"],
            state="closed",
            comments=[
                approved,
                {
                    "user": {"login": "github-actions[bot]"},
                    "body": (
                        "<!-- factory-release-executed "
                        + json.dumps(execution, separators=(",", ":"), sort_keys=True)
                        + " -->"
                    ),
                },
            ],
        )
        self.assertEqual(
            rw.plan_rearm({**base, "gates": [executed]}),
            {"action": "none", "reason": "latest_release_executed"},
        )


    def test_release_evidence_validation_fails_closed(self) -> None:
        with self.assertRaises(rw.ReleaseWindowError):
            rw._canonical_time(None, "now")
        with self.assertRaises(rw.ReleaseWindowError):
            rw._canonical_time("not-a-time", "now")
        with self.assertRaises(rw.ReleaseWindowError):
            rw._sha("not-a-sha", "sha")
        with self.assertRaises(rw.ReleaseWindowError):
            rw._semver("1.2")
        with self.assertRaises(rw.ReleaseWindowError):
            rw.check_pull_request([])

        rendered = rw._render_gate("1.0.23", OLD_SHA, NOW, source_issue=900)
        self.assertIsNone(rw._gate_from_body("plain text"))
        self.assertIsNone(rw._window_from_body("plain text", OLD_SHA))
        with self.assertRaises(rw.ReleaseWindowError):
            rw._window_from_body("<!-- factory-release-window -->", OLD_SHA)

        gate, _, _ = rw._gate_from_body(rendered["body"])
        fingerprint = rw._gate_fingerprint(gate)
        self.assertFalse(rw._decision_a([], fingerprint))
        self.assertFalse(rw._decision_a([
            {"user": {"login": "someone"}, "body": "<!-- factory-human-decision {} -->"}
        ], fingerprint))

        option_b = {
            "gate_sha256": fingerprint,
            "option": "B",
            "version": 2,
        }
        self.assertFalse(rw._decision_a([
            {
                "user": {"login": "github-actions[bot]"},
                "body": (
                    "<!-- factory-human-decision "
                    + json.dumps(option_b, separators=(",", ":"), sort_keys=True)
                    + " -->"
                ),
            }
        ], fingerprint))

        with self.assertRaises(rw.ReleaseWindowError):
            rw._decision_a([
                {
                    "user": {"login": "github-actions[bot]"},
                    "body": "<!-- factory-human-decision {broken} -->",
                }
            ], fingerprint)

        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records("not-a-list")
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([{
                "issue": {
                    "number": 1,
                    "state": "open",
                    "body": "<!-- factory-release-window {} -->",
                },
                "comments": [],
            }])

    def test_execution_markers_reject_ambiguous_or_invalid_evidence(self) -> None:
        rendered = rw._render_gate("1.0.23", OLD_SHA, NOW, source_issue=900)
        approved = approved_comment(rendered["body"])

        invalid_execution = {
            "user": {"login": "github-actions[bot]"},
            "body": "<!-- factory-release-executed {broken} -->",
        }
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([
                gate_row(
                    number=918,
                    body=rendered["body"],
                    state="closed",
                    comments=[approved, invalid_execution],
                )
            ])

        def execution_comment(run_id: int) -> dict[str, object]:
            payload = {
                "version": 1,
                "sha": OLD_SHA,
                "run_id": run_id,
                "executed_at": "2026-10-03T10:05:00Z",
            }
            return {
                "user": {"login": "github-actions[bot]"},
                "body": (
                    "<!-- factory-release-executed "
                    + json.dumps(payload, separators=(",", ":"), sort_keys=True)
                    + " -->"
                ),
            }

        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([
                gate_row(
                    number=918,
                    body=rendered["body"],
                    state="closed",
                    comments=[approved, execution_comment(1), execution_comment(2)],
                )
            ])

        self.assertEqual(
            rw.plan_execution({
                "conclusion": "success",
                "now": "2026-10-03T10:30:00Z",
                "head_sha": OLD_SHA,
                "run_id": 123,
                "gates": [
                    gate_row(
                        number=918,
                        body=rendered["body"],
                        state="closed",
                        comments=[],
                    )
                ],
            }),
            {"action": "none", "reason": "no_approved_gate_for_run_sha"},
        )
        with self.assertRaises(rw.ReleaseWindowError):
            rw.plan_execution({
                "conclusion": "success",
                "now": "2026-10-03T10:30:00Z",
                "head_sha": OLD_SHA,
                "run_id": 0,
                "gates": [],
            })


if __name__ == "__main__":
    unittest.main()
