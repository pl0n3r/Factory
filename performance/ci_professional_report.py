"""Diagnóstico canónico y no ejecutor de CI FactoryRunner para profesionales.

Un caller autenticado debe aportar el snapshot exacto de GitHub Actions.
Esta composición NO autentica HTTP, crea WorkItems, despacha ni aplica fixes.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from performance.github_actions_ci import evaluate_factoryrunner_ci_run
from performance.team_compiler_bridge import compile_performance_team


def diagnose_factoryrunner_ci_professionals(
    contract: Mapping[str, Any], run: Mapping[str, Any], *, evaluated_at: str
) -> dict[str, Any]:
    """Une detector/readiness y Team Compiler sin aumentar autoridad.

    CI fallido, snapshot ajeno o evidencia incompleta falla cerrado en el
    adaptador. Evidencia stale conserva UNKNOWN y no produce equipo.
    """
    observation = evaluate_factoryrunner_ci_run(
        contract, run, evaluated_at=evaluated_at,
    )
    status = observation["performance_status"]
    detection = observation["detection"]
    if (
        detection["evidence_state"] == "CURRENT"
        and detection["classification"] in {"PERF_DEGRADATION", "PERF_INCIDENT"}
        and status["status"] in {"DEGRADED", "BLOCKED"}
    ):
        team = compile_performance_team(detection, evaluated_at=evaluated_at)
    else:
        team = {
            "version": 1, "decision": "NO_ASSIGNMENT",
            "roles": [], "primary": None, "review": None,
            "authority": "unchanged", "execute_actions": False,
            "create_work_item": False, "dispatch": False,
        }
    # Lista blanca: nunca copiar la respuesta GitHub, logs, tokens ni
    # metadata de usuario ajena a las evidencias ya saneadas.
    return {
        "version": 1,
        "project": status["project"],
        "surface": status["surface"],
        "metric": status["metric"],
        "classification": status["classification"],
        "evidence_state": status["evidence_state"],
        "status": status["status"],
        "identity": dict(status["identity"]),
        "evidence_refs": list(status["evidence_refs"]),
        "readiness": observation["readiness"],
        "team": team,
        "authority": "unchanged",
        "execute_actions": False,
        "create_work_item": False,
        "dispatch": False,
        "adopt": False,
        "candidate_terminal": False,
    }
