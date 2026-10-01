#!/usr/bin/env python3
"""Materialización pura e idempotente de trabajo narrativo en leaves de Factory."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from scripts.aceptacion_kit import AcceptanceError, contract_fingerprint, parse_contract
from scripts.work_inventory import (
    CANONICAL_REPOSITORIES,
    PRIORITY_ORDER,
    WorkInventoryError,
    project_inventory,
)

MATERIALIZABLE_KIND = "executable"
GATED_KINDS = frozenset({"future_idea", "decision_required", "live_only"})
ALLOWED_KINDS = GATED_KINDS | {MATERIALIZABLE_KIND}
NEW_LEAF_STATES = frozenset({"available", "blocked"})
MAX_COLLECTION = 50
MAX_TEXT = 500
_ROLE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_LEAF_KEY = re.compile(r"^[A-Za-z0-9_.-]+#[1-9][0-9]*$")


class WorkMaterializerError(ValueError):
    """Candidato narrativo fuera del contrato cerrado de materialización."""


def _text(value: Any, field: str, *, max_len: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise WorkMaterializerError(f"{field} debe ser texto.")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > max_len
        or "\n" in normalized
        or "\r" in normalized
        or "\x00" in normalized
    ):
        raise WorkMaterializerError(f"{field} está vacío o fuera de límites.")
    return normalized


def _items(value: Any, field: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_COLLECTION:
        raise WorkMaterializerError(f"{field} debe ser una lista acotada.")
    normalized = sorted({_text(item, f"{field}[]") for item in value})
    if not allow_empty and not normalized:
        raise WorkMaterializerError(f"{field} no puede estar vacío.")
    return normalized


def _roles(value: Any) -> list[str]:
    roles = _items(value, "roles", allow_empty=False)
    if any(_ROLE.fullmatch(role) is None for role in roles):
        raise WorkMaterializerError("roles contiene un identificador no canónico.")
    return roles


def _acceptance(body: Any) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(body, str):
        raise WorkMaterializerError("acceptance_body debe ser texto.")
    try:
        criteria = parse_contract(body)
        fingerprint = contract_fingerprint(body)
    except AcceptanceError as exc:
        raise WorkMaterializerError("acceptance_body no es ejecutable.") from exc
    return fingerprint, [
        {"id": item.id, "kind": item.kind, "target": item.target}
        for item in sorted(criteria, key=lambda criterion: criterion.id)
    ]


def validate_materialization_candidate(payload: Any) -> dict[str, Any]:
    """Valida y normaliza todo lo necesario antes de crear un leaf lógico."""
    required = {
        "identity",
        "repository_ref",
        "leaf_key",
        "title",
        "objective",
        "scope",
        "acceptance_body",
        "depends_on",
        "priority",
        "roles",
        "state",
        "kind",
        "source_ref",
        "parent_ref",
    }
    if not isinstance(payload, Mapping) or set(payload) != required:
        raise WorkMaterializerError("candidato requiere el contrato cerrado completo.")

    repository_ref = _text(payload["repository_ref"], "repository_ref")
    if repository_ref not in CANONICAL_REPOSITORIES:
        raise WorkMaterializerError("repository_ref no pertenece a la cola canónica.")
    leaf_key = _text(payload["leaf_key"], "leaf_key")
    if _LEAF_KEY.fullmatch(leaf_key) is None:
        raise WorkMaterializerError("leaf_key debe usar Repo#N canónico.")
    repository_name = repository_ref.split("/", 1)[1]
    if leaf_key.split("#", 1)[0] != repository_name:
        raise WorkMaterializerError(
            "leaf_key no pertenece al repository_ref declarado."
        )
    priority = _text(payload["priority"], "priority")
    if priority not in PRIORITY_ORDER:
        raise WorkMaterializerError("priority fuera del catálogo.")
    state = _text(payload["state"], "state")
    if state not in NEW_LEAF_STATES:
        raise WorkMaterializerError("state nuevo debe ser available o blocked.")
    kind = _text(payload["kind"], "kind")
    if kind not in ALLOWED_KINDS:
        raise WorkMaterializerError("kind fuera del catálogo.")

    acceptance_sha256, criteria = _acceptance(payload["acceptance_body"])
    return {
        "identity": _text(payload["identity"], "identity"),
        "repository_ref": repository_ref,
        "leaf_key": leaf_key,
        "title": _text(payload["title"], "title"),
        "objective": _text(payload["objective"], "objective"),
        "scope": _text(payload["scope"], "scope"),
        "acceptance_sha256": acceptance_sha256,
        "acceptance_criteria": criteria,
        "depends_on": _items(payload["depends_on"], "depends_on", allow_empty=True),
        "priority": priority,
        "roles": _roles(payload["roles"]),
        "state": state,
        "kind": kind,
        "source_ref": _text(payload["source_ref"], "source_ref"),
        "parent_ref": _text(payload["parent_ref"], "parent_ref"),
    }


def materialization_fingerprint(payload: Any) -> str:
    """Identidad estable de un candidato normalizado, independiente del orden de listas."""
    normalized = validate_materialization_candidate(payload)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _existing_identities(
    existing_leaves: Iterable[Mapping[str, Any]],
    repository_ref: str,
) -> tuple[dict[str, str | None], set[str]]:
    rows = list(existing_leaves)
    try:
        project_inventory({
            "repository_ref": repository_ref,
            "leaves": rows,
            "narrative": [],
        })
    except WorkInventoryError as exc:
        raise WorkMaterializerError(
            "existing_leaves viola el inventario canónico."
        ) from exc

    keys: dict[str, str | None] = {}
    identities: set[str] = set()
    for raw in rows:
        key = raw["key"].strip()
        identity = raw.get("source_identity")
        canonical_identity = identity.strip() if identity else None
        if canonical_identity in identities:
            raise WorkMaterializerError(
                "existing_leaves contiene source_identity duplicada."
            )
        keys[key] = canonical_identity
        if canonical_identity:
            identities.add(canonical_identity)
    return keys, identities


def materialize_leaf(
    payload: Any,
    *,
    existing_leaves: Iterable[Mapping[str, Any]] = (),
    completed_dependencies: Iterable[str] = (),
) -> dict[str, Any]:
    """Devuelve una decisión pura; nunca publica ni muta GitHub."""
    normalized = validate_materialization_candidate(payload)
    fingerprint = materialization_fingerprint(payload)

    if normalized["kind"] != MATERIALIZABLE_KIND:
        return {
            "materialized": False,
            "reason": f"gated:{normalized['kind']}",
            "fingerprint": fingerprint,
            "leaf": None,
        }

    completed = {
        _text(item, "completed_dependencies[]") for item in completed_dependencies
    }
    open_dependencies = sorted(set(normalized["depends_on"]) - completed)
    if normalized["state"] == "available" and open_dependencies:
        return {
            "materialized": False,
            "reason": "open_dependencies",
            "fingerprint": fingerprint,
            "leaf": None,
        }

    keys, identities = _existing_identities(
        existing_leaves, normalized["repository_ref"]
    )
    if normalized["identity"] in identities:
        return {
            "materialized": False,
            "reason": "already_materialized",
            "fingerprint": fingerprint,
            "leaf": None,
        }
    if normalized["leaf_key"] in keys:
        if keys[normalized["leaf_key"]] != normalized["identity"]:
            raise WorkMaterializerError(
                "leaf_key existente colisiona con otra source_identity."
            )
        return {
            "materialized": False,
            "reason": "already_materialized",
            "fingerprint": fingerprint,
            "leaf": None,
        }

    leaf = {
        "key": normalized["leaf_key"],
        "title": normalized["title"],
        "state": normalized["state"],
        "priority": normalized["priority"],
        "source_refs": [normalized["source_ref"]],
        "parent_ref": normalized["parent_ref"],
        "source_identity": normalized["identity"],
    }
    return {
        "materialized": True,
        "reason": "materialized",
        "fingerprint": fingerprint,
        "leaf": leaf,
    }
