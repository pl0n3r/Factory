#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
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


def legacy_gate_body(version: str, sha: str) -> str:
    rendered = rw._render_gate(version, sha, NOW, source_issue=900)
    return "\n".join(
        line
        for line in rendered["body"].splitlines()
        if "factory-release-window" not in line
        and "factory-release-rearm" not in line
    )


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

    def test_legacy_approved_gate_without_window_rearms_new_head_without_reusing_decision(self) -> None:
        legacy = legacy_gate_body("1.0.23", OLD_SHA)
        row = gate_row(
            number=918,
            body=legacy,
            state="closed",
            comments=[approved_comment(legacy)],
        )

        records = rw.gate_records([row])
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["window"])
        self.assertTrue(records[0]["approved_a"])

        planned = rw.plan_rearm({
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
            "gates": [row],
        })
        self.assertEqual(planned["action"], "create_gate")
        self.assertEqual(planned["source_issue"], 918)
        self.assertEqual(planned["source_sha"], OLD_SHA)
        self.assertEqual(planned["sha"], NEW_SHA)
        self.assertIn('"safe_default":"B"', planned["body"])
        self.assertNotIn("factory-human-decision", planned["body"])

    def test_legacy_open_gate_without_window_rearms_new_head(self) -> None:
        legacy = legacy_gate_body("1.0.23", OLD_SHA)
        planned = rw.plan_rearm({
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
            "gates": [gate_row(number=918, body=legacy, state="open")],
        })

        self.assertEqual(planned["action"], "create_gate")
        self.assertEqual(planned["source_issue"], 918)
        self.assertEqual(planned["source_sha"], OLD_SHA)
        self.assertEqual(planned["sha"], NEW_SHA)

    def test_legacy_gate_without_window_does_not_freeze_retroactively(self) -> None:
        legacy = legacy_gate_body("1.0.23", OLD_SHA)
        records = rw.gate_records([
            gate_row(
                number=918,
                body=legacy,
                state="closed",
                comments=[approved_comment(legacy)],
            )
        ])

        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["window"])
        self.assertIsNone(rw.freeze_gate(records, NOW))

    def test_invalid_window_intent_stays_fail_closed_while_modern_window_remains_supported(self) -> None:
        self.assertFalse(rw._legacy_factory_release_intent("plain text"))
        self.assertTrue(
            rw._legacy_factory_release_intent(
                '<!-- factory-human-gate {broken factory-release} -->'
            )
        )
        self.assertFalse(
            rw._legacy_factory_release_intent(
                '<!-- factory-human-gate {broken} -->'
            )
        )

        unrelated_legacy = (
            '<!-- factory-human-gate '
            '{"category":"product-direction","context":"legacy schema"} -->'
        )
        self.assertEqual(
            rw.gate_records([
                gate_row(number=700, body=unrelated_legacy, state="closed")
            ]),
            [],
        )

        obsolete_release_legacy = (
            '<!-- factory-human-gate '
            '{"category":"factory-release","context":"Factory v1.0.23 main@'
            + OLD_SHA
            + '","options":[{"id":"A","label":"Publicar"},{"id":"B","label":"No publicar"}],'
            '"safe_default":"B"} -->'
        )
        self.assertEqual(
            rw.gate_records([
                gate_row(number=470, body=obsolete_release_legacy, state="closed")
            ]),
            [],
        )

        legacy = legacy_gate_body("1.0.23", OLD_SHA)
        malformed = legacy + "\n<!-- factory-release-window -->"
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([gate_row(number=918, body=malformed)])

        modern = rw._render_gate("1.0.23", OLD_SHA, NOW, source_issue=918)
        records = rw.gate_records([gate_row(number=927, body=modern["body"])])
        self.assertEqual(len(records), 1)
        self.assertIsNotNone(records[0]["window"])
        active = rw.freeze_gate(
            records,
            datetime(2026, 10, 3, 10, 30, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(active)
        self.assertEqual(active["number"], 927)

    def test_new_version_bootstraps_from_latest_canonical_release_gate(self) -> None:
        older_sha = "3" * 40
        older = rw._render_gate("1.0.25", older_sha, NOW, source_issue=900)
        latest = rw._render_gate("1.0.26", OLD_SHA, NOW, source_issue=995)

        planned = rw.plan_rearm({
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.27",
            "gates": [
                gate_row(number=990, body=older["body"], state="closed"),
                gate_row(number=997, body=latest["body"], state="open"),
            ],
        })

        self.assertEqual(planned["action"], "create_gate")
        self.assertEqual(planned["reason"], "new_version_gate")
        self.assertEqual(planned["source_issue"], 997)
        self.assertEqual(planned["source_sha"], OLD_SHA)
        self.assertEqual(planned["sha"], NEW_SHA)
        self.assertEqual(planned["version"], "1.0.27")
        self.assertIn("Factory **1.0.27**", planned["body"])
        self.assertIn(f"main@{NEW_SHA}", planned["body"])
        self.assertIn('"safe_default":"B"', planned["body"])
        self.assertNotIn("factory-human-decision", planned["body"])
        self.assertNotIn("factory-release-executed", planned["body"])

        record = rw.gate_records([
            gate_row(number=1000, body=planned["body"], state="open")
        ])[0]
        self.assertEqual(record["version"], "1.0.27")
        self.assertFalse(record["approved_a"])
        self.assertIsNone(record["executed"])

    def test_new_version_bootstrap_never_inherits_prior_decision_or_execution(self) -> None:
        prior = rw._render_gate("1.0.26", OLD_SHA, NOW, source_issue=995)
        parsed = rw._gate_from_body(prior["body"])
        assert parsed is not None
        prior_gate, _, _ = parsed
        fingerprint = rw._gate_fingerprint(prior_gate)

        def decision(option: str) -> dict[str, object]:
            payload = {
                "gate_sha256": fingerprint,
                "option": option,
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

        execution = {
            "version": 1,
            "sha": OLD_SHA,
            "run_id": 9876,
            "executed_at": "2026-10-03T10:05:00Z",
        }
        executed_comment = {
            "user": {"login": "github-actions[bot]"},
            "body": (
                "<!-- factory-release-executed "
                + json.dumps(execution, separators=(",", ":"), sort_keys=True)
                + " -->"
            ),
        }

        variants = (
            ("open", "open", []),
            ("closed-b", "closed", [decision("B")]),
            ("closed-a", "closed", [decision("A")]),
            ("executed", "closed", [decision("A"), executed_comment]),
        )
        for name, state, comments in variants:
            with self.subTest(name=name):
                planned = rw.plan_rearm({
                    "now": "2026-10-03T10:20:00Z",
                    "main_sha": NEW_SHA,
                    "version": "1.0.27",
                    "gates": [
                        gate_row(
                            number=997,
                            body=prior["body"],
                            state=state,
                            comments=comments,
                        )
                    ],
                })
                self.assertEqual(planned["action"], "create_gate")
                self.assertEqual(planned["reason"], "new_version_gate")
                self.assertEqual(planned["source_issue"], 997)
                self.assertNotIn("factory-human-decision", planned["body"])
                self.assertNotIn("factory-release-executed", planned["body"])

                fresh = rw.gate_records([
                    gate_row(number=1000, body=planned["body"], state="open")
                ])[0]
                self.assertFalse(fresh["approved_a"])
                self.assertIsNone(fresh["executed"])

    def test_new_version_without_any_release_history_stays_fail_closed(self) -> None:
        self.assertEqual(
            rw.plan_rearm({
                "now": "2026-10-03T10:20:00Z",
                "main_sha": NEW_SHA,
                "version": "1.0.27",
                "gates": [],
            }),
            {"action": "none", "reason": "no_prior_release_gate"},
        )

    def test_existing_version_keeps_same_version_rearm_semantics(self) -> None:
        current = rw._render_gate("1.0.27", OLD_SHA, NOW, source_issue=997)

        self.assertEqual(
            rw.plan_rearm({
                "now": "2026-10-03T10:20:00Z",
                "main_sha": NEW_SHA,
                "version": "1.0.27",
                "gates": [
                    gate_row(
                        number=998,
                        body=current["body"],
                        state="closed",
                    )
                ],
            }),
            {"action": "none", "reason": "latest_gate_not_approved"},
        )

        self.assertEqual(
            rw.plan_rearm({
                "now": "2026-10-03T10:20:00Z",
                "main_sha": OLD_SHA,
                "version": "1.0.27",
                "gates": [
                    gate_row(
                        number=998,
                        body=current["body"],
                        state="open",
                    )
                ],
            }),
            {"action": "none", "reason": "current_head_already_has_gate"},
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

        self.assertNotIn("push:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("workflow_run:", workflow)
        self.assertIn("Release Factory v1.x", workflow)
        self.assertIn("python3 scripts/release_window.py request", workflow)
        self.assertIn("python3 scripts/release_window.py workflow-run", workflow)
        self.assertIn("issues: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("factory-release-executed", workflow)
        self.assertIn("factory-release-owner-request", workflow)

        self.assertIn("release_window:", factory_ci)
        self.assertIn("issues: read", factory_ci)
        self.assertIn("pull-requests: read", factory_ci)
        self.assertIn("python3 scripts/release_window.py pr-check", factory_ci)
        coordination = factory_ci.split("  coordinacion:", 1)[1].split("  acceptance:", 1)[0]
        self.assertIn("needs: [release_window]", coordination)
        self.assertIn("needs: [workflows, scripts, coordinacion, acceptance]", factory_ci)


    def test_workflow_projects_minimal_release_evidence_before_parser(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "release-window.yml"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            workflow.count("| {number, state, title, body, updated_at}"),
            2,
        )
        self.assertEqual(
            workflow.count('select(.user.login == "github-actions[bot]")'),
            2,
        )
        self.assertEqual(
            workflow.count('contains("factory-human-decision")'),
            2,
        )
        self.assertEqual(
            workflow.count('contains("factory-release-executed")'),
            2,
        )
        self.assertEqual(
            workflow.count(
                '| {user: {login: .user.login}, body: (.body // "")}'
            ),
            2,
        )
        self.assertNotIn(
            "--slurp | jq 'add // []' > /tmp/release-comments.json",
            workflow,
        )

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


    def test_cli_dispatches_all_modes_and_reports_invalid_json(self) -> None:
        def cli(mode: str, payload: object | None = None, raw: str | None = None):
            stdout = io.StringIO()
            stderr = io.StringIO()
            data = raw if raw is not None else json.dumps(payload, separators=(",", ":"))
            with (
                patch.object(rw.sys, "argv", ["release_window.py", mode]),
                patch.object(rw.sys, "stdin", io.StringIO(data)),
                patch.object(rw.sys, "stdout", stdout),
                patch.object(rw.sys, "stderr", stderr),
            ):
                code = rw.main()
            return code, stdout.getvalue(), stderr.getvalue()

        code, out, err = cli("summary", {"gates": []})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), None)
        self.assertEqual(err, "")

        code, out, _ = cli("workflow-run", {"conclusion": "failure"})
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(out),
            {"action": "none", "reason": "release_run_not_successful"},
        )

        code, out, _ = cli("push", {
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
            "gates": [],
        })
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["reason"], "no_prior_release_gate")

        rendered = rw._render_gate("1.0.23", OLD_SHA, NOW, source_issue=918)
        code, out, _ = cli("pr-check", {
            "now": "2026-10-03T10:10:00Z",
            "gates": [gate_row(number=918, body=rendered["body"])],
            "pr": {"number": 922, "body": ""},
            "work_issue": {
                "number": 922,
                "state": "open",
                "labels": [{"name": "prioridad: alta"}],
            },
        })
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(out)["allowed"])

        code, out, err = cli("summary", raw="{broken")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ERROR: JSON inválido.", err)


if __name__ == "__main__":
    unittest.main()
