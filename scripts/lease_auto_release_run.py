#!/usr/bin/env python3
"""Runner inyectable para reservas V3, desconectado del cron mutante.

Sin transporte GitHub, credenciales, lectura de variables de entorno ni
entrypoint operativo. El feature flag, la puerta de mutación y dry-run son
controles separados: ninguno se infiere de un resultado del decisor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.lease_auto_release import Decision, Evidence, decide
from scripts.lease_release_executor import Result, Snapshot, execute


@dataclass(frozen=True)
class CycleReport:
    """Resultados por Issue; ninguna conclusión certifica publicación."""
    state: str
    results: tuple[tuple[int, Result], ...]


def decision_from_snapshot(snapshot: Any) -> Decision:
    """Adaptador tipado, sin otorgar autoridad distinta a la del Port."""
    if type(snapshot) is not Snapshot:
        return Decision("unknown", "invalid_snapshot")
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
