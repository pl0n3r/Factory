import json
import tempfile
import unittest
from pathlib import Path

from costos import CostError, ci_trend, evaluate_pr, load_budgets


BUDGETS = {
    "schema_version": 1,
    "global_limits": {"commits": 10, "review_rounds": 3},
    "sizes": {
        "small": {"tokens": 100, "ci_minutes": 10, "agent_minutes": 20},
        "medium": {"tokens": 200, "ci_minutes": 20, "agent_minutes": 40},
        "large": {"tokens": 400, "ci_minutes": 40, "agent_minutes": 80},
    },
    "task_type_multipliers": {"default": 1.0, "infraestructura": 1.2},
}


def event(marker=None, commits=2):
    body = "Closes #7"
    if marker is not None:
        body += "\n<!-- factory-cost " + json.dumps(marker, separators=(",", ":")) + " -->"
    return {"repository": {"full_name": "pl0n3r/factory"},
            "pull_request": {"number": 17, "body": body, "commits": commits}}


def marker(**changes):
    value = {"task_type": "infraestructura", "size": "small", "tokens": 60,
             "ci_minutes": 5, "agent_minutes": 10, "review_rounds": 1}
    value.update(changes)
    return value


def write_budget(tmp, data):
    path = Path(tmp) / "budgets.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class CostTests(unittest.TestCase):
    def test_declared_usage_never_reports_verified_ok(self):
        result = evaluate_pr(event(marker()), BUDGETS)
        self.assertEqual(result["status"], "warning")
        self.assertFalse(result["verified"])
        self.assertEqual(result["usage_sources"]["commits"], "observed")
        self.assertEqual(result["usage_sources"]["tokens"], "declared")
        self.assertIn("unverified:tokens", result["reasons"])

    def test_near_limit_warns_and_over_limit_soft_blocks(self):
        warning = evaluate_pr(event(marker(tokens=100)), BUDGETS)
        self.assertEqual(warning["status"], "warning")
        blocked = evaluate_pr(event(marker(tokens=121), commits=11), BUDGETS)
        self.assertEqual(blocked["status"], "soft-block")
        self.assertIn("over:tokens", blocked["reasons"])
        self.assertIn("over:commits", blocked["reasons"])

    def test_missing_marker_is_soft_block_not_silent(self):
        result = evaluate_pr(event(), BUDGETS)
        self.assertEqual(result["status"], "soft-block")
        self.assertEqual(result["reasons"], ["missing-cost-marker"])
        self.assertEqual(result["usage_sources"], {"commits": "observed"})

    def test_invalid_usage_fails_closed(self):
        with self.assertRaisesRegex(CostError, "tokens"):
            evaluate_pr(event(marker(tokens=-1)), BUDGETS)

    def test_budget_root_must_be_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(CostError, "raíz de objeto JSON"):
                load_budgets(write_budget(tmp, []))

    def test_boolean_budget_and_multiplier_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["sizes"]["small"]["tokens"] = True
            with self.assertRaisesRegex(CostError, "Presupuesto inválido"):
                load_budgets(write_budget(tmp, changed))
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["task_type_multipliers"]["default"] = True
            with self.assertRaisesRegex(CostError, "Multiplicador inválido"):
                load_budgets(write_budget(tmp, changed))

    def test_multiplier_cannot_round_effective_budget_to_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["task_type_multipliers"]["tiny"] = 0.001
            with self.assertRaisesRegex(CostError, "presupuesto efectivo menor que 1"):
                load_budgets(write_budget(tmp, changed))

    def test_global_limits_cannot_be_relaxed(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["global_limits"]["commits"] = 11
            with self.assertRaisesRegex(CostError, "exactamente 10 commits"):
                load_budgets(write_budget(tmp, changed))

    def test_ci_trend_groups_all_completed_runs_by_pr(self):
        rows = [
            {"pr_number": 1, "run_id": 101, "conclusion": "failure",
             "created_at": "2026-01-01T00:00:00Z", "ci_minutes": 10},
            {"pr_number": 1, "run_id": 102, "conclusion": "success",
             "created_at": "2026-01-01T01:00:00Z", "ci_minutes": 20},
            {"pr_number": 2, "run_id": 201, "conclusion": "cancelled",
             "created_at": "2026-01-02T00:00:00Z", "ci_minutes": 10},
            {"pr_number": 2, "run_id": 202, "conclusion": "success",
             "created_at": "2026-01-02T01:00:00Z", "ci_minutes": 10},
            {"pr_number": 3, "run_id": 301, "conclusion": "success",
             "created_at": "2026-02-01T00:00:00Z", "ci_minutes": 10},
            {"pr_number": 4, "run_id": 401, "conclusion": "success",
             "created_at": "2026-02-02T00:00:00Z", "ci_minutes": 5},
        ]
        result = ci_trend(rows)
        self.assertEqual(result["metric"], "ci_minutes_per_pr")
        self.assertEqual(result["samples"], 4)
        self.assertEqual(result["run_samples"], 6)
        self.assertEqual(result["included_conclusions"], ["cancelled", "failure", "success"])
        self.assertEqual(result["before_avg"], 25.0)
        self.assertEqual(result["after_avg"], 7.5)
        self.assertEqual(result["delta_pct"], -70.0)

    def test_ci_trend_rejects_duplicate_run_ids(self):
        row = {"pr_number": 1, "run_id": 101, "conclusion": "success",
               "created_at": "2026-01-01T00:00:00Z", "ci_minutes": 10}
        with self.assertRaisesRegex(CostError, "run_id duplicado"):
            ci_trend([row, dict(row)])


if __name__ == "__main__":
    unittest.main()
