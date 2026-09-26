import copy
import unittest

from evolution.fitness import FitnessError, compare_fitness


def metric(value, direction="higher"):
    return {"value": value, "direction": direction}


class FitnessEngineTests(unittest.TestCase):
    def test_fitness_is_multidimensional_not_single_magic_score(self):
        result = compare_fitness(
            baseline={
                "security": metric(0.90),
                "performance": metric(100),
                "cost": metric(10, "lower"),
            },
            candidate={
                "security": metric(0.95),
                "performance": metric(100),
                "cost": metric(8, "lower"),
            },
        )
        self.assertNotIn("score", result)
        self.assertEqual(
            set(result["dimensions"]),
            {"security", "performance", "cost"},
        )
        self.assertEqual(result["dimensions"]["security"]["status"], "improved")
        self.assertEqual(result["dimensions"]["performance"]["status"], "equal")
        self.assertEqual(result["dimensions"]["cost"]["status"], "improved")
        self.assertEqual(result["claim"], "improved")
        self.assertTrue(result["can_claim_improvement"])

    def test_protected_dimension_regression_blocks_improvement_claim(self):
        result = compare_fitness(
            baseline={
                "security": metric(0.95),
                "cost": metric(10, "lower"),
            },
            candidate={
                "security": metric(0.90),
                "cost": metric(5, "lower"),
            },
        )
        self.assertEqual(result["dimensions"]["cost"]["status"], "improved")
        self.assertEqual(result["dimensions"]["security"]["status"], "regressed")
        self.assertEqual(result["protected_regressions"], ["security"])
        self.assertEqual(result["claim"], "blocked")
        self.assertFalse(result["can_claim_improvement"])

    def test_missing_metrics_lower_confidence_not_get_imputed(self):
        result = compare_fitness(
            baseline={
                "security": metric(0.90),
                "cost": metric(10, "lower"),
            },
            candidate={
                "security": metric(0.95),
            },
        )
        self.assertEqual(result["missing_dimensions"], ["cost"])
        self.assertEqual(
            result["confidence"],
            {"comparable": 1, "total": 2, "ratio": 0.5},
        )
        self.assertEqual(result["dimensions"]["cost"]["baseline"], 10)
        self.assertIsNone(result["dimensions"]["cost"]["candidate"])
        self.assertIsNone(result["dimensions"]["cost"]["delta"])
        self.assertEqual(result["claim"], "inconclusive")
        self.assertFalse(result["can_claim_improvement"])

    def test_baseline_comparison_is_deterministic(self):
        baseline = {
            "cost": metric(10, "lower"),
            "security": metric(0.90),
            "performance": metric(100),
        }
        candidate = {
            "performance": metric(105),
            "security": metric(0.92),
            "cost": metric(9, "lower"),
        }
        reordered_baseline = {
            "performance": copy.deepcopy(baseline["performance"]),
            "security": copy.deepcopy(baseline["security"]),
            "cost": copy.deepcopy(baseline["cost"]),
        }
        first = compare_fitness(baseline=baseline, candidate=candidate)
        second = compare_fitness(
            baseline=reordered_baseline,
            candidate=copy.deepcopy(candidate),
        )
        self.assertEqual(first, second)
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")

    def test_rejects_direction_drift_and_non_finite_values(self):
        with self.assertRaisesRegex(FitnessError, "direction no coincide"):
            compare_fitness(
                baseline={"latency": metric(100, "lower")},
                candidate={"latency": metric(90, "higher")},
            )
        with self.assertRaisesRegex(FitnessError, "finito"):
            compare_fitness(
                baseline={"security": metric(1.0)},
                candidate={"security": metric(float("nan"))},
            )


if __name__ == "__main__":
    unittest.main()
