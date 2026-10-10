#!/usr/bin/env python3
"""Diagnóstico puro de runway de la cola. Sin GitHub/API, red ni escrituras."""
from __future__ import annotations

REPOSITORIES = (
    "Factory", "Condor", "GrindFlow", "brvtal", "ControlBot",
    "AutoFactory", "FactoryRunner",
)
STATES = ("available", "reserved", "blocked", "planned", "in_review")
CAUSES = frozenset(("dependency", "claims", "human_gate", "planned", "unknown"))
MAX_ISSUES = 10000
MAX_CANDIDATES = 32


class QueueHealthError(ValueError):
    """Inventario insuficiente o no confiable; nunca incluir valores externos."""


def _exact(value: object, keys: set[str]) -> bool:
    return type(value) is dict and set(value) == keys


def _integer(value: object, high: int, *, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= high


def diagnose_queue(snapshot: object) -> dict:
    """Clasifica un inventario cerrado; el caller obtiene la evidencia remota.

    Nunca concede reservas, permisos, actividad de agentes ni producción GREEN.
    Un report parcial/ambiguo produce QueueHealthError, no 'cola sana'.
    """
    if not _exact(snapshot, {"version", "repositories", "agent_capacity", "rate_limit"}):
        raise QueueHealthError("invalid_snapshot")
    if type(snapshot["version"]) is not int or snapshot["version"] != 1:
        raise QueueHealthError("invalid_version")
    budget = snapshot["rate_limit"]
    if not _exact(budget, {"limit", "remaining"}) or not _integer(
        budget["limit"], 100000000, minimum=1
    ) or not _integer(budget["remaining"], budget["limit"]):
        raise QueueHealthError("invalid_rate_limit")
    capacity = snapshot["agent_capacity"]
    if capacity is not None and not _integer(capacity, 1000):
        raise QueueHealthError("invalid_capacity")
    rows = snapshot["repositories"]
    if type(rows) is not list or len(rows) != len(REPOSITORIES):
        raise QueueHealthError("incomplete_inventory")

    seen_repos: set[str] = set()
    by_repo: dict[str, dict] = {}
    candidates: list[dict] = []
    reported_blockers = 0
    for row in rows:
        if not _exact(row, {"name", "complete", "open_issues", "counts", "blockers"}):
            raise QueueHealthError("invalid_repository")
        name = row["name"]
        if type(name) is not str or name not in REPOSITORIES or name in seen_repos:
            raise QueueHealthError("duplicate_or_unknown_repository")
        seen_repos.add(name)
        if row["complete"] is not True or not _integer(row["open_issues"], MAX_ISSUES):
            raise QueueHealthError("incomplete_inventory")
        counts = row["counts"]
        if not _exact(counts, set(STATES)) or not all(
            _integer(counts[key], MAX_ISSUES) for key in STATES
        ) or sum(counts.values()) != row["open_issues"]:
            raise QueueHealthError("uncounted_issues")
        blockers = row["blockers"]
        if type(blockers) is not list or len(blockers) != counts["blocked"]:
            raise QueueHealthError("incomplete_blockers")
        reported_blockers += len(blockers)
        if reported_blockers > MAX_ISSUES:
            raise QueueHealthError("blocker_report_too_large")
        seen_issues: set[int] = set()
        safe_blockers: list[dict] = []
        cause_counts = {cause: 0 for cause in sorted(CAUSES)}
        for blocked in blockers:
            if not _exact(blocked, {"number", "cause", "roadmap"}):
                raise QueueHealthError("invalid_blocker")
            n, cause, roadmap = blocked["number"], blocked["cause"], blocked["roadmap"]
            if (not _integer(n, 100000000, minimum=1) or n in seen_issues
                    or type(cause) is not str or cause not in CAUSES
                    or type(roadmap) is not bool):
                raise QueueHealthError("invalid_blocker")
            seen_issues.add(n)
            cause_counts[cause] += 1
            safe_blockers.append({"issue": n, "cause": cause, "roadmap": roadmap})
            # A human decision or UNKNOWN is evidence, never an executable leaf.
            if roadmap and cause not in ("human_gate", "unknown"):
                candidates.append({"repository": name, "issue": n, "cause": cause})
        by_repo[name] = {
            "open_issues": row["open_issues"],
            "counts": {state: counts[state] for state in STATES},
            "blocked_reasons": sorted(safe_blockers, key=lambda entry: entry["issue"]),
            "blocked_cause_counts": cause_counts,
        }

    if seen_repos != set(REPOSITORIES):
        raise QueueHealthError("incomplete_inventory")
    total_available = sum(r["counts"]["available"] for r in by_repo.values())
    total_open = sum(r["open_issues"] for r in by_repo.values())
    total_causes = {
        cause: sum(by_repo[name]["blocked_cause_counts"][cause] for name in REPOSITORIES)
        for cause in sorted(CAUSES)
    }
    # Multiplication rather than float avoids truncation at the 20% threshold.
    if budget["remaining"] * 5 < budget["limit"]:
        state = "budget_deferred"
    elif total_available == 0:
        state = "queue_empty"
    elif capacity is None:
        state = "unknown_capacity"
    elif total_available < capacity:
        state = "below_capacity"
    else:
        state = "healthy"

    reason = {
        "budget_deferred": "rate_limit_below_20_percent",
        "queue_empty": "zero_available",
        "unknown_capacity": "capacity_not_observed",
        "below_capacity": "fewer_ready_than_capacity",
        "healthy": "reported_capacity_sufficient",
    }[state]

    sorted_candidates = sorted(
        candidates, key=lambda x: (REPOSITORIES.index(x["repository"]), x["issue"])
    )
    # During budget deferral there is no grounded trigger to publish or act on.
    selected = [] if state == "budget_deferred" else sorted_candidates[:MAX_CANDIDATES]
    return {"version": 1, "state": state, "reason": reason,
            "available_total": total_available, "open_total": total_open,
            "agent_capacity": capacity, "blocked_cause_totals": total_causes,
            "repositories": {name: by_repo[name] for name in REPOSITORIES},
            "roadmap_candidates": selected,
            "omitted_candidates": 0 if state == "budget_deferred"
            else len(sorted_candidates) - len(selected),
            "publication_allowed": False}
