"""Knowledge Item Contract v1 sobre el lifecycle canónico de Factory."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from evolution.capability_authority import AUTHORITY_CLASSES
from evolution.knowledge_lifecycle import (
    effective_state,
    validate_knowledge_record,
)

VERSION = 1
MAX_PAYLOAD_BYTES = 100_000
MAX_TAGS = 24
MAX_REFS = 50
MAX_RELATIONS = 50

ITEM_CLASSES = frozenset(
    {
        "decision",
        "adr",
        "runbook",
        "postmortem",
        "architecture_invariant",
        "product_rule",
        "operational_procedure",
        "troubleshooting",
        "known_limitation",
        "experiment_result",
        "lesson_guardrail_candidate",
    }
)
SENSITIVITY_CLASSES = frozenset({"normal", "personal_data", "sensitive_data"})
_AUTHORITY_CLASSES = frozenset(AUTHORITY_CLASSES)

_FIELDS = frozenset(
    {
        "version",
        "item_id",
        "item_class",
        "title",
        "summary",
        "tags",
        "owner_ref",
        "authority_class",
        "sensitivity",
        "related_refs",
        "supersedes",
        "superseded_by",
        "lifecycle",
    }
)
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
_TAG = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+-]{0,239}$")
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(?:password|passwd|secret|token|cookie|authorization|api[_-]?key|"
    r"private[_-]?key|email|phone|address|document|ip[_-]?address)(?:$|[_-])",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?:"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b|"
    r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)"
    r")",
    re.IGNORECASE,
)


class KnowledgeContractError(ValueError):
    """Knowledge Item fuera del contrato operativo v1."""


def validate_knowledge_item(payload: Any) -> dict[str, Any]:
    """Valida metadata operativa y delega lifecycle a su contrato canónico."""
    _payload_size(payload)
    data = _mapping(payload, _FIELDS, "knowledge_item")
    if data["version"] != VERSION:
        raise KnowledgeContractError("version fuera del contrato v1.")

    item_id = _identifier(data["item_id"], "item_id")
    item_class = _enum(data["item_class"], ITEM_CLASSES, "item_class")
    lifecycle = _lifecycle(data["lifecycle"])

    if lifecycle["knowledge_id"] != item_id:
        raise KnowledgeContractError("item_id no coincide con lifecycle.")
    if lifecycle["knowledge_type"] != item_class:
        raise KnowledgeContractError("item_class no coincide con lifecycle.")

    supersedes = _id_list(data["supersedes"], "supersedes")
    superseded_by = _id_list(data["superseded_by"], "superseded_by")
    if item_id in supersedes or item_id in superseded_by:
        raise KnowledgeContractError("supersession no admite autorreferencia.")
    if set(supersedes).intersection(superseded_by):
        raise KnowledgeContractError("supersession contiene relaciones contradictorias.")

    return {
        "version": VERSION,
        "item_id": item_id,
        "item_class": item_class,
        "title": _text(data["title"], "title", max_len=160),
        "summary": _text(data["summary"], "summary", max_len=500),
        "tags": _tag_list(data["tags"]),
        "owner_ref": _ref(data["owner_ref"], "owner_ref"),
        "authority_class": _enum(
            data["authority_class"], _AUTHORITY_CLASSES, "authority_class"
        ),
        "sensitivity": _enum(
            data["sensitivity"], SENSITIVITY_CLASSES, "sensitivity"
        ),
        "related_refs": _ref_list(data["related_refs"], "related_refs"),
        "supersedes": supersedes,
        "superseded_by": superseded_by,
        "lifecycle": lifecycle,
    }


def knowledge_item_status(payload: Any, *, now_at: str) -> dict[str, Any]:
    """Expone freshness/estado desde Knowledge Lifecycle, sin otra fórmula."""
    item = validate_knowledge_item(payload)
    state = effective_state(item["lifecycle"], now_at)
    return {
        "version": VERSION,
        "item_id": item["item_id"],
        "state": state,
        "current": state == "active",
        "authority_class": item["authority_class"],
        "sensitivity": item["sensitivity"],
        "supersedes": list(item["supersedes"]),
        "superseded_by": list(item["superseded_by"]),
        "source": "knowledge-lifecycle-v1",
        "authority": "unchanged",
    }


def canonical_knowledge_item(payload: Any) -> str:
    """Serialización determinista del item validado."""
    return json.dumps(
        validate_knowledge_item(payload),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def knowledge_item_fingerprint(payload: Any) -> str:
    """Fingerprint estable de metadata + lifecycle canónicos."""
    return hashlib.sha256(
        canonical_knowledge_item(payload).encode("utf-8")
    ).hexdigest()


def _payload_size(payload: Any) -> None:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise KnowledgeContractError(
            "knowledge_item debe ser JSON finito y serializable."
        ) from exc
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise KnowledgeContractError("knowledge_item excede el tamaño máximo.")


def _mapping(value: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KnowledgeContractError(f"{label} debe ser objeto.")
    if not all(isinstance(key, str) for key in value):
        raise KnowledgeContractError(f"{label} contiene campos inválidos.")
    if any(_SENSITIVE_KEY.search(key) for key in value):
        raise KnowledgeContractError(f"{label} contiene campo sensible no permitido.")
    if set(value) != expected:
        raise KnowledgeContractError(
            f"{label} contiene campos faltantes o no permitidos."
        )
    return value


def _lifecycle(value: Any) -> dict[str, Any]:
    try:
        lifecycle = validate_knowledge_record(value)
    except (TypeError, ValueError) as exc:
        raise KnowledgeContractError("lifecycle inválido.") from exc
    return lifecycle


def _text(value: Any, label: str, *, max_len: int) -> str:
    if not isinstance(value, str):
        raise KnowledgeContractError(f"{label} debe ser texto.")
    normalized = " ".join(value.split())
    if (
        not normalized
        or len(normalized) > max_len
        or "\x00" in normalized
        or _SENSITIVE_VALUE.search(normalized)
    ):
        raise KnowledgeContractError(
            f"{label} vacío, sensible o fuera de límites."
        )
    return normalized


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise KnowledgeContractError(f"{label} inválido.")
    return value


def _enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise KnowledgeContractError(f"{label} fuera del catálogo.")
    return value


def _ref(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or _REF.fullmatch(value) is None
        or _SENSITIVE_VALUE.search(value)
    ):
        raise KnowledgeContractError(f"{label} inválida o sensible.")
    return value


def _tag_list(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > MAX_TAGS
        or not all(isinstance(item, str) and _TAG.fullmatch(item) for item in value)
        or len(value) != len(set(value))
    ):
        raise KnowledgeContractError("tags debe ser lista única y acotada.")
    return sorted(value)


def _ref_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_REFS:
        raise KnowledgeContractError(f"{label} debe ser lista acotada.")
    normalized = [_ref(item, f"{label}[]") for item in value]
    if len(normalized) != len(set(normalized)):
        raise KnowledgeContractError(f"{label} contiene duplicados.")
    return sorted(normalized)


def _id_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_RELATIONS:
        raise KnowledgeContractError(f"{label} debe ser lista acotada.")
    normalized = [_identifier(item, f"{label}[]") for item in value]
    if len(normalized) != len(set(normalized)):
        raise KnowledgeContractError(f"{label} contiene duplicados.")
    return sorted(normalized)
