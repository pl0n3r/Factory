from pathlib import Path
import re
import unittest

from evolution.constitution import ConstitutionError
from lab.factory_lab import FactoryLabError, evaluate_shadow, promotion_contract


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "evolution-lab.yml"


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
                "path": "evolution_state.heuristics.lab_candidate",
                "operation": "add",
                "value": {"status": "candidate"},
            }
        ],
        "evidence": ["pl0n3r/factory#153"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }


class FactoryLabContractTests(unittest.TestCase):
    def test_shadow_mode_has_no_mutation_permissions(self):
        result = evaluate_shadow(
            stable_sha="a" * 40,
            candidate_sha="b" * 40,
            stable_metrics=metrics(0.90),
            candidate_metrics=metrics(0.95),
            constitution_candidate=constitution_candidate(),
        )

        self.assertEqual(result["mode"], "shadow")
        self.assertFalse(result["mutation_allowed"])
        self.assertEqual(result["external_writes"], [])
        self.assertEqual(result["promotion"]["execution"], "not-performed")

    def test_candidate_is_compared_against_stable_baseline(self):
        result = evaluate_shadow(
            stable_sha="1" * 40,
            candidate_sha="2" * 40,
            stable_metrics=metrics(0.90),
            candidate_metrics=metrics(0.95),
            constitution_candidate=constitution_candidate(),
        )

        self.assertEqual(result["baseline"]["name"], "stable")
        self.assertEqual(result["baseline"]["sha"], "1" * 40)
        self.assertEqual(result["candidate"]["sha"], "2" * 40)
        self.assertEqual(result["fitness"]["claim"], "improved")
        self.assertRegex(
            result["baseline"]["metrics_fingerprint"],
            r"^[0-9a-f]{64}$",
        )
        self.assertNotEqual(
            result["baseline"]["metrics_fingerprint"],
            result["candidate"]["metrics_fingerprint"],
        )

    def test_promotion_requires_constitution_and_fitness(self):
        shadow = evaluate_shadow(
            stable_sha="3" * 40,
            candidate_sha="4" * 40,
            stable_metrics=metrics(0.90),
            candidate_metrics=metrics(0.95),
            constitution_candidate=constitution_candidate(),
        )
        contract = promotion_contract(shadow)
        self.assertTrue(contract["requires_human_or_authorized_promotion"])
        self.assertEqual(contract["execution"], "not-performed")
        self.assertRegex(contract["constitution_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertRegex(contract["fitness_fingerprint"], r"^[0-9a-f]{64}$")

        not_improved = evaluate_shadow(
            stable_sha="5" * 40,
            candidate_sha="6" * 40,
            stable_metrics=metrics(0.95),
            candidate_metrics=metrics(0.90),
            constitution_candidate=constitution_candidate(),
        )
        with self.assertRaisesRegex(FactoryLabError, "evidencia insuficiente"):
            promotion_contract(not_improved)

        invalid_candidate = constitution_candidate()
        invalid_candidate["changes"][0]["path"] = "constitution.principles"
        invalid_stable_metrics = metrics(0.90)
        invalid_candidate_metrics = metrics(0.95)
        with self.assertRaisesRegex(FactoryLabError, "viola Constitution"):
            evaluate_shadow(
                stable_sha="7" * 40,
                candidate_sha="8" * 40,
                stable_metrics=invalid_stable_metrics,
                candidate_metrics=invalid_candidate_metrics,
                constitution_candidate=invalid_candidate,
            )

    def test_workflow_uses_minimum_permissions_and_sha_pinned_actions(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertNotRegex(text, r"(?m)^\s*(issues|pull-requests|actions|deployments|packages):\s*write\s*$")
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("issues: write", text)

        uses = re.findall(r"(?m)^\s*-?\s*uses:\s*([^\s]+)\s*$", text)
        self.assertTrue(uses)
        for action in uses:
            if action.startswith("./"):
                continue
            self.assertRegex(action, r"^[^@\s]+@[0-9a-f]{40}$")

        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("GH_TOKEN", text)


if __name__ == "__main__":
    unittest.main()
