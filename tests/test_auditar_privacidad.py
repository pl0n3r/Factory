"""Regresiones de la auditoría periódica de privacidad."""
from copy import deepcopy
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
        previous = data_map()
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

        direct = build_legal_gate_body(current["project"], report["material_reasons"])
        self.assertEqual(direct, report["legal_gate_body"])

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


if __name__ == "__main__":
    unittest.main()
