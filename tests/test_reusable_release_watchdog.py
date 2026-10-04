#!/usr/bin/env python3
"""Regresiones del vigilante post-release de reusables Factory."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.reusable_release_watchdog import (
    ReusableReleaseWatchdogError,
    evaluate_release_watchdog,
    main as watchdog_main,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "reusable-release-watchdog.yml"


def observation(
    *,
    repository_ref="pl0n3r/ControlBot",
    workflow="Coordinación",
    run_id=37037895618,
    conclusion="startup_failure",
    caller_sha="a" * 40,
    caller_path=".github/workflows/coordinacion.yml",
    reusable_ref=(
        "pl0n3r/factory/.github/workflows/coordinacion.yml@v1"
    ),
):
    return {
        "repository_ref": repository_ref,
        "workflow": workflow,
        "run_id": run_id,
        "observed_at": "2026-10-02T17:01:00Z",
        "factory_sha": "b" * 40,
        "factory_channel": "v1",
        "conclusion": conclusion,
        "caller_sha": caller_sha,
        "caller_path": caller_path,
        "reusable_ref": reusable_ref,
    }


def payload(*observations):
    return {
        "factory_sha": "b" * 40,
        "factory_channel": "v1",
        "release_started_at": "2026-10-02T16:50:55Z",
        "observations": list(observations),
    }


class ReusableReleaseWatchdogTests(unittest.TestCase):
    def test_startup_failures_are_bound_to_repo_workflow_run_and_factory_sha(self):
        item = observation()
        result = evaluate_release_watchdog(payload(item))

        self.assertEqual(result["status"], "ALERT")
        self.assertEqual(result["factory_sha"], "b" * 40)
        self.assertEqual(result["factory_channel"], "v1")
        self.assertEqual(result["affected_repositories"], ["pl0n3r/ControlBot"])
        self.assertEqual(result["observations"], [item])
        self.assertEqual(result["observations"][0]["run_id"], 37037895618)
        self.assertEqual(
            result["observations"][0]["reusable_ref"],
            "pl0n3r/factory/.github/workflows/coordinacion.yml@v1",
        )

    def test_two_distinct_affected_repositories_recommend_rollback_without_authority(self):
        first = observation()
        second = observation(
            repository_ref="pl0n3r/FactoryRunner",
            workflow="Etiquetas",
            run_id=37037902998,
            caller_sha="c" * 40,
            caller_path=".github/workflows/etiquetas.yml",
            reusable_ref=(
                "pl0n3r/factory/.github/workflows/etiquetas.yml@v1"
            ),
        )

        result = evaluate_release_watchdog(payload(first, second))

        self.assertEqual(result["affected_repository_count"], 2)
        self.assertTrue(result["rollback_recommended"])
        self.assertEqual(result["recommendation"], "rollback_v1_recommended")
        self.assertEqual(result["authority"], "unchanged")
        self.assertFalse(result["execute_rollback"])

    def test_duplicate_runs_collapse_to_one_stable_alert_fingerprint(self):
        item = observation()
        duplicated = evaluate_release_watchdog(payload(item, copy.deepcopy(item)))
        single = evaluate_release_watchdog(payload(item))

        self.assertEqual(len(duplicated["observations"]), 1)
        self.assertEqual(duplicated["fingerprint"], single["fingerprint"])

    def test_unknown_repo_workflow_conclusion_or_ambiguous_evidence_fails_closed(self):
        cases = []

        unknown_repo = observation(repository_ref="pl0n3r/Unknown")
        cases.append(payload(unknown_repo))

        unknown_workflow = observation(workflow="CI")
        cases.append(payload(unknown_workflow))

        wrong_conclusion = observation(conclusion="failure")
        cases.append(payload(wrong_conclusion))

        labels_with_coordination_ref = observation(
            workflow="Etiquetas",
            caller_path=".github/workflows/etiquetas.yml",
        )
        cases.append(payload(labels_with_coordination_ref))

        ambiguous_a = observation()
        ambiguous_b = observation(caller_sha="d" * 40)
        cases.append(payload(ambiguous_a, ambiguous_b))

        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ReusableReleaseWatchdogError):
                    evaluate_release_watchdog(value)

    def test_empty_observations_produce_clear_without_rollback_authority(self):
        result = evaluate_release_watchdog(payload())

        self.assertEqual(result["status"], "CLEAR")
        self.assertEqual(result["affected_repository_count"], 0)
        self.assertEqual(result["affected_repositories"], [])
        self.assertFalse(result["rollback_recommended"])
        self.assertEqual(
            result["recommendation"],
            "observe_without_rollback_recommendation",
        )
        self.assertEqual(result["authority"], "unchanged")
        self.assertFalse(result["execute_rollback"])

    def test_root_and_observation_contract_errors_fail_closed(self):
        base = payload(observation())
        invalid_cases = []

        invalid_cases.append(None)

        extra_root = copy.deepcopy(base)
        extra_root["extra"] = True
        invalid_cases.append(extra_root)

        bad_factory_sha = copy.deepcopy(base)
        bad_factory_sha["factory_sha"] = "bad"
        invalid_cases.append(bad_factory_sha)

        bad_channel = copy.deepcopy(base)
        bad_channel["factory_channel"] = "latest"
        invalid_cases.append(bad_channel)

        bad_timestamp_shape = copy.deepcopy(base)
        bad_timestamp_shape["release_started_at"] = "2026-10-02T16:50:55+00:00"
        invalid_cases.append(bad_timestamp_shape)

        bad_timestamp_value = copy.deepcopy(base)
        bad_timestamp_value["release_started_at"] = "not-a-dateZ"
        invalid_cases.append(bad_timestamp_value)

        bad_observations_type = copy.deepcopy(base)
        bad_observations_type["observations"] = {}
        invalid_cases.append(bad_observations_type)

        too_many = payload()
        too_many["observations"] = [observation()] * 201
        invalid_cases.append(too_many)

        missing_field = copy.deepcopy(base)
        missing_field["observations"][0].pop("run_id")
        invalid_cases.append(missing_field)

        unknown_reusable = copy.deepcopy(base)
        unknown_reusable["observations"][0]["reusable_ref"] = (
            "pl0n3r/factory/.github/workflows/unknown.yml@v1"
        )
        invalid_cases.append(unknown_reusable)

        invalid_run_id = copy.deepcopy(base)
        invalid_run_id["observations"][0]["run_id"] = True
        invalid_cases.append(invalid_run_id)

        before_release = copy.deepcopy(base)
        before_release["observations"][0]["observed_at"] = (
            "2026-10-02T16:00:00Z"
        )
        invalid_cases.append(before_release)

        mismatched_factory_sha = copy.deepcopy(base)
        mismatched_factory_sha["observations"][0]["factory_sha"] = "c" * 40
        invalid_cases.append(mismatched_factory_sha)

        mismatched_channel = copy.deepcopy(base)
        mismatched_channel["observations"][0]["factory_channel"] = "main"
        invalid_cases.append(mismatched_channel)

        invalid_caller_sha = copy.deepcopy(base)
        invalid_caller_sha["observations"][0]["caller_sha"] = "bad"
        invalid_cases.append(invalid_caller_sha)

        invalid_caller_path = copy.deepcopy(base)
        invalid_caller_path["observations"][0]["caller_path"] = "../caller.yml"
        invalid_cases.append(invalid_caller_path)

        for value in invalid_cases:
            with self.subTest(value=value):
                with self.assertRaises(ReusableReleaseWatchdogError):
                    evaluate_release_watchdog(value)

    def test_cli_success_invalid_json_and_input_limit_are_explicit(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "sys.stdin",
                io.StringIO(json.dumps(payload())),
            ),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(watchdog_main(), 0)

        parsed = json.loads(stdout.getvalue())
        self.assertEqual(parsed["status"], "CLEAR")
        self.assertEqual(stderr.getvalue(), "")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO("{not-json")),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(watchdog_main(), 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("ERROR:", stderr.getvalue())

        stderr = io.StringIO()
        with (
            patch("scripts.reusable_release_watchdog.MAX_INPUT", 5),
            patch("sys.stdin", io.StringIO("123456")),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(watchdog_main(), 2)
        self.assertIn("payload demasiado grande", stderr.getvalue())

    def test_workflow_filters_startup_failure_before_bounded_actions_evidence(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "--data-urlencode 'status=startup_failure'",
            workflow,
        )
        self.assertIn(
            '--data-urlencode "created=>=$release_started_at"',
            workflow,
        )
        self.assertIn("--data-urlencode 'per_page=100'", workflow)
        self.assertLess(
            workflow.index("--data-urlencode 'status=startup_failure'"),
            workflow.index("--data-urlencode 'per_page=100'"),
        )

    def test_workflow_preserves_six_consumer_queries_and_post_release_scope(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        for repository in (
            "pl0n3r/Condor",
            "pl0n3r/ControlBot",
            "pl0n3r/FactoryRunner",
            "pl0n3r/GrindFlow",
            "pl0n3r/brvtal",
            "pl0n3r/AutoFactory",
        ):
            self.assertIn(repository, workflow)
        self.assertEqual(
            workflow.count("actions_url=\"https://api.github.com/repos/$repo/actions/runs\""),
            1,
        )
        self.assertIn("--data-urlencode 'status=startup_failure'", workflow)
        self.assertIn(".conclusion == \"startup_failure\"", workflow)
        self.assertIn("authority=unchanged", workflow)

    def test_workflow_keeps_startup_failure_defense_in_depth_and_total_count_bound(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            ".workflow_runs[]\n              | select(.conclusion == \"startup_failure\")",
            workflow,
        )
        self.assertIn("(( total_count <= 100 ))", workflow)

    def test_workflow_declares_post_merge_watchdog_contract_without_pr_activation(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: Vigilar startup_failure de reusables publicados", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        for repository in (
            "pl0n3r/Condor",
            "pl0n3r/ControlBot",
            "pl0n3r/FactoryRunner",
            "pl0n3r/GrindFlow",
            "pl0n3r/brvtal",
            "pl0n3r/AutoFactory",
        ):
            self.assertIn(f'"{repository}"', workflow)

    def test_workflow_builds_consumer_actions_url_without_encoding_owner_repo_slash(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn('for repo in "${consumers[@]}"; do', workflow)
        self.assertIn(
            'actions_url="https://api.github.com/repos/$repo/actions/runs"',
            workflow,
        )
        self.assertIn('"$actions_url"', workflow)
        self.assertNotIn("encoded_repo=", workflow)
        self.assertNotIn("%2F", workflow)

    def test_workflow_failure_message_names_repo_and_url_on_http_error(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("--write-out '%{http_code}'", workflow)
        self.assertIn(
            "No se pudo consultar Actions para $repo "
            "($actions_url; curl exit $curl_exit).",
            workflow,
        )
        self.assertIn(
            "Actions para $repo devolvió HTTP $http_code ($actions_url).",
            workflow,
        )

    def test_workflow_keeps_minimal_permissions_and_evidence_limits(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("contents: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("--data-urlencode 'per_page=100'", workflow)
        self.assertIn("(( total_count <= 100 ))", workflow)

    def test_workflow_reactivation_cron_stays_offset_fifteen_minutes_and_keeps_manual_dispatch(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("schedule:", workflow)
        self.assertIn("cron: '7,22,37,52 * * * *'", workflow)
        self.assertNotIn("cron: '*/15 * * * *'", workflow)
        self.assertIn("workflow_dispatch:", workflow)

    def test_workflow_never_moves_tags_and_keeps_rollback_advisory_only(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("schedule:", workflow)
        self.assertIn("cron: '7,22,37,52 * * * *'", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn(
            "python3 -m scripts.reusable_release_watchdog",
            workflow,
        )
        for repository in (
            "pl0n3r/Condor",
            "pl0n3r/ControlBot",
            "pl0n3r/FactoryRunner",
            "pl0n3r/GrindFlow",
            "pl0n3r/brvtal",
            "pl0n3r/AutoFactory",
        ):
            self.assertIn(repository, workflow)

        self.assertIn("authority=unchanged", workflow)
        self.assertIn("execute_rollback=false", workflow)
        self.assertIn("factory-reusable-release-alert", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("git/refs/tags", workflow)
        self.assertNotIn("refs/tags/v1", workflow)


if __name__ == "__main__":
    unittest.main()
