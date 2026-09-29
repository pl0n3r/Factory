import copy
import unittest
from pathlib import Path

from recovery.pipeline import (
    RecoveryPipelineError,
    build_backup_pipeline,
    verify_backup_evidence,
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


def request(cold_ref="drive:condor:001"):
    return {
        "source": "database",
        "backup_id": "backup:condor:001",
        "snapshot_ref": "snapshot:condor:001",
        "encrypted_ref": "encrypted:condor:001",
        "object_storage_ref": "object:condor:001",
        "cold_copy_ref": cold_ref,
        "checksum_sha256": "a" * 64,
        "idempotency_key": "backup:condor:001",
    }


def evidence(cold=True, cold_ref="drive:condor:001"):
    return {
        "backup_id": "backup:condor:001",
        "source": "database",
        "checksum_sha256": "a" * 64,
        "encrypted": True,
        "primary_verified": True,
        "primary_ref": "object:condor:001",
        "immutable_version_ref": "version:object:001",
        "cold_copy_verified": cold,
        "cold_copy_ref": cold_ref,
        "created_at": "2026-09-29T00:00:00Z",
        "verified_at": "2026-09-29T00:02:00Z",
        "evidence_refs": ["run:backup:001", "checksum:001"],
    }


class RecoveryPipelineTests(unittest.TestCase):
    def test_backup_pipeline_is_deterministic_declarative_and_external_io_free(self):
        first = build_backup_pipeline(manifest(), request())
        second = build_backup_pipeline(
            copy.deepcopy(manifest()), copy.deepcopy(request())
        )
        self.assertEqual(first, second)
        self.assertEqual(
            [row["kind"] for row in first["steps"]],
            [
                "snapshot",
                "checksum",
                "encrypt",
                "upload_primary",
                "verify_primary",
                "cold_copy",
                "record_evidence",
            ],
        )
        self.assertFalse(first["execute"])
        self.assertEqual(first["authority"], "unchanged")

        source = (ROOT / "recovery" / "pipeline.py").read_text()
        for forbidden in (
            "import socket",
            "import subprocess",
            "import urllib",
            "import requests",
            "Path(",
            "open(",
        ):
            self.assertNotIn(forbidden, source)

    def test_required_backup_cannot_be_verified_without_contract_evidence(self):
        pipeline = build_backup_pipeline(manifest(), request())
        invalid = []
        value = evidence(); value["encrypted"] = False; invalid.append(value)
        value = evidence(); value["primary_verified"] = False; invalid.append(value)
        value = evidence(); value["checksum_sha256"] = "b" * 64; invalid.append(value)
        value = evidence(); value["immutable_version_ref"] = "../unsafe"; invalid.append(value)
        value = evidence(); value["evidence_refs"] = []; invalid.append(value)
        value = evidence(); value["verified_at"] = "2026-09-28T23:59:00Z"; invalid.append(value)

        recovery_manifest = manifest()
        for value in invalid:
            with self.subTest(case=str(value)[:60]):
                with self.assertRaises(RecoveryPipelineError):
                    verify_backup_evidence(recovery_manifest, pipeline, value)

        verified = verify_backup_evidence(
            recovery_manifest, pipeline, evidence()
        )
        self.assertEqual(verified["status"], "VERIFIED")
        self.assertEqual(verified["freshness_target_seconds"], 900)

    def test_google_drive_is_optional_cold_copy_never_primary(self):
        with_drive = build_backup_pipeline(manifest(), request())
        self.assertEqual(
            [row["provider"] for row in with_drive["destinations"]],
            ["object_storage", "google_drive"],
        )
        self.assertEqual(with_drive["destinations"][0]["role"], "primary_offsite")
        self.assertEqual(with_drive["destinations"][1]["role"], "cold_copy")

        without_manifest = manifest("NOT_APPLICABLE")
        without_request = request("NOT_APPLICABLE")
        without_drive = build_backup_pipeline(without_manifest, without_request)
        self.assertEqual(
            [row["provider"] for row in without_drive["destinations"]],
            ["object_storage"],
        )
        without_evidence = evidence(
            cold="NOT_APPLICABLE",
            cold_ref="NOT_APPLICABLE",
        )
        verified = verify_backup_evidence(
            without_manifest, without_drive, without_evidence
        )
        self.assertEqual(
            [row["provider"] for row in verified["destinations"]],
            ["object_storage"],
        )

    def test_pipeline_output_is_sanitized_non_authorizing_and_fail_closed(self):
        pipeline = build_backup_pipeline(manifest(), request())
        verified = verify_backup_evidence(manifest(), pipeline, evidence())
        self.assertFalse(verified["execute"])
        self.assertEqual(verified["authority"], "unchanged")
        self.assertNotIn("payload", verified)

        invalid_requests = []
        value = request(); value["source"] = "media"; invalid_requests.append(value)
        value = request(); value["checksum_sha256"] = "bad"; invalid_requests.append(value)
        value = request(); value["object_storage_ref"] = "../backup"; invalid_requests.append(value)
        value = request(); value["future"] = True; invalid_requests.append(value)
        value = request(); value["backup_id"] = "ghp_" + ("A" * 24); invalid_requests.append(value)

        recovery_manifest = manifest()
        for value in invalid_requests:
            with self.subTest(case=str(value)[:60]):
                with self.assertRaises(RecoveryPipelineError) as ctx:
                    build_backup_pipeline(recovery_manifest, value)
            self.assertNotIn("ghp_", str(ctx.exception))

        invalid_evidence = evidence()
        invalid_evidence["evidence_refs"] = ["person@example.com"]
        with self.assertRaises(RecoveryPipelineError) as ctx:
            verify_backup_evidence(
                recovery_manifest,
                pipeline,
                invalid_evidence,
            )
        self.assertNotIn("person@example.com", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
