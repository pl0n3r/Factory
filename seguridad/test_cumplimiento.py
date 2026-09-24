"""Casos mínimos y adversariales de trazabilidad jurídica y licencias."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import shutil
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

import seguridad.cumplimiento as cumplimiento
from seguridad.cumplimiento import (
    ComplianceError, inspect_composer, inspect_npm, inspect_npm_snapshot,
    validate_inventory, validate_privacy, main,
)

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
SNAPSHOT_ROOT = Path(__file__).resolve().parent / "evidencia" / "brvtal-npm"


def record():
    return {
        "version": 1,
        "project": "pl0n3r/GrindFlow",
        "scope": "web_frontend",
        "purpose": "account_management",
        "data_categories": ["account_identifier", "usage_events"],
        "consent_or_exception": "consent_documented",
        "evidence": {
            key: f"audit:{key}-v1" for key in (
                "privacy_policy", "terms", "processing_register", "rights_channel",
                "retention_schedule", "vendor_review", "legal_review"
            )
        },
        "reviewed_at": "2026-09-23T10:00:00Z",
    }


class PrivacyTests(unittest.TestCase):
    def test_valid_record(self):
        self.assertEqual(validate_privacy(record(), now=NOW), "pl0n3r/GrindFlow")

    def test_all_three_products_supported(self):
        for project in ("pl0n3r/Condor", "pl0n3r/GrindFlow", "pl0n3r/brvtal"):
            item = record()
            item["project"] = project
            self.assertEqual(validate_privacy(item, now=NOW), project)

    def test_invalid_project_type_fails_closed(self):
        item = record()
        item["project"] = ["pl0n3r/GrindFlow"]
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_missing_legal_review_fails(self):
        item = record()
        del item["evidence"]["legal_review"]
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_extra_personal_information_field_fails_without_leak(self):
        item = record()
        item["customer_email"] = "sensitive@example.invalid"
        with self.assertRaises(ComplianceError) as caught:
            validate_privacy(item, now=NOW)
        self.assertNotIn("sensitive@example.invalid", str(caught.exception))

    def test_uncontrolled_free_text_fails(self):
        item = record()
        item["purpose"] = "My client Jane Doe"
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_stale_review_fails(self):
        item = record()
        item["reviewed_at"] = "2020-01-01T00:00:00Z"
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_future_review_fails(self):
        item = record()
        item["reviewed_at"] = "2027-01-01T00:00:00Z"
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_boolean_version_fails(self):
        item = record()
        item["version"] = True
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_none_category_with_personal_data_fails(self):
        item = record()
        item["data_categories"] = ["none", "account_identifier"]
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_consent_basis_inconsistent_with_no_data_fails(self):
        item = record()
        item["data_categories"] = ["none"]
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_duplicate_categories_fails(self):
        item = record()
        item["data_categories"] = ["usage_events", "usage_events"]
        with self.assertRaises(ComplianceError):
            validate_privacy(item, now=NOW)

    def test_copy_not_mutated(self):
        item = record()
        original = deepcopy(item)
        validate_privacy(item, now=NOW)
        self.assertEqual(item, original)


class LicenseTests(unittest.TestCase):
    def test_composer_includes_dev_dependencies(self):
        lock = {"packages": [{"name": "vendor/a", "version": "v1.0.0", "license": ["MIT"]}],
                "packages-dev": [{"name": "vendor/b", "version": "2.0", "license": ["Apache-2.0"]}]}
        self.assertEqual(validate_inventory(inspect_composer(lock))["packages_observed"], 2)

    def test_npm_includes_nested_dependencies(self):
        lock = {"packages": {"": {}, "node_modules/foo": {"version": "1.0.0", "license": "MIT"},
                             "node_modules/foo/node_modules/@scope/bar": {"version": "3.2.1", "license": "BSD-3-Clause"}}}
        self.assertEqual(validate_inventory(inspect_npm(lock))["packages_observed"], 2)

    def test_unknown_license_fails(self):
        lock = {"packages": [], "packages-dev": [{"name": "vendor/a", "version": "1.0", "license": ["NOASSERTION"]}]}
        with self.assertRaises(ComplianceError):
            inspect_composer(lock)

    def test_missing_npm_license_fails(self):
        lock = {"packages": {"": {}, "node_modules/foo": {"version": "1.0.0"}}}
        with self.assertRaises(ComplianceError):
            inspect_npm(lock)

    def test_multiple_composer_licenses_require_review(self):
        lock = {"packages": [], "packages-dev": [{"name": "vendor/a", "version": "1.0", "license": ["MIT", "GPL-2.0-only"]}]}
        with self.assertRaises(ComplianceError):
            inspect_composer(lock)

    def test_duplicate_package_fails(self):
        with self.assertRaises(ComplianceError):
            validate_inventory([("foo", "1.0", "MIT"), ("foo", "1.0", "MIT")])

    def test_version_missing_fails(self):
        with self.assertRaises(ComplianceError):
            inspect_composer({"packages": [], "packages-dev": [{"name": "vendor/a", "license": ["MIT"]}]})

    def test_license_expression_does_not_claim_compatibility(self):
        package = inspect_composer({"packages": [{"name": "vendor/a", "version": "1.0", "license": ["MIT OR Apache-2.0"]}], "packages-dev": []})
        self.assertEqual(validate_inventory(package)["license_status"], "identifiers_present_review_required")


class ExternalNpmSnapshotTests(unittest.TestCase):
    def test_brvtal_snapshot_is_versioned_and_valid(self):
        self.assertTrue((SNAPSHOT_ROOT / "package.json").is_file())
        self.assertTrue((SNAPSHOT_ROOT / "package-lock.json").is_file())
        manifest = json.loads(
            (SNAPSHOT_ROOT / "snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["generation_run"], 36001724208)
        self.assertEqual(manifest["npm_version"], "10.9.8")
        self.assertEqual(manifest["sha256"], cumplimiento.NPM_SNAPSHOT_SHA256)
        packages = inspect_npm_snapshot(
            "brvtal",
            expected_project="pl0n3r/brvtal",
        )
        self.assertEqual(validate_inventory(packages)["packages_observed"], 3)

    def test_snapshot_uses_canonical_paths_and_expected_sha(self):
        manifest = json.loads(
            (SNAPSHOT_ROOT / "snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["source_sha"],
            "138b1babac0ff6797ad9e0f3ccb0fbda0f793452",
        )
        self.assertEqual(
            manifest["source_package_blob"],
            "a23d3ab36b5988c2edd9a38ff15a19d8fd572b1b",
        )
        with self.assertRaises(ComplianceError):
            inspect_npm_snapshot(
                "brvtal",
                expected_project="pl0n3r/Condor",
            )
        with self.assertRaises(ComplianceError):
            inspect_npm_snapshot("../../etc/passwd")

    def test_snapshot_inventory_includes_transitives(self):
        packages = inspect_npm_snapshot(
            "brvtal",
            expected_project="pl0n3r/brvtal",
        )
        self.assertEqual(
            packages,
            [
                ("@playwright/test", "1.63.0", "Apache-2.0"),
                ("playwright", "1.63.0", "Apache-2.0"),
                ("playwright-core", "1.63.0", "Apache-2.0"),
            ],
        )

    def test_snapshot_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp) / "brvtal-npm"
            shutil.copytree(SNAPSHOT_ROOT, fake_root)
            lock_path = fake_root / "package-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["packages"]["node_modules/playwright"]["license"] = "MIT"
            lock_path.write_text(
                json.dumps(lock, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path = fake_root / "snapshot.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["sha256"]["package-lock.json"] = hashlib.sha256(
                lock_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            with (
                patch.object(cumplimiento, "NPM_SNAPSHOT_ROOT", fake_root),
                patch.object(cumplimiento, "NPM_SNAPSHOT_MANIFEST", manifest_path),
                patch.object(
                    cumplimiento,
                    "NPM_SNAPSHOT_PACKAGE",
                    fake_root / "package.json",
                ),
                patch.object(cumplimiento, "NPM_SNAPSHOT_LOCK", lock_path),
            ):
                with self.assertRaises(ComplianceError):
                    cumplimiento.inspect_npm_snapshot(
                        "brvtal",
                        expected_project="pl0n3r/brvtal",
                    )


class CliSafetyTests(unittest.TestCase):
    def test_cli_rejects_arbitrary_paths(self):
        with patch(
            "sys.argv",
            [
                "cumplimiento.py",
                "--privacy",
                "/tmp/private.json",
                "--stdlib-only",
            ],
        ), patch("sys.stdin", io.StringIO("{}")):
            with self.assertRaises(SystemExit) as caught:
                main()
        self.assertEqual(caught.exception.code, 2)

    def test_cli_accepts_canonical_brvtal_snapshot(self):
        privacy = record()
        privacy["project"] = "pl0n3r/brvtal"
        privacy["reviewed_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        with patch(
            "sys.argv",
            ["cumplimiento.py", "--npm-snapshot", "brvtal"],
        ), patch(
            "sys.stdin",
            io.StringIO(json.dumps(privacy)),
        ):
            self.assertEqual(main(), 0)

    def test_cli_reads_privacy_from_stdin_and_canonical_lock(self):
        privacy = record()
        privacy["reviewed_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        lock = {
            "packages": [
                {
                    "name": "vendor/a",
                    "version": "1.0.0",
                    "license": ["MIT"],
                }
            ],
            "packages-dev": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.lock").write_text(
                __import__("json").dumps(lock),
                encoding="utf-8",
            )
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch(
                    "sys.argv",
                    ["cumplimiento.py", "--composer"],
                ), patch(
                    "sys.stdin",
                    io.StringIO(__import__("json").dumps(privacy)),
                ):
                    self.assertEqual(main(), 0)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
