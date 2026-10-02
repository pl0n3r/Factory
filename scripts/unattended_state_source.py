#!/usr/bin/env python3
"""Fuente pura STATE/Presence desde evidencia GitHub ya obtenida por el caller."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re

from scripts.unattended_watchdog import validate_state

TRUSTED_RESERVATION_LOGIN = "github-actions[bot]"
RESERVATION_RE = re.compile(r"<!--\s*condor-reserva\s+(\{.*?\})\s*-->", re.DOTALL)
STATE_START_RE = re.compile(r"<!--\s*factory-state\b")
STATE_RE = re.compile(r"<!--\s*factory-state\s+(\{.*?\})\s*-->", re.DOTALL)
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
RESERVATION_V1_RELEASE_FIELDS = frozenset({
    "active",
    "branch",
    "owner",
    "reason",
    "reservation_id",
    "version",
})
RESERVATION_V3_FIELDS = frozenset({
    "version",
    "owner",
    "reservation_id",
    "branch",
    "active",
    "reason",
    "acceptance_sha256",
    "task_marker_sha256",
    "task_paths",
    "task_depends_on",
})


class StateSourceValidationError(ValueError):
    """La evidencia no permite construir una fuente canónica segura."""


class DuplicateJsonKeyError(ValueError):
    """Un marker no puede depender de semántica last-key-wins."""


@dataclass(frozen=True)
class StatePresenceProjection:
    status: str
    authority: str
    reasons: tuple[str, ...]
    state: dict[str, object] | None
    presence: dict[str, object]
    reservation_id: str | None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _json(raw: str, reason: str) -> dict[str, object]:
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, DuplicateJsonKeyError, TypeError) as exc:
        raise StateSourceValidationError(reason) from exc
    if not isinstance(value, dict):
        raise StateSourceValidationError(reason)
    return value


def _time(value: object, reason: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise StateSourceValidationError(reason)
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise StateSourceValidationError(reason) from exc
    if parsed.tzinfo is None:
        raise StateSourceValidationError(reason)
    return parsed


def _comment_time(comment: dict[str, object]) -> datetime:
    return _time(comment.get("updated_at") or comment.get("created_at"), "invalid_comment_timestamp")


def _comments(value: object, now: datetime) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise StateSourceValidationError("invalid_comments")
    normalized: list[dict[str, object]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise StateSourceValidationError("invalid_comment")
        user = raw.get("user")
        body = raw.get("body")
        if not isinstance(user, dict) or not isinstance(user.get("login"), str):
            raise StateSourceValidationError("invalid_comment_user")
        if not isinstance(body, str):
            raise StateSourceValidationError("invalid_comment_body")
        stamp = _comment_time(raw)
        if stamp > now:
            raise StateSourceValidationError("future_comment_timestamp")
        normalized.append({**raw, "_time": stamp})
    normalized.sort(key=lambda item: item["_time"])
    return normalized


def _reservation(value: dict[str, object], issue_number: int) -> dict[str, object]:
    version = value.get("version")
    if type(version) is not int:
        raise StateSourceValidationError("invalid_reservation_version")
    if version == 1:
        if set(value) != RESERVATION_V1_RELEASE_FIELDS:
            raise StateSourceValidationError("invalid_reservation_shape")
    elif version == 3:
        if set(value) != RESERVATION_V3_FIELDS:
            raise StateSourceValidationError("invalid_reservation_shape")
    else:
        raise StateSourceValidationError("invalid_reservation_version")

    if not isinstance(value["owner"], str) or not value["owner"]:
        raise StateSourceValidationError("invalid_reservation_owner")
    rid = value["reservation_id"]
    if not isinstance(rid, str) or not UUID_RE.fullmatch(rid.lower()):
        raise StateSourceValidationError("invalid_reservation_id")
    if value["branch"] != f"trabajo/issue-{issue_number}":
        raise StateSourceValidationError("reservation_branch_mismatch")
    if not isinstance(value["active"], bool):
        raise StateSourceValidationError("invalid_reservation_active")
    if not isinstance(value["reason"], str) or not value["reason"]:
        raise StateSourceValidationError("invalid_reservation_reason")

    if version == 1:
        if value["active"] is not False:
            raise StateSourceValidationError("invalid_reservation_v1_active")
        return value

    if value["active"] is not True:
        raise StateSourceValidationError("invalid_reservation_v3_active")
    if (
        not isinstance(value["acceptance_sha256"], str)
        or not SHA256_RE.fullmatch(value["acceptance_sha256"])
    ):
        raise StateSourceValidationError("invalid_acceptance_sha256")
    if (
        not isinstance(value["task_marker_sha256"], str)
        or not SHA256_RE.fullmatch(value["task_marker_sha256"])
    ):
        raise StateSourceValidationError("invalid_task_marker_sha256")
    paths = value["task_paths"]
    if (
        not isinstance(paths, list)
        or not paths
        or any(not isinstance(path, str) or not path for path in paths)
        or len(paths) != len(set(paths))
    ):
        raise StateSourceValidationError("invalid_reservation_paths")
    dependencies = value["task_depends_on"]
    if (
        not isinstance(dependencies, list)
        or any(type(number) is not int or number <= 0 for number in dependencies)
        or len(dependencies) != len(set(dependencies))
    ):
        raise StateSourceValidationError("invalid_reservation_dependencies")
    return value


def _latest_reservation(
    comments: list[dict[str, object]], issue_number: int
) -> tuple[dict[str, object] | None, datetime | None]:
    latest: dict[str, object] | None = None
    latest_at: datetime | None = None
    for comment in comments:
        if comment["user"]["login"] != TRUSTED_RESERVATION_LOGIN:
            continue
        matches = RESERVATION_RE.findall(comment["body"])
        if not matches:
            continue
        if len(matches) != 1:
            raise StateSourceValidationError("reservation_marker_duplicated")
        latest = _reservation(_json(matches[0], "invalid_reservation_json"), issue_number)
        latest_at = comment["_time"]
    return latest, latest_at


def _state_candidates(
    comments: list[dict[str, object]],
) -> list[tuple[dict[str, object], dict[str, object]]]:
    found: list[tuple[dict[str, object], dict[str, object]]] = []
    for comment in comments:
        starts = STATE_START_RE.findall(comment["body"])
        if not starts:
            continue
        matches = STATE_RE.findall(comment["body"])
        if len(starts) != 1 or len(matches) != 1:
            raise StateSourceValidationError("state_marker_missing_or_duplicated")
        marker = _json(matches[0], "invalid_state_marker_json")
        if (
            set(marker) != {"version", "state"}
            or type(marker["version"]) is not int
            or marker["version"] != 1
        ):
            raise StateSourceValidationError("invalid_state_marker_shape")
        if not isinstance(marker["state"], dict):
            raise StateSourceValidationError("invalid_state_marker_state")
        found.append((comment, marker["state"]))
    return found


def _unknown_presence(now_text: str) -> dict[str, object]:
    return {
        "version": 1,
        "source": "factory-state-github",
        "observed_at": now_text,
        "sessions": [],
        "capacity": {
            "known_slots": 0,
            "eligible_free_slots": 0,
            "degraded_slots": 0,
            "freshness": "unknown",
        },
    }


def project_state_presence(
    *,
    repository: str,
    issue_number: int,
    comments: object,
    now: str,
    state_stale_minutes: int,
    reservation_stale_minutes: int,
    branch_head_sha: str | None = None,
) -> StatePresenceProjection:
    """Proyecta solo evidencia demostrable; heartbeat/capacidad ausentes quedan UNKNOWN."""
    try:
        if not isinstance(repository, str) or not REPO_RE.fullmatch(repository):
            raise StateSourceValidationError("invalid_repository")
        if type(issue_number) is not int or issue_number <= 0:
            raise StateSourceValidationError("invalid_issue_number")
        if type(state_stale_minutes) is not int or state_stale_minutes <= 0:
            raise StateSourceValidationError("invalid_state_stale_minutes")
        if type(reservation_stale_minutes) is not int or reservation_stale_minutes <= 0:
            raise StateSourceValidationError("invalid_reservation_stale_minutes")
        if branch_head_sha is not None and (
            not isinstance(branch_head_sha, str) or not SHA_RE.fullmatch(branch_head_sha)
        ):
            raise StateSourceValidationError("invalid_branch_head_sha")
        now_dt = _time(now, "invalid_now")
        parsed = _comments(comments, now_dt)
        reservation, reservation_at = _latest_reservation(parsed, issue_number)
        presence = _unknown_presence(now)

        if reservation is None or reservation.get("active") is not True:
            return StatePresenceProjection(
                "UNKNOWN",
                "unchanged",
                ("active_reservation_unavailable",),
                None,
                presence,
                None,
            )

        reasons: list[str] = [
            "presence_heartbeat_unavailable",
            "presence_capacity_unknown",
        ]
        assert reservation_at is not None
        if (now_dt - reservation_at).total_seconds() / 60.0 >= reservation_stale_minutes:
            reasons.append("reservation_stale")

        candidates = [
            pair
            for pair in _state_candidates(parsed)
            if pair[0]["user"]["login"] == reservation["owner"]
        ]
        if not candidates:
            return StatePresenceProjection(
                "UNKNOWN",
                "unchanged",
                tuple(sorted(set((*reasons, "state_marker_unavailable")))),
                None,
                presence,
                str(reservation["reservation_id"]),
            )

        comment, raw_state = candidates[-1]
        normalized = validate_state(
            raw_state,
            now=now_dt,
            stale_after_minutes=state_stale_minutes,
        )
        if _time(normalized["updated_at"], "invalid_state_updated_at") > comment["_time"]:
            raise StateSourceValidationError("state_timestamp_after_comment")

        expected_identity = f"{repository}#{issue_number}"
        if normalized["repository"] != repository:
            raise StateSourceValidationError("state_repository_mismatch")
        if normalized["work_identity"] != expected_identity:
            raise StateSourceValidationError("state_work_identity_mismatch")
        if normalized["reservation_id"] != reservation["reservation_id"]:
            raise StateSourceValidationError("state_reservation_mismatch")
        if normalized["branch"] != reservation["branch"]:
            raise StateSourceValidationError("state_branch_mismatch")
        if (
            branch_head_sha is not None
            and normalized["head_sha"] is not None
            and normalized["head_sha"] != branch_head_sha
        ):
            raise StateSourceValidationError("state_head_sha_mismatch")

        if normalized["freshness"] == "stale":
            reasons.append("state_stale")
        status = "UNKNOWN" if "reservation_stale" in reasons else "READY"
        canonical_state = dict(raw_state)
        return StatePresenceProjection(
            status,
            "unchanged",
            tuple(sorted(set(reasons))),
            canonical_state,
            presence,
            str(reservation["reservation_id"]),
        )
    except (StateSourceValidationError, ValueError, TypeError) as exc:
        reason = str(exc) if str(exc) else "invalid_state_source"
        return StatePresenceProjection(
            "BLOCKED",
            "unchanged",
            (reason,),
            None,
            _unknown_presence("1970-01-01T00:00:00Z"),
            None,
        )
