"""Regresión offline: todos los contadores validados están acotados (#1217)."""

import json
import math
import unittest

from metricas.evaluar_agentes import (
    MAX_METRIC_INTEGER,
    ValidationError,
    aggregate,
    validate_record,
)


def fixture(task_id="factory#1", **updates):
    record = {
        "task_id": task_id,
        "task_type": "backend",
        "agent": "gpt",
        "model": "model-test",
        "prompt_id": "bounded-v1",
        "roles": ["ingenieria-software"],
        "success": True,
        "merged_first_try": True,
        "commits": 1,
        "review_rounds": 1,
        "rework_commits": 0,
        "incidents_after": 0,
        "completed_at": "2026-10-11T09:00:00Z",
        "tokens_input": 10,
        "tokens_output": 20,
        "ci_minutes": 2,
        "agent_minutes": 4,
    }
    record.update(updates)
    return record


class MetricIntegerBoundsTests(unittest.TestCase):
    METRIC_FIELDS = (
        "commits", "rework_commits", "incidents_after",
        "tokens_input", "tokens_output", "ci_minutes", "agent_minutes",
    )

    def test_huge_integer_fields_rejected_with_typed_error(self):
        hostile = 10**500
        for field in ("commits", "incidents_after", "tokens_input", "agent_minutes"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as raised:
                    validate_record(fixture(**{field: hostile}), "synthetic")
                message = str(raised.exception)
                self.assertIn(field, message)
                self.assertIn("máximo", message)
                self.assertNotIn(str(hostile), message)
                self.assertNotIn("OverflowError", message)

    def test_numeric_bounds_and_existing_type_rules(self):
        self.assertEqual(MAX_METRIC_INTEGER, 1_000_000_000_000)
        for field in self.METRIC_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(
                    validate_record(fixture(**{field: 0}), "zero")[field], 0
                )
                self.assertEqual(
                    validate_record(fixture(**{field: MAX_METRIC_INTEGER}), "max")[field],
                    MAX_METRIC_INTEGER,
                )
                with self.assertRaises(ValidationError):
                    validate_record(
                        fixture(**{field: MAX_METRIC_INTEGER + 1}), "too-large"
                    )
                for invalid in (True, 1.5, "7", -1):
                    with self.subTest(field=field, invalid=repr(invalid)):
                        with self.assertRaises(ValidationError):
                            validate_record(fixture(**{field: invalid}), "invalid")
        for field in ("tokens_input", "tokens_output", "ci_minutes", "agent_minutes"):
            with self.subTest(optional=field):
                self.assertIsNone(
                    validate_record(fixture(**{field: None}), "missing")[field]
                )
        self.assertEqual(
            validate_record(fixture(review_rounds=3), "review")["review_rounds"], 3
        )
        with self.assertRaises(ValidationError):
            validate_record(fixture(review_rounds=4), "review")

    def test_valid_bounded_numbers_aggregate_to_finite_json(self):
        maximum = MAX_METRIC_INTEGER
        high = validate_record(fixture(
            "factory#1", commits=maximum, rework_commits=maximum,
            incidents_after=maximum, tokens_input=maximum,
            tokens_output=maximum, ci_minutes=maximum,
            agent_minutes=maximum, review_rounds=3,
        ), "high")
        low = validate_record(fixture(
            "factory#2", commits=0, rework_commits=0,
            incidents_after=0, tokens_input=0, tokens_output=0,
            ci_minutes=0, agent_minutes=0, review_rounds=0,
        ), "low")
        report = aggregate([high, low], min_samples=3)
        self.assertEqual(report, aggregate([low, high], min_samples=3))
        row = report["task_types"]["backend"]["configurations"][0]
        self.assertEqual(row["commits_avg"], maximum / 2)
        self.assertEqual(row["tokens_avg"], maximum)
        self.assertTrue(math.isfinite(row["incidents_per_task"]))
        self.assertTrue(math.isfinite(row["agent_minutes_avg"]))
        self.assertEqual(row["sample_status"], "insufficient_data")
        self.assertIsNone(report["task_types"]["backend"]["recommendation"])
        self.assertEqual(
            json.dumps(report, sort_keys=True, allow_nan=False),
            json.dumps(aggregate([high, low], min_samples=3),
                       sort_keys=True, allow_nan=False),
        )


if __name__ == "__main__":
    unittest.main()
