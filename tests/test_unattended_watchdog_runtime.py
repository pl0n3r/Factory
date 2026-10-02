#!/usr/bin/env python3
"""Regresiones del runtime programado del watchdog desatendido."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from scripts.unattended_watchdog_runtime import (
    ALERT_TITLE,
    AlertSpec,
    COLLECTION_PAGE_SIZE,
    GitHubIssueClient,
    MAX_PAGES,
    MAX_STDIN_BYTES,
    RuntimeValidationError,
    _https_json_request,
    collect_github_input,
    evaluate_runtime,
    load_config,
    main as runtime_main,
    parse_owned_alert,
    read_stdin_json,
)

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
        self.assertIn("cron: '7,22,37,52 * * * *'", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("branches:", workflow)
        self.assertIn("- main", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("timeout-minutes: 5", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("workflow_run", workflow)
        self.assertNotIn("--input", workflow)
        self.assertNotIn("--config", workflow)
        runtime = (ROOT / "scripts" / "unattended_watchdog_runtime.py").read_text(encoding="utf-8")
        self.assertIn("evaluate_unattended_kill_switch(client.get_issue(767))", runtime)
        self.assertIn("project_state_presence(", runtime)
        self.assertIn('"state": "all"', runtime)
        self.assertIn('"labels": self._labels(spec)', runtime)

    def test_workflow_runs_watchdog_on_main_push_schedule_and_manual_only(self):
        workflow = (
            ROOT / ".github" / "workflows" / "unattended-watchdog.yml"
        ).read_text(encoding="utf-8")
        watchdog = workflow.split("  watchdog:", 1)[1].split("  daily-summary:", 1)[0]
        self.assertIn("push:", workflow)
        self.assertIn("branches:", workflow)
        self.assertIn("- main", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", watchdog)
        self.assertIn("github.event_name == 'push'", watchdog)
        self.assertIn("github.event_name == 'workflow_dispatch'", watchdog)
        self.assertIn("github.event_name == 'schedule'", watchdog)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("workflow_run", workflow)

    def test_watchdog_schedule_keeps_four_offset_quarter_hour_slots(self):
        workflow = (
            ROOT / ".github" / "workflows" / "unattended-watchdog.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("cron: '7,22,37,52 * * * *'", workflow)
        self.assertNotIn("cron: '*/15 * * * *'", workflow)
        minutes = (7, 22, 37, 52)
        gaps = tuple(
            (minutes[(index + 1) % len(minutes)] - minute) % 60
            for index, minute in enumerate(minutes)
        )
        self.assertEqual(gaps, (15, 15, 15, 15))
        self.assertTrue(set(minutes).isdisjoint({0, 15, 30, 45}))

    def test_main_push_never_runs_daily_summary(self):
        workflow = (
            ROOT / ".github" / "workflows" / "unattended-watchdog.yml"
        ).read_text(encoding="utf-8")
        daily = workflow.split("  daily-summary:", 1)[1]
        self.assertIn("github.event_name == 'schedule'", daily)
        self.assertIn("github.event.schedule == '0 13 * * *'", daily)
        self.assertNotIn("github.event_name == 'push'", daily)

    def test_workflow_preserves_concurrency_permissions_and_fail_closed_contract(self):
        workflow = (
            ROOT / ".github" / "workflows" / "unattended-watchdog.yml"
        ).read_text(encoding="utf-8")
        runtime = (
            ROOT / "scripts" / "unattended_watchdog_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn("group: unattended-watchdog-${{ github.repository_id }}", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn(
            "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            workflow,
        )
        self.assertNotIn("secrets.", workflow)
        self.assertIn(
            "evaluate_unattended_kill_switch(client.get_issue(767))",
            runtime,
        )
        self.assertIn("if switch.global_pause:", runtime)
        self.assertIn('"action": "BLOCKED"', runtime)

    def test_runtime_runbook_documents_push_schedule_and_rollback(self):
        runbook = (
            ROOT / "docs" / "unattended-watchdog-runtime.md"
        ).read_text(encoding="utf-8")
        self.assertIn("`push` a `main`", runbook)
        self.assertIn("07/22/37/52", runbook)
        self.assertIn("post-merge", runbook)
        self.assertIn("## Reversión", runbook)
        self.assertIn("Factory#815", runbook)

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


    def test_runtime_projects_live_github_state_source_fail_closed(self):
        reservation_id = "11111111-1111-4111-8111-111111111111"
        branch = "trabajo/issue-769"
        head = "d" * 40
        reservation_payload = {
            "version": 3,
            "owner": "pl0n3r",
            "reservation_id": reservation_id,
            "branch": branch,
            "active": True,
            "reason": "tomar",
            "acceptance_sha256": "a" * 64,
            "task_marker_sha256": "b" * 64,
            "task_paths": ["scripts/unattended_watchdog_runtime.py"],
            "task_depends_on": [767, 775],
        }
        state_payload = {
            "work_identity": "pl0n3r/Factory#769",
            "repository": "pl0n3r/Factory",
            "branch": branch,
            "head_sha": head,
            "reservation_id": reservation_id,
            "risk": "medium",
            "severity": "S3",
            "evidence": ["Factory#769", "source:#775"],
            "last_state": "implementing",
            "next_action": "run watchdog",
            "blockers": [],
            "updated_at": "2026-10-02T00:59:00Z",
        }
        comments = [
            {
                "user": {"login": "github-actions[bot]"},
                "body": (
                    "<!-- condor-reserva "
                    + json.dumps(reservation_payload, sort_keys=True, separators=(",", ":"))
                    + " -->"
                ),
                "created_at": "2026-10-02T00:58:30Z",
                "updated_at": "2026-10-02T00:58:30Z",
            },
            {
                "user": {"login": "pl0n3r"},
                "body": (
                    "<!-- factory-state "
                    + json.dumps(
                        {"version": 1, "state": state_payload},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + " -->"
                ),
                "created_at": "2026-10-02T00:59:30Z",
                "updated_at": "2026-10-02T00:59:30Z",
            },
        ]

        class FakeClient:
            repository = "pl0n3r/Factory"

            def list_open_work_items(self):
                return [{"number": 769, "labels": [{"name": "estado: reservado"}]}]

            def list_issue_comments(self, issue_number):
                self.issue_number = issue_number
                return comments

            def get_branch_head(self, issue_number):
                self.head_issue_number = issue_number
                return head

        client = FakeClient()
        runtime_input = collect_github_input(
            client,
            config(),
            "2026-10-02T01:00:00Z",
        )
        self.assertEqual(runtime_input["guard"]["action"], "BLOCKED")
        self.assertEqual(
            runtime_input["evidence"]["state"]["work_identity"],
            "pl0n3r/Factory#769",
        )
        self.assertEqual(
            runtime_input["evidence"]["presence"]["source"],
            "factory-state-github",
        )
        self.assertEqual(runtime_input["evidence"]["presence"]["sessions"], [])
        self.assertEqual(
            runtime_input["evidence"]["presence"]["capacity"]["freshness"],
            "unknown",
        )
        self.assertEqual(client.head_issue_number, 769)

        decision, plan = evaluate_runtime(
            config(),
            runtime_input["guard"],
            runtime_input["evidence"],
            {},
        )
        self.assertEqual(decision.action, "BLOCKED")
        self.assertTrue(
            any(item.code == "presence_insufficient" for item in decision.incidents)
        )
        self.assertGreaterEqual(len(plan.create), 1)

        stale_state = dict(state_payload)
        stale_state["updated_at"] = "2026-10-02T00:30:00Z"
        comments[1]["body"] = (
            "<!-- factory-state "
            + json.dumps(
                {"version": 1, "state": stale_state},
                sort_keys=True,
                separators=(",", ":"),
            )
            + " -->"
        )
        stale_input = collect_github_input(
            client,
            config(),
            "2026-10-02T01:00:00Z",
        )
        stale_decision, stale_plan = evaluate_runtime(
            config(),
            stale_input["guard"],
            stale_input["evidence"],
            {},
        )
        self.assertEqual(stale_decision.action, "BLOCKED")
        stale_runtime_alert = next(
            item for item in stale_plan.create if item.code == "state_stale"
        )
        current = {
            item.fingerprint: {"number": index + 80, "state": "open"}
            for index, item in enumerate(stale_plan.create)
        }
        historical_fingerprint = "e" * 64
        historical_number = 999
        self.assertNotIn(
            historical_fingerprint,
            {item.fingerprint for item in stale_decision.incidents},
        )
        current[historical_fingerprint] = {
            "number": historical_number,
            "state": "open",
        }
        repeated_decision, repeated_plan = evaluate_runtime(
            config(),
            stale_input["guard"],
            stale_input["evidence"],
            current,
        )
        self.assertEqual(repeated_decision.action, "BLOCKED")
        self.assertEqual(repeated_plan.create, ())
        self.assertEqual(repeated_plan.close, ())

        comments[1]["body"] = (
            "<!-- factory-state "
            + json.dumps(
                {"version": 1, "state": state_payload},
                sort_keys=True,
                separators=(",", ":"),
            )
            + " -->"
        )
        resolved_input = collect_github_input(
            client,
            config(),
            "2026-10-02T01:00:00Z",
        )
        resolved_decision, resolved_plan = evaluate_runtime(
            config(),
            resolved_input["guard"],
            resolved_input["evidence"],
            current,
        )
        self.assertEqual(resolved_decision.action, "BLOCKED")
        self.assertEqual(
            resolved_plan.close,
            tuple(
                sorted(
                    (
                        current[stale_runtime_alert.fingerprint]["number"],
                        historical_number,
                    )
                )
            ),
        )


    def test_owned_alert_rejects_malformed_duplicate_marker(self):
        fingerprint = "c" * 64
        body = (
            '<!-- factory-unattended-watchdog-alert '
            f'{{"version":1,"fingerprint":"{fingerprint}"}} -->'
            "\n<!-- factory-unattended-watchdog-alert broken -->"
        )
        self.assertIsNone(
            parse_owned_alert(
                {
                    "number": 11,
                    "state": "open",
                    "title": f"{ALERT_TITLE} UNKNOWN {fingerprint[:12]}",
                    "body": body,
                    "user": {"login": "github-actions[bot]"},
                }
            )
        )

    def test_github_client_transport_paths_and_mutations(self):
        calls = []
        fingerprint = "d" * 64
        owned = {
            "number": 7,
            "state": "open",
            "title": f"{ALERT_TITLE} UNKNOWN {fingerprint[:12]}",
            "body": (
                '<!-- factory-unattended-watchdog-alert '
                f'{{"version":1,"fingerprint":"{fingerprint}"}} -->'
            ),
            "user": {"login": "github-actions[bot]"},
            "labels": [],
        }

        def transport(method, path, payload):
            calls.append((method, path, payload))
            if "/git/ref/heads/" in path:
                return {"object": {"sha": "a" * 40}}
            if "/comments?" in path:
                return []
            if "/issues?" in path and "state=all" in path:
                return [owned]
            if "/issues?" in path:
                return [
                    {
                        "number": 700,
                        "title": f"{ALERT_TITLE} S1 own",
                        "labels": [{"name": "estado: disponible"}],
                    },
                    {
                        "number": 769,
                        "title": "runtime",
                        "labels": [{"name": "estado: reservado"}],
                    },
                    {
                        "number": 900,
                        "title": "ready work",
                        "labels": [{"name": "estado: disponible"}],
                    },
                ]
            if method == "GET":
                return {"number": 767}
            return {"ok": True}

        client = GitHubIssueClient("token", "pl0n3r/Factory", transport)
        self.assertEqual(client.get_issue(767)["number"], 767)
        self.assertEqual(client.list_issue_comments(769), [])
        self.assertEqual(client.get_branch_head(769), "a" * 40)
        self.assertEqual([item["number"] for item in client.list_open_work_items()], [769, 900])
        self.assertEqual(
            client.list_owned_alerts(),
            {fingerprint: {"number": 7, "state": "open"}},
        )
        spec = AlertSpec(
            fingerprint,
            "UNKNOWN",
            "runtime_source_blocked",
            ("test",),
            fingerprint,
        )
        client.create_alert(spec)
        client.reopen_alert(7, spec)
        client.close_alert(7)
        self.assertTrue(
            all(path.startswith("/repos/pl0n3r/Factory/") for _, path, _ in calls)
        )
        with self.assertRaises(RuntimeValidationError):
            client._request("GET", "/repos/other/repo/issues")
        with self.assertRaises(RuntimeValidationError):
            GitHubIssueClient("", "pl0n3r/Factory")
        with self.assertRaises(RuntimeValidationError):
            GitHubIssueClient("token", "bad repo")
        with self.assertRaises(RuntimeValidationError):
            GitHubIssueClient("token", "pl0n3r/other")

    def test_owned_alert_scan_uses_canonical_creator_and_bounded_pages(self):
        calls = []
        fingerprint = "1" * 64
        owned = {
            "number": 7,
            "state": "open",
            "title": f"{ALERT_TITLE} S3 {fingerprint[:12]}",
            "body": (
                '<!-- factory-unattended-watchdog-alert '
                f'{{"version":1,"fingerprint":"{fingerprint}"}} -->'
            ),
            "user": {"login": "github-actions[bot]"},
        }

        def transport(method, path, payload):
            calls.append((method, path, payload))
            if "state=all" in path:
                return [owned]
            raise AssertionError(f"unexpected request: {path}")

        client = GitHubIssueClient("token", "pl0n3r/Factory", transport)
        self.assertEqual(
            client.list_owned_alerts(),
            {fingerprint: {"number": 7, "state": "open"}},
        )
        self.assertEqual(len(calls), 1)
        path = calls[0][1]
        self.assertIn("state=all", path)
        self.assertIn("creator=github-actions%5Bbot%5D", path)
        self.assertIn(f"per_page={COLLECTION_PAGE_SIZE}", path)
        self.assertNotIn("per_page=100", path)

    def test_bounded_pagination_preserves_thousand_item_budget(self):
        self.assertEqual(COLLECTION_PAGE_SIZE, 50)
        self.assertEqual(MAX_PAGES, 20)
        self.assertEqual(COLLECTION_PAGE_SIZE * MAX_PAGES, 1000)
        calls = []

        def page_number(path):
            return int(path.rsplit("page=", 1)[1])

        def transport(method, path, payload):
            calls.append(path)
            page = page_number(path)
            count = COLLECTION_PAGE_SIZE if page < MAX_PAGES else COLLECTION_PAGE_SIZE - 1
            return [
                {
                    "number": page * 1000 + index,
                    "state": "open",
                    "title": "not-owned",
                    "body": "",
                    "user": {"login": "github-actions[bot]"},
                }
                for index in range(count)
            ]

        client = GitHubIssueClient("token", "pl0n3r/Factory", transport)
        self.assertEqual(client.list_owned_alerts(), {})
        self.assertEqual(len(calls), MAX_PAGES)
        self.assertTrue(
            all(f"per_page={COLLECTION_PAGE_SIZE}" in path for path in calls)
        )

        def saturated(method, path, payload):
            page = page_number(path)
            return [
                {
                    "number": page * 1000 + index,
                    "state": "open",
                    "title": "not-owned",
                    "body": "",
                    "user": {"login": "github-actions[bot]"},
                }
                for index in range(COLLECTION_PAGE_SIZE)
            ]

        with self.assertRaisesRegex(
            RuntimeValidationError,
            "github_issue_listing_truncated",
        ):
            GitHubIssueClient(
                "token",
                "pl0n3r/Factory",
                saturated,
            ).list_owned_alerts()

    def test_large_issue_inventory_does_not_require_unfiltered_hundred_item_page(self):
        fingerprint = "2" * 64
        owned = {
            "number": 8,
            "state": "closed",
            "title": f"{ALERT_TITLE} S3 {fingerprint[:12]}",
            "body": (
                '<!-- factory-unattended-watchdog-alert '
                f'{{"version":1,"fingerprint":"{fingerprint}"}} -->'
            ),
            "user": {"login": "github-actions[bot]"},
        }

        def transport(method, path, payload):
            if "state=all" not in path:
                raise AssertionError(f"unexpected request: {path}")
            if "creator=github-actions%5Bbot%5D" not in path or "per_page=100" in path:
                raise RuntimeValidationError("github_response_too_large")
            return [owned]

        client = GitHubIssueClient("token", "pl0n3r/Factory", transport)
        self.assertEqual(
            client.list_owned_alerts(),
            {fingerprint: {"number": 8, "state": "closed"}},
        )

    def test_oversized_github_response_remains_fail_closed(self):
        class Response:
            status = 200

            def read(self, size):
                return b"x" * (1024 * 1024 + 1)

        class Connection:
            def __init__(self, host, timeout):
                self.host = host
                self.timeout = timeout

            def request(self, method, path, body=None, headers=None):
                self.path = path

            def getresponse(self):
                return Response()

            def close(self):
                self.closed = True

        target = "scripts.unattended_watchdog_runtime.http.client.HTTPSConnection"
        with patch(target, Connection), self.assertRaisesRegex(
            RuntimeValidationError,
            "github_response_too_large",
        ):
            _https_json_request(
                "token",
                "GET",
                "/repos/pl0n3r/Factory/issues/1",
                None,
            )

    def test_fixed_host_transport_success_and_failures(self):
        class Response:
            def __init__(self, status=200, raw=b'{"ok":true}'):
                self.status = status
                self.raw = raw

            def read(self, size):
                return self.raw

        class Connection:
            response = Response()
            seen = []

            def __init__(self, host, timeout):
                self.host = host
                self.timeout = timeout

            def request(self, method, path, body=None, headers=None):
                self.seen.append((self.host, method, path, body, headers))

            def getresponse(self):
                return self.response

            def close(self):
                self.closed = True

        target = "scripts.unattended_watchdog_runtime.http.client.HTTPSConnection"
        with patch(target, Connection):
            result = _https_json_request(
                "token",
                "GET",
                "/repos/pl0n3r/Factory/issues/1",
                None,
            )
            self.assertEqual(result, {"ok": True})
            self.assertEqual(Connection.seen[-1][0], "api.github.com")

            with self.assertRaisesRegex(
                RuntimeValidationError,
                "github_path_outside_repository",
            ):
                _https_json_request(
                    "token",
                    "GET",
                    "/repos/pl0n3r/other/issues/1",
                    None,
                )

            Connection.response = Response(status=500)
            with self.assertRaisesRegex(
                RuntimeValidationError,
                "github_request_failed",
            ):
                _https_json_request(
                    "token",
                    "GET",
                    "/repos/pl0n3r/Factory/issues/1",
                    None,
                )

            Connection.response = Response(raw=b"x" * (1024 * 1024 + 1))
            with self.assertRaisesRegex(
                RuntimeValidationError,
                "github_response_too_large",
            ):
                _https_json_request(
                    "token",
                    "GET",
                    "/repos/pl0n3r/Factory/issues/1",
                    None,
                )

            Connection.response = Response(raw=b"not-json")
            with self.assertRaisesRegex(
                RuntimeValidationError,
                "github_response_invalid_json",
            ):
                _https_json_request(
                    "token",
                    "GET",
                    "/repos/pl0n3r/Factory/issues/1",
                    None,
                )

        class BrokenConnection(Connection):
            def request(self, method, path, body=None, headers=None):
                raise OSError("network down")

        with patch(target, BrokenConnection):
            with self.assertRaisesRegex(
                RuntimeValidationError,
                "github_request_failed",
            ):
                _https_json_request(
                    "token",
                    "GET",
                    "/repos/pl0n3r/Factory/issues/1",
                    None,
                )

    def test_fixed_config_stdin_and_kill_switch_main_fail_closed(self):
        self.assertEqual(load_config(), config())
        with patch(
            "scripts.unattended_watchdog_runtime.CONFIG_PATH",
            ROOT / "config" / "does-not-exist.json",
        ):
            self.assertIsNone(load_config())

        payload = {"guard": guard(), "evidence": evidence()}
        self.assertEqual(
            read_stdin_json(io.StringIO(json.dumps(payload))),
            payload,
        )
        self.assertIsNone(read_stdin_json(io.StringIO("not-json")))
        self.assertIsNone(read_stdin_json(io.StringIO('{"x":1,"x":2}')))
        self.assertIsNone(read_stdin_json(io.StringIO("x" * (MAX_STDIN_BYTES + 1))))

        runtime_source = (
            ROOT / "scripts" / "unattended_watchdog_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('parser.add_argument("--config"', runtime_source)
        self.assertNotIn('parser.add_argument("--input")', runtime_source)
        self.assertNotIn("_repository_json_path", runtime_source)
        self.assertIn('parser.add_argument("--input-stdin"', runtime_source)
        self.assertIn("CONFIG_PATH.read_text", runtime_source)

        class PausedClient:
            repository = "pl0n3r/Factory"

            def __init__(self):
                self.writes = []

            def list_owned_alerts(self):
                return {}

            def list_open_work_items(self):
                return []

            def get_issue(self, number):
                return {
                    "number": 767,
                    "url": "https://api.github.com/repos/pl0n3r/Factory/issues/767",
                    "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
                    "user": {"login": "pl0n3r"},
                    "body": (
                        '<!-- factory-unattended-kill-switch '
                        '{"version":1,"state":"PAUSED","owner":"pl0n3r"} -->'
                    ),
                }

            def create_alert(self, spec):
                self.writes.append(("create", spec))

            def reopen_alert(self, number, spec):
                self.writes.append(("reopen", number, spec))

            def close_alert(self, number):
                self.writes.append(("close", number))

        fake = PausedClient()
        target = "scripts.unattended_watchdog_runtime.GitHubIssueClient"
        with patch(target, return_value=fake), patch.dict(
            os.environ,
            {
                "GH_TOKEN": "token",
                "GITHUB_REPOSITORY": "pl0n3r/Factory",
            },
            clear=False,
        ):
            code = runtime_main([])
        self.assertEqual(code, 1)
        self.assertEqual(fake.writes, [])


    def test_ready_issue_without_canonical_ready_since_fails_closed(self):
        class ReadyClient:
            repository = "pl0n3r/Factory"

            def list_open_work_items(self):
                return [
                    {"number": 769, "labels": [{"name": "estado: reservado"}]},
                    {"number": 900, "labels": [{"name": "estado: disponible"}]},
                ]

            def list_issue_comments(self, issue_number):
                return []

            def get_branch_head(self, branch):
                raise AssertionError("ready work must block before branch lookup")

        runtime_input = collect_github_input(
            ReadyClient(),
            config(),
            "2026-10-02T01:00:00Z",
        )
        self.assertEqual(runtime_input["guard"]["action"], "BLOCKED")
        self.assertIsNone(runtime_input["evidence"])
        decision, plan = evaluate_runtime(
            config(),
            runtime_input["guard"],
            runtime_input["evidence"],
            {},
        )
        self.assertEqual(decision.action, "BLOCKED")
        self.assertNotEqual(decision.action, "ALLOW")
        self.assertGreaterEqual(len(plan.create), 1)


if __name__ == "__main__":
    unittest.main()
