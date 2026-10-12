#!/usr/bin/env python3
"""Frontera REST de solo lectura para futuras liberaciones V3.

NO implementa CAS ni serialización compartida: hasta contar con una prueba
completa de *ausencia* de actividad, ningún Snapshot de este Port puede
autorizar a lease_release_executor a escribir. El resultado RECENT_ACTIVITY
solo acredita una observación positiva acotada, nunca inactividad.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
            if (type(report) is not dict or report.get("status") == UNKNOWN
                    or report.get("evidence_complete") is not True
                    or report.get("issue_number") != issue):
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
