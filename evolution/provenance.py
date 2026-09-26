"""Read-only authenticated provenance capabilities for Living Software."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from types import MappingProxyType
from typing import Any


class ProvenanceError(ValueError):
    """Invalid handle, source identity or provenance boundary use."""


def _line(value: Any, field: str, max_len: int = 240) -> str:
    """Normalize one-line provenance metadata."""
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
    """Return a detached JSON-safe object."""
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
        """Expose fixture identity."""
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


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Fail closed instead of forwarding provenance credentials to redirects."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise ProvenanceError("fuente de provenance no admite redirects")


def _fetch_json(url: str, token: str) -> dict[str, Any]:
    """Fetch an authenticated JSON object from the configured durable source."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Factory-Living-Provenance/1",
        },
        method="GET",
    )
    # add_unredirected_header keeps the bearer out of headers copied by
    # HTTPRedirectHandler; _RejectRedirects additionally rejects every 30x.
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    opener = urllib.request.build_opener(_RejectRedirects())
    try:
        with opener.open(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except ProvenanceError:
        raise
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProvenanceError("fuente de provenance no disponible o inválida") from exc
    if not isinstance(payload, dict):
        raise ProvenanceError("fuente de provenance debe devolver objeto JSON")
    return _json_copy(payload)


def _environment_source(kind: str) -> tuple[str, str, str]:
    """Resolve trust-root configuration outside caller-provided payloads."""
    prefix = "FACTORY_DECISION" if kind == "decision" else "FACTORY_INCIDENT"
    source_id = _line(os.environ.get(f"{prefix}_SOURCE_ID"), "source_id", 160)
    url = _line(os.environ.get(f"{prefix}_SOURCE_URL"), "source_url", 500)
    token = _line(os.environ.get("FACTORY_PROVENANCE_TOKEN"), "provenance_token", 4096)
    if not url.startswith("https://"):
        raise ProvenanceError("source_url productiva debe usar https")
    return source_id, url, token


def _snapshot_records(value: Any) -> MappingProxyType:
    """Freeze a detached handle->record snapshot fetched from durable storage."""
    payload = _json_copy(value)
    records: dict[str, dict[str, Any]] = {}
    for handle, record in payload.items():
        key = _line(handle, "handle", 220)
        records[key] = _json_copy(record)
    return MappingProxyType(records)


class AuthenticatedDecisionReader:
    """Read-only snapshot loaded only from externally configured authenticated I/O."""

    __slots__ = ("_source_id", "_records")

    def __init__(self) -> None:
        source_id, url, token = _environment_source("decision")
        self._source_id = source_id
        self._records = _snapshot_records(_fetch_json(url, token))

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("AuthenticatedDecisionReader no admite subclases")

    @property
    def source_id(self) -> str:
        """Expose authenticated source identity."""
        return self._source_id

    def resolve_decision(self, decision_ref: str) -> dict[str, Any] | None:
        """Resolve an exact decision handle from the authenticated snapshot."""
        key = _line(decision_ref, "decision_ref", 220)
        payload = self._records.get(key)
        return None if payload is None else _json_copy(payload)


class AuthenticatedIncidentReader:
    """Read-only snapshot loaded only from externally configured authenticated I/O."""

    __slots__ = ("_source_id", "_records")

    def __init__(self) -> None:
        source_id, url, token = _environment_source("incident")
        self._source_id = source_id
        self._records = _snapshot_records(_fetch_json(url, token))

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("AuthenticatedIncidentReader no admite subclases")

    @property
    def source_id(self) -> str:
        """Expose authenticated source identity."""
        return self._source_id

    def resolve_incident(self, incident_id: str) -> dict[str, Any] | None:
        """Resolve an exact incident handle from the authenticated snapshot."""
        key = _line(incident_id, "incident_id", 220)
        payload = self._records.get(key)
        return None if payload is None else _json_copy(payload)


def authenticated_decision_reader_from_environment() -> AuthenticatedDecisionReader:
    """Build a decision reader only from externally configured authenticated I/O."""
    return AuthenticatedDecisionReader()


def authenticated_incident_reader_from_environment() -> AuthenticatedIncidentReader:
    """Build an incident reader only from externally configured authenticated I/O."""
    return AuthenticatedIncidentReader()


def is_authenticated_decision_reader(value: Any) -> bool:
    """Return whether value is the exact production reader capability."""
    return type(value) is AuthenticatedDecisionReader


def is_authenticated_incident_reader(value: Any) -> bool:
    """Return whether value is the exact production reader capability."""
    return type(value) is AuthenticatedIncidentReader
