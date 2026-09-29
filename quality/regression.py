"""Regression Intelligence: evidencia reproducible sin convertir flakiness en PASS."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from evolution.experience_guardrails import compile_guardrail_candidates
from lecciones.memoria import LessonValidationError, validate_lesson

VERSION = 1
MAX_RUNS = 10_000
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
_PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF = re.compile(
    r"^(?:https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:issues|pull)/[1-9]\d*|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9]\d*)$"
)
_EVIDENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_SENSITIVE = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)"
    r"\b\s*[:=]|bearer\s+[A-Za-z0-9._~+/-]{8,})"
)


class QualityRegressionError(ValueError):
    """Observation de regresión inválida o evidencia insuficiente."""


def analyze_regression(observation: Any, *, evaluated_at: Any) -> dict[str, Any]:
    """Clasifica regression evidence y emite lesson solo tras verificación fuerte."""
    _reject_sensitive(observation)
    expected = {
        "version", "regression_id", "project", "surface", "signature",
        "occurred_at", "source", "root_cause", "prevention",
        "before", "after", "regression_test_ref",
    }
    data = _exact(observation, expected, "observation")
    if data["version"] != VERSION:
        raise QualityRegressionError("version debe ser 1.")

    regression_id = _identifier(data["regression_id"], "regression_id")
    project = _project(data["project"])
    surface = _identifier(data["surface"], "surface")
    signature = _text(data["signature"], "signature", 120)
    root_cause = _text(data["root_cause"], "root_cause", 280)
    prevention = _text(data["prevention"], "prevention", 280)
    source = _source(data["source"])
    evaluated = _timestamp(evaluated_at, "evaluated_at")
    occurred = _timestamp(data["occurred_at"], "occurred_at")
    if occurred > evaluated:
        raise QualityRegressionError("evidence temporal inválida.")

    before = _sample(data["before"], "before")
    after = _sample(data["after"], "after")
    if before["observed_at"] < occurred or after["observed_at"] < before["observed_at"]:
        raise QualityRegressionError("evidence temporal inválida.")
    if after["observed_at"] > evaluated:
        raise QualityRegressionError("evidence temporal inválida.")
    if before["failures"] == 0:
        raise QualityRegressionError("before debe demostrar al menos un fallo.")

    regression_test_ref = data["regression_test_ref"]
    if regression_test_ref is not None:
        regression_test_ref = _evidence_ref(
            regression_test_ref, "regression_test_ref"
        )

    flaky = 0 < before["failures"] < before["runs"]
    reproduced = before["failures"] == before["runs"]
    verified = (
        reproduced
        and after["failures"] == 0
        and regression_test_ref is not None
    )
    classification = (
        "FLAKY" if flaky else "VERIFIED" if verified else "REPRODUCED"
    )
    lesson = None
    if verified:
        lesson = _lesson(
            regression_id=regression_id,
            project=project,
            surface=surface,
            signature=signature,
            occurred_at=_iso(occurred),
            source=source,
            root_cause=root_cause,
            prevention=prevention,
        )

    result = {
        "version": VERSION,
        "regression_id": regression_id,
        "project": project,
        "surface": surface,
        "signature": signature,
        "classification": classification,
        "flaky": flaky,
        "reproduced": reproduced,
        "pass_evidence_eligible": verified,
        "guardrail_material": lesson,
        "provenance": sorted(
            {
                source,
                before["evidence_ref"],
                after["evidence_ref"],
                *([regression_test_ref] if regression_test_ref else []),
            }
        ),
    }
    result["fingerprint"] = _stable_hash(result)
    return result


def compile_regression_guardrail_candidates(
    observations: Any,
    *,
    evaluated_at: Any,
) -> list[dict[str, Any]]:
    """Delega patrones repetidos al Experience Guardrail Compiler existente."""
    if not isinstance(observations, (list, tuple)) or not observations:
        raise QualityRegressionError("observations debe ser lista no vacía.")
    lessons = []
    for observation in observations:
        result = analyze_regression(observation, evaluated_at=evaluated_at)
        if result["guardrail_material"] is not None:
            lessons.append(result["guardrail_material"])
    if not lessons:
        return []
    return compile_guardrail_candidates(lessons)


def _lesson(
    *,
    regression_id: str,
    project: str,
    surface: str,
    signature: str,
    occurred_at: str,
    source: str,
    root_cause: str,
    prevention: str,
) -> dict[str, str]:
    digest = hashlib.sha256(
        f"{project}|{surface}|{signature}|{source}".encode()
    ).hexdigest()[:16]
    lesson = {
        "id": f"regression_{digest}",
        "project": project,
        "kind": "rework",
        "occurred_at": occurred_at,
        "what": f"Regression {signature} en {surface}",
        "why": root_cause,
        "prevention": prevention,
        "source": source,
    }
    try:
        validate_lesson(lesson, f"regression:{regression_id}")
    except LessonValidationError as exc:
        raise QualityRegressionError("lesson derivada inválida.") from exc
    return lesson


def _sample(value: Any, label: str) -> dict[str, Any]:
    row = _exact(
        value,
        {"runs", "failures", "evidence_ref", "observed_at"},
        label,
    )
    runs = row["runs"]
    failures = row["failures"]
    if type(runs) is not int or not 1 <= runs <= MAX_RUNS:
        raise QualityRegressionError(f"{label}.runs fuera de límites.")
    if type(failures) is not int or not 0 <= failures <= runs:
        raise QualityRegressionError(f"{label}.failures incoherente.")
    return {
        "runs": runs,
        "failures": failures,
        "evidence_ref": _evidence_ref(row["evidence_ref"], f"{label}.evidence_ref"),
        "observed_at": _timestamp(row["observed_at"], f"{label}.observed_at"),
    }


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise QualityRegressionError(f"{label} inválido.")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise QualityRegressionError(f"{label} inválido.") from exc
    if parsed.tzinfo is None:
        raise QualityRegressionError(f"{label} inválido.")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _source(value: Any) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise QualityRegressionError("source inválida.")
    return value


def _evidence_ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or _EVIDENCE.fullmatch(value) is None:
        raise QualityRegressionError(f"{label} inválida.")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise QualityRegressionError(f"{label} inválido.")
    return value


def _project(value: Any) -> str:
    if not isinstance(value, str) or _PROJECT.fullmatch(value) is None:
        raise QualityRegressionError("project inválido.")
    return value


def _text(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise QualityRegressionError(f"{label} inválido.")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > limit:
        raise QualityRegressionError(f"{label} inválido.")
    return normalized


def _exact(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise QualityRegressionError(
            f"{label} contiene campos faltantes o no permitidos."
        )
    return value


def _reject_sensitive(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise QualityRegressionError("observation debe ser JSON finito.") from exc
    if len(encoded.encode()) > 100_000:
        raise QualityRegressionError("observation excede tamaño máximo.")
    if _SENSITIVE.search(encoded):
        raise QualityRegressionError("observation contiene forma sensible no permitida.")


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(raw).hexdigest()
