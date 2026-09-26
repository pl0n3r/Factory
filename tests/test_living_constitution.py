import json
import unittest
from pathlib import Path

from evolution.constitution import (
    ConstitutionError,
    EXPECTED_INVARIANT_SOURCES,
    MAX_JSON_VALUE_BYTES,
    PROTECTED_INVARIANTS,
    load_constitution,
    validate_candidate,
    validate_constitution,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_candidate(path="evolution_state.heuristics.review_threshold"):
    return {
        "version": 1,
        "changes": [
            {
                "path": path,
                "operation": "replace",
                "value": 3,
            }
        ],
        "evidence": ["factory#144:acceptance"],
        "rollback": {
            "reversible": True,
            "strategy": "revert",
        },
    }


class LivingConstitutionTests(unittest.TestCase):
    def test_constitution_separates_immutable_authority_from_evolvable_state(self):
        contract = load_constitution()

        self.assertEqual(contract["version"], 1)
        self.assertEqual(
            contract["stable_authority"]["autonomous_mutation"],
            "forbidden",
        )
        self.assertEqual(
            contract["stable_authority"]["human_gate_registry"],
            "seguridad/puertas-humanas.json",
        )
        self.assertEqual(
            set(contract["protected_invariants"]),
            set(PROTECTED_INVARIANTS),
        )

        for name in PROTECTED_INVARIANTS:
            rule = contract["protected_invariants"][name]
            self.assertEqual(rule["policy"], "must_not_weaken")
            self.assertEqual(rule["autonomous_mutation"], "forbidden")
            self.assertEqual(rule["source"], EXPECTED_INVARIANT_SOURCES[name])

        for source in contract["stable_authority"]["sources"]:
            self.assertTrue((ROOT / source).is_file(), source)

        prefixes = contract["candidate_policy"]["allowed_prefixes"]
        self.assertTrue(prefixes)
        self.assertTrue(
            all(prefix.startswith("evolution_state.") for prefix in prefixes)
        )
        self.assertFalse(
            any(
                prefix.startswith("stable_authority.")
                or prefix.startswith("protected_invariants.")
                for prefix in prefixes
            )
        )

    def test_candidate_cannot_weaken_protected_invariants(self):
        contract = load_constitution()
        digest = validate_candidate(valid_candidate(), contract)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

        forbidden_paths = [
            "stable_authority.autonomous_mutation",
            "candidate_policy.max_changes",
            *[
                f"protected_invariants.{name}.policy"
                for name in PROTECTED_INVARIANTS
            ],
        ]
        for path in forbidden_paths:
            with self.subTest(path=path):
                candidate = valid_candidate(path)
                with self.assertRaisesRegex(
                    ConstitutionError,
                    "autoridad o invariantes protegidos",
                ):
                    validate_candidate(candidate, contract)

        irreversible = valid_candidate()
        irreversible["rollback"]["reversible"] = False
        with self.assertRaisesRegex(ConstitutionError, "debe ser reversible"):
            validate_candidate(irreversible, contract)

    def test_constitution_is_versioned_and_deterministic(self):
        contract = load_constitution()
        self.assertEqual(contract["version"], 1)
        self.assertEqual(validate_constitution(contract), contract)

        first = valid_candidate()
        second = {
            "rollback": {
                "strategy": "revert",
                "reversible": True,
            },
            "evidence": ["factory#144:acceptance"],
            "changes": [
                {
                    "value": 3,
                    "operation": "replace",
                    "path": "evolution_state.heuristics.review_threshold",
                }
            ],
            "version": 1,
        }
        self.assertEqual(
            validate_candidate(first, contract),
            validate_candidate(second, contract),
        )

        with self.assertRaises(ConstitutionError):
            validate_candidate(first, {})

        wrong_source = json.loads(json.dumps(contract))
        wrong_source["protected_invariants"]["security"]["source"] = (
            "docs/resiliencia-fabrica.md"
        )
        with self.assertRaisesRegex(ConstitutionError, "fuente no protegida"):
            validate_constitution(wrong_source)

        invalid_rollback = valid_candidate()
        invalid_rollback["rollback"]["strategy"] = []
        with self.assertRaisesRegex(
            ConstitutionError,
            "rollback.strategy inválida",
        ):
            validate_candidate(invalid_rollback, contract)

    def test_supplied_constitution_cannot_raise_v1_change_limit(self):
        contract = load_constitution()
        raised_limit = json.loads(json.dumps(contract))
        raised_limit["candidate_policy"]["max_changes"] = 33
        candidate = valid_candidate()
        candidate["changes"] *= 33

        with self.assertRaisesRegex(ConstitutionError, "max_changes inválido"):
            validate_candidate(candidate, raised_limit)

    def test_candidate_values_are_strict_json_before_fingerprinting(self):
        contract = load_constitution()

        valid_object = valid_candidate()
        valid_object["changes"][0]["value"] = {"1": "x"}
        self.assertRegex(validate_candidate(valid_object, contract), r"^[0-9a-f]{64}$")

        invalid_values = [
            {1: "x"},
            {"nested": {1: "x"}},
            float("nan"),
            ("tuple", "is-not-json"),
        ]
        for value in invalid_values:
            with self.subTest(value=repr(value)):
                candidate = valid_candidate()
                candidate["changes"][0]["value"] = value
                with self.assertRaisesRegex(
                    ConstitutionError,
                    "candidate.change.value",
                ):
                    validate_candidate(candidate, contract)

    def test_candidate_json_validation_rejects_cycles_and_excessive_depth(self):
        contract = load_constitution()

        cyclic_list = []
        cyclic_list.append(cyclic_list)
        cyclic_dict = {}
        cyclic_dict["self"] = cyclic_dict

        deep_value = 0
        for _ in range(34):
            deep_value = [deep_value]

        invalid_values = [cyclic_list, cyclic_dict, deep_value]
        for value in invalid_values:
            with self.subTest(kind=type(value).__name__):
                candidate = valid_candidate()
                candidate["changes"][0]["value"] = value
                with self.assertRaisesRegex(
                    ConstitutionError,
                    "candidate.change.value",
                ):
                    validate_candidate(candidate, contract)

    def test_candidate_json_validation_limits_total_traversal_work(self):
        contract = load_constitution()

        shared = [0]
        for _ in range(14):
            shared = [shared, shared]

        shared_candidate = valid_candidate()
        shared_candidate["changes"][0]["value"] = shared
        with self.assertRaisesRegex(ConstitutionError, "presupuesto de nodos"):
            validate_candidate(shared_candidate, contract)

        oversized_candidate = valid_candidate()
        oversized_candidate["changes"][0]["value"] = "x" * (MAX_JSON_VALUE_BYTES + 1)
        with self.assertRaisesRegex(ConstitutionError, "presupuesto de bytes"):
            validate_candidate(oversized_candidate, contract)

    def test_documented_lifecycle_matches_machine_contract(self):
        contract = load_constitution()
        documentation = (
            ROOT / "docs" / "factory-living-software.md"
        ).read_text(encoding="utf-8")

        lifecycle = " → ".join(contract["lifecycle"])
        self.assertIn(f"constitution.version = {contract['version']}", documentation)
        self.assertIn(
            "human_gate_registry = "
            + contract["stable_authority"]["human_gate_registry"],
            documentation,
        )
        self.assertIn(lifecycle, documentation)

        for name in contract["protected_invariants"]:
            self.assertIn(f"- {name}", documentation)
        for prefix in contract["candidate_policy"]["allowed_prefixes"]:
            self.assertIn(f"- {prefix}", documentation)


if __name__ == "__main__":
    unittest.main()
