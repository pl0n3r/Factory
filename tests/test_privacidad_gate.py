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

    def test_health_endpoint_is_not_a_sensitive_health_field(self):
        """Una ruta /health no representa por sí sola un dato personal de salud."""
        item = data_map()
        diff = """diff --git a/src/HealthController.php b/src/HealthController.php
+++ b/src/HealthController.php
+    $route = "/health";
"""
        report = evaluate_change(
            diff_text=diff,
            changed_files=["src/HealthController.php"],
            current_document=item,
            documents=docs(item),
        )
        self.assertEqual(report["personal_signals"], [])

    def test_explicit_health_field_remains_sensitive(self):
        """Claves, campos de objeto y propiedades health siguen siendo sensibles."""
        item = data_map()
        snippets = (
            '$payload = ["health" => $request->get("health")];',
            'const profile = { health: value };',
            'const value = record.health;',
            'const value = userProfile.health;',
            'const { health } = req.body;',
        )
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                diff = (
                    "diff --git a/src/Profile.php b/src/Profile.php\n"
                    "+++ b/src/Profile.php\n"
                    f"+{snippet}\n"
                )
                with self.assertRaisesRegex(PrivacyGateError, "health"):
                    evaluate_change(
                        diff_text=diff,
                        changed_files=["src/Profile.php"],
                        current_document=item,
                        documents=docs(item),
                    )

    def test_php_health_property_remains_sensitive(self):
        """Propiedades PHP normales y nullsafe health siguen siendo sensibles."""
        item = data_map()
        for snippet in ("$value = $record->health;", "$value = $record?->health;"):
            with self.subTest(snippet=snippet):
                diff = (
                    "diff --git a/src/Profile.php b/src/Profile.php\n"
                    "+++ b/src/Profile.php\n"
                    f"+{snippet}\n"
                )
                with self.assertRaisesRegex(PrivacyGateError, "health"):
                    evaluate_change(
                        diff_text=diff,
                        changed_files=["src/Profile.php"],
                        current_document=item,
                        documents=docs(item),
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

    def test_generated_new_document_drift_fails(self):
        item = data_map()
        generated = docs(item)
        generated["aviso-privacidad.md"] += "drift\n"
        with self.assertRaisesRegex(PrivacyGateError, "aviso-privacidad.md"):
            evaluate_change(
                diff_text="",
                changed_files=[],
                current_document=item,
                documents=generated,
            )

    def test_gate_requires_every_document_declared_by_rules(self):
        item = data_map()
        generated = docs(item)
        generated.pop("canal-derechos.md")
        with self.assertRaisesRegex(PrivacyGateError, "incompletos"):
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


    def test_unrelated_context_does_not_activate_ambiguous_field(self):
        """Contexto personal en otra expresión no convierte UI en dato personal."""
        item = data_map()
        diff = """diff --git a/src/ui.js b/src/ui.js
+++ b/src/ui.js
+const user = getUser(); const mode = "mobile";
+const { health } = theme;
"""
        report = evaluate_change(
            diff_text=diff,
            changed_files=["src/ui.js"],
            current_document=item,
            documents=docs(item),
        )
        self.assertEqual(report["personal_signals"], [])

    def test_google_fonts_is_not_google_drive(self):
        """Google Fonts no activa el proveedor Google Drive."""
        item = data_map()
        diff = """diff --git a/src/theme.js b/src/theme.js
+++ b/src/theme.js
+const fontCss = "https://fonts.googleapis.com/css2?family=Barlow";
"""
        report = evaluate_change(
            diff_text=diff,
            changed_files=["src/theme.js"],
            current_document=item,
            documents=docs(item),
        )
        self.assertEqual(report["provider_signals"], [])


    def test_google_youtube_api_is_not_google_drive(self):
        """El host compartido de Google APIs exige una ruta específica de Drive."""
        item = data_map()
        diff = """diff --git a/src/video.js b/src/video.js
+++ b/src/video.js
+const endpoint = "https://www.googleapis.com/youtube/v3/videos";
"""
        report = evaluate_change(
            diff_text=diff,
            changed_files=["src/video.js"],
            current_document=item,
            documents=docs(item),
        )
        self.assertEqual(report["provider_signals"], [])

    def test_google_drive_api_still_requires_declaration(self):
        """El endpoint de Drive continúa detectándose tras acotar el host."""
        item = data_map()
        generated = docs(item)
        diff = """diff --git a/src/storage.js b/src/storage.js
+++ b/src/storage.js
+const endpoint = "https://www.googleapis.com/drive/v3/files";
"""
        with self.assertRaisesRegex(PrivacyGateError, "google_drive"):
            evaluate_change(
                diff_text=diff,
                changed_files=["src/storage.js"],
                current_document=item,
                documents=generated,
            )


if __name__ == "__main__":
    unittest.main()
