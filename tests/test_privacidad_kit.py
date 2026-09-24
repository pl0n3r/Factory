"""Regresiones del contrato de privacidad como código."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.privacidad_kit import (
    PLACEHOLDER_TOKEN,
    PrivacyError,
    generate_documents,
    load_rules,
    validate_data_map,
)


def data_map():
    return {
        "version": 1,
        "project": "pl0n3r/example",
        "phase": "construccion",
        "controller": {
            "name": PLACEHOLDER_TOKEN,
            "identifier": PLACEHOLDER_TOKEN,
            "address": PLACEHOLDER_TOKEN,
            "rights_email": PLACEHOLDER_TOKEN,
        },
        "treatments": [
            {
                "id": "account_email",
                "category": "contact",
                "fields": ["email"],
                "purpose": "account_access",
                "basis": "review_required",
                "retention": "account_lifecycle",
                "consent": "review_required",
                "providers": [],
            },
            {
                "id": "admin_totp",
                "category": "authentication",
                "fields": ["totp_secret"],
                "purpose": "admin_security",
                "basis": "review_required",
                "retention": "credential_lifecycle",
                "consent": "documented_explicit",
                "providers": [],
            },
        ],
    }


class PrivacyKitTests(unittest.TestCase):
    def test_valid_rules_and_data_map(self):
        rules = load_rules()
        validated = validate_data_map(data_map(), rules)
        self.assertEqual(validated["project"], "pl0n3r/example")
        self.assertEqual(
            [row["id"] for row in validated["treatments"]],
            ["account_email", "admin_totp"],
        )
        self.assertEqual(rules["categories"]["sensitive"]["maximum_retention"], "review_required")

    def test_invalid_or_personal_payload_fails_closed(self):
        rules = load_rules()
        item = data_map()
        item["customer_email"] = "sensitive@example.invalid"
        with self.assertRaises(PrivacyError) as caught:
            validate_data_map(item, rules)
        self.assertNotIn("sensitive@example.invalid", str(caught.exception))

        free_text = data_map()
        free_text["treatments"][0]["purpose"] = "Jane Doe customer account"
        with self.assertRaises(PrivacyError) as caught:
            validate_data_map(free_text, rules)
        self.assertNotIn("Jane Doe", str(caught.exception))

        sensitive = data_map()
        sensitive["treatments"][1]["consent"] = "review_required"
        with self.assertRaisesRegex(PrivacyError, "consentimiento explícito"):
            validate_data_map(sensitive, rules)

    def test_documents_are_deterministic(self):
        rules = load_rules()
        first = generate_documents(rules, data_map())
        second = generate_documents(deepcopy(rules), deepcopy(data_map()))
        self.assertEqual(first, second)
        self.assertEqual(
            set(first),
            {"politica-tratamiento.md", "registro-tratamientos.md", "retencion.md"},
        )
        self.assertIn("account_email", first["politica-tratamiento.md"])
        self.assertIn("admin_totp", first["registro-tratamientos.md"])
        self.assertIn("review_required", first["retencion.md"])

    def test_owner_placeholders_are_preserved(self):
        rules = load_rules()
        documents = generate_documents(rules, data_map())
        combined = "\n".join(documents.values())
        self.assertIn(PLACEHOLDER_TOKEN, combined)

        live = data_map()
        live["phase"] = "live"
        with self.assertRaisesRegex(PrivacyError, "go-live"):
            validate_data_map(live, rules)

        original = data_map()
        snapshot = json.dumps(original, sort_keys=True)
        generate_documents(rules, original)
        self.assertEqual(json.dumps(original, sort_keys=True), snapshot)


if __name__ == "__main__":
    unittest.main()
