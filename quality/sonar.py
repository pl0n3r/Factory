"""Normalización read-only de evidencia Sonar para Quality Health."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import math
import re
from typing import Any

from quality.contract import QualityContractError, validate_quality_contract

STATUSES = frozenset({"PASS", "FAIL", "UNKNOWN", "STALE"})
FACTORY_PROJECTS = (
    "brvtal",
    "condor",
    "controlbot",
    "factory",
    "factoryrunner",
    "grindflow",
)
_SIGNAL_ORDER = (
    "quality_gate",
    "analysis_freshness",
    "ce_task",
    "organization_line_usage",
    "visibility",
    "analysis_method",
    "coverage",
    "historical_debt",
)
_CE_STATES = frozenset({"SUCCESS", "FAILED", "CANCELED", "PENDING", "IN_PROGRESS"})
_QG_STATES = frozenset({"OK", "ERROR"})
_ANALYSIS_METHODS = frozenset({"automatic", "ci"})
_VISIBILITY = frozenset({"public", "private"})
_DEBT_TYPES = frozenset({"vulnerability", "bug", "hotspot"})
_SEVERITIES = frozenset({
    "BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO", "HIGH", "MEDIUM", "LOW",
})
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")
_URL = re.compile(r"(?i)\bhttps?://\S+")
_SENSITIVE = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)"
    r"\b\s*[:=]\s*\S+|bearer\s+[A-Za-z0-9._~+/-]{8,})"
)
_MAX_PAYLOAD_BYTES = 250_000
_MAX_REFS = 32
_MAX_CONDITIONS = 100
_MAX_DEBT_ITEMS = 10_000


class SonarEvidenceError(ValueError):
    """Evidencia Sonar inválida o insuficiente para clasificar de forma segura."""


def factory_project_catalog() -> list[str]:
    """Devuelve el catálogo explícito y acotado de proyectos Factory observables."""
    return list(FACTORY_PROJECTS)


def normalize_sonar_snapshot(
    contract: Any,
    snapshot: Any,
    *,
    observed_at: str,
) -> dict[str, Any]:
    """Normaliza un snapshot Sonar ya obtenido, sin red ni efectos laterales."""
    _finite_json(snapshot)
    try:
        quality = validate_quality_contract(contract)
    except QualityContractError as exc:
        raise SonarEvidenceError("Quality Contract inválido.") from exc

    sonar = quality.get("sonar")
    if not isinstance(sonar, Mapping):
        raise SonarEvidenceError("Sonar monitoring no configurado en Quality Contract.")
    project = quality["project"]
    if project not in FACTORY_PROJECTS:
        raise SonarEvidenceError("Proyecto fuera del catálogo Factory.")

    row = _closed(
        snapshot,
        {
            "project",
            "snapshot_at",
            "quality_gate",
            "analysis",
            "ce_task",
            "organization",
            "visibility",
            "debt",
            "evidence_refs",
        },
        "snapshot",
    )
    if row["project"] != project:
        raise SonarEvidenceError("snapshot.project no coincide con Quality Contract.")

    now = _time(observed_at, "observed_at")
    snapshot_at = _time(row["snapshot_at"], "snapshot.snapshot_at")
    snapshot_age = _age_seconds(now, snapshot_at, "snapshot.snapshot_at")
    snapshot_max_age = quality["evidence_freshness_seconds"]
    base_refs = _refs(row["evidence_refs"])

    signals = [
        _quality_gate(
            row["quality_gate"], snapshot_at, now, snapshot_max_age, base_refs
        ),
        _analysis_freshness(row["analysis"], sonar, now, base_refs),
        _ce_task(row["ce_task"], snapshot_at, now, snapshot_max_age, base_refs),
        _organization_lines(
            row["organization"], sonar, snapshot_at, now, snapshot_max_age, base_refs
        ),
        _visibility(
            row["visibility"], sonar, snapshot_at, now, snapshot_max_age, base_refs
        ),
        _analysis_method(row["analysis"], sonar, now, base_refs),
        _coverage(row["analysis"], sonar, now, base_refs),
        _historical_debt(
            row["debt"], sonar, snapshot_at, now, snapshot_max_age, base_refs
        ),
    ]
    if tuple(item["signal"] for item in signals) != _SIGNAL_ORDER:
        raise SonarEvidenceError("Orden de señales Sonar no canónico.")
    if snapshot_age > snapshot_max_age:
        signals = [
            _snapshot_stale(item, snapshot_at, snapshot_age, snapshot_max_age)
            for item in signals
        ]

    return {
        "version": 1,
        "project": project,
        "observed_at": _iso(now),
        "snapshot_freshness": {
            "state": "STALE" if snapshot_age > snapshot_max_age else "CURRENT",
            "age_seconds": snapshot_age,
            "max_age_seconds": snapshot_max_age,
        },
        "signals": signals,
        "authority": "read_only",
        "execute_actions": False,
    }


def _snapshot_stale(item, snapshot_at, age, max_age):
    if item["status"] == "STALE":
        return item
    return {
        **item,
        "status": "STALE",
        "reason": f"{item['signal']}_snapshot_stale",
        "observed_at": _iso(snapshot_at),
        "freshness": {
            "state": "STALE",
            "age_seconds": age,
            "max_age_seconds": max_age,
        },
    }


def _quality_gate(value, source_at, now, max_age, refs):
    if value is None:
        return _signal(
            "quality_gate", "UNKNOWN", "quality_gate_missing",
            source_at, now, max_age, refs, {"failed_conditions": []}
        )
    row = _closed(value, {"status", "conditions"}, "quality_gate")
    if row["status"] not in _QG_STATES:
        raise SonarEvidenceError("quality_gate.status inválido.")
    conditions = row["conditions"]
    if not isinstance(conditions, list) or len(conditions) > _MAX_CONDITIONS:
        raise SonarEvidenceError("quality_gate.conditions inválidas.")

    failed = []
    for raw in conditions:
        condition = _closed(
            raw, {"metric", "status", "actual", "threshold"}, "quality_gate.condition"
        )
        metric = _identifier(condition["metric"], "quality_gate.condition.metric")
        status = condition["status"]
        if status not in _QG_STATES:
            raise SonarEvidenceError("quality_gate.condition.status inválido.")
        item = {
            "metric": metric,
            "status": status,
            "actual": _plain_scalar(condition["actual"], "quality_gate.condition.actual"),
            "threshold": _plain_scalar(
                condition["threshold"], "quality_gate.condition.threshold"
            ),
        }
        if status == "ERROR":
            failed.append(item)

    if row["status"] == "OK" and failed:
        raise SonarEvidenceError("Quality Gate OK contiene condición fallida.")
    if row["status"] == "ERROR" and not failed:
        raise SonarEvidenceError("Quality Gate ERROR no identifica condición fallida.")

    return _signal(
        "quality_gate",
        "PASS" if row["status"] == "OK" else "FAIL",
        "quality_gate_ok" if row["status"] == "OK" else "quality_gate_failed",
        source_at,
        now,
        max_age,
        refs,
        {"failed_conditions": sorted(failed, key=lambda item: item["metric"])},
    )


def _analysis_freshness(value, sonar, now, refs):
    if value is None:
        return _signal(
            "analysis_freshness", "UNKNOWN", "analysis_missing",
            None, now, sonar["max_analysis_age_seconds"], refs, {}
        )
    row = _analysis(value)
    analyzed_at = _time(row["analyzed_at"], "analysis.analyzed_at")
    return _signal(
        "analysis_freshness", "PASS", "analysis_current",
        analyzed_at, now, sonar["max_analysis_age_seconds"], refs, {}
    )


def _ce_task(value, source_at, now, max_age, refs):
    if value is None:
        return _signal(
            "ce_task", "UNKNOWN", "ce_task_missing",
            source_at, now, max_age, refs, {"error_message": None}
        )
    row = _closed(value, {"status", "error_message"}, "ce_task")
    status = row["status"]
    if status not in _CE_STATES:
        raise SonarEvidenceError("ce_task.status inválido.")

    message = row["error_message"]
    if status == "FAILED":
        if not isinstance(message, str) or not message.strip():
            raise SonarEvidenceError("CE task FAILED requiere error_message.")
        return _signal(
            "ce_task", "FAIL", "ce_task_failed",
            source_at, now, max_age, refs,
            {"error_message": _sanitize_message(message)}
        )
    if message is not None:
        raise SonarEvidenceError("ce_task.error_message solo aplica a FAILED.")
    if status == "SUCCESS":
        result, reason = "PASS", "ce_task_success"
    elif status == "CANCELED":
        result, reason = "UNKNOWN", "ce_task_canceled"
    else:
        result, reason = "UNKNOWN", "ce_task_pending"
    return _signal(
        "ce_task", result, reason, source_at, now, max_age, refs,
        {"error_message": None},
    )


def _organization_lines(value, sonar, source_at, now, max_age, refs):
    if value is None:
        return _signal(
            "organization_line_usage", "UNKNOWN", "organization_line_usage_missing",
            source_at, now, max_age, refs, {"line_usage_percent": None}
        )
    row = _closed(value, {"line_usage_percent"}, "organization")
    usage = _percent(row["line_usage_percent"], "organization.line_usage_percent")
    threshold = sonar["max_organization_line_usage_percent"]
    failed = usage > threshold
    return _signal(
        "organization_line_usage",
        "FAIL" if failed else "PASS",
        "organization_line_usage_exceeded"
        if failed else "organization_line_usage_within_threshold",
        source_at,
        now,
        max_age,
        refs,
        {"line_usage_percent": usage, "max_percent": threshold},
    )


def _visibility(value, sonar, source_at, now, max_age, refs):
    if value is None:
        return _signal(
            "visibility", "UNKNOWN", "visibility_missing",
            source_at, now, max_age, refs,
            {"actual": None, "expected": sonar["expected_visibility"]},
        )
    if value not in _VISIBILITY:
        raise SonarEvidenceError("visibility inválida.")
    matches = value == sonar["expected_visibility"]
    return _signal(
        "visibility",
        "PASS" if matches else "FAIL",
        "visibility_matches_contract" if matches else "visibility_drift",
        source_at,
        now,
        max_age,
        refs,
        {"actual": value, "expected": sonar["expected_visibility"]},
    )


def _analysis_method(value, sonar, now, refs):
    if value is None:
        return _signal(
            "analysis_method", "UNKNOWN", "analysis_method_missing",
            None, now, sonar["max_analysis_age_seconds"], refs,
            {"actual": None, "expected": sonar["analysis_method"]},
        )
    row = _analysis(value)
    analyzed_at = _time(row["analyzed_at"], "analysis.analyzed_at")
    matches = row["method"] == sonar["analysis_method"]
    return _signal(
        "analysis_method",
        "PASS" if matches else "FAIL",
        "analysis_method_matches_contract" if matches else "analysis_method_drift",
        analyzed_at,
        now,
        sonar["max_analysis_age_seconds"],
        refs,
        {"actual": row["method"], "expected": sonar["analysis_method"]},
    )


def _coverage(value, sonar, now, refs):
    if value is None:
        return _signal(
            "coverage", "UNKNOWN", "coverage_missing",
            None, now, sonar["max_analysis_age_seconds"], refs,
            {"available": None, "analysis_method": None},
        )
    row = _analysis(value)
    analyzed_at = _time(row["analyzed_at"], "analysis.analyzed_at")
    available = row["coverage_available"]
    if row["method"] == "ci":
        status = "PASS" if available else "FAIL"
        reason = "coverage_reported" if available else "coverage_missing_for_ci"
    else:
        status = "PASS" if available else "UNKNOWN"
        reason = (
            "coverage_reported"
            if available else "coverage_not_reported_by_automatic_analysis"
        )
    return _signal(
        "coverage",
        status,
        reason,
        analyzed_at,
        now,
        sonar["max_analysis_age_seconds"],
        refs,
        {"available": available, "analysis_method": row["method"]},
    )


def _historical_debt(value, sonar, source_at, now, max_age, refs):
    if not isinstance(value, list) or len(value) > _MAX_DEBT_ITEMS:
        raise SonarEvidenceError("debt debe ser lista acotada.")

    counts: dict[tuple[str, str], int] = {}
    debt_refs = set(refs)
    oldest_age_days: int | None = None
    for raw in value:
        row = _closed(
            raw, {"type", "severity", "opened_at", "evidence_ref"}, "debt.item"
        )
        debt_type = row["type"]
        severity = row["severity"]
        if debt_type not in _DEBT_TYPES or severity not in _SEVERITIES:
            raise SonarEvidenceError("debt contiene tipo o severidad inválidos.")
        opened_at = _time(row["opened_at"], "debt.opened_at")
        age_days = _age_seconds(now, opened_at, "debt.opened_at") // 86400
        oldest_age_days = (
            age_days if oldest_age_days is None else max(oldest_age_days, age_days)
        )
        counts[(debt_type, severity)] = counts.get((debt_type, severity), 0) + 1
        debt_refs.add(_ref(row["evidence_ref"]))

    totals = {
        debt_type: sum(
            count for (kind, _), count in counts.items() if kind == debt_type
        )
        for debt_type in sorted(_DEBT_TYPES)
    }
    limits = {
        "vulnerability": sonar["max_open_vulnerabilities"],
        "bug": sonar["max_open_bugs"],
        "hotspot": sonar["max_open_hotspots"],
    }
    exceeded = [
        f"{debt_type}:{totals[debt_type]}>{limits[debt_type]}"
        for debt_type in sorted(_DEBT_TYPES)
        if totals[debt_type] > limits[debt_type]
    ]
    if oldest_age_days is not None and oldest_age_days > sonar["max_debt_age_days"]:
        exceeded.append(
            f"age_days:{oldest_age_days}>{sonar['max_debt_age_days']}"
        )
    grouped = [
        {"type": debt_type, "severity": severity, "count": count}
        for (debt_type, severity), count in sorted(counts.items())
    ]
    return _signal(
        "historical_debt",
        "FAIL" if exceeded else "PASS",
        "historical_debt_threshold_exceeded"
        if exceeded else "historical_debt_within_threshold",
        source_at,
        now,
        max_age,
        sorted(debt_refs),
        {
            "counts": grouped,
            "oldest_age_days": oldest_age_days,
            "max_debt_age_days": sonar["max_debt_age_days"],
            "exceeded": exceeded,
        },
    )


def _analysis(value):
    row = _closed(
        value, {"analyzed_at", "method", "coverage_available"}, "analysis"
    )
    if row["method"] not in _ANALYSIS_METHODS:
        raise SonarEvidenceError("analysis.method inválido.")
    if type(row["coverage_available"]) is not bool:
        raise SonarEvidenceError("analysis.coverage_available debe ser booleano.")
    _time(row["analyzed_at"], "analysis.analyzed_at")
    return row


def _signal(signal, status, reason, source_at, now, max_age, refs, details):
    if signal not in _SIGNAL_ORDER or status not in STATUSES:
        raise SonarEvidenceError("Señal Sonar inválida.")
    if not isinstance(reason, str) or not reason:
        raise SonarEvidenceError("Razón Sonar inválida.")
    if source_at is None:
        final_status = "UNKNOWN"
        freshness = {
            "state": "UNKNOWN",
            "age_seconds": None,
            "max_age_seconds": max_age,
        }
        seen = None
    else:
        age = _age_seconds(now, source_at, f"{signal}.observed_at")
        stale = age > max_age
        final_status = "STALE" if stale else status
        freshness = {
            "state": "STALE" if stale else "CURRENT",
            "age_seconds": age,
            "max_age_seconds": max_age,
        }
        seen = _iso(source_at)
        if stale:
            reason = f"{signal}_stale"
    return {
        "signal": signal,
        "status": final_status,
        "reason": reason,
        "observed_at": seen,
        "freshness": freshness,
        "evidence_refs": sorted(set(_refs(refs))),
        "details": details,
    }


def _refs(value) -> list[str]:
    if (
        not isinstance(value, (list, tuple, set))
        or not value
        or len(value) > _MAX_REFS
    ):
        raise SonarEvidenceError("evidence_refs debe ser lista no vacía y acotada.")
    refs = [_ref(item) for item in value]
    if len(refs) != len(set(refs)):
        raise SonarEvidenceError("evidence_refs contiene duplicados.")
    return sorted(refs)


def _ref(value) -> str:
    if (
        not isinstance(value, str)
        or _REF.fullmatch(value) is None
        or _URL.search(value)
        or _SENSITIVE.search(value)
    ):
        raise SonarEvidenceError("evidence_ref inválida o sensible.")
    return value


def _identifier(value, label) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise SonarEvidenceError(f"{label} inválido.")
    return value


def _plain_scalar(value, label):
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) > 200 or _URL.search(value) or _SENSITIVE.search(value):
            raise SonarEvidenceError(f"{label} contiene dato no permitido.")
        return value
    if type(value) in {int, float} and math.isfinite(value):
        return value
    raise SonarEvidenceError(f"{label} inválido.")


def _percent(value, label) -> float:
    if type(value) not in {int, float} or not math.isfinite(value):
        raise SonarEvidenceError(f"{label} inválido.")
    result = float(value)
    if not 0 <= result <= 100:
        raise SonarEvidenceError(f"{label} fuera de límites.")
    return result


def _sanitize_message(value: str) -> str:
    compact = " ".join(value.split())
    compact = _URL.sub("[url removed]", compact)
    compact = _SENSITIVE.sub("[sensitive removed]", compact)
    if not compact:
        raise SonarEvidenceError("error_message vacío tras saneamiento.")
    return compact[:500]


def _closed(value, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise SonarEvidenceError(
            f"{label} contiene campos faltantes o no permitidos."
        )
    return value


def _time(value, label) -> datetime:
    if not isinstance(value, str):
        raise SonarEvidenceError(f"{label} inválido.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SonarEvidenceError(f"{label} inválido.") from exc
    if parsed.tzinfo is None:
        raise SonarEvidenceError(f"{label} debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc)


def _age_seconds(now: datetime, seen: datetime, label: str) -> int:
    age = int((now - seen).total_seconds())
    if age < 0:
        raise SonarEvidenceError(f"{label} está en el futuro.")
    return age


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _finite_json(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SonarEvidenceError("Snapshot Sonar debe ser JSON finito.") from exc
    if len(encoded.encode()) > _MAX_PAYLOAD_BYTES:
        raise SonarEvidenceError("Snapshot Sonar excede tamaño máximo.")
