#!/usr/bin/env python3
"""Auditoría pura de una identidad hipotética de Factory@v1 (Factory #2100).

Evalúa declaraciones, no autenticidad ni autorización. Ningún resultado habilita
publicación, cambios de ruleset, uso de credenciales o movimiento de tags.
"""
from __future__ import annotations

from typing import Any

RULESET_ID = 23958613
TAG_REF = "refs/tags/v1"
REPO = "pl0n3r/Factory"
GENERIC_ACTIONS_APP_ID = 15368
REQUIRED_RULES = frozenset({"creation", "update", "deletion"})
SNAPSHOT_FIELDS = frozenset({"ruleset", "app", "installation"})
APP_FIELDS = frozenset({"id", "slug", "purpose"})
INSTALLATION_FIELDS = frozenset({
    "app_id", "repository_selection", "repositories", "permissions", "suspended_at",
})


def _result(reason: str, review: bool = False) -> dict[str, Any]:
    return {
        "state": "REVIEW_ONLY" if review else "BLOCKED",
        "reason": reason,
        "authorizes_release": False,
        "mutations": 0,
        "network_calls": 0,
        "tag_writes": 0,
        "release_writes": 0,
    }


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def evaluate_trust_root(snapshot: object) -> dict[str, Any]:
    """Comprueba estructura de configuración *declarativa* sin hacer I/O.

    El caller debe autenticar de forma independiente identidad, instalación,
    permisos y ruleset. REVIEW_ONLY solo permite revisión humana posterior.
    """
    if type(snapshot) is not dict or set(snapshot) != SNAPSHOT_FIELDS:
        return _result("snapshot_missing_or_ambiguous")

    app = snapshot["app"]
    if type(app) is not dict or set(app) != APP_FIELDS:
        return _result("app_identity_missing_or_ambiguous")
    app_id = app["id"]
    if (not _positive_int(app_id) or app_id == GENERIC_ACTIONS_APP_ID
            or type(app["slug"]) is not str
            or not 4 <= len(app["slug"]) <= 100
            or app["slug"].lower() == "github-actions"
            or app["purpose"] != "factory-release-only"):
        return _result("dedicated_release_app_not_demonstrated")

    installation = snapshot["installation"]
    if type(installation) is not dict or set(installation) != INSTALLATION_FIELDS:
        return _result("installation_missing_or_ambiguous")
    if (installation["app_id"] != app_id
            or installation["repository_selection"] != "selected"
            or installation["repositories"] != [REPO]
            or installation["permissions"] != {"contents": "write", "metadata": "read"}
            or installation["suspended_at"] is not None):
        return _result("installation_scope_or_permissions_unsafe")

    rule = snapshot["ruleset"]
    if type(rule) is not dict or set(rule) != {
        "id", "target", "enforcement", "conditions", "rules", "bypass_actors",
    }:
        return _result("ruleset_missing_or_ambiguous")
    if (type(rule["id"]) is not int or rule["id"] != RULESET_ID
            or rule["target"] != "tag" or rule["enforcement"] != "active"):
        return _result("ruleset_identity_or_enforcement_invalid")
    cond = rule["conditions"]
    if (type(cond) is not dict or set(cond) != {"ref_name"}
            or type(cond["ref_name"]) is not dict
            or set(cond["ref_name"]) != {"include", "exclude"}
            or cond["ref_name"]["include"] != [TAG_REF]
            or cond["ref_name"]["exclude"] != []):
        return _result("v1_ref_scope_unverified")

    rules = rule["rules"]
    if (type(rules) is not list or not 3 <= len(rules) <= 20
            or any(type(row) is not dict or set(row) != {"type"}
                   or type(row["type"]) is not str for row in rules)):
        return _result("v1_rules_invalid")
    names = [row["type"] for row in rules]
    if len(names) != len(set(names)) or not REQUIRED_RULES.issubset(names):
        return _result("v1_creation_update_deletion_unprotected")

    actors = rule["bypass_actors"]
    if type(actors) is not list or not 1 <= len(actors) <= 10:
        return _result("bypass_actors_missing_or_unbounded")
    integration_ids: list[int] = []
    seen: set[tuple[str, int]] = set()
    for actor in actors:
        if (type(actor) is not dict
                or set(actor) != {"actor_id", "actor_type", "bypass_mode"}
                or not _positive_int(actor["actor_id"])
                or type(actor["actor_type"]) is not str
                or actor["actor_type"] not in ("RepositoryRole", "Integration")
                or actor["bypass_mode"] != "always"):
            return _result("bypass_actor_invalid")
        identity = (actor["actor_type"], actor["actor_id"])
        if identity in seen:
            return _result("bypass_actor_duplicated")
        seen.add(identity)
        if actor["actor_type"] == "RepositoryRole" and actor["actor_id"] == 5:
            continue  # El bypass administrativo humano vigente se preserva.
        if actor["actor_type"] == "Integration":
            integration_ids.append(actor["actor_id"])
        else:
            return _result("unexpected_bypass_actor")
    if integration_ids != [app_id]:
        return _result("dedicated_app_bypass_missing_or_shared")

    return _result("hypothetical_dedicated_identity_requires_owner_activation", review=True)
