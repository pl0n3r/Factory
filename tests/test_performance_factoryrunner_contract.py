"""Contrato de rendimiento factoryrunner: workflow CI real, no runtime."""
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
RUN_WORKFLOW = "github:pl0n3r/FactoryRunner/actions/runs/38027128700/attempts/1"
COMMIT_SHA = "7cc16d7034862444721173886e2edef9357c5e46"
WORKFLOW_STARTED = "2026-10-10T05:19:39Z"
WORKFLOW_UPDATED = "2026-10-10T05:21:43Z"
WORKFLOW_ELAPSED_SECONDS = 124


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class FactoryRunnerPerformanceContractTests(unittest.TestCase):
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


    def test_workflow_baselines_proven_and_unmeasured_omitted(self):
        self.test_workflow_elapsed_contract_is_valid()
        metric = load_contract()["surfaces"][0]["metrics"][0]
        self.assertEqual(metric["baseline"]["value"], 124)
        self.assertEqual(metric["window"]["duration_seconds"], 1)
        self.assertEqual(metric["evidence"]["ref"], RUN_WORKFLOW)
        # La línea base real supera el budget prospectivo de 120 s.
        self.assertGreater(metric["baseline"]["value"], metric["budget"]["value"])
        self.test_unmeasured_runtime_metrics_remain_unknown()


    @staticmethod
    def _ci_observation(value, **overrides):
        """Fixture CI sintética: no atribuir sus duraciones al run histórico."""
        observation = {
            "version": 1, "project": PROJECT,
            "surface": "ci.workflow", "metric": "workflow_elapsed",
            "value": value, "unit": "s",
            "observed_at": WORKFLOW_UPDATED,
            "window_seconds": value, "sample_count": 1,
            "severity": "medium", "operational_impact": False,
            "bottleneck": "infrastructure",
            "evidence_ref": "fixture:factoryrunner-ci-workflow",
            "sha": "f" * 40, "release": None,
        }
        observation.update(overrides)
        return observation

    def test_fast_workflow_can_be_current_without_insufficient_window(self):
        result = detect_performance(
            load_contract(), self._ci_observation(100),
            evaluated_at=WORKFLOW_UPDATED,
        )
        self.assertEqual(result["evidence_state"], "CURRENT")
        self.assertEqual(result["classification"], "PERF_INFO")
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["breach"])
        self.assertEqual(result["budget"]["value"], 120)
        self.assertFalse(result["operational_impact"])

    def test_slow_workflow_still_reports_material_budget_breach(self):
        result = detect_performance(
            load_contract(), self._ci_observation(172),
            evaluated_at=WORKFLOW_UPDATED,
        )
        self.assertEqual(result["evidence_state"], "CURRENT")
        self.assertEqual(result["classification"], "PERF_DEGRADATION")
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["breach"])
        self.assertEqual(result["observed"]["value"], 172)
        self.assertEqual(result["baseline"]["value"], 124)
        self.assertEqual(result["delta"], 48)
        self.assertEqual(result["allowed_actions"], ["benchmark", "diagnose", "observe"])

    def test_stale_or_uncontracted_ci_remains_unknown_or_review(self):
        stale = detect_performance(
            load_contract(), self._ci_observation(100),
            evaluated_at="2026-10-18T05:21:44Z",
        )
        self.assertEqual(stale["classification"], "PERF_REVIEW")
        self.assertEqual(stale["evidence_state"], "STALE")
        self.assertIn("stale", stale["reasons"])
        unknown = detect_performance(
            load_contract(), self._ci_observation(
                100, surface="execution.runtime", metric="memory",
            ),
            evaluated_at=WORKFLOW_UPDATED,
        )
        self.assertEqual(unknown["classification"], "PERF_REVIEW")
        self.assertEqual(unknown["evidence_state"], "UNKNOWN")
        self.assertIsNone(unknown["breach"])
        self.assertEqual(unknown["allowed_actions"], [])


if __name__ == "__main__":
    unittest.main()
