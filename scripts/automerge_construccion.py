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
    "owner_waiver", "reservation", "review_bot",
})
REQUIRED_CHECKS = frozenset({
    "CI factory", "Sonar CI-based", "Evidencia CodeQL",
    "CodeRabbit", "Criterios de aceptación", "Validar coordinación", "Seguridad",
})
WAIVER_SOURCE = ("pl0n3r/Factory", 1139, 6107503429, "pl0n3r")
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
SENSITIVE = ("release", "ruleset", "security", "seguridad", "politica", "política", "policy",
             "secrets", "puertas-humanas", "production", "deploy")
SENSITIVE_PREFIXES = (".github/", "config/", "credentials/", "agentes/roles/",
                      "template/.github/", "template/config/",
                      "template/credentials/", "template/agentes/")
SENSITIVE_FILES = frozenset({"scripts/coordinar_trabajo.py", "scripts/orquestar_fabrica.py",
                             "scripts/aceptacion_kit.py", "scripts/validar_claims_issue.py",
                             "scripts/automerge_construccion.py",
                             "scripts/unattended_kill_switch.py",
                             "codeowners", "docs/codeowners",
                             "template/agentes.md", "template/agents.md",
                             "template/plan-agentes.md",
                             "docs/principios-construccion.md",
                             "docs/unattended-safe-mode.md",
                             "decisiones.yml", "agentes/nucleo.md",
                             "template/decisiones.yml"})


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
    if type(paths) is not list or not paths or len(paths) > 128:
        return "invalid_snapshot"
    seen: set[str] = set()
    for path in paths:
        if (type(path) is not str or not path or len(path) > 240
                or path != path.strip() or "\\" in path
                or path.startswith(("/", "~"))
                or any(ord(char) < 32 or ord(char) == 127 for char in path)
                or any(part in ("", ".", "..") for part in path.split("/"))):
            return "invalid_snapshot"
        normalized = path.casefold()
        if normalized in seen:
            return "invalid_snapshot"
        seen.add(normalized)
        if (any(word in normalized for word in SENSITIVE)
                or any(normalized.startswith(prefix) for prefix in SENSITIVE_PREFIXES)
                or normalized in SENSITIVE_FILES
                or normalized in {"agents.md", "agentes.md", "plan-agentes.md", "datos.yml"}
                or normalized.startswith(".github/codeowners")):
            return "sensitive_paths"
    return "ok"



def _reservation_status(value: Any, head: str, now: datetime, paths: list[str]) -> str:
    """Valida el contrato del dato atestado por el caller, no llama GitHub."""
    expected = {"version", "active", "source", "reservation_id", "owner",
                "branch", "head_sha", "verified_at", "expires_at",
                "issue_number", "task_paths"}
    if not isinstance(value, dict) or set(value) != expected:
        return "incomplete_evidence"
    if (type(value["version"]) is not int or value["version"] != 3
            or type(value["active"]) is not bool or not value["active"]
            or value["source"] != "verified_github_issue_comment"
            or value["owner"] != "pl0n3r"
            or not isinstance(value["reservation_id"], str)
            or UUID.fullmatch(value["reservation_id"]) is None
            or not isinstance(value["branch"], str)
            or type(value["issue_number"]) is not int
            or value["issue_number"] < 1
            or value["branch"] != f'trabajo/issue-{value["issue_number"]}'
            or type(value["task_paths"]) is not list
            or value["task_paths"] != paths
            or value["head_sha"] != head):
        return "incomplete_evidence"
    verified, until = _utc(value["verified_at"]), _utc(value["expires_at"])
    if (verified is None or until is None or not (verified <= now <= until)
            or until - verified > timedelta(minutes=5)
            or until == verified):
        return "stale_evidence"
    return "ok"


def _review_bot_status(value: Any, head: str) -> str:
    expected = {"provider", "result", "head_sha", "final_review",
                "blocking_findings", "trusted"}
    if not isinstance(value, dict) or set(value) != expected:
        return "incomplete_evidence"
    if (value["provider"] != "coderabbitai[bot]"
            or value["result"] != "success"
            or value["head_sha"] != head
            or value["final_review"] != "complete"
            or type(value["blocking_findings"]) is not int
            or value["blocking_findings"] != 0
            or type(value["trusted"]) is not bool or not value["trusted"]):
        return "reviews_blocked"
    return "ok"


def _waiver_status(value: Any, head: str, now: datetime) -> str:
    """Pin de decisión pública; la autenticidad REST se valida fuera de este motor.

    Un snapshot autocertificado NO autoriza fusión: salida es sólo diagnóstica.
    """
    expected = {"source", "repo", "issue", "comment_id", "author",
                "scope", "verified_at", "expires_at", "head_sha",
                "mvp_declared", "verification"}
    if not isinstance(value, dict) or set(value) != expected:
        return "independent_approval_missing"
    if ((value["repo"], value["issue"], value["comment_id"], value["author"])
            != WAIVER_SOURCE
            or value["source"] != "github_issue_comment"
            or value["verification"] != "authenticated_github_rest"
            or value["scope"] != "construccion"
            or value["head_sha"] != head
            or type(value["mvp_declared"]) is not bool
            or value["mvp_declared"]):
        return "independent_approval_missing"
    verified, until = _utc(value["verified_at"]), _utc(value["expires_at"])
    if (verified is None or until is None or not (verified <= now <= until)
            or until - verified > timedelta(minutes=5)
            or until == verified):
        return "stale_evidence"
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

    reservation_status = _reservation_status(snapshot["reservation"], head, now,
                                             snapshot["paths"])
    if reservation_status != "ok":
        return _deny(reservation_status)
    review_bot_status = _review_bot_status(snapshot["review_bot"], head)
    if review_bot_status != "ok":
        return _deny(review_bot_status)

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
    if len(checks) > 128:
        return _deny("invalid_snapshot")
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

    if not REQUIRED_CHECKS.issubset(names):
        return _deny("incomplete_evidence")

    if type(snapshot["blocking_threads"]) is not int or snapshot["blocking_threads"] < 0:
        return _deny("invalid_snapshot")
    if snapshot["blocking_threads"]:
        return _deny("blocking_threads")
    author, reviews = snapshot["author"], snapshot["reviews"]
    if (not isinstance(author, str) or not author or not isinstance(reviews, list)
            or len(reviews) > 128):
        return _deny("invalid_snapshot")
    # Solo un estado efectivo por revisor. Si llegan filas históricas duplicadas,
    # no existe una cronología confiable en este snapshot: denegar, nunca reaprobar.
    effective_reviewers: set[str] = set()
    approved = False
    for review in reviews:
        if not isinstance(review, dict) or set(review) != {"author", "state", "head_sha", "trusted"}:
            return _deny("invalid_snapshot")
        if (not isinstance(review["author"], str) or not review["author"]
                or type(review["trusted"]) is not bool or not _sha(review["head_sha"])
                or not isinstance(review["state"], str)
                or review["state"] not in {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}):
            return _deny("invalid_snapshot")
        reviewer = review["author"].casefold()
        if reviewer in effective_reviewers:
            return _deny("invalid_snapshot")
        effective_reviewers.add(reviewer)
        if review["state"] == "CHANGES_REQUESTED":
            return _deny("reviews_blocked")
        if (review["state"] == "APPROVED" and review["trusted"]
                and review["head_sha"] == head
                and reviewer != author.casefold()):
            approved = True
    if not approved:
        waiver_status = _waiver_status(snapshot["owner_waiver"], head, now)
        if waiver_status != "ok":
            return _deny(waiver_status)
        if any(review["state"] == "DISMISSED" for review in reviews):
            return _deny("reviews_blocked")
    return Decision(True, "eligible_diagnostic_only")

