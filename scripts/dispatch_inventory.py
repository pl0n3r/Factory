#!/usr/bin/env python3
"""Adaptador delgado entre Dispatcher V2 y el inventario canónico de trabajo."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from scripts.dispatcher_v2 import Candidate, dispatch_record
from scripts.work_inventory import (
    PROJECT_STATES,
    WorkInventoryError,
    controlbot_projection,
)

_INVENTORY_FALLBACK_ORDER = (
    "UNMATERIALIZED_WORK",
    "WAITING_DECISION",
    "LIVE_GATED",
    "ALL_BLOCKED",
    "NO_WORK",
)


def _inventory_fallback(
    projection: dict[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    """Interpreta estados ya derivados sin crear una segunda clasificación."""
    project_states: dict[str, str] = {}
    repositories_by_state: dict[str, list[str]] = {
        state: [] for state in PROJECT_STATES
    }
    unmaterialized: dict[str, tuple[str, ...]] = {}

    for project in projection["projects"]:
        repository_ref = str(project["repository_ref"])
        state = str(project["state"])
        if state not in PROJECT_STATES:
            raise WorkInventoryError("estado de inventario no canónico.")
        project_states[repository_ref] = state
        repositories_by_state[state].append(repository_ref)
        if state == "UNMATERIALIZED_WORK":
            identities = project.get("unmaterialized_identities", [])
            if not isinstance(identities, list):
                raise WorkInventoryError(
                    "unmaterialized_identities debe ser lista en la proyección canónica."
                )
            unmaterialized[repository_ref] = tuple(str(value) for value in identities)

    if "READY" in project_states.values():
        raise WorkInventoryError(
            "inventario READY sin candidato seleccionado; no declarar ausencia."
        )

    fallback_state = next(
        (
            state
            for state in _INVENTORY_FALLBACK_ORDER
            if repositories_by_state[state]
        ),
        None,
    )
    if fallback_state is None:
        raise WorkInventoryError("inventario sin estado canónico interpretable.")

    repositories = tuple(repositories_by_state[fallback_state])
    handoff: dict[str, object] = {
        "project_states": project_states,
        "states_present": tuple(sorted(set(project_states.values()))),
        "fallback_state": fallback_state,
        "repositories": repositories,
    }
    next_action: dict[str, object] = {
        "step": (
            "materialize_inventory"
            if fallback_state == "UNMATERIALIZED_WORK"
            else "inventory_state"
        ),
        "work": {
            "kind": "inventory",
            "key": f"inventory:{fallback_state.lower()}",
        },
        "reason": fallback_state,
        "repositories": repositories,
    }
    if fallback_state == "UNMATERIALIZED_WORK":
        next_action["unmaterialized_identities"] = unmaterialized

    return handoff, next_action


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

    handoff, next_action = _inventory_fallback(projection)
    result["inventory_no_candidate"] = handoff
    result["next_action"] = next_action
    return result
