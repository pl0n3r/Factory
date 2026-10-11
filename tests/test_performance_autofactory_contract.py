"""Contrato de rendimiento autofactory: workflow CI real, no runtime."""
import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from performance.contract import PerformanceContractError, validate_performance_contract
from performance.detector import detect_performance

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "performance" / "contracts" / "autofactory.json"
PROJECT = "autofactory"
RUN_WORKFLOW = "github:pl0n3r/AutoFactory/actions/runs/38041222908/attempts/1"
COMMIT_SHA = "8d1f0dcd051435ad4cb58644ec6eae0956a46ba5"
WORKFLOW_STARTED = "2026-10-10T09:23:35Z"
WORKFLOW_UPDATED = "2026-10-10T09:24:05Z"
WORKFLOW_ELAPSED_SECONDS = 30


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class AutoFactoryPerformanceContractTests(unittest.TestCase):
    def test_workflow_elapsed_contract_is_valid(self):
        raw = load_contract()
        contract = validate_performance_contract(raw)
        schema = json.loads(
            (ROOT / "performance" / "contract.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(contract["project"], PROJECT)
        self.assertEqual(contract["version"], 1)
        self.assertEqual(len(contract["surfaces"]), 1)
        surface = contract["surfaces"][0]
        self.assertEqual(surface["id"], "ci.workflow")
        self.assertEqual(len(surface["metrics"]), 1)
        metric = surface["metrics"][0]
        self.assertEqual(metric["id"], "workflow_elapsed")

        # Intento 1 del workflow CI exitoso, fijado por run_id y SHA.
        # Se mide run_started_at -> updated_at; incluye overhead de Actions,
        # NO mide tiempo de ejecución del producto ni memoria.
        first = datetime.fromisoformat(WORKFLOW_STARTED.replace("Z", "+00:00"))
        last = datetime.fromisoformat(WORKFLOW_UPDATED.replace("Z", "+00:00"))
        span = round((last - first).total_seconds(), 3)
        self.assertEqual(span, WORKFLOW_ELAPSED_SECONDS)
        self.assertEqual(metric["baseline"]["value"], span)
        self.assertEqual(metric["baseline"]["unit"], "s")
        self.assertEqual(metric["baseline"]["observed_at"], WORKFLOW_UPDATED[:19] + "Z")
        self.assertEqual(metric["evidence"], {
            "source": "github_actions",
            "ref": RUN_WORKFLOW,
            "observed_at": WORKFLOW_UPDATED[:19] + "Z",
        })

        # Budget es objetivo propuesto de vigilancia; no baseline observado.
        self.assertEqual(metric["budget"], {"operator": "lte", "value": 120, "unit": "s"})
        self.assertNotIn("create_work_item", metric["allowed_actions"])
        self.assertEqual(metric["window"], {"duration_seconds": 30, "min_samples": 1})

        extra = copy.deepcopy(raw)
        extra["surfaces"][0]["metrics"][0]["actual_product_memory"] = 0
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(extra)

    def test_unmeasured_extension_metrics_remain_unknown(self):
        contract = load_contract()
        # UNKNOWN: no se dispone de series instrumentadas exact-SHA para
        # estas métricas operativas; prohibido convertir CI en evidencia de
        # rendimiento real o inferir readiness.
        for metric_id in ["pacing","memory","heartbeat.latency","release.size"]:
            with self.subTest(metric=metric_id):
                observation = {
                    "version": 1, "project": PROJECT,
                    "surface": "extension.runtime", "metric": metric_id,
                    "value": 1, "unit": "s",
                    "observed_at": WORKFLOW_UPDATED[:19] + "Z",
                    "window_seconds": 1, "sample_count": 1,
                    "severity": "info", "operational_impact": False,
                    "bottleneck": "unknown", "evidence_ref": RUN_WORKFLOW,
                    "sha": COMMIT_SHA, "release": None,
                }
                result = detect_performance(
                    contract, observation, evaluated_at=WORKFLOW_UPDATED[:19] + "Z"
                )
                self.assertEqual(result["classification"], "PERF_REVIEW")
                self.assertEqual(result["evidence_state"], "UNKNOWN")
                self.assertEqual(result["reasons"], ["unknown_contract_identity"])
                self.assertIsNone(result["baseline"])
                self.assertIsNone(result["budget"])
                self.assertIsNone(result["breach"])


    def test_both_contracts_validate_against_canonical_schema(self):
        for project in ("autofactory", "factoryrunner"):
            with self.subTest(project=project):
                path = ROOT / "performance" / "contracts" / f"{project}.json"
                raw = json.loads(path.read_text(encoding="utf-8"))
                validated = validate_performance_contract(raw)
                self.assertEqual(validated["project"], project)
                self.assertEqual(len(validated["surfaces"]), 1)
                self.assertEqual(validated["surfaces"][0]["id"], "ci.workflow")
                metric = validated["surfaces"][0]["metrics"][0]
                self.assertEqual(metric["id"], "workflow_elapsed")
                self.assertEqual(metric["baseline"]["unit"], "s")
                self.assertEqual(metric["evidence"]["source"], "github_actions")
                self.assertTrue(metric["evidence"]["ref"].endswith("/attempts/1"))
                self.assertNotIn("create_work_item", metric["allowed_actions"])

    def test_ci_regressions_cover_both_contracts(self):
        expected = {"autofactory": 30, "factoryrunner": 124}
        for project, elapsed in expected.items():
            with self.subTest(project=project):
                path = ROOT / "performance" / "contracts" / f"{project}.json"
                raw = json.loads(path.read_text(encoding="utf-8"))
                metric = raw["surfaces"][0]["metrics"][0]
                self.assertEqual(metric["baseline"]["value"], elapsed)
                self.assertEqual(metric["window"]["duration_seconds"], elapsed)
                self.assertEqual(metric["evidence"]["observed_at"],
                                 metric["baseline"]["observed_at"])
                self.assertEqual(metric["budget"]["value"], 120)
                broken = copy.deepcopy(raw)
                broken["surfaces"][0]["metrics"][0]["baseline"]["value"] = None
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(broken)
        self.test_unmeasured_extension_metrics_remain_unknown()


if __name__ == "__main__":
    unittest.main()
