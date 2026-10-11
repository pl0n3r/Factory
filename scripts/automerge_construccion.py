"""Política diagnóstica pura; nunca autoriza ni ejecuta una fusión."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

SHA = re.compile(r"[0-9a-f]{40}\Z")
FIELDS = frozenset({
    "phase", "kill_switch", "head_sha", "observed_head_sha", "base_sha",
    "main_sha", "draft", "mergeable", "behind_by", "required_checks",
    "gates", "reviews", "author", "blocking_threads", "paths",
    "freeze_active", "human_gate_required", "inventory_complete",
    "api_remaining", "api_minimum", "observed_at", "expires_at", "now",
})
SENSITIVE = ("release", "ruleset", "security", "seguridad", "politica", "política", "policy")


@dataclass(frozen=True)
class Decision:
    eligible: bool = False
    reason: str = "invalid_snapshot"

    def public(self) -> dict[str, bool | str]:
        """Proyección fija sin eco de campos, tokens ni mensajes externos."""
        return {"eligible": self.eligible, "reason": self.reason}


def _deny(reason: str) -> Decision:
    return Decision(False, reason)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None
    return parsed.astimezone(timezone.utc)


def _paths_status(paths: Any) -> str:
    if not isinstance(paths, list) or not paths:
        return "invalid_snapshot"
    for path in paths:
        if (not isinstance(path, str) or not path or path != path.strip()
                or "\\" in path or "\x00" in path or path.startswith("/")
                or any(part in ("", ".", "..") for part in path.split("/"))):
            return "invalid_snapshot"
        normalized = path.casefold()
        if (any(word in normalized for word in SENSITIVE)
                or normalized in {"agents.md", "agentes.md", "plan-agentes.md", "datos.yml"}
                or normalized.startswith(".github/codeowners")):
            return "sensitive_paths"
    return "ok"


def evaluate(snapshot: Any) -> Decision:
    """Evalúa evidencia sintética no confiable; *eligible* solo es diagnóstico."""
    if not isinstance(snapshot, dict) or set(snapshot) != FIELDS:
        return _deny("invalid_snapshot")
    if snapshot["phase"] != "construccion":
        return _deny("human_gate_required")
    if snapshot["kill_switch"] != "RUNNING":
        return _deny("kill_switch_inactive")
    head = snapshot["head_sha"]
    if (not _sha(head) or not _sha(snapshot["observed_head_sha"])
            or not _sha(snapshot["base_sha"]) or not _sha(snapshot["main_sha"])
            or head != snapshot["observed_head_sha"]
            or snapshot["base_sha"] != snapshot["main_sha"]):
        return _deny("sha_mismatch")
    if (type(snapshot["draft"]) is not bool or type(snapshot["mergeable"]) is not bool
            or type(snapshot["behind_by"]) is not int or snapshot["behind_by"] < 0):
        return _deny("invalid_snapshot")
    if snapshot["draft"] or not snapshot["mergeable"] or snapshot["behind_by"]:
        return _deny("pr_not_ready")
    for flag in ("freeze_active", "human_gate_required", "inventory_complete"):
        if type(snapshot[flag]) is not bool:
            return _deny("invalid_snapshot")
    if snapshot["freeze_active"] or snapshot["human_gate_required"]:
        return _deny("human_gate_required")
    if not snapshot["inventory_complete"]:
        return _deny("incomplete_evidence")
    path_status = _paths_status(snapshot["paths"])
    if path_status != "ok":
        return _deny(path_status)

    times = [_utc(snapshot[key]) for key in ("observed_at", "expires_at", "now")]
    if any(value is None for value in times):
        return _deny("incomplete_evidence")
    observed, expiry, now = times
    if not (observed <= now <= expiry and timedelta(0) < expiry - observed <= timedelta(minutes=5)):
        return _deny("stale_evidence")

    remaining, minimum = snapshot["api_remaining"], snapshot["api_minimum"]
    if type(remaining) is not int or type(minimum) is not int or remaining < 0 or minimum < 20:
        return _deny("invalid_snapshot")
    if remaining < minimum:
        return _deny("insufficient_budget")

    gates = snapshot["gates"]
    if not isinstance(gates, dict) or set(gates) != {"acceptance", "coordination", "security"}:
        return _deny("incomplete_evidence")
    for gate in gates.values():
        if not isinstance(gate, dict) or set(gate) != {"conclusion", "head_sha"}:
            return _deny("invalid_snapshot")
        if gate["conclusion"] != "success" or gate["head_sha"] != head:
            return _deny("checks_not_green")

    checks = snapshot["required_checks"]
    if not isinstance(checks, list) or not checks:
        return _deny("incomplete_evidence")
    names: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"name", "conclusion", "head_sha"}:
            return _deny("invalid_snapshot")
        name = check["name"]
        if not isinstance(name, str) or not name or name in names:
            return _deny("invalid_snapshot")
        names.add(name)
        if check["conclusion"] != "success" or check["head_sha"] != head:
            return _deny("checks_not_green")

    if type(snapshot["blocking_threads"]) is not int or snapshot["blocking_threads"] < 0:
        return _deny("invalid_snapshot")
    if snapshot["blocking_threads"]:
        return _deny("blocking_threads")
    author, reviews = snapshot["author"], snapshot["reviews"]
    if not isinstance(author, str) or not author or not isinstance(reviews, list):
        return _deny("invalid_snapshot")
    approved = False
    for review in reviews:
        if not isinstance(review, dict) or set(review) != {"author", "state", "head_sha", "trusted"}:
            return _deny("invalid_snapshot")
        if (not isinstance(review["author"], str) or not review["author"]
                or type(review["trusted"]) is not bool or not _sha(review["head_sha"])
                or review["state"] not in {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}):
            return _deny("invalid_snapshot")
        if review["state"] == "CHANGES_REQUESTED":
            return _deny("reviews_blocked")
        if (review["state"] == "APPROVED" and review["trusted"]
                and review["head_sha"] == head
                and review["author"].casefold() != author.casefold()):
            approved = True
    if not approved:
        return _deny("independent_approval_missing")
    return Decision(True, "eligible_diagnostic_only")

