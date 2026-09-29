"""Recovery Health v1: estado explicable para Queue y Readiness, sin scheduler."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any

from recovery.contract import validate_recovery_manifest

HEALTH_STATES = frozenset({"HEALTHY", "DEGRADED", "UNKNOWN", "BLOCKED"})
WORK_ITEM_CLASSES = frozenset({
    "backup_missing", "backup_stale", "offsite_missing", "checksum_failed",
    "restore_drill_failed", "rpo_breached", "rto_breached", "retention_drift",
})
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}|\b(?:password|passwd|secret|token|api[_-]?key|cookie)\s*[:=]|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)


class RecoveryStatusError(ValueError):
    """Recovery Status no puede demostrarse de forma segura."""


class _EvidenceProblem(Exception):
    def __init__(self, reason: str, work_class: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.work_class = work_class


def derive_recovery_health(
    manifest: Any,
    verified_backup: Any | None,
    drill_result: Any | None,
    *,
    observed_at: str,
    drill_observed_at: str | None = None,
    retention_drift: bool = False,
) -> dict[str, Any]:
    """Deriva Recovery Health con freshness del propio contrato Recovery."""
    recovery = validate_recovery_manifest(manifest)
    now = _time(observed_at, "observed_at")
    if retention_drift is not True and retention_drift is not False:
        raise RecoveryStatusError("retention_drift debe ser boolean.")

    if verified_backup is None:
        return _status(
            recovery, "UNKNOWN", now, ["BACKUP_MISSING"], ["backup_missing"]
        )

    try:
        backup = _backup(recovery, verified_backup, now)
    except _EvidenceProblem as problem:
        return _status(
            recovery, "BLOCKED", now, [problem.reason],
            _work_classes(problem.work_class),
        )

    backup_age = int((now - backup["created_at"]).total_seconds())
    backup_freshness = recovery["target"]["rpo_minutes"] * 60
    if backup_age > backup_freshness:
        return _status(
            recovery, "UNKNOWN", now,
            ["BACKUP_STALE"],
            ["backup_stale"],
            backup=backup,
            freshness={"backup_age_seconds": backup_age,
                       "backup_max_age_seconds": backup_freshness},
        )

    if drill_result is None or drill_observed_at is None:
        return _status(
            recovery, "UNKNOWN", now, ["RESTORE_DRILL_MISSING"],
            ["restore_drill_failed"], backup=backup,
        )

    try:
        drill_seen = _time(drill_observed_at, "drill_observed_at")
        if drill_seen > now:
            raise _EvidenceProblem("DRILL_EVIDENCE_FUTURE", "restore_drill_failed")
        drill = _drill(recovery, backup, drill_result)
    except (_EvidenceProblem, RecoveryStatusError) as problem:
        reason = getattr(problem, "reason", "RESTORE_DRILL_INVALID")
        work_class = getattr(problem, "work_class", "restore_drill_failed")
        return _status(
            recovery, "BLOCKED", now, [reason], _work_classes(work_class),
            backup=backup,
        )

    drill_age = int((now - drill_seen).total_seconds())
    drill_freshness = recovery["restore_drill"]["cadence_days"] * 86_400
    freshness = {
        "backup_age_seconds": backup_age,
        "backup_max_age_seconds": backup_freshness,
        "drill_age_seconds": drill_age,
        "drill_max_age_seconds": drill_freshness,
    }
    if drill_age > drill_freshness:
        return _status(
            recovery, "UNKNOWN", now, ["RESTORE_DRILL_STALE"],
            ["restore_drill_failed"], backup=backup, drill=drill,
            freshness=freshness,
        )

    reasons, classes = [], []
    if retention_drift:
        reasons.append("RETENTION_DRIFT")
        classes.append("retention_drift")
    if drill["status"] == "BREACHED":
        if "RPO_EXCEEDED" in drill["reasons"]:
            reasons.append("RPO_BREACHED")
            classes.append("rpo_breached")
        if "RTO_EXCEEDED" in drill["reasons"]:
            reasons.append("RTO_BREACHED")
            classes.append("rto_breached")
    state = "DEGRADED" if reasons else "HEALTHY"
    if not reasons:
        reasons = ["RECOVERY_EVIDENCE_CURRENT"]
    return _status(
        recovery, state, now, reasons, classes, backup=backup, drill=drill,
        freshness=freshness,
    )


def recovery_work_item_classes(health: Mapping[str, Any]) -> list[str]:
    """Devuelve solo clases canónicas; no crea WorkItems ni una cola paralela."""
    if health.get("state") not in HEALTH_STATES:
        raise RecoveryStatusError("Recovery Health state inválido.")
    raw = health.get("work_item_classes")
    if (
        not isinstance(raw, list)
        or not all(isinstance(item, str) for item in raw)
        or any(item not in WORK_ITEM_CLASSES for item in raw)
    ):
        raise RecoveryStatusError("Recovery Health contiene clase no canónica.")
    return sorted(set(raw))


def project_recovery_readiness(
    health: Mapping[str, Any], *, critical: bool = True
) -> dict[str, Any]:
    """Proyecta el mismo Health; no recalcula ni genera porcentajes."""
    if critical is not True and critical is not False:
        raise RecoveryStatusError("critical debe ser boolean.")
    state = health.get("state")
    if state not in HEALTH_STATES:
        raise RecoveryStatusError("Recovery Health state inválido.")
    classes = recovery_work_item_classes(health)
    blocked = critical and state in {"UNKNOWN", "BLOCKED"}
    return {
        "recovery_health": state,
        "ready": not blocked,
        "critical_blocker": blocked,
        "reasons": list(health.get("reasons", [])),
        "work_item_classes": classes,
        "source": "recovery_health_v1",
        "recalculated": False,
    }


def _backup(
    recovery: Mapping[str, Any], value: Any, now: datetime
) -> dict[str, Any]:
    _safe_json(value, "BACKUP_SENSITIVE", "backup_missing")
    fields = {
        "version", "status", "project", "source", "backup_id", "checksum_sha256",
        "encrypted", "immutable_version_ref", "destinations", "created_at",
        "verified_at", "freshness_target_seconds", "evidence_refs", "authority",
        "execute",
    }
    data = _closed(value, fields, "BACKUP_INVALID", "backup_missing")
    source = data["source"]
    if (
        data["version"] != 1 or data["status"] != "VERIFIED"
        or data["project"] != recovery["project"] or data["encrypted"] is not True
        or data["authority"] != "unchanged" or data["execute"] is not False
        or source not in recovery["sources"] or recovery["sources"][source] != "REQUIRED"
        or data["freshness_target_seconds"] != recovery["target"]["rpo_minutes"] * 60
    ):
        raise _EvidenceProblem("BACKUP_CONTRACT_INVALID", "backup_missing")
    backup_id = _opaque(data["backup_id"], "BACKUP_ID_INVALID", "backup_missing")
    checksum = _checksum(data["checksum_sha256"])
    immutable = _opaque(
        data["immutable_version_ref"], "IMMUTABILITY_MISSING", "offsite_missing"
    )
    created = _time(data["created_at"], "backup.created_at")
    verified = _time(data["verified_at"], "backup.verified_at")
    if created > now or verified > now:
        raise _EvidenceProblem("BACKUP_EVIDENCE_FUTURE", "backup_stale")
    if verified < created:
        raise _EvidenceProblem("BACKUP_TIMESTAMPS_INVALID", "backup_stale")
    if not _refs(data["evidence_refs"], "BACKUP_EVIDENCE_INVALID", "backup_missing"):
        raise _EvidenceProblem("BACKUP_EVIDENCE_MISSING", "backup_missing")

    destinations = data["destinations"]
    if not isinstance(destinations, list):
        raise _EvidenceProblem("OFFSITE_INVALID", "offsite_missing")
    primary = [
        row for row in destinations
        if isinstance(row, Mapping)
        and row.get("provider") == "object_storage"
        and row.get("role") == "primary_offsite"
        and row.get("verified") is True
    ]
    if len(primary) != 1:
        raise _EvidenceProblem("OFFSITE_MISSING", "offsite_missing")
    _opaque(primary[0].get("object_ref"), "OFFSITE_REF_INVALID", "offsite_missing")
    if recovery["offsite"]["cold_copy"] == "google_drive":
        cold = [
            row for row in destinations
            if isinstance(row, Mapping)
            and row.get("provider") == "google_drive"
            and row.get("role") == "cold_copy"
            and row.get("verified") is True
        ]
        if len(cold) != 1:
            raise _EvidenceProblem("OFFSITE_COLD_COPY_MISSING", "offsite_missing")

    return {
        "backup_id": backup_id, "source": source, "checksum_sha256": checksum,
        "immutable_version_ref": immutable, "created_at": created,
        "verified_at": verified,
    }


def _drill(
    recovery: Mapping[str, Any],
    backup: Mapping[str, Any],
    value: Any,
) -> dict[str, Any]:
    _safe_json(value, "DRILL_SENSITIVE", "restore_drill_failed")
    fields = {
        "version", "status", "project", "source", "backup_id", "checksum_sha256",
        "target", "observed", "checks", "reasons", "evidence_refs",
        "authority", "execute",
    }
    data = _closed(value, fields, "DRILL_INVALID", "restore_drill_failed")
    if (
        data["version"] != 1 or data["status"] not in {"PASSED", "BREACHED"}
        or data["project"] != recovery["project"]
        or data["source"] != backup["source"]
        or data["backup_id"] != backup["backup_id"]
        or data["authority"] != "unchanged" or data["execute"] is not False
    ):
        raise _EvidenceProblem("DRILL_CONTRACT_INVALID", "restore_drill_failed")
    if _checksum(data["checksum_sha256"]) != backup["checksum_sha256"]:
        raise _EvidenceProblem("CHECKSUM_MISMATCH", "checksum_failed")
    target = _closed(
        data["target"], {"kind", "target_ref"}, "DRILL_TARGET_INVALID",
        "restore_drill_failed",
    )
    if target["kind"] != "disposable":
        raise _EvidenceProblem("DRILL_TARGET_NOT_DISPOSABLE", "restore_drill_failed")
    _opaque(target["target_ref"], "DRILL_TARGET_REF_INVALID", "restore_drill_failed")
    checks = _closed(
        data["checks"], {"health", "smoke", "integrity"},
        "DRILL_CHECKS_INVALID", "restore_drill_failed",
    )
    if not all(checks[key] is True for key in ("health", "smoke", "integrity")):
        raise _EvidenceProblem("RESTORE_DRILL_FAILED", "restore_drill_failed")
    observed = _closed(
        data["observed"],
        {"rpo_seconds", "rto_seconds", "rpo_target_seconds", "rto_target_seconds"},
        "DRILL_OBSERVED_INVALID", "restore_drill_failed",
    )
    for key, item in observed.items():
        if type(item) is not int or item < 0:
            raise _EvidenceProblem("DRILL_OBSERVED_INVALID", "restore_drill_failed")
    if (
        observed["rpo_target_seconds"] != recovery["target"]["rpo_minutes"] * 60
        or observed["rto_target_seconds"] != recovery["target"]["rto_minutes"] * 60
    ):
        raise _EvidenceProblem("DRILL_TARGETS_INCOHERENT", "restore_drill_failed")
    allowed_reasons = {"RPO_EXCEEDED", "RTO_EXCEEDED"}
    reasons = data["reasons"]
    if (
        not isinstance(reasons, list)
        or any(item not in allowed_reasons for item in reasons)
        or len(reasons) != len(set(reasons))
    ):
        raise _EvidenceProblem("DRILL_REASONS_INVALID", "restore_drill_failed")
    if data["status"] == "PASSED" and reasons:
        raise _EvidenceProblem("DRILL_STATUS_INCOHERENT", "restore_drill_failed")
    if data["status"] == "BREACHED" and not reasons:
        raise _EvidenceProblem("DRILL_STATUS_INCOHERENT", "restore_drill_failed")
    if not _refs(data["evidence_refs"], "DRILL_EVIDENCE_INVALID", "restore_drill_failed"):
        raise _EvidenceProblem("DRILL_EVIDENCE_MISSING", "restore_drill_failed")
    return {"status": data["status"], "reasons": list(reasons), "observed": dict(observed)}


def _status(
    recovery, state, now, reasons, classes, *, backup=None, drill=None, freshness=None
):
    return {
        "version": 1,
        "project": recovery["project"],
        "state": state,
        "observed_at": _format_time(now),
        "reasons": sorted(set(reasons)),
        "work_item_classes": sorted(set(classes)),
        "freshness": freshness or {},
        "backup_ref": backup["backup_id"] if backup else None,
        "drill_status": drill["status"] if drill else None,
        "authority": "unchanged",
        "execute": False,
    }


def _work_classes(item: str | None) -> list[str]:
    if item is None:
        return []
    if item not in WORK_ITEM_CLASSES:
        raise RecoveryStatusError("clase de WorkItem no canónica.")
    return [item]


def _closed(value, fields, reason, work_class):
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _EvidenceProblem(reason, work_class)
    return value


def _opaque(value, reason, work_class):
    if (
        not isinstance(value, str) or _REF.fullmatch(value) is None
        or ".." in value or "://" in value
    ):
        raise _EvidenceProblem(reason, work_class)
    return value


def _checksum(value):
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise _EvidenceProblem("CHECKSUM_INVALID", "checksum_failed")
    return value


def _refs(value, reason, work_class):
    if not isinstance(value, list) or len(value) > 50:
        raise _EvidenceProblem(reason, work_class)
    return sorted({_opaque(item, reason, work_class) for item in value})


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise RecoveryStatusError(f"{label} debe ser ISO-8601.")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise RecoveryStatusError(f"{label} debe ser ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise RecoveryStatusError(f"{label} debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_json(value, reason, work_class):
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise _EvidenceProblem(reason, work_class) from exc
    if len(encoded.encode()) > 100_000 or _SENSITIVE.search(encoded):
        raise _EvidenceProblem(reason, work_class)
