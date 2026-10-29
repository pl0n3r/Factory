"""Cobertura conductual offline de Fitness Engine y Growth (Factory #1809)."""
from __future__ import annotations

import copy
import socket
import subprocess
import unittest
import urllib.request
from unittest import mock

from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from evolution.fitness import FitnessError, compare_fitness, validate_fitness_evidence
from evolution.growth import (
    GrowthError, canonical_capability, compile_growth_candidate, detect_capability_gap,
)


def _metric(value, direction="higher"):
    return {"value": value, "direction": direction}


def _vector(**extra):
    values = {name: _metric(1.0) for name in PROTECTED_INVARIANTS}
    values.update(extra)
    return values


def _growth(available=None, required="Schema Drift Detector"):
    inventory = ["risk compiler"] if available is None else available
    gap = detect_capability_gap(
        required_capability=required, available_capabilities=inventory,
    )
    result = compile_growth_candidate(
        gap=gap, required_capability=required, available_capabilities=inventory,
        evidence=["synthetic:test-b", "synthetic:test-a"],
        expected_value="Detect schema drift before promotion.",
    )
    return gap, result


class CoberturaFactory18Tests(unittest.TestCase):
    """AC-01: los 20 contratos ejercen motores reales, no el estado de la matriz."""

    def test_contrato_principal(self):
        baseline = _vector(latency=_metric(100, "lower"))
        faster = _vector(latency=_metric(90, "lower"))
        slower = _vector(latency=_metric(110, "lower"))
        improved = compare_fitness(baseline=baseline, candidate=faster)
        equal = compare_fitness(baseline=baseline, candidate=baseline)
        regressed = compare_fitness(baseline=baseline, candidate=slower)

        with self.subTest(row="fitness:L30-U1"):
            blocked = compare_fitness(
                baseline=_vector(security=_metric(0.9)),
                candidate=_vector(security=_metric(0.8)),
            )
            self.assertEqual(blocked["claim"], "blocked")
            self.assertFalse(blocked["can_claim_improvement"])
            self.assertNotIn("promotion_executed", blocked)

        with self.subTest(row="fitness:L37-U1"):
            self.assertEqual(improved["dimensions"]["latency"]["status"], "improved")
            self.assertEqual(improved["dimensions"]["latency"]["delta"], -10)
            throughput = compare_fitness(
                baseline=_vector(throughput=_metric(3)),
                candidate=_vector(throughput=_metric(4)),
            )
            self.assertEqual(throughput["dimensions"]["throughput"]["status"], "improved")

        with self.subTest(row="fitness:L38-U1"):
            self.assertEqual(equal["dimensions"]["latency"]["status"], "equal")
            self.assertEqual(equal["dimensions"]["latency"]["delta"], 0)

        with self.subTest(row="fitness:L39-U1"):
            self.assertEqual(regressed["dimensions"]["latency"]["status"], "regressed")
            self.assertEqual(regressed["dimensions"]["latency"]["delta"], 10)

        missing = compare_fitness(baseline=baseline, candidate=_vector())
        with self.subTest(row="fitness:L40-U1"):
            self.assertEqual(missing["dimensions"]["latency"]["status"], "unknown")
            self.assertIsNone(missing["dimensions"]["latency"]["candidate"])
            self.assertIsNone(missing["dimensions"]["latency"]["delta"])

        protected_regression = compare_fitness(
            baseline=_vector(authority=_metric(1.0),
                             latency=_metric(100, "lower")),
            candidate=_vector(authority=_metric(0.0),
                              latency=_metric(80, "lower")),
        )
        with self.subTest(row="fitness:L50-U1"):
            self.assertEqual(protected_regression["claim"], "blocked")
            self.assertIn("authority", protected_regression["protected_regressions"])
            self.assertEqual(protected_regression["dimensions"]["latency"]["status"],
                             "improved")

        with self.subTest(row="fitness:L51-U1"):
            self.assertEqual(missing["claim"], "inconclusive")
            self.assertIn("latency", missing["missing_dimensions"])
            self.assertLess(missing["confidence"]["ratio"], 1)

        mixed = compare_fitness(
            baseline=_vector(latency=_metric(100, "lower"),
                             throughput=_metric(3)),
            candidate=_vector(latency=_metric(110, "lower"),
                              throughput=_metric(4)),
        )
        with self.subTest(row="fitness:L52-U1"):
            self.assertEqual(mixed["claim"], "mixed")
            self.assertFalse(mixed["can_claim_improvement"])

        with self.subTest(row="fitness:L53-U1"):
            self.assertEqual(improved["claim"], "improved")
            self.assertEqual(improved["missing_dimensions"], [])
            self.assertEqual(improved["protected_regressions"], [])

        with self.subTest(row="fitness:L54-U1"):
            self.assertEqual(equal["claim"], "equal")
            self.assertEqual(equal["confidence"]["ratio"], 1)

        with self.subTest(row="fitness:L56-U1"):
            for result, expected in (
                (improved, True), (equal, False), (regressed, False),
                (missing, False), (mixed, False), (protected_regression, False),
            ):
                self.assertIs(result["can_claim_improvement"], expected)

        with self.subTest(row="fitness:L62-U1"):
            reordered = compare_fitness(
                baseline=dict(reversed(list(baseline.items()))),
                candidate=dict(reversed(list(faster.items()))),
            )
            self.assertRegex(improved["fingerprint"], r"^[0-9a-f]{64}$")
            self.assertEqual(improved["fingerprint"], reordered["fingerprint"])

        with self.subTest(row="fitness:L69-U1"):
            self.assertEqual(
                validate_fitness_evidence(
                    baseline=baseline, candidate=faster,
                    result=copy.deepcopy(improved),
                ),
                improved,
            )
            self.assertNotIn("score", improved)
            self.assertEqual(improved["dimensions"]["latency"]["baseline"], 100)
            self.assertEqual(improved["dimensions"]["latency"]["candidate"], 90)

        with self.subTest(row="fitness:L75-U1"):
            self.assertTrue(set(PROTECTED_INVARIANTS).issubset(
                improved["protected_dimensions"]))
            for name in ("reversibility", "authority"):
                self.assertTrue(improved["dimensions"][name]["protected"])
            absent = compare_fitness(
                baseline={"cost": _metric(9, "lower")},
                candidate={"cost": _metric(8, "lower")},
            )
            self.assertEqual(absent["claim"], "inconclusive")
            self.assertIn("reversibility", absent["missing_dimensions"])
            self.assertIn("authority", absent["missing_dimensions"])

        gap, growth = _growth()
        self.assertIsNotNone(growth)
        with self.subTest(row="growth:L10-U1"):
            self.assertEqual(canonical_capability(" SCHÉMA... Drift   Detector "),
                             "schema-drift-detector")
            reuse = detect_capability_gap(
                required_capability="SCHÉMA drift detector!",
                available_capabilities=["schema-drift-detector"],
            )
            self.assertFalse(reuse["gap"])
            self.assertEqual(reuse["reuse"], "schema-drift-detector")
            self.assertTrue(detect_capability_gap(
                required_capability="authorization",
                available_capabilities=["permissions"],
            )["gap"])

        with self.subTest(row="growth:L20-U1"):
            self.assertEqual(gap["required"], "schema-drift-detector")
            self.assertEqual(growth["capability"], gap["required"])
            self.assertEqual(
                growth["candidate"]["changes"][0]["value"]["capability"],
                gap["required"],
            )

        with self.subTest(row="growth:L21-U1"):
            self.assertEqual(growth["expected_value"],
                             "Detect schema drift before promotion.")
            self.assertEqual(
                growth["candidate"]["changes"][0]["value"]["expected_value"],
                growth["expected_value"],
            )

        with self.subTest(row="growth:L22-U1"):
            self.assertRegex(gap["fingerprint"], r"^[0-9a-f]{64}$")
            self.assertEqual(growth["lineage"]["gap_fingerprint"],
                             gap["fingerprint"])
            self.assertEqual(
                growth["candidate"]["changes"][0]["value"]["lineage"]["gap_fingerprint"],
                gap["fingerprint"],
            )

        with self.subTest(row="growth:L23-U1"):
            self.assertEqual(growth["lineage"]["evidence"],
                             ["synthetic:test-a", "synthetic:test-b"])
            self.assertEqual(growth["candidate"]["evidence"],
                             growth["lineage"]["evidence"])

        with self.subTest(row="growth:L24-U1"):
            self.assertTrue(growth["candidate"]["rollback"]["reversible"])
            self.assertEqual(growth["candidate"]["rollback"]["strategy"], "revert")
            self.assertEqual(validate_candidate(growth["candidate"]),
                             growth["candidate_fingerprint"])

    def test_falla_cerrado(self):
        """AC-02: rechaza incertidumbre, fraude y pérdida de protecciones."""
        base = _vector()
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(non_finite=value), self.assertRaises(FitnessError):
                compare_fitness(
                    baseline=base, candidate=_vector(security=_metric(value)),
                )
        with self.assertRaises(FitnessError):
            compare_fitness(
                baseline=_vector(latency=_metric(10, "lower")),
                candidate=_vector(latency=_metric(8, "higher")),
            )
        with self.assertRaises(FitnessError):
            compare_fitness(
                baseline=base, candidate=base,
                protected_dimensions=["security", "privacy"],
            )
        with self.assertRaises(FitnessError):
            compare_fitness(baseline={}, candidate=base)
        forged_result = compare_fitness(baseline=base, candidate=base)
        forged_result["can_claim_improvement"] = True
        with self.assertRaises(FitnessError):
            validate_fitness_evidence(
                baseline=base, candidate=base, result=forged_result,
            )
        gap, _ = _growth()
        args = {
            "required_capability": "Schema Drift Detector",
            "available_capabilities": ["risk compiler"],
            "evidence": ["synthetic:test"],
            "expected_value": "New detector",
        }
        with self.assertRaises(GrowthError):
            compile_growth_candidate(
                gap={**gap, "required": "other-capability"}, **args,
            )
        with self.assertRaises(GrowthError):
            compile_growth_candidate(gap=gap, **{**args, "evidence": []})
        with self.assertRaises(GrowthError):
            compile_growth_candidate(
                gap=gap, **{**args, "expected_value": "  "},
            )
        with self.assertRaises(GrowthError):
            detect_capability_gap(required_capability="  ",
                                  available_capabilities=[])
        self.assertIsNone(compile_growth_candidate(
            gap=gap,
            **{**args, "available_capabilities": ["Schema Drift Detector"]},
        ))

    def test_sin_datos_reales(self):
        """AC-03: la ejecución sintética no invoca red ni subprocesos."""
        baseline = _vector(latency=_metric(12, "lower"))
        candidate = _vector(latency=_metric(11, "lower"))
        original = copy.deepcopy((baseline, candidate))
        with (mock.patch.object(socket, "socket", side_effect=AssertionError("no network")),
              mock.patch.object(socket, "create_connection",
                                side_effect=AssertionError("no network")),
              mock.patch.object(urllib.request, "urlopen",
                                side_effect=AssertionError("no network")),
              mock.patch.object(subprocess, "run",
                                side_effect=AssertionError("no subprocess"))):
            fitness = compare_fitness(baseline=baseline, candidate=candidate)
            gap, growth = _growth()
            evidence = validate_fitness_evidence(
                baseline=baseline, candidate=candidate, result=fitness,
            )
        self.assertEqual(evidence["fingerprint"], fitness["fingerprint"])
        self.assertEqual(growth["lineage"]["gap_fingerprint"], gap["fingerprint"])
        self.assertEqual((baseline, candidate), original)
        self.assertEqual(fitness["claim"], "improved")
        self.assertTrue(growth["candidate"]["rollback"]["reversible"])


if __name__ == "__main__":
    unittest.main()
