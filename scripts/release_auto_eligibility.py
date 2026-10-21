#!/usr/bin/env python3
"""Evaluador de elegibilidad DRY-RUN de Factory #1080/#1448.

Trust boundary: los snapshots son entradas del caller, NO pruebas autenticadas
por este módulo. Ninguna salida concede autoridad para tags, workflows o release.
Sin I/O, sin red, sin efectos secundarios y sin secretos.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")

REQUIRED_CHECKS = frozenset({
    "Validar",
    "SonarCloud Code Analysis",
    "CodeQL",
    "Compatibilidad de consumidores",
    "Vigilar startup_failure de reusables publicados",
})
STATES = frozenset({"DRY_RUN_ELIGIBLE", "HUMAN_GATE_REQUIRED", "BLOCKED"})


def _result(state: str, reason: str) -> dict[str, Any]:
    """El resultado nunca transporta una facultad de publicación."""
    assert state in STATES
    return {
        "decision": state,
        "reason": reason,
        "authorizes_release": False,
        "mutations": 0,
    }


def _version(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or len(value) > 64 or not SEMVER.fullmatch(value):
        return None
    return tuple(int(segment) for segment in value.split("."))


def evaluate(snapshot: object) -> dict[str, Any]:
    """Valida un snapshot de pruebas locales, sin emitir permisos.

    El caller futuro DEBE autenticar por separado origen, completitud, SHA,
    permisos de publicación y decisiones humanas. Un DRY_RUN_ELIGIBLE solo
    significa que no se detectó veto en ESTE snapshot sintético.
    """
    if not isinstance(snapshot, Mapping):
        return _result("BLOCKED", "snapshot_invalid")

    phase = snapshot.get("phase")
    if phase not in ("construccion", "live"):
        return _result("BLOCKED", "phase_unknown")

    if snapshot.get("kill_switch_state") != "RUNNING":
        return _result("BLOCKED", "kill_switch_not_running")

    touched = snapshot.get("release_machinery_changed")
    if type(touched) is not bool:
        return _result("BLOCKED", "release_change_classification_unknown")
    if phase == "live" or touched:
        return _result("HUMAN_GATE_REQUIRED", "live_or_release_machinery")

    if snapshot.get("v1_tag_protected") is not True:
        return _result("BLOCKED", "v1_tag_unprotected_or_unknown")
    if snapshot.get("evidence_authenticated") is not True:
        return _result("BLOCKED", "evidence_not_authenticated")

    main_sha = snapshot.get("main_sha")
    observed = snapshot.get("observed_main_sha")
    if not isinstance(main_sha, str) or not SHA40.fullmatch(main_sha):
        return _result("BLOCKED", "main_sha_invalid")
    if not isinstance(observed, str) or observed != main_sha:
        return _result("BLOCKED", "main_sha_stale")

    candidate = _version(snapshot.get("candidate_version"))
    published = _version(snapshot.get("published_version"))
    if candidate is None or published is None:
        return _result("BLOCKED", "semver_invalid")
    if candidate[0] != published[0] or candidate <= published:
        return _result("BLOCKED", "semver_not_forward_same_major")

    checks = snapshot.get("checks")
    if not isinstance(checks, list) or not checks or len(checks) > 100:
        return _result("BLOCKED", "checks_missing_or_unbounded")

    seen: set[str] = set()
    for item in checks:
        if not isinstance(item, dict) or set(item) != {
            "name", "head_sha", "status", "conclusion", "authenticated"
        }:
            return _result("BLOCKED", "check_record_invalid")
        name = item["name"]
        if not isinstance(name, str) or not name or len(name) > 128 or name in seen:
            return _result("BLOCKED", "check_name_invalid_or_duplicate")
        seen.add(name)
        if item["authenticated"] is not True or item["head_sha"] != main_sha:
            return _result("BLOCKED", "check_untrusted_or_wrong_sha")
        if item["status"] != "completed" or item["conclusion"] != "success":
            return _result("BLOCKED", "check_not_terminal_green")

    if not REQUIRED_CHECKS.issubset(seen):
        return _result("BLOCKED", "required_check_missing")
    return _result("DRY_RUN_ELIGIBLE", "offline_snapshot_only")
