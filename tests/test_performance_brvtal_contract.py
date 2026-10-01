import json
import statistics
import unittest
from pathlib import Path

from performance.contract import validate_performance_contract
from performance.detector import detect_performance

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "performance" / "contracts" / "brvtal.json"
DOC_PATH = ROOT / "docs" / "performance-brvtal.md"
EVALUATED_AT = "2026-10-01T12:00:00Z"

SAMPLES = (
    {
        "sha": "c62baaabc994484d925d11f3625bb12772a8b5cb",
        "release": "0.1.101",
        "observed_at": "2026-09-30T22:32:54Z",
        "evidence_ref": "github:pl0n3r/brvtal/actions/runs/36786118661",
        "public.home.mobile": {"fcp": 380, "lcp": 1600, "cls": 0},
        "public.home.desktop": {"fcp": 456, "lcp": 1772, "cls": 0.005},
    },
    {
        "sha": "7ac39afa8ad205cc3c3668906a6d1ffa873ac1cf",
        "release": "0.1.101",
        "observed_at": "2026-10-01T11:09:01Z",
        "evidence_ref": "github:pl0n3r/brvtal/actions/runs/36853443439@attempt1",
        "public.home.mobile": {"fcp": 468, "lcp": 1768, "cls": 0},
        "public.home.desktop": {"fcp": 788, "lcp": 2352, "cls": 0.004},
    },
    {
        "sha": "7ac39afa8ad205cc3c3668906a6d1ffa873ac1cf",
        "release": "0.1.101",
        "observed_at": "2026-10-01T11:47:55Z",
        "evidence_ref": "github:pl0n3r/brvtal/actions/runs/36853443439@attempt2",
        "public.home.mobile": {"fcp": 380, "lcp": 1624, "cls": 0},
        "public.home.desktop": {"fcp": 440, "lcp": 1748, "cls": 0.005},
    },
)
UNITS = {"fcp": "ms", "lcp": "ms", "cls": "ratio"}
BUDGETS = {"fcp": 1800, "lcp": 2500, "cls": 0.1}


def load_contract():
    return json.loads(CONTRACT_PATH.read_text())


def observation(sample, surface, metric, value):
    return {
        "version": 1,
        "project": "brvtal",
        "surface": surface,
        "metric": metric,
        "value": value,
        "unit": UNITS.get(metric, "ms"),
        "observed_at": sample["observed_at"],
        "window_seconds": 1,
        "sample_count": 1,
        "severity": "info",
        "operational_impact": False,
        "bottleneck": "frontend",
        "evidence_ref": sample["evidence_ref"],
        "sha": sample["sha"],
        "release": sample["release"],
    }


class BrvtalPerformanceContractTests(unittest.TestCase):
    def test_contract_uses_reproducible_medians_and_explicit_budgets(self):
        contract = validate_performance_contract(load_contract())
        self.assertEqual(contract["project"], "brvtal")
        self.assertEqual(
            {surface["id"] for surface in contract["surfaces"]},
            {"public.home.mobile", "public.home.desktop"},
        )

        expected = {}
        for surface in ("public.home.mobile", "public.home.desktop"):
            expected[surface] = {
                metric: statistics.median(
                    sample[surface][metric] for sample in SAMPLES
                )
                for metric in ("fcp", "lcp", "cls")
            }

        for surface in contract["surfaces"]:
            self.assertEqual(
                {metric["id"] for metric in surface["metrics"]},
                {"fcp", "lcp", "cls"},
            )
            for metric in surface["metrics"]:
                metric_id = metric["id"]
                self.assertEqual(
                    metric["baseline"]["value"],
                    expected[surface["id"]][metric_id],
                )
                self.assertEqual(metric["budget"]["operator"], "lte")
                self.assertEqual(metric["budget"]["value"], BUDGETS[metric_id])
                self.assertEqual(metric["window"], {"duration_seconds": 1, "min_samples": 1})
                self.assertEqual(metric["freshness"], {"max_age_seconds": 604800})
                self.assertEqual(
                    set(metric["allowed_actions"]),
                    {"benchmark", "diagnose", "measure_before_after", "observe"},
                )
                self.assertEqual(
                    set(metric["escalation_conditions"]),
                    {"architecture_change", "capacity_budget"},
                )
                self.assertNotIn("create_work_item", metric["allowed_actions"])
                self.assertNotIn("cost_change", metric["escalation_conditions"])

    def test_policy_documents_evidence_and_lab_limitations(self):
        docs = DOC_PATH.read_text()
        for expected in (
            "36786118661",
            "36853443439",
            "attempt 1",
            "attempt 2",
            "Factory #304",
            "BRVTAL #819/#820",
            "mediana",
            "laboratorio",
            "p75",
            "CrUX",
            "https://web.dev/articles/fcp",
            "https://web.dev/articles/lcp",
            "https://web.dev/articles/cls",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, docs)

    def test_three_historical_samples_are_info_without_breach(self):
        contract = load_contract()
        results = []
        for sample in SAMPLES:
            for surface in ("public.home.mobile", "public.home.desktop"):
                for metric in ("fcp", "lcp", "cls"):
                    result = detect_performance(
                        contract,
                        observation(sample, surface, metric, sample[surface][metric]),
                        evaluated_at=EVALUATED_AT,
                    )
                    results.append(result)
                    self.assertEqual(result["classification"], "PERF_INFO")
                    self.assertEqual(result["evidence_state"], "CURRENT")
                    self.assertFalse(result["breach"])
        self.assertEqual(len(results), 18)

    def test_unbudgeted_timing_metrics_remain_unknown(self):
        contract = load_contract()
        sample = SAMPLES[-1]
        for surface in ("public.home.mobile", "public.home.desktop"):
            for metric in ("dom_content_loaded", "load_event_end"):
                with self.subTest(surface=surface, metric=metric):
                    result = detect_performance(
                        contract,
                        observation(sample, surface, metric, 900),
                        evaluated_at=EVALUATED_AT,
                    )
                    self.assertEqual(result["classification"], "PERF_REVIEW")
                    self.assertEqual(result["evidence_state"], "UNKNOWN")
                    self.assertEqual(result["reasons"], ["unknown_contract_identity"])
                    self.assertIsNone(result["breach"])
                    self.assertIsNone(result["budget"])


if __name__ == "__main__":
    unittest.main()
