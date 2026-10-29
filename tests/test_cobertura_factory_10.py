#!/usr/bin/env python3
"""Factory #1801: regresiones offline de privacidad y vistas derivadas.

Solo se ejercita código real con datos sintéticos. No consulta la matriz,
no certifica cumplimiento jurídico y no presupone ejecución productiva.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from intelligence.derived_views import (
    DerivedViewDriftError, DerivedViewError, DerivedViewSpec,
    check_drift, render_markdown_table, replace_delimited_block,
)
from seguridad.cumplimiento import (
    ComplianceError, REQUIRED_EVIDENCE, inspect_composer, inspect_npm,
    main as compliance_main, validate_inventory, validate_privacy,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
PRIV = "docs/cumplimiento-datos-licencias.md:"
VIEWS = "docs/derived-views.md:"
OFFLINE = frozenset({
    PRIV + "L21-U2", PRIV + "L36-U1", PRIV + "L7-U1",
    VIEWS + "L10-U1", VIEWS + "L11-U1", VIEWS + "L12-U1",
    VIEWS + "L13-U1", VIEWS + "L14-U1", VIEWS + "L18-U1",
    VIEWS + "L18-U2", VIEWS + "L24-U1", VIEWS + "L28-U1",
    VIEWS + "L3-U1",
})
# Clasificaciones fuera de la prueba: exigen mundo real o expresan política.
WORLD = {
    PRIV + "L37-U1": "Ejecución de seguridad.yml en GitHub Actions",
    PRIV + "L37-U2": "Ejecución real de Validar puertas del candidato",
    PRIV + "L38-U1": "Evidencias verificadas de tratamientos y lockfiles reales",
    PRIV + "L39-U1": "Revisión material y CI del cierre de #12",
}
POLICY = {
    PRIV + "L38-U2": "Fixture no certifica cumplimiento de un producto",
    VIEWS + "L24-U2": "No alterar la fuente para satisfacer un check",
    VIEWS + "L28-U2": "El uso prudente de regression es política documental",
}


def synthetic_record() -> dict:
    return {
        "version": 1, "project": "pl0n3r/GrindFlow",
        "scope": "operations", "purpose": "testing",
        "data_categories": ["none"], "consent_or_exception": "no_personal_data",
        "evidence": {key: "fixture:" + key for key in REQUIRED_EVIDENCE},
        "reviewed_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def run_cli(record: dict, args: list[str] | None = None) -> tuple[int, str]:
    output = StringIO()
    with patch.object(sys, "argv", ["cumplimiento.py", *(args or ["--stdlib-only"])]), \
         patch.object(sys, "stdin", StringIO(json.dumps(record))), \
         redirect_stdout(output):
        return compliance_main(), output.getvalue()


class CoberturaFactory10Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: ejecutar código real por cada uno de los 13 claims offline."""
        self.assertEqual((len(OFFLINE), len(WORLD), len(POLICY)), (13, 4, 3))
        self.assertEqual(len(OFFLINE | WORLD.keys() | POLICY.keys()), 20)
        exercised: set[str] = set()

        # L7: la función valida referencias y los dos lockfile schemas.
        record = synthetic_record()
        self.assertEqual(validate_privacy(record, now=NOW), "pl0n3r/GrindFlow")
        composer = inspect_composer({
            "packages": [{"name": "vendor/one", "version": "1.0.0",
                          "license": ["MIT"]}],
            "packages-dev": [{"name": "vendor/dev", "version": "2.0.0",
                              "license": ["Apache-2.0"]}],
        })
        npm = inspect_npm({"packages": {
            "": {}, "node_modules/dependency": {
                "version": "3.0.0", "license": "BSD-3-Clause",
            },
        }})
        self.assertEqual(validate_inventory(composer + npm), {
            "packages_observed": 3,
            "license_status": "identifiers_present_review_required",
        })
        exercised.add(PRIV + "L7-U1")

        # L21: el CLI lee manifiesto por stdin y no revela sus referencias.
        with patch("seguridad.cumplimiento.datetime") as fake_dt:
            fake_dt.now.return_value = NOW
            fake_dt.strptime.side_effect = datetime.strptime
            code, output = run_cli(record)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["evidence_status"],
                         "documented_not_legally_approved")
        self.assertNotIn("fixture:", output)
        exercised.add(PRIV + "L21-U2")

        # L36: ejecutar la suite real, no buscar una cadena en documentación.
        suite = unittest.TestLoader().discover(
            str(ROOT / "seguridad"), pattern="test_cumplimiento.py")
        result = unittest.TestResult()
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            suite.run(result)
        self.assertTrue(result.wasSuccessful(),
                        f"fallos: {result.failures}; errores: {result.errors}")
        self.assertGreater(result.testsRun, 0)
        exercised.add(PRIV + "L36-U1")

        # L10-14: validar las vistas registradas usando la clase de dominio.
        registry = json.loads((ROOT / "config" / "derived_views.json").read_text(
            encoding="utf-8"))
        self.assertEqual(registry["version"], 1)
        specs = [DerivedViewSpec(**view) for view in registry["views"]]
        self.assertTrue(specs)
        for spec in specs:
            spec.validate()
        self.assertTrue(all(s.source for s in specs))
        exercised.add(VIEWS + "L10-U1")
        self.assertTrue(all(s.view for s in specs))
        exercised.add(VIEWS + "L11-U1")
        self.assertEqual({s.mode for s in specs}, {"generated", "regression"})
        exercised.add(VIEWS + "L12-U1")
        self.assertTrue(all(s.generator for s in specs if s.mode == "generated"))
        exercised.add(VIEWS + "L13-U1")
        self.assertTrue(all(s.drift_check for s in specs))
        exercised.add(VIEWS + "L14-U1")

        # L3: una vista nunca se valida como fuente de sí misma.
        with self.assertRaises(DerivedViewError):
            DerivedViewSpec("loop", "canonical", "canonical", "regression",
                            None, "tests/test_derived_views.py").validate()
        exercised.add(VIEWS + "L3-U1")

        # L18: la primitiva pura ordena, escapa Markdown y estabiliza bytes.
        rows = [{"id": "z", "status": "a|b"},
                {"id": "a", "status": "active"}]
        columns = ("id", "status")
        expected = "| id | status |\n| --- | --- |\n| a | active |\n| z | a\\|b |\n"
        self.assertEqual(render_markdown_table(rows, columns, sort_by="id"),
                         expected)
        with patch("time.time", side_effect=AssertionError("time forbidden")), \
             patch("random.random", side_effect=AssertionError("random forbidden")):
            self.assertEqual(render_markdown_table(rows, columns, sort_by="id"),
                             expected)
        exercised.add(VIEWS + "L18-U1")
        self.assertEqual(
            render_markdown_table(reversed(rows), columns, sort_by="id").encode(),
            expected.encode(),
        )
        exercised.add(VIEWS + "L18-U2")

        # L24: drift exacto falla cerrado incluso por un solo cambio.
        check_drift(expected, expected)
        with self.assertRaises(DerivedViewDriftError):
            check_drift(expected, expected.replace("active", "paused"))
        exercised.add(VIEWS + "L24-U1")

        # L28: regresión real de claims README/ESTADO sobre sus fuentes.
        suite = unittest.TestLoader().discover(
            str(ROOT / "tests"), pattern="test_readme_tandas.py")
        result = unittest.TestResult()
        suite.run(result)
        self.assertTrue(result.wasSuccessful(),
                        f"regresión: {result.failures}; {result.errors}")
        self.assertGreater(result.testsRun, 0)
        exercised.add(VIEWS + "L28-U1")
        self.assertEqual(exercised, OFFLINE)

    def test_falla_cerrado(self) -> None:
        """AC-02: datos ambiguos, faltantes o permisos inválidos se rechazan."""
        record = synthetic_record()
        for invalid in (
            {**record, "evidence": {}},
            {**record, "data_categories": ["none", "identifier"]},
            {**record, "project": "pl0n3r/Unknown"},
            {**record, "untrusted_email": "synthetic@example.test"},
        ):
            with self.subTest(fields=sorted(invalid)):
                with self.assertRaises(ComplianceError):
                    validate_privacy(invalid, now=NOW)
        with self.assertRaises(ComplianceError):
            inspect_composer({
                "packages": [{"name": "vendor/x", "version": "1",
                              "license": ["NOASSERTION"]}],
                "packages-dev": [],
            })
        with self.assertRaises(ComplianceError):
            inspect_npm({"packages": {
                "node_modules/x": {"version": "1"},
            }})

        template = DerivedViewSpec("one", "source", "view", "generated",
                                   "module:function", "test_drift")
        for difference in (
            {"view_id": ""}, {"source": ""}, {"view": ""},
            {"mode": "invalid"}, {"generator": None},
            {"drift_check": ""}, {"source": "view"},
        ):
            with self.subTest(spec=difference):
                with self.assertRaises(DerivedViewError):
                    DerivedViewSpec(**{**vars(template), **difference}).validate()
        with self.assertRaises(DerivedViewError):
            DerivedViewSpec("one", "src", "dst", "regression",
                            "generator", "test").validate()
        with self.assertRaises(DerivedViewError):
            render_markdown_table([{"id": "x"}], (), sort_by="id")
        with self.assertRaises(DerivedViewError):
            render_markdown_table([{"id": "x"}], ("id",), sort_by="absent")
        with self.assertRaises(DerivedViewDriftError):
            check_drift("source canonical\n", "source modified\n")
        with self.assertRaises(DerivedViewError):
            replace_delimited_block(
                "<!-- begin --><!-- begin --><!-- end -->",
                start_marker="<!-- begin -->", end_marker="<!-- end -->",
                content="x",
            )
        self.assertEqual((len(WORLD), len(POLICY)), (4, 3))

    def test_sin_datos_reales(self) -> None:
        """AC-03: fixtures no son certificación ni fuga de información."""
        record = synthetic_record()
        original = deepcopy(record)
        self.assertEqual(validate_privacy(record, now=NOW), "pl0n3r/GrindFlow")
        self.assertEqual(record, original)
        self.assertEqual(set(record["evidence"]), REQUIRED_EVIDENCE)
        self.assertTrue(all(v.startswith("fixture:")
                            for v in record["evidence"].values()))
        self.assertFalse(any("@" in v for v in record["evidence"].values()))
        with patch("seguridad.cumplimiento.datetime") as fake_dt:
            fake_dt.now.return_value = NOW
            fake_dt.strptime.side_effect = datetime.strptime
            status, output = run_cli(record)
        self.assertEqual(status, 0)
        result = json.loads(output)
        self.assertEqual(result["evidence_status"],
                         "documented_not_legally_approved")
        self.assertEqual(result["license_status"],
                         "identifiers_present_review_required")
        self.assertNotIn("evidence", result)
        self.assertNotIn("consent_or_exception", result)
        self.assertNotIn("fixture:", output)


if __name__ == "__main__":
    unittest.main()
