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
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import (
    DailySummary,
    EMAIL_RE as WATCHDOG_EMAIL_RE,
    SEVERITIES as WATCHDOG_SEVERITIES,
    SENSITIVE_VALUE_FRAGMENTS as WATCHDOG_SENSITIVE_VALUE_FRAGMENTS,
    WatchdogDecision,
    WatchdogIncident,
)
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


@dataclass(frozen=True)
class BlockedWork:
    """Bloqueo con condición verificable ya evaluada por el adaptador de evidencia."""

    key: str
    unlock_condition: str
    condition_satisfied: bool
    evidence_refs: tuple[str, ...] = ()
    already_reconciled: bool = False


WORK_LADDER_LANES = {"normal", "quality", "filler"}
FILLER_MAX_EFFORT = 2
FILLER_MAX_RISK = 1


CANONICAL_DISPATCH_REPOS = {
    "pl0n3r/Factory",
    "pl0n3r/Condor",
    "pl0n3r/GrindFlow",
    "pl0n3r/brvtal",
    "pl0n3r/ControlBot",
    "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
}

PRODUCT_DIRECTION_REPOS = {
    "pl0n3r/Factory",
    "pl0n3r/Condor",
    "pl0n3r/GrindFlow",
    "pl0n3r/brvtal",
    "pl0n3r/ControlBot",
    "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
}
PRODUCT_DIRECTION_ELIGIBLE_LEAF_THRESHOLD = 1
PRODUCT_DIRECTION_FORBIDDEN_AUTHORITY_MARKERS = {
    "pl0n3r/ControlBot": (
        "backblaze",
        "go-live",
        "go live",
        "salir a live",
        "production authority",
        "autoridad de producción",
        "recovery real",
        "recuperación real",
    ),
    "pl0n3r/AutoFactory": (
        "go-live",
        "go live",
        "salir a live",
        "comprar",
        "purchase",
        "cambiar plan",
        "change plan",
        "cambiar cuenta",
        "change account",
        "dato sensible",
        "datos sensibles",
        "sensitive data",
    ),
    "pl0n3r/FactoryRunner": (
        "go-live",
        "go live",
        "salir a live",
        "comprar",
        "purchase",
        "proveedor de pago",
        "paid provider",
        "backblaze",
    ),
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
        raise ValueError("product direction only applies to canonical product-direction repos")
    objective = proposal.objective.strip()
    if not objective:
        raise ValueError("direction proposal objective is required")
    if not proposal.leaves:
        raise ValueError("direction proposal requires at least one leaf")

    authority_text = " ".join(
        [objective, *(leaf.title.strip() for leaf in proposal.leaves)]
    ).casefold()
    for marker in PRODUCT_DIRECTION_FORBIDDEN_AUTHORITY_MARKERS.get(
        proposal.repository_ref, ()
    ):
        if marker in authority_text:
            raise ValueError(
                "product direction cannot cross human-only authority blocks "
                f"for {proposal.repository_ref}: {marker}"
            )

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
                f"{repo} tiene pocas hojas elegibles; se propone el siguiente "
                f"tramo de roadmap (proposal_sha256={proposal_sha256})."
            ),
            "title_simple": (
                f"¿Aprobamos el siguiente tramo de {str(repo).split('/')[-1]}?"
            ),
            "summary_simple": (
                "La cola del producto está cerca de quedarse sin trabajo listo. "
                "Hay un tramo nuevo propuesto con pruebas y dependencias explícitas."
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


def _work_lane(candidate: Candidate) -> str:
    lane = candidate.metadata.get("work_ladder_lane", "normal")
    return lane if lane in WORK_LADDER_LANES else "normal"


def _filler_is_safe(candidate: Candidate) -> bool:
    """Acepta solo relleno curado, reversible, sin gasto y de riesgo/esfuerzo bajo."""

    metadata = candidate.metadata
    return (
        _work_lane(candidate) == "filler"
        and metadata.get("filler_curated") is True
        and metadata.get("filler_reversible") is True
        and metadata.get("filler_no_spend") is True
        and candidate.risk <= FILLER_MAX_RISK
        and candidate.effort <= FILLER_MAX_EFFORT
        and not candidate.requires_extra_authority
        and not candidate.pending_human_gate
    )


def reconcile_stale_blocks(
    blocked_work: Iterable[BlockedWork],
    *,
    reconciled_keys: Iterable[str] = (),
) -> tuple[dict[str, object], ...]:
    """Devuelve desbloqueos idempotentes solo con condición y evidencia verificadas."""

    seen = set(reconciled_keys)
    actions: list[dict[str, object]] = []
    for item in sorted(blocked_work, key=lambda value: value.key):
        condition = item.unlock_condition.strip()
        if (
            item.key in seen
            or item.already_reconciled
            or not condition
            or not item.condition_satisfied
            or not item.evidence_refs
        ):
            continue

        evidence = tuple(
            ref.strip()
            for ref in item.evidence_refs
            if isinstance(ref, str) and ref.strip()
        )
        if not evidence:
            continue

        actions.append(
            {
                "action": "unblock",
                "key": item.key,
                "unlock_condition": condition,
                "evidence_refs": evidence,
                "comment": (
                    "Desbloqueo automático: la condición declarada ya se cumple. "
                    "Evidencia: " + ", ".join(evidence)
                ),
            }
        )
        seen.add(item.key)

    return tuple(actions)


def idle_time_metric(
    *,
    agent_id: str,
    repository_ref: str,
    finished_at: str,
    next_dispatch_at: str,
    threshold_minutes: int = 15,
) -> dict[str, object]:
    """Mide tiempo ocioso con timestamps aware y expone estado para Quality Health."""

    if repository_ref not in CANONICAL_DISPATCH_REPOS:
        raise ValueError("idle metric requires a canonical dispatch repository")
    if not agent_id.strip():
        raise ValueError("idle metric requires agent_id")
    if (
        isinstance(threshold_minutes, bool)
        or not isinstance(threshold_minutes, int)
        or threshold_minutes <= 0
    ):
        raise ValueError("idle threshold must be a positive integer")

    def parse(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("idle timestamps must include timezone")
        return parsed

    finished = parse(finished_at)
    dispatched = parse(next_dispatch_at)
    elapsed_seconds = (dispatched - finished).total_seconds()
    if elapsed_seconds < 0:
        raise ValueError("next dispatch cannot precede finished work")

    alert = elapsed_seconds > threshold_minutes * 60
    return {
        "agent_id": agent_id.strip(),
        "repository_ref": repository_ref,
        "idle_seconds": int(elapsed_seconds),
        "threshold_seconds": threshold_minutes * 60,
        "alert": alert,
        "quality_health": "DEGRADED" if alert else "HEALTHY",
    }


def work_ladder(
    candidates: Iterable[Candidate],
    *,
    blocked_work: Iterable[BlockedWork] = (),
    reconciled_block_keys: Iterable[str] = (),
    direction_proposals: Iterable[DirectionProposal] = (),
    existing_gate_keys: Iterable[str] = (),
    known_proposal_sha256s: Iterable[str] = (),
    active_tranche: int | None = None,
    active_filler_count: int = 0,
    max_filler_parallel: int = 2,
    no_safe_work_reason: str = (
        "No hay trabajo seguro listo; se requiere nueva evidencia, "
        "desbloqueo o dirección explícita."
    ),
) -> dict[str, object]:
    """Escalera total: siempre devuelve un siguiente paso explicable."""

    if (
        isinstance(active_filler_count, bool)
        or not isinstance(active_filler_count, int)
        or active_filler_count < 0
        or isinstance(max_filler_parallel, bool)
        or not isinstance(max_filler_parallel, int)
        or max_filler_parallel < 0
        or max_filler_parallel > 2
    ):
        raise ValueError(
            "filler parallel counts must be non-negative integers capped at 2"
        )

    items = list(candidates)
    for step, lane in (
        ("normal", "normal"),
        ("quality", "quality"),
        ("filler", "filler"),
    ):
        if step == "filler" and active_filler_count >= max_filler_parallel:
            continue
        if step == "quality":
            actions = reconcile_stale_blocks(
                blocked_work,
                reconciled_keys=reconciled_block_keys,
            )
            if actions:
                return {
                    "step": "reconcile_stale_blocks",
                    "work": {
                        "kind": "stale_block_reconciliation",
                        "key": str(actions[0]["key"]),
                    },
                    "actions": actions,
                }

        lane_candidates = [
            candidate for candidate in items if _work_lane(candidate) == lane
        ]
        if step == "filler":
            lane_candidates = [
                candidate for candidate in lane_candidates if _filler_is_safe(candidate)
            ]
        selected = select_next(
            lane_candidates,
            active_tranche=active_tranche,
        )
        if selected is not None:
            return {
                "step": step,
                "work": {"kind": "candidate", "key": selected.key},
                "selected_class": authority_class(selected),
            }

    gate_keys = tuple(existing_gate_keys)
    proposal_hashes = tuple(known_proposal_sha256s)
    for proposal in sorted(
        direction_proposals,
        key=lambda value: value.repository_ref,
    ):
        trigger = direction_gate_trigger(
            proposal,
            items,
            existing_gate_keys=gate_keys,
            known_proposal_sha256s=proposal_hashes,
            active_tranche=active_tranche,
        )
        if trigger["action"] == "open_gate":
            return {
                "step": "product_direction",
                "work": {
                    "kind": "product_direction",
                    "key": str(trigger["gate_key"]),
                },
                "trigger": trigger,
            }

    reason = no_safe_work_reason.strip()
    if not reason:
        raise ValueError("work ladder requires a reason when no safe work exists")
    return {
        "step": "declare_idle_reason",
        "work": {
            "kind": "status",
            "key": "dispatcher:no-safe-work",
        },
        "reason": reason,
        "needs": (
            "evidencia que satisfaga un bloqueo, un candidato safe/ready "
            "o una decisión humana aplicable"
        ),
    }


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
    known_proposal_sha256s: Iterable[str] = (),
    eligible_leaf_threshold: int = PRODUCT_DIRECTION_ELIGIBLE_LEAF_THRESHOLD,
    active_tranche: int | None = None,
) -> dict[str, object]:
    """Propone una puerta cuando quedan pocas hojas, sin repetir tramo conocido."""
    normalized = _normalize_direction_proposal(proposal)
    if (
        isinstance(eligible_leaf_threshold, bool)
        or not isinstance(eligible_leaf_threshold, int)
        or eligible_leaf_threshold < 0
    ):
        raise ValueError("eligible leaf threshold must be a non-negative integer")

    repo = str(normalized["repository_ref"])
    key = _direction_gate_key(repo)
    if key in set(existing_gate_keys):
        return {
            "action": "noop",
            "reason": "direction_gate_already_open",
            "gate_key": key,
        }

    product_candidates = [
        candidate
        for candidate in candidates
        if candidate.metadata.get("repository_ref") == repo and not candidate.is_epic
    ]
    eligible_leaf_count = sum(
        1
        for candidate in product_candidates
        if classify_readiness(candidate, active_tranche=active_tranche).ready
    )
    if eligible_leaf_count > eligible_leaf_threshold:
        return {
            "action": "noop",
            "reason": "sufficient_eligible_work",
            "gate_key": key,
            "eligible_leaf_count": eligible_leaf_count,
            "eligible_leaf_threshold": eligible_leaf_threshold,
        }

    result = _direction_gate(proposal)
    if result["proposal_sha256"] in set(known_proposal_sha256s):
        return {
            "action": "noop",
            "reason": "direction_proposal_already_known",
            "gate_key": key,
            "proposal_sha256": result["proposal_sha256"],
            "eligible_leaf_count": eligible_leaf_count,
            "eligible_leaf_threshold": eligible_leaf_threshold,
        }

    return {
        "action": "open_gate",
        "materialize_leaves": False,
        "eligible_leaf_count": eligible_leaf_count,
        "eligible_leaf_threshold": eligible_leaf_threshold,
        **result,
    }


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
                "state": "blocked" if leaf["depends_on"] else "available",
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
    next_action = work_ladder(
        items,
        active_tranche=active_tranche,
    )
    excluded = {
        candidate.key: list(states[candidate.key].reasons)
        for candidate in items
        if not states[candidate.key].ready
    }
    return {
        "selected": selected.key if selected else None,
        "selected_class": authority_class(selected) if selected else None,
        "next_action": next_action,
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


UNATTENDED_ACTIONS = frozenset({"ALLOW", "PAUSE", "BLOCKED"})
UNATTENDED_CANONICAL_PAIRS = frozenset({
    ("ALLOW", "ALLOW"),
    ("ALLOW", "BLOCKED"),
    ("PAUSE", "PAUSE"),
    ("PAUSE", "BLOCKED"),
    ("BLOCKED", "BLOCKED"),
})


def _valid_unattended_fingerprint(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value.lower())
    )


def _valid_unattended_reason(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 128:
        return False
    if any(fragment in value.lower() for fragment in (
        "secret",
        "token",
        "password",
        "credential",
        "authorization",
        "cookie",
        "email",
    )):
        return False
    return all(char.isalnum() or char in "._:-" for char in value)


def _valid_unattended_incident_code(value: object) -> bool:
    """Compatibilidad estructural con el texto seguro que 4C ya acepta."""
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 521
    ):
        return False
    lowered = value.lower()
    if any(fragment in lowered for fragment in WATCHDOG_SENSITIVE_VALUE_FRAGMENTS):
        return False
    return WATCHDOG_EMAIL_RE.search(value) is None


def _valid_unattended_incident(incident: object) -> bool:
    return (
        isinstance(incident, WatchdogIncident)
        and _valid_unattended_incident_code(incident.code)
        and incident.severity in WATCHDOG_SEVERITIES
        and _valid_unattended_fingerprint(incident.fingerprint)
        and isinstance(incident.repeated, bool)
        and isinstance(incident.reasons, tuple)
        and all(
            isinstance(reason, str) and 0 < len(reason) <= 521
            for reason in incident.reasons
        )
    )


def _valid_unattended_watchdog_contract(watchdog: WatchdogDecision) -> bool:
    if not isinstance(watchdog.daily_summary, DailySummary):
        return False
    if not isinstance(watchdog.incidents, tuple) or any(
        not _valid_unattended_incident(incident)
        for incident in watchdog.incidents
    ):
        return False
    if not isinstance(watchdog.new_alert_fingerprints, tuple) or any(
        not _valid_unattended_fingerprint(fingerprint)
        for fingerprint in watchdog.new_alert_fingerprints
    ):
        return False
    expected_alerts = tuple(
        sorted(
            incident.fingerprint
            for incident in watchdog.incidents
            if not incident.repeated
        )
    )
    if tuple(sorted(watchdog.new_alert_fingerprints)) != expected_alerts:
        return False
    if not isinstance(watchdog.interrupt_owner, bool):
        return False
    expected_interrupt = any(
        incident.severity in {"S1", "S2"} and not incident.repeated
        for incident in watchdog.incidents
    )
    if watchdog.interrupt_owner is not expected_interrupt:
        return False
    if watchdog.action == "ALLOW" and (
        watchdog.incidents
        or watchdog.new_alert_fingerprints
        or watchdog.interrupt_owner
    ):
        return False
    return _valid_unattended_fingerprint(watchdog.evidence_fingerprint)


def _unattended_dispatch_gate(
    guard: GuardDecision | None,
    watchdog: WatchdogDecision | None,
) -> tuple[str, tuple[str, ...]]:
    """Consume decisiones 4B/4C sin recalcular su política ni ampliar autoridad."""
    if not isinstance(guard, GuardDecision):
        return "BLOCKED", ("unattended_guard_decision_invalid",)
    if not isinstance(watchdog, WatchdogDecision):
        return "BLOCKED", ("unattended_watchdog_decision_invalid",)
    if guard.authority != "unchanged":
        return "BLOCKED", ("unattended_guard_authority_invalid",)
    if watchdog.authority != "unchanged":
        return "BLOCKED", ("unattended_watchdog_authority_invalid",)
    if guard.action not in UNATTENDED_ACTIONS:
        return "BLOCKED", ("unattended_guard_action_invalid",)
    if watchdog.action not in UNATTENDED_ACTIONS:
        return "BLOCKED", ("unattended_watchdog_action_invalid",)
    if not isinstance(guard.pause_allowed, bool):
        return "BLOCKED", ("unattended_guard_pause_contract_invalid",)
    if guard.pause_allowed is not (guard.action == "PAUSE"):
        return "BLOCKED", ("unattended_guard_pause_contract_invalid",)
    if (
        not isinstance(guard.reasons, tuple)
        or not guard.reasons
        or any(not _valid_unattended_reason(reason) for reason in guard.reasons)
        or not _valid_unattended_fingerprint(guard.evidence_fingerprint)
    ):
        return "BLOCKED", ("unattended_guard_evidence_invalid",)
    if not _valid_unattended_watchdog_contract(watchdog):
        return "BLOCKED", ("unattended_watchdog_contract_incoherent",)
    if (guard.action, watchdog.action) not in UNATTENDED_CANONICAL_PAIRS:
        return "BLOCKED", ("unattended_decisions_incoherent",)

    action = watchdog.action
    if action == "ALLOW":
        return "ALLOW", ()

    reasons: list[str] = [f"unattended_watchdog_{action.lower()}"]
    if guard.action != "ALLOW":
        reasons.append(f"unattended_guard_{guard.action.lower()}")
        reasons.extend(f"guard:{reason}" for reason in guard.reasons)
    reasons.extend(
        f"watchdog:{incident.code}"
        for incident in watchdog.incidents
    )
    return action, tuple(sorted(set(reasons)))


def _suppressed_adaptive_dispatch_record(
    candidates: list[Candidate],
    *,
    action: str,
    reasons: tuple[str, ...],
    aging_threshold: int,
    active_tranche: int | None,
) -> dict[str, object]:
    """Proyecta bloqueo desatendido sin invocar select_next/work_ladder."""
    states = {
        candidate.key: classify_readiness(candidate, active_tranche=active_tranche)
        for candidate in candidates
    }
    return {
        "selected": None,
        "selected_class": None,
        "next_action": {
            "step": "unattended_gate",
            "work": {
                "kind": "status",
                "key": "dispatcher:unattended-safe-mode",
            },
            "action": action,
            "authority": "unchanged",
            "reasons": reasons,
            "mutates": False,
        },
        "ready_not_selected": [],
        "excluded": {
            candidate.key: list(states[candidate.key].reasons)
            for candidate in candidates
        },
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
            for candidate in candidates
        },
        "aging_threshold": aging_threshold,
        "active_tranche": active_tranche,
        "suppressed_by": "unattended",
        "suppression_reasons": reasons,
    }


def adaptive_dispatch_record(
    candidates: Iterable[Candidate],
    *,
    presence: PresenceAssessment,
    fencing: FencingDecision,
    replan_action: str,
    replan_reasons: tuple[str, ...] = (),
    aging_threshold: int = 3,
    active_tranche: int | None = None,
    unattended_mode: bool = False,
    unattended_guard: GuardDecision | None = None,
    unattended_watchdog: WatchdogDecision | None = None,
) -> dict[str, object]:
    """Compone Adaptive Orchestration con Dispatcher V2 y aplica 4B/4C opt-in."""
    adapted = adapt_candidates_for_adaptive(
        candidates,
        presence=presence,
        fencing=fencing,
        replan_action=replan_action,
        replan_reasons=replan_reasons,
    )

    unattended_action = "ALLOW"
    unattended_reasons: tuple[str, ...] = ()
    if not isinstance(unattended_mode, bool):
        unattended_action = "BLOCKED"
        unattended_reasons = ("unattended_mode_invalid",)
    elif unattended_mode:
        unattended_action, unattended_reasons = _unattended_dispatch_gate(
            unattended_guard,
            unattended_watchdog,
        )

    if unattended_action != "ALLOW":
        adapted = [
            replace(
                candidate,
                external_readiness_reasons=tuple(
                    sorted(
                        set(
                            (
                                *candidate.external_readiness_reasons,
                                *unattended_reasons,
                            )
                        )
                    )
                ),
            )
            for candidate in adapted
        ]

    if unattended_action == "ALLOW":
        record = dispatch_record(
            adapted,
            aging_threshold=aging_threshold,
            active_tranche=active_tranche,
        )
    else:
        record = _suppressed_adaptive_dispatch_record(
            adapted,
            action=unattended_action,
            reasons=unattended_reasons,
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

    if unattended_mode is True or not isinstance(unattended_mode, bool):
        record["unattended"] = {
            "enabled": unattended_mode is True,
            "action": unattended_action,
            "authority": "unchanged",
            "reasons": unattended_reasons,
        }
    return record

