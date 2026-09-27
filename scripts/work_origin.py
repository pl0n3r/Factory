#!/usr/bin/env python3
"""Contrato puro WorkItem v1 para la cola única de Factory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

ORIGIN_MODES = frozenset({"directed", "automatic"})
ORIGIN_SYSTEMS = frozenset(
    {
        "controlbot",
        "aegis",
        "momentum",
        "capital",
        "factory",
        "runner",
        "autofactory",
        "venture",
        "product",
        "human",
    }
)
WORK_TYPES = frozenset(
    {
        "engineering",
        "security",
        "infrastructure",
        "operations",
        "data_analytics",
        "product",
        "content",
        "marketing_growth",
        "sales_support",
        "finance_analysis",
        "compliance_review",
        "knowledge_documentation",
    }
)
PRIORITY_CLASSES = frozenset({"critical", "high", "medium"})
SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})

MAX_PAYLOAD_BYTES = 100_000
MAX_COLLECTION = 50
MAX_REF = 240
MAX_IDEMPOTENCY = 128

_REQUIRED_FIELDS = frozenset(
    {
        "work_id",
        "origin_mode",
        "origin_system",
        "group_id",
        "work_type",
        "requested_capabilities",
        "required_roles",
        "authority_level",
        "priority_class",
        "depends_on",
        "claims",
        "policy_ref",
        "evidence_refs",
        "idempotency_key",
    }
)
_OPTIONAL_FIELDS = frozenset(
    {
        "producer_ref",
        "requested_by",
        "venture_id",
        "project_id",
        "repository_ref",
        "severity",
        "budget_ref",
        "approval_ref",
        "observed_at",
    }
)
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS

_SLUG = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SECRET_VALUE = re.compile(
    r"(?:"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}"
    r")",
    re.IGNORECASE,
)
_SECRET_KEY = re.compile(
    r"(?:^|[_-])(password|passwd|secret|token|api[_-]?key|private[_-]?key)(?:$|[_-])",
    re.IGNORECASE,
)


class WorkOriginError(ValueError):
    """Payload fuera del contrato WorkItem v1."""


def _payload_size(payload: Any) -> int:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise WorkOriginError("WorkItem debe ser JSON serializable.") from exc
    size = len(encoded.encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise WorkOriginError("WorkItem excede el tamaño máximo.")
    return size


def _text(value: Any, field: str, *, max_len: int = MAX_REF) -> str:
    if not isinstance(value, str):
        raise WorkOriginError(f"{field} debe ser texto.")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > max_len
        or "\n" in normalized
        or "\r" in normalized
        or "\x00" in normalized
    ):
        raise WorkOriginError(f"{field} está vacío o fuera de límites.")
    if _SECRET_VALUE.search(normalized):
        raise WorkOriginError(f"{field} contiene material con forma de secreto.")
    return normalized


def _slug(value: Any, field: str) -> str:
    normalized = _text(value, field, max_len=64)
    if not _SLUG.fullmatch(normalized):
        raise WorkOriginError(f"{field} debe ser un identificador canónico.")
    return normalized


def _collection(
    value: Any,
    field: str,
    *,
    allow_empty: bool = True,
    slug: bool = False,
) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_COLLECTION:
        raise WorkOriginError(f"{field} debe ser una lista acotada.")
    if not allow_empty and not value:
        raise WorkOriginError(f"{field} no puede estar vacío.")
    normalized = [
        _slug(item, f"{field}[]") if slug else _text(item, f"{field}[]")
        for item in value
    ]
    return sorted(set(normalized))


def _timestamp(value: Any) -> str:
    raw = _text(value, "observed_at", max_len=64)
    parsed_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(parsed_raw)
    except ValueError as exc:
        raise WorkOriginError("observed_at debe usar ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise WorkOriginError("observed_at debe incluir zona horaria.")
    canonical = parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    return canonical.replace("+00:00", "Z")


def validate_work_item(payload: Any) -> dict[str, Any]:
    """Valida y normaliza un WorkItem v1 sin tomar decisiones de readiness."""
    if not isinstance(payload, dict) or not payload:
        raise WorkOriginError("WorkItem debe ser un objeto no vacío.")
    _payload_size(payload)

    keys = set(payload)
    if not all(isinstance(key, str) for key in keys):
        raise WorkOriginError("Todos los campos de WorkItem deben ser texto.")
    secret_keys = sorted(key for key in keys if _SECRET_KEY.search(key))
    if secret_keys:
        raise WorkOriginError("WorkItem no admite campos con forma de secreto.")
    unknown = sorted(key for key in keys if key not in _ALLOWED_FIELDS)
    if unknown:
        raise WorkOriginError("Campos desconocidos: " + ", ".join(map(str, unknown)))
    missing = sorted(_REQUIRED_FIELDS - keys)
    if missing:
        raise WorkOriginError("Campos requeridos ausentes: " + ", ".join(missing))

    has_producer = "producer_ref" in payload
    has_requested_by = "requested_by" in payload
    if not (has_producer or has_requested_by):
        raise WorkOriginError("WorkItem requiere producer_ref o requested_by.")
    producer_ref = _text(
        payload["producer_ref"] if has_producer else payload["requested_by"],
        "producer_ref",
    )
    if has_producer and has_requested_by:
        requested_by = _text(payload["requested_by"], "requested_by")
        if requested_by != producer_ref:
            raise WorkOriginError("producer_ref y requested_by no pueden divergir.")

    origin_mode = _slug(payload["origin_mode"], "origin_mode")
    if origin_mode not in ORIGIN_MODES:
        raise WorkOriginError("origin_mode fuera del catálogo.")
    origin_system = _slug(payload["origin_system"], "origin_system")
    if origin_system not in ORIGIN_SYSTEMS:
        raise WorkOriginError("origin_system fuera del catálogo.")
    work_type = _slug(payload["work_type"], "work_type")
    if work_type not in WORK_TYPES:
        raise WorkOriginError("work_type fuera del catálogo.")
    priority = _slug(payload["priority_class"], "priority_class")
    if priority not in PRIORITY_CLASSES:
        raise WorkOriginError("priority_class fuera del catálogo.")

    result: dict[str, Any] = {
        "work_id": _text(payload["work_id"], "work_id"),
        "origin_mode": origin_mode,
        "origin_system": origin_system,
        "group_id": _text(payload["group_id"], "group_id"),
        "work_type": work_type,
        "requested_capabilities": _collection(
            payload["requested_capabilities"],
            "requested_capabilities",
            allow_empty=False,
            slug=True,
        ),
        "required_roles": _collection(
            payload["required_roles"],
            "required_roles",
            allow_empty=False,
            slug=True,
        ),
        "authority_level": _slug(payload["authority_level"], "authority_level"),
        "producer_ref": producer_ref,
        "priority_class": priority,
        "depends_on": _collection(payload["depends_on"], "depends_on"),
        "claims": _collection(payload["claims"], "claims"),
        "policy_ref": _text(payload["policy_ref"], "policy_ref"),
        "evidence_refs": _collection(payload["evidence_refs"], "evidence_refs"),
        "idempotency_key": _text(
            payload["idempotency_key"],
            "idempotency_key",
            max_len=MAX_IDEMPOTENCY,
        ),
    }

    for field in ("venture_id", "project_id", "budget_ref", "approval_ref"):
        if field in payload and payload[field] is not None:
            result[field] = _text(payload[field], field)

    if "repository_ref" in payload and payload["repository_ref"] is not None:
        repository_ref = _text(payload["repository_ref"], "repository_ref")
        if not _REPOSITORY.fullmatch(repository_ref):
            raise WorkOriginError("repository_ref debe usar owner/repo.")
        result["repository_ref"] = repository_ref

    if "severity" in payload and payload["severity"] is not None:
        severity = _slug(payload["severity"], "severity")
        if severity not in SEVERITIES:
            raise WorkOriginError("severity fuera del catálogo.")
        result["severity"] = severity

    if "observed_at" in payload and payload["observed_at"] is not None:
        result["observed_at"] = _timestamp(payload["observed_at"])

    return result


def canonical_payload(payload: Any) -> str:
    """Representación JSON determinista del WorkItem validado."""
    normalized = validate_work_item(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def work_fingerprint(payload: Any) -> str:
    """Fingerprint de contenido del WorkItem canónico."""
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def idempotency_scope(payload: Any) -> str:
    """Clave estable de deduplicación cross-origin sin mezclar scopes de negocio."""
    item = validate_work_item(payload)
    scope = {
        "group_id": item["group_id"],
        "venture_id": item.get("venture_id"),
        "project_id": item.get("project_id"),
        "work_type": item["work_type"],
        "idempotency_key": item["idempotency_key"],
    }
    encoded = json.dumps(
        scope,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
