import json
import unittest

from recovery.drill import (
    RecoveryDrillError, build_restore_drill_plan, evaluate_restore_drill,
)
from recovery.pipeline import (
    RecoveryPipelineError, build_backup_pipeline, verify_backup_evidence,
)
from recovery.status import (
    RecoveryStatusError, derive_recovery_health, project_recovery_readiness,
)


def manifest():
    return {
        "version": 1, "project": "condor",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {"copies": 3, "media_types": 2, "offsite_copies": 1,
                       "immutable_copies": 1, "undetected_restore_failures": 0},
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {"database": "REQUIRED", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "google_drive"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def verified_backup():
    recovery = manifest()
    plan = build_backup_pipeline(recovery, {
        "source": "database", "backup_id": "backup:001",
        "snapshot_ref": "snapshot:001", "encrypted_ref": "encrypted:001",
        "object_storage_ref": "object:001", "cold_copy_ref": "drive:001",
        "checksum_sha256": "a" * 64, "idempotency_key": "backup:001",
    })
    backup = verify_backup_evidence(recovery, plan, {
        "backup_id": "backup:001", "source": "database",
        "checksum_sha256": "a" * 64, "encrypted": True,
        "primary_verified": True, "primary_ref": "object:001",
        "immutable_version_ref": "version:001",
        "cold_copy_verified": True, "cold_copy_ref": "drive:001",
        "created_at": "2026-09-29T01:20:00Z",
        "verified_at": "2026-09-29T01:21:00Z",
        "evidence_refs": ["run:backup:001", "offsite:drive:001"],
    })
    return plan, backup


def drill_result(backup, breached=False):
    recovery = manifest()
    restore = build_restore_drill_plan(
        recovery, backup, {"kind": "disposable", "target_ref": "sandbox:001"}
    )
    observed = {
        "backup_id": "backup:001", "checksum_sha256": "a" * 64,
        "health_ok": True, "smoke_ok": True, "integrity_ok": True,
        "incident_at": "2026-09-29T01:25:00Z",
        "started_at": "2026-09-29T01:26:00Z",
        "completed_at": "2026-09-29T01:31:00Z",
        "evidence_refs": ["drill:001", "health:001", "smoke:001", "integrity:001"],
    }
    if breached:
        observed.update({
            "incident_at": "2026-09-29T01:36:00Z",
            "started_at": "2026-09-29T01:37:00Z",
            "completed_at": "2026-09-29T02:40:00Z",
        })
    return restore, evaluate_restore_drill(recovery, restore, backup, observed)


class RecoveryE2ETests(unittest.TestCase):
    def test_backup_offsite_restore_health_smoke_and_rpo_rto_flow_without_source_or_secrets(self):
        source_original = {"kind": "database", "bytes": "SIMULATED_ONLY"}
        backup_plan, backup = verified_backup()
        self.assertEqual(
            [row["provider"] for row in backup_plan["destinations"]],
            ["object_storage", "google_drive"],
        )
        self.assertEqual(backup["status"], "VERIFIED")
        self.assertNotIn("snapshot_ref", backup)
        self.assertNotIn("encrypted_ref", backup)

        del source_original
        restore, drill = drill_result(backup)
        self.assertEqual(restore["target"]["kind"], "disposable")
        self.assertEqual(drill["status"], "PASSED")
        self.assertEqual(
            (drill["observed"]["rpo_seconds"], drill["observed"]["rto_seconds"]),
            (300, 300),
        )
        self.assertEqual(drill["checks"], {
            "health": True, "smoke": True, "integrity": True,
        })

        serialized = json.dumps({
            "backup": backup, "restore": restore, "drill": drill,
        }, sort_keys=True)
        for forbidden in ("secret=", "token=", "password=", "@example.com"):
            self.assertNotIn(forbidden, serialized)

    def test_healthy_recovery_projects_same_health_into_readiness(self):
        _, backup = verified_backup()
        _, drill = drill_result(backup)
        health = derive_recovery_health(
            manifest(), backup, drill,
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        readiness = project_recovery_readiness(health, critical=True)
        self.assertEqual(health["state"], "HEALTHY")
        self.assertEqual(readiness["recovery_health"], health["state"])
        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["recalculated"])
        self.assertEqual((health["authority"], health["execute"]),
                         ("unchanged", False))

    def test_rpo_rto_breach_propagates_as_degraded_canonical_health(self):
        _, backup = verified_backup()
        _, drill = drill_result(backup, breached=True)
        health = derive_recovery_health(
            manifest(), backup, drill,
            observed_at="2026-09-29T02:42:00Z",
            drill_observed_at="2026-09-29T02:41:00Z",
        )
        self.assertEqual(health["state"], "DEGRADED")
        self.assertEqual(
            health["work_item_classes"],
            ["backup_stale", "rpo_breached", "rto_breached"],
        )
        self.assertEqual(
            health["drill_observed"],
            {
                "rpo_seconds": 960, "rto_seconds": 3780,
                "rpo_target_seconds": 900, "rto_target_seconds": 3600,
            },
        )

    def test_e2e_rejects_sensitive_or_authority_expanding_inputs_without_side_effects(self):
        recovery = manifest()
        sensitive = {
            "source": "database", "backup_id": "ghp_" + ("A" * 24),
            "snapshot_ref": "snapshot:001", "encrypted_ref": "encrypted:001",
            "object_storage_ref": "object:001", "cold_copy_ref": "drive:001",
            "checksum_sha256": "a" * 64, "idempotency_key": "backup:001",
        }
        with self.assertRaises(RecoveryPipelineError) as ctx:
            build_backup_pipeline(recovery, sensitive)
        self.assertNotIn("ghp_", str(ctx.exception))

        _, backup = verified_backup()
        with self.assertRaises(RecoveryDrillError):
            build_restore_drill_plan(
                recovery, backup, {"kind": "production", "target_ref": "prod:001"}
            )

        _, drill = drill_result(backup)
        health = derive_recovery_health(
            recovery, backup, drill,
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        forged = dict(health)
        forged["authority"] = "production-write"
        with self.assertRaises(RecoveryStatusError):
            project_recovery_readiness(forged, critical=True)

        for artifact in (backup, drill, health):
            self.assertEqual((artifact["authority"], artifact["execute"]),
                             ("unchanged", False))


if __name__ == "__main__":
    unittest.main()
