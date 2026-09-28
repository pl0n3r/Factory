"""Cálculo determinista de Progress + Readiness para README Contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import re
from typing import Any


class ProgressReadinessError(ValueError):
    """Input o snapshot fuera del contrato Progress + Readiness v1."""


EVIDENCE_STATES = {
    "SATISFIED",
    "UNSATISFIED",
    "UNKNOWN",
    "STALE",
    "NOT_APPLICABLE",
}
BLOCKER_STATES = {"OPEN", "RESOLVED", "UNKNOWN", "STALE"}
SEVERITIES = {"critical", "high", "medium", "low", "info"}
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
MAX_DIMENSIONS = 50
MAX_MILESTONES = 100
MAX_BLOCKERS = 100
MAX_EVIDENCE_REFS = 50
MAX_WEIGHT = 1_000_000


def calculate_progress_readiness(
    payload: Mapping[str, Any],
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normaliza evidencia y produce el payload canónico v1."""
    source = _normalize_input(payload)
    (
        dimension_rows,
        progress_parts,
        readiness_parts,
        degraded_evidence,
    ) = _calculate_dimensions(source["dimensions"])

    progress = _aggregate_metric(progress_parts)
    readiness = _aggregate_metric(readiness_parts)
    progress["status"] = (
        "MEASURED" if progress["basis_points"] is not None else "UNKNOWN"
    )

    blockers = source["blockers"]
    for blocker in blockers:
        if blocker["state"] in {"UNKNOWN", "STALE"}:
            degraded_evidence = True
    critical_blockers = [
        blocker
        for blocker in blockers
        if blocker["severity"] == "critical" and blocker["state"] != "RESOLVED"
    ]

    if readiness["basis_points"] is None:
        readiness_status = "UNKNOWN"
    elif critical_blockers:
        readiness_status = "BLOCKED"
    elif readiness["basis_points"] == 10_000:
        readiness_status = "READY"
    else:
        readiness_status = "BUILDING"
    readiness["status"] = readiness_status

    target = source["target"]
    result: dict[str, Any] = {
        "version": 1,
        "target": target,
        "target_fingerprint": _target_fingerprint(target, source["dimensions"]),
        "observed_at": source["observed_at"],
        "progress": progress,
        "readiness": readiness,
        "evidence_freshness": "DEGRADED" if degraded_evidence else "CURRENT",
        "dimensions": dimension_rows,
        "blockers": blockers,
        "critical_blockers": critical_blockers,
    }
    result["trend"] = _no_trend()
    if previous is not None:
        result["trend"] = _compare(previous, result)
    return result


def _calculate_dimensions(
    dimensions: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[tuple[str, int, Fraction, dict[str, Any]]],
    list[tuple[str, int, Fraction, dict[str, Any]]],
    bool,
]:
    """Calcula detalle y contribuciones por dimensión sin efectos externos."""
    rows: list[dict[str, Any]] = []
    progress_parts: list[tuple[str, int, Fraction, dict[str, Any]]] = []
    readiness_parts: list[tuple[str, int, Fraction, dict[str, Any]]] = []
    degraded = False
    for dimension in dimensions:
        progress_detail, progress_fraction = _dimension_metric(
            dimension, "progress_state"
        )
        readiness_detail, readiness_fraction = _dimension_metric(
            dimension, "readiness_state"
        )
        degraded = degraded or bool(
            progress_detail["unknown_or_stale"]
            or readiness_detail["unknown_or_stale"]
        )
        rows.append(
            {
                "id": dimension["id"],
                "label": dimension["label"],
                "weight": dimension["weight"],
                "progress": progress_detail,
                "readiness": readiness_detail,
                "milestones": dimension["milestones"],
            }
        )
        if progress_fraction is not None:
            progress_parts.append(
                (dimension["id"], dimension["weight"], progress_fraction, progress_detail)
            )
        if readiness_fraction is not None:
            readiness_parts.append(
                (dimension["id"], dimension["weight"], readiness_fraction, readiness_detail)
            )
    return rows, progress_parts, readiness_parts, degraded


def canonical_payload(snapshot: Mapping[str, Any]) -> str:
    """Serialización estable para README, tests y consumidores posteriores."""
    _validate_snapshot_shape(snapshot)
    return json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def compare_progress_readiness(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Compara snapshots; cambios de target son rebaseline, no tendencia."""
    _validate_snapshot_shape(previous)
    _validate_snapshot_shape(current)
    return _compare(previous, current)


def _normalize_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ProgressReadinessError("payload debe ser objeto.")
    _exact_keys(
        payload,
        {"version", "target", "dimensions", "blockers", "observed_at"},
        "payload",
    )
    if payload["version"] != 1:
        raise ProgressReadinessError("version debe ser 1.")

    target = _normalize_target(payload["target"])
    observed_at = _timestamp(payload["observed_at"], "observed_at")
    dimensions = _normalize_dimensions(payload["dimensions"])
    blockers = _normalize_blockers(payload["blockers"])
    return {
        "version": 1,
        "target": target,
        "dimensions": dimensions,
        "blockers": blockers,
        "observed_at": observed_at,
    }


def _normalize_target(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise ProgressReadinessError("target debe ser objeto.")
    _exact_keys(raw, {"id", "label", "scope", "version"}, "target")
    return {
        "id": _identifier(raw["id"], "target.id"),
        "label": _text(raw["label"], "target.label", 160),
        "scope": _text(raw["scope"], "target.scope", 200),
        "version": _text(raw["version"], "target.version", 80),
    }


def _normalize_dimensions(raw: Any) -> list[dict[str, Any]]:
    if (
        not isinstance(raw, list)
        or not raw
        or len(raw) > MAX_DIMENSIONS
    ):
        raise ProgressReadinessError("dimensions debe ser lista no vacía y acotada.")

    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ProgressReadinessError("dimension debe ser objeto.")
        _exact_keys(item, {"id", "label", "weight", "milestones"}, "dimension")
        dimension_id = _identifier(item["id"], "dimension.id")
        if dimension_id in seen:
            raise ProgressReadinessError("dimension.id duplicado.")
        seen.add(dimension_id)
        result.append(
            {
                "id": dimension_id,
                "label": _text(item["label"], "dimension.label", 160),
                "weight": _weight(item["weight"], "dimension.weight"),
                "milestones": _normalize_milestones(item["milestones"]),
            }
        )
    result.sort(key=lambda row: row["id"])
    return result


def _normalize_milestones(raw: Any) -> list[dict[str, Any]]:
    if (
        not isinstance(raw, list)
        or not raw
        or len(raw) > MAX_MILESTONES
    ):
        raise ProgressReadinessError("milestones debe ser lista no vacía y acotada.")

    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ProgressReadinessError("milestone debe ser objeto.")
        _exact_keys(
            item,
            {
                "id",
                "label",
                "weight",
                "progress_state",
                "readiness_state",
                "evidence_refs",
            },
            "milestone",
        )
        milestone_id = _identifier(item["id"], "milestone.id")
        if milestone_id in seen:
            raise ProgressReadinessError("milestone.id duplicado.")
        seen.add(milestone_id)
        progress_state = _enum(
            item["progress_state"], EVIDENCE_STATES, "milestone.progress_state"
        )
        readiness_state = _enum(
            item["readiness_state"], EVIDENCE_STATES, "milestone.readiness_state"
        )
        evidence_refs = _refs(item["evidence_refs"], "milestone.evidence_refs")
        if (
            progress_state != "UNKNOWN" or readiness_state != "UNKNOWN"
        ) and not evidence_refs:
            raise ProgressReadinessError(
                "Todo estado demostrado/stale/N/A requiere evidence_refs."
            )
        result.append(
            {
                "id": milestone_id,
                "label": _text(item["label"], "milestone.label", 160),
                "weight": _weight(item["weight"], "milestone.weight"),
                "progress_state": progress_state,
                "readiness_state": readiness_state,
                "evidence_refs": evidence_refs,
            }
        )
    result.sort(key=lambda row: row["id"])
    return result


def _normalize_blockers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > MAX_BLOCKERS:
        raise ProgressReadinessError("blockers debe ser lista acotada.")
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ProgressReadinessError("blocker debe ser objeto.")
        _exact_keys(
            item,
            {"id", "label", "severity", "state", "evidence_refs"},
            "blocker",
        )
        blocker_id = _identifier(item["id"], "blocker.id")
        if blocker_id in seen:
            raise ProgressReadinessError("blocker.id duplicado.")
        seen.add(blocker_id)
        state = _enum(item["state"], BLOCKER_STATES, "blocker.state")
        evidence_refs = _refs(item["evidence_refs"], "blocker.evidence_refs")
        if state != "UNKNOWN" and not evidence_refs:
            raise ProgressReadinessError("Blocker conocido/stale requiere evidence_refs.")
        result.append(
            {
                "id": blocker_id,
                "label": _text(item["label"], "blocker.label", 160),
                "severity": _enum(item["severity"], SEVERITIES, "blocker.severity"),
                "state": state,
                "evidence_refs": evidence_refs,
            }
        )
    result.sort(key=lambda row: (row["severity"], row["id"]))
    return result


def _dimension_metric(
    dimension: Mapping[str, Any],
    state_field: str,
) -> tuple[dict[str, Any], Fraction | None]:
    milestones = dimension["milestones"]
    applicable = [
        milestone
        for milestone in milestones
        if milestone[state_field] != "NOT_APPLICABLE"
    ]
    denominator = sum(milestone["weight"] for milestone in applicable)
    satisfied = sum(
        milestone["weight"]
        for milestone in applicable
        if milestone[state_field] == "SATISFIED"
    )
    evidence = sorted(
        {
            ref
            for milestone in milestones
            for ref in milestone["evidence_refs"]
        }
    )
    unknown_or_stale = [
        milestone["id"]
        for milestone in applicable
        if milestone[state_field] in {"UNKNOWN", "STALE"}
    ]

    if denominator == 0:
        return (
            {
                "status": "NOT_APPLICABLE",
                "basis_points": None,
                "percent": None,
                "satisfied_weight": 0,
                "applicable_weight": 0,
                "evidence_refs": evidence,
                "unknown_or_stale": [],
            },
            None,
        )

    fraction = Fraction(satisfied, denominator)
    basis_points = _to_basis_points(fraction)
    return (
        {
            "status": "MEASURED",
            "basis_points": basis_points,
            "percent": _percent(basis_points),
            "satisfied_weight": satisfied,
            "applicable_weight": denominator,
            "evidence_refs": evidence,
            "unknown_or_stale": unknown_or_stale,
        },
        fraction,
    )


def _aggregate_metric(
    parts: list[tuple[str, int, Fraction, dict[str, Any]]],
) -> dict[str, Any]:
    if not parts:
        return {
            "basis_points": None,
            "percent": None,
            "dimension_weight": 0,
            "contributions": [],
        }

    denominator = sum(weight for _, weight, _, _ in parts)
    weighted = sum(
        (Fraction(weight) * score for _, weight, score, _ in parts),
        start=Fraction(0),
    )
    score = weighted / denominator
    basis_points = _to_basis_points(score)
    contributions = [
        {
            "dimension_id": dimension_id,
            "weight": weight,
            "basis_points": _to_basis_points(fraction),
            "evidence_refs": detail["evidence_refs"],
            "unknown_or_stale": detail["unknown_or_stale"],
        }
        for dimension_id, weight, fraction, detail in parts
    ]
    return {
        "basis_points": basis_points,
        "percent": _percent(basis_points),
        "dimension_weight": denominator,
        "contributions": contributions,
    }


def _compare(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_snapshot_shape(previous)
    _validate_snapshot_shape(current)
    if previous["target_fingerprint"] != current["target_fingerprint"]:
        return {
            "kind": "REBASELINE",
            "comparable": False,
            "progress_delta_basis_points": None,
            "readiness_delta_basis_points": None,
            "causes": [
                {
                    "type": "target_change",
                    "from": previous["target"],
                    "to": current["target"],
                }
            ],
        }

    progress_delta = _delta(
        previous["progress"]["basis_points"], current["progress"]["basis_points"]
    )
    readiness_delta = _delta(
        previous["readiness"]["basis_points"], current["readiness"]["basis_points"]
    )
    causes = _change_causes(previous, current)
    return {
        "kind": "TREND",
        "comparable": True,
        "progress_delta_basis_points": progress_delta,
        "readiness_delta_basis_points": readiness_delta,
        "causes": causes,
    }


def _change_causes(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> list[dict[str, Any]]:
    old = _milestone_map(previous)
    new = _milestone_map(current)
    causes: list[dict[str, Any]] = []
    for key in sorted(set(old) | set(new)):
        if old.get(key) == new.get(key):
            continue
        dimension_id, milestone_id = key
        causes.append(
            {
                "type": "milestone_change",
                "dimension_id": dimension_id,
                "milestone_id": milestone_id,
                "from": old.get(key),
                "to": new.get(key),
                "evidence_refs": (
                    new.get(key, {}).get("evidence_refs", [])
                    if isinstance(new.get(key), Mapping)
                    else []
                ),
            }
        )

    old_blockers = {row["id"]: row for row in previous["blockers"]}
    new_blockers = {row["id"]: row for row in current["blockers"]}
    for blocker_id in sorted(set(old_blockers) | set(new_blockers)):
        if old_blockers.get(blocker_id) == new_blockers.get(blocker_id):
            continue
        causes.append(
            {
                "type": "blocker_change",
                "blocker_id": blocker_id,
                "from": old_blockers.get(blocker_id),
                "to": new_blockers.get(blocker_id),
            }
        )
    return causes


def _milestone_map(snapshot: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (dimension["id"], milestone["id"]): {
            "weight": milestone["weight"],
            "progress_state": milestone["progress_state"],
            "readiness_state": milestone["readiness_state"],
            "evidence_refs": milestone["evidence_refs"],
        }
        for dimension in snapshot["dimensions"]
        for milestone in dimension["milestones"]
    }


def _validate_snapshot_shape(snapshot: Mapping[str, Any]) -> None:
    if not isinstance(snapshot, Mapping):
        raise ProgressReadinessError("snapshot debe ser objeto.")
    required = {
        "version",
        "target",
        "target_fingerprint",
        "observed_at",
        "progress",
        "readiness",
        "evidence_freshness",
        "dimensions",
        "blockers",
        "critical_blockers",
        "trend",
    }
    if set(snapshot) != required or snapshot.get("version") != 1:
        raise ProgressReadinessError("snapshot no coincide con contrato v1.")


def _no_trend() -> dict[str, Any]:
    return {
        "kind": "UNAVAILABLE",
        "comparable": False,
        "progress_delta_basis_points": None,
        "readiness_delta_basis_points": None,
        "causes": [],
    }


def _target_fingerprint(
    target: Mapping[str, str],
    dimensions: list[dict[str, Any]],
) -> str:
    identity = {
        "target": {
            "id": target["id"],
            "scope": target["scope"],
            "version": target["version"],
        },
        "baseline": [
            {
                "id": dimension["id"],
                "weight": dimension["weight"],
                "milestones": [
                    {
                        "id": milestone["id"],
                        "weight": milestone["weight"],
                        "progress_applicable": (
                            milestone["progress_state"] != "NOT_APPLICABLE"
                        ),
                        "readiness_applicable": (
                            milestone["readiness_state"] != "NOT_APPLICABLE"
                        ),
                    }
                    for milestone in dimension["milestones"]
                ],
            }
            for dimension in dimensions
        ],
    }
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _delta(previous: Any, current: Any) -> int | None:
    if not isinstance(previous, int) or not isinstance(current, int):
        return None
    return current - previous


def _to_basis_points(value: Fraction) -> int:
    numerator = value.numerator * 10_000
    denominator = value.denominator
    return (2 * numerator + denominator) // (2 * denominator)


def _percent(basis_points: int) -> str:
    return f"{basis_points // 100}.{basis_points % 100:02d}"


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ProgressReadinessError(f"{label} contiene campos faltantes o no permitidos.")


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ProgressReadinessError(f"{label} inválido.")
    return value


def _text(value: Any, label: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ProgressReadinessError(f"{label} debe ser texto.")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > max_length:
        raise ProgressReadinessError(f"{label} vacío o fuera de límites.")
    return normalized


def _weight(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProgressReadinessError(f"{label} debe ser entero.")
    if value < 1 or value > MAX_WEIGHT:
        raise ProgressReadinessError(f"{label} fuera de límites.")
    return value


def _refs(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > MAX_EVIDENCE_REFS
        or not all(isinstance(item, str) for item in value)
    ):
        raise ProgressReadinessError(f"{label} debe ser lista acotada de refs.")
    refs: set[str] = set()
    for item in value:
        normalized = item.strip()
        if not normalized or _REF.fullmatch(normalized) is None:
            raise ProgressReadinessError(f"{label} contiene ref inválida.")
        refs.add(normalized)
    return sorted(refs)


def _enum(value: Any, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProgressReadinessError(f"{label} fuera del catálogo.")
    return value


def _timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ProgressReadinessError(f"{label} debe ser ISO-8601.")
    parsed = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(parsed)
    except ValueError as exc:
        raise ProgressReadinessError(f"{label} debe ser ISO-8601.") from exc
    if timestamp.tzinfo is None:
        raise ProgressReadinessError(f"{label} debe incluir zona horaria.")
    return timestamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
