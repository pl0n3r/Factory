import unittest
from pathlib import Path

from performance.detector import detect_performance
from performance.remediation import evaluate_before_after, plan_remediation
from performance.status import (
    PerformanceStatusError,
    derive_performance_status,
    readiness_projection,
)
from performance.triage import triage_performance

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-28T20:06:00Z"


def contract():
    metric = {
        "id": "latency_p95", "label": "Latency p95",
        "baseline": {"value": 180, "unit": "ms", "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": 250, "unit": "ms"},
        "window": {"duration_seconds": 300, "min_samples": 20},
        "freshness": {"max_age_seconds": 900},
        "evidence": {"source": "ci", "ref": "run:1", "observed_at": "2026-09-28T20:00:00Z"},
        "allowed_actions": ["create_work_item", "measure_before_after"],
        "escalation_conditions": ["architecture_change", "cost_change"],
    }
    return {"version": 1, "project": "condor",
            "surfaces": [{"id": "inventory", "label": "Inventory", "metrics": [metric]}]}


def observation(value=300, **overrides):
    data = {
        "version": 1, "project": "condor", "surface": "inventory",
        "metric": "latency_p95", "value": value, "unit": "ms",
        "observed_at": "2026-09-28T20:05:00Z", "window_seconds": 300,
        "sample_count": 30, "severity": "high", "operational_impact": False,
        "bottleneck": "database", "evidence_ref": "run:2",
        "sha": "a" * 40, "release": "v1.2.3",
    }
    data.update(overrides)
    return data


def work_item(evidence_ref="run:2"):
    return {
        "work_id": "perf-condor-inventory-1", "origin_mode": "automatic",
        "origin_system": "factory", "group_id": "pl0n3r-group",
        "project_id": "condor", "repository_ref": "pl0n3r/Condor",
        "work_type": "engineering", "requested_capabilities": ["coding", "database"],
        "required_roles": ["dba", "ingenieria-software", "qa"],
        "authority_level": "operational", "producer_ref": "factory:performance",
        "priority_class": "high", "severity": "high", "depends_on": [],
        "claims": ["performance:condor:inventory"], "policy_ref": "factory:constitution-v1",
        "evidence_refs": [evidence_ref], "idempotency_key": "perf-condor-inventory-run2",
        "observed_at": "2026-09-28T20:05:00Z",
    }


def proposal(evidence_ref="run:2", **overrides):
    data = {
        "version": 1, "workflow_action": "create_work_item",
        "change_id": "inventory_index", "hypothesis_ref": "hypothesis:inventory-index",
        "reversible": True, "tests_covered": True, "within_authority": True,
        "changes_product_semantics": False, "triggered_conditions": [],
        "rollback_ref": "rollback:revert-index", "work_item": work_item(evidence_ref),
    }
    data.update(overrides)
    return data


def detected(value=300, **overrides):
    return detect_performance(contract(), observation(value, **overrides), evaluated_at=NOW)


class PerformanceLoopE2ETests(unittest.TestCase):
    def test_status_maps_current_classifications_without_hidden_score(self):
        info = derive_performance_status(detected(220))
        degraded = derive_performance_status(detected(300))
        incident_detection = detected(300, severity="critical", operational_impact=True)
        incident = derive_performance_status(incident_detection)
        self.assertEqual((info["status"], degraded["status"], incident["status"]),
                         ("HEALTHY", "DEGRADED", "BLOCKED"))
        self.assertNotIn("score", info)

    def test_noncurrent_evidence_is_unknown_never_healthy(self):
        for item in (
            detected(220, observed_at="2026-09-28T19:00:00Z"),
            detected(220, sample_count=2),
            detected(220, metric="missing_metric"),
        ):
            with self.subTest(state=item["evidence_state"]):
                self.assertEqual(derive_performance_status(item)["status"], "UNKNOWN")

    def test_status_output_is_explainable_sanitized_and_non_executing(self):
        status = derive_performance_status(detected(300))
        self.assertEqual(status["identity"], {"sha": "a" * 40, "release": "v1.2.3"})
        self.assertEqual(status["evidence_refs"], ["run:2"])
        self.assertEqual(status["authority"], "unchanged")
        self.assertFalse(status["execute_actions"])
        self.assertFalse(status["parallel_queue"])

        unsafe = dict(detected(300))
        unsafe["evidence_ref"] = "user@example.com"
        with self.assertRaisesRegex(PerformanceStatusError, "sensible"):
            derive_performance_status(unsafe)

    def test_readiness_projection_copies_canonical_status_without_recalculation(self):
        status = derive_performance_status(detected(300))
        projection = readiness_projection(status)
        self.assertEqual(projection["status"], status["status"])
        self.assertEqual(projection["reasons"], status["reasons"])
        self.assertEqual(projection["evidence_refs"], status["evidence_refs"])
        self.assertEqual(projection["evidence_state"], status["evidence_state"])

    def test_e2e_regression_to_adopted_improvement_becomes_healthy(self):
        before = detected(300)
        triage = triage_performance(before)
        plan = plan_remediation(before, triage, proposal())
        after = detected(220, evidence_ref="run:3")
        comparison = evaluate_before_after(before, after)
        status = derive_performance_status(after, remediation=plan, comparison=comparison)
        self.assertEqual(plan["decision"], "AUTO_REPAIR")
        self.assertEqual(comparison["decision"], "ADOPT")
        self.assertEqual(status["status"], "HEALTHY")

    def test_e2e_fail_closed_paths_never_become_healthy_or_parallel_queue(self):
        before = detected(300)
        triage = triage_performance(before)
        escalated = plan_remediation(
            before, triage, proposal(triggered_conditions=["cost_change"])
        )
        self.assertEqual(
            derive_performance_status(before, remediation=escalated)["status"],
            "BLOCKED",
        )

        stale = derive_performance_status(
            detected(220, observed_at="2026-09-28T19:00:00Z")
        )
        worse = detected(340, evidence_ref="run:4")
        comparison = evaluate_before_after(before, worse)
        final = derive_performance_status(worse, comparison=comparison)
        self.assertEqual(stale["status"], "UNKNOWN")
        self.assertNotEqual(final["status"], "HEALTHY")
        self.assertFalse(final["parallel_queue"])

        docs = (ROOT / "docs" / "performance-engineering.md").read_text()
        self.assertIn("no crea scheduler ni backlog paralelo", docs)
        self.assertIn("Factory Queue #269", docs)


if __name__ == "__main__":
    unittest.main()
