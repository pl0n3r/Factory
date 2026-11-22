"""Regresiones del carril Dependabot sin red ni credenciales."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from scripts.dependabot_lane import create_followup, _terminal_checks_green, _switch_running, reconcile, comment_stale, sweep

from scripts.dependabot_lane import LaneError, _age_over_seven_days, classify


SHA = "a" * 40
BOT = {
    "login": "dependabot[bot]", "id": 49699333, "type": "Bot",
    "html_url": "https://github.com/apps/dependabot",
    "avatar_url": "https://avatars.githubusercontent.com/in/29110?v=4",
}


def pr(*, user=None, head=SHA):
    return {
        "number": 99, "state": "open", "user": BOT if user is None else user,
        "head": {"sha": head, "repo": {"full_name": "pl0n3r/Factory"}},
        "base": {"ref": "main", "repo": {"full_name": "pl0n3r/Factory"}},
    }


def commit(kind="minor"):
    return {
        "author": {"login": "dependabot[bot]", "id": 49699333},
        "commit": {
            "verification": {"verified": True},
            "message": "chore(deps): update\n\nupdated-dependencies:\n"
                       "- dependency-name: example/package\n"
                       "  dependency-version: 2.0.0\n"
                       "  dependency-type: direct:production\n"
                       "  update-type: version-update:semver-" + kind,
        },
    }


def manifest(name="package-lock.json"):
    return {"filename": name, "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"}


def workflow():
    return {
        "filename": ".github/workflows/ci.yml", "status": "modified",
        "patch": "@@ -3 +3 @@\n"
                 "-  uses: actions/checkout@" + "1" * 40 + "\n"
                 "+  uses: actions/checkout@" + "2" * 40,
    }


class DependabotLaneTests(unittest.TestCase):
    def test_bot_lockfile_only_exempt_from_v3_and_contract(self):
        lane = classify(pr(), [manifest()], commit(), repo="pl0n3r/Factory", head=SHA)
        self.assertTrue(lane["dependabot"])
        self.assertEqual(lane["policy"], "auto")

    def test_bot_with_code_fails_closed(self):
        with self.assertRaisesRegex(LaneError, "Archivo fuera"):
            classify(pr(), [manifest(), manifest("src/app.py")],
                     commit(), repo="pl0n3r/Factory", head=SHA)

    def test_name_copy_with_other_app_id_fails_closed(self):
        fake = {**BOT, "avatar_url": "https://avatars.githubusercontent.com/in/99999?v=4"}
        with self.assertRaisesRegex(LaneError, "app_id"):
            classify(pr(user=fake), [manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)
        fake = {**BOT, "id": 12345}
        with self.assertRaises(LaneError):
            classify(pr(user=fake), [manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)

    def test_major_manual_and_canonical_followup(self):
        lane = classify(pr(), [manifest()], commit("major"),
                        repo="pl0n3r/Factory", head=SHA)
        self.assertEqual(lane["policy"], "manual")
        self.assertTrue(lane["major"])
        self.assertIn('example/package a la versión mayor 2.0.0', lane['major_target'])

    def test_major_generates_canonical_issue_once(self):
        repo = "pl0n3r/Factory"
        created = []

        def fake_api(_repo, path, _token, *, method="GET", payload=None):
            self.assertEqual(_repo, repo)
            if method == "GET":
                return {"incomplete_results": False, "total_count": 0, "items": []}
            created.append(payload)
            return {"number": 2180}

        with patch("scripts.dependabot_lane.api", side_effect=fake_api):
            number = create_followup(repo, 2107, SHA, "token", reason="major", paths=["package-lock.json"])
        self.assertEqual(number, 2180)
        self.assertEqual(len(created), 1)
        self.assertIn("Actualizar dependencias", created[0]["title"])
        self.assertIn("factory-dependabot-followup", created[0]["body"])
        self.assertIn("factory-acceptance", created[0]["body"])
        self.assertIn("estado: disponible", created[0]["labels"])
        self.assertIn("factory-plan-task", created[0]["body"])
        self.assertIn("package-lock.json", created[0]["body"])

        marker = '<!-- factory-dependabot-followup {"pr":2107,"repo":"pl0n3r/Factory","version":1} -->'
        def existing(*_args, **_kwargs):
            self.assertEqual(_kwargs.get("method", "GET"), "GET")
            return {"incomplete_results": False, "total_count": 1,
                    "items": [{"number": 2180, "body": marker}]}
        with patch("scripts.dependabot_lane.api", side_effect=existing):
            self.assertEqual(create_followup(repo, 2107, SHA, "token", reason="major", paths=["package-lock.json"]), 2180)

    def test_workflow_pins_require_manual_review(self):
        lane = classify(pr(), [workflow()], commit(),
                        repo="pl0n3r/Factory", head=SHA)
        self.assertEqual(lane["policy"], "manual")
        self.assertTrue(lane["workflow"])
        changed_command = {**workflow(), "patch": "@@ -1 +1 @@\n- run: echo safe\n+ run: curl evil"}
        with self.assertRaisesRegex(LaneError, "Workflow altera"):
            classify(pr(), [changed_command], commit(),
                     repo="pl0n3r/Factory", head=SHA)

    def test_foreign_pr_keeps_normal_gates(self):
        user = {**BOT, "login": "someone[bot]"}
        self.assertIsNone(classify(pr(user=user), [manifest()], commit(),
                                   repo="pl0n3r/Factory", head=SHA))

    def test_unknown_semver_and_unverified_commit_fail_closed(self):
        with self.assertRaises(LaneError):
            classify(pr(), [manifest()], commit("unknown"),
                     repo="pl0n3r/Factory", head=SHA)
        unsigned = commit()
        unsigned["commit"]["verification"]["verified"] = False
        with self.assertRaises(LaneError):
            classify(pr(), [manifest()], unsigned,
                     repo="pl0n3r/Factory", head=SHA)

    def test_head_ref_races_rejected(self):
        with self.assertRaises(LaneError):
            classify(pr(head="b" * 40), [manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)
        with self.assertRaises(LaneError):
            classify(pr(), [manifest(), manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)

    def test_green_minor_squashes_exact_head_without_bypass(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        request = pr()
        request["created_at"] = "2026-11-21T00:00:00Z"
        lane = {"dependabot": True, "policy": "auto", "head": SHA, "file_paths": ["package-lock.json"]}
        writes = []
        def api_stub(repo, path, token, *, method="GET", payload=None):
            writes.append((method, path, payload))
            self.assertEqual(repo, "pl0n3r/Factory")
            return {"merged": True, "sha": "b" * 40}
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane.read_exact",
                  return_value=(request, lane)) as reader,
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane._terminal_checks_green",
                  return_value=True),
            patch("scripts.dependabot_lane.api", side_effect=api_stub),
        ):
            result = reconcile("pl0n3r/Factory", 99, SHA, "token", now=now)
        self.assertTrue(result["merged"])
        self.assertEqual(reader.call_count, 2)
        self.assertEqual(writes, [("PUT", "/repos/pl0n3r/Factory/pulls/99/merge",
                                  {"sha": SHA, "merge_method": "squash"})])

    def test_red_minor_never_calls_merge(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        request = pr()
        request["created_at"] = "2026-11-21T00:00:00Z"
        lane = {"dependabot": True, "policy": "auto", "head": SHA}
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane.read_exact",
                  return_value=(request, lane)),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane._terminal_checks_green", return_value=False),
            patch("scripts.dependabot_lane.api",
                  side_effect=AssertionError("prohibido merge")),
        ):
            result = reconcile("pl0n3r/Factory", 99, SHA, "token", now=now)
        self.assertFalse(result["auto_merge_enabled"])
        self.assertFalse(result["followup_required"])

    def test_kill_switch_rejects_duplicate_keys_and_bool_version(self):
        base = {
            "number": 767, "state": "closed",
            "url": "https://api.github.com/repos/pl0n3r/Factory/issues/767",
            "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
            "user": {"login": "pl0n3r"},
            "body": '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->',
        }
        with patch("scripts.dependabot_lane.api", return_value=base):
            self.assertTrue(_switch_running("pl0n3r/Factory", "token"))
            base["body"] = '<!-- factory-unattended-kill-switch {"version":true,"state":"RUNNING","owner":"pl0n3r"} -->'
            self.assertFalse(_switch_running("pl0n3r/Factory", "token"))
            base["body"] = '<!-- factory-unattended-kill-switch {"version":1,"state":"PAUSED","state":"RUNNING","owner":"pl0n3r"} -->'
            self.assertFalse(_switch_running("pl0n3r/Factory", "token"))

    def test_stale_comment_is_idempotent(self):
        posted = []
        def fake_api(_repo, path, _token, *, method="GET", payload=None):
            if method == "POST":
                posted.append(payload["body"])
                return {"id": 123}
            return [{"body": posted[0]}] if posted else []
        with patch("scripts.dependabot_lane.api", side_effect=fake_api):
            self.assertTrue(comment_stale("pl0n3r/Factory", 2107, 2174, "token"))
            self.assertFalse(comment_stale("pl0n3r/Factory", 2107, 2174, "token"))
        self.assertEqual(len(posted), 1)
        self.assertIn("más de 7 días", posted[0])

    def test_schedule_sweeps_only_dependabot_with_global_guard(self):
        rows = [
            {"number": 101, "user": {"login": "pl0n3r"}, "head": {"sha": SHA}},
            {"number": 2107, "user": {"login": "dependabot[bot]"},
             "head": {"sha": SHA}},
        ]
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane.api", return_value=rows),
            patch("scripts.dependabot_lane.reconcile",
                  return_value={"pr": 2107}) as run,
        ):
            got = sweep("pl0n3r/Factory", "token",
                        now=datetime(2026, 11, 22, tzinfo=timezone.utc))
        self.assertEqual(got, [{"pr": 2107}])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[1], 2107)

    def test_workflow_run_ignores_human_pr_without_mutations(self):
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane.read_exact",
                  return_value=(pr(user={"login": "pl0n3r"}), {"dependabot": False})),
            patch("scripts.dependabot_lane.api",
                  side_effect=AssertionError("no mutar")),
        ):
            result = reconcile("pl0n3r/Factory", 99, SHA, "token",
                               now=datetime(2026, 11, 22, tzinfo=timezone.utc))
        self.assertEqual(result, {"dependabot": False, "skipped": True,
                                  "auto_merge_enabled": False})

    def test_reusable_keeps_workflow_call_only_and_trusted_v1_for_consumers(self):
        workflow = Path(".github/workflows/coordinacion.yml").read_text(encoding="utf-8")
        header = workflow.split("\npermissions:", 1)[0]
        self.assertIn("on:\n  workflow_call:", header)
        self.assertNotIn("  schedule:", header)
        self.assertNotIn("  workflow_run:", header)
        self.assertEqual(workflow.count("ref: ${{ job.workflow_sha }}"), 6)
        self.assertEqual(workflow.count("repository: ${{ job.workflow_repository }}"), 6)
        for name in ("dependabot", "dependabot-sweep"):
            block = workflow.split(f"  {name}:\n", 1)[1].split("\n  sweep:\n", 1)[0]
            self.assertIn("repository: pl0n3r/factory", block)
            self.assertIn("ref: v1", block)
            self.assertNotIn("github.event.pull_request.head.sha", block.split("steps:", 1)[0])
        self.assertIn("reconcile --repo", workflow)
        self.assertIn("sweep --repo", workflow)
        self.assertNotIn("pull_request_target:", header)

    def test_check_validar_requires_trusted_github_actions_app(self):
        check = {
            "id": 1, "name": "Validar", "head_sha": SHA, "status": "completed",
            "conclusion": "success", "app": {"slug": "github-actions", "id": 15368},
        }
        def fake_api(_repo, _path, _token, *, method="GET", payload=None):
            return {"total_count": 1, "check_runs": [check]}
        with patch("scripts.dependabot_lane.api", side_effect=fake_api):
            self.assertTrue(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
            check["app"] = {"slug": "untrusted", "id": 999}
            with self.assertRaisesRegex(LaneError, "App no autorizada"):
                _terminal_checks_green("pl0n3r/Factory", SHA, "token")

    def test_seven_day_threshold(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        pr_payload = {"created_at": (now - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        self.assertTrue(_age_over_seven_days(pr_payload, now=now))
        pr_payload["created_at"] = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(_age_over_seven_days(pr_payload, now=now))


if __name__ == "__main__":
    unittest.main()
