"""Adaptador puro y GET-only de corridas CI autenticadas a Performance Contract v1.

La autenticación REST y la completitud del snapshot pertenecen al caller. Esta
función no crea trabajo, reserva, writeback, jobs ni altera la autoridad.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Any

from performance.detector import detect_performance
from performance.status import derive_performance_status, readiness_projection
from performance.triage import triage_performance

_REPOSITORY = "pl0n3r/FactoryRunner"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_MAX_RUN_SECONDS = 24 * 60 * 60


class PerformanceCiObservationError(ValueError):
    """Una corrida no es una evidencia completa, comparable y confiable."""


def evaluate_factoryrunner_ci_run(
    contract: Mapping[str, Any], run: Mapping[str, Any], *, evaluated_at: str
) -> dict[str, Any]:
    """Clasifica una corrida push/main CI, sin inferir un fix ni conceder autoridad.

    \`run\` debe proceder de GET autenticado a la API de GitHub, exact-run; la
    función valida su identidad pero no autentica por sí misma su procedencia.
    """
    if not isinstance(run, Mapping):
        raise PerformanceCiObservationError("La corrida no es un objeto.")
    repository = run.get("repository")
    if not isinstance(repository, Mapping) or repository.get("full_name") != _REPOSITORY:
        raise PerformanceCiObservationError("Repositorio de evidencia incompatible.")
    expected = {
        "name": "CI", "event": "push", "head_branch": "main",
        "status": "completed", "conclusion": "success",
    }
    if any(run.get(key) != value for key, value in expected.items()):
        raise PerformanceCiObservationError("Corrida no es CI push/main completado exitosamente.")
    sha = run.get("head_sha")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise PerformanceCiObservationError("SHA de la corrida inválido.")
    run_id, attempt = run.get("id"), run.get("run_attempt")
    if (type(run_id) is not int or not 1 <= run_id <= 10**18
            or type(attempt) is not int or not 1 <= attempt <= 100):
        raise PerformanceCiObservationError("Identidad de corrida inválida.")
    start = _parse_timestamp(run.get("run_started_at"), "run_started_at")
    end = _parse_timestamp(run.get("updated_at"), "updated_at")
    elapsed = (end - start).total_seconds()
    if not 1 <= elapsed <= _MAX_RUN_SECONDS:
        raise PerformanceCiObservationError("Duración de corrida inválida.")
    observation = {
        "version": 1,
        "project": "factoryrunner",
        "surface": "ci.workflow",
        "metric": "workflow_elapsed",
        "value": int(elapsed),
        "unit": "s",
        "observed_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_seconds": max(1, int(elapsed)),
        "sample_count": 1,
        "severity": "medium",
        "operational_impact": False,
        "bottleneck": "unknown",
        "evidence_ref": f"github:{_REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}",
        "sha": sha,
        "release": "ci",
    }
    detection = detect_performance(contract, observation, evaluated_at=evaluated_at)
    triage = triage_performance(detection)
    status = derive_performance_status(detection)
    return {
        "version": 1,
        "detection": detection,
        "triage": triage,
        "performance_status": status,
        "readiness": readiness_projection(status),
        "authority": "unchanged",
        "execute_actions": False,
        "create_work_item": False,
        "candidate_terminal": False,
    }


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise PerformanceCiObservationError(f"{field} carece de timestamp UTC exacto.")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PerformanceCiObservationError(f"{field} es inválido.") from exc
    return parsed
