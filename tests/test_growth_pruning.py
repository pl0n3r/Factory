import unittest

from evolution.constitution import validate_candidate
from evolution.growth import (
    compile_growth_candidate,
    detect_capability_gap,
)
from evolution.pruning import (
    PruningError,
    compile_pruning_candidate,
    evaluate_pruning,
)


class GrowthPruningTests(unittest.TestCase):
    def test_missing_capability_can_generate_validated_candidate(self):
        gap = detect_capability_gap(
            required_capability="Schema Drift Detector",
            available_capabilities=["risk compiler", "fitness engine"],
        )
        self.assertTrue(gap["gap"])

        growth = compile_growth_candidate(
            gap=gap,
            evidence=["pl0n3r/factory#154", "pl0n3r/factory#143"],
            expected_value="Detect schema drift before promotion.",
        )

        self.assertIsNotNone(growth)
        self.assertEqual(growth["capability"], "schema-drift-detector")
        self.assertEqual(
            validate_candidate(growth["candidate"]),
            growth["candidate_fingerprint"],
        )
        self.assertTrue(growth["candidate"]["rollback"]["reversible"])

    def test_duplicate_capability_is_reused_not_regrown(self):
        gap = detect_capability_gap(
            required_capability="Schema Drift Detector",
            available_capabilities=[
                "schema-drift-detector",
                "Risk Compiler",
            ],
        )

        self.assertFalse(gap["gap"])
        self.assertEqual(gap["reuse"], "schema-drift-detector")
        self.assertIsNone(
            compile_growth_candidate(
                gap=gap,
                evidence=["pl0n3r/factory#154"],
                expected_value="Should not duplicate.",
            )
        )

    def test_pruning_requires_evidence_and_preserves_lineage(self):
        insufficient = evaluate_pruning(
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130"],
            parent_fingerprint="a" * 64,
        )
        self.assertFalse(insufficient["eligible"])
        self.assertIsNone(compile_pruning_candidate(insufficient))

        evaluation = evaluate_pruning(
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130", "pl0n3r/factory#131"],
            parent_fingerprint="a" * 64,
        )
        pruning = compile_pruning_candidate(evaluation)

        self.assertTrue(evaluation["eligible"])
        self.assertIsNotNone(pruning)
        self.assertEqual(pruning["lineage"]["parent_fingerprint"], "a" * 64)
        self.assertTrue(pruning["lineage"]["history_preserved"])
        self.assertEqual(
            pruning["lineage"]["evaluation_fingerprint"],
            evaluation["fingerprint"],
        )
        self.assertEqual(
            validate_candidate(pruning["candidate"]),
            pruning["candidate_fingerprint"],
        )

    def test_non_finite_value_score_fails_closed(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(PruningError, "finito"):
                    evaluate_pruning(
                        capability="legacy formatter",
                        usage_count=0,
                        age_days=180,
                        value_score=value,
                        evidence=[
                            "pl0n3r/factory#130",
                            "pl0n3r/factory#131",
                        ],
                    )

    def test_protected_capabilities_cannot_be_pruned(self):
        for capability in ("security", "privacy", "constitution", "human gates"):
            with self.subTest(capability=capability):
                with self.assertRaisesRegex(PruningError, "protegida"):
                    evaluate_pruning(
                        capability=capability,
                        usage_count=0,
                        age_days=999,
                        value_score=0,
                        evidence=[
                            "pl0n3r/factory#140",
                            "pl0n3r/factory#141",
                        ],
                    )


if __name__ == "__main__":
    unittest.main()
