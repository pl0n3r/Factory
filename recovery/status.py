"""Recovery Health v1: estado común para Queue y Readiness, sin scheduler."""
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
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", re.IGNORECASE,
)


class RecoveryStatusError(ValueError):
    """Recovery Health no puede demostrarse de forma segura."""


class _Problem(Exception):
    def __init__(self, reason: str, work_class: str):
        super().__init__(reason)
        self.reason, self.work_class = reason, work_class


def derive_recovery_health(
    manifest: Any,
    verified_backup: Any | None,
    drill_result: Any | None,
    *,
    observed_at: str,
    drill_observed_at: str | None = None,
    retention_drift: bool = False,
) -> dict[str, Any]:
    recovery = validate_recovery_manifest(manifest)
    now = _time(observed_at, "observed_at")
    if type(retention_drift) is not bool:
        raise RecoveryStatusError("retention_drift debe ser boolean.")

    if verified_backup is None:
        return _health(recovery, "UNKNOWN", now, ["BACKUP_MISSING"], ["backup_missing"])

    try:
        backup = _backup(recovery, verified_backup, now)
    except _Problem as problem:
        return _health(
            recovery, "BLOCKED", now, [problem.reason], [problem.work_class]
        )

    backup_age = int((now - backup["created_at"]).total_seconds())
    backup_max = recovery["target"]["rpo_minutes"] * 60
    backup_stale = backup_age > backup_max

    if drill_result is None or drill_observed_at is None:
        reasons = ["RESTORE_DRILL_MISSING"]
        classes = ["restore_drill_failed"]
        if backup_stale:
            reasons.append("BACKUP_STALE")
            classes.append("backup_stale")
        return _health(
            recovery, "UNKNOWN", now, reasons, classes, backup=backup,
            freshness={"backup_age_seconds": backup_age,
                       "backup_max_age_seconds": backup_max},
        )

    try:
        drill_seen = _time(drill_observed_at, "drill_observed_at")
        if drill_seen > now:
            raise _Problem("DRILL_EVIDENCE_FUTURE", "restore_drill_failed")
        drill = _drill(recovery, backup, drill_result)
    except _Problem as problem:
        return _health(
            recovery, "BLOCKED", now, [problem.reason], [problem.work_class],
            backup=backup,
        )

    drill_age = int((now - drill_seen).total_seconds())
    drill_max = recovery["restore_drill"]["cadence_days"] * 86_400
    freshness = {
        "backup_age_seconds": backup_age, "backup_max_age_seconds": backup_max,
        "drill_age_seconds": drill_age, "drill_max_age_seconds": drill_max,
    }
    if drill_age > drill_max:
        reasons, classes = ["RESTORE_DRILL_STALE"], ["restore_drill_failed"]
        if backup_stale:
            reasons.append("BACKUP_STALE")
            classes.append("backup_stale")
        return _health(
            recovery, "UNKNOWN", now, reasons, classes, backup=backup,
            drill=drill, freshness=freshness,
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

    if reasons:
        if backup_stale:
            reasons.append("BACKUP_STALE")
            classes.append("backup_stale")
        state = "DEGRADED"
    elif backup_stale:
        state, reasons, classes = "UNKNOWN", ["BACKUP_STALE"], ["backup_stale"]
    else:
        state, reasons = "HEALTHY", ["RECOVERY_EVIDENCE_CURRENT"]

    return _health(
        recovery, state, now, reasons, classes, backup=backup, drill=drill,
        freshness=freshness,
    )


def recovery_work_item_classes(health: Mapping[str, Any]) -> list[str]:
    if health.get("state") not in HEALTH_STATES:
        raise RecoveryStatusError("Recovery Health state inválido.")
    classes = health.get("work_item_classes")
    if (
        not isinstance(classes, list)
        or not all(isinstance(item, str) for item in classes)
        or any(item not in WORK_ITEM_CLASSES for item in classes)
    ):
        raise RecoveryStatusError("Recovery Health contiene clase no canónica.")
    return sorted(set(classes))


def project_recovery_readiness(
    health: Mapping[str, Any], *, critical: bool = True
) -> dict[str, Any]:
    if type(critical) is not bool:
        raise RecoveryStatusError("critical debe ser boolean.")
    state = health.get("state")
    if state not in HEALTH_STATES:
        raise RecoveryStatusError("Recovery Health state inválido.")
    blocked = critical and state in {"UNKNOWN", "BLOCKED"}
    return {
        "recovery_health": state, "ready": not blocked,
        "critical_blocker": blocked,
        "reasons": list(health.get("reasons", [])),
        "work_item_classes": recovery_work_item_classes(health),
        "source": "recovery_health_v1", "recalculated": False,
    }


def _backup(recovery, value, now):
    _safe(value, "BACKUP_SENSITIVE", "backup_missing")
    data = _closed(value, {
        "version", "status", "project", "source", "backup_id", "checksum_sha256",
        "encrypted", "immutable_version_ref", "destinations", "created_at",
        "verified_at", "freshness_target_seconds", "evidence_refs", "authority",
        "execute",
    }, "BACKUP_INVALID", "backup_missing")
    source = data["source"]
    if (
        data["version"] != 1 or data["status"] != "VERIFIED"
        or data["project"] != recovery["project"] or data["encrypted"] is not True
        or data["authority"] != "unchanged" or data["execute"] is not False
        or source not in recovery["sources"] or recovery["sources"][source] != "REQUIRED"
        or data["freshness_target_seconds"] != recovery["target"]["rpo_minutes"] * 60
    ):
        raise _Problem("BACKUP_CONTRACT_INVALID", "backup_missing")

    backup_id = _opaque(data["backup_id"], "BACKUP_ID_INVALID", "backup_missing")
    checksum = _checksum(data["checksum_sha256"])
    _opaque(data["immutable_version_ref"], "IMMUTABILITY_MISSING", "offsite_missing")
    created = _time(data["created_at"], "backup.created_at")
    verified = _time(data["verified_at"], "backup.verified_at")
    if created > now or verified > now or verified < created:
        raise _Problem("BACKUP_TIMESTAMPS_INVALID", "backup_stale")
    if not _refs(data["evidence_refs"], "BACKUP_EVIDENCE_INVALID", "backup_missing"):
        raise _Problem("BACKUP_EVIDENCE_MISSING", "backup_missing")

    destinations = data["destinations"]
    if not isinstance(destinations, list):
        raise _Problem("OFFSITE_INVALID", "offsite_missing")
    primary = [
        row for row in destinations if isinstance(row, Mapping)
        and row.get("provider") == "object_storage"
        and row.get("role") == "primary_offsite" and row.get("verified") is True
    ]
    if len(primary) != 1:
        raise _Problem("OFFSITE_MISSING", "offsite_missing")
    _opaque(primary[0].get("object_ref"), "OFFSITE_REF_INVALID", "offsite_missing")

    if recovery["offsite"]["cold_copy"] == "google_drive":
        cold = [
            row for row in destinations if isinstance(row, Mapping)
            and row.get("provider") == "google_drive"
            and row.get("role") == "cold_copy" and row.get("verified") is True
        ]
        if len(cold) != 1:
            raise _Problem("OFFSITE_COLD_COPY_MISSING", "offsite_missing")

    return {"backup_id": backup_id, "source": source, "checksum_sha256": checksum,
            "created_at": created}


def _drill(recovery, backup, value):
    _safe(value, "DRILL_SENSITIVE", "restore_drill_failed")
    data = _closed(value, {
        "version", "status", "project", "source", "backup_id", "checksum_sha256",
        "target", "observed", "checks", "reasons", "evidence_refs",
        "authority", "execute",
    }, "DRILL_INVALID", "restore_drill_failed")
    if (
        data["version"] != 1 or data["status"] not in {"PASSED", "BREACHED"}
        or data["project"] != recovery["project"] or data["source"] != backup["source"]
        or data["backup_id"] != backup["backup_id"]
        or data["authority"] != "unchanged" or data["execute"] is not False
    ):
        raise _Problem("DRILL_CONTRACT_INVALID", "restore_drill_failed")
    if _checksum(data["checksum_sha256"]) != backup["checksum_sha256"]:
        raise _Problem("CHECKSUM_MISMATCH", "checksum_failed")

    target = _closed(
        data["target"], {"kind", "target_ref"},
        "DRILL_TARGET_INVALID", "restore_drill_failed",
    )
    if target["kind"] != "disposable":
        raise _Problem("DRILL_TARGET_NOT_DISPOSABLE", "restore_drill_failed")
    _opaque(target["target_ref"], "DRILL_TARGET_REF_INVALID", "restore_drill_failed")

    checks = _closed(
        data["checks"], {"health", "smoke", "integrity"},
        "DRILL_CHECKS_INVALID", "restore_drill_failed",
    )
    if not all(checks[key] is True for key in checks):
        raise _Problem("RESTORE_DRILL_FAILED", "restore_drill_failed")

    observed = _closed(
        data["observed"],
        {"rpo_seconds", "rto_seconds", "rpo_target_seconds", "rto_target_seconds"},
        "DRILL_OBSERVED_INVALID", "restore_drill_failed",
    )
    if any(type(item) is not int or item < 0 for item in observed.values()):
        raise _Problem("DRILL_OBSERVED_INVALID", "restore_drill_failed")
    if (
        observed["rpo_target_seconds"] != recovery["target"]["rpo_minutes"] * 60
        or observed["rto_target_seconds"] != recovery["target"]["rto_minutes"] * 60
    ):
        raise _Problem("DRILL_TARGETS_INCOHERENT", "restore_drill_failed")

    reasons = data["reasons"]
    allowed = {"RPO_EXCEEDED", "RTO_EXCEEDED"}
    if (
        not isinstance(reasons, list) or len(reasons) != len(set(reasons))
        or any(item not in allowed for item in reasons)
        or (data["status"] == "PASSED" and reasons)
        or (data["status"] == "BREACHED" and not reasons)
    ):
        raise _Problem("DRILL_STATUS_INCOHERENT", "restore_drill_failed")
    if not _refs(data["evidence_refs"], "DRILL_EVIDENCE_INVALID", "restore_drill_failed"):
        raise _Problem("DRILL_EVIDENCE_MISSING", "restore_drill_failed")
    return {"status": data["status"], "reasons": list(reasons),
            "observed": dict(observed)}


def _health(recovery, state, now, reasons, classes, *, backup=None, drill=None,
            freshness=None):
    return {
        "version": 1, "project": recovery["project"], "state": state,
        "observed_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "reasons": sorted(set(reasons)), "work_item_classes": sorted(set(classes)),
        "freshness": freshness or {}, "backup_ref": backup["backup_id"] if backup else None,
        "drill_status": drill["status"] if drill else None,
        "drill_observed": drill["observed"] if drill else None,
        "authority": "unchanged", "execute": False,
    }


def _closed(value, fields, reason, work_class):
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _Problem(reason, work_class)
    return value


def _opaque(value, reason, work_class):
    if (
        not isinstance(value, str) or _REF.fullmatch(value) is None
        or ".." in value or "://" in value
    ):
        raise _Problem(reason, work_class)
    return value


def _checksum(value):
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise _Problem("CHECKSUM_INVALID", "checksum_failed")
    return value


def _refs(value, reason, work_class):
    if not isinstance(value, list) or len(value) > 50:
        raise _Problem(reason, work_class)
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


def _safe(value, reason, work_class):
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise _Problem(reason, work_class) from exc
    if len(encoded.encode()) > 100_000 or _SENSITIVE.search(encoded):
        raise _Problem(reason, work_class)
