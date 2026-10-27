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
        disallowed = proposal(workflow_action="diagnose")
        material = finding()
        staffing = triage()
        with self.assertRaisesRegex(PerformanceRemediationError, "no está permitida"):
            plan_remediation(material, staffing, disallowed)

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

    def test_plan_rejects_unhashable_or_wrong_typed_triggered_conditions(self):
        invalid_cases = (
            [["cost_change"]],
            [{"condition": "cost_change"}],
            [None],
            [True],
            [1],
            ["not_in_catalog"],
            "cost_change",
        )
        for conditions in invalid_cases:
            with self.subTest(conditions=conditions):
                with self.assertRaisesRegex(
                    PerformanceRemediationError,
                    "triggered_conditions fuera de catálogo",
                ):
                    plan_remediation(
                        finding(), triage(),
                        proposal(triggered_conditions=conditions),
                    )

    def test_plan_preserves_valid_triggered_conditions_and_rejects_duplicates(self):
        escalated = plan_remediation(
            finding(), triage(), proposal(triggered_conditions=["cost_change"]),
        )
        self.assertEqual(escalated["decision"], "ESCALATE")
        self.assertEqual(escalated["reasons"], ["cost_change"])
        self.assertTrue(escalated["human_gate_required"])
        self.assertFalse(escalated["execute_actions"])
        with self.assertRaisesRegex(
            PerformanceRemediationError, "triggered_conditions fuera de catálogo",
        ):
            plan_remediation(
                finding(), triage(),
                proposal(triggered_conditions=["cost_change", "cost_change"]),
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
            observed={**finding()["observed"], "value": 220,
                      "observed_at": "2026-09-28T20:06:00Z"},
            identity={"sha": "b" * 40, "release": "v1.2.4"},
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

        other_surface = finding(surface="orders")
        with self.assertRaisesRegex(PerformanceRemediationError, "identidades distintas"):
            evaluate_before_after(before, other_surface)

    def test_before_after_rejects_same_timestamp_and_repeated_ref(self):
        old = finding()
        new = finding(
            classification="PERF_INFO", breach=False,
            observed={**old["observed"], "value": 220},
            identity={"sha": "b" * 40, "release": "v1.2.4"},
            evidence_ref="run:3",
        )
        duplicate_time = evaluate_before_after(old, new)
        self.assertEqual(duplicate_time["decision"], "REVERT_OR_REPLAN")
        self.assertEqual(duplicate_time["reasons"], ["after_not_later"])
        self.assertFalse(duplicate_time["improved"])

        later = copy.deepcopy(new)
        later["observed"]["observed_at"] = "2026-09-28T20:06:00Z"
        later["evidence_ref"] = old["evidence_ref"]
        duplicate_ref = evaluate_before_after(old, later)
        self.assertEqual(duplicate_ref["decision"], "REVERT_OR_REPLAN")
        self.assertEqual(duplicate_ref["reasons"], ["reused_evidence_ref"])

        earlier = copy.deepcopy(new)
        earlier["observed"]["observed_at"] = "2026-09-28T20:04:00Z"
        self.assertEqual(
            evaluate_before_after(old, earlier)["reasons"], ["after_not_later"]
        )

    def test_before_after_requires_distinct_build_identity(self):
        old = finding()
        later = finding(
            classification="PERF_INFO", breach=False,
            observed={**old["observed"], "value": 220,
                      "observed_at": "2026-09-28T20:06:00Z"},
            evidence_ref="run:3",
        )
        unchanged = evaluate_before_after(old, later)
        self.assertEqual(unchanged["decision"], "REVERT_OR_REPLAN")
        self.assertEqual(unchanged["reasons"], ["unchanged_build_identity"])
        self.assertFalse(unchanged["improved"])

        missing = copy.deepcopy(later)
        missing["identity"] = {"sha": None, "release": None}
        self.assertEqual(
            evaluate_before_after(old, missing)["reasons"], ["unchanged_build_identity"]
        )

    def test_before_after_adopts_only_newer_distinct_current_evidence(self):
        old = finding()
        later = finding(
            classification="PERF_INFO", breach=False,
            observed={**old["observed"], "value": 220,
                      "observed_at": "2026-09-28T20:06:00Z"},
            evidence_ref="run:3",
            identity={"sha": "b" * 40, "release": "v1.2.4"},
        )
        comparison = evaluate_before_after(old, later)
        self.assertEqual(comparison["decision"], "ADOPT")
        self.assertTrue(comparison["improved"])
        self.assertEqual(comparison["delta"], -80)
        self.assertFalse(comparison["execute_actions"])

        # A versioned configuration change may keep SHA, but needs a new release.
        release_only = copy.deepcopy(later)
        release_only["identity"] = {"sha": "a" * 40, "release": "v1.2.4"}
        self.assertEqual(
            evaluate_before_after(old, release_only)["decision"], "ADOPT"
        )

    def test_before_after_invalid_timestamps_fail_closed(self):
        old = finding()
        later = finding(
            classification="PERF_INFO", breach=False,
            observed={**old["observed"], "value": 220,
                      "observed_at": "2026-09-28T20:06:00Z"},
            evidence_ref="run:3",
            identity={"sha": "b" * 40, "release": "v1.2.4"},
        )
        for invalid in (None, "not-a-time", "2026-09-28T20:06:00",
                        "2026-09-28T20:06:00+00:00",
                        "2026-02-30T20:06:00Z"):
            with self.subTest(invalid=invalid):
                changed = copy.deepcopy(later)
                changed["observed"]["observed_at"] = invalid
                with self.assertRaises(PerformanceRemediationError):
                    evaluate_before_after(old, changed)
        for identity in ({}, {"sha": "broken", "release": "v1.2.4"}):
            with self.subTest(identity=identity):
                changed = copy.deepcopy(later)
                changed["identity"] = identity
                with self.assertRaises(PerformanceRemediationError):
                    evaluate_before_after(old, changed)

    def test_before_after_rejects_impossible_sample_count_and_window(self):
        original = finding()
        newer = finding(
            classification="PERF_INFO", breach=False,
            observed={**original["observed"], "value": 220,
                      "observed_at": "2026-09-28T20:06:00Z"},
            evidence_ref="run:3",
            identity={"sha": "b" * 40, "release": "v1.2.4"},
        )
        for side in ("before", "after"):
            for field in ("sample_count", "window_seconds"):
                for invalid in (0, -1, True, 1.5, 31_536_001, None):
                    with self.subTest(side=side, field=field, invalid=invalid):
                        before, after = copy.deepcopy(original), copy.deepcopy(newer)
                        value = before if side == "before" else after
                        value["observed"][field] = invalid
                        with self.assertRaises(PerformanceRemediationError):
                            evaluate_before_after(before, after)

    def test_before_after_rejects_invalid_measurement_values(self):
        original = finding()
        newer = finding(
            classification="PERF_INFO", breach=False,
            observed={**original["observed"], "value": 220,
                      "observed_at": "2026-09-28T20:06:00Z"},
            evidence_ref="run:3",
            identity={"sha": "b" * 40, "release": "v1.2.4"},
        )
        for side in ("before", "after"):
            for invalid in (None, "220", True, float("nan"), float("inf"),
                            float("-inf"), 10**16):
                with self.subTest(side=side, invalid=str(invalid)):
                    before, after = copy.deepcopy(original), copy.deepcopy(newer)
                    value = before if side == "before" else after
                    value["observed"]["value"] = invalid
                    with self.assertRaises(PerformanceRemediationError):
                        evaluate_before_after(before, after)
        for invalid_budget in (
            {"operator": "lte", "value": float("nan"), "unit": "ms"},
            {"operator": "wrong", "value": 250, "unit": "ms"},
            {"operator": "lte", "value": 250, "unit": "bytes"},
        ):
            with self.subTest(budget=invalid_budget):
                before, after = copy.deepcopy(original), copy.deepcopy(newer)
                before["budget"] = dict(invalid_budget)
                after["budget"] = dict(invalid_budget)
                with self.assertRaises(PerformanceRemediationError):
                    evaluate_before_after(before, after)

    def test_before_after_valid_sampled_measurement_still_adopts(self):
        original = finding()
        newer = finding(
            classification="PERF_INFO", breach=False,
            observed={**original["observed"], "value": 220,
                      "observed_at": "2026-09-28T20:06:00Z",
                      "sample_count": 31_536_000, "window_seconds": 31_536_000},
            evidence_ref="run:3",
            identity={"sha": "b" * 40, "release": "v1.2.4"},
        )
        comparison = evaluate_before_after(original, newer)
        self.assertEqual(comparison["decision"], "ADOPT")
        self.assertTrue(comparison["improved"])
        self.assertEqual(comparison["delta"], -80)
        self.assertFalse(comparison["execute_actions"])

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

        foreign = proposal()
        foreign["work_item"] = {**work_item(), "project_id": "brvtal"}
        with self.assertRaisesRegex(
            PerformanceRemediationError,
            "ligado al hallazgo",
        ):
            plan_remediation(finding(), triage(), foreign)

        with self.assertRaisesRegex(
            PerformanceRemediationError,
            "sensible",
        ):
            plan_remediation(
                finding(),
                triage(),
                proposal(hypothesis_ref="user@example.com"),
            )

        sensitive_work = work_item()
        sensitive_work["evidence_refs"] = ["user@example.com"]
        with self.assertRaisesRegex(
            PerformanceRemediationError,
            "sensible",
        ):
            plan_remediation(
                finding(),
                triage(),
                proposal(work_item=sensitive_work),
            )

        docs = (ROOT / "docs" / "performance-remediation.md").read_text()
        self.assertIn("no crea WorkItems remotamente", docs)
        self.assertIn("Factory #269", docs)
        self.assertIn("#313", docs)


if __name__ == "__main__":
    unittest.main()
