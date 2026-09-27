#!/usr/bin/env python3
"""Generation fencing y cooldown deterministas para Adaptive Orchestration."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from scripts.adaptive_replan import (
    ReplanDecision,
    ReplanEvent,
    decide_replan,
    event_fingerprint as replan_event_fingerprint,
    normalize_event,
)

IMMEDIATE_TYPES = frozenset({"health_changed", "incident_changed"})


class FencingValidationError(ValueError):
    """Entrada inválida para el contrato de fencing."""


@dataclass(frozen=True)
class FencedEvent:
    """Evento de replan asociado a generation/attempt del propietario."""

    event: ReplanEvent
    generation: int
    attempt: int


@dataclass(frozen=True)
class FencingContext:
    """Contexto explícito de fencing, cooldown y continuidad del intento."""

    current_generation: int
    current_attempt: int
    cooldown_seconds: int
    elapsed_since_replan: int
    active_work_safe: bool
    active_work_ready: bool
    safe_point: bool
    preemptibility: str
    authority_valid: bool | None = True
    readiness_valid: bool | None = True
    readiness_changed: bool = False
    owner_decision_target_ready: bool | None = None


@dataclass(frozen=True)
class FencingDecision:
    """Resultado puro del fence/cooldown sin ejecutar transición alguna."""

    action: str
    pause_allowed: bool
    generation: int
    attempt: int
    snapshot_fingerprint: str
    event_fingerprint: str
    coalesced_events: int
    reasons: tuple[str, ...]


def _non_negative_int(value: object, field: str) -> int:
    """Valida enteros no negativos excluyendo bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FencingValidationError(f"invalid_{field}")
    return value


def _boolean_or_unknown(value: object, field: str) -> bool | None:
    """Valida un gate triestado: true, false o unknown."""
    if value is None or isinstance(value, bool):
        return value
    raise FencingValidationError(f"invalid_{field}")


def _fingerprint(payload: object) -> str:
    """Calcula SHA-256 sobre JSON canónico para evidencia reproducible."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_fenced_event(payload: object) -> FencedEvent:
    """Valida un envelope sin reinterpretar el contrato del evento de replan."""
    if not isinstance(payload, dict):
        raise FencingValidationError("fenced_event_must_be_object")
    allowed = {"event", "generation", "attempt"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise FencingValidationError(f"unknown_field:{unknown[0]}")
    event_payload = payload.get("event")
    if not isinstance(event_payload, dict):
        raise FencingValidationError("invalid_event")
    return FencedEvent(
        event=normalize_event(event_payload),
        generation=_non_negative_int(payload.get("generation"), "generation"),
        attempt=_non_negative_int(payload.get("attempt"), "attempt"),
    )


def _fenced_event_fingerprint(event: FencedEvent) -> str:
    """Combina fingerprint del evento con la identidad fenced de su intento."""
    return _fingerprint({
        "event": replan_event_fingerprint(event.event),
        "generation": event.generation,
        "attempt": event.attempt,
    })


def coalesce_fenced_events(events: list[dict[str, object]]) -> tuple[FencedEvent, ...]:
    """Deduplica envelopes equivalentes y devuelve orden canónico."""
    unique: dict[str, FencedEvent] = {}
    for payload in events:
        event = _normalize_fenced_event(payload)
        unique.setdefault(_fenced_event_fingerprint(event), event)
    return tuple(unique[key] for key in sorted(unique))


def _event_payload(event: ReplanEvent) -> dict[str, object]:
    """Reconstruye el payload público consumido por decide_replan."""
    return {
        "event_type": event.event_type,
        "subject": event.subject,
        "state": event.state,
        "evidence_ref": event.evidence_ref,
    }


def _gate_reason(name: str, value: bool | None) -> str | None:
    """Convierte un gate triestado en razón fail-closed cuando no es true."""
    if value is True:
        return None
    if value is False:
        return f"{name}_invalid"
    return f"{name}_unknown"


def _validate_context(context: FencingContext) -> FencingContext:
    """Valida el contexto completo y devuelve una copia normalizada."""
    if not isinstance(context, FencingContext):
        raise FencingValidationError("invalid_context")
    if not isinstance(context.active_work_safe, bool) or not isinstance(context.active_work_ready, bool):
        raise FencingValidationError("invalid_active_work_state")
    if not isinstance(context.safe_point, bool):
        raise FencingValidationError("invalid_safe_point")
    if context.preemptibility not in {"preemptible", "non_preemptible"}:
        raise FencingValidationError("invalid_preemptibility")
    return FencingContext(
        current_generation=_non_negative_int(context.current_generation, "current_generation"),
        current_attempt=_non_negative_int(context.current_attempt, "current_attempt"),
        cooldown_seconds=_non_negative_int(context.cooldown_seconds, "cooldown_seconds"),
        elapsed_since_replan=_non_negative_int(
            context.elapsed_since_replan,
            "elapsed_since_replan",
        ),
        active_work_safe=context.active_work_safe,
        active_work_ready=context.active_work_ready,
        safe_point=context.safe_point,
        preemptibility=context.preemptibility,
        authority_valid=_boolean_or_unknown(context.authority_valid, "authority_valid"),
        readiness_valid=_boolean_or_unknown(context.readiness_valid, "readiness_valid"),
        readiness_changed=context.readiness_changed,
        owner_decision_target_ready=context.owner_decision_target_ready,
    )


def _fence_reasons(
    events: tuple[FencedEvent, ...],
    *,
    current_generation: int,
    current_attempt: int,
) -> tuple[str, ...]:
    """Detecta envelopes stale/futuros antes de consultar el motor de replan."""
    reasons: list[str] = []
    for item in events:
        if item.generation < current_generation:
            reasons.append(f"stale_generation:{item.generation}<{current_generation}")
        elif item.generation > current_generation:
            reasons.append(f"future_generation:{item.generation}>{current_generation}")
        elif item.attempt < current_attempt:
            reasons.append(f"stale_attempt:{item.attempt}<{current_attempt}")
        elif item.attempt > current_attempt:
            reasons.append(f"future_attempt:{item.attempt}>{current_attempt}")
    return tuple(sorted(set(reasons)))


def _batch_fingerprint(events: tuple[FencedEvent, ...]) -> str:
    """Fingerprint estable del lote coalescido con generation/attempt."""
    return _fingerprint([_fenced_event_fingerprint(event) for event in events])


def _failed_fence_decision(
    snapshot: dict[str, object],
    events: tuple[FencedEvent, ...],
    context: FencingContext,
    reasons: tuple[str, ...],
) -> FencingDecision:
    """Construye una decisión fail-closed sin invocar el motor de replan."""
    return FencingDecision(
        action="fail_closed",
        pause_allowed=False,
        generation=context.current_generation,
        attempt=context.current_attempt,
        snapshot_fingerprint=_fingerprint(snapshot),
        event_fingerprint=_batch_fingerprint(events),
        coalesced_events=len(events),
        reasons=reasons,
    )


def _apply_gates_and_cooldown(
    replan: ReplanDecision,
    events: tuple[FencedEvent, ...],
    context: FencingContext,
) -> tuple[str, list[str]]:
    """Aplica gates y cooldown sin modificar la decisión fuente de #281."""
    action = replan.action
    reasons = list(replan.reasons)
    if action == "replan":
        gate_reasons = tuple(
            reason
            for name, value in (
                ("authority", context.authority_valid),
                ("readiness", context.readiness_valid),
            )
            if (reason := _gate_reason(name, value)) is not None
        )
        if gate_reasons:
            reasons.extend(gate_reasons)
            return "fail_closed", reasons

    immediate = any(item.event.event_type in IMMEDIATE_TYPES for item in events)
    remaining = max(context.cooldown_seconds - context.elapsed_since_replan, 0)
    if action == "replan" and not immediate and remaining > 0:
        reasons.append(f"cooldown_active:{remaining}")
        return "keep", reasons
    return action, reasons


def _pause_policy(
    action: str,
    reasons: list[str],
    context: FencingContext,
) -> tuple[bool, list[str]]:
    """Habilita pausa solo para replan preemptible en safe point."""
    if action != "replan":
        return False, reasons
    if context.preemptibility != "preemptible":
        reasons.append("pause_blocked_non_preemptible")
        return False, reasons
    if not context.safe_point:
        reasons.append("pause_blocked_unsafe_point")
        return False, reasons
    reasons.append("pause_allowed_safe_point")
    return True, reasons


def evaluate_fencing(
    snapshot: dict[str, object],
    events: list[dict[str, object]],
    context: FencingContext,
) -> FencingDecision:
    """Aplica fencing/cooldown alrededor de #281 sin ejecutar ni persistir runtime."""
    checked = _validate_context(context)
    normalized = coalesce_fenced_events(events)
    fence_reasons = _fence_reasons(
        normalized,
        current_generation=checked.current_generation,
        current_attempt=checked.current_attempt,
    )
    if fence_reasons:
        return _failed_fence_decision(snapshot, normalized, checked, fence_reasons)

    replan = decide_replan(
        snapshot,
        [_event_payload(item.event) for item in normalized],
        active_work_safe=checked.active_work_safe,
        active_work_ready=checked.active_work_ready,
        readiness_changed=checked.readiness_changed,
        owner_decision_target_ready=checked.owner_decision_target_ready,
    )
    action, reasons = _apply_gates_and_cooldown(replan, normalized, checked)
    pause_allowed, reasons = _pause_policy(action, reasons, checked)

    return FencingDecision(
        action=action,
        pause_allowed=pause_allowed,
        generation=checked.current_generation,
        attempt=checked.current_attempt,
        snapshot_fingerprint=replan.snapshot_fingerprint,
        event_fingerprint=_batch_fingerprint(normalized),
        coalesced_events=len(normalized),
        reasons=tuple(sorted(set(reasons))),
    )
