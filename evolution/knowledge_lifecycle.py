"""Lifecycle canónico para conocimiento aprendido y guardrails promovibles."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from typing import Any


KNOWLEDGE_VERSION = 1
STATES = ("candidate", "active", "needs_review", "deprecated", "archived")
EVIDENCE_CLASSES = (
    "single-source",
    "multi-source",
    "reproduced",
    "verified",
)
AUTONOMY_EVIDENCE = frozenset({"reproduced", "verified"})
AUTONOMY_MIN_CONFIDENCE = 0.75
MAX_PROVENANCE = 32
UTC_OFFSET = "+00:00"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
PROJECT_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SOURCE_RE = re.compile(
    r"^(?:https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:issues|pull)/[1-9]\d*"
    r"|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9]\d*)$"
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FIELDS = {
    "version",
    "knowledge_id",
    "knowledge_type",
    "content_fingerprint",
    "provenance",
    "scope",
    "created_at",
    "last_validated_at",
    "last_useful_at",
    "confidence",
    "evidence_class",
    "review_policy",
    "state",
    "history",
}


class KnowledgeLifecycleError(ValueError):
    """Contrato de lifecycle inválido o transición no permitida."""


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise KnowledgeLifecycleError(f"{field} debe ser ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", UTC_OFFSET))
    except ValueError as exc:
        raise KnowledgeLifecycleError(f"{field} debe ser ISO-8601") from exc
    if parsed.tzinfo is None:
        raise KnowledgeLifecycleError(f"{field} debe incluir zona horaria")
    return parsed.astimezone(timezone.utc)


def _text(value: Any, field: str, *, max_len: int = 96) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > max_len
        or "\n" in value
    ):
        raise KnowledgeLifecycleError(f"{field} inválido")
    return value


def _sources(value: Any, field: str = "provenance") -> list[str]:
    if (
        not isinstance(value, (list, tuple))
        or not 1 <= len(value) <= MAX_PROVENANCE
        or not all(isinstance(item, str) and SOURCE_RE.fullmatch(item) for item in value)
    ):
        raise KnowledgeLifecycleError(f"{field} inválida")
    ordered = sorted(set(value))
    if len(ordered) != len(value):
        raise KnowledgeLifecycleError(f"{field} contiene duplicados")
    return ordered


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KnowledgeLifecycleError("confidence debe ser número 0..1")
    number = float(value)
    if not math.isfinite(number) or number < 0 or number > 1:
        raise KnowledgeLifecycleError("confidence debe ser número finito 0..1")
    return number


def _scope(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"project", "domain"}:
        raise KnowledgeLifecycleError("scope debe contener project y domain")
    project = _text(value.get("project"), "scope.project")
    if not PROJECT_RE.fullmatch(project):
        raise KnowledgeLifecycleError("scope.project debe usar owner/repo")
    domain = _text(value.get("domain"), "scope.domain")
    if not ID_RE.fullmatch(domain):
        raise KnowledgeLifecycleError("scope.domain inválido")
    return {"project": project, "domain": domain}


def _review_policy(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {
        "review_after_days",
        "expires_after_days",
    }:
        raise KnowledgeLifecycleError("review_policy inválida")
    review = value["review_after_days"]
    expires = value["expires_after_days"]
    if (
        type(review) is not int
        or type(expires) is not int
        or not 1 <= review < expires <= 3650
    ):
        raise KnowledgeLifecycleError(
            "review_policy requiere 1 <= review_after_days < expires_after_days <= 3650"
        )
    return {
        "review_after_days": review,
        "expires_after_days": expires,
    }


def _history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 128:
        raise KnowledgeLifecycleError("history inválida")
    validated: list[dict[str, Any]] = []
    previous_at: datetime | None = None
    previous_to: str | None = None
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "at", "from", "to", "reason", "evidence"
        }:
            raise KnowledgeLifecycleError("evento de history inválido")
        at = _timestamp(item["at"], "history.at")
        if previous_at is not None and at < previous_at:
            raise KnowledgeLifecycleError("history no es cronológico")
        previous_at = at
        source_state = _text(item["from"], "history.from")
        target_state = _text(item["to"], "history.to")
        if source_state not in STATES or target_state not in STATES:
            raise KnowledgeLifecycleError("estado de history inválido")
        if previous_to is not None and source_state != previous_to:
            raise KnowledgeLifecycleError("history no encadena estados")
        previous_to = target_state
        reason = _text(item["reason"], "history.reason", max_len=120)
        evidence = _sources(item["evidence"], "history.evidence")
        validated.append({
            "at": item["at"],
            "from": source_state,
            "to": target_state,
            "reason": reason,
            "evidence": evidence,
        })
    return validated


def validate_knowledge_record(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != REQUIRED_FIELDS:
        raise KnowledgeLifecycleError("registro de conocimiento con campos inválidos")
    if raw.get("version") != KNOWLEDGE_VERSION:
        raise KnowledgeLifecycleError("version de conocimiento no soportada")

    knowledge_id = _text(raw.get("knowledge_id"), "knowledge_id")
    if not ID_RE.fullmatch(knowledge_id):
        raise KnowledgeLifecycleError("knowledge_id inválido")
    knowledge_type = _text(raw.get("knowledge_type"), "knowledge_type")
    if not ID_RE.fullmatch(knowledge_type):
        raise KnowledgeLifecycleError("knowledge_type inválido")

    fingerprint = raw.get("content_fingerprint")
    if not isinstance(fingerprint, str) or not HEX64_RE.fullmatch(fingerprint):
        raise KnowledgeLifecycleError("content_fingerprint inválido")

    created = _timestamp(raw.get("created_at"), "created_at")
    validated_at = _timestamp(raw.get("last_validated_at"), "last_validated_at")
    useful_at = _timestamp(raw.get("last_useful_at"), "last_useful_at")
    if validated_at < created or useful_at < created:
        raise KnowledgeLifecycleError("timestamps de conocimiento regresivos")

    evidence_class = raw.get("evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        raise KnowledgeLifecycleError("evidence_class inválida")
    state = raw.get("state")
    if state not in STATES:
        raise KnowledgeLifecycleError("state inválido")

    history = _history(raw.get("history"))
    if history:
        if _timestamp(history[0]["at"], "history.at") < created:
            raise KnowledgeLifecycleError("history anterior a created_at")
        if history[-1]["to"] != state:
            raise KnowledgeLifecycleError("history no coincide con state")

    return {
        "version": KNOWLEDGE_VERSION,
        "knowledge_id": knowledge_id,
        "knowledge_type": knowledge_type,
        "content_fingerprint": fingerprint,
        "provenance": _sources(raw.get("provenance")),
        "scope": _scope(raw.get("scope")),
        "created_at": raw["created_at"],
        "last_validated_at": raw["last_validated_at"],
        "last_useful_at": raw["last_useful_at"],
        "confidence": _confidence(raw.get("confidence")),
        "evidence_class": evidence_class,
        "review_policy": _review_policy(raw.get("review_policy")),
        "state": state,
        "history": history,
    }


def create_knowledge_record(
    *,
    knowledge_id: str,
    knowledge_type: str,
    content_fingerprint: str,
    provenance: list[str],
    project: str,
    domain: str,
    created_at: str,
    last_validated_at: str,
    last_useful_at: str,
    confidence: float,
    evidence_class: str,
    review_after_days: int,
    expires_after_days: int,
    state: str = "candidate",
) -> dict[str, Any]:
    return validate_knowledge_record({
        "version": KNOWLEDGE_VERSION,
        "knowledge_id": knowledge_id,
        "knowledge_type": knowledge_type,
        "content_fingerprint": content_fingerprint,
        "provenance": provenance,
        "scope": {"project": project, "domain": domain},
        "created_at": created_at,
        "last_validated_at": last_validated_at,
        "last_useful_at": last_useful_at,
        "confidence": confidence,
        "evidence_class": evidence_class,
        "review_policy": {
            "review_after_days": review_after_days,
            "expires_after_days": expires_after_days,
        },
        "state": state,
        "history": [],
    })


def effective_state(raw: Any, now_at: str) -> str:
    record = validate_knowledge_record(raw)
    now = _timestamp(now_at, "now_at")
    if now < _timestamp(record["created_at"], "created_at"):
        raise KnowledgeLifecycleError("now_at anterior a created_at")
    if record["state"] != "active":
        return record["state"]

    age = now - _timestamp(record["last_validated_at"], "last_validated_at")
    review_days = record["review_policy"]["review_after_days"]
    expires_days = record["review_policy"]["expires_after_days"]
    if age.days >= expires_days or age.days >= review_days:
        return "needs_review"
    return "active"


def can_increase_autonomy(raw: Any, now_at: str) -> bool:
    record = validate_knowledge_record(raw)
    return (
        effective_state(record, now_at) == "active"
        and record["evidence_class"] in AUTONOMY_EVIDENCE
        and record["confidence"] >= AUTONOMY_MIN_CONFIDENCE
    )


def revalidate_knowledge(
    raw: Any,
    *,
    validated_at: str,
    evidence: list[str],
    confidence: float,
    evidence_class: str,
) -> dict[str, Any]:
    record = validate_knowledge_record(raw)
    at = _timestamp(validated_at, "validated_at")
    if at < _timestamp(record["last_validated_at"], "last_validated_at"):
        raise KnowledgeLifecycleError("revalidación anterior a last_validated_at")
    if evidence_class not in EVIDENCE_CLASSES:
        raise KnowledgeLifecycleError("evidence_class inválida")
    new_sources = _sources(evidence, "revalidation.evidence")
    source_state = effective_state(record, validated_at)
    if source_state in {"deprecated", "archived"}:
        raise KnowledgeLifecycleError("conocimiento retirado no se reactiva por revalidación")

    updated = deepcopy(record)
    if source_state == "needs_review" and record["state"] == "active":
        updated["history"].append({
            "at": validated_at,
            "from": "active",
            "to": "needs_review",
            "reason": "review-window-expired",
            "evidence": new_sources,
        })
    updated["provenance"] = sorted(set(record["provenance"]) | set(new_sources))
    updated["last_validated_at"] = validated_at
    updated["last_useful_at"] = validated_at
    updated["confidence"] = _confidence(confidence)
    updated["evidence_class"] = evidence_class
    updated["state"] = "active"
    updated["history"].append({
        "at": validated_at,
        "from": source_state,
        "to": "active",
        "reason": "revalidated",
        "evidence": new_sources,
    })
    return validate_knowledge_record(updated)


def transition_knowledge(
    raw: Any,
    *,
    target_state: str,
    at: str,
    evidence: list[str],
    reason: str,
) -> dict[str, Any]:
    record = validate_knowledge_record(raw)
    source_state = effective_state(record, at)
    allowed = {
        "candidate": {"deprecated"},
        "active": {"deprecated"},
        "needs_review": {"deprecated"},
        "deprecated": {"archived"},
        "archived": set(),
    }
    if target_state not in allowed[source_state]:
        raise KnowledgeLifecycleError(
            f"transición no permitida: {source_state} -> {target_state}"
        )
    if _timestamp(at, "at") < _timestamp(record["created_at"], "created_at"):
        raise KnowledgeLifecycleError("transición anterior a created_at")

    transition_evidence = _sources(evidence, "transition.evidence")
    updated = deepcopy(record)
    if source_state == "needs_review" and record["state"] == "active":
        updated["history"].append({
            "at": at,
            "from": "active",
            "to": "needs_review",
            "reason": "review-window-expired",
            "evidence": transition_evidence,
        })
    updated["state"] = target_state
    updated["history"].append({
        "at": at,
        "from": source_state,
        "to": target_state,
        "reason": _text(reason, "reason", max_len=120),
        "evidence": transition_evidence,
    })
    return validate_knowledge_record(updated)


def propose_pruning_candidates(records: Any, *, now_at: str) -> list[dict[str, Any]]:
    if not isinstance(records, (list, tuple)) or not records:
        raise KnowledgeLifecycleError("records debe ser lista no vacía")
    now = _timestamp(now_at, "now_at")
    validated = [validate_knowledge_record(item) for item in records]
    ids = [item["knowledge_id"] for item in validated]
    if len(ids) != len(set(ids)):
        raise KnowledgeLifecycleError("knowledge_id duplicado")

    by_fingerprint: dict[str, list[str]] = {}
    for item in validated:
        by_fingerprint.setdefault(item["content_fingerprint"], []).append(
            item["knowledge_id"]
        )

    proposals: list[dict[str, Any]] = []
    for item in validated:
        reasons: set[str] = set()
        peers = sorted(by_fingerprint[item["content_fingerprint"]])
        if len(peers) > 1:
            reasons.add("duplicate")

        useful_age = now - _timestamp(item["last_useful_at"], "last_useful_at")
        validated_age = now - _timestamp(
            item["last_validated_at"], "last_validated_at"
        )
        policy = item["review_policy"]
        if useful_age.days >= policy["expires_after_days"]:
            reasons.add("unused")
        if (
            validated_age.days >= policy["review_after_days"]
            or effective_state(item, now_at) in {"needs_review", "deprecated"}
        ):
            reasons.add("aged")

        if reasons:
            proposal_ids = peers if "duplicate" in reasons else [item["knowledge_id"]]
            proposals.append({
                "version": KNOWLEDGE_VERSION,
                "proposal_id": f"knowledge-prune-{proposal_ids[0]}",
                "knowledge_ids": proposal_ids,
                "action": (
                    "review-consolidation"
                    if "duplicate" in reasons
                    else "review-retirement"
                ),
                "reasons": sorted(reasons),
                "delete": False,
                "history_preserved": True,
                "generated_at": now_at,
            })

    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for proposal in proposals:
        key = tuple(proposal["knowledge_ids"])
        current = unique.get(key)
        if current is None:
            unique[key] = proposal
            continue
        current["reasons"] = sorted(
            set(current["reasons"]) | set(proposal["reasons"])
        )
    return sorted(unique.values(), key=lambda item: item["proposal_id"])
