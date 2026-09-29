"""Recovery pipeline v1: plan/evidence declarativos y fail-closed."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from recovery.adapters import build_adapter_descriptor
from recovery.contract import validate_recovery_manifest

SOURCES = frozenset({"database", "media", "repository"})
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}|\b(?:password|passwd|secret|token|api[_-]?key|cookie)\s*[:=]|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", re.IGNORECASE,
)


class RecoveryPipelineError(ValueError):
    """Plan/evidencia Recovery inválidos."""


def build_backup_pipeline(manifest: Any, request: Any) -> dict[str, Any]:
    recovery = validate_recovery_manifest(manifest)
    data = _closed(request, {
        "source", "backup_id", "snapshot_ref", "encrypted_ref",
        "object_storage_ref", "cold_copy_ref", "checksum_sha256",
        "idempotency_key",
    }, "request")
    _safe_json(data)
    source = _choice(data["source"], SOURCES, "source")
    if recovery["sources"][source] != "REQUIRED":
        raise RecoveryPipelineError("source no es REQUIRED en el manifest.")

    backup_id = _opaque(data["backup_id"], "backup_id")
    checksum = _checksum(data["checksum_sha256"])
    refs = {
        "snapshot": _opaque(data["snapshot_ref"], "snapshot_ref"),
        "encrypted": _opaque(data["encrypted_ref"], "encrypted_ref"),
        "primary": _opaque(data["object_storage_ref"], "object_storage_ref"),
    }
    root_key = _opaque(data["idempotency_key"], "idempotency_key")
    cold_required = recovery["offsite"]["cold_copy"] == "google_drive"
    cold_ref = data["cold_copy_ref"]
    if cold_required:
        refs["cold"] = _opaque(cold_ref, "cold_copy_ref")
    elif cold_ref != "NOT_APPLICABLE":
        raise RecoveryPipelineError("cold_copy_ref debe ser NOT_APPLICABLE.")

    primary_upload = _adapter(
        recovery, "object_storage", "upload", refs["primary"], checksum,
        _child_key(root_key, "upload"),
    )
    primary_verify = _adapter(
        recovery, "object_storage", "verify", refs["primary"], checksum,
        _child_key(root_key, "verify"),
    )
    steps = [
        _step("snapshot", source, refs["snapshot"]),
        _step("checksum", source, checksum),
        _step("encrypt", source, refs["encrypted"]),
        _step("upload_primary", source, primary_upload["descriptor_id"]),
        _step("verify_primary", source, primary_verify["descriptor_id"]),
    ]
    destinations = [{
        "provider": "object_storage", "role": "primary_offsite",
        "object_ref": refs["primary"],
        "upload_descriptor_id": primary_upload["descriptor_id"],
        "verify_descriptor_id": primary_verify["descriptor_id"],
    }]
    if cold_required:
        cold_upload = _adapter(
            recovery, "google_drive", "upload", refs["cold"], checksum,
            _child_key(root_key, "cold"),
        )
        steps.append(_step("cold_copy", source, cold_upload["descriptor_id"]))
        destinations.append({
            "provider": "google_drive", "role": "cold_copy",
            "object_ref": refs["cold"],
            "upload_descriptor_id": cold_upload["descriptor_id"],
            "verify_descriptor_id": "NOT_APPLICABLE",
        })
    steps.append(_step("record_evidence", source, backup_id))

    return {
        "version": 1, "project": recovery["project"], "source": source,
        "backup_id": backup_id, "checksum_sha256": checksum,
        "pipeline_state": "PLANNED", "steps": steps, "destinations": destinations,
        "requirements": {
            "encryption_required": True, "immutability_required": True,
            "primary_offsite_required": True, "cold_copy_required": cold_required,
            "rpo_minutes": recovery["target"]["rpo_minutes"],
            "rto_minutes": recovery["target"]["rto_minutes"],
        },
        "authority": "unchanged", "execute": False,
    }


def verify_backup_evidence(
    manifest: Any, pipeline: Mapping[str, Any], evidence: Any
) -> dict[str, Any]:
    recovery = validate_recovery_manifest(manifest)
    _pipeline(recovery, pipeline)
    data = _closed(evidence, {
        "backup_id", "source", "checksum_sha256", "encrypted",
        "primary_verified", "primary_ref", "immutable_version_ref",
        "cold_copy_verified", "cold_copy_ref", "created_at", "verified_at",
        "evidence_refs",
    }, "evidence")
    _safe_json(data)

    if _opaque(data["backup_id"], "backup_id") != pipeline["backup_id"]:
        raise RecoveryPipelineError("evidence backup_id no coincide.")
    if _choice(data["source"], SOURCES, "source") != pipeline["source"]:
        raise RecoveryPipelineError("evidence source no coincide.")
    checksum = _checksum(data["checksum_sha256"])
    if checksum != pipeline["checksum_sha256"]:
        raise RecoveryPipelineError("evidence checksum no coincide.")
    if data["encrypted"] is not True or data["primary_verified"] is not True:
        raise RecoveryPipelineError("encryption/primary verification requeridos.")

    primary = _destination(pipeline, "object_storage")
    if _opaque(data["primary_ref"], "primary_ref") != primary["object_ref"]:
        raise RecoveryPipelineError("primary_ref no coincide.")
    immutable = _opaque(data["immutable_version_ref"], "immutable_version_ref")

    cold_required = recovery["offsite"]["cold_copy"] == "google_drive"
    destinations = [{
        "provider": "object_storage", "role": "primary_offsite",
        "object_ref": primary["object_ref"], "verified": True,
    }]
    if cold_required:
        cold = _destination(pipeline, "google_drive")
        if data["cold_copy_verified"] is not True:
            raise RecoveryPipelineError("cold-copy requerida no verificada.")
        cold_ref = _opaque(data["cold_copy_ref"], "cold_copy_ref")
        if cold_ref != cold["object_ref"]:
            raise RecoveryPipelineError("cold_copy_ref no coincide.")
        destinations.append({
            "provider": "google_drive", "role": "cold_copy",
            "object_ref": cold_ref, "verified": True,
        })
    elif (
        data["cold_copy_verified"] != "NOT_APPLICABLE"
        or data["cold_copy_ref"] != "NOT_APPLICABLE"
    ):
        raise RecoveryPipelineError("cold-copy debe ser NOT_APPLICABLE.")

    created = _timestamp(data["created_at"], "created_at")
    verified = _timestamp(data["verified_at"], "verified_at")
    if verified < created:
        raise RecoveryPipelineError("verified_at no puede anteceder created_at.")
    evidence_refs = _refs(data["evidence_refs"])
    if not evidence_refs:
        raise RecoveryPipelineError("evidence_refs no puede estar vacío.")

    return {
        "version": 1, "status": "VERIFIED", "project": recovery["project"],
        "source": pipeline["source"], "backup_id": pipeline["backup_id"],
        "checksum_sha256": checksum, "encrypted": True,
        "immutable_version_ref": immutable, "destinations": destinations,
        "created_at": created, "verified_at": verified,
        "freshness_target_seconds": recovery["target"]["rpo_minutes"] * 60,
        "evidence_refs": evidence_refs, "authority": "unchanged", "execute": False,
    }


def _adapter(manifest, provider, operation, ref, checksum, key):
    return build_adapter_descriptor(manifest, {
        "provider": provider, "operation": operation, "object_ref": ref,
        "checksum_sha256": checksum, "idempotency_key": key,
    })


def _child_key(root: str, stage: str) -> str:
    return hashlib.sha256(f"{root}:{stage}".encode()).hexdigest()


def _step(kind: str, source: str, ref: str) -> dict[str, Any]:
    return {"kind": kind, "source": source, "ref": ref,
            "authority": "unchanged", "execute": False}


def _destination(pipeline: Mapping[str, Any], provider: str) -> Mapping[str, Any]:
    rows = [
        row for row in pipeline.get("destinations", [])
        if isinstance(row, Mapping) and row.get("provider") == provider
    ]
    if len(rows) != 1:
        raise RecoveryPipelineError("pipeline destinations inválidos.")
    return rows[0]


def _pipeline(recovery: Mapping[str, Any], value: Any) -> None:
    required = {
        "version", "project", "source", "backup_id", "checksum_sha256",
        "pipeline_state", "steps", "destinations", "requirements",
        "authority", "execute",
    }
    if (
        not isinstance(value, Mapping) or set(value) != required
        or value.get("version") != 1 or value.get("project") != recovery["project"]
        or value.get("pipeline_state") != "PLANNED"
        or value.get("authority") != "unchanged" or value.get("execute") is not False
    ):
        raise RecoveryPipelineError("pipeline no coincide con contrato v1.")


def _closed(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise RecoveryPipelineError(f"{label} contiene campos faltantes/no permitidos.")
    return value


def _choice(value: Any, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise RecoveryPipelineError(f"{label} fuera del catálogo.")
    return value


def _opaque(value: Any, label: str) -> str:
    if (
        not isinstance(value, str) or _REF.fullmatch(value) is None
        or ".." in value or "://" in value
    ):
        raise RecoveryPipelineError(f"{label} debe ser ref opaca segura.")
    return value


def _checksum(value: Any) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise RecoveryPipelineError("checksum_sha256 inválido.")
    return value


def _refs(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > 50:
        raise RecoveryPipelineError("evidence_refs debe ser lista acotada.")
    return sorted({_opaque(item, "evidence_ref") for item in value})


def _timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise RecoveryPipelineError(f"{label} debe ser ISO-8601.")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise RecoveryPipelineError(f"{label} debe ser ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise RecoveryPipelineError(f"{label} debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _safe_json(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RecoveryPipelineError("payload debe ser JSON finito.") from exc
    if len(encoded.encode()) > 100_000:
        raise RecoveryPipelineError("payload excede tamaño máximo.")
    if _SENSITIVE.search(encoded):
        raise RecoveryPipelineError("payload contiene forma sensible no permitida.")
