#!/usr/bin/env python3
"""Parser puro del kill switch global del modo desatendido.

No realiza I/O. El caller obtiene la respuesta JSON de la URL canónica y entrega
ese objeto a `evaluate_unattended_kill_switch`.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

CANONICAL_SOURCE_URL = "https://api.github.com/repos/pl0n3r/Factory/issues/767"
CANONICAL_REPOSITORY_URL = "https://api.github.com/repos/pl0n3r/Factory"
CANONICAL_ISSUE_NUMBER = 767
CANONICAL_OWNER = "pl0n3r"
MARKER_START_RE = re.compile(r"<!--\s*factory-unattended-kill-switch\b")
MARKER_RE = re.compile(
    r"<!--\s*factory-unattended-kill-switch\s+(\{.*?\})\s*-->",
    re.DOTALL,
)


@dataclass(frozen=True)
class KillSwitchDecision:
    state: str
    global_pause: bool
    reason: str
    source_url: str = CANONICAL_SOURCE_URL
    authority: str = "unchanged"


def _paused(reason: str) -> KillSwitchDecision:
    return KillSwitchDecision("UNKNOWN", True, reason)


def evaluate_unattended_kill_switch(issue_payload: object) -> KillSwitchDecision:
    """Valida la fuente canónica; toda ambigüedad pausa fail-closed."""
    if not isinstance(issue_payload, dict):
        return _paused("source_unreadable")

    if issue_payload.get("number") != CANONICAL_ISSUE_NUMBER:
        return _paused("unexpected_issue")
    if issue_payload.get("url") != CANONICAL_SOURCE_URL:
        return _paused("unexpected_issue_url")
    if issue_payload.get("repository_url") != CANONICAL_REPOSITORY_URL:
        return _paused("unexpected_repository")

    creator = issue_payload.get("user")
    if not isinstance(creator, dict) or creator.get("login") != CANONICAL_OWNER:
        return _paused("unexpected_issue_author")

    body = issue_payload.get("body")
    if not isinstance(body, str):
        return _paused("invalid_issue_body")

    marker_starts = MARKER_START_RE.findall(body)
    if len(marker_starts) != 1:
        return _paused("kill_switch_marker_count_invalid")

    match = MARKER_RE.search(body)
    if match is None:
        return _paused("kill_switch_marker_invalid_syntax")

    try:
        marker = json.loads(match.group(1), object_pairs_hook=_unique_object)
    except DuplicateMarkerKeyError:
        return _paused("kill_switch_marker_duplicate_key")
    except (TypeError, json.JSONDecodeError):
        return _paused("kill_switch_marker_invalid_json")

    if not isinstance(marker, dict) or set(marker) != {"version", "state", "owner"}:
        return _paused("kill_switch_marker_invalid_shape")
    version = marker["version"]
    if type(version) is not int or version != 1:
        return _paused("kill_switch_marker_invalid_version")
    if marker["owner"] != CANONICAL_OWNER:
        return _paused("kill_switch_marker_invalid_owner")

    state = marker["state"]
    if state == "PAUSED":
        return KillSwitchDecision("PAUSED", True, "kill_switch_paused")
    if state == "RUNNING":
        return KillSwitchDecision("RUNNING", False, "kill_switch_running")
    return _paused("kill_switch_marker_invalid_state")
