"""Trusted append-only provenance capabilities for Living Software."""
from __future__ import annotations

import json
from typing import Any


class ProvenanceError(ValueError):
    """Invalid handle, source identity or append-only provenance mutation."""


def _line(value: Any, field: str, max_len: int = 240) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_len
        or "\n" in value
        or "\r" in value
    ):
        raise ProvenanceError(f"{field} debe ser texto de una línea")
    return value.strip()


def _json_copy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProvenanceError("registro de provenance debe ser objeto JSON")
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ProvenanceError("registro de provenance no es JSON seguro") from exc
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ProvenanceError("registro de provenance debe ser objeto JSON")
    return loaded


class _AppendOnlyJsonSource:
    """Small capability object whose records cannot be replaced after append."""

    def __init__(self, source_id: str) -> None:
        self._source_id = _line(source_id, "source_id", 160)
        self._records: dict[str, dict[str, Any]] = {}

    @property
    def source_id(self) -> str:
        return self._source_id

    def _append(self, handle: str, payload: Any) -> None:
        key = _line(handle, "handle", 220)
        if key in self._records:
            raise ProvenanceError("registro append-only ya existe")
        self._records[key] = _json_copy(payload)

    def _resolve(self, handle: str) -> dict[str, Any] | None:
        key = _line(handle, "handle", 220)
        payload = self._records.get(key)
        return None if payload is None else _json_copy(payload)


class TrustedDecisionSource(_AppendOnlyJsonSource):
    """Durable/authenticated decision capability owned by the runtime boundary."""

    def record_decision(self, decision_ref: str, evidence: Any) -> None:
        self._append(decision_ref, evidence)

    def resolve_decision(self, decision_ref: str) -> dict[str, Any] | None:
        return self._resolve(decision_ref)


class TrustedIncidentRegistry(_AppendOnlyJsonSource):
    """Append-only incident capability used as the root of immunity provenance."""

    def record_incident(self, incident_id: str, snapshot: Any) -> None:
        self._append(incident_id, snapshot)

    def resolve_incident(self, incident_id: str) -> dict[str, Any] | None:
        return self._resolve(incident_id)
