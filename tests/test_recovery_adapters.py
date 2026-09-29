import copy
import unittest
from pathlib import Path

from recovery.adapters import (
    RecoveryAdapterError,
    build_adapter_descriptor,
    canonical_adapter_descriptor,
    supported_providers,
)

ROOT = Path(__file__).resolve().parents[1]


def manifest(cold_copy="google_drive"):
    return {
        "version": 1,
        "project": "condor",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {
            "copies": 3,
            "media_types": 2,
            "offsite_copies": 1,
            "immutable_copies": 1,
            "undetected_restore_failures": 0,
        },
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {
            "database": "REQUIRED",
            "media": "NOT_APPLICABLE",
            "repository": "REQUIRED",
        },
        "offsite": {
            "object_storage": "REQUIRED",
            "cold_copy": cold_copy,
        },
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def request(provider="object_storage", operation="upload"):
    return {
        "provider": provider,
        "operation": operation,
        "object_ref": "backup:20260928:001",
        "checksum_sha256": "a" * 64,
        "idempotency_key": "backup:condor:001",
    }


class RecoveryAdaptersTests(unittest.TestCase):
    def test_object_storage_and_google_drive_cold_copy_are_opaque_idempotent_and_checksum_aware(self):
        primary = build_adapter_descriptor(manifest(), request())
        cold = build_adapter_descriptor(
            manifest(), request(provider="google_drive", operation="verify")
        )
        self.assertEqual(primary["role"], "primary_offsite")
        self.assertEqual(cold["role"], "cold_copy")
        self.assertEqual(primary["checksum_sha256"], "a" * 64)
        self.assertEqual(primary["namespace"], "recovery:condor")
        self.assertEqual(
            canonical_adapter_descriptor(manifest(), request()),
            canonical_adapter_descriptor(manifest(), copy.deepcopy(request())),
        )
        self.assertEqual(
            primary["descriptor_id"],
            build_adapter_descriptor(manifest(), request())["descriptor_id"],
        )

    def test_object_storage_remains_primary_and_icloud_is_not_supported(self):
        self.assertEqual(
            supported_providers(),
            ("google_drive", "object_storage"),
        )
        self.assertNotIn("icloud", supported_providers())
        self.assertEqual(
            build_adapter_descriptor(manifest(), request())["role"],
            "primary_offsite",
        )
        disabled = manifest("NOT_APPLICABLE")
        disabled_request = request(provider="google_drive")
        with self.assertRaises(RecoveryAdapterError):
            build_adapter_descriptor(disabled, disabled_request)

    def test_invalid_sensitive_or_unsafe_adapter_input_fails_closed_without_echo(self):
        invalid = []
        value = request(); value["provider"] = "icloud"; invalid.append(value)
        value = request(); value["operation"] = "delete"; invalid.append(value)
        value = request(); value["object_ref"] = "../backup"; invalid.append(value)
        value = request(); value["object_ref"] = "https://storage.example/x"; invalid.append(value)
        value = request(); value["checksum_sha256"] = "abc"; invalid.append(value)
        value = request(); value["future"] = True; invalid.append(value)
        secret = "token=supersecretvalue"
        value = request(); value["idempotency_key"] = secret; invalid.append(value)
        opaque_secret = "ghp_" + ("A" * 24)
        value = request(); value["object_ref"] = opaque_secret; invalid.append(value)
        pii = "person@example.com"
        value = request(); value["object_ref"] = pii; invalid.append(value)

        recovery_manifest = manifest()
        for value in invalid:
            with self.subTest(case=str(value)[:50]):
                with self.assertRaises(RecoveryAdapterError) as ctx:
                    build_adapter_descriptor(recovery_manifest, value)
            self.assertNotIn("supersecretvalue", str(ctx.exception))
            self.assertNotIn("ghp_", str(ctx.exception))
            self.assertNotIn("person@example.com", str(ctx.exception))

    def test_adapter_contract_is_declarative_external_io_free_and_non_authorizing(self):
        descriptor = build_adapter_descriptor(
            manifest(), request(operation="materialize")
        )
        self.assertFalse(descriptor["execute"])
        self.assertEqual(descriptor["authority"], "unchanged")

        source = (ROOT / "recovery" / "adapters.py").read_text()
        for forbidden in (
            "import socket",
            "import subprocess",
            "import urllib",
            "import requests",
            "Path(",
            "open(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
