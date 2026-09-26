"""Experience Guardrail Compiler: lecciones repetidas -> candidatos preventivos."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from evolution.constitution import validate_candidate
from lecciones.memoria import LessonValidationError, validate_lesson


GUARDRAIL_VERSION = 1
MIN_OCCURRENCES = 2
MAX_LESSONS = 32
_TOKEN = re.compile(r"[a-z0-9]+")


class ExperienceGuardrailError(ValueError):
    """Lecciones o parámetros inválidos para compilar guardrails."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _canonical_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(_TOKEN.findall(ascii_text))


def _validated_lessons(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise ExperienceGuardrailError("lessons debe ser lista")
    if not 1 <= len(value) <= MAX_LESSONS:
        raise ExperienceGuardrailError(
            f"lessons debe contener 1..{MAX_LESSONS} elementos"
        )

    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    try:
        for index, raw in enumerate(value, 1):
            item = validate_lesson(raw, f"lesson[{index}]")
            if item["id"] in seen_ids:
                raise ExperienceGuardrailError("lesson id duplicado")
            seen_ids.add(item["id"])
            validated.append(item)
    except LessonValidationError as exc:
        raise ExperienceGuardrailError(str(exc)) from exc
    return validated


def _pattern_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        item["project"].casefold(),
        _canonical_text(item["why"]),
        _canonical_text(item["prevention"]),
    )


def _pattern_fingerprint(key: tuple[str, str, str]) -> str:
    return _stable_hash(
        {"project": key[0], "why": key[1], "prevention": key[2]}
    )


def _candidate_for_group(
    lessons: list[dict[str, Any]],
    pattern_key: tuple[str, str, str],
) -> dict[str, Any]:
    ordered = sorted(
        lessons,
        key=lambda item: (item["source"], item["id"], item["occurred_at"]),
    )
    pattern_fingerprint = _pattern_fingerprint(pattern_key)
    guardrail_id = f"guardrail_{pattern_fingerprint[:16]}"
    sources = sorted({item["source"] for item in ordered})
    lesson_ids = sorted(item["id"] for item in ordered)
    prevention = min(
        {item["prevention"].strip() for item in ordered},
        key=lambda text: (text.casefold(), text),
    )

    origins = [
        {
            "lesson_id": item["id"],
            "source": item["source"],
            "kind": item["kind"],
            "occurred_at": item["occurred_at"],
        }
        for item in ordered
    ]
    value = {
        "version": GUARDRAIL_VERSION,
        "guardrail_id": guardrail_id,
        "project": ordered[0]["project"],
        "pattern_fingerprint": pattern_fingerprint,
        "occurrences": len(ordered),
        "expected_prevention": prevention,
        "origins": origins,
        "status": "candidate",
    }
    candidate = {
        "version": 1,
        "changes": [
            {
                "path": f"evolution_state.heuristics.{guardrail_id}",
                "operation": "add",
                "value": value,
            }
        ],
        "evidence": sources,
        "rollback": {
            "reversible": True,
            "strategy": "revert",
        },
    }
    candidate_fingerprint = validate_candidate(candidate)

    return {
        "version": GUARDRAIL_VERSION,
        "guardrail_id": guardrail_id,
        "pattern_fingerprint": pattern_fingerprint,
        "occurrences": len(ordered),
        "lesson_ids": lesson_ids,
        "sources": sources,
        "expected_prevention": prevention,
        "candidate": candidate,
        "candidate_fingerprint": candidate_fingerprint,
    }


def compile_guardrail_candidates(
    lessons: Any,
    *,
    min_occurrences: int = MIN_OCCURRENCES,
) -> list[dict[str, Any]]:
    """Consolida patrones repetidos y emite candidatos, nunca política estable."""
    if (
        type(min_occurrences) is not int
        or min_occurrences < MIN_OCCURRENCES
        or min_occurrences > MAX_LESSONS
    ):
        raise ExperienceGuardrailError(
            f"min_occurrences debe estar entre {MIN_OCCURRENCES} y {MAX_LESSONS}"
        )

    validated = _validated_lessons(lessons)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in validated:
        groups.setdefault(_pattern_key(item), []).append(item)

    candidates: list[dict[str, Any]] = []
    for key, grouped in groups.items():
        distinct_sources = {item["source"] for item in grouped}
        if len(grouped) < min_occurrences or len(distinct_sources) < min_occurrences:
            continue
        candidates.append(_candidate_for_group(grouped, key))

    return sorted(
        candidates,
        key=lambda item: (
            item["guardrail_id"],
            item["candidate_fingerprint"],
        ),
    )
