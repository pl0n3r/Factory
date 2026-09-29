import copy
import unittest
from pathlib import Path

from recovery.drill import build_restore_drill_plan, evaluate_restore_drill
from recovery.pipeline import build_backup_pipeline, verify_backup_evidence
from recovery.status import (
    RecoveryStatusError,
    WORK_ITEM_CLASSES,
    derive_recovery_health,
    project_recovery_readiness,
    recovery_work_item_classes,
)

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


def backup():
    m = manifest()
    plan = build_backup_pipeline(m, {
        "source": "database", "backup_id": "backup:001",
        "snapshot_ref": "snapshot:001", "encrypted_ref": "encrypted:001",
        "object_storage_ref": "object:001", "cold_copy_ref": "NOT_APPLICABLE",
        "checksum_sha256": "a" * 64, "idempotency_key": "backup:001",
    })
    return verify_backup_evidence(m, plan, {
        "backup_id": "backup:001", "source": "database",
        "checksum_sha256": "a" * 64, "encrypted": True,
        "primary_verified": True, "primary_ref": "object:001",
        "immutable_version_ref": "version:001",
        "cold_copy_verified": "NOT_APPLICABLE",
        "cold_copy_ref": "NOT_APPLICABLE",
        "created_at": "2026-09-29T01:20:00Z",
        "verified_at": "2026-09-29T01:21:00Z",
        "evidence_refs": ["run:backup:001"],
    })


def drill(status="PASSED"):
    m, b = manifest(), backup()
    plan = build_restore_drill_plan(
        m, b, {"kind": "disposable", "target_ref": "sandbox:001"}
    )
    completed = "2026-09-29T01:31:00Z"
    incident = "2026-09-29T01:25:00Z"
    if status == "BREACHED":
        completed = "2026-09-29T02:40:00Z"
        incident = "2026-09-29T01:40:00Z"
    return evaluate_restore_drill(m, plan, b, {
        "backup_id": "backup:001", "checksum_sha256": "a" * 64,
        "health_ok": True, "smoke_ok": True, "integrity_ok": True,
        "incident_at": incident, "started_at": "2026-09-29T01:26:00Z",
        "completed_at": completed, "evidence_refs": ["drill:001"],
    })


class RecoveryStatusTests(unittest.TestCase):
    def test_recovery_health_is_explainable_freshness_aware_and_fail_closed(self):
        healthy = derive_recovery_health(
            manifest(), backup(), drill(),
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        self.assertEqual(healthy["state"], "HEALTHY")
        self.assertEqual(healthy["reasons"], ["RECOVERY_EVIDENCE_CURRENT"])

        missing = derive_recovery_health(
            manifest(), None, None, observed_at="2026-09-29T01:34:00Z"
        )
        self.assertEqual((missing["state"], missing["work_item_classes"]),
                         ("UNKNOWN", ["backup_missing"]))

        stale = derive_recovery_health(
            manifest(), backup(), drill(),
            observed_at="2026-09-29T02:00:01Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        self.assertEqual((stale["state"], stale["work_item_classes"]),
                         ("UNKNOWN", ["backup_stale"]))

        breached = derive_recovery_health(
            manifest(), backup(), drill("BREACHED"),
            observed_at="2026-09-29T01:45:00Z",
            drill_observed_at="2026-09-29T01:44:00Z",
        )
        self.assertEqual(breached["state"], "DEGRADED")
        self.assertEqual(
            breached["work_item_classes"], ["rpo_breached", "rto_breached"]
        )

    def test_recovery_drift_maps_to_canonical_work_item_classes_without_scheduler(self):
        recovery = manifest()
        valid_backup = backup()
        cases = []

        no_primary = copy.deepcopy(valid_backup); no_primary["destinations"] = []
        cases.append(("offsite_missing", no_primary, drill(), False))

        bad_checksum = copy.deepcopy(drill()); bad_checksum["checksum_sha256"] = "b" * 64
        cases.append(("checksum_failed", valid_backup, bad_checksum, False))

        cases.append(("retention_drift", valid_backup, drill(), True))

        for expected, candidate_backup, candidate_drill, retention in cases:
            health = derive_recovery_health(
                recovery, candidate_backup, candidate_drill,
                observed_at="2026-09-29T01:34:00Z",
                drill_observed_at="2026-09-29T01:32:00Z",
                retention_drift=retention,
            )
            self.assertIn(expected, recovery_work_item_classes(health))
            self.assertTrue(set(health["work_item_classes"]) <= WORK_ITEM_CLASSES)

        source = (ROOT / "recovery" / "status.py").read_text()
        for forbidden in ("schedule(", "create_issue", "dispatch(", "requests."):
            self.assertNotIn(forbidden, source)

    def test_readiness_projection_reuses_recovery_health_without_recalculation(self):
        unknown = derive_recovery_health(
            manifest(), None, None, observed_at="2026-09-29T01:34:00Z"
        )
        projection = project_recovery_readiness(unknown, critical=True)
        self.assertEqual(projection["recovery_health"], unknown["state"])
        self.assertFalse(projection["ready"])
        self.assertTrue(projection["critical_blocker"])
        self.assertFalse(projection["recalculated"])
        self.assertEqual(
            projection["work_item_classes"], unknown["work_item_classes"]
        )

        degraded = derive_recovery_health(
            manifest(), backup(), drill("BREACHED"),
            observed_at="2026-09-29T01:45:00Z",
            drill_observed_at="2026-09-29T01:44:00Z",
        )
        projected = project_recovery_readiness(degraded, critical=True)
        self.assertEqual(projected["recovery_health"], "DEGRADED")
        self.assertTrue(projected["ready"])
        self.assertFalse(projected["critical_blocker"])

    def test_recovery_status_rejects_sensitive_future_or_authority_expanding_evidence(self):
        recovery = manifest()
        sensitive = copy.deepcopy(backup())
        sensitive["evidence_refs"] = ["token=supersecretvalue"]
        blocked = derive_recovery_health(
            recovery, sensitive, drill(),
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertNotIn("supersecretvalue", str(blocked))

        expanded = copy.deepcopy(drill()); expanded["authority"] = "production-write"
        blocked = derive_recovery_health(
            recovery, backup(), expanded,
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        self.assertEqual(blocked["state"], "BLOCKED")

        future = derive_recovery_health(
            recovery, backup(), drill(),
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:35:00Z",
        )
        self.assertEqual(future["state"], "BLOCKED")

        forged = {"state": "HEALTHY", "work_item_classes": ["other"]}
        with self.assertRaises(RecoveryStatusError):
            recovery_work_item_classes(forged)


if __name__ == "__main__":
    unittest.main()
