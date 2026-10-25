"""Compone roles de un hallazgo real con Team Compiler, sin despachar trabajo.

La autenticacion del snapshot corresponde al caller. No crea WorkItems.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Any

from performance.status import PerformanceStatusError, derive_performance_status
from performance.triage import triage_performance
from scripts.roles_kit import REQUIRED_ROLES, RoleError, compile_team, load_catalog

_PRIMARY = {
    "database": "dba",
    "backend": "ingenieria-software",
    "frontend": "frontend",
    "infrastructure": "infraestructura",
    "sre": "sre",
    "data": "datos-analitica",
    "architecture": "arquitectura",
    "unknown": "sre",
}
_TOPICS = {
    "database": "Investigar indices, consultas y locking sin atribuir causa",
    "backend": "Investigar algoritmos y latencia de backend",
    "frontend": "Investigar renderizado de frontend",
    "infrastructure": "Revisar capacidad de infraestructura",
    "sre": "Revisar saturacion, errores y latencia operativa",
    "data": "Investigar muestras, series y percentiles",
    "architecture": "Evaluar trade-offs arquitectonicos con evidencia",
    "unknown": "Diagnosticar causa aun no determinada",
}


class PerformanceTeamCompilerBridgeError(ValueError):
    """Evidencia o catalogo incompatible: no hay asignacion."""


def compile_performance_team(
    detection: Mapping[str, Any], *,
    evaluated_at: str,
    catalog: Mapping[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Produce una recomendacion auditada, nunca una asignacion ejecutada."""
    try:
        status = derive_performance_status(detection)
        triage = triage_performance(detection)
    except (PerformanceStatusError, ValueError, TypeError) as exc:
        raise PerformanceTeamCompilerBridgeError("Evidencia de rendimiento invalida.") from exc
    if status["evidence_state"] != "CURRENT":
        raise PerformanceTeamCompilerBridgeError("Evidencia no CURRENT.")
    _require_fresh_at(detection, evaluated_at)
    if status["classification"] not in {"PERF_DEGRADATION", "PERF_INCIDENT"}:
        return {
            "version": 1, "decision": "NO_ASSIGNMENT", "roles": [],
            "primary": None, "review": None, "authority": "unchanged",
            "execute_actions": False, "create_work_item": False, "dispatch": False,
        }

    bottleneck = triage["bottleneck"]
    if bottleneck not in _PRIMARY:
        raise PerformanceTeamCompilerBridgeError("Cuello no reconocido.")
    try:
        canonical_catalog = load_catalog()
        valid_catalog = canonical_catalog if catalog is None else catalog
    except RoleError as exc:
        raise PerformanceTeamCompilerBridgeError("Catalogo invalido.") from exc
    if (
        not isinstance(valid_catalog, Mapping)
        or not REQUIRED_ROLES.issubset(valid_catalog)
        or not set(triage["role_hints"]).issubset(valid_catalog)
        or valid_catalog != canonical_catalog
    ):
        raise PerformanceTeamCompilerBridgeError("Catalogo incompleto.")

    # Temas de diagnostico, NO causas probadas ni paths inventados.
    context = {
        "title": "Diagnostico profesional de rendimiento",
        "body": _TOPICS[bottleneck],
        "labels": ["tipo: infraestructura"],
        "files": [],
    }
    try:
        composed = compile_team(context, valid_catalog)
    except (RoleError, ValueError, TypeError) as exc:
        raise PerformanceTeamCompilerBridgeError("Team Compiler no pudo componer.") from exc
    roles = sorted(set(composed["roles"]) | set(triage["role_hints"]))
    primary = _PRIMARY[bottleneck]
    if primary not in roles or not set(roles).issubset(valid_catalog):
        raise PerformanceTeamCompilerBridgeError("Composicion incompatible.")
    review = composed["review"]
    if review is not None and review not in roles:
        raise PerformanceTeamCompilerBridgeError("Revisor incompatible.")
    return {
        "version": 1, "decision": "TEAM_RECOMMENDED",
        "project": status["project"], "surface": status["surface"],
        "metric": status["metric"], "classification": status["classification"],
        "evidence_refs": list(status["evidence_refs"]), "bottleneck": bottleneck,
        "primary": primary, "review": review, "roles": roles,
        "compiler_primary": composed["primary"],
        "contextual_profiles": list(composed["contextual_profiles"]),
        "authority": "unchanged", "execute_actions": False,
        "create_work_item": False, "dispatch": False,
    }

def _require_fresh_at(detection: Mapping[str, Any], evaluated_at: str) -> None:
    """Revalida la frescura en la evaluacion actual, nunca en un snapshot viejo."""
    if not isinstance(evaluated_at, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", evaluated_at
    ) is None:
        raise PerformanceTeamCompilerBridgeError("evaluated_at debe ser UTC exacto.")
    observed = detection.get("observed")
    freshness = detection.get("freshness")
    if not isinstance(observed, Mapping) or not isinstance(freshness, Mapping):
        raise PerformanceTeamCompilerBridgeError("Evidencia de frescura incompleta.")
    observed_at = observed.get("observed_at")
    age_before = freshness.get("age_seconds")
    max_age = freshness.get("max_age_seconds")
    if (
        not isinstance(observed_at, str)
        or type(age_before) is not int or age_before < 0
        or type(max_age) is not int or max_age <= 0
    ):
        raise PerformanceTeamCompilerBridgeError("Evidencia de frescura invalida.")
    try:
        then = datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        now = datetime.strptime(evaluated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PerformanceTeamCompilerBridgeError("Timestamp de frescura invalido.") from exc
    age_now = (now - then).total_seconds()
    if age_now < age_before or age_now > max_age:
        raise PerformanceTeamCompilerBridgeError("La evidencia ya no es CURRENT.")
