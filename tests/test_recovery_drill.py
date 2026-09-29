import copy
import unittest
from pathlib import Path

from recovery.drill import RecoveryDrillError, build_restore_drill_plan, evaluate_restore_drill
from recovery.pipeline import build_backup_pipeline, verify_backup_evidence

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return {
        "version": 1, "project": "condor",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {"copies": 3, "media_types": 2, "offsite_copies": 1,
                       "immutable_copies": 1, "undetected_restore_failures": 0},
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {"database": "REQUIRED", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "NOT_APPLICABLE"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def verified_backup():
    m = manifest()
    request = {
        "source": "database", "backup_id": "backup:001",
        "snapshot_ref": "snapshot:001", "encrypted_ref": "encrypted:001",
        "object_storage_ref": "object:001", "cold_copy_ref": "NOT_APPLICABLE",
        "checksum_sha256": "a" * 64, "idempotency_key": "backup:001",
    }
    pipeline = build_backup_pipeline(m, request)
    evidence = {
        "backup_id": "backup:001", "source": "database",
        "checksum_sha256": "a" * 64, "encrypted": True,
        "primary_verified": True, "primary_ref": "object:001",
        "immutable_version_ref": "version:001",
        "cold_copy_verified": "NOT_APPLICABLE",
        "cold_copy_ref": "NOT_APPLICABLE",
        "created_at": "2026-09-29T00:00:00Z",
        "verified_at": "2026-09-29T00:02:00Z",
        "evidence_refs": ["run:001"],
    }
    return verify_backup_evidence(m, pipeline, evidence)


def evidence(incident="2026-09-29T00:10:00Z", completed="2026-09-29T00:40:00Z"):
    return {
        "backup_id": "backup:001", "checksum_sha256": "a" * 64,
        "health_ok": True, "smoke_ok": True, "integrity_ok": True,
        "incident_at": incident, "started_at": "2026-09-29T00:12:00Z",
        "completed_at": completed, "evidence_refs": ["drill:001"],
    }


class RecoveryDrillTests(unittest.TestCase):
    def test_restore_drill_plan_is_deterministic_disposable_and_external_io_free(self):
        backup = verified_backup()
        target = {"kind": "disposable", "target_ref": "sandbox:001"}
        first = build_restore_drill_plan(recovery, backup, target)
        self.assertEqual(first, build_restore_drill_plan(recovery, backup, target))
        self.assertEqual(first["target"]["kind"], "disposable")
        self.assertEqual((first["authority"], first["execute"]), ("unchanged", False))
        source = (ROOT / "recovery" / "drill.py").read_text()
        for forbidden in ("import requests", "import urllib", "import socket",
                          "import subprocess", "Path(", "open("):
            self.assertNotIn(forbidden, source)

    def test_drill_requires_verified_backup_and_health_smoke_integrity_evidence(self):
        backup = verified_backup()
        target = {"kind": "disposable", "target_ref": "sandbox:001"}
        plan = build_restore_drill_plan(recovery, backup, target)
        bad_backup = dict(backup); bad_backup["status"] = "PLANNED"
        with self.assertRaises(RecoveryDrillError):
            build_restore_drill_plan(recovery, bad_backup, target)
        no_primary = dict(backup); no_primary["destinations"] = []
        with self.assertRaises(RecoveryDrillError):
            build_restore_drill_plan(manifest(), no_primary, target)
        for field in ("health_ok", "smoke_ok", "integrity_ok"):
            bad = evidence(); bad[field] = False
            with self.subTest(field=field), self.assertRaises(RecoveryDrillError):
                evaluate_restore_drill(recovery, plan, backup, bad)
        bad = evidence(); bad["checksum_sha256"] = "b" * 64
        with self.assertRaises(RecoveryDrillError):
            evaluate_restore_drill(recovery, plan, backup, bad)

    def test_drill_measures_rpo_rto_and_reports_passed_or_breached(self):
        backup = verified_backup()
        plan = build_restore_drill_plan(
            manifest(), backup, {"kind": "disposable", "target_ref": "sandbox:001"}
        )
        passed = evaluate_restore_drill(manifest(), plan, backup, evidence())
        self.assertEqual(passed["status"], "PASSED")
        self.assertEqual(passed["observed"]["rpo_seconds"], 600)
        self.assertEqual(passed["observed"]["rto_seconds"], 1680)

        breached = evaluate_restore_drill(
            manifest(), plan, backup,
            evidence("2026-09-29T00:20:00Z", "2026-09-29T01:30:00Z"),
        )
        self.assertEqual(breached["status"], "BREACHED")
        self.assertEqual(breached["reasons"], ["RPO_EXCEEDED", "RTO_EXCEEDED"])

    def test_drill_fails_closed_for_production_sensitive_or_authority_expansion(self):
        backup = verified_backup()
        for target in (
            {"kind": "production", "target_ref": "prod:001"},
            {"kind": "disposable", "target_ref": "ghp_" + "A" * 24},
        ):
            with self.subTest(target=target), self.assertRaises(RecoveryDrillError) as ctx:
                build_restore_drill_plan(recovery, backup, target)
            self.assertNotIn("ghp_", str(ctx.exception))

        expanded = dict(backup); expanded["authority"] = "production-write"
        with self.assertRaises(RecoveryDrillError):
            build_restore_drill_plan(
                manifest(), expanded,
                {"kind": "disposable", "target_ref": "sandbox:001"},
            )

        plan = build_restore_drill_plan(
            manifest(), backup, {"kind": "disposable", "target_ref": "sandbox:001"}
        )
        tampered = copy.deepcopy(plan); tampered["source"] = "repository"
        with self.assertRaises(RecoveryDrillError):
            evaluate_restore_drill(recovery, tampered, backup, evidence())
        tampered = copy.deepcopy(plan); tampered["steps"][0]["authority"] = "production-write"
        with self.assertRaises(RecoveryDrillError):
            evaluate_restore_drill(recovery, tampered, backup, evidence())


if __name__ == "__main__":
    unittest.main()
