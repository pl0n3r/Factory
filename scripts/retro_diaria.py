#!/usr/bin/env python3
"""Retrospectiva de 24 horas sobre evidencia autenticada; módulo puro y fail-closed.

No hace solicitudes, lecturas, publicaciones ni mutaciones de GitHub.
El caller recopila las fuentes y obtiene los datos de forma independiente.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
EVENT_KINDS = frozenset({"pr_merged", "incident_opened", "incident_closed", "lesson_recorded", "agent_dispatched"})
MAX_EVENTS = 2000
MAX_SOURCES = 50
UTC_OFFSET = "+00:00"


def _utc(value: Any) -> datetime | None:
    """Rechaza timestamps ingenuos, bool, epoch y cadenas malformadas."""
    if not isinstance(value, str) or not value or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", UTC_OFFSET))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _deny(reason: str) -> dict[str, str]:
    return {"status": "UNKNOWN", "reason": reason}


def _validated_sources(sources: list[Any]) -> tuple[dict[str, str], set[str], str | None]:
    """Build a source index without trusting case variants as unique repos."""
    valid_sources: dict[str, str] = {}
    repos: set[str] = set()
    canonical_repos: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            return {}, set(), "invalid_source"
        sid, repo, sha = (source.get(x) for x in ("id", "repo", "sha"))
        if (not isinstance(sid, str) or not 1 <= len(sid) <= 100
                or not isinstance(repo, str) or not REPO_RE.fullmatch(repo)
                or not isinstance(sha, str) or not SHA_RE.fullmatch(sha)
                or source.get("authenticated") is not True
                or source.get("complete") is not True):
            return {}, set(), "unauthenticated_or_incomplete_source"
        # GitHub repository identities are case-insensitive.
        canonical = repo.casefold()
        if sid in valid_sources or canonical in canonical_repos:
            return {}, set(), "ambiguous_source_identity"
        valid_sources[sid] = repo
        repos.add(repo)
        canonical_repos.add(canonical)
    return valid_sources, repos, None


def _validated_events(
    events: list[Any], valid_sources: dict[str, str], repos: set[str], anchor: datetime,
) -> tuple[dict[tuple[str, str], tuple[str, str, str, datetime]], str | None]:
    """Validate every event before projecting any counts or public output."""
    dedup: dict[tuple[str, str], tuple[str, str, str, datetime]] = {}
    for item in events:
        if not isinstance(item, dict):
            return {}, "invalid_event"
        eid, sid, repo, kind = (item.get(x) for x in ("id", "source_id", "repo", "kind"))
        stamp = _utc(item.get("occurred_at"))
        # Check primitive types BEFORE comparing/looking up untrusted values.
        # A str subclass or a foreign object can override equality and hashing.
        if (type(eid) is not str or not 1 <= len(eid) <= 120
                or type(sid) is not str or type(repo) is not str
                or type(kind) is not str
                or valid_sources.get(sid) != repo or repo not in repos
                or kind not in EVENT_KINDS):
            return {}, "invalid_event_identity"
        if stamp is None or stamp > anchor:
            return {}, "invalid_event_time"
        row = (repo, kind, sid, stamp)
        key = (repo, eid)
        if key in dedup and dedup[key] != row:
            return {}, "conflicting_duplicate_event"
        dedup[key] = row
    return dedup, None


def _format_utc(value: datetime) -> str:
    return value.isoformat().replace(UTC_OFFSET, "Z")


def evaluate_retro_daily(*, events: Any, sources: Any, now: Any) -> dict[str, Any]:
    """Genera resumen estable de [now-24h, now] sin convertir huecos en ceros.

    sources: lista de {id, repo, sha, authenticated, complete}. Cada fuente
    describe un inventario externo exhaustivo y autenticado del repositorio.
    events: lista de {id, source_id, repo, kind, occurred_at}. id debe ser
    identidad estable del hecho en el repositorio (no ID del envío/webhook).
    Duplicados idénticos se descartan; los contradictorios invalidan el snapshot.
    now: timestamp ISO 8601 con zona, explícito para reproducibilidad.

    status=READY describe SOLO un resumen offline. No autoriza publicar.
    """
    anchor = _utc(now)
    if anchor is None:
        return _deny("invalid_clock")
    if (not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES
            or not isinstance(events, list) or len(events) > MAX_EVENTS):
        return _deny("missing_or_unbounded_evidence")

    valid_sources, repos, source_problem = _validated_sources(sources)
    if source_problem is not None:
        return _deny(source_problem)

    try:
        start = anchor - timedelta(hours=24)
    except OverflowError:
        return _deny("invalid_clock_range")
    # Una identidad de evento es única DENTRO del repositorio, no entre repos.
    dedup, event_problem = _validated_events(events, valid_sources, repos, anchor)
    if event_problem is not None:
        return _deny(event_problem)

    selected = sorted(
        ((eid, *row) for (_, eid), row in dedup.items() if start <= row[-1] <= anchor),
        key=lambda item: (item[4], item[1], item[2], item[0]),
    )
    totals = {repo: dict.fromkeys(sorted(EVENT_KINDS), 0) for repo in sorted(repos)}
    for _, repo, kind, _, _ in selected:
        totals[repo][kind] += 1
    # No exponer IDs crudos, comentarios ni metadatos de origen en el resumen.
    public_events = [
        {"repo": repo, "kind": kind,
         "occurred_at": _format_utc(stamp)}
        for _, repo, kind, _, stamp in selected
    ]
    return {
        "status": "READY",
        "reason": "complete_authenticated_snapshot",
        "window_start": _format_utc(start),
        "window_end": _format_utc(anchor),
        "events": public_events,
        "counts_by_repo": totals,
        "publication_allowed": False,
    }
