import unittest
from pathlib import Path

from performance.detector import detect_performance
from performance.triage import ROLE_HINTS, triage_performance

ROOT = Path(__file__).resolve().parents[1]


def contract():
    return {
        "version": 1,
        "project": "condor",
        "surfaces": [{
            "id": "inventory",
            "label": "Inventory",
            "metrics": [{
                "id": "latency_p95",
                "label": "Latency p95",
                "baseline": {"value": 180, "unit": "ms", "observed_at": "2026-09-28T20:00:00Z"},
                "budget": {"operator": "lte", "value": 250, "unit": "ms"},
                "window": {"duration_seconds": 300, "min_samples": 20},
                "freshness": {"max_age_seconds": 900},
                "evidence": {"source": "ci", "ref": "run:1", "observed_at": "2026-09-28T20:00:00Z"},
                "allowed_actions": ["benchmark", "diagnose", "observe"],
                "escalation_conditions": ["architecture_change", "cost_change"],
            }],
        }],
    }


def observation(**overrides):
    data = {
        "version": 1,
        "project": "condor",
        "surface": "inventory",
        "metric": "latency_p95",
        "value": 300,
        "unit": "ms",
        "observed_at": "2026-09-28T20:05:00Z",
        "window_seconds": 300,
        "sample_count": 30,
        "severity": "high",
        "operational_impact": False,
        "bottleneck": "database",
        "evidence_ref": "run:2",
        "sha": "a" * 40,
        "release": "v1.2.3",
    }
    data.update(overrides)
    return data


class PerformanceDetectorTests(unittest.TestCase):
    def test_budget_comparison_uses_exact_contract_metric(self):
        degraded = detect_performance(
            contract(), observation(), evaluated_at="2026-09-28T20:06:00Z"
        )
        healthy = detect_performance(
            contract(), observation(value=220), evaluated_at="2026-09-28T20:06:00Z"
        )
        self.assertTrue(degraded["breach"])
        self.assertEqual(degraded["classification"], "PERF_DEGRADATION")
        self.assertEqual(degraded["delta"], 120)
        self.assertFalse(healthy["breach"])
        self.assertEqual(healthy["classification"], "PERF_INFO")

    def test_stale_insufficient_or_unknown_evidence_fails_closed(self):
        cases = [
            observation(observed_at="2026-09-28T19:00:00Z"),
            observation(sample_count=2),
            observation(window_seconds=30),
            observation(metric="missing_metric"),
        ]
        for item in cases:
            with self.subTest(item=item["metric"]):
                result = detect_performance(
                    contract(), item, evaluated_at="2026-09-28T20:06:00Z"
                )
                self.assertEqual(result["classification"], "PERF_REVIEW")
                self.assertNotEqual(result["evidence_state"], "CURRENT")

    def test_incident_requires_critical_operational_impact_beyond_breach(self):
        critical_only = detect_performance(
            contract(), observation(severity="critical"),
            evaluated_at="2026-09-28T20:06:00Z",
        )
        incident = detect_performance(
            contract(), observation(severity="critical", operational_impact=True),
            evaluated_at="2026-09-28T20:06:00Z",
        )
        self.assertEqual(critical_only["classification"], "PERF_DEGRADATION")
        self.assertEqual(incident["classification"], "PERF_INCIDENT")

    def test_triage_role_hints_are_closed_deterministic_and_non_authorizing(self):
        result = detect_performance(
            contract(), observation(), evaluated_at="2026-09-28T20:06:00Z"
        )
        first = triage_performance(result)
        second = triage_performance(result)
        self.assertEqual(first, second)
        self.assertEqual(first["role_hints"], sorted(ROLE_HINTS["database"]))
        self.assertEqual(first["authority"], "unchanged")
        self.assertFalse(first["execute_actions"])
        self.assertFalse(first["create_work_item"])

    def test_result_is_explainable_and_sanitized(self):
        result = detect_performance(
            contract(), observation(), evaluated_at="2026-09-28T20:06:00Z"
        )
        self.assertEqual(result["baseline"]["value"], 180)
        self.assertEqual(result["observed"]["value"], 300)
        self.assertEqual(result["observed"]["sample_count"], 30)
        self.assertEqual(result["observed"]["window_seconds"], 300)
        self.assertEqual(result["freshness"]["max_age_seconds"], 900)
        self.assertEqual(result["identity"]["sha"], "a" * 40)
        self.assertEqual(result["identity"]["release"], "v1.2.3")
        self.assertEqual(result["evidence_ref"], "run:2")
        self.assertNotIn("payload", result)

    def test_docs_keep_detection_boundary_without_parallel_scheduler(self):
        docs = (ROOT / "docs" / "performance-detection.md").read_text()
        self.assertIn("#312", docs)
        self.assertIn("#313", docs)
        self.assertIn("no crea scheduler ni backlog paralelo", docs)
        self.assertIn("Factory Queue #269", docs)


if __name__ == "__main__":
    unittest.main()
