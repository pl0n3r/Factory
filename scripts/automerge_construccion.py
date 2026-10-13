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
    "quality_evidence", "quality_findings", "hard_gates", "commit_count",
    "review_rounds", "quality_debt_cleared_for_live",
})
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


def evaluate(snapshot: Any) -> Decision:
    """Evalúa evidencia sintética no confiable; *eligible* solo es diagnóstico."""
    if not isinstance(snapshot, dict):
        return _deny("invalid_snapshot")
    if set(snapshot) != FIELDS:
        # El workflow observador legado sigue siendo explícitamente no autorizado:
        # fase UNKNOWN + freeze/human gate activos. Nunca acepta campos incompletos
        # para emitir un resultado eligible, ni infiere evidencia de calidad ausente.
        legacy_missing = {
            "quality_evidence", "quality_findings", "hard_gates",
            "commit_count", "review_rounds", "quality_debt_cleared_for_live",
        }
        if (set(snapshot) == FIELDS - legacy_missing
                and snapshot.get("phase") == "UNKNOWN"
                and snapshot.get("freeze_active") is True
                and snapshot.get("human_gate_required") is True):
            return _deny("human_gate_required")
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
    hard = snapshot["hard_gates"]
    required_hard = {"spend", "real_data", "deploy", "release", "move_v1",
                     "go_live", "destructive", "reservation_v3", "branch_protection"}
    if not isinstance(hard, dict) or set(hard) != required_hard:
        return _deny("incomplete_evidence")
    if any(type(value) is not bool for value in hard.values()):
        return _deny("invalid_snapshot")
    if any(hard[name] for name in required_hard - {"reservation_v3", "branch_protection"}):
        return _deny("human_gate_required")
    if not hard["reservation_v3"] or not hard["branch_protection"]:
        return _deny("human_gate_required")
    if type(snapshot["quality_debt_cleared_for_live"]) is not bool:
        return _deny("invalid_snapshot")
    for field in ("commit_count", "review_rounds"):
        if type(snapshot[field]) is not int or snapshot[field] < 0:
            return _deny("invalid_snapshot")
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
    for name, gate in gates.items():
        if not isinstance(gate, dict) or set(gate) != {"conclusion", "head_sha"}:
            return _deny("invalid_snapshot")
        if gate["head_sha"] != head or type(gate["conclusion"]) is not str or gate["conclusion"] not in {
                "success", "failure", "pending", "cancelled", "skipped"}:
            return _deny("invalid_snapshot")
        # Aceptación y coordinación quedan registradas, pero no vetan el diagnóstico.
        if name == "security" and gate["conclusion"] != "success":
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
        if check["head_sha"] != head or type(check["conclusion"]) is not str or check["conclusion"] not in {
                "success", "failure", "pending", "cancelled", "skipped"}:
            return _deny("invalid_snapshot")
        # Toda señal esencial presente (CI, tests, lint o build) debe ser verde.
        # No permitir snapshots contradictorios con Validar=success y lint rojo.
        if name.casefold() in {"validar", "validate", "tests de scripts", "tests",
                               "lint de workflows", "lint", "build", "build del producto"} and check["conclusion"] != "success":
            return _deny("checks_not_green")
    if not (names & {"Validar", "validate"}):
        return _deny("incomplete_evidence")

    quality = snapshot["quality_evidence"]
    if type(quality) is not list or len(quality) != 3:
        return _deny("incomplete_evidence")
    sources: set[str] = set()
    for item in quality:
        if (type(item) is not dict or set(item) != {"source", "head_sha", "complete"}
                or type(item["source"]) is not str
                or item["source"] not in {"sonarcloud", "codeql", "coderabbit"}
                or item["source"] in sources or not _sha(item["head_sha"])
                or type(item["complete"]) is not bool):
            return _deny("invalid_snapshot")
        if not item["complete"] or item["head_sha"] != head:
            return _deny("incomplete_evidence")
        sources.add(item["source"])
    if sources != {"sonarcloud", "codeql", "coderabbit"}:
        return _deny("incomplete_evidence")
    findings = snapshot["quality_findings"]
    if type(findings) is not list or len(findings) > 128:
        return _deny("invalid_snapshot")
    for finding in findings:
        if (type(finding) is not dict
                or set(finding) != {"source", "severity", "category", "on_new_code", "open"}
                or type(finding["source"]) is not str
                or finding["source"] not in sources
                or type(finding["severity"]) is not str
                or finding["severity"] not in {"critical", "high", "medium", "low", "info"}
                or type(finding["category"]) is not str
                or finding["category"] not in {"security", "bug", "reliability", "code_smell"}
                or type(finding["on_new_code"]) is not bool
                or type(finding["open"]) is not bool):
            return _deny("invalid_snapshot")
        if (finding["open"] and finding["on_new_code"]
                and finding["severity"] in {"critical", "high"}
                and finding["category"] in {"security", "bug", "reliability"}):
            return _deny("severe_quality_finding")

    if type(snapshot["blocking_threads"]) is not int or snapshot["blocking_threads"] < 0:
        return _deny("invalid_snapshot")
    # Hilos y solicitudes de cambios no graves son deuda/feedback, no veto de merge.
    author, reviews = snapshot["author"], snapshot["reviews"]
    if (not isinstance(author, str) or not author or not isinstance(reviews, list)
            or len(reviews) > 128):
        return _deny("invalid_snapshot")
    # Solo un estado efectivo por revisor. Si llegan filas históricas duplicadas,
    # no existe una cronología confiable en este snapshot: denegar, nunca reaprobar.
    effective_reviewers: set[str] = set()
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
        # La revisión se conserva para auditoría; un hallazgo grave se expresa
        # en quality_findings y nunca puede ser neutralizado con APPROVED.
    return Decision(True, "eligible_diagnostic_only")

