#!/usr/bin/env python3
"""#1834: ejecutar contratos Quality reales contra fixtures sintéticos.

Cada unidad apunta a una regresión existente que invoca la API de negocio
(Quality Health, Project DNA, Risk/DoD o Regression Intelligence).
NO lee la matriz ni infiere estados de despliegue o aprobación de producción.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from functools import lru_cache
from importlib import import_module
from pathlib import Path
import socket
import sys
import traceback
import unittest
from unittest import mock

from quality.regression import QualityRegressionError, analyze_regression

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


@contextmanager
def _local_test_imports():
    """Restituye temporalmente la ruta que acceptance-kit quita al importar."""
    added = []
    for entry in (str(ROOT), str(TESTS)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
            added.append(entry)
    try:
        yield
    finally:
        for entry in added:
            if entry in sys.path:
                sys.path.remove(entry)


# (ID de requisito, módulo funcional, clase, test real). 20 unidades exactas.
OFFLINE_CASES = (
    ['docs/quality-gates.md:L7-U2','test_quality_gates','QualityGateCompilerTests','test_missing_mismatched_or_undeclared_quality_context_fails_closed'],
    ['docs/quality-health.md:B01','test_quality_status','QualityStatusTests','test_quality_health_derives_pass_degraded_unknown_blocked_with_reasons_and_freshness'],
    ['docs/quality-health.md:B02','test_quality_status','QualityStatusTests','test_sonar_fail_unknown_and_stale_never_promote_to_pass'],
    ['docs/quality-health.md:B03','test_quality_status','QualityStatusTests','test_performance_and_recovery_are_external_dimensions_without_recalculation'],
    ['docs/quality-health.md:B04','test_quality_status','QualityStatusTests','test_readiness_projection_reuses_quality_health_and_unknown_or_blocked_never_ready'],
    ['docs/quality-project-dna.md:L12-U1','test_quality_project_dna','QualityProjectDnaTests','test_valid_quality_contract_is_attached_by_reference_and_fingerprint'],
    ['docs/quality-project-dna.md:L13-U1','test_quality_project_dna','QualityProjectDnaTests','test_valid_quality_contract_is_attached_by_reference_and_fingerprint'],
    ['docs/quality-project-dna.md:L17-U1','test_quality_project_dna','QualityProjectDnaTests','test_valid_quality_contract_is_attached_by_reference_and_fingerprint'],
    ['docs/quality-project-dna.md:L18-U1','test_quality_project_dna','QualityProjectDnaTests','test_invalid_contract_reference_or_tampered_dna_fails_closed_without_inference'],
    ['docs/quality-project-dna.md:L19-U1','test_quality_project_dna','QualityProjectDnaTests','test_existing_project_dna_discovery_remains_backward_compatible'],
    ['docs/quality-project-dna.md:L20-U1','test_quality_project_dna','QualityProjectDnaTests','test_valid_quality_contract_is_attached_by_reference_and_fingerprint'],
    ['docs/quality-project-dna.md:L21-U1','test_quality_project_dna','QualityProjectDnaTests','test_invalid_contract_reference_or_tampered_dna_fails_closed_without_inference'],
    ['docs/quality-project-dna.md:L22-U1','test_quality_project_dna','QualityProjectDnaTests','test_schema_documents_quality_extension_without_closing_extensions_namespace'],
    ['docs/quality-project-dna.md:L24-U1','test_quality_project_dna','QualityProjectDnaTests','test_valid_quality_contract_is_attached_by_reference_and_fingerprint'],
    ['docs/quality-project-dna.md:L9-U1','test_quality_project_dna','QualityProjectDnaTests','test_valid_quality_contract_is_attached_by_reference_and_fingerprint'],
    ['docs/quality-regression.md:L10-U1','test_quality_regression','QualityRegressionTests','test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green'],
    ['docs/quality-regression.md:L11-U1','test_quality_regression','QualityRegressionTests','test_unverified_fix_or_missing_regression_test_never_emits_guardrail_material'],
    ['docs/quality-regression.md:L12-U1','test_quality_regression','QualityRegressionTests','test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler'],
    ['docs/quality-regression.md:L18-U1','test_quality_regression','QualityRegressionTests','test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green'],
    ['docs/quality-regression.md:L18-U2','test_quality_regression','QualityRegressionTests','test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green'],
)


@lru_cache(maxsize=4)
def _source_module(module_name: str):
    """Carga por ruta exacta la suite funcional, nunca por nombre arbitrario."""
    allowed = {
        "test_quality_gates",
        "test_quality_status",
        "test_quality_project_dna",
        "test_quality_regression",
    }
    if module_name not in allowed:
        raise AssertionError("Módulo de prueba fuera del contrato")
    with _local_test_imports():
        return import_module(module_name)


def _exercise(case):
    """Ejecuta la regresión real, exige exactamente un caso y cero fallos."""
    _, module_name, class_name, test_name = case
    module = _source_module(module_name)
    suite = unittest.TestLoader().loadTestsFromName(
        class_name + "." + test_name, module
    )
    result = unittest.TestResult()
    with _local_test_imports():
        suite.run(result)
    if result.testsRun != 1 or not result.wasSuccessful():
        print(
            "FACTORY43_DIAGNOSTIC",
            case[0], "runs=", result.testsRun,
            "errors=", result.errors, "failures=", result.failures,
            flush=True,
        )
        raise AssertionError(
            "Regresión funcional no acreditada: "
            + class_name + "." + test_name
            + " errors=" + str(result.errors)
            + " failures=" + str(result.failures)
        )
    return result.testsRun


class CoberturaFactory43Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: cada una de las 20 unidades ejecuta el código real."""
        ids = [row[0] for row in OFFLINE_CASES]
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)
        try:
            self.assertEqual(
                sum(_exercise(case) for case in OFFLINE_CASES), 20
            )
        except Exception:
            print("FACTORY43_AC01_TRACE", traceback.format_exc(), flush=True)
            raise

    def test_falla_cerrado(self):
        """AC-02: evidencias ambiguas, contrato ausente y pruebas no válidas."""
        for unit in (
            "docs/quality-gates.md:L7-U2",
            "docs/quality-health.md:B02",
            "docs/quality-health.md:B04",
            "docs/quality-project-dna.md:L21-U1",
            "docs/quality-regression.md:L18-U2",
        ):
            case = next(c for c in OFFLINE_CASES if c[0] == unit)
            with self.subTest(unit=unit):
                self.assertEqual(_exercise(case), 1)

        regression = _source_module("test_quality_regression")
        valid = regression.observation()
        for missing in ("before", "after", "root_cause", "source"):
            with self.subTest(missing=missing):
                invalid = copy.deepcopy(valid)
                invalid.pop(missing)
                with self.assertRaises(QualityRegressionError):
                    analyze_regression(
                        invalid, evaluated_at=regression.EVALUATED_AT
                    )
        with self.assertRaises(AssertionError):
            _source_module("untrusted_unknown_file")

    def test_sin_datos_reales(self):
        """AC-03: tests funcionales con fixtures y sin conexiones exteriores."""
        units = (
            "docs/quality-health.md:B03",
            "docs/quality-project-dna.md:L13-U1",
            "docs/quality-regression.md:L10-U1",
        )
        # Los módulos se cargan antes del veto de red; los casos ejecutan
        # lógica real con sus muestras deterministas, no una API externa.
        for unit in units:
            case = next(c for c in OFFLINE_CASES if c[0] == unit)
            _source_module(case[1])
        with mock.patch.object(
            socket.socket, "connect",
            side_effect=AssertionError("Red prohibida en pruebas sintéticas"),
        ) as connect:
            for unit in units:
                with self.subTest(unit=unit):
                    case = next(c for c in OFFLINE_CASES if c[0] == unit)
                    self.assertEqual(_exercise(case), 1)
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
