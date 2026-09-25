#!/usr/bin/env python3
"""Dispatcher V2: selección determinista, explicable y auditable de trabajo Factory."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

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
class Readiness:
    ready: bool
    reasons: tuple[str, ...]


def classify_readiness(candidate: Candidate) -> Readiness:
    reasons: list[str] = []
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
