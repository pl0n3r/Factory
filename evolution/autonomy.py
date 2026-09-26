"""Autonomy Engine: autonomía ganada, auditable y constitucionalmente acotada."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from evolution.constitution import PROTECTED_INVARIANTS


AUTONOMY_VERSION = 1
AUTONOMY_LEVELS = (
    "observe",
    "propose",
    "shadow",
    "supervised",
    "autonomous",
)
LEVEL_INDEX = {level: index for index, level in enumerate(AUTONOMY_LEVELS)}
FAILURE_TARGETS = {
    "minor": 1,
    "major": 2,
    "critical": 4,
}
FORBIDDEN_EXTERNAL_AUTHORITY = (
    "money",
    "legal",
    "personal_data",
    "irreversible_delete",
)
CONSTITUTIONAL_AUTHORITY = {
    "source": "constitution",
    "protected_invariants": list(PROTECTED_INVARIANTS),
    "external_permissions_added": [],
    "forbidden_external_authority": list(FORBIDDEN_EXTERNAL_AUTHORITY),
}


class AutonomyError(ValueError):
    """Transición o evidencia de autonomía inválida."""


@dataclass(frozen=True)
class AutonomyRecord:
    sequence: int
    capability: str
    level: str
    previous_level: str | None
    action: str
    reason: str
    evidence: tuple[str, ...]
    fitness_fingerprint: str | None
    risk_fingerprint: str | None
    authority_fingerprint: str


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


AUTHORITY_FINGERPRINT = _stable_hash(CONSTITUTIONAL_AUTHORITY)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AutonomyError(f"{field} debe ser string no vacío")
    return value.strip()


def _evidence(value: Any) -> tuple[str, ...]:
    if (
        not isinstance(value, (list, tuple))
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise AutonomyError("evidence debe ser lista no vacía")
    normalized = tuple(item.strip() for item in value)
    if len(normalized) > 32:
        raise AutonomyError("evidence excede el límite")
    return normalized


def _validate_fitness(value: Any) -> str:
    if not isinstance(value, dict):
        raise AutonomyError("fitness inválido")
    required = {
        "claim",
        "can_claim_improvement",
        "protected_regressions",
        "missing_dimensions",
        "confidence",
        "fingerprint",
    }
    if not required.issubset(value):
        raise AutonomyError("fitness incompleto")
    if not isinstance(value["fingerprint"], str) or len(value["fingerprint"]) != 64:
        raise AutonomyError("fitness fingerprint inválido")
    if value["protected_regressions"]:
        raise AutonomyError("fitness degrada dimensión protegida")
    confidence = value["confidence"]
    if (
        not isinstance(confidence, dict)
        or confidence.get("ratio") != 1.0
        or value["missing_dimensions"]
    ):
        raise AutonomyError("fitness incompleto o con incertidumbre")
    if value["claim"] not in {"equal", "improved"}:
        raise AutonomyError("fitness no demuestra estabilidad suficiente")
    return value["fingerprint"]


def _validate_risk(value: Any, target_level: str) -> str:
    if not isinstance(value, dict):
        raise AutonomyError("risk inválido")
    required = {"risk", "context_complete", "unknown_critical_signals", "fingerprint"}
    if not required.issubset(value):
        raise AutonomyError("risk incompleto")
    if not isinstance(value["fingerprint"], str) or len(value["fingerprint"]) != 64:
        raise AutonomyError("risk fingerprint inválido")
    if value["context_complete"] is not True or value["unknown_critical_signals"]:
        raise AutonomyError("riesgo conserva incertidumbre crítica")
    if value["risk"] not in {"low", "medium", "high"}:
        raise AutonomyError("nivel de riesgo inválido")
    if target_level == "autonomous" and value["risk"] == "high":
        raise AutonomyError("riesgo high no puede promover a autonomous")
    return value["fingerprint"]


class AutonomyEngine:
    """Escalera de autonomía por capacidad, sin ampliar autoridad externa."""

    def __init__(
        self,
        capability: str,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> None:
        self._capability = _text(capability, "capability")
        self._history: list[AutonomyRecord] = [
            AutonomyRecord(
                sequence=0,
                capability=self._capability,
                level="observe",
                previous_level=None,
                action="initialize",
                reason=_text(reason, "reason"),
                evidence=_evidence(evidence),
                fitness_fingerprint=None,
                risk_fingerprint=None,
                authority_fingerprint=AUTHORITY_FINGERPRINT,
            )
        ]

    @property
    def current(self) -> AutonomyRecord:
        return self._history[-1]

    @property
    def history(self) -> tuple[AutonomyRecord, ...]:
        return tuple(self._history)

    @property
    def authority(self) -> dict[str, Any]:
        return json.loads(json.dumps(CONSTITUTIONAL_AUTHORITY))

    def _append(
        self,
        *,
        level: str,
        action: str,
        reason: str,
        evidence: Any,
        fitness_fingerprint: str | None,
        risk_fingerprint: str | None,
    ) -> AutonomyRecord:
        record = AutonomyRecord(
            sequence=len(self._history),
            capability=self._capability,
            level=level,
            previous_level=self.current.level,
            action=action,
            reason=_text(reason, "reason"),
            evidence=_evidence(evidence),
            fitness_fingerprint=fitness_fingerprint,
            risk_fingerprint=risk_fingerprint,
            authority_fingerprint=AUTHORITY_FINGERPRINT,
        )
        self._history.append(record)
        return record

    def promote(
        self,
        *,
        fitness: Any,
        risk: Any,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> AutonomyRecord:
        """Avanza exactamente un nivel si fitness/risk permiten ganar autonomía."""
        current_index = LEVEL_INDEX[self.current.level]
        if current_index >= len(AUTONOMY_LEVELS) - 1:
            raise AutonomyError("capability ya está en autonomous")
        target = AUTONOMY_LEVELS[current_index + 1]

        fitness_fingerprint = _validate_fitness(fitness)
        risk_fingerprint = _validate_risk(risk, target)

        return self._append(
            level=target,
            action="promote",
            reason=reason,
            evidence=evidence,
            fitness_fingerprint=fitness_fingerprint,
            risk_fingerprint=risk_fingerprint,
        )

    def record_failure(
        self,
        severity: str,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> AutonomyRecord:
        """Reduce o revoca autonomía de forma determinista según severidad."""
        if severity not in FAILURE_TARGETS:
            raise AutonomyError("severity debe ser minor, major o critical")
        current_index = LEVEL_INDEX[self.current.level]
        target_index = max(0, current_index - FAILURE_TARGETS[severity])
        target = AUTONOMY_LEVELS[target_index]

        return self._append(
            level=target,
            action=f"downgrade:{severity}",
            reason=reason,
            evidence=evidence,
            fitness_fingerprint=None,
            risk_fingerprint=None,
        )

    def snapshot(self) -> dict[str, Any]:
        """Devuelve estado auditable y fingerprint determinista sin mutarlo."""
        payload = {
            "version": AUTONOMY_VERSION,
            "capability": self._capability,
            "level": self.current.level,
            "authority": self.authority,
            "history": [asdict(record) for record in self._history],
        }
        payload["fingerprint"] = _stable_hash(payload)
        return payload
