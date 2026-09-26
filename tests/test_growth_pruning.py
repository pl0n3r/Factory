import unittest

from evolution.constitution import validate_candidate
from evolution.growth import (
    GrowthError,
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
            required_capability="Schema Drift Detector",
            available_capabilities=["risk compiler", "fitness engine"],
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
                required_capability="Schema Drift Detector",
                available_capabilities=[
                    "schema-drift-detector",
                    "Risk Compiler",
                ],
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
        self.assertIsNone(
            compile_pruning_candidate(
                insufficient,
                capability="legacy formatter",
                usage_count=0,
                age_days=180,
                value_score=0.10,
                evidence=["pl0n3r/factory#130"],
                parent_fingerprint="a" * 64,
            )
        )

        evaluation = evaluate_pruning(
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130", "pl0n3r/factory#131"],
            parent_fingerprint="a" * 64,
        )
        pruning = compile_pruning_candidate(
            evaluation,
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130", "pl0n3r/factory#131"],
            parent_fingerprint="a" * 64,
        )

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

    def test_forged_gap_cannot_generate_candidate(self):
        canonical = detect_capability_gap(
            required_capability="schema drift detector",
            available_capabilities=["risk compiler"],
        )
        forged = dict(canonical)
        forged["required"] = "different-capability"
        forged_without_fingerprint = dict(forged)
        forged_without_fingerprint.pop("fingerprint")
        import hashlib
        import json
        forged["fingerprint"] = hashlib.sha256(
            json.dumps(
                forged_without_fingerprint,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        with self.assertRaisesRegex(GrowthError, "evidencia fuente"):
            compile_growth_candidate(
                gap=forged,
                required_capability="schema drift detector",
                available_capabilities=["risk compiler"],
                evidence=["pl0n3r/factory#213"],
                expected_value="Detect drift.",
            )

    def test_growth_recomputes_reuse_from_source_inventory(self):
        forged = detect_capability_gap(
            required_capability="schema drift detector",
            available_capabilities=["risk compiler"],
        )
        self.assertTrue(forged["gap"])

        result = compile_growth_candidate(
            gap=forged,
            required_capability="schema drift detector",
            available_capabilities=["Schema Drift Detector", "risk compiler"],
            evidence=["pl0n3r/factory#213"],
            expected_value="Must reuse instead.",
        )
        self.assertIsNone(result)
        canonical = detect_capability_gap(
            required_capability="schema drift detector",
            available_capabilities=["Schema Drift Detector", "risk compiler"],
        )
        self.assertFalse(canonical["gap"])
        self.assertEqual(canonical["reuse"], "Schema Drift Detector")

    def test_forged_pruning_evaluation_cannot_generate_candidate(self):
        forged = evaluate_pruning(
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130", "pl0n3r/factory#131"],
            parent_fingerprint="b" * 64,
        )
        self.assertTrue(forged["eligible"])

        result = compile_pruning_candidate(
            forged,
            capability="legacy formatter",
            usage_count=12,
            age_days=10,
            value_score=0.90,
            evidence=["pl0n3r/factory#130"],
            parent_fingerprint="b" * 64,
        )
        self.assertIsNone(result)

    def test_pruning_recomputes_eligibility_from_source_evidence(self):
        eligible = evaluate_pruning(
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130", "pl0n3r/factory#131"],
            parent_fingerprint="c" * 64,
        )

        for source in (
            {
                "usage_count": 2,
                "age_days": 180,
                "value_score": 0.10,
                "evidence": ["pl0n3r/factory#130", "pl0n3r/factory#131"],
            },
            {
                "usage_count": 0,
                "age_days": 89,
                "value_score": 0.10,
                "evidence": ["pl0n3r/factory#130", "pl0n3r/factory#131"],
            },
            {
                "usage_count": 0,
                "age_days": 180,
                "value_score": 0.26,
                "evidence": ["pl0n3r/factory#130", "pl0n3r/factory#131"],
            },
            {
                "usage_count": 0,
                "age_days": 180,
                "value_score": 0.10,
                "evidence": ["pl0n3r/factory#130"],
            },
        ):
            with self.subTest(source=source):
                self.assertIsNone(
                    compile_pruning_candidate(
                        eligible,
                        capability="legacy formatter",
                        parent_fingerprint="c" * 64,
                        **source,
                    )
                )

    def test_canonical_growth_and_pruning_remain_valid(self):
        gap = detect_capability_gap(
            required_capability="schema drift detector",
            available_capabilities=["risk compiler"],
        )
        growth = compile_growth_candidate(
            gap=gap,
            required_capability="schema drift detector",
            available_capabilities=["risk compiler"],
            evidence=["pl0n3r/factory#143", "pl0n3r/factory#213"],
            expected_value="Detect schema drift.",
        )
        self.assertIsNotNone(growth)
        self.assertEqual(
            validate_candidate(growth["candidate"]),
            growth["candidate_fingerprint"],
        )
        self.assertTrue(growth["candidate"]["rollback"]["reversible"])
        self.assertEqual(growth["lineage"]["gap_fingerprint"], gap["fingerprint"])

        evaluation = evaluate_pruning(
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130", "pl0n3r/factory#131"],
            parent_fingerprint="d" * 64,
        )
        pruning = compile_pruning_candidate(
            evaluation,
            capability="legacy formatter",
            usage_count=0,
            age_days=180,
            value_score=0.10,
            evidence=["pl0n3r/factory#130", "pl0n3r/factory#131"],
            parent_fingerprint="d" * 64,
        )
        self.assertIsNotNone(pruning)
        self.assertEqual(
            validate_candidate(pruning["candidate"]),
            pruning["candidate_fingerprint"],
        )
        self.assertEqual(pruning["lineage"]["parent_fingerprint"], "d" * 64)
        self.assertTrue(pruning["lineage"]["history_preserved"])
        self.assertEqual(
            pruning["lineage"]["evaluation_fingerprint"],
            evaluation["fingerprint"],
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
