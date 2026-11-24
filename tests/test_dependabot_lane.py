"""Regresiones del carril Dependabot sin red ni credenciales."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
import os
import io
import json
from urllib.error import URLError
from pathlib import Path
from unittest.mock import patch

from scripts.dependabot_lane import create_followup, _terminal_checks_green, _switch_running, reconcile, comment_stale, sweep

from scripts.dependabot_lane import LaneError, _age_over_seven_days, classify, api, read_exact, classify_from_api, main
import scripts.dependabot_lane as lane


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
            self.assertEqual(repo, "pl0n3r/GrindFlow")
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
            patch("scripts.dependabot_lane._postmerge_exact_main_ci",
                  return_value={"run_id": 13, "head_sha": "b" * 40,
                                "validate": "success"}) as postmerge,
        ):
            result = reconcile("pl0n3r/GrindFlow", 99, SHA, "token", now=now)
        self.assertTrue(result["merged"])
        self.assertEqual(reader.call_count, 2)
        postmerge.assert_called_once_with("pl0n3r/GrindFlow", "b" * 40, "token")
        self.assertEqual(result["post_merge_ci"]["validate"], "success")
        self.assertEqual(writes, [("PUT", "/repos/pl0n3r/GrindFlow/pulls/99/merge",
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

    def test_consumer_exact_required_ci_gate(self):
        # Cada consumidor tiene su propio contexto CI obligatorio. Los
        # fixtures son independientes para que un negativo no contamine otro.
        cases = {
            "pl0n3r/Factory": ("Validar",),
            "pl0n3r/Condor": ("Validar",),
            "pl0n3r/ControlBot": ("Validar",),
            "pl0n3r/AutoFactory": ("Validate / Pruebas y smoke Chrome",),
            "pl0n3r/GrindFlow": ("validate",),
            "pl0n3r/FactoryRunner": ("validate", "ci / Validar"),
        }

        def check(name, ident, *, status="completed", conclusion="success"):
            return {
                "name": name, "id": ident, "head_sha": SHA,
                "status": status, "conclusion": conclusion,
                "app": {"slug": "github-actions", "id": 15368},
            }

        for repo, required in cases.items():
            # Incluye siempre un check no canónico en verde.
            passing = [
                *[check(name, index + 1) for index, name in enumerate(required)],
                check("Other passing check", 10),
            ]
            for scenario in ("success", "repo_casefold", "missing", "skipped", "pending"):
                rows = [dict(row) for row in passing]
                checked_repo = repo.swapcase() if scenario == "repo_casefold" else repo
                if scenario == "missing":
                    rows = [row for row in rows if row["name"] != required[0]]
                elif scenario == "skipped":
                    rows[0]["conclusion"] = "skipped"
                elif scenario == "pending":
                    rows[0]["status"] = "in_progress"
                    rows[0]["conclusion"] = None

                def response(_repo, _path, _token, *, method="GET", payload=None):
                    return {"total_count": len(rows), "check_runs": rows}

                with self.subTest(repo=repo, scenario=scenario):
                    with patch.object(lane, "api", side_effect=response):
                        self.assertIs(
                            _terminal_checks_green(checked_repo, SHA, "token"),
                            scenario in ("success", "repo_casefold"),
                        )

            # FactoryRunner exige dos gates: faltar cualquiera debe fallar.
            if len(required) > 1:
                rows = [row for row in passing if row["name"] != required[-1]]

                def response(_repo, _path, _token, *, method="GET", payload=None):
                    return {"total_count": len(rows), "check_runs": rows}

                with self.subTest(repo=repo, scenario="missing-second-required"):
                    with patch.object(lane, "api", side_effect=response):
                        self.assertFalse(_terminal_checks_green(repo, SHA, "token"))

    def test_consumer_gate_rejects_wrong_repo_or_untrusted_check(self):
        def check(name, ident, *, issuer=None, conclusion="success", head=SHA):
            return {"name": name, "id": ident, "head_sha": head,
                    "status": "completed", "conclusion": conclusion,
                    "app": issuer or {"slug": "github-actions", "id": 15368}}
        rows = [check("validate", 1), check("Other check", 2)]
        def response(_repo, _path, _token, *, method="GET", payload=None):
            return {"total_count": len(rows), "check_runs": rows}
        with patch.object(lane, "api", side_effect=response):
            for repo in ("pl0n3r/brvtal", "pl0n3r/Unknown", "other/GrindFlow"):
                with self.subTest(repo=repo), self.assertRaisesRegex(
                    LaneError, "sin gate"
                ):
                    _terminal_checks_green(repo, SHA, "token")
            rows[0] = check("Validar", 1)
            self.assertFalse(_terminal_checks_green("pl0n3r/GrindFlow", SHA, "token"))
            rows[0] = check("validate", 1, issuer={"slug": "other", "id": 10})
            with self.assertRaisesRegex(LaneError, "App no autorizada"):
                _terminal_checks_green("pl0n3r/GrindFlow", SHA, "token")
            rows[0] = check("validate", 1, head="b" * 40)
            with self.assertRaisesRegex(LaneError, "HEAD incorrecto"):
                _terminal_checks_green("pl0n3r/GrindFlow", SHA, "token")
            rows[0] = check("validate", 1)
            rows.append(check("validate", 1, conclusion="failure"))
            with self.assertRaisesRegex(LaneError, "homónimo contradictorio"):
                _terminal_checks_green("pl0n3r/GrindFlow", SHA, "token")
            rows.pop()
            rows[1]["conclusion"] = "failure"
            self.assertFalse(_terminal_checks_green("pl0n3r/GrindFlow", SHA, "token"))
            rows[1]["conclusion"] = "success"
            rows[0]["conclusion"] = "neutral"
            self.assertFalse(_terminal_checks_green("pl0n3r/GrindFlow", SHA, "token"))
            # Un ID antiguo contradictorio no debe escapar porque otro
            # intento con mayor ID haya quedado en latest.
            rows[:] = [
                check("validate", 3),
                check("validate", 1, conclusion="failure"),
                check("validate", 1),
            ]
            with self.assertRaisesRegex(LaneError, "homónimo contradictorio"):
                _terminal_checks_green("pl0n3r/GrindFlow", SHA, "token")
            # Reintentos diferentes son válidos si el último está verde.
            rows[:] = [check("validate", 1, conclusion="failure"), check("validate", 3)]
            self.assertTrue(_terminal_checks_green("pl0n3r/GrindFlow", SHA, "token"))

    def test_postmerge_exact_main_dispatch_and_success(self):
        merge_sha = "b" * 40
        workflow = "grindflow-ci.yml"
        sent = []
        run = {
            "id": 1723, "name": "GrindFlow CI", "event": "workflow_dispatch",
            "head_branch": "main", "head_sha": merge_sha,
            "status": "completed", "conclusion": "success",
        }

        def mocked_api(repo, path, token, *, method="GET", payload=None):
            self.assertEqual(repo, "pl0n3r/GrindFlow")
            if path.endswith("/git/ref/heads/main"):
                return {"object": {"sha": merge_sha}}
            if "/dispatches" in path:
                self.assertEqual(method, "POST")
                self.assertEqual(payload, {"ref": "main"})
                sent.append(path)
                return None
            if "/runs?event=" in path:
                return {"total_count": 1 if sent else 0,
                        "workflow_runs": [run] if sent else []}
            if path.endswith("/actions/runs/1723"):
                return run
            if path.endswith("/actions/runs/1723/jobs?per_page=100"):
                return {"total_count": 1, "jobs": [{
                    "name": "validate", "head_sha": merge_sha,
                    "status": "completed", "conclusion": "success",
                }]}
            raise AssertionError(path)

        with patch("scripts.dependabot_lane.api", side_effect=mocked_api):
            result = lane._postmerge_exact_main_ci("pl0n3r/GrindFlow", merge_sha, "token")
        self.assertEqual(result, {"run_id": 1723, "head_sha": merge_sha,
                                  "validate": "success"})
        self.assertEqual(len(sent), 1)

    def test_postmerge_rejects_wrong_sha_or_failure(self):
        merge_sha = "b" * 40
        for fault in ("wrong-main", "wrong-run-sha", "failed-run", "failed-validate",
                      "duplicate-run"):
            with self.subTest(fault=fault):
                posted = []
                run = {
                    "id": 1723, "name": "GrindFlow CI", "event": "workflow_dispatch",
                    "head_branch": "main", "head_sha": (
                        "c" * 40 if fault == "wrong-run-sha" else merge_sha),
                    "status": "completed", "conclusion": (
                        "failure" if fault == "failed-run" else "success"),
                }

                def fake_api(_repo, path, _token, *, method="GET", payload=None):
                    if path.endswith("/git/ref/heads/main"):
                        return {"object": {"sha": (
                            "c" * 40 if fault == "wrong-main" else merge_sha)}}
                    if path.endswith("/dispatches"):
                        posted.append(path)
                        return None
                    if "/runs?event=" in path:
                        rows = [run] if posted else []
                        if posted and fault == "duplicate-run":
                            rows.append({**run, "id": 1724})
                        return {"total_count": len(rows), "workflow_runs": rows}
                    if path.endswith("/actions/runs/1723"):
                        return run
                    if path.endswith("/actions/runs/1723/jobs?per_page=100"):
                        return {"total_count": 1, "jobs": [{
                            "name": "validate", "head_sha": merge_sha,
                            "status": "completed", "conclusion": (
                                "failure" if fault == "failed-validate" else "success"),
                        }]}
                    raise AssertionError(path)

                with patch("scripts.dependabot_lane.api", side_effect=fake_api):
                    with self.assertRaises(LaneError):
                        lane._postmerge_exact_main_ci(
                            "pl0n3r/GrindFlow", merge_sha, "token")
                if fault == "wrong-main":
                    self.assertEqual(posted, [])

        with patch("scripts.dependabot_lane.api", side_effect=AssertionError("no dispatch")):
            with self.assertRaisesRegex(LaneError, "capacidad"):
                lane._postmerge_exact_main_ci("pl0n3r/Factory", merge_sha, "token")


    def test_postmerge_fail_closed_on_untrusted_dispatch_inventory_and_jobs(self):
        sha = "b" * 40
        faults = (
            "invalid-head", "dispatch-body", "invalid-inventory", "invalid-row",
            "wrong-branch", "wrong-event", "wrong-name", "actual-run-moved",
            "missing-jobs", "wrong-job-sha", "duplicate-job", "no-new-run",
            "main-moved-after-dispatch",
        )
        for fault in faults:
            with self.subTest(fault=fault):
                posts = []
                seen_main = []
                run = {"id": 1002, "name": "GrindFlow CI",
                       "head_sha": sha, "head_branch": "main",
                       "event": "workflow_dispatch", "status": "completed",
                       "conclusion": "success"}
                if fault == "wrong-branch":
                    run["head_branch"] = "other"
                if fault == "wrong-event":
                    run["event"] = "push"
                if fault == "wrong-name":
                    run["name"] = "malicious"
                good_job = {"name": "validate", "head_sha": (
                    "c" * 40 if fault == "wrong-job-sha" else sha),
                    "status": "completed", "conclusion": "success"}

                def fake_api(_repo, path, _token, *, method="GET", payload=None):
                    if path.endswith("/git/ref/heads/main"):
                        seen_main.append(path)
                        drift = fault == "main-moved-after-dispatch" and posts
                        return {"object": {"sha": "c" * 40 if drift else sha}}
                    if path.endswith("/dispatches"):
                        posts.append(path)
                        return {"unexpected": True} if fault == "dispatch-body" else None
                    if "/runs?event=" in path:
                        if fault == "invalid-inventory":
                            return {"total_count": "NaN", "workflow_runs": []}
                        rows = [run] if posts and fault != "no-new-run" else []
                        if fault == "invalid-row" and posts:
                            rows = [3]
                        return {"total_count": len(rows), "workflow_runs": rows}
                    if path.endswith("/actions/runs/1002"):
                        return {**run, "head_sha": (
                            "d" * 40 if fault == "actual-run-moved" else run["head_sha"])}
                    if path.endswith("/actions/runs/1002/jobs?per_page=100"):
                        jobs = [] if fault == "missing-jobs" else [good_job]
                        if fault == "duplicate-job":
                            jobs.append(good_job.copy())
                        return {"total_count": len(jobs), "jobs": jobs}
                    raise AssertionError(path)

                with (
                    patch("scripts.dependabot_lane.api", side_effect=fake_api),
                    patch("scripts.dependabot_lane.time.sleep", return_value=None),
                ):
                    with self.assertRaises(LaneError):
                        lane._postmerge_exact_main_ci(
                            "pl0n3r/GrindFlow",
                            "not-sha" if fault == "invalid-head" else sha,
                            "token")
                if fault == "invalid-head":
                    self.assertFalse(posts)
                    self.assertFalse(seen_main)
                if fault == "main-moved-after-dispatch":
                    self.assertEqual(len(posts), 1)



class DependabotLaneCoverageTests(unittest.TestCase):
    """Cobertura de fallos de transporte, carrera, seguridad y rutas privilegiadas."""

    @staticmethod
    def source_pr():
        source = pr()
        source["changed_files"] = 1
        source["base"]["sha"] = "b" * 40
        source["created_at"] = "2026-11-21T00:00:00Z"
        return source

    def test_api_transport_requests_and_rejects_untrusted_inputs(self):
        captured = []

        def open_url(request, timeout):
            captured.append((request.full_url, request.get_method(), request.data,
                             request.headers.get("Authorization"), timeout))
            return io.BytesIO(b'{"number":2171,"ok":true}')

        with patch("scripts.dependabot_lane.urlopen", side_effect=open_url):
            got = api("pl0n3r/Factory", "/repos/pl0n3r/Factory/issues/2171", "token")
            self.assertEqual(got["number"], 2171)
            created = api("pl0n3r/Factory", "/repos/pl0n3r/Factory/issues",
                          "token", method="POST", payload={"title": "safe"})
            self.assertTrue(created["ok"])
        self.assertEqual(captured[0][1], "GET")
        self.assertEqual(captured[1][1], "POST")
        self.assertEqual(json.loads(captured[1][2]), {"title": "safe"})
        self.assertEqual(captured[0][3], "Bearer token")
        self.assertEqual(captured[0][4], 20)
        self.assertTrue(captured[0][0].startswith("https://api.github.com/"))
        for repo_name, method in (("../escape", "GET"), ("pl0n3r/Factory", "DELETE")):
            with self.subTest(repo=repo_name, method=method), self.assertRaises(LaneError):
                api(repo_name, "/repos/pl0n3r/Factory/issues", "token", method=method)
        with patch("scripts.dependabot_lane.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(LaneError, "URLError"):
                api("pl0n3r/Factory", "/repos/pl0n3r/Factory/issues", "token")
        class NoContent(io.BytesIO):
            status = 204
        with patch("scripts.dependabot_lane.urlopen", return_value=NoContent(b"")):
            self.assertIsNone(api("pl0n3r/GrindFlow",
                                  "/repos/pl0n3r/GrindFlow/actions/workflows/grindflow-ci.yml/dispatches",
                                  "token", method="POST", payload={"ref": "main"}))
        with patch("scripts.dependabot_lane.urlopen", return_value=io.BytesIO(b"not json")):
            with self.assertRaisesRegex(LaneError, "JSONDecodeError"):
                api("pl0n3r/Factory", "/repos/pl0n3r/Factory/issues", "token")

    def test_exact_head_classification_from_paginated_github_data(self):
        source = self.source_pr()
        requests = []

        def get(_repo, path, _token, *, method="GET", payload=None):
            requests.append(path)
            if path.endswith("/pulls/99"):
                return source
            if "/files?" in path:
                return [manifest()]
            if "/commits/" in path:
                return commit()
            raise AssertionError(path)

        with patch("scripts.dependabot_lane.api", side_effect=get):
            snapshot, result = read_exact("pl0n3r/Factory", 99, SHA, "token")
            self.assertEqual(snapshot["head"]["sha"], SHA)
            self.assertEqual(result["policy"], "auto")
            self.assertEqual(classify_from_api("pl0n3r/Factory", 99, SHA, "token")["files"], 1)
        self.assertEqual(sum("/pulls/99" in a and "/files?" not in a for a in requests), 4)
        self.assertEqual(sum("/commits/" in a for a in requests), 2)
        self.assertEqual(sum("/files?" in a for a in requests), 2)

    def test_exact_head_pagination_and_human_shortcircuit(self):
        source = self.source_pr()
        source["changed_files"] = 101
        requests = []
        rows = [manifest(f"modules/mod{i}/package-lock.json") for i in range(101)]

        def get(_repo, path, _token, *, method="GET", payload=None):
            requests.append(path)
            if path.endswith("/pulls/99"):
                return source
            if "/files?" in path:
                return rows[:100] if path.endswith("&page=1") else rows[100:]
            if "/commits/" in path:
                return commit()
            raise AssertionError(path)

        with patch("scripts.dependabot_lane.api", side_effect=get):
            _, result = read_exact("pl0n3r/Factory", 99, SHA, "token")
        self.assertEqual(result["files"], 101)
        self.assertEqual(sum("/files?" in path for path in requests), 2)
        source["user"] = {"login": "pl0n3r", "id": 1, "type": "User"}
        requests.clear()
        with patch("scripts.dependabot_lane.api", side_effect=get):
            _, result = read_exact("pl0n3r/Factory", 99, SHA, "token")
        self.assertEqual(result, {"dependabot": False})
        self.assertEqual(requests, ["/repos/pl0n3r/Factory/pulls/99"])

    def test_exact_head_invalid_metadata_and_races(self):
        with patch("scripts.dependabot_lane.api", side_effect=AssertionError("no request")):
            for number, sha in ((0, SHA), (99, "bad"), (True, SHA)):
                with self.subTest(number=number, sha=sha), self.assertRaises(LaneError):
                    read_exact("pl0n3r/Factory", number, sha, "token")
        source = self.source_pr()

        def get(_repo, path, _token, *, method="GET", payload=None):
            if path.endswith("/pulls/99"):
                return source
            if "/files?" in path:
                return [manifest()]
            return commit()

        with patch("scripts.dependabot_lane.api", side_effect=get):
            for bad in (0, 3001, None, "1"):
                with self.subTest(changed_files=bad), self.assertRaises(LaneError):
                    source["changed_files"] = bad
                    read_exact("pl0n3r/Factory", 99, SHA, "token")
            source["changed_files"] = 2
            with self.assertRaisesRegex(LaneError, "truncado"):
                read_exact("pl0n3r/Factory", 99, SHA, "token")
            source["changed_files"] = 1
        updates = 0

        def race(_repo, path, _token, *, method="GET", payload=None):
            nonlocal updates
            if path.endswith("/pulls/99"):
                updates += 1
                if updates > 1:
                    return {**source, "head": {"sha": "c" * 40, "repo": {"full_name": "pl0n3r/Factory"}}}
                return source
            return [manifest()] if "/files?" in path else commit()

        with patch("scripts.dependabot_lane.api", side_effect=race):
            with self.assertRaisesRegex(LaneError, "Carrera"):
                read_exact("pl0n3r/Factory", 99, SHA, "token")
        with patch("scripts.dependabot_lane.api", return_value=[]):
            with self.assertRaisesRegex(LaneError, "PR ilegible"):
                read_exact("pl0n3r/Factory", 99, SHA, "token")

    def test_check_run_versions_and_failclosed_sources(self):
        def check(name, ident, status="completed", conclusion="success", issuer=None):
            return {"id": ident, "name": name, "head_sha": SHA,
                    "status": status, "conclusion": conclusion,
                    "app": issuer or {"slug": "github-actions", "id": 15368}}

        rows = [check("Validar", 1), check("Tests de scripts", 2)]
        def response(_repo, _path, _token, *, method="GET", payload=None):
            return {"total_count": len(rows), "check_runs": rows}
        with patch("scripts.dependabot_lane.api", side_effect=response):
            self.assertTrue(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
            rows.append(check("Validar", 3, conclusion="failure"))
            self.assertFalse(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
            rows.append(check("Validar", 4))
            self.assertTrue(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
            rows.append(check("Waiting gate", 5, "in_progress", None))
            self.assertFalse(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
            rows.pop()
            rows[:] = [check("Other", 2)]
            self.assertFalse(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
            rows.append(check("Validar", 3, issuer={"slug": "fake", "id": 999}))
            with self.assertRaisesRegex(LaneError, "App no autorizada"):
                _terminal_checks_green("pl0n3r/Factory", SHA, "token")
            rows[-1]["app"] = {"slug": "github-actions", "id": 15368}
            rows.append(check("Reconciliar Dependabot", 4, status="in_progress", conclusion=None))
            self.assertTrue(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
            rows[0]["head_sha"] = "c" * 40
            with self.assertRaisesRegex(LaneError, "HEAD incorrecto"):
                _terminal_checks_green("pl0n3r/Factory", SHA, "token")

    def test_acceptance_runner_loads_consumer_gate_exactly_once(self):
        # Reproduce el cargador aislado de scripts/aceptacion_kit.py para
        # detectar importaciones/efectos del orden de unittest discover.
        from scripts.aceptacion_kit import _load_test_module

        loaded = _load_test_module(Path("tests/test_dependabot_lane.py"), Path.cwd())
        suite = unittest.TestLoader().loadTestsFromName(
            "DependabotLaneTests.test_consumer_exact_required_ci_gate", loaded
        )
        diagnostic = io.StringIO()
        result = unittest.TextTestRunner(stream=diagnostic, verbosity=2).run(suite)
        self.assertEqual(result.testsRun, 1, diagnostic.getvalue())
        self.assertTrue(result.wasSuccessful(), diagnostic.getvalue())

    def test_check_runs_pagination_and_invalid_responses(self):
        def row(i):
            return {"id": i, "name": "Validar" if i == 0 else f"Aux {i}",
                    "head_sha": SHA, "status": "completed", "conclusion": "success",
                    "app": {"id": 15368, "slug": "github-actions"}}
        records = [row(i) for i in range(101)]
        visited = []
        def paged(_repo, path, _token, *, method="GET", payload=None):
            visited.append(path)
            return {"total_count": 101,
                    "check_runs": records[:100] if path.endswith("&page=1") else records[100:]}
        with patch("scripts.dependabot_lane.api", side_effect=paged):
            self.assertTrue(_terminal_checks_green("pl0n3r/Factory", SHA, "token"))
        self.assertEqual(len(visited), 2)
        for bad in (
            {"total_count": "1", "check_runs": [row(0)]},
            {"total_count": 1, "check_runs": None},
            {"total_count": 2, "check_runs": [row(0)]},
            {"total_count": 0, "check_runs": []},
            {"total_count": 1, "check_runs": [{**row(0), "id": "1"}]},
            {"total_count": 1, "check_runs": [{**row(0), "app": None}]},
        ):
            with self.subTest(bad=bad), patch("scripts.dependabot_lane.api", return_value=bad):
                with self.assertRaises(LaneError):
                    _terminal_checks_green("pl0n3r/Factory", SHA, "token")

    def test_switch_rejects_invalid_sources_and_duplicate_markers(self):
        valid = {
            "number": 767, "state": "closed",
            "url": "https://api.github.com/repos/pl0n3r/Factory/issues/767",
            "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
            "user": {"login": "pl0n3r"},
            "body": '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->',
        }
        variants = [
            {**valid, "number": 768}, {**valid, "state": "open"},
            {**valid, "user": {"login": "intruder"}},
            {**valid, "body": None},
            {**valid, "body": ""},
            {**valid, "body": valid["body"] + "\n" + valid["body"]},
            {**valid, "body": '<!-- factory-unattended-kill-switch {"version":1,} -->'},
        ]
        with patch("scripts.dependabot_lane.api", return_value=valid):
            self.assertTrue(_switch_running("pl0n3r/Factory", "token"))
        for variant in variants:
            with self.subTest(variant=variant), patch("scripts.dependabot_lane.api", return_value=variant):
                self.assertFalse(_switch_running("pl0n3r/Factory", "token"))

    def test_followup_variants_and_invalid_metadata(self):
        created = []
        def server(_repo, path, _token, *, method="GET", payload=None):
            if method == "POST":
                created.append(payload)
                return {"number": 2500}
            return {"incomplete_results": False, "total_count": 0, "items": []}

        with patch("scripts.dependabot_lane.api", side_effect=server):
            self.assertEqual(create_followup("pl0n3r/Factory", 2107, SHA, "token",
                                             reason="workflow", paths=[".github/workflows/ci.yml"]), 2500)
            self.assertEqual(create_followup("pl0n3r/Factory", 2107, SHA, "token",
                                             reason="stale", paths=["package-lock.json"]), 2500)
            self.assertEqual(create_followup("pl0n3r/Factory", 2107, SHA, "token",
                                             reason="major", paths=["package-lock.json"],
                                             major_target="foo a la versión mayor 9"), 2500)
        self.assertIn("Revisar workflow", created[0]["title"])
        self.assertIn("Desbloquear", created[1]["title"])
        self.assertIn("foo a la versión mayor 9", created[2]["title"])
        self.assertIn("factory-plan-task", created[0]["body"])
        with patch("scripts.dependabot_lane.api", side_effect=AssertionError("no request")):
            for reason, paths in (("other", ["package-lock.json"]), ("stale", []),
                                  ("stale", ["src/app.py"]), ("major", ["package.json"] * 2)):
                with self.subTest(reason=reason, paths=paths), self.assertRaises(LaneError):
                    create_followup("pl0n3r/Factory", 10, SHA, "token", reason=reason, paths=paths)

    def test_followup_incomplete_search_and_bad_create(self):
        responses = [
            {"incomplete_results": True, "total_count": 0, "items": []},
            {"incomplete_results": False, "total_count": 101, "items": []},
            {"incomplete_results": False, "total_count": 1, "items": []},
        ]
        for response in responses:
            with self.subTest(response=response), patch("scripts.dependabot_lane.api", return_value=response):
                with self.assertRaisesRegex(LaneError, "Search Issues"):
                    create_followup("pl0n3r/Factory", 2107, SHA, "token",
                                    reason="workflow", paths=["package-lock.json"])
        def bad(_repo, path, _token, *, method="GET", payload=None):
            if method == "POST":
                return {"number": "2500"}
            return {"incomplete_results": False, "total_count": 0, "items": []}
        with patch("scripts.dependabot_lane.api", side_effect=bad):
            with self.assertRaisesRegex(LaneError, "no confirmado"):
                create_followup("pl0n3r/Factory", 2107, SHA, "token",
                                reason="workflow", paths=["package-lock.json"])

    def test_stale_comments_page_two_and_missing_pages(self):
        calls = []
        marker = "<!-- factory-dependabot-stale:pr-2107 -->"
        def server(_repo, path, _token, *, method="GET", payload=None):
            calls.append(path)
            if path.endswith("&page=1"):
                return [{"body": "another comment"}] * 100
            return [{"body": marker}]
        with patch("scripts.dependabot_lane.api", side_effect=server):
            self.assertFalse(comment_stale("pl0n3r/Factory", 2107, 2174, "token"))
        self.assertEqual(len(calls), 2)
        with patch("scripts.dependabot_lane.api", return_value={"not": "a list"}):
            with self.assertRaisesRegex(LaneError, "incompletos"):
                comment_stale("pl0n3r/Factory", 2107, 2174, "token")
        with patch("scripts.dependabot_lane.api", return_value=[{"body": "other"}] * 100):
            with self.assertRaisesRegex(LaneError, "Demasiados comentarios"):
                comment_stale("pl0n3r/Factory", 2107, 2174, "token")

    def test_sweep_rejects_untrusted_authority_and_inventory(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "pull_request",
                                     "GITHUB_REF": "refs/heads/main"}):
            with self.assertRaisesRegex(LaneError, "schedule"):
                sweep("pl0n3r/Factory", "token", now=now)
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule",
                                     "GITHUB_REF": "refs/heads/foreign"}):
            with self.assertRaisesRegex(LaneError, "main"):
                sweep("pl0n3r/Factory", "token", now=now)
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane._switch_running", return_value=False),
        ):
            with self.assertRaisesRegex(LaneError, "RUNNING"):
                sweep("pl0n3r/Factory", "token", now=now)
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
        ):
            for rows in (None, [{"user": None}], [{"user": BOT, "number": "2", "head": {"sha": SHA}}],
                         [{"user": BOT, "number": 2, "head": {"sha": "short"}}]):
                with self.subTest(rows=rows), patch("scripts.dependabot_lane.api", return_value=rows):
                    with self.assertRaises(LaneError):
                        sweep("pl0n3r/Factory", "token", now=now)
            with patch("scripts.dependabot_lane.api", return_value=[]):
                self.assertEqual(sweep("pl0n3r/Factory", "token", now=now), [])

    def test_sweep_paginated_authorized_bot_only(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        pages = []
        def get(_repo, path, _token, *, method="GET", payload=None):
            pages.append(path)
            if path.endswith("&page=1"):
                return [{"user": {"login": "other"}, "number": i} for i in range(99)] + [
                    {"user": BOT, "number": 7, "head": {"sha": SHA}},
                ]
            return [{"user": BOT, "number": 8, "head": {"sha": SHA}}]
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane.api", side_effect=get),
            patch("scripts.dependabot_lane.reconcile", side_effect=lambda repo, number, head, token, now: {"pr": number}) as run,
        ):
            got = sweep("pl0n3r/Factory", "token", now=now)
        self.assertEqual(got, [{"pr": 7}, {"pr": 8}])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(len(pages), 2)



    def test_reconcile_manual_major_and_workflow_followups(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        source = self.source_pr()
        choices = [
            {"dependabot": True, "policy": "manual", "major": True,
             "workflow": False, "file_paths": ["package-lock.json"],
             "major_target": "demo a la versión mayor 4"},
            {"dependabot": True, "policy": "manual", "major": False,
             "workflow": True, "file_paths": [".github/workflows/ci.yml"],
             "major_target": None},
        ]
        for lane, reason in zip(choices, ("major", "workflow")):
            with (
                self.subTest(reason=reason),
                patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run",
                                        "GITHUB_REF": "refs/heads/main"}),
                patch("scripts.dependabot_lane.read_exact", return_value=(source, lane)),
                patch("scripts.dependabot_lane._switch_running", return_value=True),
                patch("scripts.dependabot_lane.create_followup", return_value=2200) as followup,
                patch("scripts.dependabot_lane.api", side_effect=AssertionError("no merge")),
            ):
                result = reconcile("pl0n3r/Factory", 99, SHA, "token", now=now)
            self.assertTrue(result["followup_required"])
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["issue"], 2200)
            self.assertEqual(followup.call_args.kwargs["paths"], lane["file_paths"])
            self.assertEqual(followup.call_args.kwargs["reason"], reason)

        source["created_at"] = "2026-11-10T00:00:00Z"
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane.read_exact", return_value=(source, choices[1])),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane.create_followup", return_value=2201),
            patch("scripts.dependabot_lane._terminal_checks_green", return_value=False),
            patch("scripts.dependabot_lane.comment_stale", return_value=True) as notify,
        ):
            result = reconcile("pl0n3r/Factory", 99, SHA, "token", now=now)
        self.assertEqual(result["issue"], 2201)
        notify.assert_called_once_with("pl0n3r/Factory", 99, 2201, "token")

    def test_reconcile_stale_minor_and_unknown_checks(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        source = self.source_pr()
        lane = {"dependabot": True, "policy": "auto",
                "file_paths": ["package-lock.json"]}
        source["created_at"] = "2026-11-10T00:00:00Z"
        for check_failure in (False, LaneError("unavailable")):
            def fail_checks(*args):
                if isinstance(check_failure, Exception):
                    raise check_failure
                return check_failure
            with (
                self.subTest(check_failure=check_failure),
                patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule",
                                        "GITHUB_REF": "refs/heads/main"}),
                patch("scripts.dependabot_lane.read_exact", return_value=(source, lane)),
                patch("scripts.dependabot_lane._switch_running", return_value=True),
                patch("scripts.dependabot_lane._terminal_checks_green", side_effect=fail_checks),
                patch("scripts.dependabot_lane.create_followup", return_value=2200) as issue,
                patch("scripts.dependabot_lane.comment_stale", return_value=True) as comment,
                patch("scripts.dependabot_lane.api", side_effect=AssertionError("no merge")),
            ):
                result = reconcile("pl0n3r/Factory", 99, SHA, "token", now=now)
            self.assertTrue(result["followup_required"])
            self.assertEqual(result["reason"], "stale")
            self.assertEqual(issue.call_args.kwargs["reason"], "stale")
            comment.assert_called_once_with("pl0n3r/Factory", 99, 2200, "token")
        source["created_at"] = "2026-11-21T00:00:00Z"
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane.read_exact", return_value=(source, lane)),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane._terminal_checks_green",
                  side_effect=LaneError("bad checks")),
        ):
            with self.assertRaisesRegex(LaneError, "desconocida"):
                reconcile("pl0n3r/Factory", 99, SHA, "token", now=now)

    def test_reconcile_denies_missing_authority_and_changed_heads(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        source = self.source_pr()
        lane = {"dependabot": True, "policy": "auto", "file_paths": ["package-lock.json"]}
        with patch("scripts.dependabot_lane.read_exact",
                   side_effect=AssertionError("unauthorized source")):
            for event, ref in (("pull_request", "refs/heads/main"),
                               ("workflow_run", "refs/heads/other")):
                with (
                    self.subTest(event=event, ref=ref),
                    patch.dict(os.environ, {"GITHUB_EVENT_NAME": event, "GITHUB_REF": ref}),
                ):
                    with self.assertRaises(LaneError):
                        reconcile("pl0n3r/GrindFlow", 99, SHA, "token", now=now)
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane.read_exact", return_value=(source, lane)),
            patch("scripts.dependabot_lane._switch_running", return_value=False),
            patch("scripts.dependabot_lane.api", side_effect=AssertionError("no merge")),
        ):
            with self.assertRaisesRegex(LaneError, "RUNNING"):
                reconcile("pl0n3r/GrindFlow", 99, SHA, "token", now=now)
        changed = {**lane, "file_paths": ["composer.lock"]}
        with (
            patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run",
                                    "GITHUB_REF": "refs/heads/main"}),
            patch("scripts.dependabot_lane.read_exact",
                  side_effect=[(source, lane), (source, changed)]),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane._terminal_checks_green", return_value=True),
            patch("scripts.dependabot_lane.api", side_effect=AssertionError("no merge")),
        ):
            with self.assertRaisesRegex(LaneError, "cambió"):
                reconcile("pl0n3r/GrindFlow", 99, SHA, "token", now=now)

    def test_reconcile_denies_check_race_and_unverified_merge_response(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        source = self.source_pr()
        lane = {"dependabot": True, "policy": "auto", "file_paths": ["package-lock.json"]}
        environment = {"GITHUB_EVENT_NAME": "workflow_run", "GITHUB_REF": "refs/heads/main"}
        with (
            patch.dict(os.environ, environment),
            patch("scripts.dependabot_lane.read_exact", return_value=(source, lane)),
            patch("scripts.dependabot_lane._switch_running", return_value=True),
            patch("scripts.dependabot_lane._terminal_checks_green", side_effect=[True, False]),
            patch("scripts.dependabot_lane.api", side_effect=AssertionError("no merge")),
        ):
            with self.assertRaisesRegex(LaneError, "cambió"):
                reconcile("pl0n3r/GrindFlow", 99, SHA, "token", now=now)
        with (
            patch.dict(os.environ, environment),
            patch("scripts.dependabot_lane.read_exact", return_value=(source, lane)),
            patch("scripts.dependabot_lane._switch_running", side_effect=[True, False]),
            patch("scripts.dependabot_lane._terminal_checks_green", return_value=True),
            patch("scripts.dependabot_lane.api", side_effect=AssertionError("no merge")),
        ):
            with self.assertRaisesRegex(LaneError, "Interruptor global cambió"):
                reconcile("pl0n3r/GrindFlow", 99, SHA, "token", now=now)
        for response in ({"merged": False, "sha": "b" * 40},
                         {"merged": True, "sha": "not a SHA"}):
            with (
                self.subTest(response=response),
                patch.dict(os.environ, environment),
                patch("scripts.dependabot_lane.read_exact", return_value=(source, lane)),
                patch("scripts.dependabot_lane._switch_running", return_value=True),
                patch("scripts.dependabot_lane._terminal_checks_green", return_value=True),
                patch("scripts.dependabot_lane.api", return_value=response),
            ):
                with self.assertRaises(LaneError):
                    reconcile("pl0n3r/GrindFlow", 99, SHA, "token", now=now)

    def test_cli_classify_reconcile_sweep_and_failures(self):
        args = ["--repo", "pl0n3r/Factory", "--pr", "99", "--head", SHA]
        with (
            patch.dict(os.environ, {"GH_TOKEN": "token"}),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO),
            patch("scripts.dependabot_lane.classify_from_api",
                  return_value={"dependabot": True}) as classifier,
        ):
            self.assertEqual(main(["classify", *args]), 0)
            self.assertEqual(classifier.call_count, 1)
            classifier.return_value = {"dependabot": False}
            self.assertEqual(main(["classify", *args]), 20)
            classifier.side_effect = LaneError("malformed")
            self.assertEqual(main(["classify", *args]), 1)
        with (
            patch.dict(os.environ, {"GH_TOKEN": "token"}),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("scripts.dependabot_lane.reconcile", return_value={"merged": False}) as executor,
            patch("scripts.dependabot_lane.sweep", return_value=[{"followup_required": True}]) as sweepcall,
        ):
            self.assertEqual(main(["reconcile", *args]), 0)
            self.assertEqual(executor.call_count, 1)
            self.assertEqual(main(["sweep", "--repo", "pl0n3r/Factory"]), 0)
            self.assertEqual(sweepcall.call_count, 1)
            self.assertEqual(main(["classify", "--repo", "pl0n3r/Factory"]), 1)
        with (
            patch.dict(os.environ, {"GH_TOKEN": ""}),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            self.assertEqual(main(["classify", *args]), 1)

    def test_classify_rejects_ambiguous_dependency_metadata_and_paths(self):
        good = self.source_pr()
        base_commit = commit()
        invalid_changes = [
            {"status": "renamed", "filename": "package-lock.json"},
            {"status": "modified", "filename": "../package-lock.json"},
            {"status": "modified", "filename": "./package-lock.json"},
            {"status": "modified", "filename": "src/app.py"},
            {"status": "modified", "filename": ".github/workflows/ci.yml",
             "patch": "@@ -1 +1 @@\n- run: safe\n+ run: unsafe"},
            {"status": "modified", "filename": ".github/workflows/ci.yml",
             "patch": None},
        ]
        for changed in invalid_changes:
            with self.subTest(change=changed), self.assertRaises(LaneError):
                classify(good, [changed], base_commit, repo="pl0n3r/Factory", head=SHA)
        for change in (
            {"author": {"login": "other", "id": 1}, "commit": base_commit["commit"]},
            {"author": base_commit["author"], "commit": {"verification": {"verified": False}, "message": base_commit["commit"]["message"]}},
            {"author": base_commit["author"], "commit": {"verification": {"verified": True}, "message": "no metadata"}},
        ):
            with self.subTest(change=change), self.assertRaises(LaneError):
                classify(good, [manifest()], change, repo="pl0n3r/Factory", head=SHA)
        for mutant in (
            {**good, "head": {"sha": "b" * 40, "repo": {"full_name": "pl0n3r/Factory"}}},
            {**good, "base": {"ref": "dev", "repo": {"full_name": "pl0n3r/Factory"}}},
            {**good, "state": "closed"},
            {**good, "head": {"sha": SHA, "repo": {"full_name": "other/project"}}},
        ):
            with self.subTest(mutant=mutant), self.assertRaises(LaneError):
                classify(mutant, [manifest()], base_commit, repo="pl0n3r/Factory", head=SHA)
        with self.assertRaises(LaneError):
            classify(good, [], base_commit, repo="pl0n3r/Factory", head=SHA)
        with self.assertRaises(LaneError):
            classify(good, [manifest()], base_commit, repo="not-allowed", head=SHA)

if __name__ == "__main__":
    unittest.main()
