"""Autonomy Engine: autonomía ganada, auditable y constitucionalmente acotada."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from evolution.constitution import PROTECTED_INVARIANTS
from evolution.fitness import FitnessError, validate_fitness_evidence
from intelligence.risk_compiler import RiskCompilerError, validate_risk_evidence


AUTONOMY_VERSION = 1
AUTONOMY_LEVELS = (
    "observe",
    "propose",
    "shadow",
    "supervised",
    "autonomous",
)
LEVEL_INDEX = {level: index for index, level in enumerate(AUTONOMY_LEVELS)}
FAILURE_TARGETS = {"minor": 1, "major": 2, "critical": 4}
AUTHORITY_CLASSES = {
    "operational",
    "money",
    "legal",
    "personal_data",
    "irreversible_delete",
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
class CapabilityScope:
    name: str
    authority_class: str = "operational"


@dataclass(frozen=True)
class AutonomyRecord:
    sequence: int
    capability: str
    authority_class: str
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


def _scope(value: Any) -> CapabilityScope:
    if isinstance(value, str):
        scope = CapabilityScope(name=_text(value, "capability"))
    elif isinstance(value, CapabilityScope):
        scope = CapabilityScope(
            name=_text(value.name, "capability.name"),
            authority_class=_text(value.authority_class, "capability.authority_class"),
        )
    else:
        raise AutonomyError("capability debe ser string o CapabilityScope")
    if scope.authority_class not in AUTHORITY_CLASSES:
        raise AutonomyError("authority_class no admitida")
    return scope


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


def _canonical_fitness(envelope: Any) -> dict[str, Any]:
    if not isinstance(envelope, dict) or set(envelope) != {
        "baseline",
        "candidate",
        "protected_dimensions",
        "result",
    }:
        raise AutonomyError("fitness evidence inválida")
    try:
        result = validate_fitness_evidence(
            baseline=envelope["baseline"],
            candidate=envelope["candidate"],
            protected_dimensions=envelope["protected_dimensions"],
            result=envelope["result"],
        )
    except FitnessError as exc:
        raise AutonomyError("fitness evidence no es canónica") from exc
    if result["protected_regressions"]:
        raise AutonomyError("fitness degrada dimensión protegida")
    confidence = result["confidence"]
    if (
        type(confidence.get("comparable")) is not int
        or type(confidence.get("total")) is not int
        or confidence["total"] <= 0
        or confidence["comparable"] != confidence["total"]
        or result["missing_dimensions"]
    ):
        raise AutonomyError("fitness incompleto o con incertidumbre")
    if result["claim"] not in {"equal", "improved"}:
        raise AutonomyError("fitness no demuestra estabilidad suficiente")
    return result


def _canonical_risk(envelope: Any, target_level: str) -> dict[str, Any]:
    if not isinstance(envelope, dict) or set(envelope) != {
        "project_dna",
        "task",
        "result",
    }:
        raise AutonomyError("risk evidence inválida")
    try:
        result = validate_risk_evidence(
            project_dna=envelope["project_dna"],
            task=envelope["task"],
            result=envelope["result"],
        )
    except RiskCompilerError as exc:
        raise AutonomyError("risk evidence no es canónica") from exc
    if result["context_complete"] is not True or result["unknown_critical_signals"]:
        raise AutonomyError("riesgo conserva incertidumbre crítica")
    if target_level == "autonomous" and result["risk"] == "high":
        raise AutonomyError("riesgo high no puede promover a autonomous")
    return result


class AutonomyEngine:
    """Escalera de autonomía por capacidad, sin ampliar autoridad externa."""

    def __init__(
        self,
        capability: str | CapabilityScope,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> None:
        self._scope = _scope(capability)
        self._history: list[AutonomyRecord] = [
            AutonomyRecord(
                sequence=0,
                capability=self._scope.name,
                authority_class=self._scope.authority_class,
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
            capability=self._scope.name,
            authority_class=self._scope.authority_class,
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
        """Avanza exactamente un nivel tras revalidar evidencia canónica."""
        if self._scope.authority_class != "operational":
            raise AutonomyError("authority class prohibida no puede ganar autonomía")
        current_index = LEVEL_INDEX[self.current.level]
        if current_index >= len(AUTONOMY_LEVELS) - 1:
            raise AutonomyError("capability ya está en autonomous")
        target = AUTONOMY_LEVELS[current_index + 1]

        fitness_result = _canonical_fitness(fitness)
        risk_result = _canonical_risk(risk, target)

        return self._append(
            level=target,
            action="promote",
            reason=reason,
            evidence=evidence,
            fitness_fingerprint=fitness_result["fingerprint"],
            risk_fingerprint=risk_result["fingerprint"],
        )

    def record_failure(
        self,
        severity: str,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> AutonomyRecord:
        if severity not in FAILURE_TARGETS:
            raise AutonomyError("severity debe ser minor, major o critical")
        current_index = LEVEL_INDEX[self.current.level]
        target_index = max(0, current_index - FAILURE_TARGETS[severity])
        return self._append(
            level=AUTONOMY_LEVELS[target_index],
            action=f"downgrade:{severity}",
            reason=reason,
            evidence=evidence,
            fitness_fingerprint=None,
            risk_fingerprint=None,
        )

    def snapshot(self) -> dict[str, Any]:
        payload = {
            "version": AUTONOMY_VERSION,
            "capability": self._scope.name,
            "authority_class": self._scope.authority_class,
            "level": self.current.level,
            "authority": self.authority,
            "history": [asdict(record) for record in self._history],
        }
        payload["fingerprint"] = _stable_hash(payload)
        return payload
