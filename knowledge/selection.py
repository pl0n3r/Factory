"""Selección scoped de Knowledge Items para Context Compiler."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from evolution.knowledge_lifecycle import KnowledgeLifecycleError
from knowledge.contract import (
    KnowledgeContractError,
    knowledge_item_status,
    validate_knowledge_item,
)

VERSION = 1
MAX_CATALOG_ITEMS = 500
MAX_SELECTED_ITEMS = 12
MAX_PAYLOAD_BYTES = 100_000

CONTEXT_CATEGORIES = frozenset({"decision", "lesson", "constraint", "evidence"})
ITEM_CATEGORY = {
    "decision": "decision",
    "adr": "decision",
    "runbook": "constraint",
    "postmortem": "evidence",
    "architecture_invariant": "constraint",
    "product_rule": "constraint",
    "operational_procedure": "constraint",
    "troubleshooting": "constraint",
    "known_limitation": "constraint",
    "experiment_result": "evidence",
    "lesson_guardrail_candidate": "lesson",
}

_MISSION_FIELDS = frozenset(
    {
        "version",
        "project",
        "domain",
        "tags",
        "categories",
        "require_current",
        "max_items",
        "now_at",
    }
)
_PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
_TAG = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(?:password|passwd|secret|token|cookie|authorization|api[_-]?key|"
    r"private[_-]?key|email|phone|address|document|ip[_-]?address)(?:$|[_-])",
    re.IGNORECASE,
)


class KnowledgeSelectionError(ValueError):
    """Misión o catálogo no aptos para selección de contexto."""


def _payload_size(payload: Any) -> None:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise KnowledgeSelectionError(
            "entrada debe ser JSON finito y serializable."
        ) from exc
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise KnowledgeSelectionError("entrada excede el tamaño máximo.")


def _mission(payload: Any) -> dict[str, Any]:
    _payload_size(payload)
    if not isinstance(payload, Mapping):
        raise KnowledgeSelectionError("mission debe ser objeto.")
    if not all(isinstance(key, str) for key in payload):
        raise KnowledgeSelectionError("mission contiene campos inválidos.")
    if any(_SENSITIVE_KEY.search(key) for key in payload):
        raise KnowledgeSelectionError("mission contiene campo sensible no permitido.")
    if set(payload) != _MISSION_FIELDS:
        raise KnowledgeSelectionError(
            "mission contiene campos faltantes o no permitidos."
        )
    if payload["version"] != VERSION:
        raise KnowledgeSelectionError("mission.version fuera del contrato v1.")

    project = payload["project"]
    if not isinstance(project, str) or _PROJECT.fullmatch(project) is None:
        raise KnowledgeSelectionError("mission.project inválido.")

    domain = payload["domain"]
    if not isinstance(domain, str) or _ID.fullmatch(domain) is None:
        raise KnowledgeSelectionError("mission.domain inválido.")

    tags = payload["tags"]
    if (
        not isinstance(tags, list)
        or len(tags) > 24
        or not all(isinstance(item, str) and _TAG.fullmatch(item) for item in tags)
        or len(tags) != len(set(tags))
    ):
        raise KnowledgeSelectionError("mission.tags debe ser lista única y acotada.")

    categories = payload["categories"]
    if (
        not isinstance(categories, list)
        or not categories
        or len(categories) > len(CONTEXT_CATEGORIES)
        or not all(item in CONTEXT_CATEGORIES for item in categories)
        or len(categories) != len(set(categories))
    ):
        raise KnowledgeSelectionError(
            "mission.categories debe usar categorías admitidas."
        )

    require_current = payload["require_current"]
    if not isinstance(require_current, bool):
        raise KnowledgeSelectionError("mission.require_current debe ser booleano.")

    max_items = payload["max_items"]
    if (
        isinstance(max_items, bool)
        or not isinstance(max_items, int)
        or not 1 <= max_items <= MAX_SELECTED_ITEMS
    ):
        raise KnowledgeSelectionError("mission.max_items fuera de límites.")

    now_at = payload["now_at"]
    if not isinstance(now_at, str) or not now_at.strip():
        raise KnowledgeSelectionError("mission.now_at inválido.")

    return {
        "version": VERSION,
        "project": project,
        "domain": domain,
        "tags": sorted(tags),
        "categories": sorted(categories),
        "require_current": require_current,
        "max_items": max_items,
        "now_at": now_at,
    }


def _validated_items(raw_items: Any) -> list[dict[str, Any]]:
    _payload_size(raw_items)
    if (
        not isinstance(raw_items, Sequence)
        or isinstance(raw_items, (str, bytes))
        or not 1 <= len(raw_items) <= MAX_CATALOG_ITEMS
    ):
        raise KnowledgeSelectionError(
            "knowledge_items debe ser lista no vacía y acotada."
        )
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    try:
        for raw in raw_items:
            item = validate_knowledge_item(raw)
            if item["item_id"] in ids:
                raise KnowledgeSelectionError("knowledge_items contiene ids duplicados.")
            ids.add(item["item_id"])
            result.append(item)
    except (KnowledgeContractError, TypeError, ValueError) as exc:
        if isinstance(exc, KnowledgeSelectionError):
            raise
        raise KnowledgeSelectionError("knowledge_item inválido.") from exc
    return result


def _matches_mission(item: dict[str, Any], mission: dict[str, Any]) -> bool:
    scope = item["lifecycle"]["scope"]
    if scope["project"] != mission["project"] or scope["domain"] != mission["domain"]:
        return False
    category = ITEM_CATEGORY[item["item_class"]]
    if category not in mission["categories"]:
        return False
    mission_tags = set(mission["tags"])
    return not mission_tags or bool(mission_tags.intersection(item["tags"]))


def _context_projection(item: dict[str, Any], category: str) -> dict[str, Any]:
    return {
        "category": category,
        "source": f"knowledge:{item['item_id']}",
        "text": f"{item['title']}: {item['summary']}",
        "tags": list(item["tags"]),
    }


def select_knowledge_for_context(*, mission: Any, knowledge_items: Any) -> dict[str, Any]:
    """Selecciona conocimiento current, scoped y compatible sin ejecutar I/O."""
    normalized_mission = _mission(mission)
    items = _validated_items(knowledge_items)

    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in items:
        if not _matches_mission(item, normalized_mission):
            continue
        if item["sensitivity"] != "normal":
            raise KnowledgeSelectionError(
                "knowledge_item sensible no permitido para Context Compiler."
            )
        try:
            status = knowledge_item_status(
                item,
                now_at=normalized_mission["now_at"],
            )
        except (KnowledgeContractError, KnowledgeLifecycleError, TypeError, ValueError) as exc:
            raise KnowledgeSelectionError("knowledge_item lifecycle inválido.") from exc
        if not status["current"]:
            continue
        category = ITEM_CATEGORY[item["item_class"]]
        candidates.append(
            (
                _context_projection(item, category),
                {
                    "item_id": item["item_id"],
                    "category": category,
                    "provenance": list(item["lifecycle"]["provenance"]),
                    "authority_class": item["authority_class"],
                    "state": status["state"],
                    "source": "knowledge-contract-v1",
                    "authority": "unchanged",
                },
            )
        )

    candidates.sort(
        key=lambda pair: (
            pair[0]["category"],
            pair[1]["item_id"],
        )
    )
    selected = candidates[: normalized_mission["max_items"]]

    if normalized_mission["require_current"] and not selected:
        raise KnowledgeSelectionError(
            "mission requiere conocimiento current y no existe selección compatible."
        )

    return {
        "version": VERSION,
        "mission": normalized_mission,
        "context_items": [context for context, _ in selected],
        "bindings": [binding for _, binding in selected],
        "selected_count": len(selected),
        "selection_policy": "exact-scope+category+tag;lexical-order;no-score",
    }
