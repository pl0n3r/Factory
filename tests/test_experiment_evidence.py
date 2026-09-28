import unittest

from lab.experiment_evidence import evaluate_experiment_evidence
from lab.factory_lab import (
    FactoryLabError,
    causal_promotion_contract,
    evaluate_shadow,
)


def metrics(reliability):
    return {
        "security": {"value": 1.0, "direction": "higher"},
        "privacy": {"value": 1.0, "direction": "higher"},
        "traceability": {"value": 1.0, "direction": "higher"},
        "reversibility": {"value": 1.0, "direction": "higher"},
        "authority": {"value": 1.0, "direction": "higher"},
        "reliability": {"value": reliability, "direction": "higher"},
    }


def constitution_candidate():
    return {
        "version": 1,
        "changes": [
            {
                "path": "evolution_state.heuristics.causal_candidate",
                "operation": "add",
                "value": {"status": "candidate"},
            }
        ],
        "evidence": ["pl0n3r/factory#244"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }


def experiment(
    *,
    evidence_class="controlled_shadow",
    impact="high",
    baseline_sample_size=8,
    treatment_sample_size=8,
    confounders=(),
    simultaneous_changes=(),
    baseline_sha="a" * 40,
    treatment_sha="b" * 40,
):
    return {
        "baseline": "stable:main",
        "treatment": "candidate:issue-244",
        "baseline_sha": baseline_sha,
        "treatment_sha": treatment_sha,
        "protected_metrics": [
            "security",
            "privacy",
            "traceability",
            "reversibility",
            "authority",
        ],
        "evidence_class": evidence_class,
        "impact": impact,
        "baseline_sample_size": baseline_sample_size,
        "treatment_sample_size": treatment_sample_size,
        "confounders": list(confounders),
        "simultaneous_changes": list(simultaneous_changes),
    }


class ExperimentEvidenceTests(unittest.TestCase):
    def test_experiment_declares_baseline_treatment_and_protected_metrics(self):
        result = evaluate_experiment_evidence(experiment())

        self.assertEqual(result["baseline"], "stable:main")
        self.assertEqual(result["treatment"], "candidate:issue-244")
        self.assertEqual(result["baseline_sha"], "a" * 40)
        self.assertEqual(result["treatment_sha"], "b" * 40)
        self.assertEqual(
            result["protected_metrics"],
            ["authority", "privacy", "reversibility", "security", "traceability"],
        )
        self.assertEqual(result["evidence_class"], "controlled_shadow")
        self.assertEqual(result["impact"], "high")
        self.assertNotIn("score", result)

    def test_observational_single_case_cannot_promote_high_impact_change(self):
        result = evaluate_experiment_evidence(
            experiment(
                evidence_class="observational",
                impact="high",
                baseline_sample_size=1,
                treatment_sample_size=1,
            )
        )

        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertFalse(result["promotion_allowed"])
        self.assertIn("sample_below_risk_minimum", result["reasons"])
        self.assertIn(
            "causal_strength_below_impact_requirement",
            result["reasons"],
        )

    def test_insufficient_sample_returns_insufficient_evidence(self):
        result = evaluate_experiment_evidence(
            experiment(
                evidence_class="controlled_shadow",
                impact="high",
                baseline_sample_size=4,
                treatment_sample_size=4,
            )
        )

        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertFalse(result["promotion_allowed"])
        self.assertEqual(result["sample"]["required_minimum"], 8)

    def test_confounders_are_recorded_and_reduce_claim_strength(self):
        clean = evaluate_experiment_evidence(
            experiment(
                impact="medium",
                baseline_sample_size=8,
                treatment_sample_size=8,
            )
        )
        confounded = evaluate_experiment_evidence(
            experiment(
                impact="medium",
                baseline_sample_size=8,
                treatment_sample_size=8,
                confounders=("model-version",),
                simultaneous_changes=("prompt-and-role-change",),
            )
        )

        self.assertEqual(clean["claim_strength"], "strong")
        self.assertEqual(confounded["claim_strength"], "moderate")
        self.assertEqual(confounded["confounders"], ["model-version"])
        self.assertEqual(
            confounded["simultaneous_changes"],
            ["prompt-and-role-change"],
        )

    def test_lab_accepts_reproducible_evidence_and_rejects_weak_claim(self):
        stable = metrics(0.90)
        candidate = metrics(0.95)
        constitution = constitution_candidate()
        shadow = evaluate_shadow(
            stable_sha="a" * 40,
            candidate_sha="b" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
        )

        strong = causal_promotion_contract(
            shadow_result=shadow,
            stable_sha="a" * 40,
            candidate_sha="b" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
            experiment_declaration=experiment(),
        )
        self.assertTrue(strong["experiment_evidence"]["promotion_allowed"])
        self.assertEqual(strong["execution"], "not-performed")

        with self.assertRaisesRegex(
            FactoryLabError,
            "evidencia causal insuficiente",
        ):
            causal_promotion_contract(
                shadow_result=shadow,
                stable_sha="a" * 40,
                candidate_sha="b" * 40,
                stable_metrics=stable,
                candidate_metrics=candidate,
                constitution_candidate=constitution,
                experiment_declaration=experiment(
                    evidence_class="observational",
                    impact="high",
                    baseline_sample_size=8,
                    treatment_sample_size=8,
                ),
            )

    def test_causal_promotion_rejects_unmeasured_protected_metric(self):
        stable = metrics(0.90)
        candidate = metrics(0.95)
        constitution = constitution_candidate()
        shadow = evaluate_shadow(
            stable_sha="a" * 40,
            candidate_sha="b" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
        )
        declaration = experiment()
        declaration["protected_metrics"].append("latency")

        with self.assertRaisesRegex(
            FactoryLabError,
            "protected_metrics no presentes en Fitness: latency",
        ):
            causal_promotion_contract(
                shadow_result=shadow,
                stable_sha="a" * 40,
                candidate_sha="b" * 40,
                stable_metrics=stable,
                candidate_metrics=candidate,
                constitution_candidate=constitution,
                experiment_declaration=declaration,
            )


    def test_causal_promotion_rejects_evidence_from_another_candidate_pair(self):
        stable = metrics(0.90)
        candidate = metrics(0.95)
        constitution = constitution_candidate()
        shadow = evaluate_shadow(
            stable_sha="a" * 40,
            candidate_sha="b" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
        )

        with self.assertRaisesRegex(
            FactoryLabError,
            "evidencia causal no corresponde al par evaluado",
        ):
            causal_promotion_contract(
                shadow_result=shadow,
                stable_sha="a" * 40,
                candidate_sha="b" * 40,
                stable_metrics=stable,
                candidate_metrics=candidate,
                constitution_candidate=constitution,
                experiment_declaration=experiment(
                    baseline_sha="c" * 40,
                    treatment_sha="d" * 40,
                ),
            )


if __name__ == "__main__":
    unittest.main()
