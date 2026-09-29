import copy
import unittest
from pathlib import Path

from evolution.constitution import PROTECTED_INVARIANTS
from metricas.costos import load_budgets
from metricas.organizational_complexity import (
    build_complexity_report,
    compare_simplification,
    contextual_budget,
    evaluate_workitem_complexity,
)


ROOT = Path(__file__).resolve().parents[1]
BUDGETS = load_budgets(Path("metricas/presupuestos.json"), root=ROOT)


def observation(
    work_id="pl0n3r/Factory#245-before",
    *,
    comparison_scope="factory-245-comparable",
    task_type="infraestructura",
    task_size="small",
    risk="medium",
    rules=None,
    roles=None,
    reviewers=None,
    checks=None,
    handoffs=None,
    engines=None,
    context_tokens=8_000,
    coordination=10,
    wait=8,
    review=10,
    useful=40,
    protected=None,
):
    return {
        "version": 1,
        "work_id": work_id,
        "comparison_scope": comparison_scope,
        "task_type": task_type,
        "task_size": task_size,
        "risk": risk,
        "rules_consulted": rules or ["rule:constitution", "rule:factory-plan"],
        "active_roles": roles or ["role:architecture", "role:engineering"],
        "reviewers": reviewers or ["reviewer:qa"],
        "checks": checks or ["check:ci", "check:sonar"],
        "handoffs": handoffs or [],
        "engines_consulted": engines or ["engine:fitness"],
        "context_tokens": context_tokens,
        "coordination_minutes": coordination,
        "wait_minutes": wait,
        "review_minutes": review,
        "useful_execution_minutes": useful,
        "protected_metrics": protected or {
            key: 1.0 for key in PROTECTED_INVARIANTS
        },
        "evidence_refs": ["pl0n3r/Factory#245@event:measurement"],
        "observed_at": "2026-09-29T00:55:00Z",
    }


class OrganizationalComplexityTests(unittest.TestCase):
    def test_workitem_complexity_is_reproducible(self):
        first = observation()
        second = copy.deepcopy(first)
        second["rules_consulted"].reverse()
        second["checks"].reverse()
        left = evaluate_workitem_complexity(first, BUDGETS)
        right = evaluate_workitem_complexity(second, BUDGETS)
        self.assertEqual(left, right)
        self.assertRegex(left["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertNotIn("score", left)
        self.assertEqual(
            left["measurements"]["organizational_overhead_minutes"],
            28,
        )
        self.assertEqual(left["measurements"]["useful_execution_minutes"], 40)

    def test_budget_is_contextual_and_preserves_constitution(self):
        documentation = observation(
            task_type="documentacion",
            task_size="small",
            risk="low",
        )
        security = observation(
            task_type="seguridad",
            task_size="small",
            risk="high",
        )
        doc_budget = contextual_budget(documentation, BUDGETS)
        security_budget = contextual_budget(security, BUDGETS)

        self.assertNotEqual(
            doc_budget["limits"]["coordination_minutes"],
            security_budget["limits"]["coordination_minutes"],
        )
        self.assertNotEqual(
            doc_budget["limits"]["context_tokens"],
            security_budget["limits"]["context_tokens"],
        )
        self.assertEqual(
            set(doc_budget["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        self.assertEqual(
            set(security_budget["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        for protected in PROTECTED_INVARIANTS:
            self.assertNotIn(protected, doc_budget["limits"])
            self.assertNotIn(protected, security_budget["limits"])

    def test_excess_overhead_generates_simplification_candidate(self):
        item = observation(
            rules=[f"rule:{index}" for index in range(20)],
            roles=[f"role:{index}" for index in range(10)],
            reviewers=[f"reviewer:{index}" for index in range(6)],
            checks=[f"check:{index}" for index in range(16)],
            handoffs=[f"handoff:{index}" for index in range(5)],
            engines=[f"engine:{index}" for index in range(10)],
            context_tokens=40_000,
            coordination=80,
            wait=90,
            review=70,
            useful=30,
        )
        result = evaluate_workitem_complexity(item, BUDGETS)
        candidate = result["simplification_candidate"]

        self.assertTrue(result["over_budget_dimensions"])
        self.assertIsNotNone(candidate)
        self.assertEqual(
            candidate["target_dimensions"],
            result["over_budget_dimensions"],
        )
        self.assertEqual(
            candidate["evidence_refs"],
            item["evidence_refs"],
        )
        self.assertEqual(
            set(candidate["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        self.assertEqual(candidate["authority"], "unchanged")
        self.assertFalse(candidate["execute"])

    def test_simplification_requires_no_protected_regression(self):
        before = observation(
            context_tokens=20_000,
            coordination=40,
            wait=30,
            review=30,
            useful=40,
        )
        after = observation(
            "pl0n3r/Factory#245-after",
            context_tokens=10_000,
            coordination=20,
            wait=15,
            review=15,
            useful=40,
        )
        regressed = copy.deepcopy(after)
        regressed["protected_metrics"]["security"] = 0.9

        blocked = compare_simplification(before, regressed)
        self.assertEqual(blocked["fitness"]["claim"], "blocked")
        self.assertIn(
            "security",
            blocked["fitness"]["protected_regressions"],
        )
        self.assertFalse(blocked["can_claim_simplification"])

        improved = compare_simplification(before, after)
        self.assertEqual(improved["fitness"]["claim"], "improved")
        self.assertFalse(improved["fitness"]["protected_regressions"])
        self.assertTrue(improved["can_claim_simplification"])
        self.assertEqual(improved["authority"], "unchanged")
        self.assertFalse(improved["execute"])

    def test_report_separates_execution_and_overhead(self):
        first = observation(
            "pl0n3r/Factory#245-a",
            coordination=10,
            wait=5,
            review=5,
            useful=40,
        )
        second = observation(
            "pl0n3r/Factory#245-b",
            coordination=20,
            wait=10,
            review=10,
            useful=60,
        )
        report = build_complexity_report([second, first], BUDGETS)

        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["useful_execution_minutes"], 100)
        self.assertEqual(report["organizational_overhead_minutes"], 60)
        self.assertEqual(report["total_minutes"], 160)
        self.assertEqual(report["overhead_ratio"], 0.375)
        self.assertEqual(
            set(report["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        self.assertRegex(report["fingerprint"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
