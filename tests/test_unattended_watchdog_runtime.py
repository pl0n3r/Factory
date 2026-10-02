#!/usr/bin/env python3
"""Regresiones del runtime programado del watchdog desatendido."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from scripts.unattended_watchdog_runtime import (
    ALERT_TITLE,
    AlertSpec,
    GitHubIssueClient,
    RuntimeValidationError,
    _https_json_request,
    collect_github_input,
    evaluate_runtime,
    main as runtime_main,
    parse_owned_alert,
    read_json,
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
        self.assertIn("cron: '*/15 * * * *'", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("timeout-minutes: 5", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("workflow_run", workflow)
        self.assertNotIn("--input", workflow)
        runtime = (ROOT / "scripts" / "unattended_watchdog_runtime.py").read_text(encoding="utf-8")
        self.assertIn("evaluate_unattended_kill_switch(client.get_issue(767))", runtime)
        self.assertIn("project_state_presence(", runtime)
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

            def get_branch_head(self, requested_branch):
                self.requested_branch = requested_branch
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
        self.assertEqual(client.requested_branch, branch)

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
                        "number": 769,
                        "title": "runtime",
                        "labels": [{"name": "estado: reservado"}],
                    }
                ]
            if method == "GET":
                return {"number": 767}
            return {"ok": True}

        client = GitHubIssueClient("token", "pl0n3r/Factory", transport)
        self.assertEqual(client.get_issue(767)["number"], 767)
        self.assertEqual(client.list_issue_comments(769), [])
        self.assertEqual(client.get_branch_head("trabajo/issue-769"), "a" * 40)
        self.assertEqual(len(client.list_open_work_items()), 1)
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

    def test_read_json_and_kill_switch_main_fail_closed(self):
        config_path = ROOT / "config" / "unattended-watchdog.json"
        self.assertEqual(read_json(str(config_path)), config())
        self.assertIsNone(read_json("/definitely/missing/watchdog.json"))

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
            code = runtime_main(["--config", str(config_path)])
        self.assertEqual(code, 1)
        self.assertEqual(fake.writes, [])


if __name__ == "__main__":
    unittest.main()
