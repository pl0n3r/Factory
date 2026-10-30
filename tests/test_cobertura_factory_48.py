#!/usr/bin/env python3
"""Factory #1839: recuperación sintética con contratos reales; nunca runtime/live."""
from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from recovery.contract import RecoveryContractError, validate_recovery_manifest
from recovery.drill import (
    RecoveryDrillError, build_restore_drill_plan, evaluate_restore_drill,
)
from recovery.gdrive_adapter import (
    ColdCopyError, FakeDriveTransport, GDriveColdCopy,
)
from recovery.pipeline import (
    RecoveryPipelineError, build_backup_pipeline, verify_backup_evidence,
)
from recovery.status import (
    RecoveryStatusError, WORK_ITEM_CLASSES, derive_recovery_health,
    project_recovery_readiness, recovery_work_item_classes,
)


def manifest(cold_copy="google_drive"):
    return {
        "version": 1, "project": "synthetic-factory",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {"copies": 3, "media_types": 2, "offsite_copies": 1,
                       "immutable_copies": 1, "undetected_restore_failures": 0},
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {"database": "REQUIRED", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": cold_copy},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def backup_request(cold_copy=True):
    return {
        "source": "database", "backup_id": "backup:synthetic",
        "snapshot_ref": "snapshot:synthetic",
        "encrypted_ref": "encrypted:synthetic",
        "object_storage_ref": "object:synthetic",
        "cold_copy_ref": "drive:synthetic" if cold_copy else "NOT_APPLICABLE",
        "checksum_sha256": "a" * 64, "idempotency_key": "backup:synthetic",
    }


def backup_receipt(cold_copy=True):
    return {
        "backup_id": "backup:synthetic", "source": "database",
        "checksum_sha256": "a" * 64, "encrypted": True,
        "primary_verified": True, "primary_ref": "object:synthetic",
        "immutable_version_ref": "version:synthetic",
        "cold_copy_verified": True if cold_copy else "NOT_APPLICABLE",
        "cold_copy_ref": "drive:synthetic" if cold_copy else "NOT_APPLICABLE",
        "created_at": "2026-09-29T01:20:00Z",
        "verified_at": "2026-09-29T01:21:00Z",
        "evidence_refs": ["run:synthetic", "offsite:synthetic"],
    }


def drill_receipt(breached=False):
    result = {
        "backup_id": "backup:synthetic", "checksum_sha256": "a" * 64,
        "health_ok": True, "smoke_ok": True, "integrity_ok": True,
        "incident_at": "2026-09-29T01:25:00Z",
        "started_at": "2026-09-29T01:26:00Z",
        "completed_at": "2026-09-29T01:31:00Z",
        "evidence_refs": ["drill:synthetic", "health:synthetic"],
    }
    if breached:
        result.update({
            "incident_at": "2026-09-29T01:36:00Z",
            "started_at": "2026-09-29T01:37:00Z",
            "completed_at": "2026-09-29T02:40:00Z",
        })
    return result


def scenario(*, breached=False, cold_copy=True):
    m = manifest("google_drive" if cold_copy else "NOT_APPLICABLE")
    pipeline = build_backup_pipeline(m, backup_request(cold_copy))
    backup = verify_backup_evidence(m, pipeline, backup_receipt(cold_copy))
    restore = build_restore_drill_plan(
        m, backup, {"kind": "disposable", "target_ref": "sandbox:synthetic"}
    )
    drill = evaluate_restore_drill(
        m, restore, backup, drill_receipt(breached)
    )
    now, seen = (
        ("2026-09-29T02:42:00Z", "2026-09-29T02:41:00Z")
        if breached else
        ("2026-09-29T01:34:00Z", "2026-09-29T01:32:00Z")
    )
    health = derive_recovery_health(
        m, backup, drill, observed_at=now, drill_observed_at=seen
    )
    return m, pipeline, backup, restore, drill, health


def rejected(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except (RecoveryContractError, RecoveryPipelineError,
            RecoveryDrillError, RecoveryStatusError):
        return True
    return False


class CoberturaFactory48Tests(unittest.TestCase):
    """Prueba el código, NO lee ni condiciona el estado de la matriz."""

    def test_contrato_principal(self):
        m, pipeline, backup, restore, drill, healthy = scenario()
        _, _, _, _, breached_drill, degraded = scenario(breached=True)
        _, no_cold, no_cold_backup, _, _, _ = scenario(cold_copy=False)

        all_na = manifest()
        all_na["sources"] = {k: "NOT_APPLICABLE" for k in all_na["sources"]}
        invalid_encryption = manifest()
        invalid_encryption["encryption"]["key_material"] = "INLINE"
        unknown_field = manifest()
        unknown_field["unapproved"] = True
        wrong_checksum = backup_receipt()
        wrong_checksum["checksum_sha256"] = "b" * 64
        unencrypted = backup_receipt()
        unencrypted["encrypted"] = False

        missing = derive_recovery_health(
            m, None, None, observed_at="2026-09-29T01:34:00Z"
        )
        blocked_backup = deepcopy(backup)
        blocked_backup["destinations"] = []
        blocked = derive_recovery_health(
            m, blocked_backup, drill, observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        readiness = project_recovery_readiness(healthy, critical=True)
        degraded_ready = project_recovery_readiness(degraded, critical=True)
        stale = derive_recovery_health(
            m, backup, drill,
            observed_at="2026-09-29T02:00:01Z",
            drill_observed_at="2026-09-29T01:59:00Z",
        )
        canonical_classes = {
            "backup_missing", "backup_stale", "offsite_missing",
            "checksum_failed", "restore_drill_failed", "rpo_breached",
            "rto_breached", "retention_drift",
        }
        # 17 filas observables del Issue, cada una invoca contratos ejecutables.
        proof = {
            # docs/recovery-contract.md:L7-U1
            "contract:L7-U1": (
                validate_recovery_manifest(m)["sources"]["database"] == "REQUIRED"
                and rejected(validate_recovery_manifest, all_na)),
            # docs/recovery-contract.md:L9-U1
            "contract:L9-U1": (
                validate_recovery_manifest(m)["encryption"]
                == {"required": True, "key_material": "EXTERNAL_ONLY"}
                and rejected(validate_recovery_manifest, invalid_encryption)),
            # docs/recovery-contract.md:L9-U2
            "contract:L9-U2": (
                rejected(validate_recovery_manifest, unknown_field)
                and rejected(validate_recovery_manifest,
                             {**m, "target": {"rpo_minutes": True,
                                            "rto_minutes": 60}})),
            # docs/recovery-drill.md:L5-U1
            "drill:L5-U1": (
                drill["status"] == "PASSED"
                and drill["checks"] == {"health": True, "smoke": True, "integrity": True}
                and rejected(evaluate_restore_drill, m, restore, backup,
                             {**drill_receipt(), "smoke_ok": False})),
            # docs/recovery-e2e.md:L18-U1
            "e2e:L18-U1": (
                pipeline == build_backup_pipeline(m, backup_request())
                and backup["backup_id"] == "backup:synthetic"
                and pipeline["execute"] is False),
            # docs/recovery-e2e.md:L18-U2
            "e2e:L18-U2": (
                backup["status"] == "VERIFIED"
                and restore["backup_id"] == backup["backup_id"]
                and restore["checksum_sha256"] == backup["checksum_sha256"]
                and "snapshot_ref" not in backup
                and "encrypted_ref" not in backup
                and "snapshot_ref" not in restore),
            # docs/recovery-e2e.md:L21-U1
            "e2e:L21-U1": (
                healthy["state"] == "HEALTHY"
                and readiness["recovery_health"] == "HEALTHY"
                and readiness["ready"] is True
                and readiness["recalculated"] is False),
            # docs/recovery-e2e.md:L22-U1
            "e2e:L22-U1": (
                breached_drill["status"] == "BREACHED"
                and degraded["state"] == "DEGRADED"
                and {"rpo_breached", "rto_breached"}
                <= set(degraded["work_item_classes"])),
            # docs/recovery-e2e.md:L22-U2
            "e2e:L22-U2": (
                stale["state"] == "UNKNOWN"
                and "backup_stale" in stale["work_item_classes"]
                and "backup_stale" in degraded["work_item_classes"]),
            # docs/recovery-pipeline.md:L5-U1
            "pipeline:L5-U1": (
                [step["kind"] for step in pipeline["steps"]]
                == ["snapshot", "checksum", "encrypt", "upload_primary",
                    "verify_primary", "cold_copy", "record_evidence"]
                and pipeline["pipeline_state"] == "PLANNED"
                and all(step["authority"] == "unchanged"
                        and step["execute"] is False for step in pipeline["steps"])),
            # docs/recovery-pipeline.md:L7-U1
            "pipeline:L7-U1": (
                pipeline["destinations"][0]["provider"] == "object_storage"
                and pipeline["destinations"][0]["role"] == "primary_offsite"
                and no_cold["destinations"][0]["role"] == "primary_offsite"),
            # docs/recovery-pipeline.md:L7-U2
            "pipeline:L7-U2": (
                [row["role"] for row in pipeline["destinations"]]
                == ["primary_offsite", "cold_copy"]
                and [row["provider"] for row in no_cold["destinations"]]
                == ["object_storage"]
                and [row["provider"] for row in no_cold_backup["destinations"]]
                == ["object_storage"]),
            # docs/recovery-pipeline.md:L9-U1
            "pipeline:L9-U1": (
                backup["status"] == "VERIFIED"
                and backup["encrypted"] is True
                and backup["checksum_sha256"] == "a" * 64
                and rejected(verify_backup_evidence, m, pipeline, wrong_checksum)
                and rejected(verify_backup_evidence, m, pipeline, unencrypted)),
            # docs/recovery-status.md:L15-U1
            "status:L15-U1": (
                set(WORK_ITEM_CLASSES) == canonical_classes
                and set(recovery_work_item_classes(degraded))
                == set(degraded["work_item_classes"])
                and bool(degraded["reasons"])),
            # docs/recovery-status.md:L17-U1
            "status:L17-U1": (
                project_recovery_readiness(missing, critical=True)["ready"] is False
                and project_recovery_readiness(blocked, critical=True)["ready"] is False
                and degraded_ready["ready"] is True
                and degraded_ready["recovery_health"] == "DEGRADED"),
            # docs/recovery-status.md:L21-U1
            "status:L21-U1": (
                healthy["authority"] == "unchanged"
                and healthy["execute"] is False
                and healthy["backup_ref"] == backup["backup_id"]),
            # docs/recovery-status.md:L6-U1
            "status:L6-U1": (
                backup["status"] == "VERIFIED"
                and drill["status"] == "PASSED"
                and healthy["state"] == "HEALTHY"
                and healthy["reasons"] == ["RECOVERY_EVIDENCE_CURRENT"]),
        }
        self.assertEqual(17, len(proof))
        for clause, passed in proof.items():
            with self.subTest(clause=clause):
                self.assertTrue(passed, "no se demostró comportamiento real")

    def test_falla_cerrado(self):
        m, pipeline, backup, restore, drill, _ = scenario()
        for field, bad in (
            ("checksum_sha256", "b" * 64),
            ("primary_verified", False),
            ("encrypted", False),
            ("immutable_version_ref", "../outside"),
            ("evidence_refs", []),
        ):
            receipt = backup_receipt()
            receipt[field] = bad
            with self.subTest(receipt=field):
                with self.assertRaises(RecoveryPipelineError):
                    verify_backup_evidence(m, pipeline, receipt)

        for key in ("health_ok", "smoke_ok", "integrity_ok"):
            evidence = drill_receipt()
            evidence[key] = False
            with self.subTest(drill_check=key):
                with self.assertRaises(RecoveryDrillError):
                    evaluate_restore_drill(m, restore, backup, evidence)

        with self.assertRaises(RecoveryDrillError):
            build_restore_drill_plan(
                m, backup, {"kind": "production", "target_ref": "prod:forbidden"}
            )
        invalid_request = {**backup_request(), "object_storage_ref": "../outside"}
        with self.assertRaises(RecoveryPipelineError):
            build_backup_pipeline(m, invalid_request)
        bad_backup = deepcopy(backup)
        bad_backup["checksum_sha256"] = "b" * 64
        blocked = derive_recovery_health(
            m, bad_backup, drill,
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        self.assertEqual("BLOCKED", blocked["state"])
        self.assertFalse(project_recovery_readiness(blocked, critical=True)["ready"])
        missing = derive_recovery_health(
            m, None, None, observed_at="2026-09-29T01:34:00Z"
        )
        self.assertEqual(("UNKNOWN", ["backup_missing"]),
                         (missing["state"], missing["work_item_classes"]))
        healthy = derive_recovery_health(
            m, backup, drill,
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z",
        )
        spoofed = {**healthy, "authority": "production-write"}
        with self.assertRaises(RecoveryStatusError):
            project_recovery_readiness(spoofed, critical=True)
        fake = FakeDriveTransport()
        denied_drive = GDriveColdCopy(
            m, transport=fake, secret_provider=object(),
            credential_ref="credential:synthetic",
            now=datetime(2026, 9, 29, 1, 34, tzinfo=timezone.utc),
            restore_authorizer=lambda _request: False,
        )
        with self.assertRaisesRegex(ColdCopyError, "restore_not_authorized"):
            denied_drive.materialize_fake(
                "object:synthetic", "a" * 64, purpose="offline_restore_test"
            )
        self.assertEqual({}, fake.objects)
        causal = derive_recovery_health(
            m, backup, drill,
            observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:19:59Z",
        )
        self.assertEqual(("BLOCKED", ["restore_drill_failed"]),
                         (causal["state"], causal["work_item_classes"]))

    def test_sin_datos_reales(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {name.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for name in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {
            "requests", "httpx", "urllib", "socket", "subprocess",
            "playwright", "selenium", "psycopg2", "pymysql",
        })
        m, pipeline, backup, restore, drill, health = scenario()
        self.assertEqual("synthetic-factory", m["project"])
        self.assertEqual("EXTERNAL_ONLY", m["encryption"]["key_material"])
        self.assertEqual((pipeline["authority"], pipeline["execute"]),
                         ("unchanged", False))
        for artifact in (backup, restore, drill, health):
            with self.subTest(artifact=artifact.get("status", artifact.get("state"))):
                self.assertEqual(("unchanged", False),
                                 (artifact["authority"], artifact["execute"]))
        exported = json.dumps([pipeline, backup, restore, drill, health])
        for private in ("-----BEGIN", "Bearer ", "person@", "api_key="):
            self.assertNotIn(private, exported)


if __name__ == "__main__":
    unittest.main()
