#!/usr/bin/env python3
"""Regresiones del vigilante post-release de reusables Factory."""
from __future__ import annotations

import copy
from pathlib import Path
import unittest

from scripts.reusable_release_watchdog import (
    ReusableReleaseWatchdogError,
    evaluate_release_watchdog,
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

    def test_workflow_never_moves_tags_and_keeps_rollback_advisory_only(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("schedule:", workflow)
        self.assertIn("cron: '*/15 * * * *'", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("contents: read", workflow)
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
