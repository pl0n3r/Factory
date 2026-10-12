#!/usr/bin/env python3
"""Frontera REST de solo lectura para futuras liberaciones V3.

NO implementa CAS ni serialización compartida: hasta contar con una prueba
completa de *ausencia* de actividad, ningún Snapshot de este Port puede
autorizar a lease_release_executor a escribir. El resultado RECENT_ACTIVITY
solo acredita una observación positiva acotada, nunca inactividad.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from scripts.lease_release_executor import SESSION_RE, SHA

from scripts.lease_activity_collector import collect_activity
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch


GLOBAL_SWITCH = "/repos/pl0n3r/Factory/issues/767"
UNKNOWN = "UNKNOWN"
RECENT = "RECENT_ACTIVITY"


class PortNotArmed(RuntimeError):
    """Falta evidencia completa de inactividad, lock y CAS compartido."""


@dataclass(frozen=True)
class Inspection:
    state: str
    issue: int
    release_authorized: bool = False
    lease_id: str | None = None
    branch_sha: str | None = None
    last_activity_at: str | None = None


_RECENT_STATES = frozenset({
    "estado: reservado", "estado: en revisión", "estado: requiere recuperación",
})
_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\\Z")


def _recent_report_ok(report: Any, issue: int, repo: Any, now: Any) -> bool:
    """Defensa adicional del límite inspector/collector; nunca ausencia."""
    if (type(report) is not dict or report.get("evidence_complete") is not True
            or report.get("status") not in _RECENT_STATES
            or type(repo) is not str or report.get("repo") != repo
            or type(report.get("issue_number")) is not int
            or report["issue_number"] != issue
            or type(report.get("repository_id")) is not int
            or report["repository_id"] <= 0
            or type(report.get("owner")) is not str
            or not report["owner"]
            or report.get("branch") != f"trabajo/issue-{issue}"
            or type(report.get("lease_id")) is not str
            or SESSION_RE.fullmatch(report["lease_id"]) is None
            or type(report.get("branch_sha")) is not str
            or SHA.fullmatch(report["branch_sha"]) is None
            or type(report.get("ci_running")) is not bool
            or type(report.get("rate_limit")) is not int
            or type(report.get("rate_remaining")) is not int
            or report["rate_limit"] <= 0 or report["rate_remaining"] < 0
            or report["rate_remaining"] > report["rate_limit"]
            or report["rate_remaining"] * 5 < report["rate_limit"]
            or type(report.get("pagination")) is not dict
            or type(report.get("api_requests")) is not int
            or not 1 <= report["api_requests"] <= 32
            or type(now) is not datetime or now.tzinfo is None
            or now.utcoffset() is None):
        return False
    stamp = report.get("last_activity_at")
    if type(stamp) is not str or _STAMP.fullmatch(stamp) is None:
        return False
    try:
        activity = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        observed = now.astimezone(timezone.utc)
        return (timedelta(0) <= observed - activity < timedelta(minutes=30))
    except (ValueError, OverflowError, TypeError):
        return False


class LeaseGithubPort:
    """Adaptador inyectado: únicamente GET sobre una API autenticada.

    No importa tokens, no abre sockets y no acepta que el caller proporcione
    otro origen para el interruptor global. Una excepción se reduce a UNKNOWN
    sin exponer cuerpos, URLs con credenciales ni detalles privados.
    """

    def __init__(self, api: Any) -> None:
        self._api = api

    def _running(self) -> bool:
        obj = self._api.request("GET", GLOBAL_SWITCH)
        verdict = evaluate_unattended_kill_switch(obj)
        return verdict.state == "RUNNING" and verdict.global_pause is False

    def inspect(self, issue: int, *, now: datetime) -> Inspection:
        invalid = Inspection(UNKNOWN, issue if type(issue) is int else 0)
        if type(issue) is not int or issue <= 0:
            return invalid
        try:
            # Preflight global absoluto antes de consultar otro recurso.
            if not self._running():
                return invalid
            report = collect_activity(self._api, issue, now=now)
            if not _recent_report_ok(report, issue, getattr(self._api, "repo", None),
                                     now):
                return invalid
            # Volver a leer #767: RUNNING no es un permiso duradero.
            if not self._running():
                return invalid
            return Inspection(
                RECENT, issue, release_authorized=False,
                lease_id=report["lease_id"],
                branch_sha=report["branch_sha"],
                last_activity_at=report["last_activity_at"],
            )
        except Exception:
            return invalid

    def read(self, issue: int) -> Any:
        # Una muestra de actividad RECIENTE nunca permite certificar
        # AUSENCIA de push/comentario del titular durante >30 min.
        raise PortNotArmed("complete_inactivity_proof_unavailable")

    def lock(self, group: str) -> Any:
        raise PortNotArmed("shared_v3_cas_lock_not_implemented")

    def append(self, issue: int, body: str, expected: Any) -> None:
        raise PortNotArmed("mutation_disabled")

    def recovery_note(self, issue: int, expected: Any) -> Any:
        raise PortNotArmed("authenticated_recovery_proof_unavailable")

    def recovery_label(self, issue: int, expected: Any) -> Any:
        raise PortNotArmed("authenticated_timeline_proof_unavailable")

    def status(self, issue: int, state: str, expected: Any) -> None:
        raise PortNotArmed("mutation_disabled")
