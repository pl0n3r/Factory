"""Regresiones reproducibles del reporte antes/después (sin GitHub ni red)."""
import json
import os
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import reporte_antes_despues as report

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return {
        "version": 1,
        "periods": {
            "antes": {"start": "2026-10-01T00:00:00Z", "end": "2026-10-08T00:00:00Z", "complete": True},
            "despues": {"start": "2026-10-08T00:00:00Z", "end": "2026-10-15T00:00:00Z", "complete": True},
        },
        "issues": [
            {"number": 1, "created_at": "2026-10-01T00:00:00Z", "closed_at": "2026-10-02T00:00:00Z"},
            {"number": 2, "created_at": "2026-10-09T00:00:00Z", "closed_at": "2026-10-09T12:00:00Z"},
            {"number": 3, "created_at": "2026-10-09T00:00:00Z", "closed_at": "2026-10-10T00:00:00Z"},
            {"number": 4, "created_at": "2026-10-14T00:00:00Z", "closed_at": None},
        ],
        "pull_requests": [
            {"number": 10, "created_at": "2026-10-01T00:00:00Z", "merged_at": "2026-10-04T00:00:00Z"},
            {"number": 11, "created_at": "2026-10-10T00:00:00Z", "merged_at": "2026-10-11T00:00:00Z"},
            {"number": 12, "created_at": "2026-10-10T00:00:00Z", "merged_at": "2026-10-12T00:00:00Z"},
        ],
    }


class ReporteAntesDespuesTests(unittest.TestCase):
    def test_criterio_principal(self):
        result = report.evaluate(fixture())
        self.assertEqual(result["antes"]["issues_cerrados"], 1)
        self.assertEqual(result["despues"]["issues_cerrados"], 2)
        self.assertEqual(result["diferencia_despues_menos_antes"]["prs_fusionados"], 1)
        self.assertEqual(result["antes"]["horas_promedio_por_issue"], 24)
        self.assertEqual(result["despues"]["horas_promedio_por_issue"], 18)
        self.assertEqual(result["costo"]["gasto_nuevo_cop"], 0)
        self.assertEqual(result["costo"]["costo_operativo_total_cop"], "UNKNOWN")
        self.assertEqual(result["antes"]["inicio_bogota_12h"], "2026-09-30 07:00 PM")
        self.assertEqual(result["zona_horaria"], "America/Bogota")

    def test_registros_vacios_sin_inventar_tiempos(self):
        value = fixture()
        value["issues"], value["pull_requests"] = [], []
        result = report.evaluate(value)
        self.assertEqual(result["antes"]["issues_cerrados"], 0)
        self.assertEqual(result["despues"]["prs_fusionados"], 0)
        self.assertEqual(result["antes"]["horas_promedio_por_issue"], "UNKNOWN")
        self.assertEqual(result["diferencia_despues_menos_antes"]["horas_promedio_por_issue"], "UNKNOWN")

    def test_periodo_incompleto_falla_cerrado(self):
        value = fixture()
        value["periods"]["despues"]["complete"] = False
        result = report.evaluate(value)
        self.assertEqual(result["despues"]["estado"], "UNKNOWN")
        self.assertEqual(result["despues"]["issues_cerrados"], "UNKNOWN")
        self.assertEqual(result["diferencia_despues_menos_antes"]["issues_cerrados"], "UNKNOWN")

    def test_sin_fecha_creacion_no_estima_duracion(self):
        value = fixture()
        value["issues"][1]["created_at"] = None
        result = report.evaluate(value)
        self.assertEqual(result["despues"]["issues_cerrados"], 2)
        self.assertEqual(result["despues"]["horas_promedio_por_issue"], "UNKNOWN")

    def test_rechaza_fechas_o_identidades_ambiguas(self):
        value = fixture()
        value["issues"].append(dict(value["issues"][0]))
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["periods"]["antes"]["end"] = "2026-10-09T00:00:00Z"
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["issues"][0]["closed_at"] = "not-a-date"
        with self.assertRaises(report.ReportError):
            report.evaluate(value)

    def test_fechas_de_borde_y_completitud_de_exportacion(self):
        value = fixture()
        value["issues"][0]["closed_at"] = "2026-10-08T00:00:00Z"
        result = report.evaluate(value)
        self.assertEqual(result["antes"]["issues_cerrados"], 0)
        self.assertEqual(result["despues"]["issues_cerrados"], 3)
        value = fixture()
        value["issues"][3]["state"] = "closed"
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["pull_requests"][0]["merged_at"] = None
        value["pull_requests"][0]["merged"] = True
        with self.assertRaises(report.ReportError):
            report.evaluate(value)

    def test_rechazar_registros_invalidos_y_cronologia(self):
        bad = [None, [], {"version": True}, {"version": 2}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(report.ReportError):
                report.evaluate(value)
        value = fixture()
        value["periods"]["antes"]["complete"] = "true"
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["periods"]["antes"]["start"] = value["periods"]["antes"]["end"]
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["issues"][0]["created_at"] = "2026-10-03T00:00:00Z"
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["pull_requests"][0]["number"] = False
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["issues"] = ["invalid"]
        with self.assertRaises(report.ReportError):
            report.evaluate(value)
        value = fixture()
        value["pull_requests"] = "invalid"
        with self.assertRaises(report.ReportError):
            report.evaluate(value)

    def test_cli_stdin_y_errores_no_revelan_entrada(self):
        command = [sys.executable, "scripts/reporte_antes_despues.py", "--input", "-"]
        good = subprocess.run(command, cwd=ROOT, input=json.dumps(fixture()),
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(good.returncode, 0, good.stderr)
        for input_text in ('{bad-json NEVER_PRINT', 'X' * (report.MAX_INPUT_BYTES + 1)):
            bad = subprocess.run(command, cwd=ROOT, input=input_text,
                                 capture_output=True, text=True, timeout=20)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout, '')
            self.assertNotIn('NEVER_PRINT', bad.stderr)
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / 'missing-private-value.txt'
            bad = subprocess.run(command[:-1] + [str(missing)], cwd=ROOT,
                                 capture_output=True, text=True, timeout=20)
            self.assertEqual(bad.returncode, 2)
            self.assertNotIn('missing-private-value', bad.stderr)

    def test_main_inprocess_con_cobertura_de_lectura_y_errores(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            out = io.StringIO()
            original = Path.cwd()
            try:
                os.chdir(folder)
                with redirect_stdout(out):
                    self.assertEqual(report.main(["--input", path.name]), 0)
                self.assertEqual(json.loads(out.getvalue())["antes"]["issues_cerrados"], 1)
                path.write_text('not-json-private-secret', encoding="utf-8")
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertEqual(report.main(["--input", path.name]), 2)
                self.assertNotIn('private-secret', err.getvalue())
                path.write_bytes(b'X' * (report.MAX_INPUT_BYTES + 1))
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(report.main(["--input", path.name]), 2)
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(report.main(["--input", "../private.json"]), 2)
                path.unlink()
                target = Path(folder) / "real.json"
                target.write_text(json.dumps(fixture()), encoding="utf-8")
                path.symlink_to(target)
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(report.main(["--input", path.name]), 2)
            finally:
                os.chdir(original)

    def test_cli_sin_red_y_salida_solo_metricas(self):
        value = fixture()
        value["issues"][0]["secret_note"] = "NEVER_EMIT_PII"
        run = subprocess.run([sys.executable, "scripts/reporte_antes_despues.py", "--input", "-"],
                             input=json.dumps(value), cwd=ROOT, capture_output=True,
                             text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("NEVER_EMIT_PII", run.stdout)
        self.assertEqual(json.loads(run.stdout)["despues"]["prs_fusionados"], 2)


if __name__ == "__main__":
    unittest.main()
