"""Factory #1677: 16 brechas de reconciliación y Recovery, solo sintéticas.

Una prueba offline no acredita PR fusionado, producción ni restore real.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import re
import unittest

from recovery.adapters import RecoveryAdapterError, build_adapter_descriptor, supported_providers
from recovery.contract import RecoveryContractError, validate_recovery_manifest
from recovery.drill import RecoveryDrillError, build_restore_drill_plan, evaluate_restore_drill
from recovery.pipeline import build_backup_pipeline, verify_backup_evidence

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
IDS = (
    "docs/reconciliacion-issues-20261024.md:L5-U1",
    "docs/recovery-adapters.md:L13-U1",
    "docs/recovery-adapters.md:L15-U1",
    "docs/recovery-adapters.md:L17-U1",
    "docs/recovery-adapters.md:L18-U1",
    "docs/recovery-adapters.md:L19-U1",
    "docs/recovery-adapters.md:L25-U1",
    "docs/recovery-adapters.md:L7-U1",
    "docs/recovery-adapters.md:L7-U2",
    "docs/recovery-adapters.md:L8-U1",
    "docs/recovery-adapters.md:L9-U1",
    "docs/recovery-contract.md:L7-U1",
    "docs/recovery-contract.md:L9-U1",
    "docs/recovery-contract.md:L9-U2",
    "docs/recovery-drill.md:L5-U1",
    "docs/recovery-e2e.md:L18-U1",
)
EVIDENCE_GAPS = {IDS[0]: "merged_pr_and_exact_head_validation_not_proven"}


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(raw):
    """El estado de la matriz nunca se promociona sin evidencia."""
    if not isinstance(raw, str):
        raise ValueError("matriz ausente")
    found = {}
    for line in raw.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        # Conserva escaped pipes de Markdown (provider object_storage\\|google_drive).
        cells = tuple(part.strip() for part in re.split(r"(?<!\\)\|", line.strip().strip("|")))
        key = cells[0].strip("`")
        if key not in IDS:
            continue
        if key in found or len(cells) != 5 or not all(cells[:4]):
            raise ValueError("fila incompleta o repetida: " + key)
        if cells[2] != "NO_VERIFICABLE":
            raise ValueError("promoción sin PR: " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError("faltan IDs")
    return found


def project(matrix, checks):
    try:
        matrix_rows(matrix)
    except ValueError:
        return dict.fromkeys(IDS, UNKNOWN)
    if (type(checks) is not dict or set(checks) != set(IDS)
            or any(type(value) is not bool for value in checks.values())):
        return dict.fromkeys(IDS, UNKNOWN)
    return {key: ("OFFLINE_VERIFIED" if checks[key] and key not in EVIDENCE_GAPS
                  else UNKNOWN) for key in IDS}


def manifest(cold_copy="google_drive"):
    return {
        "version": 1, "project": "factory",
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


def adapter_request(provider="object_storage", operation="upload"):
    return {
        "provider": provider, "operation": operation,
        "object_ref": "object:synthetic:001",
        "checksum_sha256": "a" * 64,
        "idempotency_key": "idempotent:synthetic:001",
    }


def verified_backup():
    recovery = manifest()
    plan = build_backup_pipeline(recovery, {
        "source": "database", "backup_id": "backup:synthetic:001",
        "snapshot_ref": "snapshot:synthetic:001",
        "encrypted_ref": "encrypted:synthetic:001",
        "object_storage_ref": "object:synthetic:001",
        "cold_copy_ref": "drive:synthetic:001",
        "checksum_sha256": "a" * 64,
        "idempotency_key": "backup:synthetic:001",
    })
    evidence = {
        "backup_id": "backup:synthetic:001", "source": "database",
        "checksum_sha256": "a" * 64, "encrypted": True,
        "primary_verified": True, "primary_ref": "object:synthetic:001",
        "immutable_version_ref": "version:synthetic:001",
        "cold_copy_verified": True, "cold_copy_ref": "drive:synthetic:001",
        "created_at": "2026-09-29T01:20:00Z",
        "verified_at": "2026-09-29T01:21:00Z",
        "evidence_refs": ["run:synthetic:001", "offsite:synthetic:001"],
    }
    return plan, verify_backup_evidence(recovery, plan, evidence)


def drill_case():
    _, backup = verified_backup()
    plan = build_restore_drill_plan(
        manifest(), backup, {"kind": "disposable", "target_ref": "sandbox:synthetic:001"},
    )
    evidence = {
        "backup_id": "backup:synthetic:001", "checksum_sha256": "a" * 64,
        "health_ok": True, "smoke_ok": True, "integrity_ok": True,
        "incident_at": "2026-09-29T01:25:00Z",
        "started_at": "2026-09-29T01:26:00Z",
        "completed_at": "2026-09-29T01:31:00Z",
        "evidence_refs": ["drill:synthetic:001"],
    }
    return backup, plan, evidence


def behavioral_evidence():
    """Cada posición de IDS tiene una aserción de contrato real."""
    recovery = validate_recovery_manifest(manifest())
    primary = build_adapter_descriptor(recovery, adapter_request())
    cold = build_adapter_descriptor(recovery, adapter_request("google_drive", "verify"))
    again = build_adapter_descriptor(recovery, adapter_request())
    optional = build_adapter_descriptor(manifest("NOT_APPLICABLE"), adapter_request())
    pipeline, backup = verified_backup()
    _, restore, expected = drill_case()
    drill = evaluate_restore_drill(recovery, restore, backup, expected)
    return dict(zip(IDS, (
        "no se declara cumplido por un PR parcial ni por un test offline"
            in read("docs/reconciliacion-issues-20261024.md"),
        recovery["version"] == primary["version"] == 1,
        {primary["provider"], cold["provider"]} == {"object_storage", "google_drive"},
        primary["object_ref"] == "object:synthetic:001",
        re.fullmatch(r"[0-9a-f]{64}", primary["checksum_sha256"]) is not None,
        primary["idempotency_key"] == adapter_request()["idempotency_key"]
            and primary["descriptor_id"] == again["descriptor_id"],
        primary["execute"] is False and primary["authority"] == "unchanged",
        primary["role"] == "primary_offsite",
        primary["role"] == optional["role"] == "primary_offsite",
        cold["role"] == "cold_copy" and len(pipeline["destinations"]) == 2,
        "icloud" not in supported_providers(),
        "REQUIRED" in recovery["sources"].values(),
        recovery["encryption"] == {"required": True, "key_material": "EXTERNAL_ONLY"},
        set(recovery) == {"version", "project", "target", "protection",
                          "retention", "sources", "offsite", "encryption", "restore_drill"},
        drill["status"] == "PASSED" and drill["checks"] ==
            {"health": True, "smoke": True, "integrity": True},
        backup["status"] == "VERIFIED" and restore["target"]["kind"] == "disposable"
            and restore["authority"] == drill["authority"] == "unchanged"
            and restore["execute"] is drill["execute"] is False
            and "snapshot_ref" not in backup and "encrypted_ref" not in backup,
    )))


class BrechasFactory59Tests(unittest.TestCase):
    def test_contrato_principal(self):
        matrix = read("docs/matriz-cobertura.md")
        rows = matrix_rows(matrix)
        checks = behavioral_evidence()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(rows), set(IDS))
        self.assertEqual(set(checks), set(IDS))
        for key in IDS:
            with self.subTest(unit=key):
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")
                self.assertTrue(checks[key], "brecha sin aserción: " + key)
        self.assertEqual(project(matrix, checks)[IDS[0]], UNKNOWN)
        self.assertEqual(set(project(matrix, checks).values()),
                         {UNKNOWN, "OFFLINE_VERIFIED"})

    def test_falla_cerrado(self):
        original = read("docs/matriz-cobertura.md")
        line = next(row for row in original.splitlines() if "`" + IDS[0] + "`" in row)
        for value in (
            None, "", original.replace(line, "", 1), original + "\n" + line,
            original.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO")),
            original.replace(line, "| `" + IDS[0] + "` |"),
        ):
            with self.subTest(matrix=str(value)[:25]):
                with self.assertRaises(ValueError):
                    matrix_rows(value)
                self.assertEqual(set(project(value, dict.fromkeys(IDS, True)).values()),
                                 {UNKNOWN})
        for invalid in (None, {}, {IDS[0]: True}, dict.fromkeys(IDS, 1),
                        dict.fromkeys(IDS, "success"),
                        {**dict.fromkeys(IDS, True), "extra": True}):
            self.assertEqual(set(project(original, invalid).values()), {UNKNOWN})

        bad = manifest()
        bad["sources"] = dict.fromkeys(bad["sources"], "NOT_APPLICABLE")
        with self.assertRaises(RecoveryContractError):
            validate_recovery_manifest(bad)
        for field, value in (("required", False), ("key_material", "INLINE")):
            bad = manifest()
            bad["encryption"][field] = value
            with self.subTest(encryption=field), self.assertRaises(RecoveryContractError):
                validate_recovery_manifest(bad)
        for field, value in (("future", True), ("version", "1")):
            bad = manifest()
            bad[field] = value
            with self.subTest(manifest=field), self.assertRaises(RecoveryContractError):
                validate_recovery_manifest(bad)
        bad = manifest()
        bad["encryption"]["token"] = "token=value"
        with self.assertRaises(RecoveryContractError):
            validate_recovery_manifest(bad)

        for field, invalid in (
            ("provider", "icloud"), ("provider", "s3"),
            ("operation", "delete"), ("object_ref", "../backup"),
            ("object_ref", "https://example.invalid/file"),
            ("checksum_sha256", "A" * 64), ("checksum_sha256", "abc"),
            ("idempotency_key", "../unstable"),
            ("object_ref", "person@example.invalid"),
            ("object_ref", "ghp_" + "A" * 24),
        ):
            request = adapter_request()
            request[field] = invalid
            with self.subTest(adapter=field, value=invalid[:12]):
                with self.assertRaises(RecoveryAdapterError) as ctx:
                    build_adapter_descriptor(manifest(), request)
                self.assertNotIn(invalid, str(ctx.exception))
        request = adapter_request()
        request["unexpected"] = "value"
        with self.assertRaises(RecoveryAdapterError):
            build_adapter_descriptor(manifest(), request)
        with self.assertRaises(RecoveryAdapterError):
            build_adapter_descriptor(manifest("NOT_APPLICABLE"),
                                     adapter_request("google_drive"))
        bad = manifest()
        bad["version"] = 2
        with self.assertRaises(RecoveryContractError):
            build_adapter_descriptor(bad, adapter_request())

        backup, plan, proof = drill_case()
        for field, invalid in (
            ("checksum_sha256", "b" * 64), ("health_ok", False),
            ("smoke_ok", False), ("integrity_ok", False),
        ):
            bad = dict(proof)
            bad[field] = invalid
            with self.subTest(drill=field), self.assertRaises(RecoveryDrillError):
                evaluate_restore_drill(manifest(), plan, backup, bad)

    def test_sin_datos_reales(self):
        synthetic = json.dumps([
            manifest(), adapter_request(), adapter_request("google_drive", "verify"),
            verified_backup(), drill_case(),
        ], sort_keys=True).lower()
        for forbidden in ("password=", "secret=", "authorization", "access_token",
                          "https://", "http://", "@gmail", "@example", "private key"):
            self.assertNotIn(forbidden, synthetic)
        tree = ast.parse(read("tests/test_brechas_factory_59.py"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({a.name.split(".")[0] for a in node.names}
                                 & {"requests", "socket", "urllib", "subprocess"})
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0],
                                 {"requests", "socket", "urllib", "subprocess"})
        self.assertEqual(len(IDS), len(set(IDS)))

    def test_estados_unknown_explicitos(self):
        matrix = read("docs/matriz-cobertura.md")
        checks = behavioral_evidence()
        verdicts = project(matrix, checks)
        self.assertEqual(verdicts[IDS[0]], UNKNOWN,
                         "Sin PR fusionado no se cierra el contrato del Issue")
        self.assertEqual(set(EVIDENCE_GAPS), {IDS[0]})
        for key in IDS:
            with self.subTest(unit=key):
                self.assertNotIn(verdicts[key], {"LIVE", "PRODUCTION_GREEN", "CUBIERTO"})
                self.assertEqual(project(matrix, {**checks, key: False})[key], UNKNOWN)
        self.assertEqual(set(project(matrix, dict.fromkeys(IDS, False)).values()),
                         {UNKNOWN})
        backup, plan, proof = drill_case()
        proof.pop("integrity_ok")
        with self.assertRaises(RecoveryDrillError):
            evaluate_restore_drill(manifest(), plan, backup, proof)


if __name__ == "__main__":
    unittest.main()
