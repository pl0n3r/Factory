"""Aprendizaje puro desde eventos agregados de límite de capacidad."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from lecciones.memoria import LessonValidationError, validate_lesson

VERSION = 1
MAX_EVENTS = 200
REQUEST_FIELDS = frozenset({"version", "project", "events"})
EVENT_FIELDS = frozenset({
    "account_alias", "occurred_at", "capacity_fingerprint", "source",
})
_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
LESSON_FIELDS = (
    "id", "project", "kind", "occurred_at",
    "what", "why", "prevention", "source",
)


class AccountCapacityLearningError(ValueError):
    """La telemetría agregada no cumple el contrato de aprendizaje v1."""


def _hash(value: Any) -> str:
    try:
        raw = json.dumps(
            value, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise AccountCapacityLearningError("Evidencia JSON inválida.") from exc
    return hashlib.sha256(raw).hexdigest()


def _closed(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise AccountCapacityLearningError(f"{name} debe usar esquema cerrado.")
    return value


def _timestamp(value: Any, name: str) -> tuple[datetime, str]:
    if not isinstance(value, str):
        raise AccountCapacityLearningError(f"{name} debe ser ISO-8601.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AccountCapacityLearningError(f"{name} debe ser ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise AccountCapacityLearningError(f"{name} debe incluir zona horaria.")
    utc = parsed.astimezone(timezone.utc)
    return utc, utc.isoformat().replace("+00:00", "Z")


def _project(value: Any) -> str:
    if not isinstance(value, str) or _PROJECT.fullmatch(value) is None:
        raise AccountCapacityLearningError("project debe usar owner/repo.")
    return value


def _event(value: Any, *, now: datetime) -> dict[str, str]:
    row = _closed(value, EVENT_FIELDS, "event")
    alias = row["account_alias"]
    if (
        not isinstance(alias, str)
        or _ALIAS.fullmatch(alias) is None
        or "@" in alias
    ):
        raise AccountCapacityLearningError("account_alias debe ser opaco.")

    occurred, occurred_at = _timestamp(row["occurred_at"], "event.occurred_at")
    if occurred > now:
        raise AccountCapacityLearningError(
            "event.occurred_at no puede estar en el futuro."
        )

    fingerprint = row["capacity_fingerprint"]
    if (
        not isinstance(fingerprint, str)
        or _FINGERPRINT.fullmatch(fingerprint) is None
    ):
        raise AccountCapacityLearningError("capacity_fingerprint inválido.")

    source = row["source"]
    if not isinstance(source, str):
        raise AccountCapacityLearningError("event.source inválido.")
    _validate_source(source, occurred_at)
    return {
        "account_alias": alias,
        "occurred_at": occurred_at,
        "capacity_fingerprint": fingerprint,
        "source": source,
    }


def _validate_source(source: str, occurred_at: str) -> None:
    probe = {
        "id": "capacity-limit-source",
        "project": "pl0n3r/factory",
        "kind": "incident",
        "occurred_at": occurred_at,
        "what": "Evento agregado de límite observado.",
        "why": "La capacidad observada alcanzó su límite.",
        "prevention": "Mantener un presupuesto conservador.",
        "source": source,
    }
    try:
        validate_lesson(probe, "event.source")
    except LessonValidationError as exc:
        raise AccountCapacityLearningError(
            "event.source debe enlazar Issue/PR de GitHub."
        ) from exc


def _lesson(
    project: str,
    event: dict[str, str],
    event_fingerprint: str,
) -> dict[str, str]:
    lesson = {
        "id": f"capacity-limit-{event_fingerprint}",
        "project": project,
        "kind": "incident",
        "occurred_at": event["occurred_at"],
        "what": "AutoFactory reportó un evento agregado de límite de capacidad.",
        "why": "La evidencia agregada alcanzó el límite observado.",
        "prevention": (
            "Aplicar el presupuesto conservador y reestimar antes de subir el ritmo."
        ),
        "source": event["source"],
    }
    try:
        validated = validate_lesson(lesson, lesson["id"])
    except LessonValidationError as exc:
        raise AccountCapacityLearningError(
            "No fue posible producir una lección canónica."
        ) from exc
    return {field: validated[field] for field in LESSON_FIELDS}


def learn_limit_events(payload: Any, *, now: str) -> dict[str, Any]:
    """Compila lecciones y recurrencia idempotentes, sin I/O."""
    row = _closed(payload, REQUEST_FIELDS, "request")
    if type(row["version"]) is not int or row["version"] != VERSION:
        raise AccountCapacityLearningError("request.version no soportada.")
    project = _project(row["project"])
    now_value, _ = _timestamp(now, "now")
    events = row["events"]
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise AccountCapacityLearningError("events debe ser una lista acotada.")

    unique: dict[str, dict[str, str]] = {}
    for raw_event in events:
        normalized = _event(raw_event, now=now_value)
        unique.setdefault(_hash(normalized), normalized)

    ordered = sorted(
        unique.items(),
        key=lambda item: (
            item[1]["account_alias"],
            _timestamp(item[1]["occurred_at"], "event.occurred_at")[0],
            item[0],
        ),
    )
    lessons = [_lesson(project, event, key) for key, event in ordered]

    grouped: dict[str, list[dict[str, str]]] = {}
    for _, event in ordered:
        grouped.setdefault(event["account_alias"], []).append(event)
    recurrence = [
        {
            "accountAlias": alias,
            "limitEvents": len(items),
            "lastOccurredAt": max(
                items,
                key=lambda item: _timestamp(
                    item["occurred_at"], "event.occurred_at"
                )[0],
            )["occurred_at"],
        }
        for alias, items in sorted(grouped.items())
    ]

    material = {
        "version": VERSION,
        "project": project,
        "lessons": lessons,
        "recurrence": recurrence,
    }
    return {**material, "fingerprint": _hash(material)}
