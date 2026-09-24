#!/usr/bin/env python3
"""Regresiones del readiness check de la raíz de confianza v1."""
import copy
import unittest

from scripts.verificar_ruleset_v1 import (
    RulesetValidationError,
    validate_rulesets,
)


def protected_ruleset():
    return {
        "id": 83,
        "name": "factory-v1-trust-root",
        "target": "tag",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/tags/v1"],
                "exclude": [],
            }
        },
        "rules": [
            {"type": "creation"},
            {"type": "update", "parameters": {"update_allows_fetch_and_merge": False}},
            {"type": "deletion"},
        ],
    }


class V1RulesetTests(unittest.TestCase):
    def test_accepts_active_v1_tag_ruleset(self):
        self.assertEqual(
            validate_rulesets([protected_ruleset()]),
            {"status": "protected", "ruleset_id": 83},
        )

    def test_rejects_unprotected_variants(self):
        cases = {}

        cases["empty"] = []

        wrong_target = protected_ruleset()
        wrong_target["target"] = "branch"
        cases["wrong-target"] = [wrong_target]

        for enforcement in ("disabled", "evaluate"):
            item = protected_ruleset()
            item["enforcement"] = enforcement
            cases[f"enforcement-{enforcement}"] = [item]

        missing_ref = protected_ruleset()
        missing_ref["conditions"]["ref_name"]["include"] = ["refs/tags/v2"]
        cases["v1-absent"] = [missing_ref]

        excluded_ref = protected_ruleset()
        excluded_ref["conditions"]["ref_name"]["exclude"] = ["refs/tags/v1"]
        cases["v1-excluded"] = [excluded_ref]

        for rule_type in ("creation", "update", "deletion"):
            item = protected_ruleset()
            item["rules"] = [
                rule for rule in item["rules"] if rule["type"] != rule_type
            ]
            cases[f"missing-{rule_type}"] = [item]

        for name, payload in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(RulesetValidationError):
                    validate_rulesets(payload)

        malformed = copy.deepcopy(protected_ruleset())
        malformed["conditions"]["ref_name"]["include"] = "refs/tags/v1"
        with self.assertRaises(RulesetValidationError):
            validate_rulesets([malformed])


if __name__ == "__main__":
    unittest.main()
