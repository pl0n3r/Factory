import json
import unittest
from datetime import datetime
from pathlib import Path

from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from lab.factory_lab import evaluate_shadow
from metricas.organizational_complexity import compare_simplification


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "feedback" / "data" / "living-software-operational-e2e.json"


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def duration_seconds(row):
    start = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00"))
    return int((end - start).total_seconds())


def protected():
    return {name: 1.0 for name in PROTECTED_INVARIANTS}


def constitution_candidate(data):
    return {
        "version": 1,
        "changes": [
            {
                "path": "evolution_state.heuristics.reservation_readiness_preflight",
                "operation": "add",
                "value": {
                    "checks": [
                        "acceptance_contract",
                        "status_available",
                        "factory_plan_task",
                    ],
                    "mode": "preflight",
                    "scope": "issue_reservation",
                },
            }
        ],
        "evidence": [
            "pl0n3r/Factory#247",
            *data["origin"]["provenance"],
        ],
        "rollback": {
            "reversible": True,
            "strategy": data["shadow_candidate"]["rollback"],
        },
    }


def lab_vectors(data):
    baseline = {
        name: {"value": 1.0, "direction": "higher"}
        for name in PROTECTED_INVARIANTS
    }
    candidate = {
        name: {"value": 1.0, "direction": "higher"}
        for name in PROTECTED_INVARIANTS
    }
    baseline.update(
        {
            "coordination_seconds": {
                "value": data["complexity"]["before_coordination_seconds"],
                "direction": "lower",
            },
            "reservation_attempts": {
                "value": 3,
                "direction": "lower",
            },
        }
    )
    candidate.update(
        {
            "coordination_seconds": {
                "value": data["complexity"]["after_coordination_seconds"],
                "direction": "lower",
            },
            "reservation_attempts": {
                "value": 1,
                "direction": "lower",
            },
        }
    )
    return baseline, candidate


def complexity_observation(data, *, before):
    seconds = (
        data["complexity"]["before_coordination_seconds"]
        if before
        else data["complexity"]["after_coordination_seconds"]
    )
    evidence = (
        ["run:36507015627", "run:36507097760", "run:36507219161"]
        if before
        else ["run:36507269422"]
    )
    return {
        "version": 1,
        "work_id": (
            "factory-247-readiness-before"
            if before
            else "factory-247-readiness-after"
        ),
        "comparison_scope": data["complexity"]["comparison_scope"],
        "task_type": "coordination",
        "task_size": "small",
        "risk": "medium",
        "rules_consulted": [
            "acceptance-contract",
            "factory-plan-task",
            "status-available",
        ],
        "active_roles": [],
        "reviewers": [],
        "checks": [
            "acceptance",
            "availability",
            "parallel-claims",
        ],
        "handoffs": ["issue-comment"],
        "engines_consulted": ["coordination"],
        "context_tokens": 0,
        "coordination_minutes": seconds / 60,
        "wait_minutes": 0,
        "review_minutes": 0,
        "useful_execution_minutes": (
            data["complexity"]["useful_execution_seconds"] / 60
        ),
        "protected_metrics": protected(),
        "evidence_refs": evidence,
        "observed_at": (
            "2026-09-29T01:17:53Z"
            if before
            else "2026-09-29T01:18:50Z"
        ),
    }


class LivingSoftwareOperationalE2ETests(unittest.TestCase):
    def test_manifest_uses_real_coordination_and_execution_evidence(self):
        data = load_manifest()
        attempts = data["coordination_attempts"]

        self.assertEqual(
            [row["run_id"] for row in attempts],
            [36507015627, 36507097760, 36507219161, 36507269422],
        )
        self.assertEqual(
            [row["conclusion"] for row in attempts],
            ["failure", "success", "failure", "success"],
        )
        self.assertEqual(
            [row["duration_seconds"] for row in attempts],
            [duration_seconds(row) for row in attempts],
        )
        self.assertEqual(
            attempts[1]["effect"],
            "no_reservation_missing_available_state",
        )
        self.assertEqual(attempts[-1]["effect"], "reservation_created")

    def test_unsolicited_preflight_candidate_is_derived_from_observed_friction(self):
        data = load_manifest()
        origin = data["origin"]

        self.assertTrue(origin["unsolicited"])
        self.assertFalse(origin["owner_request"])
        self.assertEqual(
            origin["candidate"],
            "reservation-readiness-preflight",
        )
        self.assertEqual(len(origin["provenance"]), 4)
        self.assertEqual(
            data["decision"]["status"],
            "adopted_bounded_scenario",
        )
        self.assertFalse(data["decision"]["stable_mutation"])

    def test_candidate_passes_constitution_lab_fitness_without_authority_expansion(self):
        data = load_manifest()
        proposal = constitution_candidate(data)
        fingerprint = validate_candidate(proposal)
        self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")

        stable, candidate = lab_vectors(data)
        shadow = evaluate_shadow(
            stable_sha=data["shadow_candidate"]["stable_sha"],
            candidate_sha=data["shadow_candidate"]["candidate_sha"],
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=proposal,
        )

        self.assertEqual(shadow["mode"], "shadow")
        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual(shadow["external_writes"], [])
        self.assertEqual(shadow["fitness"]["claim"], "improved")
        self.assertEqual(shadow["fitness"]["protected_regressions"], [])
        self.assertTrue(shadow["promotion"]["ready"])
        self.assertFalse(data["decision"]["authority_expanded"])

    def test_posterior_execution_reaches_pr_and_exact_main_green(self):
        data = load_manifest()
        posterior = data["posterior_execution"]

        self.assertEqual(posterior["reservation_run"], 36507269422)
        self.assertEqual(posterior["pr"], 339)
        self.assertEqual(
            posterior["pr_head_sha"],
            data["shadow_candidate"]["candidate_sha"],
        )
        self.assertEqual(posterior["pr_ci_run"], 36507555400)
        self.assertEqual(posterior["pr_ci_duration_seconds"], 29)
        self.assertEqual(
            posterior["merge_sha"],
            "7e9062203f3faae85a6dfc6fc9cb446d4faaf71e",
        )
        exact = posterior["exact_main"]
        self.assertEqual(exact["ci_conclusion"], "success")
        self.assertEqual(exact["codeql_conclusion"], "success")
        self.assertEqual(exact["codeql_evidence_conclusion"], "success")

    def test_organizational_complexity_improves_without_protected_regression(self):
        data = load_manifest()
        attempts = data["coordination_attempts"]

        self.assertEqual(
            sum(row["duration_seconds"] for row in attempts[:3]),
            35,
        )
        self.assertEqual(attempts[-1]["duration_seconds"], 27)
        self.assertEqual(data["complexity"]["useful_execution_seconds"], 29)

        result = compare_simplification(
            complexity_observation(data, before=True),
            complexity_observation(data, before=False),
        )
        self.assertEqual(result["fitness"]["claim"], "improved")
        self.assertEqual(result["fitness"]["protected_regressions"], [])
        self.assertEqual(result["fitness"]["missing_dimensions"], [])
        self.assertTrue(result["can_claim_simplification"])
        self.assertEqual(result["authority"], "unchanged")
        self.assertFalse(result["execute"])

    def test_docs_close_epic_without_parallel_engine(self):
        text = (
            ROOT / "docs" / "living-software-operational-e2e.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "#248",
            "#341",
            "reservation-readiness-preflight",
            "35 s",
            "27 s",
            "Factory Lab",
            "Fitness",
            "#245",
            "PR #339",
            "7e9062203f3faae85a6dfc6fc9cb446d4faaf71e",
            "sin crear un Engine",
            "authority",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
