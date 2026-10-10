"""Regresión reproducible del contrato de rendimiento GrindFlow con evidencia real."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from performance.contract import PerformanceContractError, validate_performance_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "performance" / "contracts" / "grindflow.json"
DOC = ROOT / "docs" / "performance-grindflow.md"
RUN_ID = "38010129128"
JOB_ID = "114087986892"
STARTED_AT = "2026-10-10T00:41:39Z"
COMPLETED_AT = "2026-10-10T00:42:17Z"
MAIN_SHA = "3c137b21654d30bc5ce123853e58934d973ce4b5"


class GrindflowPerformanceContractTests(unittest.TestCase):
    def load(self):
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def metric(self):
        raw = self.load()
        self.assertEqual(len(raw["surfaces"]), 1)
        self.assertEqual(len(raw["surfaces"][0]["metrics"]), 1)
        return raw["surfaces"][0]["metrics"][0]

    def test_contract_schema_accepts_exact_measured_ci_metric(self):
        value = validate_performance_contract(self.load())
        self.assertEqual(value["project"], "grindflow")
        self.assertEqual({s["id"] for s in value["surfaces"]}, {"ci.production_smoke"})
        metric = value["surfaces"][0]["metrics"][0]
        self.assertEqual(metric["id"], "job_duration")
        self.assertEqual(metric["baseline"], {
            "value": 38, "unit": "s", "observed_at": COMPLETED_AT,
        })
        self.assertEqual(metric["budget"], {"operator": "lte", "value": 120, "unit": "s"})
        self.assertEqual(metric["allowed_actions"], sorted([
            "observe", "diagnose", "benchmark", "measure_before_after",
        ]))
        self.assertNotIn("create_work_item", metric["allowed_actions"])

    def test_baselines_are_real_or_explicitly_unknown(self):
        metric = self.metric()
        evidence = metric["evidence"]
        self.assertEqual(evidence["observed_at"], COMPLETED_AT)
        self.assertEqual(evidence["source"], "github_actions")
        self.assertEqual(
            evidence["ref"],
            f"github:pl0n3r/GrindFlow/actions/runs/{RUN_ID}#job-{JOB_ID}",
        )
        from datetime import datetime
        seconds = int(
            (datetime.fromisoformat(COMPLETED_AT.replace("Z", "+00:00"))
             - datetime.fromisoformat(STARTED_AT.replace("Z", "+00:00")))
            .total_seconds()
        )
        self.assertEqual(metric["baseline"]["value"], seconds)
        doc = DOC.read_text(encoding="utf-8")
        for phrase in (RUN_ID, JOB_ID, STARTED_AT, COMPLETED_AT, MAIN_SHA,
                       "Landing pública", "Login", "Composer", "Library", "UNKNOWN",
                       "no TTFB", "sin evidencia"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, doc)
        self.assertEqual(doc.count("| UNKNOWN |"), 4)

    def test_budget_guard_rejects_fake_or_unsupported_measurements(self):
        original = self.load()
        metric = self.metric()
        self.assertNotIn("ttfb", json.dumps(original).lower())
        self.assertNotIn("public.home", json.dumps(original).lower())
        self.assertEqual(metric["window"], {"duration_seconds": 1, "min_samples": 1})
        self.assertEqual(metric["freshness"], {"max_age_seconds": 604800})
        # El schema no permite UNKNOWN numérico: nunca reemplazarlo por 0.
        invalid = copy.deepcopy(original)
        invalid["surfaces"][0]["metrics"][0]["baseline"]["value"] = "UNKNOWN"
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(invalid)
        invalid = copy.deepcopy(original)
        invalid["surfaces"][0]["metrics"][0]["evidence"]["reason"] = "unknown"
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(invalid)


if __name__ == "__main__":
    unittest.main()
