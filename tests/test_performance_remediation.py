import copy
import unittest
from pathlib import Path

from performance.remediation import (
    PerformanceRemediationError,
    evaluate_before_after,
    plan_remediation,
)

ROOT = Path(__file__).resolve().parents[1]


def finding(**overrides):
    data = {
        "version": 1, "project": "condor", "surface": "inventory",
        "metric": "latency_p95", "classification": "PERF_DEGRADATION",
        "evidence_state": "CURRENT", "reasons": [], "breach": True,
        "baseline": {"value": 180, "unit": "ms", "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": 250, "unit": "ms"},
        "observed": {"value": 300, "unit": "ms", "observed_at": "2026-09-28T20:05:00Z",
                     "sample_count": 30, "window_seconds": 300},
        "delta": 120, "freshness": {"age_seconds": 60, "max_age_seconds": 900},
        "identity": {"sha": "a" * 40, "release": "v1.2.3"},
        "severity": "high", "operational_impact": False, "bottleneck": "database",
        "evidence_ref": "run:2",
        "allowed_actions": ["create_work_item", "measure_before_after"],
        "escalation_conditions": [
            "architecture_change", "business_semantics", "capacity_budget",
            "consistency_risk", "cost_change", "destructive_migration", "sensitive_data",
        ],
    }
    data.update(overrides)
    return data


def triage(classification="PERF_DEGRADATION"):
    return {
        "version": 1, "classification": classification, "bottleneck": "database",
        "role_hints": ["dba", "ingenieria-software", "qa"],
        "authority": "unchanged", "execute_actions": False, "create_work_item": False,
    }


def work_item():
    return {
        "work_id": "perf-condor-inventory-1", "origin_mode": "automatic",
        "origin_system": "factory", "group_id": "pl0n3r-group",
        "project_id": "condor", "repository_ref": "pl0n3r/Condor",
        "work_type": "engineering", "requested_capabilities": ["database", "coding"],
        "required_roles": ["dba", "ingenieria-software", "qa"],
        "authority_level": "operational", "producer_ref": "factory:performance",
        "priority_class": "high", "severity": "high", "depends_on": [],
        "claims": ["performance:condor:inventory"], "policy_ref": "factory:constitution-v1",
        "evidence_refs": ["run:2"], "idempotency_key": "perf-condor-inventory-run2",
        "observed_at": "2026-09-28T20:05:00Z",
    }


def proposal(**overrides):
    data = {
        "version": 1, "workflow_action": "create_work_item",
        "change_id": "add_inventory_index", "hypothesis_ref": "hypothesis:inventory-index",
        "reversible": True, "tests_covered": True, "within_authority": True,
        "changes_product_semantics": False, "triggered_conditions": [],
        "rollback_ref": "rollback:revert-index", "work_item": work_item(),
    }
    data.update(overrides)
    return data


class PerformanceRemediationTests(unittest.TestCase):
    def test_plan_requires_material_finding_and_allowed_action(self):
        plan = plan_remediation(finding(), triage(), proposal())
        self.assertEqual(plan["decision"], "AUTO_REPAIR")
        info = finding(classification="PERF_INFO", breach=False)
        self.assertEqual(
            plan_remediation(info, triage("PERF_INFO"), proposal())["decision"],
            "NO_ACTION",
        )
        with self.assertRaisesRegex(PerformanceRemediationError, "no está permitida"):
            plan_remediation(finding(), triage(), proposal(workflow_action="diagnose"))

    def test_auto_repair_requires_reversible_tested_authorized_safe_change(self):
        for changes in (
            {"reversible": False}, {"tests_covered": False}, {"within_authority": False},
        ):
            with self.subTest(changes=changes):
                decision = plan_remediation(finding(), triage(), proposal(**changes))["decision"]
                self.assertNotEqual(decision, "AUTO_REPAIR")
        self.assertEqual(
            plan_remediation(finding(evidence_state="STALE"), triage(), proposal())["decision"],
            "BLOCKED",
        )

    def test_escalation_conditions_force_human_gate(self):
        for condition in (
            "cost_change", "architecture_change", "consistency_risk",
            "business_semantics", "destructive_migration", "sensitive_data", "capacity_budget",
        ):
            with self.subTest(condition=condition):
                plan = plan_remediation(
                    finding(), triage(), proposal(triggered_conditions=[condition])
                )
                self.assertEqual(plan["decision"], "ESCALATE")
                self.assertTrue(plan["human_gate_required"])

    def test_before_after_requires_same_current_identity_and_budget_direction(self):
        before = finding()
        after = finding(
            classification="PERF_INFO",
            breach=False,
            observed={**finding()["observed"], "value": 220},
            evidence_ref="run:3",
        )
        result = evaluate_before_after(before, after)
        self.assertEqual((result["decision"], result["improved"], result["delta"]), ("ADOPT", True, -80))

        gte_before = copy.deepcopy(before)
        gte_after = copy.deepcopy(after)
        for item in (gte_before, gte_after):
            item["budget"] = {"operator": "gte", "value": 250, "unit": "ms"}
        gte_before["observed"]["value"], gte_after["observed"]["value"] = 220, 300
        self.assertEqual(evaluate_before_after(gte_before, gte_after)["decision"], "ADOPT")

        with self.assertRaisesRegex(PerformanceRemediationError, "identidades distintas"):
            evaluate_before_after(before, finding(surface="orders"))

    def test_non_improving_or_stale_after_is_never_adopted(self):
        before = finding()
        worse = finding(observed={**before["observed"], "value": 340}, evidence_ref="run:4")
        stale = finding(evidence_state="STALE", evidence_ref="run:5")
        self.assertEqual(evaluate_before_after(before, worse)["decision"], "REVERT_OR_REPLAN")
        self.assertEqual(evaluate_before_after(before, stale)["decision"], "REVERT_OR_REPLAN")

    def test_output_is_sanitized_non_executing_and_queue_only(self):
        plan = plan_remediation(finding(), triage(), proposal())
        self.assertFalse(plan["execute_actions"])
        self.assertEqual(plan["authority"], "unchanged")
        self.assertTrue(plan["queue_required"])
        self.assertEqual(plan["work_item"]["origin_system"], "factory")
        self.assertNotIn("password", str(plan).lower())
        docs = (ROOT / "docs" / "performance-remediation.md").read_text()
        self.assertIn("no crea WorkItems remotamente", docs)
        self.assertIn("Factory #269", docs)
        self.assertIn("#313", docs)


if __name__ == "__main__":
    unittest.main()
