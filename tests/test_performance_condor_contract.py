"""Contratos de rendimiento Condor: baselines GitHub verificables, no cifras live inventadas."""
from __future__ import annotations

import json
import statistics
import unittest
from datetime import datetime, timezone
from pathlib import Path

from performance.contract import validate_performance_contract
from performance.detector import detect_performance

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "performance" / "contracts" / "condor.json"
SCHEMA = ROOT / "performance" / "contract.schema.json"

# GitHub Actions REST, event=push, conclusión SUCCESS. La duración se obtiene
# de run_started_at -> updated_at, incluye colas y cleanup; NO mide web/TTFB.
CI_SAMPLES = (
    ("37440339332", "2026-10-06T09:03:37Z", "2026-10-06T09:05:39Z", 122),
    ("37441854318", "2026-10-06T09:16:48Z", "2026-10-06T09:18:38Z", 110),
    ("37443207734", "2026-10-06T09:28:35Z", "2026-10-06T09:30:45Z", 130),
)
LATEST_SHA = "615ede5ffc037c2deb366c871e5ae2535a58e9be"
# No existe evidencia pública HTTP en este entorno: GET condorapp.com.co
# devolvió error de DNS (2026-10-10). El schema v1 exige baseline numérico:
# registrar en la lista, no introducir un 0 o inferir una latencia de CI.
UNMEASURED_PUBLIC = {
    "public.home": "DNS/no authenticated HTTP measurement",
    "public.health": "no real health response with exact-main SHA",
    "public.login": "no unauthenticated timing measurement",
    "public.dashboard": "requires authenticated timing; not authorized",
}


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class CondorPerformanceContractTests(unittest.TestCase):
    def test_condor_contract_matches_v1_schema(self):
        raw = load_contract()
        validated = validate_performance_contract(raw)
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(validated["version"], schema["properties"]["version"]["const"])
        self.assertEqual(validated["project"], "condor")
        self.assertEqual(raw, validated)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual([s["id"] for s in validated["surfaces"]], ["ci.validation"])
        metric = validated["surfaces"][0]["metrics"][0]
        self.assertEqual(metric["id"], "workflow_wall_seconds")
        self.assertEqual(metric["baseline"]["unit"], "s")
        self.assertEqual(metric["budget"], {"operator": "lte", "unit": "s", "value": 300})
        self.assertEqual(metric["window"], {"duration_seconds": 1500, "min_samples": 3})
        self.assertEqual(set(metric["allowed_actions"]),
                         {"observe", "diagnose", "benchmark", "measure_before_after"})

    def test_no_public_baseline_is_invented(self):
        contract = load_contract()
        self.assertEqual(len(UNMEASURED_PUBLIC), 4)
        self.assertTrue(all(reason for reason in UNMEASURED_PUBLIC.values()))
        surface_names = {s["id"] for s in contract["surfaces"]}
        self.assertFalse(surface_names.intersection(UNMEASURED_PUBLIC))
        self.assertEqual(surface_names, {"ci.validation"})
        self.assertFalse(any(metric["id"] in ("ttfb", "lcp", "health_latency", "memory_mb")
                             for s in contract["surfaces"] for metric in s["metrics"]))
        for surface in contract["surfaces"]:
            for metric in surface["metrics"]:
                self.assertGreater(metric["baseline"]["value"], 0)
                self.assertNotIn("public", metric["evidence"]["source"])

    def test_ci_evidence_and_detector_contract(self):
        contract = load_contract()
        metric = contract["surfaces"][0]["metrics"][0]
        durations = []
        for run_id, started, updated, seconds in CI_SAMPLES:
            self.assertTrue(run_id.isdigit())
            self.assertEqual((parse_utc(updated) - parse_utc(started)).total_seconds(), seconds)
            durations.append(seconds)
        self.assertEqual(statistics.median(durations), metric["baseline"]["value"])
        self.assertEqual(metric["evidence"]["ref"],
                         "github:pl0n3r/Condor/actions/runs/" + CI_SAMPLES[-1][0])
        self.assertEqual(metric["baseline"]["observed_at"], CI_SAMPLES[-1][2])
        self.assertEqual(metric["evidence"]["observed_at"], CI_SAMPLES[-1][2])
        window_seconds = int((parse_utc(CI_SAMPLES[-1][2]) - parse_utc(CI_SAMPLES[0][2])).total_seconds())
        self.assertGreaterEqual(window_seconds, metric["window"]["duration_seconds"])
        observation = {
            "version": 1, "project": "condor", "surface": "ci.validation",
            "metric": "workflow_wall_seconds", "value": 130, "unit": "s",
            "observed_at": CI_SAMPLES[-1][2], "window_seconds": window_seconds,
            "sample_count": len(CI_SAMPLES), "severity": "info",
            "operational_impact": False, "bottleneck": "infrastructure",
            "evidence_ref": metric["evidence"]["ref"],
            "sha": LATEST_SHA, "release": None,
        }
        result = detect_performance(contract, observation, evaluated_at="2026-10-10T09:30:45Z")
        self.assertEqual(result["classification"], "PERF_INFO")
        self.assertEqual(result["evidence_state"], "CURRENT")
        self.assertFalse(result["breach"])

        # El detector nunca trata un KPI web no medido como conforme.
        missing = dict(observation, surface="public.health", metric="ttfb", unit="ms", value=100)
        unknown = detect_performance(contract, missing, evaluated_at="2026-10-10T09:30:45Z")
        self.assertEqual(unknown["classification"], "PERF_REVIEW")
        self.assertEqual(unknown["evidence_state"], "UNKNOWN")
        self.assertIsNone(unknown["baseline"])
        self.assertIsNone(unknown["breach"])


if __name__ == "__main__":
    unittest.main()
