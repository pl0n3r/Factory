"""Postmortem operativo verificable hacia lecciones/guardrails existentes."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any

from knowledge.contract import (
    KnowledgeContractError,
    knowledge_item_fingerprint,
    validate_knowledge_item,
)
from lecciones.memoria import LessonValidationError, validate_lesson

VERSION = 1
ROOT_CAUSE_STATES = frozenset({"known", "unknown"})
MAX_TIMELINE = 64
MAX_FACTORS = 24
MAX_ACTIONS = 32
MAX_REFS = 50
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+-]{0,239}$")
_SENSITIVE = re.compile(
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


class KnowledgePostmortemError(ValueError):
    """Postmortem fuera del contrato operativo v1."""


def validate_postmortem(payload: Any) -> dict[str, Any]:
    """Valida un postmortem sin inferir causa ni ejecutar acciones."""
    _payload_size(payload)
    fields = {
        "version", "knowledge_item", "incident_ref", "occurred_at", "impact",
        "timeline", "detection", "recovery", "root_cause",
        "contributing_factors", "actions", "guardrail_prevention", "evidence_refs",
    }
    data = _mapping(payload, fields, "postmortem")
    if data["version"] != VERSION:
        raise KnowledgePostmortemError("version debe ser 1.")

    try:
        item = validate_knowledge_item(data["knowledge_item"])
    except KnowledgeContractError as exc:
        raise KnowledgePostmortemError("knowledge_item inválido.") from exc
    if item["item_class"] != "postmortem":
        raise KnowledgePostmortemError("knowledge_item debe ser postmortem.")

    occurred_at = _timestamp(data["occurred_at"], "occurred_at")
    root_cause = _root_cause(data["root_cause"])
    prevention = _optional_text(
        data["guardrail_prevention"], "guardrail_prevention", max_len=280
    )
    if root_cause["status"] == "known" and prevention is None:
        raise KnowledgePostmortemError(
            "causa conocida requiere guardrail_prevention explícita."
        )

    timeline = _timeline(data["timeline"], occurred_at)
    actions = _actions(data["actions"])
    result = {
        "version": VERSION,
        "knowledge_item": item,
        "knowledge_fingerprint": knowledge_item_fingerprint(item),
        "incident_ref": _ref(data["incident_ref"], "incident_ref"),
        "occurred_at": occurred_at,
        "impact": _text(data["impact"], "impact", max_len=280),
        "timeline": timeline,
        "detection": _text(data["detection"], "detection", max_len=280),
        "recovery": _text(data["recovery"], "recovery", max_len=280),
        "root_cause": root_cause,
        "contributing_factors": _texts(
            data["contributing_factors"], "contributing_factors", MAX_FACTORS
        ),
        "actions": actions,
        "guardrail_prevention": prevention,
        "evidence_refs": _refs(data["evidence_refs"], "evidence_refs"),
        "authority": "unchanged",
        "execute_actions": False,
        "emit_work_items": False,
    }
    return result


def guardrail_lesson_input(payload: Any) -> dict[str, str] | None:
    """Emite una lección compatible con Experience Guardrails solo con causa verificada."""
    postmortem = validate_postmortem(payload)
    cause = postmortem["root_cause"]
    if cause["status"] != "known":
        return None

    lesson = {
        "id": f"postmortem-{postmortem['knowledge_item']['item_id']}",
        "project": postmortem["knowledge_item"]["lifecycle"]["scope"]["project"],
        "kind": "incident",
        "occurred_at": postmortem["occurred_at"],
        "what": postmortem["impact"],
        "why": cause["summary"],
        "prevention": postmortem["guardrail_prevention"],
        "source": postmortem["incident_ref"],
    }
    try:
        validated = validate_lesson(lesson, "postmortem.guardrail_lesson")
    except LessonValidationError as exc:
        raise KnowledgePostmortemError(
            "lesson/guardrail input incompatible con memoria canónica."
        ) from exc
    return {key: value for key, value in validated.items() if key != "_sort_at"}


def canonical_postmortem(payload: Any) -> str:
    """Serialización determinista del postmortem validado."""
    return json.dumps(
        validate_postmortem(payload),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _root_cause(raw: Any) -> dict[str, Any]:
    data = _mapping(raw, {"status", "summary", "evidence_refs"}, "root_cause")
    status = data["status"]
    if status not in ROOT_CAUSE_STATES:
        raise KnowledgePostmortemError("root_cause.status fuera del catálogo.")
    evidence = _refs(data["evidence_refs"], "root_cause.evidence_refs")
    if status == "known":
        summary = _text(data["summary"], "root_cause.summary", max_len=280)
        if not evidence:
            raise KnowledgePostmortemError(
                "causa conocida requiere evidencia verificable."
            )
        return {"status": status, "summary": summary, "evidence_refs": evidence}
    if data["summary"] is not None or evidence:
        raise KnowledgePostmortemError(
            "causa unknown no puede fingir resumen o evidencia causal."
        )
    return {"status": status, "summary": None, "evidence_refs": []}


def _timeline(raw: Any, occurred_at: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw or len(raw) > MAX_TIMELINE:
        raise KnowledgePostmortemError("timeline debe ser lista no vacía y acotada.")
    floor = _parse_time(occurred_at, "occurred_at")
    rows = []
    for entry in raw:
        data = _mapping(entry, {"at", "event", "evidence_refs"}, "timeline[]")
        at = _timestamp(data["at"], "timeline.at")
        if _parse_time(at, "timeline.at") < floor:
            raise KnowledgePostmortemError("timeline no puede preceder al incidente.")
        rows.append({
            "at": at,
            "event": _text(data["event"], "timeline.event", max_len=240),
            "evidence_refs": _refs(data["evidence_refs"], "timeline.evidence_refs"),
        })
    rows.sort(key=lambda row: (row["at"], row["event"], row["evidence_refs"]))
    return rows


def _actions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > MAX_ACTIONS:
        raise KnowledgePostmortemError("actions debe ser lista acotada.")
    seen, rows = set(), []
    for entry in raw:
        data = _mapping(entry, {"id", "summary", "evidence_refs"}, "actions[]")
        action_id = _identifier(data["id"], "actions.id")
        if action_id in seen:
            raise KnowledgePostmortemError("actions.id duplicado.")
        seen.add(action_id)
        rows.append({
            "id": action_id,
            "summary": _text(data["summary"], "actions.summary", max_len=240),
            "evidence_refs": _refs(data["evidence_refs"], "actions.evidence_refs"),
        })
    return sorted(rows, key=lambda row: row["id"])


def _mapping(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise KnowledgePostmortemError(
            f"{label} contiene campos faltantes o no permitidos."
        )
    return value


def _payload_size(payload: Any) -> None:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise KnowledgePostmortemError("postmortem debe ser JSON finito.") from exc
    if len(encoded.encode("utf-8")) > 100_000:
        raise KnowledgePostmortemError("postmortem excede tamaño máximo.")


def _text(value: Any, label: str, *, max_len: int) -> str:
    if not isinstance(value, str):
        raise KnowledgePostmortemError(f"{label} debe ser texto.")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > max_len or _SENSITIVE.search(normalized):
        raise KnowledgePostmortemError(
            f"{label} vacío, sensible o fuera de límites."
        )
    return normalized


def _optional_text(value: Any, label: str, *, max_len: int) -> str | None:
    if value is None:
        return None
    return _text(value, label, max_len=max_len)


def _texts(value: Any, label: str, limit: int) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise KnowledgePostmortemError(f"{label} debe ser lista acotada.")
    rows = [_text(item, f"{label}[]", max_len=240) for item in value]
    if len(rows) != len(set(rows)):
        raise KnowledgePostmortemError(f"{label} contiene duplicados.")
    return sorted(rows)


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise KnowledgePostmortemError(f"{label} inválido.")
    return value


def _ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise KnowledgePostmortemError(f"{label} inválida.")
    return value


def _refs(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_REFS:
        raise KnowledgePostmortemError(f"{label} debe ser lista acotada.")
    refs = [_ref(item, f"{label}[]") for item in value]
    if len(refs) != len(set(refs)):
        raise KnowledgePostmortemError(f"{label} contiene duplicados.")
    return sorted(refs)


def _timestamp(value: Any, label: str) -> str:
    parsed = _parse_time(value, label)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise KnowledgePostmortemError(f"{label} debe ser ISO-8601 con zona.")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise KnowledgePostmortemError(
            f"{label} debe ser ISO-8601 con zona."
        ) from exc
    if parsed.tzinfo is None:
        raise KnowledgePostmortemError(f"{label} debe incluir zona horaria.")
    return parsed
