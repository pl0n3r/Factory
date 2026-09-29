"""Recovery restore drill v1: plan y resultado declarativos sobre target descartable."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any

from recovery.contract import validate_recovery_manifest

_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}|\b(?:password|passwd|secret|token|api[_-]?key|cookie)\s*[:=]|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)

_STEP_KINDS = (
    "select_verified_backup", "validate_checksum", "decrypt",
    "prepare_disposable_target", "restore", "compatible_migrations",
    "health", "smoke", "integrity", "report",
)


class RecoveryDrillError(ValueError):
    """Restore drill inválido o no demostrable."""


def build_restore_drill_plan(
    manifest: Any, verified_backup: Any, target: Any
) -> dict[str, Any]:
    recovery = validate_recovery_manifest(manifest)
    backup = _verified_backup(recovery, verified_backup)
    target_data = _closed(target, {"kind", "target_ref"}, "target")
    _safe_json(target_data)
    if target_data["kind"] != "disposable":
        raise RecoveryDrillError("target.kind debe ser disposable.")
    target_ref = _opaque(target_data["target_ref"], "target_ref")

    return {
        "version": 1,
        "project": recovery["project"],
        "source": backup["source"],
        "backup_id": backup["backup_id"],
        "checksum_sha256": backup["checksum_sha256"],
        "recovery_point_at": backup["created_at"],
        "target": {"kind": "disposable", "target_ref": target_ref},
        "steps": [
            {"kind": kind, "authority": "unchanged", "execute": False}
            for kind in _STEP_KINDS
        ],
        "authority": "unchanged",
        "execute": False,
    }


def evaluate_restore_drill(
    manifest: Any,
    plan: Any,
    verified_backup: Any,
    evidence: Any,
) -> dict[str, Any]:
    recovery = validate_recovery_manifest(manifest)
    backup = _verified_backup(recovery, verified_backup)
    drill = _plan(recovery, plan, backup)
    data = _closed(evidence, {
        "backup_id", "checksum_sha256", "health_ok", "smoke_ok", "integrity_ok",
        "incident_at", "started_at", "completed_at", "evidence_refs",
    }, "evidence")
    _safe_json(data)

    if _opaque(data["backup_id"], "backup_id") != backup["backup_id"]:
        raise RecoveryDrillError("evidence backup_id no coincide.")
    checksum = _checksum(data["checksum_sha256"])
    if checksum != backup["checksum_sha256"]:
        raise RecoveryDrillError("evidence checksum no coincide.")
    if not all(data[key] is True for key in ("health_ok", "smoke_ok", "integrity_ok")):
        raise RecoveryDrillError("health, smoke e integrity deben pasar.")

    recovery_point = _time(backup["created_at"], "backup.created_at")
    incident = _time(data["incident_at"], "incident_at")
    started = _time(data["started_at"], "started_at")
    completed = _time(data["completed_at"], "completed_at")
    if not recovery_point <= incident <= started <= completed:
        raise RecoveryDrillError("timestamps del drill fuera de orden.")

    refs = _refs(data["evidence_refs"])
    if not refs:
        raise RecoveryDrillError("evidence_refs no puede estar vacío.")

    rpo = int((incident - recovery_point).total_seconds())
    rto = int((completed - started).total_seconds())
    rpo_target = recovery["target"]["rpo_minutes"] * 60
    rto_target = recovery["target"]["rto_minutes"] * 60
    reasons = []
    if rpo > rpo_target:
        reasons.append("RPO_EXCEEDED")
    if rto > rto_target:
        reasons.append("RTO_EXCEEDED")

    return {
        "version": 1,
        "status": "BREACHED" if reasons else "PASSED",
        "project": recovery["project"],
        "source": backup["source"],
        "backup_id": backup["backup_id"],
        "checksum_sha256": checksum,
        "target": drill["target"],
        "observed": {
            "rpo_seconds": rpo, "rto_seconds": rto,
            "rpo_target_seconds": rpo_target, "rto_target_seconds": rto_target,
        },
        "checks": {"health": True, "smoke": True, "integrity": True},
        "reasons": reasons,
        "evidence_refs": refs,
        "authority": "unchanged",
        "execute": False,
    }


def _verified_backup(recovery: Mapping[str, Any], value: Any) -> Mapping[str, Any]:
    fields = {
        "version", "status", "project", "source", "backup_id", "checksum_sha256",
        "encrypted", "immutable_version_ref", "destinations", "created_at",
        "verified_at", "freshness_target_seconds", "evidence_refs", "authority",
        "execute",
    }
    data = _closed(value, fields, "verified_backup")
    _safe_json(data)
    source = data["source"]
    if (
        data["version"] != 1 or data["status"] != "VERIFIED"
        or data["project"] != recovery["project"] or data["encrypted"] is not True
        or data["authority"] != "unchanged" or data["execute"] is not False
        or source not in recovery["sources"] or recovery["sources"][source] != "REQUIRED"
        or data["freshness_target_seconds"] != recovery["target"]["rpo_minutes"] * 60
    ):
        raise RecoveryDrillError("backup no cumple contrato VERIFIED.")
    _opaque(data["backup_id"], "backup_id")
    _checksum(data["checksum_sha256"])
    _opaque(data["immutable_version_ref"], "immutable_version_ref")
    created = _time(data["created_at"], "created_at")
    verified = _time(data["verified_at"], "verified_at")
    if verified < created:
        raise RecoveryDrillError("backup timestamps inválidos.")
    if not isinstance(data["destinations"], list):
        raise RecoveryDrillError("backup destinations inválidos.")
    primary = [
        row for row in data["destinations"]
        if isinstance(row, Mapping)
        and row.get("provider") == "object_storage"
        and row.get("role") == "primary_offsite"
        and row.get("verified") is True
    ]
    if len(primary) != 1:
        raise RecoveryDrillError("backup primary offsite no verificado.")
    _opaque(primary[0].get("object_ref"), "primary.object_ref")
    if not _refs(data["evidence_refs"]):
        raise RecoveryDrillError("backup evidence_refs inválidos.")
    return data


def _plan(
    recovery: Mapping[str, Any], value: Any, backup: Mapping[str, Any]
) -> Mapping[str, Any]:
    fields = {
        "version", "project", "source", "backup_id", "checksum_sha256",
        "recovery_point_at", "target", "steps", "authority", "execute",
    }
    data = _closed(value, fields, "plan")
    _safe_json(data)
    if (
        data["version"] != 1 or data["project"] != recovery["project"]
        or data["source"] != backup["source"]
        or data["backup_id"] != backup["backup_id"]
        or data["checksum_sha256"] != backup["checksum_sha256"]
        or data["recovery_point_at"] != backup["created_at"]
        or data["authority"] != "unchanged" or data["execute"] is not False
    ):
        raise RecoveryDrillError("plan no coincide con backup/manifest.")
    target = _closed(data["target"], {"kind", "target_ref"}, "plan.target")
    if target["kind"] != "disposable":
        raise RecoveryDrillError("plan target debe ser disposable.")
    _opaque(target["target_ref"], "plan.target_ref")
    steps = data["steps"]
    if not isinstance(steps, list) or len(steps) != len(_STEP_KINDS):
        raise RecoveryDrillError("plan steps inválidos.")
    for expected, step in zip(_STEP_KINDS, steps):
        row = _closed(step, {"kind", "authority", "execute"}, "plan.step")
        if (
            row["kind"] != expected or row["authority"] != "unchanged"
            or row["execute"] is not False
        ):
            raise RecoveryDrillError("plan step no cumple contrato.")
    return data


def _closed(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise RecoveryDrillError(f"{label} contiene campos faltantes/no permitidos.")
    return value


def _opaque(value: Any, label: str) -> str:
    if (
        not isinstance(value, str) or _REF.fullmatch(value) is None
        or ".." in value or "://" in value
    ):
        raise RecoveryDrillError(f"{label} debe ser ref opaca segura.")
    return value


def _checksum(value: Any) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise RecoveryDrillError("checksum_sha256 inválido.")
    return value


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise RecoveryDrillError(f"{label} debe ser ISO-8601.")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise RecoveryDrillError(f"{label} debe ser ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise RecoveryDrillError(f"{label} debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc)


def _refs(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > 50:
        raise RecoveryDrillError("evidence_refs debe ser lista acotada.")
    return sorted({_opaque(item, "evidence_ref") for item in value})


def _safe_json(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RecoveryDrillError("payload debe ser JSON finito.") from exc
    if len(encoded.encode()) > 100_000:
        raise RecoveryDrillError("payload excede tamaño máximo.")
    if _SENSITIVE.search(encoded):
        raise RecoveryDrillError("payload contiene forma sensible no permitida.")
