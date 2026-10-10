#!/usr/bin/env python3
"""Propuesta pura de incidente de cola: sin I/O ni autoridad para publicar."""
from __future__ import annotations

import hashlib
import json

REPOSITORIES = (
    "Factory", "Condor", "GrindFlow", "brvtal", "ControlBot",
    "AutoFactory", "FactoryRunner",
)
CAUSES = ("claims", "dependency", "human_gate", "planned", "unknown")
STATES = frozenset(("queue_empty", "below_capacity", "healthy",
                    "unknown_capacity", "budget_deferred"))
MAX_ISSUES = 10000
MAX_CANDIDATES = 32


class IncidentPlanError(ValueError):
    """La evidencia de cola no basta para construir una propuesta."""


def _exact(value: object, keys: set[str]) -> bool:
    return type(value) is dict and set(value) == keys


def _int(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def plan_incidente_cola(report: object, previous: object = None) -> dict:
    """Retorna create/update/noop/deferred como plan, nunca como permiso.

    Solo acepta un reporte reducido, explícitamente completo y tipado; el
    integrador futuro tendrá que autenticar el snapshot y revalidar la puerta.
    """
    keys = {"version", "state", "complete", "available_total", "open_total",
            "agent_capacity", "rate_limit", "blocked_cause_totals",
            "roadmap_candidates", "repositories"}
    if not _exact(report, keys):
        raise IncidentPlanError("invalid_report")
    if report["version"] != 1 or type(report["version"]) is not int:
        raise IncidentPlanError("invalid_version")
    if report["complete"] is not True:
        raise IncidentPlanError("incomplete_inventory")
    state = report["state"]
    if type(state) is not str or state not in STATES:
        raise IncidentPlanError("invalid_state")
    open_total, available = report["open_total"], report["available_total"]
    capacity = report["agent_capacity"]
    if (not _int(open_total, 0, 7 * MAX_ISSUES)
            or not _int(available, 0, open_total)
            or (capacity is not None and not _int(capacity, 0, 1000))):
        raise IncidentPlanError("invalid_totals")
    budget = report["rate_limit"]
    if (not _exact(budget, {"limit", "remaining"})
            or not _int(budget["limit"], 1, 100000000)
            or not _int(budget["remaining"], 0, budget["limit"])):
        raise IncidentPlanError("invalid_budget")
    low_budget = budget["remaining"] * 5 < budget["limit"]
    if (state == "budget_deferred") != low_budget:
        raise IncidentPlanError("inconsistent_budget_state")
    if not low_budget:
        if state == "queue_empty" and available != 0:
            raise IncidentPlanError("inconsistent_queue_state")
        if state == "below_capacity" and (
            available == 0 or capacity is None
            or (capacity != 0 and available >= capacity)
        ):
            raise IncidentPlanError("inconsistent_queue_state")
        if state == "healthy" and (
            available == 0 or capacity is None or capacity == 0
            or available < capacity
        ):
            raise IncidentPlanError("inconsistent_queue_state")
        if state == "unknown_capacity" and (available == 0 or capacity is not None):
            raise IncidentPlanError("inconsistent_queue_state")
    causes = report["blocked_cause_totals"]
    if (not _exact(causes, set(CAUSES))
            or not all(_int(causes[c], 0, 7 * MAX_ISSUES) for c in CAUSES)):
        raise IncidentPlanError("invalid_causes")
    rows = report["repositories"]
    if type(rows) is not list or len(rows) != len(REPOSITORIES):
        raise IncidentPlanError("incomplete_inventory")
    normalized = []
    seen = set()
    for row in rows:
        if not _exact(row, {"name", "open_issues", "available", "blocked"}):
            raise IncidentPlanError("invalid_repository")
        name = row["name"]
        if type(name) is not str or name not in REPOSITORIES or name in seen:
            raise IncidentPlanError("duplicate_or_unknown_repository")
        seen.add(name)
        if (not _int(row["open_issues"], 0, MAX_ISSUES)
                or not _int(row["available"], 0, row["open_issues"])
                or not _int(row["blocked"], 0, row["open_issues"] - row["available"])):
            raise IncidentPlanError("invalid_repository_counts")
        normalized.append({"name": name, "open_issues": row["open_issues"],
                           "available": row["available"], "blocked": row["blocked"]})
    normalized.sort(key=lambda x: REPOSITORIES.index(x["name"]))
    if (sum(r["open_issues"] for r in normalized) != open_total
            or sum(r["available"] for r in normalized) != available
            or sum(r["blocked"] for r in normalized) != sum(causes.values())):
        raise IncidentPlanError("inconsistent_totals")
    raw_candidates = report["roadmap_candidates"]
    if type(raw_candidates) is not list or len(raw_candidates) > MAX_CANDIDATES:
        raise IncidentPlanError("invalid_candidates")
    # El productor canónico #1098 suprime todo roadmap bajo 20 %.
    # No generar recomendaciones desde un snapshot diferido o contradictorio.
    if low_budget and raw_candidates:
        raise IncidentPlanError("inconsistent_candidate_budget")
    candidates = []
    seen_candidates = set()
    for item in raw_candidates:
        if not _exact(item, {"repository", "issue", "cause"}):
            raise IncidentPlanError("invalid_candidate")
        repo, issue, cause = item["repository"], item["issue"], item["cause"]
        if (type(repo) is not str or repo not in REPOSITORIES
                or not _int(issue, 1, 100000000)
                or type(cause) is not str or cause not in ("dependency", "claims")
                or (repo, issue) in seen_candidates):
            raise IncidentPlanError("invalid_candidate")
        seen_candidates.add((repo, issue))
        candidates.append({"repository": repo, "issue": issue, "cause": cause})
    if (any(sum(1 for x in candidates if x["cause"] == cause) > causes[cause]
            for cause in ("dependency", "claims"))
            or any(sum(1 for x in candidates if x["repository"] == row["name"])
                   > row["blocked"] for row in normalized)):
        # A candidate cannot belong to a repo that reports zero blockers.
        raise IncidentPlanError("inconsistent_candidates")
    candidates.sort(key=lambda x: (REPOSITORIES.index(x["repository"]), x["issue"]))
    canonical = {"version": 1, "state": state, "available_total": available,
                 "open_total": open_total, "agent_capacity": capacity,
                 "blocked_cause_totals": {c: causes[c] for c in CAUSES},
                 "repositories": normalized, "roadmap_candidates": candidates}
    fingerprint = hashlib.sha256(json.dumps(canonical, ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    previous_number = None
    previous_fingerprint = None
    if previous is not None:
        if (not _exact(previous, {"issue_number", "fingerprint"})
                or not _int(previous["issue_number"], 1, 100000000)
                or type(previous["fingerprint"]) is not str
                or len(previous["fingerprint"]) != 64
                or any(ch not in "0123456789abcdef" for ch in previous["fingerprint"])):
            raise IncidentPlanError("invalid_previous")
        previous_number = previous["issue_number"]
        previous_fingerprint = previous["fingerprint"]
    if low_budget:
        action, reason = "deferred", "rate_limit_below_20_percent"
    elif state in ("healthy", "unknown_capacity"):
        action, reason = "noop", "no_verified_incident"
    elif previous is None:
        action, reason = "create", "new_incident_proposal"
    elif previous_fingerprint == fingerprint:
        action, reason = "noop", "unchanged_incident"
    else:
        action, reason = "update", "incident_evidence_changed"
    return {"version": 1, "action": action, "reason": reason,
            "fingerprint": fingerprint, "previous_issue_number": previous_number,
            "available_total": available, "open_total": open_total,
            "blocked_cause_totals": {c: causes[c] for c in CAUSES},
            "roadmap_candidates": candidates,
            "can_publish": False}


def report_from_diagnosis(diagnosis: object, rate_limit: object) -> dict:
    """Adapta la salida pura real de #1098 más presupuesto del MISMO snapshot.

    Esta conversión no autentica GitHub, no acredita temporalidad ni permite
    publicar. Un ejecutor futuro debe verificar origen/SHA antes de usarla.
    """
    fields = {"version", "state", "reason", "available_total", "open_total",
              "agent_capacity", "blocked_cause_totals", "repositories",
              "roadmap_candidates", "omitted_candidates", "can_dispatch",
              "publication_allowed"}
    if (not _exact(diagnosis, fields)
            or diagnosis["publication_allowed"] is not False
            or type(diagnosis["can_dispatch"]) is not bool
            or not _int(diagnosis["omitted_candidates"], 0, 7 * MAX_ISSUES)
            or not _int(diagnosis["open_total"], 0, 7 * MAX_ISSUES)
            or not _int(diagnosis["available_total"], 0, diagnosis["open_total"])
            or (diagnosis["agent_capacity"] is not None
                and not _int(diagnosis["agent_capacity"], 0, 1000))):
        raise IncidentPlanError("invalid_diagnosis")
    states = ("available", "reserved", "blocked", "planned", "in_review")
    by_repo = diagnosis["repositories"]
    if type(by_repo) is not dict or set(by_repo) != set(REPOSITORIES):
        raise IncidentPlanError("incomplete_inventory")
    rows = []
    totals = {cause: 0 for cause in CAUSES}
    confirmed_candidates = set()
    for name in REPOSITORIES:
        row = by_repo[name]
        if not _exact(row, {"open_issues", "counts", "blocked_reasons",
                            "blocked_cause_counts"}):
            raise IncidentPlanError("invalid_diagnosis_repository")
        counts = row["counts"]
        if (not _exact(counts, set(states))
                or not all(_int(counts[s], 0, MAX_ISSUES) for s in states)
                or not _int(row["open_issues"], 0, MAX_ISSUES)
                or sum(counts.values()) != row["open_issues"]):
            raise IncidentPlanError("invalid_diagnosis_counts")
        reasons = row["blocked_reasons"]
        if type(reasons) is not list or len(reasons) != counts["blocked"]:
            raise IncidentPlanError("invalid_diagnosis_blockers")
        found = {c: 0 for c in CAUSES}
        ids = set()
        for blocker in reasons:
            if not _exact(blocker, {"issue", "cause", "roadmap"}):
                raise IncidentPlanError("invalid_diagnosis_blocker")
            issue, cause, roadmap = (blocker["issue"], blocker["cause"],
                                     blocker["roadmap"])
            if (not _int(issue, 1, 100000000) or issue in ids
                    or type(cause) is not str or cause not in CAUSES
                    or type(roadmap) is not bool
                    or (roadmap and cause in ("unknown", "human_gate", "planned"))):
                raise IncidentPlanError("invalid_diagnosis_blocker")
            ids.add(issue)
            found[cause] += 1
            if roadmap and cause in ("dependency", "claims"):
                confirmed_candidates.add((name, issue, cause))
        if (not _exact(row["blocked_cause_counts"], set(CAUSES))
                or any(not _int(row["blocked_cause_counts"][c], 0, MAX_ISSUES)
                       for c in CAUSES)
                or row["blocked_cause_counts"] != found):
            raise IncidentPlanError("inconsistent_diagnosis_causes")
        for c in CAUSES:
            totals[c] += found[c]
        rows.append({"name": name, "open_issues": row["open_issues"],
                     "available": counts["available"],
                     "blocked": counts["blocked"]})
    reported_causes = diagnosis["blocked_cause_totals"]
    if (not _exact(reported_causes, set(CAUSES))
            or any(not _int(reported_causes[c], 0, 7 * MAX_ISSUES)
                   for c in CAUSES)
            or reported_causes != totals):
        # bool == int in Python, but bool is never a valid count.
        raise IncidentPlanError("inconsistent_diagnosis_causes")
    raw_candidates = diagnosis["roadmap_candidates"]
    if type(raw_candidates) is not list or len(raw_candidates) > MAX_CANDIDATES:
        raise IncidentPlanError("invalid_diagnosis_candidates")
    for item in raw_candidates:
        if (not _exact(item, {"repository", "issue", "cause"})
                or type(item["repository"]) is not str
                or not _int(item["issue"], 1, 100000000)
                or type(item["cause"]) is not str
                or (item["repository"], item["issue"], item["cause"])
                not in confirmed_candidates):
            raise IncidentPlanError("unverified_candidate")
    # El clasificador #1098 selecciona EXACTAMENTE los primeros 32
    # candidatos en orden de repositorio y número. Cardinalidad sola no
    # prueba una proyección completa: puede ocultar el candidato más urgente.
    expected_candidates = [
        {"repository": name, "issue": issue, "cause": cause}
        for name, issue, cause in sorted(
            confirmed_candidates,
            key=lambda item: (REPOSITORIES.index(item[0]), item[1]),
        )
    ]
    if diagnosis["state"] == "budget_deferred":
        if raw_candidates or diagnosis["omitted_candidates"] != 0:
            raise IncidentPlanError("inconsistent_candidate_budget")
    elif (raw_candidates != expected_candidates[:MAX_CANDIDATES]
          or diagnosis["omitted_candidates"] != max(0, len(expected_candidates) - MAX_CANDIDATES)):
        raise IncidentPlanError("incomplete_candidates")
    expected_reason = {
        "queue_empty": "zero_available",
        "unknown_capacity": "capacity_not_observed",
        "below_capacity": ("zero_execution_capacity"
                           if diagnosis["agent_capacity"] == 0
                           else "fewer_ready_than_capacity"),
        "healthy": "reported_capacity_sufficient",
        "budget_deferred": "rate_limit_below_20_percent",
    }
    if (type(diagnosis["state"]) is not str
            or diagnosis["state"] not in expected_reason
            or diagnosis["reason"] != expected_reason[diagnosis["state"]]):
        raise IncidentPlanError("invalid_diagnosis_state")
    should_dispatch = (diagnosis["state"] != "budget_deferred"
                       and diagnosis["available_total"] > 0
                       and diagnosis["agent_capacity"] is not None
                       and diagnosis["agent_capacity"] > 0)
    if diagnosis["can_dispatch"] is not should_dispatch:
        raise IncidentPlanError("inconsistent_dispatch_signal")
    report = {"version": diagnosis["version"], "state": diagnosis["state"],
              "complete": True, "available_total": diagnosis["available_total"],
              "open_total": diagnosis["open_total"],
              "agent_capacity": diagnosis["agent_capacity"],
              "rate_limit": rate_limit, "blocked_cause_totals": totals,
              "roadmap_candidates": raw_candidates, "repositories": rows}
    # Validate all totals, rate-limit and the proposed state with the same
    # strict checks used by the eventual planning entrypoint.
    plan_incidente_cola(report)
    return report


__all__ = ["IncidentPlanError", "plan_incidente_cola", "report_from_diagnosis"]
