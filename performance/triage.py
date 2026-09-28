"""Triage profesional de performance sin ejecutar acciones ni ampliar autoridad."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from performance.detector import (
    BOTTLENECKS,
    CLASSIFICATIONS,
    PerformanceDetectionError,
)

ROLE_HINTS = {
    "database": ("dba", "ingenieria-software", "qa"),
    "backend": ("ingenieria-software", "qa"),
    "frontend": ("frontend", "qa"),
    "infrastructure": ("infraestructura", "qa", "sre"),
    "sre": ("qa", "sre"),
    "data": ("datos-analitica", "qa"),
    "architecture": ("arquitectura", "ingenieria-software", "qa"),
    "unknown": ("qa", "sre"),
}


def triage_performance(result: Mapping[str, Any]) -> dict[str, Any]:
    """Deriva role hints cerrados; la ejecución queda en capas posteriores."""
    if not isinstance(result, Mapping):
        raise PerformanceDetectionError("resultado de detección inválido.")
    classification = result.get("classification")
    bottleneck = result.get("bottleneck")
    if classification not in CLASSIFICATIONS or bottleneck not in BOTTLENECKS:
        raise PerformanceDetectionError("resultado de detección fuera de catálogo.")

    roles = set(ROLE_HINTS[bottleneck])
    if classification == "PERF_INCIDENT":
        roles.add("sre")
    return {
        "version": 1,
        "classification": classification,
        "bottleneck": bottleneck,
        "role_hints": sorted(roles),
        "authority": "unchanged",
        "execute_actions": False,
        "create_work_item": False,
    }
