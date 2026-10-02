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
    for project in projection["projects"]:
        repository_ref = str(project["repository_ref"])
        state = str(project["state"])
        if state not in PROJECT_STATES:
            raise WorkInventoryError("estado de inventario no canónico.")
        project_states[repository_ref] = state

    if "READY" in project_states.values():
        raise WorkInventoryError(
            "inventario READY sin candidato seleccionado; no declarar ausencia."
        )

    states_present = tuple(sorted(set(project_states.values())))
    result["inventory_no_candidate"] = {
        "project_states": project_states,
        "states_present": states_present,
    }

    state_priority = (
        "UNMATERIALIZED_WORK",
        "WAITING_DECISION",
        "LIVE_GATED",
        "ALL_BLOCKED",
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

    result["next_action"] = {
        "step": (
            "materialize_inventory"
            if inventory_state == "UNMATERIALIZED_WORK"
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
    return result
