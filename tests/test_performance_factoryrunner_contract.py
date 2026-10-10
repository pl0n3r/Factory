"""Contrato de rendimiento factoryrunner: evidencias reales de log CI, no runtime."""
import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from performance.contract import PerformanceContractError, validate_performance_contract
from performance.detector import detect_performance

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "performance" / "contracts" / "factoryrunner.json"
PROJECT = "factoryrunner"
RUN_JOB = "github:pl0n3r/FactoryRunner/actions/runs/38027128700/job/114140263203"
COMMIT_SHA = "7cc16d7034862444721173886e2edef9357c5e46"
LOG_FIRST = "2026-10-10T05:19:52.9705472Z"
LOG_LAST = "2026-10-10T05:19:59.7393804Z"
LOG_SPAN_SECONDS = 6.769


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class FactoryRunnerPerformanceContractTests(unittest.TestCase):
    def test_exact_ci_log_span_contract_is_valid(self):
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
        self.assertEqual(surface["id"], "ci.node.job_log")
        self.assertEqual(len(surface["metrics"]), 1)
        metric = surface["metrics"][0]
        self.assertEqual(metric["id"], "log_span")

        # Proveniencia de un único job SUCCESS exact-SHA. Los extremos son
        # timestamps del log; NO equivalen a duración total del workflow,
        # memoria ni rendimiento de ejecución del producto.
        first = datetime.fromisoformat(LOG_FIRST.replace("Z", "+00:00"))
        last = datetime.fromisoformat(LOG_LAST.replace("Z", "+00:00"))
        span = round((last - first).total_seconds(), 3)
        self.assertEqual(span, LOG_SPAN_SECONDS)
        self.assertEqual(metric["baseline"]["value"], span)
        self.assertEqual(metric["baseline"]["unit"], "s")
        self.assertEqual(metric["baseline"]["observed_at"], LOG_LAST[:19] + "Z")
        self.assertEqual(metric["evidence"], {
            "source": "github_actions_job",
            "ref": RUN_JOB,
            "observed_at": LOG_LAST[:19] + "Z",
        })

        # Budget es objetivo propuesto de vigilancia; no baseline observado.
        self.assertEqual(metric["budget"], {"operator": "lte", "value": 120, "unit": "s"})
        self.assertNotIn("create_work_item", metric["allowed_actions"])
        self.assertEqual(metric["window"], {"duration_seconds": 1, "min_samples": 1})

        extra = copy.deepcopy(raw)
        extra["surfaces"][0]["metrics"][0]["actual_product_memory"] = 0
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(extra)

    def test_unmeasured_runtime_metrics_remain_unknown(self):
        contract = load_contract()
        # UNKNOWN: no se dispone de series instrumentadas exact-SHA para
        # estas métricas operativas; prohibido convertir CI en evidencia de
        # rendimiento real o inferir readiness.
        for metric_id in ["job.duration","throughput","memory"]:
            with self.subTest(metric=metric_id):
                observation = {
                    "version": 1, "project": PROJECT,
                    "surface": "execution.runtime", "metric": metric_id,
                    "value": 1, "unit": "s",
                    "observed_at": LOG_LAST[:19] + "Z",
                    "window_seconds": 1, "sample_count": 1,
                    "severity": "info", "operational_impact": False,
                    "bottleneck": "unknown", "evidence_ref": RUN_JOB,
                    "sha": COMMIT_SHA, "release": None,
                }
                result = detect_performance(
                    contract, observation, evaluated_at=LOG_LAST[:19] + "Z"
                )
                self.assertEqual(result["classification"], "PERF_REVIEW")
                self.assertEqual(result["evidence_state"], "UNKNOWN")
                self.assertEqual(result["reasons"], ["unknown_contract_identity"])
                self.assertIsNone(result["baseline"])
                self.assertIsNone(result["budget"])
                self.assertIsNone(result["breach"])


if __name__ == "__main__":
    unittest.main()
