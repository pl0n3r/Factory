from pathlib import Path
import copy
import hashlib
import json
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


def root_hash(value):
    payload = dict(value)
    payload.pop("fingerprint", None)
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
        contract = promotion_contract(
            shadow_result=shadow,
            stable_sha="3" * 40,
            candidate_sha="4" * 40,
            stable_metrics=metrics(0.90),
            candidate_metrics=metrics(0.95),
            constitution_candidate=constitution_candidate(),
        )
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
        not_improved_stable = metrics(0.95)
        not_improved_candidate = metrics(0.90)
        not_improved_constitution = constitution_candidate()
        with self.assertRaisesRegex(FactoryLabError, "evidencia insuficiente"):
            promotion_contract(
                shadow_result=not_improved,
                stable_sha="5" * 40,
                candidate_sha="6" * 40,
                stable_metrics=not_improved_stable,
                candidate_metrics=not_improved_candidate,
                constitution_candidate=not_improved_constitution,
            )

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

    def test_forged_shadow_result_cannot_emit_promotion_contract(self):
        forged = {
            "version": 1,
            "mode": "shadow",
            "mutation_allowed": False,
            "external_writes": [],
            "baseline": {
                "name": "stable",
                "sha": "9" * 40,
                "metrics_fingerprint": "a" * 64,
            },
            "candidate": {
                "sha": "8" * 40,
                "metrics_fingerprint": "b" * 64,
                "constitution_fingerprint": "c" * 64,
            },
            "fitness": {
                "version": 1,
                "dimensions": {},
                "protected_dimensions": [],
                "protected_regressions": [],
                "missing_dimensions": [],
                "confidence": {"comparable": 1, "total": 1, "ratio": 1.0},
                "claim": "improved",
                "can_claim_improvement": True,
                "fingerprint": "d" * 64,
            },
            "promotion": {
                "ready": True,
                "requires": [
                    "constitution:valid",
                    "fitness:improved",
                    "fitness:no-protected-regressions",
                    "fitness:no-missing-dimensions",
                ],
                "execution": "not-performed",
            },
        }
        forged["fingerprint"] = root_hash(forged)
        stable = metrics(0.90)
        candidate = metrics(0.95)
        constitution = constitution_candidate()

        with self.assertRaisesRegex(FactoryLabError, "Constitution no coincide"):
            promotion_contract(
                shadow_result=forged,
                stable_sha="9" * 40,
                candidate_sha="8" * 40,
                stable_metrics=stable,
                candidate_metrics=candidate,
                constitution_candidate=constitution,
            )

    def test_recomputed_root_hash_does_not_replace_canonical_evidence(self):
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
        tampered = copy.deepcopy(shadow)
        tampered["fitness"]["claim"] = "equal"
        tampered["fitness"]["can_claim_improvement"] = False
        tampered["promotion"]["ready"] = True
        tampered["fitness"]["fingerprint"] = "e" * 64
        tampered["fingerprint"] = root_hash(tampered)

        with self.assertRaisesRegex(FactoryLabError, "Fitness no coincide"):
            promotion_contract(
                shadow_result=tampered,
                stable_sha="a" * 40,
                candidate_sha="b" * 40,
                stable_metrics=stable,
                candidate_metrics=candidate,
                constitution_candidate=constitution,
            )

        sha_tampered = copy.deepcopy(shadow)
        sha_tampered["candidate"]["sha"] = "1" * 40
        sha_tampered["fingerprint"] = root_hash(sha_tampered)
        with self.assertRaisesRegex(FactoryLabError, "evaluación canónica"):
            promotion_contract(
                shadow_result=sha_tampered,
                stable_sha="a" * 40,
                candidate_sha="b" * 40,
                stable_metrics=stable,
                candidate_metrics=candidate,
                constitution_candidate=constitution,
            )

    def test_canonical_shadow_evidence_remains_promotable(self):
        stable = metrics(0.90)
        candidate = metrics(0.95)
        constitution = constitution_candidate()
        shadow = evaluate_shadow(
            stable_sha="c" * 40,
            candidate_sha="d" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
        )

        contract = promotion_contract(
            shadow_result=shadow,
            stable_sha="c" * 40,
            candidate_sha="d" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
        )
        self.assertTrue(contract["requires_human_or_authorized_promotion"])
        self.assertEqual(contract["execution"], "not-performed")
        self.assertEqual(contract["shadow_fingerprint"], shadow["fingerprint"])

    def test_hardening_preserves_shadow_minimum_privilege(self):
        stable = metrics(0.90)
        candidate = metrics(0.95)
        constitution = constitution_candidate()
        shadow = evaluate_shadow(
            stable_sha="e" * 40,
            candidate_sha="f" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
        )
        contract = promotion_contract(
            shadow_result=shadow,
            stable_sha="e" * 40,
            candidate_sha="f" * 40,
            stable_metrics=stable,
            candidate_metrics=candidate,
            constitution_candidate=constitution,
        )

        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual(shadow["external_writes"], [])
        self.assertEqual(shadow["promotion"]["execution"], "not-performed")
        self.assertEqual(contract["execution"], "not-performed")

        # F1A elimina el disparador opcional, nunca la garantía shadow.
        self.assertFalse(WORKFLOW.exists(), "F1A: Evolution Lab no debe dispararse")
        module = (REPO_ROOT / "lab" / "factory_lab.py").read_text(encoding="utf-8")
        self.assertNotIn("secrets.", module)
        self.assertNotIn("GH_TOKEN", module)

    def test_lab_modules_compile_without_optional_workflow(self):
        """El reemplazo de un trigger no elimina los tests ni la sintaxis del Lab."""
        self.assertFalse(WORKFLOW.exists(), "El YAML opcional fue retirado por F1A")
        modules = sorted((REPO_ROOT / "lab").glob("*.py"))
        self.assertTrue(modules, "La implementación offline del Lab debe permanecer")
        for module in modules:
            with self.subTest(module=module.name):
                compile(module.read_text(encoding="utf-8"), str(module), "exec")
        for suite in ("test_factory_lab_contract.py", "test_experiment_evidence.py"):
            self.assertTrue((REPO_ROOT / "tests" / suite).is_file())


if __name__ == "__main__":
    unittest.main()
