"""Contrato #1578, F304: latencia por workflow con fixtures sintéticos."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "medir_rendimiento_ci.py"
SPEC = importlib.util.spec_from_file_location("medir_rendimiento_ci", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class F304MedirCiTests(unittest.TestCase):
    @staticmethod
    def fixture():
        return {"version": 1, "workflows": [
            {"workflow": "validate", "durations_ms": [200, 100, 400, 300, 500],
             "baseline": {"p50_ms": 250, "p95_ms": 400, "threshold_pct": 10}},
            {"workflow": "lint", "durations_ms": [30, 10, 20],
             "baseline": {"p50_ms": 20, "p95_ms": 30, "threshold_pct": 0}},
        ]}

    def test_contrato_principal(self):
        data = self.fixture()
        result = module.evaluate(data)
        self.assertEqual([r["workflow"] for r in result["workflows"]], ["lint", "validate"])
        lint, validate = result["workflows"]
        self.assertEqual((lint["p50_ms"], lint["p95_ms"], lint["status"]),
                         (20, 30, "WITHIN_BASELINE"))
        self.assertEqual((validate["p50_ms"], validate["p95_ms"], validate["status"]),
                         (300, 500, "REGRESSION"))
        self.assertTrue(validate["regression_p50"])
        self.assertTrue(validate["regression_p95"])
        self.assertEqual(result["authority"], "none")
        self.assertFalse(result["execute_actions"])
        self.assertEqual(result, module.evaluate(data))
        self.assertEqual(data, self.fixture(), "La entrada original nunca cambia")
        self.assertEqual(module._percentile_nearest_rank([11], 95), 11)
        self.assertEqual(module._percentile_nearest_rank([10, 20], 50), 10)

    def test_falla_cerrado(self):
        valid = self.fixture()
        invalid = [
            None, {}, {"version": True, "workflows": valid["workflows"]},
            {"version": 2, "workflows": valid["workflows"]},
            {"version": 1, "workflows": []},
            {"version": 1, "workflows": [{"workflow": "validate", "durations_ms": [0]}]},
            {"version": 1, "workflows": [{"workflow": "validate", "durations_ms": [-1]}]},
            {"version": 1, "workflows": [{"workflow": "validate", "durations_ms": [True]}]},
            {"version": 1, "workflows": [{"workflow": "validate", "durations_ms": [float('nan')]}]},
            {"version": 1, "workflows": [valid["workflows"][0], valid["workflows"][0]]},
            {"version": 1, "workflows": [dict(valid["workflows"][0], secret="opaque")]},
            {"version": 1, "workflows": [{"workflow": "valid", "durations_ms": [10],
                                           "baseline": {"p50_ms": 10, "p95_ms": 4, "threshold_pct": 10}}]},
            {"version": 1, "workflows": [{"workflow": "valid", "durations_ms": [10],
                                           "baseline": {"p50_ms": 10, "p95_ms": 10, "threshold_pct": -1}}]},
        ]
        for bad in invalid:
            with self.subTest(case=str(bad)[:90]):
                with self.assertRaises(module.CiMeasurementError):
                    module.evaluate(bad)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text('{"version":1,"version":1,"workflows":[]}', encoding="utf-8")
            run = subprocess.run([sys.executable, str(SOURCE), "--input", str(p)],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 2)
            self.assertIn('"status": "UNKNOWN"', run.stderr)
            self.assertEqual(run.stdout, "")

    def test_sin_datos_reales(self):
        data = self.fixture()
        data["workflows"][0]["repository"] = "someone/private"
        with self.assertRaises(module.CiMeasurementError):
            module.evaluate(data)
        data = self.fixture()
        data["workflows"][0]["workflow"] = "contact@example.org"
        with self.assertRaises(module.CiMeasurementError):
            module.evaluate(data)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "synthetic.json"
            path.write_text(json.dumps(self.fixture()), encoding="utf-8")
            run = subprocess.run([sys.executable, str(SOURCE), "--input", str(path)],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            out = json.loads(run.stdout)
            self.assertEqual(out["mode"], "synthetic_offline")
            self.assertFalse(out["execute_actions"])
            self.assertNotIn("secret", run.stdout.lower())
            self.assertNotIn("repository", run.stdout.lower())
            self.assertFalse(out["baseline_mutated"])

    def test_estados_unknown_explicitos(self):
        data = {"version": 1, "workflows": [
            {"workflow": "no-baseline", "durations_ms": [10, 20, 30]},
            {"workflow": "empty-fixture", "durations_ms": [],
             "baseline": {"p50_ms": 10, "p95_ms": 20, "threshold_pct": 5}},
        ]}
        out = module.evaluate(data)["workflows"]
        self.assertEqual([x["status"] for x in out], ["UNKNOWN", "UNKNOWN"])
        self.assertEqual([x["reason"] for x in out], ["no_samples", "no_baseline"])
        for item in out:
            self.assertIsNone(item["regression_p50"])
            self.assertIsNone(item["regression_p95"])
        self.assertEqual(out[0]["samples"], 0)
        self.assertIsNone(out[0]["p95_ms"])
