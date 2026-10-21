#!/usr/bin/env python3
"""Plan de rollback offline de Factory@v1; no autentica fuentes ni mueve tags.

Cualquier resultado HUMAN_GATE_REQUIRED es una recomendación para revisión del
OWNER, nunca permiso de publicación. El caller debe autenticar de forma separada
la evidencia real y verificar el resultado del rollback en consumidores nuevos.
"""
from __future__ import annotations

import re
from typing import Any

_SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
_SNAPSHOT_FIELDS = frozenset({
    "phase", "kill_switch_state", "tag_protected", "evidence_authenticated",
    "incident_type", "affected_factory_sha", "current_v1_sha",
    "stable_factory_sha", "affected_consumer_runs", "stable_consumer_runs",
})
_RUN_FIELDS = frozenset({
    "repository", "workflow", "run_id", "factory_sha", "conclusion",
    "authenticated", "materialized_jobs",
})
_POST_CHECKS = (
    "new_consumer_run_materializes_jobs",
    "new_consumer_run_is_not_startup_failure",
    "published_v1_ref_matches_stable_sha",
)


def _result(decision: str, reason: str, sha: str | None = None) -> dict[str, Any]:
    return {
        "decision": decision,
        "reason": reason,
        "proposed_stable_sha": sha,
        "authorizes_tag_move": False,
        "mutations": 0,
        "postrollback_verification_required": list(_POST_CHECKS),
    }


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _parse_runs(
    value: object, sha: str, expected_conclusion: str, jobs_materialized: bool,
) -> dict[tuple[str, str], int] | None:
    if not isinstance(value, list) or not (1 <= len(value) <= 32):
        return None
    seen: dict[tuple[str, str], int] = {}
    run_ids: set[int] = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != _RUN_FIELDS:
            return None
        repo, workflow, run_id = row["repository"], row["workflow"], row["run_id"]
        if (not isinstance(repo, str) or not (1 <= len(repo) <= 120)
                or not isinstance(workflow, str) or not (1 <= len(workflow) <= 160)
                or type(run_id) is not int or not (0 < run_id < 10**19)):
            return None
        if (row["authenticated"] is not True or row["factory_sha"] != sha
                or row["conclusion"] != expected_conclusion
                or row["materialized_jobs"] is not jobs_materialized):
            return None
        key = (repo, workflow)
        if key in seen or run_id in run_ids:
            return None
        seen[key] = run_id
        run_ids.add(run_id)
    return seen


def plan_rollback(snapshot: object) -> dict[str, Any]:
    """Valida *afirmaciones de un snapshot* y genera solo un plan no ejecutable.

    No I/O. Los booleans de autenticidad no constituyen una prueba propia de
    autenticación: únicamente un lector externo con provenance puede aportarlos.
    """
    if not isinstance(snapshot, dict) or set(snapshot) != _SNAPSHOT_FIELDS:
        return _result("BLOCKED", "snapshot_invalid_or_extra_fields")
    if snapshot["phase"] not in ("construccion", "live"):
        return _result("BLOCKED", "phase_unknown")
    if snapshot["kill_switch_state"] != "RUNNING":
        return _result("BLOCKED", "kill_switch_not_running")
    if snapshot["tag_protected"] is not True:
        return _result("BLOCKED", "v1_tag_not_protected")
    if snapshot["evidence_authenticated"] is not True:
        return _result("BLOCKED", "evidence_not_authenticated")
    if snapshot["incident_type"] != "startup_failure":
        return _result("BLOCKED", "incident_not_startup_failure")
    affected = snapshot["affected_factory_sha"]
    current = snapshot["current_v1_sha"]
    stable = snapshot["stable_factory_sha"]
    if not all(_valid_sha(v) for v in (affected, current, stable)):
        return _result("BLOCKED", "sha_invalid")
    if affected != current or stable == affected:
        return _result("BLOCKED", "sha_mismatch_or_no_prior_target")
    failures = _parse_runs(snapshot["affected_consumer_runs"], affected,
                           "startup_failure", False)
    history = _parse_runs(snapshot["stable_consumer_runs"], stable, "success", True)
    if failures is None or history is None:
        return _result("BLOCKED", "consumer_evidence_invalid")
    if not set(failures).issubset(history):
        return _result("BLOCKED", "consumer_stable_history_missing")
    if any(history[key] >= rid for key, rid in failures.items()):
        return _result("BLOCKED", "stable_history_not_earlier")
    return _result("HUMAN_GATE_REQUIRED", "owner_must_authorize_v1_rollback", stable)
