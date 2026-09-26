"""Definition-of-Done Compiler: evidencia dinámica y verificable por cambio."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence.project_dna import UNKNOWN, validate_project_dna


DOD_VERSION = 1

FACTORY_INVARIANTS = (
    {"kind": "check", "target": "ci:required"},
    {"kind": "check", "target": "reviews:no-open-findings"},
    {"kind": "check", "target": "scope:claimed-paths-only"},
)

CHANGE_PROFILES = {
    "code": (
        {"kind": "test", "target": "tests:changed-scope"},
        {"kind": "check", "target": "static:analysis"},
    ),
    "database": (
        {"kind": "check", "target": "migration:verify-plan"},
        {"kind": "check", "target": "backup:evidence"},
        {"kind": "test", "target": "schema:compatibility"},
    ),
    "ci": (
        {"kind": "check", "target": "workflow:validation"},
        {"kind": "check", "target": "workflow:representative-run"},
    ),
    "docs": (
        {"kind": "check", "target": "docs:lint"},
        {"kind": "check", "target": "docs:links"},
    ),
    "security": (
        {"kind": "check", "target": "security:scan"},
        {"kind": "test", "target": "security:negative-cases"},
    ),
}

SURFACE_PROFILES = {
    "api": ({"kind": "test", "target": "api:contract"},),
    "web": ({"kind": "test", "target": "web:smoke"},),
    "database": ({"kind": "check", "target": "migration:verify-plan"},),
    "ci": ({"kind": "check", "target": "workflow:representative-run"},),
    "release": ({"kind": "check", "target": "release:exact-sha"},),
}

RISK_PROFILES = {
    "low": (),
    "medium": (
        {"kind": "check", "target": "rollback:plan"},
    ),
    "high": (
        {"kind": "check", "target": "rollback:plan"},
        {"kind": "check", "target": "security:scan"},
        {"kind": "check", "target": "smoke:exact-sha"},
    ),
}

SAFE_FALLBACK = (
    {"kind": "test", "target": "tests:full-suite"},
    {"kind": "check", "target": "static:analysis"},
    {"kind": "check", "target": "security:scan"},
    {"kind": "check", "target": "rollback:plan"},
    {"kind": "check", "target": "context:complete-before-promotion"},
)


class DodCompilerError(ValueError):
    """Entrada no válida para compilar Definition of Done."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalized_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        raise DodCompilerError(f"{field} debe ser colección")
    normalized = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise DodCompilerError(f"{field} contiene valor inválido")
        normalized.append(item.strip().lower())
    return sorted(set(normalized))


def _task_contract(task: Any) -> dict[str, Any]:
    expected = {"id", "title", "change_type", "surfaces", "risk"}
    if not isinstance(task, dict) or set(task) != expected:
        raise DodCompilerError("task inválida")
    for field in ("id", "title", "change_type", "risk"):
        if not isinstance(task[field], str) or not task[field].strip():
            raise DodCompilerError(f"task.{field} inválido")

    change_type = task["change_type"].strip().lower()
    risk = task["risk"].strip().lower()
    if change_type not in CHANGE_PROFILES and change_type != UNKNOWN:
        raise DodCompilerError("change_type no admitido")
    if risk not in RISK_PROFILES and risk != UNKNOWN:
        raise DodCompilerError("risk no admitido")

    return {
        "id": task["id"].strip(),
        "title": task["title"].strip(),
        "change_type": change_type,
        "surfaces": _normalized_strings(task["surfaces"], "task.surfaces"),
        "risk": risk,
    }


def _has_unknown_dna(dna: dict[str, Any]) -> bool:
    fields = (
        "stack",
        "frameworks",
        "data",
        "ci",
        "hosting",
        "integrations",
        "capabilities",
    )
    return any(dna[field] == UNKNOWN for field in fields)


def _evidence_key(item: dict[str, str]) -> tuple[str, str]:
    return item["kind"], item["target"]


def _machine_verifiable(item: dict[str, str]) -> bool:
    return (
        set(item) == {"kind", "target"}
        and item["kind"] in {"test", "check"}
        and isinstance(item["target"], str)
        and ":" in item["target"]
        and not item["target"].endswith(":")
    )


def compile_done_contract(*, project_dna: Any, task: Any) -> dict[str, Any]:
    """Deriva evidencia requerida sin debilitar el estándar ante unknown."""
    dna = validate_project_dna(project_dna)
    normalized_task = _task_contract(task)

    evidence = list(FACTORY_INVARIANTS)
    incomplete_context = (
        normalized_task["change_type"] == UNKNOWN
        or normalized_task["risk"] == UNKNOWN
        or not normalized_task["surfaces"]
        or _has_unknown_dna(dna)
    )

    if incomplete_context:
        evidence.extend(SAFE_FALLBACK)
        profile = "safe-fallback"
    else:
        evidence.extend(CHANGE_PROFILES[normalized_task["change_type"]])
        evidence.extend(RISK_PROFILES[normalized_task["risk"]])
        for surface in normalized_task["surfaces"]:
            evidence.extend(
                SURFACE_PROFILES.get(
                    surface,
                    ({"kind": "check", "target": f"surface:{surface}"},),
                )
            )
        profile = "derived"

    deduped = {
        _evidence_key(item): {"kind": item["kind"], "target": item["target"]}
        for item in evidence
    }
    ordered = [deduped[key] for key in sorted(deduped)]

    if not all(_machine_verifiable(item) for item in ordered):
        raise DodCompilerError("evidencia no verificable por máquina")

    contract = {
        "version": DOD_VERSION,
        "task_id": normalized_task["id"],
        "profile": profile,
        "context_complete": not incomplete_context,
        "change_type": normalized_task["change_type"],
        "surfaces": normalized_task["surfaces"],
        "risk": normalized_task["risk"],
        "invariants": [dict(item) for item in FACTORY_INVARIANTS],
        "evidence": ordered,
        "project_dna_fingerprint": dna["fingerprint"],
    }
    contract["fingerprint"] = _stable_hash(contract)
    return contract
