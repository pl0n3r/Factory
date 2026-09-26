"""Evolution Engine alineado con Constitution v1.

El motor no redefine autoridad ni lifecycle: consume el contrato constitucional,
valida el candidato y registra cada transición como historia append-only.
"""
from __future__ import annotations

from typing import Any

from evolution.constitution import load_constitution, validate_candidate
from evolution.models import (
    EvolutionError,
    EvolutionRecord,
    normalize_evidence,
    normalize_reason,
)


class EvolutionEngine:
    """Máquina determinista de estados para un único candidato evolutivo."""

    def __init__(
        self,
        candidate: Any,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> None:
        contract = load_constitution()
        self._lifecycle = tuple(contract["lifecycle"])
        self._candidate_fingerprint = validate_candidate(candidate, contract)
        self._history: list[EvolutionRecord] = [
            EvolutionRecord(
                generation=0,
                stage=self._lifecycle[0],
                parent_generation=None,
                reason=normalize_reason(reason),
                evidence=normalize_evidence(evidence),
                candidate_fingerprint=self._candidate_fingerprint,
            )
        ]

    @property
    def history(self) -> tuple[EvolutionRecord, ...]:
        return tuple(self._history)

    @property
    def current(self) -> EvolutionRecord:
        return self._history[-1]

    @property
    def active_generation(self) -> int:
        record = self.current
        if record.stage == "rollback" and record.restores_generation is not None:
            return record.restores_generation
        return record.generation

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return self._lifecycle

    def _append(
        self,
        *,
        stage: str,
        reason: str,
        evidence: list[str] | tuple[str, ...],
        decision: str | None = None,
        restores_generation: int | None = None,
    ) -> EvolutionRecord:
        record = EvolutionRecord(
            generation=len(self._history),
            stage=stage,
            parent_generation=self.current.generation,
            reason=normalize_reason(reason),
            evidence=normalize_evidence(evidence),
            candidate_fingerprint=self._candidate_fingerprint,
            decision=decision,
            restores_generation=restores_generation,
        )
        self._history.append(record)
        return record

    def transition(
        self,
        stage: str,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
        decision: str | None = None,
    ) -> EvolutionRecord:
        """Avanza exactamente una etapa del lifecycle constitucional."""
        if not isinstance(stage, str) or stage not in self._lifecycle:
            raise EvolutionError("stage desconocido")
        current_index = self._lifecycle.index(self.current.stage)
        if current_index >= len(self._lifecycle) - 1:
            raise EvolutionError("la evolución ya alcanzó el final del lifecycle")

        expected = self._lifecycle[current_index + 1]
        if stage != expected:
            raise EvolutionError(
                f"transición inválida: se esperaba {expected}, no {stage}"
            )
        if stage == "rollback":
            raise EvolutionError("rollback requiere rollback(target_generation=...)")
        if stage == "promote_or_reject":
            if decision not in {"adopt", "reject"}:
                raise EvolutionError(
                    "promote_or_reject exige decision adopt o reject"
                )
        elif decision is not None:
            raise EvolutionError("decision solo es válida en promote_or_reject")

        return self._append(
            stage=stage,
            reason=reason,
            evidence=evidence,
            decision=decision,
        )

    def rollback(
        self,
        target_generation: int,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> EvolutionRecord:
        """Restaura una generación previa creando una entrada nueva de historia."""
        current_index = self._lifecycle.index(self.current.stage)
        expected = (
            self._lifecycle[current_index + 1]
            if current_index < len(self._lifecycle) - 1
            else None
        )
        if expected != "rollback":
            raise EvolutionError("rollback no está permitido en la etapa actual")
        if (
            type(target_generation) is not int
            or target_generation < 0
            or target_generation >= self.current.generation
        ):
            raise EvolutionError("target_generation debe referir una generación previa")

        target = self._history[target_generation]
        if target.stage == "rollback":
            raise EvolutionError("rollback no puede restaurar otra entrada rollback")

        return self._append(
            stage="rollback",
            reason=reason,
            evidence=evidence,
            restores_generation=target_generation,
        )
