"""Modelos inmutables del Evolution Engine de Factory."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class EvolutionError(ValueError):
    """El lifecycle evolutivo o su evidencia no son válidos."""


@dataclass(frozen=True)
class EvolutionRecord:
    """Entrada append-only de una evolución constitucional."""

    generation: int
    stage: str
    parent_generation: int | None
    reason: str
    evidence: tuple[str, ...]
    candidate_fingerprint: str
    decision: str | None = None
    restores_generation: int | None = None


def normalize_evidence(value: Any) -> tuple[str, ...]:
    """Normaliza evidencia no vacía sin aceptar tipos ambiguos."""
    if (
        not isinstance(value, (list, tuple))
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise EvolutionError("evidence debe ser una lista no vacía de strings")
    return tuple(item.strip() for item in value)


def normalize_reason(value: Any) -> str:
    """Exige una razón explícita para cada transición."""
    if not isinstance(value, str) or not value.strip():
        raise EvolutionError("reason debe ser un string no vacío")
    return value.strip()
