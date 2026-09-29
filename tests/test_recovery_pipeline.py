import copy
import unittest
from pathlib import Path

from recovery.pipeline import (
    RecoveryPipelineError, build_backup_pipeline, verify_backup_evidence,
)

ROOT = Path(__file__).resolve().parents[1]


def manifest(cold="google_drive"):
    return {
        "version": 1, "project": "condor",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {"copies": 3, "media_types": 2, "offsite_copies": 1,
                       "immutable_copies": 1, "undetected_restore_failures": 0},
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {"database": "REQUIRED", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": cold},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def request(cold="drive:001"):
    return {
        "source": "database", "backup_id": "backup:001",
        "snapshot_ref": "snapshot:001", "encrypted_ref": "encrypted:001",
        "object_storage_ref": "object:001", "cold_copy_ref": cold,
        "checksum_sha256": "a" * 64, "idempotency_key": "backup:001",
    }


def evidence(cold=True, ref="drive:001"):
    return {
        "backup_id": "backup:001", "source": "database",
        "checksum_sha256": "a" * 64, "encrypted": True,
        "primary_verified": True, "primary_ref": "object:001",
        "immutable_version_ref": "version:001",
        "cold_copy_verified": cold, "cold_copy_ref": ref,
        "created_at": "2026-09-29T00:00:00Z",
        "verified_at": "2026-09-29T00:02:00Z",
        "evidence_refs": ["run:001", "checksum:001"],
    }


class RecoveryPipelineTests(unittest.TestCase):
    def test_backup_pipeline_is_deterministic_declarative_and_external_io_free(self):
        first = build_backup_pipeline(manifest(), request())
        self.assertEqual(
            first, build_backup_pipeline(copy.deepcopy(manifest()), copy.deepcopy(request()))
        )
        self.assertEqual(
            [row["kind"] for row in first["steps"]],
            ["snapshot", "checksum", "encrypt", "upload_primary",
             "verify_primary", "cold_copy", "record_evidence"],
        )
        self.assertEqual((first["authority"], first["execute"]), ("unchanged", False))
        source = (ROOT / "recovery" / "pipeline.py").read_text()
        for forbidden in ("import socket", "import subprocess", "import urllib",
                          "import requests", "Path(", "open("):
            self.assertNotIn(forbidden, source)

    def test_required_backup_cannot_be_verified_without_contract_evidence(self):
        recovery, pipeline = manifest(), build_backup_pipeline(manifest(), request())
        invalid = []
        for field, value in (
            ("encrypted", False), ("primary_verified", False),
            ("checksum_sha256", "b" * 64), ("immutable_version_ref", "../bad"),
            ("evidence_refs", []), ("verified_at", "2026-09-28T23:59:00Z"),
        ):
            row = evidence(); row[field] = value; invalid.append(row)
        for row in invalid:
            with self.subTest(case=str(row)[:60]):
                with self.assertRaises(RecoveryPipelineError):
                    verify_backup_evidence(recovery, pipeline, row)
        verified = verify_backup_evidence(recovery, pipeline, evidence())
        self.assertEqual((verified["status"], verified["freshness_target_seconds"]),
                         ("VERIFIED", 900))

    def test_google_drive_is_optional_cold_copy_never_primary(self):
        with_drive = build_backup_pipeline(manifest(), request())
        self.assertEqual(
            [(row["provider"], row["role"]) for row in with_drive["destinations"]],
            [("object_storage", "primary_offsite"), ("google_drive", "cold_copy")],
        )
        recovery = manifest("NOT_APPLICABLE")
        pipeline = build_backup_pipeline(recovery, request("NOT_APPLICABLE"))
        observed = evidence("NOT_APPLICABLE", "NOT_APPLICABLE")
        verified = verify_backup_evidence(recovery, pipeline, observed)
        self.assertEqual([row["provider"] for row in verified["destinations"]],
                         ["object_storage"])

    def test_pipeline_output_is_sanitized_non_authorizing_and_fail_closed(self):
        recovery, pipeline = manifest(), build_backup_pipeline(manifest(), request())
        verified = verify_backup_evidence(recovery, pipeline, evidence())
        self.assertEqual((verified["authority"], verified["execute"]),
                         ("unchanged", False))
        invalid = []
        for field, value in (
            ("source", "media"), ("checksum_sha256", "bad"),
            ("object_storage_ref", "../backup"), ("backup_id", "ghp_" + "A" * 24),
        ):
            row = request(); row[field] = value; invalid.append(row)
        for row in invalid:
            with self.subTest(case=str(row)[:60]):
                with self.assertRaises(RecoveryPipelineError) as ctx:
                    build_backup_pipeline(recovery, row)
            self.assertNotIn("ghp_", str(ctx.exception))
        bad_evidence = evidence(); bad_evidence["evidence_refs"] = ["person@example.com"]
        with self.assertRaises(RecoveryPipelineError) as ctx:
            verify_backup_evidence(recovery, pipeline, bad_evidence)
        self.assertNotIn("person@example.com", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
