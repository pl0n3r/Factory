import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from costos import CostError, ci_trend, evaluate_pr, load_budgets, main


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
                (write_budget(tmp, []), load_budgets(Path("budgets.json"), root=Path(tmp)))[1]

    def test_boolean_budget_and_multiplier_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["sizes"]["small"]["tokens"] = True
            with self.assertRaisesRegex(CostError, "Presupuesto inválido"):
                (write_budget(tmp, changed), load_budgets(Path("budgets.json"), root=Path(tmp)))[1]
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["task_type_multipliers"]["default"] = True
            with self.assertRaisesRegex(CostError, "Multiplicador inválido"):
                (write_budget(tmp, changed), load_budgets(Path("budgets.json"), root=Path(tmp)))[1]

    def test_multiplier_cannot_round_effective_budget_to_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["task_type_multipliers"]["tiny"] = 0.001
            with self.assertRaisesRegex(CostError, "presupuesto efectivo menor que 1"):
                (write_budget(tmp, changed), load_budgets(Path("budgets.json"), root=Path(tmp)))[1]

    def test_global_limits_cannot_be_relaxed(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(json.dumps(BUDGETS))
            changed["global_limits"]["commits"] = 11
            with self.assertRaisesRegex(CostError, "exactamente 10 commits"):
                (write_budget(tmp, changed), load_budgets(Path("budgets.json"), root=Path(tmp)))[1]

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


    def test_cli_paths_are_confined_to_trusted_root(self):
        """Rechaza traversal y escapes por symlink en toda la superficie CLI."""
        invalid = [
            ("--event", "../event.json"),
            ("--budgets", "../presupuestos.json"),
            ("--json-out", "/tmp/escape.json"),
            ("--markdown-out", "artifacts/../escape.md"),
        ]
        for flag, value in invalid:
            with self.subTest(flag=flag):
                with self.assertRaises(SystemExit):
                    main(["pr", flag, value], input_stream=StringIO("{}"))

        with self.assertRaises(SystemExit):
            main(
                ["trend", "--input", "../history.json"],
                input_stream=StringIO("[]"),
            )

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / "metricas").mkdir()
            (root / "metricas/presupuestos.json").write_text(
                json.dumps(BUDGETS),
                encoding="utf-8",
            )
            (root / "artifacts").symlink_to(
                Path(outside),
                target_is_directory=True,
            )
            rc = main(
                ["pr"],
                root=root,
                input_stream=StringIO(json.dumps(event(marker()))),
            )
            self.assertEqual(rc, 2)
            self.assertFalse((Path(outside) / "presupuesto-pr.json").exists())

    def test_cli_valid_paths_preserve_cost_outputs(self):
        """Mantiene los artefactos esperados para PR y tendencia con rutas cerradas."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metricas").mkdir()
            (root / "metricas/presupuestos.json").write_text(
                json.dumps(BUDGETS),
                encoding="utf-8",
            )

            rc = main(
                [
                    "pr",
                    "--event", "-",
                    "--budgets", "metricas/presupuestos.json",
                    "--json-out", "artifacts/presupuesto-pr.json",
                    "--markdown-out", "artifacts/presupuesto-pr.md",
                ],
                root=root,
                input_stream=StringIO(json.dumps(event(marker()))),
            )
            self.assertEqual(rc, 0)
            result = json.loads(
                (root / "artifacts/presupuesto-pr.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result["status"], "warning")
            self.assertTrue(
                (root / "artifacts/presupuesto-pr.md").is_file()
            )

            rows = [
                {
                    "pr_number": number,
                    "run_id": 100 + number,
                    "conclusion": "success",
                    "created_at": f"2026-01-0{number}T00:00:00Z",
                    "ci_minutes": number,
                }
                for number in range(1, 5)
            ]
            rc = main(
                ["trend", "--input", "-", "--json-out", "artifacts/ci-trend.json"],
                root=root,
                input_stream=StringIO(json.dumps(rows)),
            )
            self.assertEqual(rc, 0)
            trend = json.loads(
                (root / "artifacts/ci-trend.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(trend["metric"], "ci_minutes_per_pr")


if __name__ == "__main__":
    unittest.main()
