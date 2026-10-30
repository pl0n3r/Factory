#!/usr/bin/env python3
"""#1833: cobertura funcional offline de puertas humanas y Quality.

Cada caso ejecuta una regresión funcional existente contra fixtures sintéticos;
no lee matrices de cobertura ni realiza operaciones de producción.
"""
from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SECURITY = ROOT / "seguridad"

CASES = [
    [
        "docs/puertas-humanas.md:B06",
        "test_puertas_humanas",
        "GateDedupTests",
        "test_bot_privacy_gate_preserves_release_and_human_authority"
    ],
    [
        "docs/quality-contract.md:L15-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_sonar_monitoring_thresholds_are_explicit_and_deterministic"
    ],
    [
        "docs/quality-contract.md:L16-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_invalid_sonar_monitoring_contract_fails_closed"
    ],
    [
        "docs/quality-contract.md:L17-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_sonar_monitoring_thresholds_are_explicit_and_deterministic"
    ],
    [
        "docs/quality-contract.md:L18-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_invalid_sonar_monitoring_contract_fails_closed"
    ],
    [
        "docs/quality-contract.md:L19-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_sonar_monitoring_thresholds_are_explicit_and_deterministic"
    ],
    [
        "docs/quality-contract.md:L20-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_invalid_sonar_monitoring_contract_fails_closed"
    ],
    [
        "docs/quality-contract.md:L22-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_legacy_contract_without_sonar_preserves_canonical_form_and_fingerprint"
    ],
    [
        "docs/quality-contract.md:L7-U1",
        "test_quality_contract",
        "QualityContractTests",
        "test_performance_and_recovery_are_external_dimensions_not_parallel_pipelines"
    ],
    [
        "docs/quality-engineering.md:L19-U1",
        "test_quality_engineering_e2e",
        "QualityEngineeringE2ETests",
        "test_current_verified_healthy_flow_reaches_quality_pass_and_ready"
    ],
    [
        "docs/quality-engineering.md:L31-U1",
        "test_quality_engineering_e2e",
        "QualityEngineeringE2ETests",
        "test_stale_flaky_or_unknown_evidence_fails_closed_without_expanding_authority"
    ],
    [
        "docs/quality-engineering.md:L32-U1",
        "test_quality_status",
        "QualityStatusTests",
        "test_flaky_observed_or_unverified_regression_never_passes_and_critical_reproduced_failure_blocks"
    ],
    [
        "docs/quality-engineering.md:L32-U2",
        "test_quality_engineering_e2e",
        "QualityEngineeringE2ETests",
        "test_stale_flaky_or_unknown_evidence_fails_closed_without_expanding_authority"
    ],
    [
        "docs/quality-engineering.md:L33-U1",
        "test_quality_engineering_e2e",
        "QualityEngineeringE2ETests",
        "test_critical_quality_failure_materializes_corrective_work_through_existing_dispatcher"
    ],
    [
        "docs/quality-engineering.md:L41-U1",
        "test_quality_engineering_e2e",
        "QualityEngineeringE2ETests",
        "test_performance_and_recovery_remain_external_without_recalculation"
    ],
    [
        "docs/quality-gates.md:L11-U1",
        "test_quality_gates",
        "QualityGateCompilerTests",
        "test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk"
    ],
    [
        "docs/quality-gates.md:L11-U2",
        "test_quality_gates",
        "QualityGateCompilerTests",
        "test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk"
    ],
    [
        "docs/quality-gates.md:L7-U1",
        "test_quality_gates",
        "QualityGateCompilerTests",
        "test_missing_mismatched_or_undeclared_quality_context_fails_closed"
    ]
]
CLASSIFIED = {
    "docs/puertas-humanas.md:B05": (
        "C", "safe_default verdaderamente seguro y reversible requiere "
        "juicio humano contextual; el schema solo verifica la opción existente"
    ),
    "docs/quality-engineering.md:L43-U1": (
        "C", "la necesidad de evidencia propia por proyecto es un límite "
        "documentado, no un comportamiento local verificable"
    ),
}


@contextmanager
def _imports():
    added = []
    for path in (str(ROOT), str(TESTS), str(SECURITY)):
        if path not in sys.path:
            sys.path.insert(0, path)
            added.append(path)
    try:
        yield
    finally:
        for path in added:
            sys.path.remove(path)


def _exercise(row):
    requirement, module_name, class_name, method = row
    with _imports():
        module = import_module(module_name)
        suite = unittest.TestLoader().loadTestsFromName(
            class_name + "." + method, module
        )
        result = unittest.TestResult()
        suite.run(result)
    if result.testsRun != 1 or not result.wasSuccessful():
        raise AssertionError(
            f"{requirement}: prueba funcional no acreditada; "
            f"errors={result.errors!r}, failures={result.failures!r}"
        )


class CoberturaFactory42Tests(unittest.TestCase):
    def test_contrato_principal(self):
        self.assertEqual(len(CASES) + len(CLASSIFIED), 20)
        self.assertEqual(len({case[0] for case in CASES}), len(CASES))
        with mock.patch("socket.socket.connect",
                        side_effect=AssertionError("red prohibida")):
            for row in CASES:
                with self.subTest(requirement=row[0]):
                    _exercise(row)

    def test_falla_cerrado(self):
        # Las regresiones reales ejercen ausencia, mismatch, autoridad y stale.
        required = (
            "docs/puertas-humanas.md:B06",
            "docs/quality-contract.md:L16-U1",
            "docs/quality-contract.md:L18-U1",
            "docs/quality-contract.md:L20-U1",
            "docs/quality-engineering.md:L31-U1",
            "docs/quality-engineering.md:L32-U1",
            "docs/quality-gates.md:L7-U1",
        )
        by_id = {row[0]: row for row in CASES}
        with mock.patch("socket.socket.connect",
                        side_effect=AssertionError("red prohibida")):
            for key in required:
                with self.subTest(requirement=key):
                    _exercise(by_id[key])

    def test_sin_datos_reales(self):
        self.assertEqual(set(CLASSIFIED), {
            "docs/puertas-humanas.md:B05",
            "docs/quality-engineering.md:L43-U1",
        })
        self.assertEqual({category for category, _ in CLASSIFIED.values()}, {"C"})
        self.assertEqual(len(CASES), 18)
        self.assertTrue(all(
            module.startswith("test_") and method.startswith("test_")
            for _, module, _, method in CASES
        ))
        self.assertTrue(all(
            "@" not in str(case) and "token" not in str(case).lower()
            for case in CASES
        ))


if __name__ == "__main__":
    unittest.main()
