#!/usr/bin/env python3
"""Evaluación puramente offline del trámite de release (Factory #1613).

Un caller entrega afirmaciones; ni el objeto de entrada ni este módulo autentican
fuentes o autorizan modificar Factory@v1. REVIEW_ONLY requiere todavía la
verificación externa, independiente y exact-SHA de todas las evidencias.
"""
from __future__ import annotations

import re
from typing import Any

SHA = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
REQUIRED_CHECKS = frozenset({"Validar", "SonarCloud Code Analysis", "CodeQL"})
FIELDS = frozenset({
    "candidate_sha", "observed_main_sha", "published_v1_sha", "v1_tag_protected",
    "evidence_authenticated", "kill_switch_state", "freeze_active", "security_veto",
    "owner_decision", "checks",
})
DECISION_FIELDS = frozenset({"option", "candidate_sha", "category", "journal_verified", "owner"})
CHECK_FIELDS = frozenset({"name", "head_sha", "status", "conclusion", "authenticated"})


def _result(reason: str) -> dict[str, Any]:
    """Ningún resultado transporta permiso de publicación o mutación."""
    return {
        "state": "REVIEW_ONLY" if reason == "offline_preflight_passed" else "BLOCKED",
        "reason": reason,
        "authorizes_release": False,
        "mutations": 0,
        "network_calls": 0,
        "release_tag_writes": 0,
    }


def _sha(value: object) -> bool:
    return type(value) is str and SHA.fullmatch(value) is not None


def evaluate(snapshot: object) -> dict[str, Any]:
    """Comprueba un snapshot declarativo sin hacer I/O ni alterar la entrada.

    Aun cuando se devuelve REVIEW_ONLY, el caller debe autenticar por separado
    origen, permiso del OWNER, HEAD actual, compatibilidad y ventana de release.
    """
    if type(snapshot) is not dict or set(snapshot) != FIELDS:
        return _result("snapshot_invalid")

    candidate = snapshot["candidate_sha"]
    if not _sha(candidate) or not _sha(snapshot["observed_main_sha"]):
        return _result("candidate_or_observation_invalid")
    if snapshot["observed_main_sha"] != candidate:
        return _result("main_sha_mismatch")
    if not _sha(snapshot["published_v1_sha"]):
        return _result("published_tag_sha_invalid")
    if snapshot["published_v1_sha"] == candidate:
        return _result("candidate_already_published")
    if snapshot["v1_tag_protected"] is not True:
        return _result("v1_tag_protection_unknown")
    if snapshot["evidence_authenticated"] is not True:
        return _result("evidence_not_authenticated")
    if snapshot["kill_switch_state"] != "RUNNING":
        return _result("kill_switch_not_running")
    if snapshot["freeze_active"] is not False:
        return _result("release_freeze_active_or_unknown")
    if snapshot["security_veto"] is not False:
        return _result("security_veto_active_or_unknown")

    decision = snapshot["owner_decision"]
    if type(decision) is not dict or set(decision) != DECISION_FIELDS:
        return _result("owner_decision_invalid")
    if (decision["option"] != "A" or decision["category"] != "factory-release"
            or decision["owner"] != "pl0n3r" or decision["journal_verified"] is not True
            or not _sha(decision["candidate_sha"]) or decision["candidate_sha"] != candidate):
        return _result("owner_authority_missing_or_wrong_sha")

    checks = snapshot["checks"]
    if type(checks) is not list or not 3 <= len(checks) <= 20:
        return _result("checks_missing_or_unbounded")
    names: set[str] = set()
    for row in checks:
        if type(row) is not dict or set(row) != CHECK_FIELDS:
            return _result("check_record_invalid")
        name = row["name"]
        if type(name) is not str or not 1 <= len(name) <= 128 or name in names:
            return _result("check_name_invalid_or_duplicate")
        names.add(name)
        if (row["head_sha"] != candidate or row["authenticated"] is not True
                or row["status"] != "completed" or row["conclusion"] != "success"):
            return _result("check_not_exact_terminal_green")
    if not REQUIRED_CHECKS.issubset(names):
        return _result("required_checks_missing")

    return _result("offline_preflight_passed")
