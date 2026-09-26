"""Risk Compiler: riesgo contextual, blast radius y controles trazables."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence.project_dna import UNKNOWN, validate_project_dna


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


def compile_risk(*, project_dna: Any, task: Any) -> dict[str, Any]:
    """Compila riesgo sin ejecutar controles ni sustituir puertas humanas."""
    dna = validate_project_dna(project_dna)
    normalized_task = _normalize_task(task)

    trace: list[dict[str, Any]] = []
    task_level = CHANGE_TYPE_RISK[normalized_task["change_type"]]
    _add_signal(
        trace,
        signal=f"change_type:{normalized_task['change_type']}",
        source="task.change_type",
        level=task_level,
        reason="tipo de cambio declarado",
    )

    surface_levels: list[str] = []
    for surface in normalized_task["surfaces"]:
        level = SURFACE_RISK.get(surface, "medium")
        surface_levels.append(level)
        _add_signal(
            trace,
            signal=f"surface:{surface}",
            source="task.surfaces",
            level=level,
            reason="superficie potencialmente afectada",
        )

    unknown_critical: list[str] = []
    signal_levels: list[str] = []
    for name, value in normalized_task["signals"].items():
        if value is True:
            level = "high" if name in CRITICAL_SIGNALS else "medium"
            signal_levels.append(level)
            _add_signal(
                trace,
                signal=f"{name}:true",
                source=f"task.signals.{name}",
                level=level,
                reason="señal explícita de mayor blast radius",
            )
        elif value == UNKNOWN:
            if name in CRITICAL_SIGNALS:
                unknown_critical.append(f"task.signals.{name}")
                signal_levels.append("high")
                _add_signal(
                    trace,
                    signal=f"{name}:unknown",
                    source=f"task.signals.{name}",
                    level="high",
                    reason="señal crítica desconocida: fail-safe",
                )
            else:
                signal_levels.append("medium")
                _add_signal(
                    trace,
                    signal=f"{name}:unknown",
                    source=f"task.signals.{name}",
                    level="medium",
                    reason="incertidumbre explícita",
                )

    dna_levels: list[str] = []
    surfaces = set(normalized_task["surfaces"])
    dna_checks = (
        ("data", "database" in surfaces),
        ("hosting", bool(surfaces & {"web", "api", "release"})),
        ("integrations", normalized_task["signals"]["external_integration"] is not False),
        ("capabilities", bool(surfaces & {"auth", "billing"})),
    )
    for field, critical_here in dna_checks:
        value = dna[field]
        if value == UNKNOWN:
            level = "high" if critical_here else "medium"
            dna_levels.append(level)
            source = f"project_dna.{field}"
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

    levels = [task_level, *surface_levels, *signal_levels, *dna_levels]
    overall = _max_level(*levels)

    blast_radius = []
    for row in trace:
        if LEVEL_RANK[row["risk"]] >= LEVEL_RANK["medium"]:
            blast_radius.append(
                {
                    "area": row["signal"],
                    "source": row["source"],
                    "risk": row["risk"],
                }
            )
    blast_radius.sort(key=lambda item: (item["risk"], item["source"], item["area"]))

    controls = []
    contributing_sources = sorted({row["source"] for row in trace})
    for target in _controls_for(overall):
        controls.append(
            {
                "target": target,
                "required_for": overall,
                "sources": contributing_sources,
            }
        )

    dimensions = {
        "change": task_level,
        "surface": _max_level(*surface_levels),
        "signals": _max_level(*(signal_levels or ["low"])),
        "project_context": _max_level(*(dna_levels or ["low"])),
    }

    result = {
        "version": RISK_VERSION,
        "task_id": normalized_task["id"],
        "project_dna_fingerprint": dna["fingerprint"],
        "risk": overall,
        "dimensions": dimensions,
        "blast_radius": blast_radius,
        "controls": controls,
        "trace": sorted(
            trace,
            key=lambda row: (row["source"], row["signal"], row["risk"], row["reason"]),
        ),
        "unknown_critical_signals": sorted(set(unknown_critical)),
        "context_complete": not unknown_critical,
    }
    result["fingerprint"] = _stable_hash(result)
    return result


def validate_risk_evidence(
    *,
    project_dna: Any,
    task: Any,
    result: Any,
) -> dict[str, Any]:
    """Recomputa Risk desde inputs fuente y exige igualdad exacta."""
    expected = compile_risk(project_dna=project_dna, task=task)
    if not isinstance(result, dict) or result != expected:
        raise RiskCompilerError("resultado Risk no coincide con evidencia fuente")
    return expected
