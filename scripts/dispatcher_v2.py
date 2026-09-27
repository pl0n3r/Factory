#!/usr/bin/env python3
"""Dispatcher V2: selección determinista, explicable y auditable de trabajo Factory."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable

from scripts.adaptive_fencing import FencingDecision
from scripts.presence_contract import PresenceAssessment
from scripts.work_origin import idempotency_scope, validate_work_item, work_fingerprint

AUTHORITY_ORDER = {
    "health": 0,
    "incident": 1,
    "active_fix": 2,
    "owner_decision": 3,
    "critical": 4,
    "high": 5,
    "medium": 6,
}

AUTO_CLASSES = {
    "AUTO_INCIDENT",
    "AUTO_SECURITY",
    "AUTO_DEGRADATION",
    "AUTO_REVIEW",
    "AUTO_INFO",
}


@dataclass(frozen=True)
class Candidate:
    key: str
    priority: str = "medium"
    health: bool = False
    incident: bool = False
    active_fix: bool = False
    owner_decision_resolved: bool = False
    auto_class: str | None = None
    auto_evidence_reviewed: bool = False
    title: str = ""
    blocked: bool = False
    fallback_safe: bool = False
    dependencies_open: tuple[str, ...] = ()
    incompatible_reservation: bool = False
    pending_human_gate: bool = False
    missing_acceptance: bool = False
    acceptance_autofixable: bool = False
    claims: frozenset[str] = frozenset()
    active_claims: frozenset[str] = frozenset()
    requires_extra_authority: bool = False
    idempotency_active: bool = False
    external_readiness_reasons: tuple[str, ...] = ()
    is_epic: bool = False
    ready_children: tuple[str, ...] = ()
    equivalent_active_fix: str | None = None
    continuing_active_fix: bool = False
    unlock_impact: int = 0
    transversal_impact: int = 0
    continuity: int = 0
    effort: int = 1
    risk: int = 1
    ready_age: int = 0
    displaced_cycles: int = 0
    active_pr: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkItemReadinessContext:
    """Evidencia externa necesaria para convertir WorkItem en candidato ejecutable."""

    authority_valid: bool | None = None
    policy_valid: bool | None = None
    freshness_valid: bool | None = None
    evidence_valid: bool | None = None
    budget_valid: bool | None = None
    approval_valid: bool | None = None
    completed_dependencies: frozenset[str] = frozenset()
    active_claims: frozenset[str] = frozenset()
    incompatible_reservation: bool = False
    active_idempotency_scopes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Readiness:
    ready: bool
    reasons: tuple[str, ...]


def _gate_reason(name: str, value: bool | None) -> str | None:
    if value is True:
        return None
    if value is False:
        return f"{name}_invalid"
    return f"{name}_unknown"


def candidate_from_work_item(
    payload: dict[str, object],
    context: WorkItemReadinessContext,
) -> Candidate:
    """Adapta WorkItem v1 a Candidate sin crear una jerarquía de despacho paralela."""
    item = validate_work_item(payload)
    reasons: list[str] = []

    for name, value in (
        ("authority", context.authority_valid),
        ("policy", context.policy_valid),
        ("freshness", context.freshness_valid),
        ("evidence", context.evidence_valid),
    ):
        reason = _gate_reason(name, value)
        if reason is not None:
            reasons.append(reason)

    if item.get("budget_ref") is not None:
        reason = _gate_reason("budget", context.budget_valid)
        if reason is not None:
            reasons.append(reason)
    if item.get("approval_ref") is not None:
        reason = _gate_reason("approval", context.approval_valid)
        if reason is not None:
            reasons.append(reason)

    authority = item["authority_level"]
    health = authority == "health"
    incident = authority == "incident"
    active_fix = authority == "active_fix"
    owner_decision = authority == "owner_decision"
    scope = idempotency_scope(payload)

    open_dependencies = tuple(
        dependency
        for dependency in item["depends_on"]
        if dependency not in context.completed_dependencies
    )

    return Candidate(
        key=item["work_id"],
        priority=item["priority_class"],
        health=health,
        incident=incident,
        active_fix=active_fix,
        owner_decision_resolved=owner_decision,
        dependencies_open=open_dependencies,
        incompatible_reservation=context.incompatible_reservation,
        claims=frozenset(item["claims"]),
        active_claims=context.active_claims,
        idempotency_active=scope in context.active_idempotency_scopes,
        external_readiness_reasons=tuple(reasons),
        metadata={
            "work_fingerprint": work_fingerprint(payload),
            "idempotency_scope": scope,
            "origin_mode": item["origin_mode"],
            "origin_system": item["origin_system"],
            "producer_ref": item["producer_ref"],
            "work_type": item["work_type"],
            "repository_ref": item.get("repository_ref"),
            "policy_ref": item["policy_ref"],
            "budget_ref": item.get("budget_ref"),
            "approval_ref": item.get("approval_ref"),
            "evidence_refs": tuple(item["evidence_refs"]),
        },
    )


def classify_readiness(candidate: Candidate) -> Readiness:
    reasons: list[str] = list(candidate.external_readiness_reasons)
    if candidate.incompatible_reservation:
        reasons.append("incompatible_reservation")
    if candidate.dependencies_open:
        reasons.append("open_dependencies")
    if candidate.pending_human_gate:
        reasons.append("pending_human_gate")
    if candidate.blocked and not candidate.fallback_safe:
        reasons.append("blocked_without_safe_fallback")
    if candidate.equivalent_active_fix and not candidate.continuing_active_fix:
        reasons.append("equivalent_active_fix_exists")
    if candidate.is_epic and candidate.ready_children:
        reasons.append("epic_has_ready_leaf")
    if candidate.missing_acceptance and not candidate.acceptance_autofixable:
        reasons.append("missing_acceptance")
    if candidate.claims & candidate.active_claims:
        reasons.append("claim_overlap")
    if candidate.idempotency_active:
        reasons.append("idempotency_active")
    if candidate.requires_extra_authority:
        reasons.append("requires_extra_authority")
    if candidate.title.startswith("[AUTO]") and candidate.auto_class is None and not candidate.auto_evidence_reviewed:
        reasons.append("unclassified_auto_needs_review")
    if candidate.auto_class == "AUTO_INFO":
        reasons.append("auto_info_not_dispatchable")
    return Readiness(not reasons, tuple(reasons))


def authority_class(candidate: Candidate) -> str:
    if candidate.health:
        return "health"
    if candidate.incident or candidate.auto_class == "AUTO_INCIDENT":
        return "incident"
    if candidate.active_fix:
        return "active_fix"
    if candidate.owner_decision_resolved:
        return "owner_decision"
    priority = candidate.priority.lower()
    if priority not in {"critical", "high", "medium"}:
        priority = "medium"
    return priority


def _tiebreak(candidate: Candidate, *, aging_threshold: int) -> tuple[object, ...]:
    aged = candidate.displaced_cycles >= aging_threshold
    return (
        -candidate.unlock_impact,
        -candidate.transversal_impact,
        -candidate.continuity,
        candidate.effort + candidate.risk,
        0 if aged else 1,
        -candidate.ready_age,
        candidate.key,
    )


def select_next(
    candidates: Iterable[Candidate],
    *,
    aging_threshold: int = 3,
) -> Candidate | None:
    evaluated = [(candidate, classify_readiness(candidate)) for candidate in candidates]
    ready = [candidate for candidate, state in evaluated if state.ready]
    if not ready:
        return None
    best_rank = min(AUTHORITY_ORDER[authority_class(candidate)] for candidate in ready)
    same_class = [
        candidate
        for candidate in ready
        if AUTHORITY_ORDER[authority_class(candidate)] == best_rank
    ]
    return min(same_class, key=lambda item: _tiebreak(item, aging_threshold=aging_threshold))


def parallel_ready(
    candidates: Iterable[Candidate],
    *,
    aging_threshold: int = 3,
) -> list[Candidate]:
    remaining = [candidate for candidate in candidates if classify_readiness(candidate).ready]
    selected: list[Candidate] = []
    claimed: set[str] = set()
    while remaining:
        candidate = select_next(remaining, aging_threshold=aging_threshold)
        if candidate is None:
            break
        remaining.remove(candidate)
        if claimed.isdisjoint(candidate.claims):
            selected.append(candidate)
            claimed.update(candidate.claims)
    return selected


def dispatch_record(
    candidates: Iterable[Candidate],
    *,
    aging_threshold: int = 3,
) -> dict[str, object]:
    items = list(candidates)
    keys = [candidate.key for candidate in items]
    if len(keys) != len(set(keys)):
        raise ValueError("candidate keys must be unique")
    states = {candidate.key: classify_readiness(candidate) for candidate in items}
    selected = select_next(items, aging_threshold=aging_threshold)
    ready = [candidate for candidate in items if states[candidate.key].ready]
    excluded = {
        candidate.key: list(states[candidate.key].reasons)
        for candidate in items
        if not states[candidate.key].ready
    }
    return {
        "selected": selected.key if selected else None,
        "selected_class": authority_class(selected) if selected else None,
        "ready_not_selected": [
            candidate.key for candidate in ready if selected is None or candidate.key != selected.key
        ],
        "excluded": excluded,
        "candidates": {
            candidate.key: {
                "authority_class": authority_class(candidate),
                "ready_age": candidate.ready_age,
                "displaced_cycles": candidate.displaced_cycles,
                "active_pr": candidate.active_pr,
                "unlock_impact": candidate.unlock_impact,
                "transversal_impact": candidate.transversal_impact,
                "claims": sorted(candidate.claims),
                "metadata": dict(candidate.metadata),
            }
            for candidate in items
        },
        "aging_threshold": aging_threshold,
    }


def _adaptive_presence_reasons(presence: PresenceAssessment) -> tuple[str, ...]:
    """Convierte presencia no confiable en razones estructuradas de readiness."""
    reasons: list[str] = []
    if "unknown" in presence.classifications:
        reasons.append("adaptive_presence_unknown")
    for reason in presence.reasons:
        if "stale" in reason:
            reasons.append("adaptive_presence_stale")
        if "freshness_unknown" in reason or reason.startswith("capacity:unknown"):
            reasons.append("adaptive_presence_unknown")
    return tuple(sorted(set(reasons)))


def _adaptive_fencing_reasons(fencing: FencingDecision) -> tuple[str, ...]:
    """Convierte un fence fail-closed en razones que excluyen candidatos."""
    if fencing.action != "fail_closed":
        return ()
    return tuple(
        sorted(f"adaptive_fencing_invalid:{reason}" for reason in fencing.reasons)
    )


def adapt_candidates_for_adaptive(
    candidates: Iterable[Candidate],
    *,
    presence: PresenceAssessment,
    fencing: FencingDecision,
    replan_action: str,
    replan_reasons: tuple[str, ...] = (),
) -> list[Candidate]:
    """Añade readiness/metadata adaptativos sin alterar la jerarquía de selección."""
    presence_reasons = _adaptive_presence_reasons(presence)
    fencing_reasons = _adaptive_fencing_reasons(fencing)
    adaptive_reasons = tuple(sorted(set((*presence_reasons, *fencing_reasons))))
    adapted: list[Candidate] = []
    for candidate in candidates:
        metadata = dict(candidate.metadata)
        metadata["adaptive"] = {
            "snapshot_fingerprint": fencing.snapshot_fingerprint,
            "event_fingerprint": fencing.event_fingerprint,
            "generation": fencing.generation,
            "attempt": fencing.attempt,
            "replan_action": replan_action,
            "fencing_action": fencing.action,
            "reasons": tuple(sorted(set((*replan_reasons, *fencing.reasons)))),
        }
        adapted.append(
            replace(
                candidate,
                external_readiness_reasons=tuple(
                    sorted(set((*candidate.external_readiness_reasons, *adaptive_reasons)))
                ),
                metadata=metadata,
            )
        )
    return adapted


def adaptive_dispatch_record(
    candidates: Iterable[Candidate],
    *,
    presence: PresenceAssessment,
    fencing: FencingDecision,
    replan_action: str,
    replan_reasons: tuple[str, ...] = (),
    aging_threshold: int = 3,
) -> dict[str, object]:
    """Compone Adaptive Orchestration con el único pipeline de Dispatcher V2."""
    adapted = adapt_candidates_for_adaptive(
        candidates,
        presence=presence,
        fencing=fencing,
        replan_action=replan_action,
        replan_reasons=replan_reasons,
    )
    record = dispatch_record(adapted, aging_threshold=aging_threshold)
    record["adaptive"] = {
        "snapshot_fingerprint": fencing.snapshot_fingerprint,
        "event_fingerprint": fencing.event_fingerprint,
        "generation": fencing.generation,
        "attempt": fencing.attempt,
        "replan_action": replan_action,
        "fencing_action": fencing.action,
        "reasons": tuple(sorted(set((*replan_reasons, *fencing.reasons)))),
    }
    return record
