"""Compila eventos agregados de límite en memoria operativa determinista."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from lecciones.memoria import LessonValidationError, validate_lesson


LEARNING_VERSION = 1
REQUEST_FIELDS = frozenset({"version", "project", "accountAlias", "events"})
EVENT_FIELDS = frozenset({
    "occurred_at",
    "accepted_before_limit",
    "window_seconds",
    "reset_after_seconds",
    "capacity_fingerprint",
    "source",
})
_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class AccountCapacityLearningError(ValueError):
    """La evidencia agregada no puede compilarse de forma segura."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _closed(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AccountCapacityLearningError(f"{label} debe usar esquema cerrado")
    return value


def _integer(value: Any, label: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise AccountCapacityLearningError(f"{label} inválido")
    return value


def _opaque_alias(value: Any) -> str:
    if not isinstance(value, str) or not _ALIAS.fullmatch(value) or "@" in value:
        raise AccountCapacityLearningError("accountAlias debe ser un alias local opaco")
    return value


def _project(value: Any) -> str:
    if not isinstance(value, str) or not _PROJECT.fullmatch(value):
        raise AccountCapacityLearningError("project debe usar owner/repo")
    return value


def _fingerprint(value: Any) -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise AccountCapacityLearningError("capacity_fingerprint inválido")
    return value


def _timestamp(value: Any, *, now: datetime | None) -> str:
    if not isinstance(value, str):
        raise AccountCapacityLearningError("occurred_at debe ser ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AccountCapacityLearningError("occurred_at debe ser ISO-8601") from exc
    if parsed.tzinfo is None:
        raise AccountCapacityLearningError("occurred_at debe incluir zona horaria")
    utc = parsed.astimezone(timezone.utc)
    if now is not None and utc > now:
        raise AccountCapacityLearningError("occurred_at no puede estar en el futuro")
    return utc.isoformat().replace("+00:00", "Z")


def _source(value: Any, *, project: str, occurred_at: str) -> str:
    lesson = {
        "id": "source-check",
        "project": project,
        "kind": "incident",
        "occurred_at": occurred_at,
        "what": "Se observó un límite agregado.",
        "why": "La capacidad disponible fue alcanzada.",
        "prevention": "Aplicar el presupuesto conservador.",
        "source": value,
    }
    try:
        validate_lesson(lesson, "account-capacity-learning")
    except LessonValidationError as exc:
        raise AccountCapacityLearningError("source debe ser Issue/PR de GitHub") from exc
    return value


def _event(value: Any, *, project: str, now: datetime | None) -> dict[str, Any]:
    row = _closed(value, EVENT_FIELDS, "event")
    occurred_at = _timestamp(row["occurred_at"], now=now)
    accepted = _integer(
        row["accepted_before_limit"],
        "accepted_before_limit",
        minimum=0,
    )
    window = _integer(row["window_seconds"], "window_seconds", minimum=1)
    reset = _integer(
        row["reset_after_seconds"],
        "reset_after_seconds",
        minimum=1,
    )
    capacity_fingerprint = _fingerprint(row["capacity_fingerprint"])
    source = _source(row["source"], project=project, occurred_at=occurred_at)
    return {
        "occurred_at": occurred_at,
        "accepted_before_limit": accepted,
        "window_seconds": window,
        "reset_after_seconds": reset,
        "capacity_fingerprint": capacity_fingerprint,
        "source": source,
    }


def _lesson(project: str, event: dict[str, Any]) -> dict[str, str]:
    evidence_hash = _stable_hash(event)
    lesson = {
        "id": f"account-cap-limit-{evidence_hash[:24]}",
        "project": project,
        "kind": "incident",
        "occurred_at": event["occurred_at"],
        "what": (
            "Se alcanzó un límite tras "
            f"{event['accepted_before_limit']} envíos agregados "
            f"en una ventana de {event['window_seconds']} s."
        ),
        "why": (
            "La evidencia agregada registró un evento de límite "
            "para la capacidad observada."
        ),
        "prevention": (
            "Aplicar el presupuesto conservador y respetar "
            f"al menos {event['reset_after_seconds']} s de recuperación."
        ),
        "source": event["source"],
    }
    try:
        validate_lesson(lesson, f"account-capacity-learning:{evidence_hash[:12]}")
    except LessonValidationError as exc:
        raise AccountCapacityLearningError("lección generada inválida") from exc
    return lesson


def compile_limit_learning(
    request: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compila lecciones y recurrencia sin leer ni escribir estado externo."""
    data = _closed(request, REQUEST_FIELDS, "request")
    if type(data["version"]) is not int or data["version"] != LEARNING_VERSION:
        raise AccountCapacityLearningError("version no soportada")
    project = _project(data["project"])
    alias = _opaque_alias(data["accountAlias"])
    events = data["events"]
    if not isinstance(events, list):
        raise AccountCapacityLearningError("events debe ser una lista")
    if now is not None:
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise AccountCapacityLearningError("now debe incluir zona horaria")
        now = now.astimezone(timezone.utc)

    normalized = [_event(item, project=project, now=now) for item in events]
    unique_by_hash = {_stable_hash(item): item for item in normalized}
    ordered = sorted(
        unique_by_hash.values(),
        key=lambda item: (
            item["occurred_at"],
            item["source"],
            item["capacity_fingerprint"],
            item["accepted_before_limit"],
            item["window_seconds"],
            item["reset_after_seconds"],
        ),
    )
    lessons = [_lesson(project, item) for item in ordered]
    occurred = [item["occurred_at"] for item in ordered]
    recurrence = {
        "limitEvents": len(ordered),
        "firstOccurredAt": occurred[0] if occurred else None,
        "lastOccurredAt": occurred[-1] if occurred else None,
        "repeated": len(ordered) > 1,
        "sourceFingerprints": sorted(
            {item["capacity_fingerprint"] for item in ordered}
        ),
    }
    material = {
        "version": LEARNING_VERSION,
        "project": project,
        "accountAlias": alias,
        "lessons": lessons,
        "recurrence": recurrence,
    }
    return {**material, "fingerprint": _stable_hash(material)}
