#!/usr/bin/env python3
"""Inventario derivado y determinista del trabajo restante de la fábrica."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANONICAL_REPOSITORIES = (
    "pl0n3r/Factory",
    "pl0n3r/Condor",
    "pl0n3r/GrindFlow",
    "pl0n3r/brvtal",
    "pl0n3r/ControlBot",
    "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
)
PROJECT_STATES = frozenset(
    {"READY", "ALL_BLOCKED", "UNMATERIALIZED_WORK", "WAITING_DECISION", "LIVE_GATED", "NO_WORK"}
)
LEAF_STATES = frozenset({"available", "reserved", "blocked", "completed"})
NARRATIVE_KINDS = frozenset({"executable", "decision_required", "live_only", "future_idea"})
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class WorkInventoryError(ValueError):
    """Snapshot fuera del contrato de inventario."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise WorkInventoryError(f"{field} debe ser texto no vacío de una línea.")
    return value.strip()


def _refs(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 100:
        raise WorkInventoryError(f"{field} debe ser una lista acotada.")
    return tuple(sorted({_text(item, f"{field}[]") for item in value}))


def _leaf(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise WorkInventoryError("leaf debe ser objeto.")
    required = {"key", "title", "state", "priority", "source_refs"}
    optional = {"parent_ref", "source_identity"}
    if set(raw) - required - optional or required - set(raw):
        raise WorkInventoryError("leaf tiene campos inválidos o incompletos.")
    state = _text(raw["state"], "leaf.state")
    priority = _text(raw["priority"], "leaf.priority")
    if state not in LEAF_STATES or priority not in PRIORITY_ORDER:
        raise WorkInventoryError("leaf state/priority fuera de catálogo.")
    return {
        "key": _text(raw["key"], "leaf.key"),
        "title": _text(raw["title"], "leaf.title"),
        "state": state,
        "priority": priority,
        "source_refs": _refs(raw["source_refs"], "leaf.source_refs"),
        "parent_ref": _text(raw["parent_ref"], "leaf.parent_ref") if raw.get("parent_ref") else None,
        "source_identity": _text(raw["source_identity"], "leaf.source_identity") if raw.get("source_identity") else None,
    }


def _narrative(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise WorkInventoryError("narrative debe ser objeto.")
    required = {"identity", "title", "kind", "source_ref"}
    optional = {"expected_leaf_key"}
    if set(raw) - required - optional or required - set(raw):
        raise WorkInventoryError("narrative tiene campos inválidos o incompletos.")
    kind = _text(raw["kind"], "narrative.kind")
    if kind not in NARRATIVE_KINDS:
        raise WorkInventoryError("narrative.kind fuera de catálogo.")
    return {
        "identity": _text(raw["identity"], "narrative.identity"),
        "title": _text(raw["title"], "narrative.title"),
        "kind": kind,
        "source_ref": _text(raw["source_ref"], "narrative.source_ref"),
        "expected_leaf_key": _text(raw["expected_leaf_key"], "narrative.expected_leaf_key")
        if raw.get("expected_leaf_key") else None,
    }


def project_inventory(snapshot: Any) -> dict[str, Any]:
    """Normaliza una fuente canónica y devuelve solo una vista derivada."""
    if not isinstance(snapshot, Mapping) or set(snapshot) != {"repository_ref", "leaves", "narrative"}:
        raise WorkInventoryError("snapshot requiere repository_ref, leaves y narrative.")
    repo = _text(snapshot["repository_ref"], "repository_ref")
    if repo not in CANONICAL_REPOSITORIES:
        raise WorkInventoryError("repository_ref no pertenece a la cola canónica.")
    if not isinstance(snapshot["leaves"], list) or not isinstance(snapshot["narrative"], list):
        raise WorkInventoryError("leaves/narrative deben ser listas.")

    leaves = [_leaf(item) for item in snapshot["leaves"]]
    if len({item["key"] for item in leaves}) != len(leaves):
        raise WorkInventoryError("leaf key duplicada.")
    narratives = [_narrative(item) for item in snapshot["narrative"]]
    if len({item["identity"] for item in narratives}) != len(narratives):
        raise WorkInventoryError("narrative identity duplicada.")

    leaf_keys = {item["key"] for item in leaves}
    materialized_identities = {item["source_identity"] for item in leaves if item["source_identity"]}
    counts = {name: 0 for name in (
        "completed", "available", "reserved", "blocked", "unmaterialized",
        "decision_required", "live_only", "future_idea", "already_materialized",
    )}
    for item in leaves:
        counts[item["state"]] += 1

    hidden = []
    for item in narratives:
        materialized = (
            item["identity"] in materialized_identities
            or (item["expected_leaf_key"] is not None and item["expected_leaf_key"] in leaf_keys)
        )
        if materialized:
            counts["already_materialized"] += 1
        elif item["kind"] == "executable":
            counts["unmaterialized"] += 1
            hidden.append(item["identity"])
        else:
            counts[item["kind"]] += 1

    ready = [item for item in leaves if item["state"] in {"available", "reserved"}]
    ready.sort(key=lambda item: (
        0 if item["state"] == "available" else 1,
        PRIORITY_ORDER[item["priority"]],
        item["key"],
    ))
    if ready:
        state = "READY"
    elif counts["unmaterialized"]:
        state = "UNMATERIALIZED_WORK"
    elif counts["decision_required"]:
        state = "WAITING_DECISION"
    elif counts["live_only"]:
        state = "LIVE_GATED"
    elif counts["blocked"]:
        state = "ALL_BLOCKED"
    elif counts["future_idea"]:
        state = "UNMATERIALIZED_WORK"
    else:
        state = "NO_WORK"

    parents: dict[str, list[dict[str, Any]]] = {}
    for item in leaves:
        if item["parent_ref"]:
            parents.setdefault(item["parent_ref"], []).append(item)
    progress = []
    for parent_ref, children in sorted(parents.items()):
        completed = sum(item["state"] == "completed" for item in children)
        progress.append({
            "parent_ref": parent_ref,
            "completed": completed,
            "total": len(children),
            "percent": (completed * 100) // len(children),
        })

    return {
        "repository_ref": repo,
        "state": state,
        "counts": counts,
        "next_work": ready[0]["key"] if ready else None,
        "unmaterialized_identities": sorted(hidden),
        "parent_progress": progress,
    }


def build_factory_inventory(snapshots: list[Mapping[str, Any]]) -> dict[str, Any]:
    projects = [project_inventory(snapshot) for snapshot in snapshots]
    by_repo = {project["repository_ref"]: project for project in projects}
    if len(by_repo) != len(projects) or set(by_repo) != set(CANONICAL_REPOSITORIES):
        raise WorkInventoryError("el inventario requiere exactamente los siete repos canónicos.")
    return {"version": 1, "projects": [by_repo[repo] for repo in CANONICAL_REPOSITORIES]}


def controlbot_projection(inventory: Any) -> dict[str, Any]:
    """ControlBot consume el mismo payload; no recalcula una fuente paralela."""
    if not isinstance(inventory, dict) or inventory.get("version") != 1 or not isinstance(inventory.get("projects"), list):
        raise WorkInventoryError("inventario canónico inválido.")
    if [p.get("repository_ref") for p in inventory["projects"]] != list(CANONICAL_REPOSITORIES):
        raise WorkInventoryError("inventario canónico incompleto o desordenado.")
    return inventory


def validate_initial_sweep(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {"version", "observed_on", "projects"} or payload["version"] != 1:
        raise WorkInventoryError("artefacto inicial inválido.")
    _text(payload["observed_on"], "observed_on")
    if not isinstance(payload["projects"], list):
        raise WorkInventoryError("projects debe ser lista.")
    repos = []
    for row in payload["projects"]:
        if not isinstance(row, dict) or set(row) != {"repository_ref", "source_refs", "leaf_refs"}:
            raise WorkInventoryError("fila de barrido inválida.")
        repo = _text(row["repository_ref"], "repository_ref")
        if repo not in CANONICAL_REPOSITORIES or not _refs(row["source_refs"], "source_refs"):
            raise WorkInventoryError("barrido sin fuente canónica.")
        _refs(row["leaf_refs"], "leaf_refs")
        repos.append(repo)
    if tuple(repos) != CANONICAL_REPOSITORIES:
        raise WorkInventoryError("barrido debe cubrir los siete repos en orden canónico.")
