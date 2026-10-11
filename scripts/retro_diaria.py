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


def _utc(value: Any) -> datetime | None:
    """Rechaza timestamps ingenuos, bool, epoch y cadenas malformadas."""
    if not isinstance(value, str) or not value or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _deny(reason: str) -> dict[str, str]:
    return {"status": "UNKNOWN", "reason": reason}


def evaluate_retro_daily(*, events: Any, sources: Any, now: Any) -> dict[str, Any]:
    """Genera resumen estable de [now-24h, now] sin convertir huecos en ceros.

    sources: lista de {id, repo, sha, authenticated, complete}. Cada fuente
    describe un inventario externo exhaustivo y autenticado del repositorio.
    events: lista de {id, source_id, repo, kind, occurred_at}. Duplicados
    idénticos se descartan; duplicados contradictorios invalidan el snapshot.
    now: timestamp ISO 8601 con zona, explícito para reproducibilidad.

    status=READY describe SOLO un resumen offline. No autoriza publicar.
    """
    anchor = _utc(now)
    if anchor is None:
        return _deny("invalid_clock")
    if (not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES
            or not isinstance(events, list) or len(events) > MAX_EVENTS):
        return _deny("missing_or_unbounded_evidence")

    valid_sources: dict[str, str] = {}
    repos: set[str] = set()
    canonical_repos: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            return _deny("invalid_source")
        sid, repo, sha = (source.get(x) for x in ("id", "repo", "sha"))
        if (not isinstance(sid, str) or not 1 <= len(sid) <= 100
                or not isinstance(repo, str) or not REPO_RE.fullmatch(repo)
                or not isinstance(sha, str) or not SHA_RE.fullmatch(sha)
                or source.get("authenticated") is not True
                or source.get("complete") is not True):
            return _deny("unauthenticated_or_incomplete_source")
        # GitHub identities are case-insensitive even when the display name differs.
        # Do not count two sources for the same canonical repository.
        canonical = repo.casefold()
        if sid in valid_sources or canonical in canonical_repos:
            return _deny("ambiguous_source_identity")
        valid_sources[sid] = repo
        repos.add(repo)
        canonical_repos.add(canonical)

    try:
        start = anchor - timedelta(hours=24)
    except OverflowError:
        return _deny("invalid_clock_range")
    # Una identidad de evento es única DENTRO del repositorio, no entre repos.
    dedup: dict[tuple[str, str], tuple[str, str, str, datetime]] = {}
    for item in events:
        if not isinstance(item, dict):
            return _deny("invalid_event")
        eid, sid, repo, kind = (item.get(x) for x in ("id", "source_id", "repo", "kind"))
        stamp = _utc(item.get("occurred_at"))
        if (not isinstance(eid, str) or not 1 <= len(eid) <= 120
                or not isinstance(sid, str) or valid_sources.get(sid) != repo
                or not isinstance(repo, str) or repo not in repos
                or not isinstance(kind, str) or kind not in EVENT_KINDS):
            return _deny("invalid_event_identity")
        if stamp is None or stamp > anchor:
            return _deny("invalid_event_time")
        row = (repo, kind, sid, stamp)
        key = (repo, eid)
        if key in dedup and dedup[key] != row:
            return _deny("conflicting_duplicate_event")
        dedup[key] = row

    selected = sorted(
        ((eid, *row) for (_, eid), row in dedup.items() if start <= row[-1] <= anchor),
        key=lambda item: (item[4], item[1], item[2], item[0]),
    )
    totals = {repo: {kind: 0 for kind in sorted(EVENT_KINDS)} for repo in sorted(repos)}
    for _, repo, kind, _, _ in selected:
        totals[repo][kind] += 1
    # No exponer IDs crudos, comentarios ni metadatos de origen en el resumen.
    public_events = [
        {"repo": repo, "kind": kind,
         "occurred_at": stamp.isoformat().replace("+00:00", "Z")}
        for _, repo, kind, _, stamp in selected
    ]
    return {
        "status": "READY",
        "reason": "complete_authenticated_snapshot",
        "window_start": start.isoformat().replace("+00:00", "Z"),
        "window_end": anchor.isoformat().replace("+00:00", "Z"),
        "events": public_events,
        "counts_by_repo": totals,
        "publication_allowed": False,
    }
