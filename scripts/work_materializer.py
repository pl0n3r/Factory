#!/usr/bin/env python3
"""Convierte trabajo narrativo ejecutable en especificaciones de Issue reservables."""
from __future__ import annotations
import json
from typing import Any, Iterable, Mapping
from scripts.aceptacion_kit import parse_contract

DEFERRED = frozenset({"decision_required", "live_only", "future_idea", "already_materialized"})
PRIORITIES = frozenset({"crítica", "alta", "media"})


class MaterializationError(ValueError):
    pass


def _required(item: Mapping[str, Any], name: str) -> Any:
    value = item.get(name)
    if value in (None, "", [], ()):
        raise MaterializationError(f"missing required field: {name}")
    return value


def materialize_leaf(
    item: Mapping[str, Any],
    existing_leaves: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    classification = item.get("classification")
    source_key = str(_required(item, "source_key"))
    existing = [dict(row) for row in existing_leaves
                if str(row.get("source_key") or row.get("key") or "") == source_key]
    if existing:
        return {"action": "reused", "leaf": existing[0]}
    if classification in DEFERRED:
        return {"action": "deferred", "source_key": source_key, "classification": classification}
    if classification not in {"leaf_ready", "leaf_blocked"}:
        raise MaterializationError("unsupported narrative classification")

    title = str(_required(item, "title"))
    objective, scope = str(_required(item, "objective")), str(_required(item, "scope"))
    outside = str(_required(item, "out_of_scope"))
    evidence, parent = str(_required(item, "evidence_ref")), str(_required(item, "parent_ref"))
    priority = str(_required(item, "priority"))
    roles = list(_required(item, "roles"))
    dependencies = list(item.get("dependencies") or [])
    criteria = list(_required(item, "acceptance"))
    if priority not in PRIORITIES or not all(isinstance(role, str) and role for role in roles):
        raise MaterializationError("invalid priority or roles")

    machine, human = [], []
    for index, criterion in enumerate(criteria, 1):
        if not isinstance(criterion, Mapping):
            raise MaterializationError("acceptance criterion must be an object")
        cid = f"AC-{index:02d}"
        kind, target = criterion.get("kind"), criterion.get("target")
        description = str(criterion.get("description") or target or "")
        machine.append({"id": cid, "kind": kind, "target": target})
        human.append(f"- [ ] [{cid}] {description}")
    marker = json.dumps({"version": 1, "criteria": machine},
                        ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    source = json.dumps({"version": 1, "source_key": source_key, "parent_ref": parent,
                         "evidence_ref": evidence}, separators=(",", ":"), sort_keys=True)
    body = f"""### Contexto

Parent: {parent}. Evidencia: {evidence}. Fuente: {source_key}.

### Alcance

{objective}

{scope}

### Fuera de alcance

{outside}

### Criterios de aceptación

{chr(10).join(human)}

### Contrato ejecutable

<!-- factory-acceptance {marker} -->

<!-- factory-work-source {source} -->"""
    parse_contract(body)
    status = "blocked" if classification == "leaf_blocked" or dependencies else "available"
    leaf = {
        "key": source_key, "source_key": source_key, "title": title, "body": body,
        "status": status, "evidence_ref": evidence, "dependencies": dependencies,
        "labels": ["tipo: producto", f"prioridad: {priority}",
                   f"estado: {'disponible' if status == 'available' else 'bloqueado'}"]
                  + [f"rol: {role}" for role in roles],
    }
    return {"action": "created", "leaf": leaf}


def materialize_detected_work(
    items: Iterable[Mapping[str, Any]],
    existing_leaves: Iterable[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    known = [dict(row) for row in existing_leaves]
    results = []
    for item in items:
        result = materialize_leaf(item, known)
        results.append(result)
        if result["action"] == "created":
            known.append(result["leaf"])
    return tuple(results)
