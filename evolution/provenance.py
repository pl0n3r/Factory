"""Read-only provenance capabilities for Living Software."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


class ProvenanceError(ValueError):
    """Invalid handle, source identity or provenance boundary use."""


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
    """Mutable in-memory store useful only for tests and local fixtures."""

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
    """Legacy mutable fixture; never accepted as production trust provenance."""

    def record_decision(self, decision_ref: str, evidence: Any) -> None:
        self._append(decision_ref, evidence)

    def resolve_decision(self, decision_ref: str) -> dict[str, Any] | None:
        return self._resolve(decision_ref)


class TrustedIncidentRegistry(_AppendOnlyJsonSource):
    """Legacy mutable fixture; never accepted as production trust provenance."""

    def record_incident(self, incident_id: str, snapshot: Any) -> None:
        self._append(incident_id, snapshot)

    def resolve_incident(self, incident_id: str) -> dict[str, Any] | None:
        return self._resolve(incident_id)


_RUNTIME_SEAL = object()


class AuthenticatedDecisionReader:
    """Sealed read-only adapter created by the authenticated composition root."""

    __slots__ = ("_source_id", "_resolver", "_seal")

    def __init__(
        self,
        source_id: str,
        resolver: Callable[[str], dict[str, Any] | None],
        *,
        _seal: object,
    ) -> None:
        if _seal is not _RUNTIME_SEAL:
            raise ProvenanceError(
                "AuthenticatedDecisionReader solo puede crearlo el composition root"
            )
        if not callable(resolver):
            raise ProvenanceError("decision resolver inválido")
        self._source_id = _line(source_id, "source_id", 160)
        self._resolver = resolver
        self._seal = _seal

    @property
    def source_id(self) -> str:
        return self._source_id

    def resolve_decision(self, decision_ref: str) -> dict[str, Any] | None:
        key = _line(decision_ref, "decision_ref", 220)
        payload = self._resolver(key)
        return None if payload is None else _json_copy(payload)


class AuthenticatedIncidentReader:
    """Sealed read-only adapter created by the authenticated composition root."""

    __slots__ = ("_source_id", "_resolver", "_seal")

    def __init__(
        self,
        source_id: str,
        resolver: Callable[[str], dict[str, Any] | None],
        *,
        _seal: object,
    ) -> None:
        if _seal is not _RUNTIME_SEAL:
            raise ProvenanceError(
                "AuthenticatedIncidentReader solo puede crearlo el composition root"
            )
        if not callable(resolver):
            raise ProvenanceError("incident resolver inválido")
        self._source_id = _line(source_id, "source_id", 160)
        self._resolver = resolver
        self._seal = _seal

    @property
    def source_id(self) -> str:
        return self._source_id

    def resolve_incident(self, incident_id: str) -> dict[str, Any] | None:
        key = _line(incident_id, "incident_id", 220)
        payload = self._resolver(key)
        return None if payload is None else _json_copy(payload)


def _authenticated_decision_reader(
    source_id: str,
    resolver: Callable[[str], dict[str, Any] | None],
) -> AuthenticatedDecisionReader:
    """Composition-root hook after external authentication/authorization."""
    return AuthenticatedDecisionReader(source_id, resolver, _seal=_RUNTIME_SEAL)


def _authenticated_incident_reader(
    source_id: str,
    resolver: Callable[[str], dict[str, Any] | None],
) -> AuthenticatedIncidentReader:
    """Composition-root hook after external authentication/authorization."""
    return AuthenticatedIncidentReader(source_id, resolver, _seal=_RUNTIME_SEAL)


def is_authenticated_decision_reader(value: Any) -> bool:
    return (
        isinstance(value, AuthenticatedDecisionReader)
        and getattr(value, "_seal", None) is _RUNTIME_SEAL
    )


def is_authenticated_incident_reader(value: Any) -> bool:
    return (
        isinstance(value, AuthenticatedIncidentReader)
        and getattr(value, "_seal", None) is _RUNTIME_SEAL
    )
