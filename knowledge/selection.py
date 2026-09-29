"""Selección scoped/current de Knowledge Items para Context Compiler."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import json, re
from typing import Any

from evolution.knowledge_lifecycle import KnowledgeLifecycleError
from knowledge.contract import (
    KnowledgeContractError, knowledge_item_status, validate_knowledge_item,
)

VERSION, MAX_CATALOG_ITEMS, MAX_SELECTED_ITEMS = 1, 500, 12
CONTEXT_CATEGORIES = frozenset({"decision", "lesson", "constraint", "evidence"})
ITEM_CATEGORY = {
    "decision": "decision", "adr": "decision",
    "runbook": "constraint", "postmortem": "evidence",
    "architecture_invariant": "constraint", "product_rule": "constraint",
    "operational_procedure": "constraint", "troubleshooting": "constraint",
    "known_limitation": "constraint", "experiment_result": "evidence",
    "lesson_guardrail_candidate": "lesson",
}
_FIELDS = {
    "version", "project", "domain", "tags", "categories",
    "require_current", "max_items", "now_at",
}
_PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
_TAG = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")


class KnowledgeSelectionError(ValueError):
    """Misión o catálogo no aptos para selección de contexto."""


def select_knowledge_for_context(*, mission: Any, knowledge_items: Any) -> dict[str, Any]:
    """Selecciona contexto mínimo sin I/O ni expansión de authority."""
    query = _mission(mission)
    items = _items(knowledge_items)
    selected = []
    for item in items:
        if not _matches(item, query):
            continue
        if item["sensitivity"] != "normal":
            raise KnowledgeSelectionError("knowledge_item sensible no permitido.")
        try:
            status = knowledge_item_status(item, now_at=query["now_at"])
        except (KnowledgeContractError, KnowledgeLifecycleError, TypeError, ValueError) as exc:
            raise KnowledgeSelectionError("knowledge_item lifecycle inválido.") from exc
        if not status["current"]:
            continue
        category = ITEM_CATEGORY[item["item_class"]]
        selected.append((
            {
                "category": category,
                "source": f"knowledge:{item['item_id']}",
                "text": f"{item['title']}: {item['summary']}",
                "tags": list(item["tags"]),
            },
            {
                "item_id": item["item_id"], "category": category,
                "provenance": list(item["lifecycle"]["provenance"]),
                "authority_class": item["authority_class"], "state": status["state"],
                "source": "knowledge-contract-v1", "authority": "unchanged",
            },
        ))
    selected.sort(key=lambda pair: (pair[0]["category"], pair[1]["item_id"]))
    selected = selected[:query["max_items"]]
    if query["require_current"] and not selected:
        raise KnowledgeSelectionError(
            "mission requiere conocimiento current y no existe selección compatible."
        )
    return {
        "version": VERSION, "mission": query,
        "context_items": [context for context, _ in selected],
        "bindings": [binding for _, binding in selected],
        "selected_count": len(selected),
        "selection_policy": "exact-scope+category+tag;lexical-order;no-score",
    }


def _mission(raw: Any) -> dict[str, Any]:
    _json_size(raw)
    if not isinstance(raw, Mapping) or set(raw) != _FIELDS:
        raise KnowledgeSelectionError("mission contiene campos faltantes o no permitidos.")
    if raw["version"] != VERSION:
        raise KnowledgeSelectionError("mission.version fuera del contrato v1.")
    project, domain = raw["project"], raw["domain"]
    if not isinstance(project, str) or _PROJECT.fullmatch(project) is None:
        raise KnowledgeSelectionError("mission.project inválido.")
    if not isinstance(domain, str) or _ID.fullmatch(domain) is None:
        raise KnowledgeSelectionError("mission.domain inválido.")
    tags = _list(raw["tags"], "mission.tags", 24, pattern=_TAG, allow_empty=True)
    categories = _list(raw["categories"], "mission.categories", len(CONTEXT_CATEGORIES))
    if not categories or any(item not in CONTEXT_CATEGORIES for item in categories):
        raise KnowledgeSelectionError("mission.categories debe usar categorías admitidas.")
    require_current, limit = raw["require_current"], raw["max_items"]
    if type(require_current) is not bool:
        raise KnowledgeSelectionError("mission.require_current debe ser booleano.")
    if type(limit) is not int or not 1 <= limit <= MAX_SELECTED_ITEMS:
        raise KnowledgeSelectionError("mission.max_items fuera de límites.")
    now_at = _timestamp(raw["now_at"])
    return {
        "version": VERSION, "project": project, "domain": domain,
        "tags": tags, "categories": categories, "require_current": require_current,
        "max_items": limit, "now_at": now_at,
    }


def _items(raw: Any) -> list[dict[str, Any]]:
    _json_size(raw)
    if (
        not isinstance(raw, Sequence) or isinstance(raw, (str, bytes))
        or not 1 <= len(raw) <= MAX_CATALOG_ITEMS
    ):
        raise KnowledgeSelectionError("knowledge_items debe ser lista no vacía y acotada.")
    result, ids = [], set()
    for value in raw:
        try:
            item = validate_knowledge_item(value)
        except (KnowledgeContractError, TypeError, ValueError) as exc:
            raise KnowledgeSelectionError("knowledge_item inválido.") from exc
        if item["item_id"] in ids:
            raise KnowledgeSelectionError("knowledge_items contiene ids duplicados.")
        ids.add(item["item_id"]); result.append(item)
    return result


def _matches(item: dict[str, Any], mission: dict[str, Any]) -> bool:
    scope = item["lifecycle"]["scope"]
    if scope != {"project": mission["project"], "domain": mission["domain"]}:
        return False
    if ITEM_CATEGORY[item["item_class"]] not in mission["categories"]:
        return False
    tags = set(mission["tags"])
    return not tags or bool(tags.intersection(item["tags"]))


def _list(value: Any, label: str, limit: int, *, pattern=None, allow_empty=False) -> list[str]:
    if (
        not isinstance(value, list) or len(value) > limit
        or (not allow_empty and not value)
        or not all(isinstance(item, str) and item for item in value)
        or len(value) != len(set(value))
        or (pattern and any(pattern.fullmatch(item) is None for item in value))
    ):
        raise KnowledgeSelectionError(f"{label} inválida.")
    return sorted(value)


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise KnowledgeSelectionError("mission.now_at inválido.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise KnowledgeSelectionError("mission.now_at inválido.") from exc
    if parsed.tzinfo is None:
        raise KnowledgeSelectionError("mission.now_at debe incluir zona horaria.")
    return value


def _json_size(value: Any) -> None:
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise KnowledgeSelectionError("entrada debe ser JSON finito.") from exc
    if len(raw.encode()) > 100_000:
        raise KnowledgeSelectionError("entrada excede tamaño máximo.")
