"""Pure, fail-closed normalization of authenticated lesson event envelopes.

The privileged workflow must authenticate GitHub event identity and bind the
verified envelope to a real run/issue. A verified flag supplied by arbitrary
input is never a substitute for that workflow authentication.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"pl0n3r/[A-Za-z0-9_.-]{1,64}\Z")
EVENT_ID = re.compile(r"[A-Za-z0-9_-]{1,90}\Z")
SENSITIVE = re.compile(
    r"(?:\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"password|passwd|authorization|bearer|cookie|secret|private[_-]?key)\b|"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)
KEYS = frozenset({"event_id", "repo", "issue", "sha", "occurred_at",
                  "event", "summary", "issuer", "verified"})
EVENTS = frozenset({"issue_closed", "pr_merged", "incident_resolved"})


class CaptureError(ValueError):
    """An event cannot be used as a trustworthy lesson candidate."""


def _parse(event: Any) -> dict[str, Any]:
    if type(event) is not dict or set(event) not in (KEYS, KEYS | {"run_sha"}):
        raise CaptureError("invalid_event_envelope")
    if event["issuer"] != "github-actions[bot]" or event["verified"] is not True:
        raise CaptureError("unverified_source")
    if (type(event["repo"]) is not str or not REPO.fullmatch(event["repo"])
            or type(event["issue"]) is not int or event["issue"] <= 0
            or type(event["sha"]) is not str or not SHA.fullmatch(event["sha"])
            or type(event["event_id"]) is not str or not EVENT_ID.fullmatch(event["event_id"])
            or type(event["event"]) is not str or event["event"] not in EVENTS):
        raise CaptureError("invalid_identity")
    # Runner context is evidence of execution, NOT business event identity.
    # It must be well-formed, but redelivery across main SHAs must not split
    # or conflict with an authenticated closure business identity.
    if "run_sha" in event and (type(event["run_sha"]) is not str
                               or not SHA.fullmatch(event["run_sha"])):
        raise CaptureError("invalid_run_provenance")
    # Defense in depth: same GitHub merge must never have two business IDs.
    # This is a structural consistency check, not source authentication.
    if (event["event"] == "pr_merged"
            and event["event_id"] != f"pr_merged-{event['issue']}-{event['sha']}"):
        raise CaptureError("invalid_business_event_identity")
    timestamp = event["occurred_at"]
    if type(timestamp) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp
    ):
        raise CaptureError("invalid_timestamp")
    try:
        when = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaptureError("invalid_timestamp") from exc
    if when.tzinfo != timezone.utc:
        raise CaptureError("invalid_timestamp")
    summary = event["summary"]
    if (type(summary) is not str or summary != summary.strip()
            or not (5 <= len(summary) <= 300)
            or any(ord(c) < 32 or ord(c) == 127 for c in summary)
            or SENSITIVE.search(summary)):
        raise CaptureError("unsafe_summary")
    record = {"event_id": event["event_id"], "repo": event["repo"],
              "issue": event["issue"], "sha": event["sha"],
              "occurred_at": when.isoformat().replace("+00:00", "Z"),
              "event": event["event"], "summary": summary}
    record["fingerprint"] = hashlib.sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return record


def capture_lessons(events: Any) -> tuple[dict[str, Any], ...]:
    """Canonical, deterministic candidates; no publication or external effects."""
    if type(events) is not list or not 1 <= len(events) <= 128:
        raise CaptureError("invalid_event_collection")
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in events:
        item = _parse(raw)
        key = item["repo"], item["event_id"]
        if key in seen and seen[key] != item:
            raise CaptureError("conflicting_event_id")
        seen[key] = item
    return tuple(sorted(seen.values(), key=lambda e: (
        e["occurred_at"], e["repo"], e["event_id"]
    )))
