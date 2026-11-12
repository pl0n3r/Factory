#!/usr/bin/env python3
"""Adaptador delgado entre Dispatcher V2 y el inventario canónico de trabajo."""
from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json
import re
from typing import Any

from scripts.dispatcher_v2 import Candidate, dispatch_record
from scripts.work_inventory import (
    CANONICAL_REPOSITORIES,
    PROJECT_STATES,
    WorkInventoryError,
    build_factory_inventory,
    controlbot_projection,
)


def dispatch_record_with_inventory(
    candidates: Iterable[Candidate],
    *,
    work_inventory: dict[str, Any],
    aging_threshold: int = 3,
    active_tranche: int | None = None,
) -> dict[str, object]:
    """Compone inventario derivado sin reimplementar ranking ni selección."""
    record = dispatch_record(
        candidates,
        aging_threshold=aging_threshold,
        active_tranche=active_tranche,
    )
    projection = controlbot_projection(work_inventory)
    result = dict(record)
    result["work_inventory"] = projection

    if record["selected"] is not None:
        result["inventory_no_candidate"] = None
        return result

    project_states: dict[str, str] = {}
    ready_with_available: list[str] = []
    reserved_only_projects: list[str] = []
    for project in projection["projects"]:
        repository_ref = str(project["repository_ref"])
        state = str(project["state"])
        if state not in PROJECT_STATES:
            raise WorkInventoryError("estado de inventario no canónico.")
        project_states[repository_ref] = state

        if state != "READY":
            continue

        counts = project.get("counts")
        if not isinstance(counts, dict):
            raise WorkInventoryError("inventario READY sin conteos canónicos.")
        available = counts.get("available")
        reserved = counts.get("reserved")
        if (
            type(available) is not int
            or type(reserved) is not int
            or available < 0
            or reserved < 0
        ):
            raise WorkInventoryError("inventario READY con conteos inválidos.")
        if available > 0:
            ready_with_available.append(repository_ref)
        elif reserved > 0:
            reserved_only_projects.append(repository_ref)
        else:
            raise WorkInventoryError(
                "inventario READY sin trabajo available/reserved."
            )

    if ready_with_available:
        raise WorkInventoryError(
            "inventario READY con trabajo disponible sin candidato seleccionado; "
            "no declarar ausencia."
        )

    states_present = tuple(sorted(set(project_states.values())))
    reserved_only = tuple(sorted(reserved_only_projects))
    result["inventory_no_candidate"] = {
        "project_states": project_states,
        "states_present": states_present,
        "reserved_only_projects": reserved_only,
    }

    state_priority = (
        "UNMATERIALIZED_WORK",
        "WAITING_DECISION",
        "LIVE_GATED",
        "ALL_BLOCKED",
        "READY",
        "NO_WORK",
    )
    inventory_state = next(
        (state for state in state_priority if state in states_present),
        None,
    )
    if inventory_state is None:
        raise WorkInventoryError(
            "inventario sin candidato no contiene un estado interpretable."
        )

    if inventory_state == "READY" and not reserved_only:
        raise WorkInventoryError(
            "inventario READY sin candidato no demuestra una reserva ajena."
        )

    action: dict[str, object] = {
        "step": (
            "materialize_inventory"
            if inventory_state == "UNMATERIALIZED_WORK"
            else "reserved_inventory"
            if inventory_state == "READY"
            else "inventory_state"
        ),
        "work": {
            "kind": "inventory",
            "key": "factory:work-inventory",
        },
        "state": inventory_state,
        "project_states": project_states,
        "mutates": False,
    }
    if inventory_state == "READY":
        action.update({
            "reason": "reserved_only_no_selectable_candidate",
            "reserved_only_projects": reserved_only,
            "session_selectable": False,
        })
    result["next_action"] = action
    return result


# Contrato de snapshot declarativo, estrictamente offline.
OFFLINE_KEYS = frozenset({
    "version", "policy_sha", "kill_switch", "projects", "candidates",
    "seen_idempotency_keys",
})
OFFLINE_CANDIDATE_KEYS = frozenset({
    "key", "repository_ref", "priority", "dependencies_open",
    "incompatible_reservation", "pending_human_gate", "claims",
    "active_claims", "requires_extra_authority", "idempotency_key",
    "policy_verified", "evidence_verified",
})
OFFLINE_SHA = re.compile(r"[0-9a-f]{64}")
OFFLINE_TOKEN = re.compile(r"[A-Za-z0-9_./:#-]{1,128}")
OFFLINE_CLAIM = re.compile(r"[A-Za-z0-9_./-]{1,160}")


class OfflineDispatchError(ValueError):
    """Snapshot offline no verificable; nunca crea autoridad para ejecución."""


def _offline_sequence(value: object, *, name: str, limit: int = 100) -> list:
    if not isinstance(value, list) or len(value) > limit:
        raise OfflineDispatchError("invalid_" + name)
    return value


def _offline_claims(value: object, *, name: str) -> frozenset[str]:
    items = _offline_sequence(value, name=name)
    if any(
        not isinstance(item, str)
        or OFFLINE_CLAIM.fullmatch(item) is None
        or item.startswith("/")
        or ".." in item.split("/")
        for item in items
    ):
        raise OfflineDispatchError("invalid_" + name)
    if len(set(items)) != len(items):
        raise OfflineDispatchError("duplicate_" + name)
    return frozenset(items)


def offline_proposal_from_snapshot(
    snapshot: object, *, policy_sha: str,
) -> dict[str, object]:
    """Usa inventario/Dispatcher V2 existentes; propone, jamás publica."""
    if not isinstance(snapshot, dict) or set(snapshot) != OFFLINE_KEYS:
        raise OfflineDispatchError("invalid_offline_snapshot")
    if type(snapshot["version"]) is not int or snapshot["version"] != 1:
        raise OfflineDispatchError("invalid_offline_version")
    if (
        not isinstance(policy_sha, str)
        or OFFLINE_SHA.fullmatch(policy_sha) is None
        or snapshot["policy_sha"] != policy_sha
    ):
        raise OfflineDispatchError("policy_sha_mismatch")

    switch = snapshot["kill_switch"]
    if (
        not isinstance(switch, dict)
        or set(switch) != {"version", "state", "owner"}
        or type(switch["version"]) is not int
        or switch["version"] != 1
        or switch["owner"] != "pl0n3r"
        or not isinstance(switch["state"], str)
        or switch["state"] not in {"RUNNING", "PAUSED", "UNKNOWN"}
    ):
        raise OfflineDispatchError("invalid_offline_switch")
    projects = _offline_sequence(snapshot["projects"], name="projects", limit=7)
    inventory = build_factory_inventory(projects)
    if [project["repository_ref"] for project in projects] != list(CANONICAL_REPOSITORIES):
        raise OfflineDispatchError("inventory_order_invalid")

    available: dict[str, tuple[str, str]] = {}
    for project in projects:
        for leaf in project["leaves"]:
            if leaf["state"] != "available":
                continue
            if leaf["key"] in available:
                raise OfflineDispatchError("duplicate_available_key")
            available[leaf["key"]] = (project["repository_ref"], leaf["priority"])

    rows = _offline_sequence(snapshot["candidates"], name="candidates")
    seen = _offline_sequence(snapshot["seen_idempotency_keys"], name="seen_keys", limit=500)
    if any(
        not isinstance(value, str) or OFFLINE_SHA.fullmatch(value) is None
        for value in seen
    ) or len(set(seen)) != len(seen):
        raise OfflineDispatchError("invalid_seen_keys")

    candidates: list[Candidate] = []
    by_key: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != OFFLINE_CANDIDATE_KEYS:
            raise OfflineDispatchError("invalid_offline_candidate")
        key, repo, priority = row["key"], row["repository_ref"], row["priority"]
        if (
            not isinstance(repo, str)
            or repo not in CANONICAL_REPOSITORIES
            or not isinstance(key, str)
            or re.fullmatch(
                re.escape(repo.split("/", 1)[1]) + r"#[1-9][0-9]{0,9}", key
            ) is None
            or not isinstance(priority, str)
            or priority not in {"critical", "high", "medium"}
            or available.get(key) != (repo, priority)
            or key in by_key
            or not isinstance(row["idempotency_key"], str)
            or OFFLINE_TOKEN.fullmatch(row["idempotency_key"]) is None
        ):
            raise OfflineDispatchError("invalid_offline_identity")
        for flag in (
            "incompatible_reservation", "pending_human_gate",
            "requires_extra_authority", "policy_verified", "evidence_verified",
        ):
            if type(row[flag]) is not bool:
                raise OfflineDispatchError("invalid_offline_gate")
        deps = _offline_sequence(row["dependencies_open"], name="dependencies")
        if any(
            not isinstance(dep, str) or OFFLINE_TOKEN.fullmatch(dep) is None
            for dep in deps
        ) or len(set(deps)) != len(deps):
            raise OfflineDispatchError("invalid_dependencies")
        claims = _offline_claims(row["claims"], name="claims")
        if not claims:
            raise OfflineDispatchError("missing_claims")
        active = _offline_claims(row["active_claims"], name="active_claims")
        candidates.append(Candidate(
            key=key,
            priority=priority,
            dependencies_open=tuple(deps),
            incompatible_reservation=row["incompatible_reservation"],
            pending_human_gate=row["pending_human_gate"],
            requires_extra_authority=row["requires_extra_authority"],
            claims=claims,
            active_claims=active,
            external_readiness_reasons=tuple(
                flag for flag in ("policy_verified", "evidence_verified")
                if row[flag] is not True
            ),
            metadata={"repository_ref": repo},
        ))
        by_key[key] = row
    if set(by_key) != set(available):
        raise OfflineDispatchError("missing_inventory_candidates")

    receipt: dict[str, object] = {
        "version": 1,
        "decision": "BLOCKED",
        "reason": "no_safe_candidate",
        "selected": None,
        "policy_sha": policy_sha,
        "order_proposal": None,
        "sent_count": 0,
        "execution": "OFFLINE_ONLY",
        "authority": "snapshot_only_not_verified_for_live",
    }
    if switch["state"] != "RUNNING":
        receipt["reason"] = "kill_switch_not_running"
        return receipt

    try:
        record = dispatch_record_with_inventory(candidates, work_inventory=inventory)
    except WorkInventoryError:
        # Disponible en inventario, pero sin candidato elegible por gates.
        return receipt
    selected = record["selected"]
    if selected is None:
        return receipt
    candidate = by_key[selected]
    digest = hashlib.sha256(json.dumps(
        [policy_sha, selected, candidate["idempotency_key"]],
        ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    receipt["selected"] = selected
    if digest in seen:
        receipt["decision"] = "REPLAY"
        receipt["reason"] = "already_proposed"
        return receipt
    receipt["decision"] = "PROPOSED"
    receipt["reason"] = None
    receipt["order_proposal"] = {
        "kind": "OFFLINE_PROPOSAL",
        "work_id": selected,
        "repository_ref": candidate["repository_ref"],
        "order_id": "offline-" + digest[:32],
        "idempotency_key": digest,
        "policy_sha": policy_sha,
        "executed": False,
    }
    return receipt
