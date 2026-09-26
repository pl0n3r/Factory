"""Context Compiler: paquete mínimo, trazable y privado para una misión."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from intelligence.project_dna import validate_project_dna


CONTEXT_VERSION = 1
MAX_CONTEXT_ITEMS = 12
MAX_ITEM_CHARS = 1200
MAX_PACKAGE_CHARS = 12_000

SENSITIVE_KEYS = {
    "secret", "secrets", "token", "password", "passwd", "private_key",
    "api_key", "apikey", "authorization", "cookie", "email", "phone",
    "telephone", "address", "document", "document_id", "ssn",
}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")


class ContextCompilerError(ValueError):
    """Entrada de contexto inválida o potencialmente sensible."""


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalize_tags(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        raise ContextCompilerError("tags debe ser colección")
    tags = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ContextCompilerError("tag inválido")
        tags.append(item.strip().lower())
    return tuple(sorted(set(tags)))


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContextCompilerError("claves no string")
            if key.strip().lower() in SENSITIVE_KEYS:
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _redact_text(value: str) -> str:
    redacted = EMAIL_RE.sub("[REDACTED]", value)
    redacted = PHONE_RE.sub("[REDACTED]", redacted)
    return redacted


def _safe_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextCompilerError(f"{field} inválido")
    text = _redact_text(value.strip())
    if len(text) > MAX_ITEM_CHARS:
        text = text[:MAX_ITEM_CHARS]
    return text


def _task_contract(task: Any) -> dict[str, Any]:
    if not isinstance(task, dict) or set(task) != {"id", "title", "goal", "tags"}:
        raise ContextCompilerError("task inválida")
    if _contains_sensitive_key(task):
        raise ContextCompilerError("task contiene campos sensibles")
    return {
        "id": _safe_text(task["id"], "task.id"),
        "title": _safe_text(task["title"], "task.title"),
        "goal": _safe_text(task["goal"], "task.goal"),
        "tags": list(_normalize_tags(task["tags"])),
    }


def _context_item(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"category", "source", "text", "tags"}:
        raise ContextCompilerError("context item inválido")
    if _contains_sensitive_key(value):
        raise ContextCompilerError("context item contiene campos sensibles")
    category = _safe_text(value["category"], "category")
    if category not in {"decision", "lesson", "constraint", "evidence"}:
        raise ContextCompilerError("category no admitida")
    return {
        "category": category,
        "source": _safe_text(value["source"], "source"),
        "text": _safe_text(value["text"], "text"),
        "tags": list(_normalize_tags(value["tags"])),
    }


def compile_mission_context(
    *,
    project_dna: Any,
    task: Any,
    context_items: Any,
) -> dict[str, Any]:
    """Compila Project DNA + tarea + contexto relevante sin ampliar autoridad."""
    dna = validate_project_dna(project_dna)
    normalized_task = _task_contract(task)
    if not isinstance(context_items, (list, tuple)):
        raise ContextCompilerError("context_items debe ser lista")

    task_tags = set(normalized_task["tags"])
    selected = []
    for raw in context_items:
        item = _context_item(raw)
        if task_tags.intersection(item["tags"]):
            selected.append(item)

    selected.sort(
        key=lambda item: (
            item["category"],
            item["source"],
            item["text"],
            item["tags"],
        )
    )
    selected = selected[:MAX_CONTEXT_ITEMS]

    package = {
        "version": CONTEXT_VERSION,
        "project_dna": dna,
        "task": normalized_task,
        "context": selected,
        "limits": {
            "max_context_items": MAX_CONTEXT_ITEMS,
            "max_item_chars": MAX_ITEM_CHARS,
            "max_package_chars": MAX_PACKAGE_CHARS,
        },
    }
    encoded = json.dumps(
        package,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(encoded) > MAX_PACKAGE_CHARS:
        raise ContextCompilerError("mission package excede el límite")
    package["fingerprint"] = _canonical_hash(package)
    return package
