import unittest
from pathlib import Path

from performance.detector import PerformanceDetectionError, detect_performance
from performance.triage import ROLE_HINTS, triage_performance

ROOT = Path(__file__).resolve().parents[1]


def contract():
    metric = {
        "id": "latency_p95", "label": "Latency p95",
        "baseline": {"value": 180, "unit": "ms", "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": 250, "unit": "ms"},
        "window": {"duration_seconds": 300, "min_samples": 20},
        "freshness": {"max_age_seconds": 900},
        "evidence": {"source": "ci", "ref": "run:1", "observed_at": "2026-09-28T20:00:00Z"},
        "allowed_actions": ["benchmark", "diagnose", "observe"],
        "escalation_conditions": ["architecture_change", "cost_change"],
    }
    return {
        "version": 1, "project": "condor",
        "surfaces": [{"id": "inventory", "label": "Inventory", "metrics": [metric]}],
    }


def observation(**overrides):
    data = {
        "version": 1, "project": "condor", "surface": "inventory",
        "metric": "latency_p95", "value": 300, "unit": "ms",
        "observed_at": "2026-09-28T20:05:00Z", "window_seconds": 300,
        "sample_count": 30, "severity": "high", "operational_impact": False,
        "bottleneck": "database", "evidence_ref": "run:2",
        "sha": "a" * 40, "release": "v1.2.3",
    }
    data.update(overrides)
    return data


class PerformanceDetectorTests(unittest.TestCase):
    NOW = "2026-09-28T20:06:00Z"

    def detect(self, **overrides):
        return detect_performance(contract(), observation(**overrides), evaluated_at=self.NOW)

    def test_budget_comparison_uses_exact_contract_metric(self):
        degraded, healthy = self.detect(), self.detect(value=220)
        self.assertTrue(degraded["breach"])
        self.assertEqual((degraded["classification"], degraded["delta"]), ("PERF_DEGRADATION", 120))
        self.assertFalse(healthy["breach"])
        self.assertEqual(healthy["classification"], "PERF_INFO")

        gte = contract()
        metric = gte["surfaces"][0]["metrics"][0]
        metric["budget"]["operator"] = "gte"
        metric["budget"]["value"] = 250
        below = detect_performance(
            gte, observation(value=220), evaluated_at="2026-09-28T20:06:00Z"
        )
        above = detect_performance(
            gte, observation(value=300), evaluated_at="2026-09-28T20:06:00Z"
        )
        self.assertTrue(below["breach"])
        self.assertFalse(above["breach"])

    def test_stale_insufficient_or_unknown_evidence_fails_closed(self):
        cases = (
            {"observed_at": "2026-09-28T19:00:00Z"},
            {"sample_count": 2},
            {"window_seconds": 30},
            {"metric": "missing_metric"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                result = self.detect(**overrides)
                self.assertEqual(result["classification"], "PERF_REVIEW")
                self.assertNotEqual(result["evidence_state"], "CURRENT")

    def test_incident_requires_critical_operational_impact_beyond_breach(self):
        critical_only = self.detect(severity="critical")
        incident = self.detect(severity="critical", operational_impact=True)
        self.assertEqual(critical_only["classification"], "PERF_DEGRADATION")
        self.assertEqual(incident["classification"], "PERF_INCIDENT")

    def test_triage_role_hints_are_closed_deterministic_and_non_authorizing(self):
        result = self.detect()
        first, second = triage_performance(result), triage_performance(result)
        self.assertEqual(first, second)
        self.assertEqual(first["role_hints"], sorted(ROLE_HINTS["database"]))
        self.assertEqual(first["authority"], "unchanged")
        self.assertFalse(first["execute_actions"])
        self.assertFalse(first["create_work_item"])

    def test_result_is_explainable_and_sanitized(self):
        result = self.detect()
        self.assertEqual(result["baseline"]["value"], 180)
        self.assertEqual(result["observed"]["value"], 300)
        self.assertEqual((result["observed"]["sample_count"], result["observed"]["window_seconds"]), (30, 300))
        self.assertEqual(result["freshness"]["max_age_seconds"], 900)
        self.assertEqual(result["identity"], {"sha": "a" * 40, "release": "v1.2.3"})
        self.assertEqual(result["evidence_ref"], "run:2")
        self.assertNotIn("payload", result)

        detection_contract = contract()
        for sensitive_ref in (
            "user@example.com",
            "192.168.1.10",
            "ghp_abcdefghijklmnopqrstuvwxyz123456",
        ):
            with self.subTest(sensitive_ref=sensitive_ref):
                sensitive_observation = observation(evidence_ref=sensitive_ref)
                with self.assertRaisesRegex(
                    PerformanceDetectionError,
                    "forma sensible",
                ):
                    detect_performance(
                        detection_contract,
                        sensitive_observation,
                        evaluated_at="2026-09-28T20:06:00Z",
                    )

        huge_observation = observation(value=10 ** 1000)
        with self.assertRaisesRegex(
            PerformanceDetectionError,
            "finito y acotado",
        ):
            detect_performance(
                detection_contract,
                huge_observation,
                evaluated_at="2026-09-28T20:06:00Z",
            )

    def test_docs_keep_detection_boundary_without_parallel_scheduler(self):
        docs = (ROOT / "docs" / "performance-detection.md").read_text()
        for expected in ("#312", "#313", "no crea scheduler ni backlog paralelo", "Factory Queue #269"):
            self.assertIn(expected, docs)


if __name__ == "__main__":
    unittest.main()
