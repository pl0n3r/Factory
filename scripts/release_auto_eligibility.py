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
# SemVer usa solo dígitos ASCII: re.ASCII evita que \d admita Unicode.
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", re.ASCII)

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


def _invalid_release_context(snapshot: Mapping) -> str | None:
    """Detecta vetos de identidad, fase, SHA y versión antes de elegir puerta."""
    if snapshot.get("phase") not in ("construccion", "live"):
        return "phase_unknown"
    if snapshot.get("kill_switch_state") != "RUNNING":
        return "kill_switch_not_running"
    if type(snapshot.get("release_machinery_changed")) is not bool:
        return "release_change_classification_unknown"
    if snapshot.get("v1_tag_protected") is not True:
        return "v1_tag_unprotected_or_unknown"
    if snapshot.get("evidence_authenticated") is not True:
        return "evidence_not_authenticated"

    main_sha = snapshot.get("main_sha")
    if not isinstance(main_sha, str) or not SHA40.fullmatch(main_sha):
        return "main_sha_invalid"
    if not isinstance(snapshot.get("observed_main_sha"), str) or snapshot["observed_main_sha"] != main_sha:
        return "main_sha_stale"

    candidate = _version(snapshot.get("candidate_version"))
    published = _version(snapshot.get("published_version"))
    if candidate is None or published is None:
        return "semver_invalid"
    if candidate[0] != published[0] or candidate <= published:
        return "semver_not_forward_same_major"
    return None


def _invalid_check_record(item: object, main_sha: str, seen: set[str]) -> str | None:
    """Valida un check sin aceptar campos adicionales ni identidades duplicadas."""
    if not isinstance(item, dict) or set(item) != {
        "name", "head_sha", "status", "conclusion", "authenticated"
    }:
        return "check_record_invalid"
    name = item["name"]
    if not isinstance(name, str) or not name or len(name) > 128 or name in seen:
        return "check_name_invalid_or_duplicate"
    if item["authenticated"] is not True or item["head_sha"] != main_sha:
        return "check_untrusted_or_wrong_sha"
    if item["status"] != "completed" or item["conclusion"] != "success":
        return "check_not_terminal_green"
    return None


def _invalid_checks(checks: object, main_sha: str) -> str | None:
    """Comprueba completitud y origen del conjunto de checks para un SHA."""
    if not isinstance(checks, list) or not checks or len(checks) > 100:
        return "checks_missing_or_unbounded"
    seen: set[str] = set()
    for item in checks:
        invalid = _invalid_check_record(item, main_sha, seen)
        if invalid is not None:
            return invalid
        seen.add(item["name"])
    if not REQUIRED_CHECKS.issubset(seen):
        return "required_check_missing"
    return None


def evaluate(snapshot: object) -> dict[str, Any]:
    """Valida un snapshot local, sin emitir permisos ni certificar su origen.

    El caller futuro DEBE autenticar por separado origen, completitud, SHA,
    permisos de publicación y decisiones humanas. Un DRY_RUN_ELIGIBLE solo
    significa que no se detectó veto en ESTE snapshot sintético.
    """
    if not isinstance(snapshot, Mapping):
        return _result("BLOCKED", "snapshot_invalid")
    invalid = _invalid_release_context(snapshot)
    if invalid is not None:
        return _result("BLOCKED", invalid)
    invalid = _invalid_checks(snapshot.get("checks"), snapshot["main_sha"])
    if invalid is not None:
        return _result("BLOCKED", invalid)
    if snapshot["phase"] == "live" or snapshot["release_machinery_changed"]:
        return _result("HUMAN_GATE_REQUIRED", "live_or_release_machinery")
    return _result("DRY_RUN_ELIGIBLE", "offline_snapshot_only")
