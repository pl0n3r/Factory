"""Regresiones de la auditoría periódica de privacidad."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.auditar_privacidad import (
    AUDIT_MARKER,
    MATERIAL_MARKER,
    PrivacyAuditError,
    _git_show,
    audit_sources,
    build_legal_gate_body,
    collect_sources,
    evaluate_repository,
    main,
)
from scripts.privacidad_kit import PLACEHOLDER_TOKEN
from seguridad.puertas_humanas import classify_body


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


def d063_data_map():
    current = data_map()
    current["d063_attestation"] = {
        "nothing_live": True,
        "no_real_customer_data": True,
    }
    return current


def live_data_map():
    current = d063_data_map()
    current["phase"] = "live"
    current["controller"] = {
        "name": "Example Controller",
        "identifier": "example-controller",
        "address": "Example Address",
        "rights_email": "privacy@example.invalid",
    }
    return current


class PrivacyAuditTests(unittest.TestCase):
    def test_undocumented_signal_is_reported_without_values(self):
        current = data_map()
        report = audit_sources(
            sources={
                "src/User.php": "$email = $user->email;\n$phone = '3001234567';\n"
            },
            current_document=current,
            previous_document=deepcopy(current),
        )
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(
            report["undocumented_fields"],
            [{"signal": "phone", "paths": ["src/User.php"]}],
        )
        rendered = str(report)
        self.assertNotIn("3001234567", rendered)
        self.assertIn(AUDIT_MARKER, report["audit_issue_body"])

    def test_health_endpoint_does_not_create_sensitive_finding(self):
        """La auditoría no confunde un endpoint /health con datos de salud."""
        current = data_map()
        report = audit_sources(
            sources={"src/HealthController.php": '$route = "/health";\n'},
            current_document=current,
            previous_document=deepcopy(current),
        )
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["undocumented_fields"], [])

    def test_explicit_health_field_is_reported_as_sensitive(self):
        """La auditoría reporta todas las formas explícitas soportadas de health."""
        current = data_map()
        snippets = (
            '$payload = ["health" => $value];\n',
            'const profile = { health: value };\n',
            'const value = record.health;\n',
            'const value = userProfile.health;\n',
            'const { health } = req.body;\n',
        )
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                report = audit_sources(
                    sources={"src/Profile.php": snippet},
                    current_document=current,
                    previous_document=deepcopy(current),
                )
                self.assertEqual(report["status"], "review_required")
                self.assertEqual(
                    report["undocumented_fields"],
                    [{"signal": "health", "paths": ["src/Profile.php"]}],
                )

    def test_php_health_property_is_reported_as_sensitive(self):
        """La auditoría reporta acceso PHP normal y nullsafe a health."""
        current = data_map()
        for snippet in ("$value = $record->health;\n", "$value = $record?->health;\n"):
            with self.subTest(snippet=snippet):
                report = audit_sources(
                    sources={"src/Profile.php": snippet},
                    current_document=current,
                    previous_document=deepcopy(current),
                )
                self.assertEqual(report["status"], "review_required")
                self.assertEqual(
                    report["undocumented_fields"],
                    [{"signal": "health", "paths": ["src/Profile.php"]}],
                )

    def test_report_is_deterministic_and_idempotent(self):
        current = data_map()
        kwargs = {
            "sources": {"src/User.php": "$email = $user->email;\n"},
            "current_document": current,
            "previous_document": deepcopy(current),
        }
        first = audit_sources(**kwargs)
        second = audit_sources(**kwargs)
        self.assertEqual(first, second)

    def test_material_change_builds_legal_gate(self):
        previous = d063_data_map()
        current = deepcopy(previous)
        current["treatments"][0]["purpose"] = "marketing_contact"
        report = audit_sources(
            sources={"src/User.php": "$email = $user->email;\n"},
            current_document=current,
            previous_document=previous,
        )
        self.assertTrue(report["legal_gate_required"])
        self.assertEqual(report["material_reasons"], ["account_email:purpose"])
        self.assertIn(MATERIAL_MARKER, report["legal_gate_body"])
        self.assertEqual(classify_body(report["legal_gate_body"])["category"], "legal")
        self.assertTrue(report["d063_applies"])
        self.assertIn('"recommendation":"B"', report["legal_gate_body"])
        self.assertIn('"safe_default":"B"', report["legal_gate_body"])
        self.assertIn("no bloquea el trabajo en construcción", report["legal_gate_body"])

        direct = build_legal_gate_body(
            current["project"],
            report["material_reasons"],
            d063_applies=True,
        )
        self.assertEqual(direct, report["legal_gate_body"])

    def test_d063_complete_attestation_enables_informational_gate(self):
        previous = d063_data_map()
        current = deepcopy(previous)
        current["treatments"][0]["purpose"] = "marketing_contact"
        report = audit_sources(
            sources={"src/User.php": "$email = $user->email;\n"},
            current_document=current,
            previous_document=previous,
        )
        self.assertTrue(report["d063_applies"])
        self.assertIn('"recommendation":"B"', report["legal_gate_body"])
        self.assertIn('"safe_default":"B"', report["legal_gate_body"])
        self.assertIn("puerta es informativa", report["legal_gate_body"])


    def test_d063_missing_attestation_fails_closed(self):
        previous = data_map()
        current = deepcopy(previous)
        current["treatments"][0]["purpose"] = "marketing_contact"
        report = audit_sources(
            sources={"src/User.php": "$email = $user->email;\n"},
            current_document=current,
            previous_document=previous,
        )
        self.assertFalse(report["d063_applies"])
        self.assertIn('"recommendation":"A"', report["legal_gate_body"])
        self.assertIn('"safe_default":"A"', report["legal_gate_body"])
        self.assertIn("puerta es bloqueante", report["legal_gate_body"])

    def test_d063_false_or_unknown_attestation_fails_closed(self):
        cases = (
            ("nothing_live", False),
            ("nothing_live", None),
            ("no_real_customer_data", False),
            ("no_real_customer_data", None),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                previous = d063_data_map()
                previous["d063_attestation"][field] = value
                current = deepcopy(previous)
                current["treatments"][0]["purpose"] = "marketing_contact"
                report = audit_sources(
                    sources={"src/User.php": "$email = $user->email;\n"},
                    current_document=current,
                    previous_document=previous,
                )
                self.assertFalse(report["d063_applies"])
                self.assertIn('"recommendation":"A"', report["legal_gate_body"])
                self.assertIn('"safe_default":"A"', report["legal_gate_body"])


    def test_d063_invalid_type_fails_closed_without_aborting(self):
        previous = d063_data_map()
        previous["d063_attestation"]["nothing_live"] = "unknown"
        current = deepcopy(previous)
        current["treatments"][0]["purpose"] = "marketing_contact"
        report = audit_sources(
            sources={"src/User.php": "$email = $user->email;\n"},
            current_document=current,
            previous_document=previous,
        )
        self.assertFalse(report["d063_applies"])
        self.assertIn('"recommendation":"A"', report["legal_gate_body"])
        self.assertIn('"safe_default":"A"', report["legal_gate_body"])

    def test_d063_invalid_fields_do_not_leak_into_report(self):
        previous = d063_data_map()
        previous["d063_attestation"] = {
            "nothing_live": True,
            "no_real_customer_data": True,
            "free_text": "discarded",
        }
        current = deepcopy(previous)
        current["treatments"][0]["purpose"] = "marketing_contact"
        report = audit_sources(
            sources={"src/User.php": "$email = $user->email;\n"},
            current_document=current,
            previous_document=previous,
        )
        self.assertFalse(report["d063_applies"])
        self.assertIn('"recommendation":"A"', report["legal_gate_body"])
        self.assertNotIn("discarded", str(report))

    def test_evaluate_repository_uses_d063_fail_closed_mode(self):
        current = d063_data_map()
        current["d063_attestation"]["nothing_live"] = "unknown"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "datos.yml").write_text(
                json.dumps(current),
                encoding="utf-8",
            )
            report = evaluate_repository(root)
        self.assertFalse(report["d063_applies"])
        self.assertTrue(report["legal_gate_required"])
        self.assertIn('"recommendation":"A"', report["legal_gate_body"])

    def test_live_gate_never_recommends_construction_default(self):
        previous = live_data_map()
        current = deepcopy(previous)
        current["treatments"][0]["purpose"] = "marketing_contact"
        report = audit_sources(
            sources={"src/User.php": "$email = $user->email;\n"},
            current_document=current,
            previous_document=previous,
        )
        self.assertFalse(report["d063_applies"])
        self.assertNotIn('"recommendation":"B"', report["legal_gate_body"])
        self.assertNotIn('"safe_default":"B"', report["legal_gate_body"])
        self.assertIn('"recommendation":"A"', report["legal_gate_body"])
        self.assertIn('"safe_default":"A"', report["legal_gate_body"])
        self.assertIn("puerta es bloqueante", report["legal_gate_body"])

    def test_workflow_removes_blocked_state_for_informational_gate(self):
        content = (
            ROOT / ".github" / "workflows" / "auditoria-privacidad.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "d063_applies=\"$(jq -r '.d063_applies' /tmp/privacy-audit.json)\"",
            content,
        )
        self.assertIn(
            'remove_label_if_present "$legal_issue" "$STATE_BLOCKED"',
            content,
        )
        self.assertIn(
            'remove_label_if_present "$legal_issue" "$DECISION_OWNER"',
            content,
        )
        self.assertIn('remove_owner_if_assigned "$legal_issue"', content)
        self.assertIn('--add-label "$STATE_AVAILABLE"', content)

    def test_workflow_keeps_blocked_state_outside_d063(self):
        content = (
            ROOT / ".github" / "workflows" / "auditoria-privacidad.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('if [[ "$d063_applies" == "true" ]]', content)
        self.assertIn('--add-assignee "$OWNER"', content)
        self.assertIn('--add-label "$STATE_BLOCKED"', content)
        self.assertIn('--add-label "$DECISION_OWNER"', content)
        self.assertIn('--add-label "$PRIORITY_CRITICAL"', content)

    def test_clean_audit_has_no_spurious_work(self):
        current = data_map()
        report = audit_sources(
            sources={"src/User.php": "$email = $user->email;\n"},
            current_document=current,
            previous_document=deepcopy(current),
        )
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["undocumented_fields"], [])
        self.assertEqual(report["undocumented_providers"], [])
        self.assertFalse(report["legal_gate_required"])
        self.assertEqual(report["legal_gate_body"], "")

    def test_collect_sources_rejects_noncanonical_path_without_echo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sensitive_name = "Jane Doe email.php"
            (root / sensitive_name).write_text("<?php $email = 'x';", encoding="utf-8")
            with self.assertRaises(PrivacyAuditError) as caught:
                collect_sources(root)
            self.assertNotIn("Jane Doe", str(caught.exception))

    def test_nextjs_route_is_audited_without_leaking_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route = root / "src" / "app" / "[locale]" / "(panel)" / "admin"
            route.mkdir(parents=True)
            source = route / "page.tsx"
            source.write_text(
                'const phone = "3001234567";\n',
                encoding="utf-8",
            )
            current = data_map()
            report = audit_sources(
                sources=collect_sources(root),
                current_document=current,
                previous_document=deepcopy(current),
            )
            expected_path = "src/app/[locale]/(panel)/admin/page.tsx"
            self.assertEqual(
                report["undocumented_fields"],
                [{"signal": "phone", "paths": [expected_path]}],
            )
            self.assertIn(expected_path, report["audit_issue_body"])
            self.assertNotIn("3001234567", str(report))

    def test_collect_sources_rejects_symlink_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "hidden.php").write_text(
                "<?php $email = 'secret@example.invalid';",
                encoding="utf-8",
            )
            (root / "linked").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(
                PrivacyAuditError,
                "directorio simbólico no auditable",
            ):
                collect_sources(root)

    def test_git_history_failure_does_not_look_like_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                PrivacyAuditError,
                "referencia histórica no verificable",
            ):
                _git_show(Path(tmp), "a" * 40)

    def test_programming_errors_are_not_swallowed_by_cli(self):
        with (
            patch(
                "scripts.auditar_privacidad.evaluate_repository",
                side_effect=TypeError("programming bug"),
            ),
            patch("sys.argv", ["auditar_privacidad.py"]),
        ):
            with self.assertRaisesRegex(TypeError, "programming bug"):
                main()

    def test_workflow_is_pinned_and_scoped(self):
        content = (
            ROOT / ".github" / "workflows" / "auditoria-privacidad.yml"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(
            content.count("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"),
            2,
        )
        self.assertIn("contents: read", content)
        self.assertIn("issues: write", content)
        self.assertNotIn("contents: write", content)
        self.assertIn("timeout-minutes: 10", content)
        self.assertIn("factory-privacy-material", content)

    def test_ambiguous_runtime_terms_do_not_create_personal_findings(self):
        """DOM, UI, healthchecks, media y schema.org no son datos por léxico."""
        current = data_map()
        report = audit_sources(
            sources={
                "src/runtime.js": (
                    "const root = document.querySelector('#app');\n"
                    "const origin = location.origin;\n"
                    'const user = getUser(); const mode = "mobile";\n'
                    'const { health } = theme;\n'
                    "const status = data.health?.status || 'unknown';\n"
                ),
                "src/seo.php": (
                    "<?php\n"
                    "$schema['location'] = ['@type' => 'Place'];\n"
                    "$schema['location']['address'] = ['@type' => 'PostalAddress'];\n"
                ),
                "api/index.php": (
                    "$type = $mime === 'application/pdf' ? 'document' : 'image';"
                    + (" " * 128)
                    + "$title = $_POST['title'];\n"
                ),
                "database/schema.sql": (
                    "type ENUM('image','video','audio','document') NOT NULL,\n"
                ),
            },
            current_document=current,
            previous_document=deepcopy(current),
        )
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["undocumented_fields"], [])
        self.assertEqual(report["undocumented_providers"], [])

    def test_ambiguous_personal_field_near_request_remains_detected(self):
        """Un campo ambiguo ligado directamente a un request sigue siendo auditable."""
        current = data_map()
        report = audit_sources(
            sources={"src/User.php": "$document = $_POST['document'];\n"},
            current_document=current,
            previous_document=deepcopy(current),
        )
        self.assertEqual(
            report["undocumented_fields"],
            [{"signal": "document", "paths": ["src/User.php"]}],
        )

    def test_real_ip_address_signal_remains_detected(self):
        """Una columna real ip_address sigue siendo evidencia auditable."""
        current = data_map()
        report = audit_sources(
            sources={
                "database/migration.sql": (
                    "CREATE TABLE activity_log (\n"
                    "  ip_address VARCHAR(45) NULL\n"
                    ");\n"
                )
            },
            current_document=current,
            previous_document=deepcopy(current),
        )
        self.assertEqual(
            report["undocumented_fields"],
            [{"signal": "ip_address", "paths": ["database/migration.sql"]}],
        )

    def test_brvtal_style_sources_report_only_real_findings(self):
        """La mezcla observada en BRVTAL conserva solo la señal real."""
        current = data_map()
        report = audit_sources(
            sources={
                "config/public_assets.php": (
                    '$mobilePreload = \'<link data-lcp="mobile">\';\n'
                    '$font = "https://fonts.googleapis.com/css2?family=Barlow";\n'
                ),
                "config/public_seo.php": (
                    "$schema['location'] = ['@type' => 'Place'];\n"
                    "$schema['location']['address'] = ['@type' => 'PostalAddress'];\n"
                ),
                "api/route.php": (
                    "$resources = ['health', 'auth', 'public'];\n"
                ),
                "discadmin/system-status-v2.js": (
                    "const status = data.health?.status || 'unknown';\n"
                ),
                "database/v4-cms-migration.sql": (
                    "ip_address VARCHAR(45) NULL,\n"
                ),
            },
            current_document=current,
            previous_document=deepcopy(current),
        )
        self.assertEqual(
            report["undocumented_fields"],
            [{"signal": "ip_address", "paths": ["database/v4-cms-migration.sql"]}],
        )
        self.assertEqual(report["undocumented_providers"], [])

if __name__ == "__main__":
    unittest.main()
