#!/usr/bin/env python3
"""Runner inyectable para reservas V3, desconectado del cron mutante.

Sin transporte GitHub, credenciales, lectura de variables de entorno ni
entrypoint operativo. El feature flag, la puerta de mutación y dry-run son
controles separados: ninguno se infiere de un resultado del decisor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scripts.lease_github_port import Inspection, LeaseGithubPort, RECENT, UNKNOWN

from scripts.lease_auto_release import Decision, Evidence, decide
from scripts.lease_release_executor import (
    Result, Snapshot, _eligible, _trusted, execute,
)
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch


@dataclass(frozen=True)
class CycleReport:
    """Resultados por Issue; ninguna conclusión certifica publicación."""
    state: str
    results: tuple[tuple[int, Result], ...]


@dataclass(frozen=True)
class RecoveryInventory:
    """Censo agregado no autoritativo; NO prueba inactividad ni permite liberar."""
    open_issues: int
    recovery: int
    reserved: int
    in_review: int
    release_authorized: bool = False


@dataclass(frozen=True)
class RecentActivityObservation:
    """Resumen público mínimo: nunca incluye UUID, owner ni cuerpos."""
    issue: int
    state: str
    libera_en_min: int | None
    release_authorized: bool = False


@dataclass(frozen=True)
class RecentActivityReport:
    """Lectura positiva individual; no certifica inactividad ni CAS."""
    state: str
    observations: tuple[RecentActivityObservation, ...]
    release_authorized: bool = False


def observe_recent_activity(issues: Any, port: Any, *, now: Any) -> RecentActivityReport:
    """Expone actividad RECIENTE autenticada, con presupuesto de 1 hoja/ciclo.

    Jamás usa Port.read/lock/append/status. No interpreta UNKNOWN como ausencia
    de actividad y no habilita el ejecutor aunque el caller pida mutaciones.
    La API de inspección comprueba el #767 absoluto antes y después del GET.
    """
    if (type(issues) is not list or len(issues) != 1
            or type(issues[0]) is not int or issues[0] <= 0
            or type(port) is not LeaseGithubPort
            or type(now) is not datetime or now.tzinfo is None):
        return RecentActivityReport("invalid_input", ())
    try:
        if now.utcoffset() is None:
            return RecentActivityReport("invalid_input", ())
    except (OverflowError, TypeError, ValueError, RuntimeError):
        return RecentActivityReport("invalid_input", ())
    issue = issues[0]
    unknown = RecentActivityObservation(issue, UNKNOWN, None)
    try:
        item = port.inspect(issue, now=now)
        if (type(item) is not Inspection or item.issue != issue
                or item.release_authorized is not False
                or item.state not in (RECENT, UNKNOWN)):
            return RecentActivityReport("read_only", (unknown,))
        if item.state == UNKNOWN:
            return RecentActivityReport("read_only", (unknown,))
        # Únicamente el inspector auténtico puede acreditar actividad
        # positiva, pero NUNCA inferir liberación desde este plazo.
        if (type(item.libera_en_min) is not int
                or not 1 <= item.libera_en_min <= 40
                or type(item.lease_id) is not str
                or type(item.branch_sha) is not str):
            return RecentActivityReport("read_only", (unknown,))
        return RecentActivityReport("read_only", (
            RecentActivityObservation(issue, RECENT, item.libera_en_min),
        ))
    except Exception:
        return RecentActivityReport("read_only", (unknown,))


def inventory_from_paginated_issues(pages: Any) -> RecoveryInventory | None:
    """Solo arrays de páginas GitHub completos en estructura y sin datos privados.

    La paginación la efectúa gh api --paginate --slurp; este contador nunca
    certifica liveness, exclusividad ni ausencia de actualizaciones concurrentes.
    """
    if (type(pages) is not list or not 1 <= len(pages) <= 100
            # Una última página llena sin página vacía de cierre podría ser
            # un prefijo truncado; no publicar un censo aparentemente íntegro.
            or type(pages[-1]) is not list or len(pages[-1]) == 100):
        return None
    seen: set[int] = set()
    open_count = recovery = reserved = in_review = 0
    for idx, page in enumerate(pages):
        if (type(page) is not list or len(page) > 100
                or (idx < len(pages) - 1 and len(page) != 100)):
            return None
        for issue in page:
            if (type(issue) is not dict or type(issue.get("number")) is not int
                    or issue["number"] <= 0 or issue["number"] in seen
                    or issue.get("state") != "open"
                    or type(issue.get("labels")) is not list):
                return None
            seen.add(issue["number"])
            # La API /issues devuelve PRs además de issues.
            if "pull_request" in issue:
                if type(issue["pull_request"]) is not dict:
                    return None
                continue
            open_count += 1
            labels = issue["labels"]
            if any(type(label) is not dict
                   or type(label.get("name")) is not str
                   or not label["name"] or label["name"] != label["name"].strip()
                   for label in labels):
                return None
            names = [label["name"] for label in labels]
            # GitHub trata etiquetas como nombres sin distinción de caja.
            # Dos alias o "ESTADO: ..." no certifican el mismo censo.
            if len(names) != len({name.casefold() for name in names}):
                return None
            if any(name.casefold().startswith("estado:")
                   and not name.startswith("estado: ") for name in names):
                return None
            statuses = [name for name in names if name.startswith("estado: ")]
            if len(statuses) > 1:
                return None
            if "estado: requiere recuperación" in names:
                recovery += 1
            if "estado: reservado" in names:
                reserved += 1
            if "estado: en revisión" in names:
                in_review += 1
    return RecoveryInventory(open_count, recovery, reserved, in_review)




def inventory_after_switch_recheck(
    before: Any, after: Any, pages: Any,
) -> RecoveryInventory | None:
    """Publicar censo solo con dos lecturas canónicas RUNNING de #767.

    No ofrece autoridad de release: una pausa durante el censo invalida
    la instantánea aunque ya se hayan leído todas las páginas. Validar
    state=closed explícitamente porque ramas previas del parser compartido
    no exigían ese campo.
    """
    for issue in (before, after):
        if (type(issue) is not dict or issue.get("state") != "closed"
                or type(issue.get("number")) is not int):
            return None
        verdict = evaluate_unattended_kill_switch(issue)
        if verdict.state != "RUNNING" or verdict.global_pause is not False:
            return None
    return inventory_from_paginated_issues(pages)


def decision_from_snapshot(snapshot: Any) -> Decision:
    """Adaptador tipado, sin otorgar autoridad distinta a la del Port."""
    if type(snapshot) is not Snapshot:
        return Decision("unknown", "invalid_snapshot")
    # Una liberación parcialmente escrita no equivale a una V3 activa.
    # Reconciliar exclusivamente el marker terminal auténtico, con todos
    # los vetos de autoridad/tiempo del ejecutor; éste revalida lock, CAS,
    # procedencia de nota y etiqueta antes de cualquier cambio de estado.
    if (type(snapshot.marker) is dict
            and snapshot.marker.get("active") is False):
        if (_trusted(snapshot, allow_partial=True)
                and _eligible(snapshot, "release")):
            return Decision("release", "authenticated_partial_reconciliation")
        return Decision("unknown", "partial_marker_not_authorized")
    return decide(Evidence(
        now=snapshot.now,
        last_activity_at=snapshot.last_activity_at,
        recovery_since=snapshot.recovery_since,
        status=snapshot.status,
        phase=snapshot.phase,
        issue_open=snapshot.issue_open,
        v3_active=snapshot.marker.get("active") is True
        if type(snapshot.marker) is dict else False,
        lease_id=snapshot.reservation_id,
        owner=snapshot.owner,
        branch_sha=snapshot.branch_sha,
        branch_present=snapshot.authenticated,
        evidence_complete=snapshot.complete and snapshot.authenticated,
        trusted_phase=snapshot.authenticated,
        kill_switch_running=snapshot.kill_switch_running,
        ci_running=snapshot.ci_running,
        changes_requested=snapshot.changes_requested,
        owner_recovered=snapshot.owner_recovered,
        rate_remaining=snapshot.rate_remaining,
        rate_limit=snapshot.rate_limit,
    ))


def run_cycle(
    issues: Any,
    port: Any,
    *,
    feature_enabled: bool = False,
    dry_run: bool = True,
    mutations_authorized: bool = False,
) -> CycleReport:
    """Evalúa un lote acotado; el contrato de escritura reside en execute().

    No enumera Issues ni fabrica Snapshots. Un futuro Port debe autenticar
    origen, paginación íntegra, continuidad de push, #767 global y lock/CAS
    real ANTES de autorizar cualquier escritura. Nunca activar desde cron por
    la sola presencia de esta función.
    """
    flags = (feature_enabled, dry_run, mutations_authorized)
    if any(type(flag) is not bool for flag in flags):
        return CycleReport("invalid_flags", ())
    if (type(issues) is not list or len(issues) > 100
            or any(type(issue) is not int or issue <= 0 for issue in issues)
            or len(issues) != len(set(issues))):
        return CycleReport("invalid_batch", ())
    if not feature_enabled:
        return CycleReport(
            "feature_disabled",
            tuple((issue, Result("wait", "feature_disabled"))
                  for issue in sorted(issues)),
        )
    if not dry_run and not mutations_authorized:
        return CycleReport(
            "mutation_gate_off",
            tuple((issue, Result("wait", "mutation_gate_off"))
                  for issue in sorted(issues)),
        )
    state = "dry_run" if dry_run else "explicit_fake_or_authorized_port"
    results = tuple(
        (issue, execute(
            issue, port, decision_from_snapshot,
            feature_enabled=True, dry_run=dry_run,
        ))
        for issue in sorted(issues)
    )
    return CycleReport(state, results)
