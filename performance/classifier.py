"""Fail-closed adapter from project performance envelopes to the canonical detector."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Any

from performance.contract import validate_performance_contract
from performance.detector import detect_performance

AUTHORITY = "factory-performance-v1"
MAX_OBSERVATIONS = 1000
ENVELOPE_FIELDS = {
    "version", "project", "classification_authority", "classification",
    "identity", "evidence_ref", "observed_at", "observations",
}
IDENTITY_FIELDS = {"sha", "release"}
_SHA = re.compile(r"^[0-9a-f]{40}$")
_RELEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class PerformanceClassifierError(ValueError):
    """Envelope cannot be classified safely."""


def classify_performance_envelope(
    contract: Mapping[str, Any],
    envelope: Mapping[str, Any],
    *,
    evaluated_at: str,
) -> dict[str, Any]:
    canonical = validate_performance_contract(contract)
    env = _envelope(envelope)
    if env["project"] != canonical["project"]:
        raise PerformanceClassifierError("Envelope project does not match contract.")
    results = []
    seen: set[tuple[str, str]] = set()
    for raw in env["observations"]:
        if not isinstance(raw, Mapping):
            raise PerformanceClassifierError("Observation must be an object.")
        if raw.get("project") != env["project"]:
            raise PerformanceClassifierError("Observation project mismatch.")
        if raw.get("sha") != env["identity"]["sha"] or raw.get("release") != env["identity"]["release"]:
            raise PerformanceClassifierError("Observation identity mismatch.")
        if raw.get("evidence_ref") != env["evidence_ref"]:
            raise PerformanceClassifierError("Observation evidence mismatch.")
        identity = (raw.get("surface"), raw.get("metric"))
        if not all(isinstance(value, str) for value in identity):
            raise PerformanceClassifierError("Observation identity is invalid.")
        if identity in seen:
            raise PerformanceClassifierError("Duplicate surface/metric observation.")
        seen.add(identity)
        results.append(detect_performance(canonical, raw, evaluated_at=evaluated_at))

    results.sort(key=lambda row: (row["surface"], row["metric"]))
    classifications = Counter(row["classification"] for row in results)
    states = Counter(row["evidence_state"] for row in results)
    return {
        "version": 1,
        "project": env["project"],
        "classification_authority": AUTHORITY,
        "evaluated_at": _timestamp(evaluated_at, "evaluated_at"),
        "identity": env["identity"],
        "evidence_ref": env["evidence_ref"],
        "source_observed_at": env["observed_at"],
        "summary": {
            "total": len(results),
            "classifications": dict(sorted(classifications.items())),
            "evidence_states": dict(sorted(states.items())),
        },
        "results": results,
    }


def _envelope(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != ENVELOPE_FIELDS:
        raise PerformanceClassifierError("Envelope shape is invalid.")
    if raw["version"] != 1 or raw["classification_authority"] != AUTHORITY:
        raise PerformanceClassifierError("Envelope version or authority is invalid.")
    if raw["classification"] is not None:
        raise PerformanceClassifierError("Producer classification must be null.")
    if not isinstance(raw["project"], str) or not raw["project"]:
        raise PerformanceClassifierError("Envelope project is invalid.")
    identity = raw["identity"]
    if not isinstance(identity, Mapping) or set(identity) != IDENTITY_FIELDS:
        raise PerformanceClassifierError("Envelope identity is invalid.")
    sha, release = identity["sha"], identity["release"]
    if not isinstance(sha, str) or _SHA.fullmatch(sha) is None:
        raise PerformanceClassifierError("Envelope SHA is invalid.")
    if not isinstance(release, str) or _RELEASE.fullmatch(release) is None:
        raise PerformanceClassifierError("Envelope release is invalid.")
    evidence_ref = raw["evidence_ref"]
    if not isinstance(evidence_ref, str) or not evidence_ref or len(evidence_ref) > 240:
        raise PerformanceClassifierError("Envelope evidence reference is invalid.")
    observed_at = _timestamp(raw["observed_at"], "observed_at")
    observations = raw["observations"]
    if not isinstance(observations, list) or not 1 <= len(observations) <= MAX_OBSERVATIONS:
        raise PerformanceClassifierError("Envelope observations are invalid.")
    return {
        "version": 1,
        "project": raw["project"],
        "classification_authority": AUTHORITY,
        "classification": None,
        "identity": {"sha": sha, "release": release},
        "evidence_ref": evidence_ref,
        "observed_at": observed_at,
        "observations": observations,
    }


def _timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PerformanceClassifierError(f"{label} must be ISO-8601 with timezone.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise PerformanceClassifierError(f"{label} must be ISO-8601 with timezone.") from exc
    if parsed.tzinfo is None:
        raise PerformanceClassifierError(f"{label} must be ISO-8601 with timezone.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
