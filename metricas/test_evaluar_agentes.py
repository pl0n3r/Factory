import json
import tempfile
import unittest
from pathlib import Path

from evaluar_agentes import ValidationError, aggregate, load_records, render_markdown, validate_record


def record(task_id, task_type="backend", model="sol", prompt="p1", **changes):
    base = {
        "task_id": task_id, "task_type": task_type, "agent": "gpt", "model": model,
        "prompt_id": prompt, "roles": ["ingenieria-software"], "success": True,
        "merged_first_try": True, "commits": 2, "review_rounds": 1,
        "rework_commits": 0, "incidents_after": 0, "completed_at": "2026-09-24T05:00:00Z",
        "tokens_input": 100, "tokens_output": 50, "ci_minutes": 4, "agent_minutes": 12,
    }
    base.update(changes)
    return base


class EvaluationTests(unittest.TestCase):
    def test_ranking_is_separate_by_task_type_and_deterministic(self):
        records = [
            validate_record(record("r#1", model="sol"), "1"),
            validate_record(record("r#2", model="sol"), "2"),
            validate_record(record("r#3", model="luna", success=False, merged_first_try=False,
                                   incidents_after=1, rework_commits=2), "3"),
            validate_record(record("r#4", model="luna"), "4"),
            validate_record(record("r#5", task_type="frontend", model="luna"), "5"),
            validate_record(record("r#6", task_type="frontend", model="luna"), "6"),
            validate_record(record("r#7", task_type="frontend", model="sol", rework_commits=1), "7"),
            validate_record(record("r#8", task_type="frontend", model="sol", rework_commits=1), "8"),
        ]
        report = aggregate(records, min_samples=2)
        self.assertEqual(report["task_types"]["backend"]["configurations"][0]["configuration"]["model"], "sol")
        self.assertEqual(report["task_types"]["backend"]["configurations"][0]["rank"], 1)
        self.assertIsNotNone(report["task_types"]["backend"]["recommendation"])
        self.assertEqual({row["rank"] for row in report["task_types"]["frontend"]["configurations"]}, {1, 2})

    def test_insufficient_sample_never_fabricates_recommendation(self):
        report = aggregate([validate_record(record("r#1"), "1")], min_samples=2)
        data = report["task_types"]["backend"]
        self.assertIsNone(data["recommendation"])
        self.assertIsNone(data["configurations"][0]["rank"])
        self.assertEqual(data["configurations"][0]["sample_status"], "insufficient_data")
        self.assertIn("Sin recomendación", render_markdown(report))

    def test_exact_quality_tie_has_no_recommendation(self):
        records = []
        for index in range(1, 4):
            records.append(validate_record(record(f"r#{index}", model="sol"), f"sol-{index}"))
            records.append(validate_record(record(f"r#{index + 10}", model="luna"), f"luna-{index}"))
        report = aggregate(records, min_samples=3)
        data = report["task_types"]["backend"]
        self.assertIsNone(data["recommendation"])
        self.assertEqual(data["recommendation_status"], "tie-or-incomplete-cost")
        self.assertEqual({row["rank"] for row in data["configurations"]}, {1})

    def test_partial_token_telemetry_never_becomes_zero_cost(self):
        records = [
            validate_record(record("r#1", model="sol", tokens_output=None), "1"),
            validate_record(record("r#2", model="sol"), "2"),
            validate_record(record("r#3", model="luna"), "3"),
            validate_record(record("r#4", model="luna"), "4"),
        ]
        report = aggregate(records, min_samples=2)
        rows = {row["configuration"]["model"]: row for row in report["task_types"]["backend"]["configurations"]}
        self.assertIsNone(rows["sol"]["tokens_avg"])
        self.assertEqual(rows["sol"]["tokens_complete_samples"], 1)
        self.assertIsNone(report["task_types"]["backend"]["recommendation"])
        self.assertEqual(report["task_types"]["backend"]["recommendation_status"], "tie-or-incomplete-cost")

    def test_empty_aggregate_is_stable_and_has_no_ranking(self):
        report = aggregate([], min_samples=1)
        self.assertEqual(report["records"], 0)
        self.assertEqual(report["task_types"], {})

    def test_same_input_produces_same_report(self):
        records = [validate_record(record("r#1"), "1")]
        self.assertEqual(aggregate(records, min_samples=1), aggregate(records, min_samples=1))

    def test_rejects_unknown_fields_and_review_rounds_over_limit(self):
        bad = record("r#1", unexpected_field="no")
        with self.assertRaisesRegex(ValidationError, "campos no permitidos"):
            validate_record(bad, "fixture")
        with self.assertRaisesRegex(ValidationError, "no puede superar 3"):
            validate_record(record("r#2", review_rounds=4), "fixture")

    def test_rejects_free_text_identity_fields(self):
        with self.assertRaisesRegex(ValidationError, "identificador"):
            validate_record(record("repo#9", prompt_id="prompt con texto"), "fixture")
        with self.assertRaisesRegex(ValidationError, "repo#N"):
            validate_record(record("correo@example.com"), "fixture")

    def test_duplicate_task_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text("\n".join(json.dumps(record("r#1")) for _ in range(2)), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "task_id duplicado"):
                load_records([path])

    def test_month_filter_uses_utc_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            rows = [
                record("r#10", completed_at="2026-09-01T00:00:00Z"),
                record("r#11", completed_at="2026-09-30T23:59:59Z"),
                record("r#12", completed_at="2026-10-01T00:30:00+01:00"),
                record("r#13", completed_at="2026-10-01T00:00:00Z"),
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            september = load_records([path], month="2026-09")
            self.assertEqual([row["task_id"] for row in september], ["r#10", "r#11", "r#12"])

    def test_month_outside_datetime_range_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for value in ("0000-01", "9999-12"):
                with self.subTest(month=value):
                    with self.assertRaisesRegex(ValidationError, "rango"):
                        load_records([directory], allow_empty=True, month=value)

    def test_symlink_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "real.jsonl"
            target.write_text(json.dumps(record("r#1")), encoding="utf-8")
            link = directory / "linked.jsonl"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValidationError, "enlaces simbólicos"):
                load_records([link])

    def test_oversized_line_is_rejected_without_echoing_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text("x" * 100_001, encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "supera el máximo"):
                load_records([path])

    def test_invalid_month_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValidationError, "YYYY-MM"):
                load_records([Path(tmp)], allow_empty=True, month="2026-13")

    def test_empty_directory_is_allowed_only_when_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with self.assertRaisesRegex(ValidationError, "No se encontraron"):
                load_records([directory])
            self.assertEqual(load_records([directory], allow_empty=True), [])


if __name__ == "__main__":
    unittest.main()
