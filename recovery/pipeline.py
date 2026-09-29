"""Recovery backup pipeline v1: plan y evidencia verificable sin I/O externo."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any

from recovery.adapters import build_adapter_descriptor
from recovery.contract import validate_recovery_manifest

SOURCES = frozenset({"database", "media", "repository"})
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}|"
    r"\b(?:password|passwd|secret|token|api[_-]?key|cookie)\s*[:=]|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)


class RecoveryPipelineError(ValueError):
    """Plan o evidencia Recovery fuera del contrato."""


def build_backup_pipeline(manifest: Any, request: Any) -> dict[str, Any]:
    """Construye el pipeline mínimo como datos; nunca ejecuta operaciones."""
    recovery = validate_recovery_manifest(manifest)
    _size_and_sensitive(request)
    data = _map(
        request,
        {
            "source", "backup_id", "snapshot_ref", "encrypted_ref",
            "object_storage_ref", "cold_copy_ref", "checksum_sha256",
            "idempotency_key",
        },
        "request",
    )
    source = _enum(data["source"], SOURCES, "source")
    if recovery["sources"][source] != "REQUIRED":
        raise RecoveryPipelineError("source no es REQUIRED en el manifest.")

    backup_id = _opaque(data["backup_id"], "backup_id")
    snapshot_ref = _opaque(data["snapshot_ref"], "snapshot_ref")
    encrypted_ref = _opaque(data["encrypted_ref"], "encrypted_ref")
    primary_ref = _opaque(data["object_storage_ref"], "object_storage_ref")
    checksum = _checksum(data["checksum_sha256"])
    idempotency = _opaque(data["idempotency_key"], "idempotency_key")

    cold_required = recovery["offsite"]["cold_copy"] == "google_drive"
    cold_ref = data["cold_copy_ref"]
    if cold_required:
        cold_ref = _opaque(cold_ref, "cold_copy_ref")
    elif cold_ref != "NOT_APPLICABLE":
        raise RecoveryPipelineError(
            "cold_copy_ref debe ser NOT_APPLICABLE cuando Drive no aplica."
        )

    primary_upload = build_adapter_descriptor(
        recovery,
        _adapter_request(
            "object_storage", "upload", primary_ref, checksum, f"{idempotency}:upload"
        ),
    )
    primary_verify = build_adapter_descriptor(
        recovery,
        _adapter_request(
            "object_storage", "verify", primary_ref, checksum, f"{idempotency}:verify"
        ),
    )

    steps: list[dict[str, Any]] = [
        _step("snapshot", source, snapshot_ref),
        _step("checksum", source, checksum),
        _step("encrypt", source, encrypted_ref),
        _step("upload_primary", source, primary_upload["descriptor_id"]),
        _step("verify_primary", source, primary_verify["descriptor_id"]),
    ]
    destinations = [
        {
            "provider": "object_storage",
            "role": "primary_offsite",
            "object_ref": primary_ref,
            "upload_descriptor_id": primary_upload["descriptor_id"],
            "verify_descriptor_id": primary_verify["descriptor_id"],
        }
    ]

    if cold_required:
        cold_upload = build_adapter_descriptor(
            recovery,
            _adapter_request(
                "google_drive", "upload", cold_ref, checksum, f"{idempotency}:cold"
            ),
        )
        steps.append(_step("cold_copy", source, cold_upload["descriptor_id"]))
        destinations.append(
            {
                "provider": "google_drive",
                "role": "cold_copy",
                "object_ref": cold_ref,
                "upload_descriptor_id": cold_upload["descriptor_id"],
                "verify_descriptor_id": "NOT_APPLICABLE",
            }
        )

    steps.append(_step("record_evidence", source, backup_id))
    return {
        "version": 1,
        "project": recovery["project"],
        "source": source,
        "backup_id": backup_id,
        "checksum_sha256": checksum,
        "pipeline_state": "PLANNED",
        "steps": steps,
        "destinations": destinations,
        "requirements": {
            "encryption_required": True,
            "immutability_required": True,
            "primary_offsite_required": True,
            "cold_copy_required": cold_required,
            "rpo_minutes": recovery["target"]["rpo_minutes"],
            "rto_minutes": recovery["target"]["rto_minutes"],
        },
        "authority": "unchanged",
        "execute": False,
    }


def verify_backup_evidence(
    manifest: Any,
    pipeline: Mapping[str, Any],
    evidence: Any,
) -> dict[str, Any]:
    """Valida evidencia observada; VERIFIED solo existe con todas las pruebas contractuales."""
    recovery = validate_recovery_manifest(manifest)
    _validate_pipeline_identity(recovery, pipeline)
    _size_and_sensitive(evidence)
    data = _map(
        evidence,
        {
            "backup_id", "source", "checksum_sha256", "encrypted",
            "primary_verified", "primary_ref", "immutable_version_ref",
            "cold_copy_verified", "cold_copy_ref", "created_at", "verified_at",
            "evidence_refs",
        },
        "evidence",
    )
    if _opaque(data["backup_id"], "backup_id") != pipeline["backup_id"]:
        raise RecoveryPipelineError("evidence backup_id no coincide.")
    if _enum(data["source"], SOURCES, "source") != pipeline["source"]:
        raise RecoveryPipelineError("evidence source no coincide.")
    checksum = _checksum(data["checksum_sha256"])
    if checksum != pipeline["checksum_sha256"]:
        raise RecoveryPipelineError("evidence checksum no coincide.")
    if data["encrypted"] is not True or data["primary_verified"] is not True:
        raise RecoveryPipelineError(
            "backup REQUIRED necesita encryption y primary verification."
        )

    primary = _destination(pipeline, "object_storage")
    if _opaque(data["primary_ref"], "primary_ref") != primary["object_ref"]:
        raise RecoveryPipelineError("evidence primary_ref no coincide.")
    immutable_ref = _opaque(
        data["immutable_version_ref"], "immutable_version_ref"
    )

    cold_required = recovery["offsite"]["cold_copy"] == "google_drive"
    if cold_required:
        cold = _destination(pipeline, "google_drive")
        if data["cold_copy_verified"] is not True:
            raise RecoveryPipelineError("cold-copy requerida no verificada.")
        cold_ref = _opaque(data["cold_copy_ref"], "cold_copy_ref")
        if cold_ref != cold["object_ref"]:
            raise RecoveryPipelineError("evidence cold_copy_ref no coincide.")
        cold_state: bool | str = True
    else:
        if (
            data["cold_copy_verified"] != "NOT_APPLICABLE"
            or data["cold_copy_ref"] != "NOT_APPLICABLE"
        ):
            raise RecoveryPipelineError("cold-copy debe ser NOT_APPLICABLE.")
        cold_ref = "NOT_APPLICABLE"
        cold_state = "NOT_APPLICABLE"

    created_at = _timestamp(data["created_at"], "created_at")
    verified_at = _timestamp(data["verified_at"], "verified_at")
    if verified_at < created_at:
        raise RecoveryPipelineError("verified_at no puede anteceder created_at.")
    refs = _refs(data["evidence_refs"])
    if not refs:
        raise RecoveryPipelineError("evidence_refs no puede estar vacío.")

    return {
        "version": 1,
        "status": "VERIFIED",
        "project": recovery["project"],
        "source": pipeline["source"],
        "backup_id": pipeline["backup_id"],
        "checksum_sha256": checksum,
        "encrypted": True,
        "immutable_version_ref": immutable_ref,
        "destinations": [
            {
                "provider": "object_storage",
                "role": "primary_offsite",
                "object_ref": primary["object_ref"],
                "verified": True,
            },
            *(
                [{
                    "provider": "google_drive",
                    "role": "cold_copy",
                    "object_ref": cold_ref,
                    "verified": cold_state,
                }]
                if cold_required
                else []
            ),
        ],
        "created_at": created_at,
        "verified_at": verified_at,
        "freshness_target_seconds": recovery["target"]["rpo_minutes"] * 60,
        "evidence_refs": refs,
        "authority": "unchanged",
        "execute": False,
    }


def _adapter_request(
    provider: str,
    operation: str,
    object_ref: str,
    checksum: str,
    idempotency: str,
) -> dict[str, str]:
    return {
        "provider": provider,
        "operation": operation,
        "object_ref": object_ref,
        "checksum_sha256": checksum,
        "idempotency_key": idempotency,
    }


def _step(kind: str, source: str, ref: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "source": source,
        "ref": ref,
        "authority": "unchanged",
        "execute": False,
    }


def _destination(pipeline: Mapping[str, Any], provider: str) -> Mapping[str, Any]:
    matches = [
        row for row in pipeline.get("destinations", [])
        if isinstance(row, Mapping) and row.get("provider") == provider
    ]
    if len(matches) != 1:
        raise RecoveryPipelineError("pipeline destinations inválidos.")
    return matches[0]


def _validate_pipeline_identity(
    recovery: Mapping[str, Any],
    pipeline: Mapping[str, Any],
) -> None:
    if not isinstance(pipeline, Mapping):
        raise RecoveryPipelineError("pipeline debe ser objeto.")
    required = {
        "version", "project", "source", "backup_id", "checksum_sha256",
        "pipeline_state", "steps", "destinations", "requirements",
        "authority", "execute",
    }
    if set(pipeline) != required or pipeline.get("version") != 1:
        raise RecoveryPipelineError("pipeline no coincide con v1.")
    if pipeline["project"] != recovery["project"]:
        raise RecoveryPipelineError("pipeline project no coincide.")
    if pipeline["pipeline_state"] != "PLANNED":
        raise RecoveryPipelineError("pipeline_state inválido.")
    if pipeline["authority"] != "unchanged" or pipeline["execute"] is not False:
        raise RecoveryPipelineError("pipeline no puede ampliar authority ni ejecutar.")


def _map(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise RecoveryPipelineError(
            f"{label} contiene campos faltantes o no permitidos."
        )
    return value


def _enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise RecoveryPipelineError(f"{label} fuera del catálogo.")
    return value


def _opaque(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or _REF.fullmatch(value) is None
        or ".." in value
        or "://" in value
    ):
        raise RecoveryPipelineError(f"{label} debe ser ref opaca segura.")
    return value


def _checksum(value: Any) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RecoveryPipelineError("checksum_sha256 inválido.")
    return value


def _refs(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > 50
        or not all(isinstance(item, str) for item in value)
    ):
        raise RecoveryPipelineError("evidence_refs debe ser lista acotada.")
    return sorted({_opaque(item, "evidence_ref") for item in value})


def _timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise RecoveryPipelineError(f"{label} debe ser ISO-8601.")
    parsed = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(parsed)
    except ValueError as exc:
        raise RecoveryPipelineError(f"{label} debe ser ISO-8601.") from exc
    if timestamp.tzinfo is None:
        raise RecoveryPipelineError(f"{label} debe incluir zona horaria.")
    return (
        timestamp.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _size_and_sensitive(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RecoveryPipelineError("payload debe ser JSON finito.") from exc
    if len(encoded.encode()) > 100_000:
        raise RecoveryPipelineError("payload excede tamaño máximo.")
    if _SENSITIVE.search(encoded):
        raise RecoveryPipelineError("payload contiene forma sensible no permitida.")
