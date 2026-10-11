#!/usr/bin/env python3
"""Normalizador puro de páginas verificadas de Issues para salud de cola.

Sin HTTP, disco, tokens, escritura de GitHub ni permiso de despacho.
El caller verifica headers Link y transporte, además del ordinal de
cada página, antes de suministrar has_next/page_number.
"""
from __future__ import annotations

REPOSITORIES = (
    "Factory", "Condor", "GrindFlow", "brvtal",
    "ControlBot", "AutoFactory", "FactoryRunner",
)
STATES = ("available", "reserved", "blocked", "planned", "in_review")
CAUSES = frozenset(("dependency", "claims", "human_gate", "planned", "unknown"))
LABEL_STATE = {
    "estado: disponible": "available",
    "estado: reservado": "reserved",
    "estado: bloqueado": "blocked",
    "estado: planificado": "planned",
    "estado: en revisión": "in_review",
    "status: available": "available",
    "status: reserved": "reserved",
    "status: blocked": "blocked",
    "status: planned": "planned",
    "status: in review": "in_review",
}
MAX_PAGES = 100
MAX_PAGE_SIZE = 100
MAX_ISSUES = 10000
MAX_BLOCKERS = 10000


class SnapshotError(ValueError):
    """No se certifica un inventario parcial, ambiguo o no canónico."""


def _shape(item: object, keys: set[str]) -> bool:
    return type(item) is dict and set(item) == keys


def _int(value: object, upper: int, lower: int = 0) -> bool:
    return type(value) is int and lower <= value <= upper


def _state(labels: object) -> str:
    if type(labels) is not list or len(labels) > 40:
        raise SnapshotError("invalid_labels")
    found: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if type(label) is not str or len(label) > 100 or label in seen:
            raise SnapshotError("invalid_labels")
        seen.add(label)
        if label in LABEL_STATE:
            found.append(LABEL_STATE[label])
        elif label in ("estado: requiere recuperación", "status: recovery required"):
            # A recovery lease is neither ordinary 'blocked' nor 'available'.
            # Sibling diagnose_queue currently has no recovery count: refuse a
            # misleading complete snapshot until both contracts are upgraded.
            raise SnapshotError("recovery_status_unrepresentable")
        elif label.casefold().startswith(("estado:", "status:")):
            raise SnapshotError("unknown_status_label")
    if len(found) != 1:
        raise SnapshotError("ambiguous_status")
    return found[0]


def _rate_limit(value: object) -> dict:
    if (not _shape(value, {"limit", "remaining"})
            or not _int(value["limit"], 100000000, 1)
            or not _int(value["remaining"], value["limit"])):
        raise SnapshotError("invalid_rate_limit")
    return {"limit": value["limit"], "remaining": value["remaining"]}


def assemble_inventory(reports: object, agent_capacity: object,
                       rate_limit: object) -> dict:
    """Prepara la forma exacta de diagnose_queue sin inferir causas ni readiness.

    Cada reporte declara page_number contiguos y has_next por página.
    El consumidor debe derivar esos datos del HTTP/Link verificados; esta
    comprobación pura no prueba integridad ni autenticidad del transporte.
    """
    if agent_capacity is not None and not _int(agent_capacity, 1000):
        raise SnapshotError("invalid_capacity")
    budget = _rate_limit(rate_limit)
    if type(reports) is not list or len(reports) != len(REPOSITORIES):
        raise SnapshotError("incomplete_repositories")
    seen_repos: set[str] = set()
    by_repo: dict[str, dict] = {}
    blocker_count = 0
    for report in reports:
        if not _shape(report, {"name", "pages"}):
            raise SnapshotError("invalid_report")
        name = report["name"]
        if type(name) is not str or name not in REPOSITORIES or name in seen_repos:
            raise SnapshotError("unknown_or_duplicate_repo")
        seen_repos.add(name)
        pages = report["pages"]
        if type(pages) is not list or not 1 <= len(pages) <= MAX_PAGES:
            raise SnapshotError("incomplete_pagination")
        seen_numbers: set[int] = set()
        counts = {state: 0 for state in STATES}
        blocked: list[dict] = []
        for index, page in enumerate(pages):
            if not _shape(page, {"issues", "has_next", "page_number"}):
                raise SnapshotError("invalid_page")
            if (not _int(page["page_number"], MAX_PAGES, 1)
                    or page["page_number"] != index + 1
                    or type(page["has_next"]) is not bool
                    or page["has_next"] is not (index < len(pages) - 1)):
                raise SnapshotError("incomplete_pagination")
            items = page["issues"]
            if type(items) is not list or len(items) > MAX_PAGE_SIZE:
                raise SnapshotError("invalid_page")
            for item in items:
                if not _shape(item, {"number", "labels", "pull_request", "blocker"}):
                    raise SnapshotError("invalid_issue")
                n = item["number"]
                if not _int(n, 100000000, 1) or n in seen_numbers:
                    raise SnapshotError("duplicate_or_invalid_issue")
                seen_numbers.add(n)
                if type(item["pull_request"]) is not bool:
                    raise SnapshotError("invalid_issue")
                if item["pull_request"]:
                    if item["blocker"] is not None:
                        raise SnapshotError("invalid_pr")
                    continue
                state = _state(item["labels"])
                evidence = item["blocker"]
                if state != "blocked":
                    if evidence is not None:
                        raise SnapshotError("unexpected_blocker")
                elif evidence is None:
                    # Missing trusted evidence cannot promote an Issue to roadmap.
                    blocked.append({"number": n, "cause": "unknown", "roadmap": False})
                else:
                    if (not _shape(evidence, {"cause", "roadmap"})
                            or type(evidence["cause"]) is not str
                            or evidence["cause"] not in CAUSES
                            or type(evidence["roadmap"]) is not bool
                            or (evidence["roadmap"] and evidence["cause"]
                                in ("unknown", "planned", "human_gate"))):
                        # Unknown/planned/human-only work cannot be promoted,
                        # even when the external snapshot asserts roadmap=True.
                        raise SnapshotError("invalid_blocker")
                    blocked.append({"number": n, "cause": evidence["cause"],
                                    "roadmap": evidence["roadmap"]})
                counts[state] += 1
                if sum(counts.values()) > MAX_ISSUES:
                    raise SnapshotError("too_many_issues")
        blocker_count += len(blocked)
        if blocker_count > MAX_BLOCKERS:
            raise SnapshotError("too_many_blockers")
        by_repo[name] = {
            "name": name, "complete": True, "open_issues": sum(counts.values()),
            "counts": counts, "blockers": sorted(blocked, key=lambda x: x["number"]),
        }
    if seen_repos != set(REPOSITORIES):
        raise SnapshotError("incomplete_repositories")
    return {
        "version": 1, "repositories": [by_repo[name] for name in REPOSITORIES],
        "agent_capacity": agent_capacity, "rate_limit": budget,
    }
