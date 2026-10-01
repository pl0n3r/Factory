#!/usr/bin/env python3
"""Dispatcher V2: selección determinista, explicable y auditable de trabajo Factory."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from dataclasses import dataclass, field, replace
from typing import Iterable

from scripts.adaptive_fencing import FencingDecision
from scripts.aceptacion_kit import CHECK_NAME, FORBIDDEN_CHECKS, TEST_TARGET, parse_contract
from scripts.presence_contract import PresenceAssessment
from scripts.work_origin import idempotency_scope, validate_work_item, work_fingerprint
from seguridad.puertas_humanas import validate_gate

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
    tranche_subject: bool = False
    tranche: int | None = None
    tranche_exception: bool = False


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
    tranche_subject: bool = False
    tranche: int | None = None
    tranche_exception: bool = False


@dataclass(frozen=True)
class Readiness:
    ready: bool
    reasons: tuple[str, ...]


PRODUCT_DIRECTION_REPOS = {
    "pl0n3r/Condor",
    "pl0n3r/GrindFlow",
    "pl0n3r/brvtal",
}


@dataclass(frozen=True)
class DirectionLeaf:
    key: str
    title: str
    acceptance_targets: tuple[str, ...]
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectionProposal:
    repository_ref: str
    objective: str
    leaves: tuple[DirectionLeaf, ...]


@dataclass(frozen=True)
class DirectionGateInstance:
    issue_number: int
    repository_ref: str
    created_at: str
    state: str
    category: str
    gate_key: str


def _normalize_direction_proposal(proposal: DirectionProposal) -> dict[str, object]:
    if proposal.repository_ref not in PRODUCT_DIRECTION_REPOS:
        raise ValueError("product direction only applies to canonical product repos")
    objective = proposal.objective.strip()
    if not objective:
        raise ValueError("direction proposal objective is required")
    if not proposal.leaves:
        raise ValueError("direction proposal requires at least one leaf")

    keys = [leaf.key.strip() for leaf in proposal.leaves]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("direction proposal leaf keys must be non-empty and unique")
    key_set = set(keys)
    normalized_leaves = []
    for leaf, key in zip(proposal.leaves, keys):
        title = leaf.title.strip()
        if not title or not leaf.acceptance_targets:
            raise ValueError("direction leaves require title and executable acceptance")
        targets = tuple(target.strip() for target in leaf.acceptance_targets)
        for target in targets:
            if target.startswith("check:"):
                check_name = target.removeprefix("check:")
                valid = (
                    CHECK_NAME.fullmatch(check_name) is not None
                    and check_name not in FORBIDDEN_CHECKS
                )
            else:
                valid = TEST_TARGET.fullmatch(target) is not None
            if not valid:
                raise ValueError(
                    "direction acceptance targets must match factory-acceptance"
                )
        dependencies = tuple(dep.strip() for dep in leaf.depends_on)
        if any(not dep or dep == key or dep not in key_set for dep in dependencies):
            raise ValueError("direction dependencies must reference another proposed leaf")
        normalized_leaves.append(
            {
                "key": key,
                "title": title,
                "acceptance_targets": list(targets),
                "depends_on": list(dependencies),
            }
        )
    return {
        "repository_ref": proposal.repository_ref,
        "objective": objective,
        "leaves": normalized_leaves,
    }


def _direction_gate_key(repository_ref: str) -> str:
    return f"product-direction:{repository_ref}"


def _direction_gate(proposal: DirectionProposal) -> dict[str, object]:
    normalized = _normalize_direction_proposal(proposal)
    repo = normalized["repository_ref"]
    proposal_json = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    proposal_sha256 = hashlib.sha256(proposal_json.encode("utf-8")).hexdigest()
    gate = validate_gate(
        {
            "category": "product-direction",
            "context": (
                f"{repo} no tiene ningún leaf elegible; se propone el siguiente "
                f"tramo de roadmap (proposal_sha256={proposal_sha256})."
            ),
            "title_simple": (
                f"¿Aprobamos el siguiente tramo de {str(repo).split('/')[-1]}?"
            ),
            "summary_simple": (
                "La cola del producto se quedó sin trabajo listo. Hay un tramo "
                "nuevo propuesto con pruebas y dependencias explícitas."
            ),
            "explain_simple": (
                "Es como terminar una lista de tareas y preparar la siguiente. "
                "El agente propone qué hacer, pero no empieza esas tareas de "
                "producto hasta que el dueño lo apruebe."
            ),
            "options": [
                {
                    "id": "A",
                    "label": "Aprobar el tramo propuesto",
                    "effect": (
                        "Los leaves propuestos pueden materializarse como trabajo disponible."
                    ),
                    "pros": ["Evita que la cola de producto quede vacía"],
                    "cons": ["Compromete el siguiente tramo funcional del roadmap"],
                    "risk": "medium",
                    "cost": "",
                    "reversible": True,
                    "explain_simple": (
                        "Aceptamos esta siguiente lista de tareas y los agentes "
                        "pueden empezar a ejecutarla."
                    ),
                },
                {
                    "id": "B",
                    "label": "Mantener el roadmap actual",
                    "effect": "No se materializa ningún leaf nuevo de producto.",
                    "pros": ["No cambia la dirección del producto"],
                    "cons": ["La cola funcional permanece sin trabajo nuevo"],
                    "risk": "low",
                    "cost": "",
                    "reversible": True,
                    "explain_simple": (
                        "No añadimos tareas nuevas todavía. El producto se queda "
                        "como está hasta otra decisión."
                    ),
                },
            ],
            "recommendation": "A",
            "safe_default": "B",
            "why_recommended": (
                "A mantiene continuidad del producto sin saltarse la aprobación "
                "humana de dirección."
            ),
            "blocks": (
                "Bloquea únicamente la materialización del nuevo tramo funcional "
                "del producto."
            ),
        }
    )
    gate_json = json.dumps(
        gate, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return {
        "gate_key": _direction_gate_key(str(repo)),
        "gate": gate,
        "gate_sha256": hashlib.sha256(gate_json.encode("utf-8")).hexdigest(),
        "marker": "<!-- factory-human-gate " + gate_json + " -->",
        "proposal": normalized,
        "proposal_sha256": proposal_sha256,
    }


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
        tranche_subject=context.tranche_subject,
        tranche=context.tranche,
        tranche_exception=context.tranche_exception,
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


def _bypasses_tranche_gate(candidate: Candidate) -> bool:
    """Conserva preempciones y la excepción Factory explícita de PLAN-AGENTES."""
    if (
        candidate.health
        or candidate.incident
        or candidate.auto_class == "AUTO_INCIDENT"
        or candidate.active_fix
        or candidate.owner_decision_resolved
    ):
        return True
    return (
        candidate.tranche_exception
        and candidate.metadata.get("repository_ref") == "pl0n3r/Factory"
    )


def _tranche_readiness_reasons(
    candidate: Candidate,
    active_tranche: int | None,
) -> tuple[str, ...]:
    """Aplica §6 solo a trabajo que declara explícitamente estar sujeto a tandas."""
    if not candidate.tranche_subject or _bypasses_tranche_gate(candidate):
        return ()

    if candidate.tranche is None or active_tranche is None:
        return ("tranche_evidence_missing",)

    if (
        isinstance(candidate.tranche, bool)
        or isinstance(active_tranche, bool)
        or not isinstance(candidate.tranche, int)
        or not isinstance(active_tranche, int)
        or candidate.tranche < 1
        or active_tranche < 1
    ):
        return ("tranche_evidence_invalid",)

    if candidate.tranche > active_tranche:
        return ("future_tranche_blocked",)

    return ()


def classify_readiness(
    candidate: Candidate,
    *,
    active_tranche: int | None = None,
) -> Readiness:
    reasons: list[str] = [
        *candidate.external_readiness_reasons,
        *_tranche_readiness_reasons(candidate, active_tranche),
    ]
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
    active_tranche: int | None = None,
) -> Candidate | None:
    evaluated = [
        (
            candidate,
            classify_readiness(candidate, active_tranche=active_tranche),
        )
        for candidate in candidates
    ]
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


def reconcile_direction_gate_instances(
    instances: Iterable[DirectionGateInstance],
    repository_ref: str,
) -> dict[str, object]:
    """Converge snapshots concurrentes a una única puerta product-direction."""
    if repository_ref not in PRODUCT_DIRECTION_REPOS:
        raise ValueError("product direction only applies to canonical product repos")

    gate_key = _direction_gate_key(repository_ref)
    valid: list[tuple[datetime, int]] = []
    for instance in instances:
        if (
            instance.repository_ref != repository_ref
            or instance.state != "open"
            or instance.category != "product-direction"
            or instance.gate_key != gate_key
            or instance.issue_number <= 0
        ):
            continue
        try:
            created_at = datetime.fromisoformat(
                instance.created_at.replace("Z", "+00:00")
            )
        except (AttributeError, TypeError, ValueError):
            continue
        if created_at.tzinfo is None:
            continue
        valid.append((created_at, instance.issue_number))

    valid.sort(key=lambda item: (item[0], item[1]))
    if not valid:
        return {
            "gate_key": gate_key,
            "winner_issue_number": None,
            "duplicate_issue_numbers": (),
        }

    winner = valid[0][1]
    duplicates = tuple(issue_number for _, issue_number in valid[1:])
    return {
        "gate_key": gate_key,
        "winner_issue_number": winner,
        "duplicate_issue_numbers": duplicates,
    }


def direction_gate_trigger(
    proposal: DirectionProposal,
    candidates: Iterable[Candidate],
    *,
    existing_gate_keys: Iterable[str] = (),
    active_tranche: int | None = None,
) -> dict[str, object]:
    """Propone una única puerta de dirección cuando un producto agotó sus leaves."""
    normalized = _normalize_direction_proposal(proposal)
    repo = str(normalized["repository_ref"])
    key = _direction_gate_key(repo)
    product_candidates = [
        candidate
        for candidate in candidates
        if candidate.metadata.get("repository_ref") == repo and not candidate.is_epic
    ]
    if any(
        classify_readiness(candidate, active_tranche=active_tranche).ready
        for candidate in product_candidates
    ):
        return {"action": "noop", "reason": "eligible_leaf_exists", "gate_key": key}
    if key in set(existing_gate_keys):
        return {
            "action": "noop",
            "reason": "direction_gate_already_open",
            "gate_key": key,
        }

    result = _direction_gate(proposal)
    return {"action": "open_gate", "materialize_leaves": False, **result}


def _direction_leaf_body(
    *,
    repository_ref: str,
    objective: str,
    leaf: dict[str, object],
) -> str:
    """Construye un contrato de aceptación canónico antes de publicar el leaf."""
    criteria = []
    human_lines = []
    for index, raw_target in enumerate(leaf["acceptance_targets"], start=1):
        target = str(raw_target)
        criterion_id = f"AC-{index:02d}"
        if target.startswith("check:"):
            kind = "check"
            machine_target = target.removeprefix("check:")
        else:
            kind = "test"
            machine_target = target
        criteria.append(
            {"id": criterion_id, "kind": kind, "target": machine_target}
        )
        human_lines.append(
            f"- [ ] [{criterion_id}] Evidencia ejecutable: `{target}`."
        )

    dependencies = leaf["depends_on"]
    dependency_text = ", ".join(str(item) for item in dependencies) or "ninguna"
    marker = json.dumps(
        {"version": 1, "criteria": criteria},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "### Contexto\n\n"
        f"Leaf `{leaf['key']}` del tramo product-direction aprobado para "
        f"`{repository_ref}`. Objetivo del tramo: {objective} "
        f"Dependencias declaradas: {dependency_text}.\n\n"
        "### Alcance\n\n"
        f"Implementar exclusivamente `{leaf['title']}` conforme a la propuesta "
        "aprobada y a sus criterios ejecutables.\n\n"
        "### Fuera de alcance\n\n"
        "Cualquier trabajo no descrito por este leaf, sus dependencias o sus "
        "criterios de aceptación. La materialización no ejecuta producto ni "
        "amplía autoridad.\n\n"
        "### Criterios de aceptación\n\n"
        + "\n".join(human_lines)
        + "\n\n### Contrato ejecutable\n\n"
        "El marker siguiente es la fuente ejecutable de aceptación usada por "
        "coordinación antes de reservar el Issue.\n\n"
        f"<!-- factory-acceptance {marker} -->"
    )


def materialize_direction_leaves(
    proposal: DirectionProposal,
    *,
    decision_evidence: dict[str, object] | None,
) -> tuple[dict[str, object], ...]:
    """Materializa solo con journal v2 y body prevalidado por aceptación."""
    if decision_evidence is None:
        return ()
    if (
        set(decision_evidence) != {"gate_sha256", "option", "version"}
        or decision_evidence.get("version") != 2
        or decision_evidence.get("option") not in {"A", "B"}
    ):
        raise ValueError("direction decision evidence is invalid")
    expected = _direction_gate(proposal)
    if decision_evidence.get("gate_sha256") != expected["gate_sha256"]:
        raise ValueError("direction decision evidence does not match proposal gate")
    if decision_evidence["option"] == "B":
        return ()
    normalized = expected["proposal"]
    materialized = []
    for leaf in normalized["leaves"]:
        body = _direction_leaf_body(
            repository_ref=str(normalized["repository_ref"]),
            objective=str(normalized["objective"]),
            leaf=leaf,
        )
        parse_contract(body)
        materialized.append(
            {
                **leaf,
                "repository_ref": normalized["repository_ref"],
                "body": body,
                "state": "available",
            }
        )
    return tuple(materialized)


def parallel_ready(
    candidates: Iterable[Candidate],
    *,
    aging_threshold: int = 3,
    active_tranche: int | None = None,
) -> list[Candidate]:
    remaining = [
        candidate
        for candidate in candidates
        if classify_readiness(
            candidate,
            active_tranche=active_tranche,
        ).ready
    ]
    selected: list[Candidate] = []
    claimed: set[str] = set()
    while remaining:
        candidate = select_next(
            remaining,
            aging_threshold=aging_threshold,
            active_tranche=active_tranche,
        )
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
    active_tranche: int | None = None,
) -> dict[str, object]:
    items = list(candidates)
    keys = [candidate.key for candidate in items]
    if len(keys) != len(set(keys)):
        raise ValueError("candidate keys must be unique")
    states = {
        candidate.key: classify_readiness(
            candidate,
            active_tranche=active_tranche,
        )
        for candidate in items
    }
    selected = select_next(
        items,
        aging_threshold=aging_threshold,
        active_tranche=active_tranche,
    )
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
                "tranche_subject": candidate.tranche_subject,
                "tranche": candidate.tranche,
                "tranche_exception": candidate.tranche_exception,
                "metadata": dict(candidate.metadata),
            }
            for candidate in items
        },
        "aging_threshold": aging_threshold,
        "active_tranche": active_tranche,
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
    """Convierte cualquier fail-closed en un bloqueo explícito de readiness."""
    if fencing.action != "fail_closed":
        return ()
    return tuple(
        sorted(
            {
                "adaptive_fencing_invalid",
                *(
                    f"adaptive_fencing_invalid:{reason}"
                    for reason in fencing.reasons
                ),
            }
        )
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
    active_tranche: int | None = None,
) -> dict[str, object]:
    """Compone Adaptive Orchestration con el único pipeline de Dispatcher V2."""
    adapted = adapt_candidates_for_adaptive(
        candidates,
        presence=presence,
        fencing=fencing,
        replan_action=replan_action,
        replan_reasons=replan_reasons,
    )
    record = dispatch_record(
        adapted,
        aging_threshold=aging_threshold,
        active_tranche=active_tranche,
    )
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
