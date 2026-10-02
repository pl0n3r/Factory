"""Snapshot auditable y read-only del dispatcher para Quality Health."""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from scripts.dispatcher_v2 import CANONICAL_DISPATCH_REPOS

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_SENSITIVE = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)"
    r"\b\s*[:=]|bearer\s+[A-Za-z0-9._~+/-]{8,})"
)


class DispatchAuditError(ValueError):
    """La evidencia no permite construir un snapshot auditable seguro."""


def _closed(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise DispatchAuditError(f"{label} fuera del contrato.")
    return value


def _safe(value: Any) -> None:
    if isinstance(value, str):
        if _SENSITIVE.search(value):
            raise DispatchAuditError("evidencia sensible rechazada.")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _safe(key)
            _safe(item)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _safe(item)


def _ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_REF.fullmatch(value) is None:
        raise DispatchAuditError(f"{label} inválida.")
    return value


def _dispatch_signature(value: Any) -> dict[str, Any]:
    row = _closed(
        value,
        {"agent_id", "signature", "repository_ref", "idle_metric"},
        "dispatch_signature",
    )
    agent_id = row["agent_id"]
    repository_ref = row["repository_ref"]
    if (
        not isinstance(agent_id, str)
        or _AGENT_ID.fullmatch(agent_id) is None
        or repository_ref not in CANONICAL_DISPATCH_REPOS
        or row["signature"] != f"Despacho ({agent_id})"
    ):
        raise DispatchAuditError("dispatch_signature incoherente.")

    idle_metric = row["idle_metric"]
    if idle_metric is not None:
        metric = _closed(
            idle_metric,
            {
                "agent_id", "repository_ref", "idle_seconds", "threshold_seconds",
                "alert", "quality_health",
            },
            "dispatch_signature.idle_metric",
        )
        if (
            metric["agent_id"] != agent_id
            or metric["repository_ref"] != repository_ref
            or type(metric["idle_seconds"]) is not int
            or metric["idle_seconds"] < 0
            or type(metric["threshold_seconds"]) is not int
            or metric["threshold_seconds"] <= 0
            or type(metric["alert"]) is not bool
            or metric["quality_health"]
            != ("DEGRADED" if metric["alert"] else "HEALTHY")
        ):
            raise DispatchAuditError("dispatch_signature.idle_metric incoherente.")

    return {
        "agent_id": agent_id,
        "signature": row["signature"],
        "repository_ref": repository_ref,
    }


def _watchdog(value: Any) -> dict[str, Any]:
    row = _closed(
        value,
        {
            "version", "repository_ref", "state", "severity", "reasons",
            "provenance", "evidence_fingerprint", "freshness", "source",
            "authority", "execute_actions",
        },
        "watchdog",
    )
    if (
        row["version"] != 1
        or row["repository_ref"] not in CANONICAL_DISPATCH_REPOS
        or row["state"] not in {"UNKNOWN", "BLOCKED"}
        or row["severity"] not in {"S1", "S2", "S3", "UNKNOWN"}
        or row["source"] != "unattended_watchdog_v1"
        or row["authority"] != "unchanged"
        or row["execute_actions"] is not False
    ):
        raise DispatchAuditError("watchdog fuera del contrato.")

    reasons = row["reasons"]
    if (
        not isinstance(reasons, list)
        or not reasons
        or len(reasons) != len(set(reasons))
    ):
        raise DispatchAuditError("watchdog reasons ambiguas.")
    normalized_reasons = [_ref(item, "watchdog.reason") for item in reasons]

    provenance = row["provenance"]
    if (
        not isinstance(provenance, list)
        or not provenance
        or len(provenance) != len(set(provenance))
    ):
        raise DispatchAuditError("watchdog provenance ambigua.")
    normalized_provenance = [_ref(item, "watchdog.provenance") for item in provenance]

    fingerprint = row["evidence_fingerprint"]
    if (
        not isinstance(fingerprint, str)
        or _HEX64.fullmatch(fingerprint) is None
        or fingerprint not in normalized_provenance
    ):
        raise DispatchAuditError("watchdog fingerprint/provenance incoherente.")

    freshness = _closed(
        row["freshness"],
        {"state", "age_seconds", "max_age_seconds"},
        "watchdog.freshness",
    )
    if (
        freshness["state"] != "CURRENT"
        or type(freshness["age_seconds"]) is not int
        or freshness["age_seconds"] < 0
        or type(freshness["max_age_seconds"]) is not int
        or freshness["max_age_seconds"] <= 0
        or freshness["age_seconds"] > freshness["max_age_seconds"]
    ):
        raise DispatchAuditError("watchdog evidence stale o desconocida.")

    return {
        "repository_ref": row["repository_ref"],
        "state": row["state"],
        "severity": row["severity"],
        "reasons": normalized_reasons,
        "provenance": normalized_provenance,
        "evidence_fingerprint": fingerprint,
        "freshness": dict(freshness),
        "source": row["source"],
    }


def _no_work(value: Any) -> dict[str, Any]:
    row = _closed(
        value,
        {
            "valid", "reason", "repository_count", "reasons",
            "initial_fingerprint", "final_fingerprint",
        },
        "no_work",
    )
    if (
        row["valid"] is not True
        or row["reason"] != "no_work_verified"
        or row["repository_count"] != len(CANONICAL_DISPATCH_REPOS)
    ):
        raise DispatchAuditError("NO_WORK no está probado.")

    reasons = row["reasons"]
    if not isinstance(reasons, Mapping) or set(reasons) != CANONICAL_DISPATCH_REPOS:
        raise DispatchAuditError("NO_WORK inventory/provenance incompleta.")
    normalized_reasons = {}
    for repository, reason in reasons.items():
        if not isinstance(reason, str) or not reason.strip():
            raise DispatchAuditError("NO_WORK reason inválida.")
        normalized_reasons[repository] = _ref(reason.strip(), "no_work.reason")

    initial = row["initial_fingerprint"]
    final = row["final_fingerprint"]
    if (
        not isinstance(initial, str)
        or _HEX64.fullmatch(initial) is None
        or not isinstance(final, str)
        or _HEX64.fullmatch(final) is None
        or initial != final
    ):
        raise DispatchAuditError("NO_WORK recheck no es estable.")

    return {
        "reasons": dict(sorted(normalized_reasons.items())),
        "initial_fingerprint": initial,
        "final_fingerprint": final,
        "repository_count": row["repository_count"],
    }


def dispatch_audit_snapshot(
    *,
    dispatch_signature: Mapping[str, Any],
    watchdog_evidence: Mapping[str, Any],
    no_work_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Vincula evidencia canónica sin recalcular ranking, watchdog ni NO_WORK."""
    _safe((dispatch_signature, watchdog_evidence, no_work_evidence))

    dispatch = _dispatch_signature(dispatch_signature)
    watchdog = _watchdog(watchdog_evidence)
    no_work = _no_work(no_work_evidence)

    if dispatch["repository_ref"] != watchdog["repository_ref"]:
        raise DispatchAuditError("repository_ref no coincide entre fuentes.")
    if "proven_idle" not in watchdog["reasons"]:
        raise DispatchAuditError("NO_WORK requiere watchdog proven_idle.")
    if "capacity:unknown" in watchdog["reasons"]:
        raise DispatchAuditError("NO_WORK contradice actividad con capacidad desconocida.")

    return {
        "version": 1,
        "agent_id": dispatch["agent_id"],
        "signature": dispatch["signature"],
        "repository_ref": dispatch["repository_ref"],
        "watchdog": {
            "state": watchdog["state"],
            "severity": watchdog["severity"],
            "source": watchdog["source"],
            "reasons": list(watchdog["reasons"]),
            "evidence_fingerprint": watchdog["evidence_fingerprint"],
        },
        "no_work": {
            "reason": "no_work_verified",
            "repository_count": no_work["repository_count"],
            "reasons": dict(no_work["reasons"]),
            "initial_fingerprint": no_work["initial_fingerprint"],
            "final_fingerprint": no_work["final_fingerprint"],
        },
        "provenance": {
            "dispatch": {
                "agent_id": dispatch["agent_id"],
                "repository_ref": dispatch["repository_ref"],
            },
            "watchdog": list(watchdog["provenance"]),
            "no_work": {
                "initial_fingerprint": no_work["initial_fingerprint"],
                "final_fingerprint": no_work["final_fingerprint"],
            },
        },
        "freshness": {
            "watchdog": dict(watchdog["freshness"]),
            "no_work_recheck_stable": True,
        },
        "authority": "unchanged",
        "execute_actions": False,
        "recalculated": False,
    }
