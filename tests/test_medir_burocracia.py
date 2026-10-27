"""AC-01..04 Factory #1577: medir puertas sin red ni datos reales."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "medir_burocracia.py"
SPEC = importlib.util.spec_from_file_location("medir_burocracia", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def timestamp(hour):
    return f"2026-10-20T{hour:02}:00:00Z"


def fixture():
    return {"version": 1,
            "issues": [
                {"issue_ref": "fixture:issue/alpha", "created_at": timestamp(0), "reserved_at": timestamp(1)},
                {"issue_ref": "fixture:issue/beta", "created_at": timestamp(0), "reserved_at": timestamp(2)},
            ],
            "pull_requests": [
                {"issue_ref": "fixture:issue/alpha", "pr_ref": "fixture:pr/one",
                 "opened_at": timestamp(3), "checks_passed_at": timestamp(7),
                 "policy_passed_at": timestamp(8), "reviewed_at": timestamp(9),
                 "merged_at": timestamp(10)},
                {"issue_ref": "fixture:issue/beta", "pr_ref": "fixture:pr/two",
                 "opened_at": timestamp(3), "checks_passed_at": timestamp(8),
                 "policy_passed_at": timestamp(9), "reviewed_at": timestamp(10),
                 "merged_at": timestamp(11)},
            ]}


class F1296MedirBurocraciaTests(unittest.TestCase):
    def test_contrato_principal(self):
        payload = fixture()
        result = module.evaluate(payload)
        self.assertEqual(result["status"], "MEASURED")
        self.assertEqual(result["case_count"], 2)
        self.assertEqual([x["step"] for x in result["ranking"]],
                         ["checks", "pr", "reserva", "merge", "politica", "revision"])
        self.assertEqual(result["ranking"][0]["total_seconds"], 9 * 3600)
        self.assertEqual(result["ranking"][0]["rank"], 1)
        self.assertEqual(result["ranking"][0]["mean_seconds"], 4 * 3600 + 1800)
        self.assertTrue(all(x["status"] == "MEASURED" for row in result["cases"]
                            for x in row["stages"]))
        self.assertEqual(result, module.evaluate(payload))
        self.assertEqual(payload, fixture(), "No se permite mutar los datos de entrada")
        self.assertFalse(result["execute_actions"])

    def test_falla_cerrado(self):
        base = fixture()
        negatives = [None, {}, [], {**base, "version": True}, {**base, "version": 2},
                     {**base, "issues": []}, {**base, "issues": base["issues"] * 51},
                     {**base, "pull_requests": [base["pull_requests"][0]] * 2},
                     {**base, "issues": [base["issues"][0]] * 2},
                     {**base, "pull_requests": [{**base["pull_requests"][0],
                                                "issue_ref": "fixture:issue/absent"}]},
                     {**base, "secret": "opaque"},
                     {**base, "issues": [{**base["issues"][0], "created_at": timestamp(12)},
                                           base["issues"][1]]},
                     {**base, "pull_requests": [{**base["pull_requests"][0],
                                                 "checks_passed_at": "2026-10-19T00:00:00Z"},
                                                base["pull_requests"][1]]},
                     {**base, "pull_requests": [{**base["pull_requests"][0],
                                                 "reviewed_at": 123}, base["pull_requests"][1]]},
                     {**base, "issues": [{**base["issues"][0], "created_at": None},
                                           base["issues"][1]]}]
        for invalid in negatives:
            with self.subTest(kind=str(invalid)[:55]), self.assertRaises(module.BurocracyMeasurementError):
                module.evaluate(invalid)
        run = subprocess.run([sys.executable, str(SOURCE), "--input", "-"],
                             input='{"version":1,"version":1}', text=True,
                             capture_output=True, check=False)
        self.assertEqual(run.returncode, 2)
        self.assertIn('"status": "UNKNOWN"', run.stderr)
        self.assertFalse(run.stdout)

    def test_sin_datos_reales(self):
        for field, value in (("issue_ref", "person@example.com"),
                             ("issue_ref", "fixture:issue/123456789"),
                             ("issue_ref", "fixture:issue/abc123456789")):
            data = fixture()
            data["issues"][0][field] = value
            with self.subTest(value=value), self.assertRaises(module.BurocracyMeasurementError):
                module.evaluate(data)
        data = fixture()
        data["pull_requests"][0]["owner_email"] = "person@example.com"
        with self.assertRaises(module.BurocracyMeasurementError):
            module.evaluate(data)
        proc = subprocess.run([sys.executable, str(SOURCE), "--input", "-"],
                              input=json.dumps(fixture()), capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        obj = json.loads(proc.stdout)
        self.assertEqual(obj["mode"], "synthetic_offline")
        self.assertFalse(obj["execute_actions"])
        self.assertTrue(obj["read_only"])
        self.assertNotIn("@", proc.stdout)
        self.assertNotIn("token", proc.stdout.lower())
        bad_input = subprocess.run([sys.executable, str(SOURCE), "--input", "../secret.json"],
                                   input="{}", capture_output=True, text=True, check=False)
        self.assertNotEqual(bad_input.returncode, 0)

    def test_estados_unknown_explicitos(self):
        data = fixture()
        del data["pull_requests"][0]["reviewed_at"]
        outcome = module.evaluate(data)
        self.assertEqual(outcome["status"], "UNKNOWN")
        stages = {x["step"]: x for x in outcome["cases"][0]["stages"]}
        self.assertIsNone(stages["revision"]["seconds"])
        self.assertIsNone(stages["merge"]["seconds"])
        for key in ("revision", "merge"):
            ranking = next(x for x in outcome["ranking"] if x["step"] == key)
            self.assertEqual(ranking["status"], "UNKNOWN")
            self.assertIsNone(ranking["total_seconds"])
            self.assertIsNone(ranking["rank"])
            self.assertEqual(ranking["unknown"], 1)
        data["pull_requests"] = []
        all_missing = module.evaluate(data)
        self.assertEqual(all_missing["status"], "UNKNOWN")
        self.assertEqual(all_missing["ranking"][0]["step"], "reserva")
        self.assertTrue(any(x["status"] == "UNKNOWN" for x in all_missing["ranking"]))
        # Incompletos nunca cuentan como tiempos medidos en el ranking.
        self.assertTrue(all(x["rank"] is None for x in all_missing["ranking"]
                            if x["status"] == "UNKNOWN"))

    def test_negative_cli_and_boundaries(self):
        fixtures = ["", "{", 'not JSON', '{"version":NaN}',
                    '{"version":1,"issues":[],"pull_requests":[]}',
                    "x" * (module.MAX_INPUT_BYTES + 1)]
        for raw in fixtures:
            with self.subTest(length=len(raw)):
                proc = subprocess.run([sys.executable, str(SOURCE), "--input", "-"],
                                      input=raw, capture_output=True, text=True, check=False)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertIn('"status": "UNKNOWN"', proc.stderr)
        data = fixture()
        data["pull_requests"][0]["merged_at"] = "2025-10-20T11:00:00Z"
        with self.assertRaises(module.BurocracyMeasurementError):
            module.evaluate(data)
        data = fixture()
        data["pull_requests"][0]["merged_at"] = "2028-10-20T11:00:00Z"
        with self.assertRaises(module.BurocracyMeasurementError):
            module.evaluate(data)
        data = fixture()
        data["pull_requests"][0]["merged_at"] = "2026-10-20T11:00:00+00:00"
        with self.assertRaises(module.BurocracyMeasurementError):
            module.evaluate(data)


if __name__ == "__main__":
    unittest.main()
