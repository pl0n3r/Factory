"""Risk Compiler: riesgo contextual, blast radius y controles trazables."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence.project_dna import UNKNOWN, validate_project_dna
from quality.contract import (
    QualityContractError,
    quality_contract_fingerprint,
    validate_quality_contract,
)


RISK_VERSION = 1
RISK_LEVELS = ("low", "medium", "high")
LEVEL_RANK = {level: index for index, level in enumerate(RISK_LEVELS)}

BASE_CONTROLS = (
    "ci:required",
    "reviews:no-open-findings",
    "scope:claimed-paths-only",
)
MEDIUM_CONTROLS = (
    "tests:changed-scope",
    "rollback:plan",
)
HIGH_CONTROLS = (
    "tests:full-suite",
    "security:scan",
    "smoke:exact-sha",
    "context:complete-before-promotion",
)

CHANGE_TYPE_RISK = {
    "docs": "low",
    "code": "medium",
    "ci": "medium",
    "database": "high",
    "security": "high",
    "release": "high",
}
SURFACE_RISK = {
    "docs": "low",
    "web": "medium",
    "api": "medium",
    "ci": "medium",
    "database": "high",
    "release": "high",
    "auth": "high",
    "billing": "high",
}
KNOWN_SIGNALS = {
    "production",
    "destructive",
    "migration",
    "touches_auth",
    "external_integration",
}
CRITICAL_SIGNALS = {
    "production",
    "destructive",
    "migration",
    "touches_auth",
}
QUALITY_CRITICALITY_RISK = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "high",
}


class RiskCompilerError(ValueError):
    """Entrada de riesgo inválida o ambigua."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _max_level(*levels: str) -> str:
    return max(levels, key=LEVEL_RANK.__getitem__)


def _normalize_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        raise RiskCompilerError(f"{field} debe ser colección")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RiskCompilerError(f"{field} contiene valor inválido")
        result.append(item.strip().lower())
    return sorted(set(result))


def _normalize_signals(value: Any) -> dict[str, bool | str]:
    if not isinstance(value, dict) or set(value) != KNOWN_SIGNALS:
        raise RiskCompilerError("task.signals debe declarar el contrato completo")
    normalized: dict[str, bool | str] = {}
    for name in sorted(KNOWN_SIGNALS):
        signal = value[name]
        if signal is not True and signal is not False and signal != UNKNOWN:
            raise RiskCompilerError(f"task.signals.{name} inválida")
        normalized[name] = signal
    return normalized


def _normalize_task(task: Any) -> dict[str, Any]:
    expected = {"id", "title", "change_type", "surfaces", "signals"}
    if not isinstance(task, dict) or set(task) != expected:
        raise RiskCompilerError("task inválida")
    for field in ("id", "title", "change_type"):
        if not isinstance(task[field], str) or not task[field].strip():
            raise RiskCompilerError(f"task.{field} inválido")

    change_type = task["change_type"].strip().lower()
    if change_type not in CHANGE_TYPE_RISK:
        raise RiskCompilerError("change_type no admitido")

    surfaces = _normalize_strings(task["surfaces"], "task.surfaces")
    if not surfaces:
        raise RiskCompilerError("task.surfaces no puede estar vacío")

    return {
        "id": task["id"].strip(),
        "title": task["title"].strip(),
        "change_type": change_type,
        "surfaces": surfaces,
        "signals": _normalize_signals(task["signals"]),
    }


def _validated_quality_context(
    dna: dict[str, Any],
    quality_contract: Any,
) -> dict[str, Any] | None:
    declared = dna["extensions"].get("quality_contract")
    if declared is None:
        if quality_contract is not None:
            raise RiskCompilerError(
                "Quality Contract no declarado por Project DNA"
            )
        return None
    if quality_contract is None:
        raise RiskCompilerError(
            "Project DNA declara Quality Contract pero falta evidencia fuente"
        )
    try:
        normalized = validate_quality_contract(quality_contract)
        fingerprint = quality_contract_fingerprint(normalized)
    except QualityContractError as exc:
        raise RiskCompilerError("Quality Contract inválido") from exc
    if (
        declared["version"] != normalized["version"]
        or declared["fingerprint"] != fingerprint
    ):
        raise RiskCompilerError(
            "Quality Contract no coincide con fingerprint de Project DNA"
        )
    return normalized


def _controls_for(level: str) -> list[str]:
    controls = list(BASE_CONTROLS)
    if LEVEL_RANK[level] >= LEVEL_RANK["medium"]:
        controls.extend(MEDIUM_CONTROLS)
    if LEVEL_RANK[level] >= LEVEL_RANK["high"]:
        controls.extend(HIGH_CONTROLS)
    return sorted(set(controls))


def _add_signal(
    rows: list[dict[str, Any]],
    *,
    signal: str,
    source: str,
    level: str,
    reason: str,
) -> None:
    rows.append(
        {
            "signal": signal,
            "source": source,
            "risk": level,
            "reason": reason,
        }
    )


def _task_trace(
    task: dict[str, Any],
) -> tuple[str, list[str], list[dict[str, Any]]]:
    trace: list[dict[str, Any]] = []
    task_level = CHANGE_TYPE_RISK[task["change_type"]]
    _add_signal(
        trace,
        signal=f"change_type:{task['change_type']}",
        source="task.change_type",
        level=task_level,
        reason="tipo de cambio declarado",
    )
    surface_levels: list[str] = []
    for surface in task["surfaces"]:
        level = SURFACE_RISK.get(surface, "medium")
        surface_levels.append(level)
        _add_signal(
            trace,
            signal=f"surface:{surface}",
            source="task.surfaces",
            level=level,
            reason="superficie potencialmente afectada",
        )
    return task_level, surface_levels, trace


def _quality_trace(
    quality: dict[str, Any] | None,
    surfaces: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    if quality is None:
        return [], []
    declared = {row["id"]: row["criticality"] for row in quality["surfaces"]}
    levels: list[str] = []
    trace: list[dict[str, Any]] = []
    for surface in surfaces:
        if surface not in declared:
            raise RiskCompilerError(
                "task.surfaces contiene superficie no declarada por Quality Contract"
            )
        criticality = declared[surface]
        level = QUALITY_CRITICALITY_RISK[criticality]
        levels.append(level)
        _add_signal(
            trace,
            signal=f"quality:{surface}:{criticality}",
            source=f"quality_contract.surfaces.{surface}.criticality",
            level=level,
            reason="criticidad declarada por Quality Contract",
        )
    return levels, trace


def _signal_trace(
    signals: dict[str, bool | str],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    levels: list[str] = []
    unknown_critical: list[str] = []
    trace: list[dict[str, Any]] = []
    for name, value in signals.items():
        if value is True:
            level = "high" if name in CRITICAL_SIGNALS else "medium"
            levels.append(level)
            _add_signal(
                trace,
                signal=f"{name}:true",
                source=f"task.signals.{name}",
                level=level,
                reason="señal explícita de mayor blast radius",
            )
            continue
        if value != UNKNOWN:
            continue
        critical = name in CRITICAL_SIGNALS
        level = "high" if critical else "medium"
        levels.append(level)
        if critical:
            unknown_critical.append(f"task.signals.{name}")
        _add_signal(
            trace,
            signal=f"{name}:unknown",
            source=f"task.signals.{name}",
            level=level,
            reason=(
                "señal crítica desconocida: fail-safe"
                if critical
                else "incertidumbre explícita"
            ),
        )
    return levels, unknown_critical, trace


def _dna_trace(
    dna: dict[str, Any],
    task: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    surfaces = set(task["surfaces"])
    checks = (
        ("data", "database" in surfaces),
        ("hosting", bool(surfaces & {"web", "api", "release"})),
        ("integrations", task["signals"]["external_integration"] is not False),
        ("capabilities", bool(surfaces & {"auth", "billing"})),
    )
    levels: list[str] = []
    unknown_critical: list[str] = []
    trace: list[dict[str, Any]] = []
    for field, critical_here in checks:
        if dna[field] != UNKNOWN:
            continue
        level = "high" if critical_here else "medium"
        source = f"project_dna.{field}"
        levels.append(level)
        if critical_here:
            unknown_critical.append(source)
        _add_signal(
            trace,
            signal=f"dna:{field}:unknown",
            source=source,
            level=level,
            reason=(
                "contexto crítico del proyecto desconocido: fail-safe"
                if critical_here
                else "contexto del proyecto incompleto"
            ),
        )
    return levels, unknown_critical, trace


def _blast_radius(trace: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [
        {
            "area": row["signal"],
            "source": row["source"],
            "risk": row["risk"],
        }
        for row in trace
        if LEVEL_RANK[row["risk"]] >= LEVEL_RANK["medium"]
    ]
    return sorted(rows, key=lambda row: (row["risk"], row["source"], row["area"]))


def _compiled_controls(
    overall: str,
    trace: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources = sorted({row["source"] for row in trace})
    return [
        {
            "target": target,
            "required_for": overall,
            "sources": sources,
        }
        for target in _controls_for(overall)
    ]


def compile_risk(
    *,
    project_dna: Any,
    task: Any,
    quality_contract: Any = None,
) -> dict[str, Any]:
    """Compila riesgo sin ejecutar controles ni sustituir puertas humanas."""
    dna = validate_project_dna(project_dna)
    normalized_task = _normalize_task(task)
    quality = _validated_quality_context(dna, quality_contract)

    task_level, surface_levels, task_rows = _task_trace(normalized_task)
    quality_levels, quality_rows = _quality_trace(
        quality,
        normalized_task["surfaces"],
    )
    signal_levels, signal_unknown, signal_rows = _signal_trace(
        normalized_task["signals"]
    )
    dna_levels, dna_unknown, dna_rows = _dna_trace(dna, normalized_task)

    trace = [*task_rows, *quality_rows, *signal_rows, *dna_rows]
    unknown_critical = sorted(set([*signal_unknown, *dna_unknown]))
    overall = _max_level(
        task_level,
        *surface_levels,
        *signal_levels,
        *dna_levels,
        *quality_levels,
    )
    dimensions = {
        "change": task_level,
        "surface": _max_level(*surface_levels),
        "signals": _max_level(*(signal_levels or ["low"])),
        "project_context": _max_level(*(dna_levels or ["low"])),
    }
    if quality is not None:
        dimensions["quality"] = _max_level(*(quality_levels or ["low"]))

    result = {
        "version": RISK_VERSION,
        "task_id": normalized_task["id"],
        "project_dna_fingerprint": dna["fingerprint"],
        "risk": overall,
        "dimensions": dimensions,
        "blast_radius": _blast_radius(trace),
        "controls": _compiled_controls(overall, trace),
        "trace": sorted(
            trace,
            key=lambda row: (
                row["source"],
                row["signal"],
                row["risk"],
                row["reason"],
            ),
        ),
        "unknown_critical_signals": unknown_critical,
        "context_complete": not unknown_critical,
    }
    if quality is not None:
        result["quality_contract_fingerprint"] = quality_contract_fingerprint(
            quality
        )
    result["fingerprint"] = _stable_hash(result)
    return result

def validate_risk_evidence(
    *,
    project_dna: Any,
    task: Any,
    result: Any,
    quality_contract: Any = None,
) -> dict[str, Any]:
    """Recomputa Risk desde inputs fuente y exige igualdad exacta."""
    expected = compile_risk(
        project_dna=project_dna,
        task=task,
        quality_contract=quality_contract,
    )
    if not isinstance(result, dict) or result != expected:
        raise RiskCompilerError("resultado Risk no coincide con evidencia fuente")
    return expected
