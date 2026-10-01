"""Aprendizaje puro de recurrencia a partir de eventos agregados de límite."""
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
    "account_alias",
    "occurred_at",
    "capacity_fingerprint",
    "source",
})
_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class AccountCapacityLearningError(ValueError):
    """La telemetría agregada no cumple el contrato de aprendizaje v1."""


def _stable_hash(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise AccountCapacityLearningError(
            "La evidencia debe ser JSON finito y serializable."
        ) from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _closed_mapping(
    value: Any,
    expected: frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise AccountCapacityLearningError(
            f"{label} debe usar esquema cerrado."
        )
    return value


def _timestamp(value: Any, label: str) -> tuple[datetime, str]:
    if not isinstance(value, str):
        raise AccountCapacityLearningError(f"{label} debe ser ISO-8601.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AccountCapacityLearningError(
            f"{label} debe ser ISO-8601."
        ) from exc
    if parsed.tzinfo is None:
        raise AccountCapacityLearningError(
            f"{label} debe incluir zona horaria."
        )
    utc = parsed.astimezone(timezone.utc)
    canonical = utc.isoformat().replace("+00:00", "Z")
    return utc, canonical


def _project(value: Any) -> str:
    if not isinstance(value, str) or _PROJECT.fullmatch(value) is None:
        raise AccountCapacityLearningError(
            "project debe usar owner/repo."
        )
    return value


def _alias(value: Any) -> str:
    if (
        not isinstance(value, str)
        or _ALIAS.fullmatch(value) is None
        or "@" in value
    ):
        raise AccountCapacityLearningError(
            "account_alias debe ser un alias local opaco."
        )
    return value


def _fingerprint(value: Any) -> str:
    if (
        not isinstance(value, str)
        or _FINGERPRINT.fullmatch(value) is None
    ):
        raise AccountCapacityLearningError(
            "capacity_fingerprint inválido."
        )
    return value


def _normalize_event(
    value: Any,
    *,
    now: datetime,
) -> dict[str, str]:
    row = _closed_mapping(value, EVENT_FIELDS, "event")
    alias = _alias(row["account_alias"])
    occurred, occurred_at = _timestamp(
        row["occurred_at"],
        "event.occurred_at",
    )
    if occurred > now:
        raise AccountCapacityLearningError(
            "event.occurred_at no puede estar en el futuro."
        )
    fingerprint = _fingerprint(row["capacity_fingerprint"])
    source = row["source"]
    if not isinstance(source, str):
        raise AccountCapacityLearningError("event.source inválido.")

    # validate_lesson es la autoridad del formato de source del repositorio.
    probe = {
        "id": "limit-source-probe",
        "project": "pl0n3r/factory",
        "kind": "process",
        "occurred_at": occurred_at,
        "what": "Evento agregado de límite observado.",
        "why": "La capacidad observada alcanzó el límite disponible.",
        "prevention": "Aplicar presupuesto conservador antes del siguiente envío.",
        "source": source,
    }
    try:
        validate_lesson(probe, "event.source")
    except LessonValidationError as exc:
        raise AccountCapacityLearningError(
            "event.source debe enlazar Issue/PR de GitHub."
        ) from exc

    return {
        "account_alias": alias,
        "occurred_at": occurred_at,
        "capacity_fingerprint": fingerprint,
        "source": source,
    }


def _lesson(
    project: str,
    event: dict[str, str],
    event_fingerprint: str,
) -> dict[str, str]:
    short = event_fingerprint[:20]
    lesson = {
        "id": f"capacity-limit-{short}",
        "project": project,
        "kind": "process",
        "occurred_at": event["occurred_at"],
        "what": (
            f"El alias opaco {event['account_alias']} registró un evento "
            "agregado de límite de capacidad."
        ),
        "why": (
            "La evidencia agregada alcanzó el límite observado ligado a "
            f"capacity fingerprint {event['capacity_fingerprint'][:12]}."
        ),
        "prevention": (
            "Aplicar el presupuesto conservador vigente y reestimar "
            "capacidad antes de aumentar el ritmo."
        ),
        "source": event["source"],
    }
    try:
        validated = validate_lesson(lesson, lesson["id"])
    except LessonValidationError as exc:
        raise AccountCapacityLearningError(
            "No fue posible producir una lección canónica."
        ) from exc
    return {
        key: validated[key]
        for key in (
            "id",
            "project",
            "kind",
            "occurred_at",
            "what",
            "why",
            "prevention",
            "source",
        )
    }


def learn_limit_events(payload: Any, *, now: str) -> dict[str, Any]:
    """Convierte telemetría minimizada en lecciones y recurrencia deterministas."""
    row = _closed_mapping(payload, REQUEST_FIELDS, "request")
    if type(row["version"]) is not int or row["version"] != VERSION:
        raise AccountCapacityLearningError(
            "request.version no soportada."
        )
    project = _project(row["project"])
    now_value, _ = _timestamp(now, "now")
    events = row["events"]
    if (
        not isinstance(events, list)
        or len(events) > MAX_EVENTS
    ):
        raise AccountCapacityLearningError(
            "events debe ser una lista acotada."
        )

    unique: dict[str, dict[str, str]] = {}
    for raw_event in events:
        event = _normalize_event(raw_event, now=now_value)
        event_fingerprint = _stable_hash(event)
        unique.setdefault(event_fingerprint, event)

    normalized = sorted(
        (
            {
                **event,
                "_event_fingerprint": event_fingerprint,
            }
            for event_fingerprint, event in unique.items()
        ),
        key=lambda item: (
            item["account_alias"],
            item["occurred_at"],
            item["_event_fingerprint"],
        ),
    )

    lessons = [
        _lesson(project, event, event["_event_fingerprint"])
        for event in normalized
    ]

    by_account: dict[str, list[dict[str, str]]] = {}
    for event in normalized:
        by_account.setdefault(event["account_alias"], []).append(event)

    recurrence = [
        {
            "accountAlias": alias,
            "limitEvents": len(account_events),
            "lastOccurredAt": max(
                item["occurred_at"] for item in account_events
            ),
        }
        for alias, account_events in sorted(by_account.items())
    ]

    material = {
        "version": VERSION,
        "project": project,
        "lessons": lessons,
        "recurrence": recurrence,
    }
    return {
        **material,
        "fingerprint": _stable_hash(material),
    }
