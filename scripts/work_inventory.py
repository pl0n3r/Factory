#!/usr/bin/env python3
"""Inventario canónico y puro del trabajo restante de la fábrica."""
from __future__ import annotations
from typing import Any, Iterable, Mapping

CANONICAL_REPOSITORIES = (
    "pl0n3r/Factory", "pl0n3r/Condor", "pl0n3r/GrindFlow", "pl0n3r/brvtal",
    "pl0n3r/ControlBot", "pl0n3r/AutoFactory", "pl0n3r/FactoryRunner",
)
PROJECT_STATES = frozenset({
    "READY", "ALL_BLOCKED", "UNMATERIALIZED_WORK",
    "WAITING_DECISION", "LIVE_GATED", "NO_WORK",
})
NARRATIVE_CLASSES = frozenset({
    "leaf_ready", "leaf_blocked", "decision_required",
    "live_only", "future_idea", "already_materialized",
})
EXECUTABLE_NARRATIVE = frozenset({"leaf_ready", "leaf_blocked"})


def _rows(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(item) for item in items]
    if any(not str(row.get("evidence_ref") or "").strip() for row in rows):
        raise ValueError("every inventory item requires evidence_ref")
    return rows


def detect_unmaterialized_executable_work(
    narrative: Iterable[Mapping[str, Any]],
    leaves: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    leaf_rows = _rows(leaves)
    seen = {str(row.get("source_key") or row.get("key") or "") for row in leaf_rows}
    result = []
    for row in _rows(narrative):
        classification = row.get("classification")
        if classification not in NARRATIVE_CLASSES:
            raise ValueError("unknown narrative classification")
        key = str(row.get("source_key") or "")
        if classification in EXECUTABLE_NARRATIVE and key and key not in seen:
            result.append(row)
            seen.add(key)
    return result


def classify_project_state(
    leaves: Iterable[Mapping[str, Any]],
    narrative: Iterable[Mapping[str, Any]],
) -> str:
    leaf_rows, narrative_rows = _rows(leaves), _rows(narrative)
    statuses = {row.get("status") for row in leaf_rows}
    if statuses & {"available", "reserved"}:
        return "READY"
    if detect_unmaterialized_executable_work(narrative_rows, leaf_rows):
        return "UNMATERIALIZED_WORK"
    classes = {row.get("classification") for row in narrative_rows}
    if "decision_required" in classes:
        return "WAITING_DECISION"
    if "live_only" in classes:
        return "LIVE_GATED"
    if "blocked" in statuses:
        return "ALL_BLOCKED"
    return "NO_WORK"


def remaining_work_summary(
    repository_ref: str,
    leaves: Iterable[Mapping[str, Any]],
    narrative: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    if repository_ref not in CANONICAL_REPOSITORIES:
        raise ValueError("repository is not in the canonical dispatch set")
    leaf_rows, narrative_rows = _rows(leaves), _rows(narrative)
    hidden = detect_unmaterialized_executable_work(narrative_rows, leaf_rows)
    state = classify_project_state(leaf_rows, narrative_rows)
    counts = {name: sum(row.get("status") == name for row in leaf_rows)
              for name in ("completed", "available", "reserved", "blocked")}
    counts.update({
        "decision_required": sum(row.get("classification") == "decision_required" for row in narrative_rows),
        "live_only": sum(row.get("classification") == "live_only" for row in narrative_rows),
        "future_idea": sum(row.get("classification") == "future_idea" for row in narrative_rows),
        "unmaterialized": len(hidden),
    })
    order = ([row for status in ("available", "reserved") for row in leaf_rows if row.get("status") == status]
             + hidden
             + [row for cls in ("decision_required", "live_only") for row in narrative_rows if row.get("classification") == cls]
             + [row for row in leaf_rows if row.get("status") == "blocked"])
    next_work = None if not order else str(order[0].get("key") or order[0].get("source_key") or "")
    evidence = sorted({str(row["evidence_ref"]) for row in leaf_rows + narrative_rows})
    return {"repository_ref": repository_ref, "state": state, "counts": counts,
            "next_work": next_work, "evidence_refs": evidence}


def initial_sweep_artifact(
    projects: Mapping[str, Mapping[str, Iterable[Mapping[str, Any]]]],
    observed_at: str,
) -> dict[str, Any]:
    if set(projects) != set(CANONICAL_REPOSITORIES) or not observed_at.strip():
        raise ValueError("initial sweep must cover the seven canonical repositories")
    summaries = {}
    for repo in CANONICAL_REPOSITORIES:
        payload = projects[repo]
        summaries[repo] = remaining_work_summary(
            repo, payload.get("leaves", ()), payload.get("narrative", ())
        )
    return {"version": 1, "observed_at": observed_at, "projects": summaries}


def controlbot_projection(artifact: Mapping[str, Any]) -> dict[str, Any]:
    if artifact.get("version") != 1 or set(artifact.get("projects", {})) != set(CANONICAL_REPOSITORIES):
        raise ValueError("invalid canonical inventory artifact")
    return {"version": 1, "observed_at": artifact["observed_at"],
            "projects": artifact["projects"]}


def parent_progress(leaves: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    rows = _rows(leaves)
    completed = sum(row.get("status") == "completed" for row in rows)
    return {"completed": completed, "total": len(rows),
            "percent": 100 if not rows else completed * 100 // len(rows)}
