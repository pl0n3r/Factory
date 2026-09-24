"""Regresiones del gate reusable de privacidad."""
from copy import deepcopy
from pathlib import Path
import unittest

from scripts.privacidad_gate import PrivacyGateError, evaluate_change
from scripts.privacidad_kit import PLACEHOLDER_TOKEN, generate_documents, load_rules


ROOT = Path(__file__).resolve().parents[1]


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
            }
        ],
    }


def docs(item):
    rules = load_rules()
    return generate_documents(rules, item)


class PrivacyGateTests(unittest.TestCase):
    def test_personal_signal_requires_data_map_change(self):
        diff = """diff --git a/src/User.php b/src/User.php
+++ b/src/User.php
+    $phone = $request->get('phone');
"""
        with self.assertRaisesRegex(PrivacyGateError, "phone"):
            evaluate_change(
                diff_text=diff,
                changed_files=["src/User.php"],
                current_document=data_map(),
                documents=docs(data_map()),
            )

    def test_new_provider_requires_declaration(self):
        diff = """diff --git a/src/Telemetry.js b/src/Telemetry.js
+++ b/src/Telemetry.js
+const dsn = "https://example.sentry.io/123";
"""
        with self.assertRaisesRegex(PrivacyGateError, "sentry"):
            evaluate_change(
                diff_text=diff,
                changed_files=["src/Telemetry.js"],
                current_document=data_map(),
                documents=docs(data_map()),
            )

    def test_generated_documents_drift_fails(self):
        item = data_map()
        generated = docs(item)
        generated["retencion.md"] += "drift\n"
        with self.assertRaisesRegex(PrivacyGateError, "retencion.md"):
            evaluate_change(
                diff_text="",
                changed_files=[],
                current_document=item,
                documents=generated,
            )

    def test_material_change_requires_legal_gate(self):
        previous = data_map()
        current = deepcopy(previous)
        current["treatments"][0]["purpose"] = "marketing_contact"
        report = evaluate_change(
            diff_text="",
            changed_files=["datos.yml", "docs/privacidad/politica-tratamiento.md"],
            previous_document=previous,
            current_document=current,
            documents=docs(current),
        )
        self.assertTrue(report["legal_gate_required"])
        self.assertEqual(report["material_reasons"], ["account_email:purpose"])
        self.assertEqual(report["status"], "documented_not_legally_approved")

    def test_declared_signal_passes_without_payload_echo(self):
        item = data_map()
        diff = """diff --git a/src/User.php b/src/User.php
+++ b/src/User.php
+$email = "do-not-log@example.invalid";
"""
        report = evaluate_change(
            diff_text=diff,
            changed_files=["src/User.php"],
            current_document=item,
            documents=docs(item),
        )
        self.assertEqual(report["personal_signals"], ["email"])
        self.assertNotIn("do-not-log", str(report))

    def test_workflow_uses_pinned_checkout_and_read_only_permissions(self):
        content = (ROOT / ".github" / "workflows" / "privacidad.yml").read_text(
            encoding="utf-8"
        )
        self.assertGreaterEqual(
            content.count("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"),
            2,
        )
        self.assertIn("permissions:\n  contents: read", content)
        self.assertNotIn("issues: write", content)
        self.assertIn("persist-credentials: false", content)
        self.assertIn("timeout-minutes: 8", content)


if __name__ == "__main__":
    unittest.main()
