#!/usr/bin/env python3
"""Handoff read-only del ciclo desatendido canónico para consumidores."""

from __future__ import annotations

CYCLE_FIELDS = frozenset(
    {
        "version",
        "action",
        "authority",
        "selected",
        "selected_class",
        "freshness",
        "reasons",
        "provenance",
        "components",
    }
)
ACTIONS = frozenset({"ALLOW", "PAUSE", "BLOCKED"})
FRESHNESS = frozenset({"fresh", "stale", "unknown"})
PROVENANCE_FIELDS = frozenset(
    {"head_sha", "dispatch_ref", "guard_ref", "watchdog_ref", "freshness"}
)
WATCHDOG_FIELDS = frozenset(
    {"action", "incident_codes", "state_freshness", "interrupt_owner", "evidence_ref"}
)
PERMISSIONS = {
    "reserve": False,
    "merge": False,
    "deploy": False,
    "spend": False,
    "live": False,
}


def _blocked(reason: str) -> dict[str, object]:
    return {
        "version": 1,
        "action": "BLOCKED",
        "next_transition": "BLOCKED",
        "authority": "unchanged",
        "work_identity": None,
        "work_class": None,
        "freshness": "unknown",
        "reasons": (reason,),
        "provenance": None,
        "incidents": (),
        "interrupt_owner": None,
        "permissions": dict(PERMISSIONS),
    }


def _valid_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value.strip() == value
        and len(value) <= 512
    )


def _valid_provenance(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != PROVENANCE_FIELDS:
        return False
    return (
        _valid_text(value["head_sha"])
        and _valid_text(value["dispatch_ref"])
        and _valid_text(value["guard_ref"])
        and _valid_text(value["watchdog_ref"])
        and value["freshness"] in FRESHNESS
    )


def _watchdog_projection(
    components: object,
) -> tuple[tuple[str, ...], bool | None] | None:
    if not isinstance(components, dict):
        return None
    if not components:
        return ((), None)

    watchdog = components.get("watchdog")
    if not isinstance(watchdog, dict) or set(watchdog) != WATCHDOG_FIELDS:
        return None
    if watchdog["action"] not in ACTIONS:
        return None
    incidents = watchdog["incident_codes"]
    if (
        not isinstance(incidents, tuple)
        or any(not _valid_text(item) for item in incidents)
        or len(incidents) != len(set(incidents))
    ):
        return None
    interrupt_owner = watchdog["interrupt_owner"]
    if not isinstance(interrupt_owner, bool):
        return None
    if watchdog["state_freshness"] not in FRESHNESS:
        return None
    if not _valid_text(watchdog["evidence_ref"]):
        return None
    return (incidents, interrupt_owner)


def project_unattended_cycle_handoff(cycle: object) -> dict[str, object]:
    """Proyecta un envelope ya calculado sin I/O, ranking ni mutaciones."""

    if not isinstance(cycle, dict) or set(cycle) != CYCLE_FIELDS:
        return _blocked("handoff_cycle_invalid")

    if (
        cycle["version"] != 1
        or cycle["action"] not in ACTIONS
        or cycle["authority"] != "unchanged"
        or cycle["freshness"] not in FRESHNESS
    ):
        return _blocked("handoff_cycle_invalid")

    selected = cycle["selected"]
    selected_class = cycle["selected_class"]
    if selected is not None and not _valid_text(selected):
        return _blocked("handoff_cycle_invalid")
    if selected_class is not None and not _valid_text(selected_class):
        return _blocked("handoff_cycle_invalid")

    reasons = cycle["reasons"]
    if (
        not isinstance(reasons, tuple)
        or any(not _valid_text(reason) for reason in reasons)
        or len(reasons) != len(set(reasons))
    ):
        return _blocked("handoff_cycle_invalid")

    provenance = cycle["provenance"]
    if provenance is not None and not _valid_provenance(provenance):
        return _blocked("handoff_provenance_invalid")
    if cycle["action"] != "BLOCKED" and provenance is None:
        return _blocked("handoff_provenance_invalid")

    watchdog = _watchdog_projection(cycle["components"])
    if watchdog is None:
        return _blocked("handoff_components_invalid")
    incidents, interrupt_owner = watchdog

    return {
        "version": 1,
        "action": cycle["action"],
        "next_transition": cycle["action"],
        "authority": "unchanged",
        "work_identity": selected,
        "work_class": selected_class,
        "freshness": cycle["freshness"],
        "reasons": reasons,
        "provenance": None if provenance is None else dict(provenance),
        "incidents": incidents,
        "interrupt_owner": interrupt_owner,
        "permissions": dict(PERMISSIONS),
    }


__all__ = ["project_unattended_cycle_handoff"]
