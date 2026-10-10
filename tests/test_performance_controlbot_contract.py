"""Contrato ControlBot: solo línea base respaldada por GitHub Actions.

Orquestador y /health: UNKNOWN, sin medición pública válida. La ruta pública
no fue observable sin autenticación; los tiempos de CI nunca se interpretan
como tiempos de respuesta de producción.
"""
from datetime import datetime
import json
import statistics
import unittest
from pathlib import Path

from performance.contract import PerformanceContractError, validate_performance_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "performance" / "contracts" / "controlbot.json"

# Runs push/main de "CI ControlBot", conclusion success, intento 1.
# Metadatos públicos de GitHub, no mediciones de la web productiva.
CI_RUNS = (
    (37304562934, "3f6bf4532cb901598a4a9a0132d3824573cccf3a", "2026-10-05T11:41:35Z", "2026-10-05T11:43:54Z"),
    (37339588357, "d74a0b8c36992670fd9f2dc41f5592231fb968bd", "2026-10-05T16:16:43Z", "2026-10-05T16:18:12Z"),
    (37343055211, "bf22c83633b8b0bbfb047534a278d7ecff98087a", "2026-10-05T16:43:51Z", "2026-10-05T16:45:45Z"),
)

# Un estado UNKNOWN pertenece a la evidencia, no a baseline.value numérico.
UNMEASURED = {
    "admin.orchestrator": "UNKNOWN: interfaz no medible sin acceso autenticado",
    "public.health": "UNKNOWN: endpoint no medido con GET público verificable",
}


def load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def utc_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ControlBotPerformanceContractTests(unittest.TestCase):
    def test_contract_matches_v1_schema(self):
        raw = load_contract()
        validated = validate_performance_contract(raw)
        schema = json.loads((ROOT / "performance" / "contract.schema.json").read_text())
        self.assertEqual(schema["properties"]["version"]["const"], 1)
        self.assertEqual(validated["project"], "controlbot")
        self.assertEqual([s["id"] for s in validated["surfaces"]], ["ci.validation"])
        metric = validated["surfaces"][0]["metrics"][0]
        self.assertEqual(metric["id"], "workflow_elapsed")
        self.assertEqual(metric["baseline"]["unit"], "s")
        self.assertEqual(metric["budget"], {"operator": "lte", "value": 300, "unit": "s"})
        self.assertNotIn("create_work_item", metric["allowed_actions"])

    def test_baseline_is_grounded_in_github_workflow_evidence(self):
        values = [(utc_timestamp(ended) - utc_timestamp(started)).total_seconds()
                  for _, sha, started, ended in CI_RUNS]
        self.assertEqual(values, [139, 89, 114])
        self.assertTrue(all(len(sha) == 40 for _, sha, _, _ in CI_RUNS))
        self.assertEqual(len({run_id for run_id, _, _, _ in CI_RUNS}), 3)
        metric = load_contract()["surfaces"][0]["metrics"][0]
        self.assertEqual(metric["baseline"]["value"], statistics.median(values))
        self.assertEqual(metric["baseline"]["observed_at"], CI_RUNS[-1][3])
        self.assertEqual(metric["evidence"]["observed_at"], CI_RUNS[-1][3])
        self.assertEqual(metric["evidence"]["source"], "github_actions")
        self.assertEqual(metric["evidence"]["ref"],
                         f"github:pl0n3r/ControlBot/actions/runs/{CI_RUNS[-1][0]}")
        self.assertEqual(metric["window"]["min_samples"], len(CI_RUNS))
        self.assertEqual(metric["freshness"]["max_age_seconds"], 604800)

    def test_unmeasured_public_surfaces_remain_unknown_without_fabrication(self):
        self.assertEqual(set(UNMEASURED), {"admin.orchestrator", "public.health"})
        self.assertTrue(all(reason.startswith("UNKNOWN:") for reason in UNMEASURED.values()))
        contract = load_contract()
        surfaces = {surface["id"] for surface in contract["surfaces"]}
        self.assertTrue(set(UNMEASURED).isdisjoint(surfaces))
        self.assertEqual(surfaces, {"ci.validation"})
        contract["surfaces"][0]["metrics"][0]["baseline"]["value"] = None
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(contract)


if __name__ == "__main__":
    unittest.main()
