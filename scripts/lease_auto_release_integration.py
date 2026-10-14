"""Ensamblaje de diagnóstico V3: colector autenticado -> Snapshot -> decisor.

No implementa un escritor ni certifica ausencia de actividad. El decisor
existente y el executor conservan todas sus puertas. Hasta que exista una
fuente integral de inactividad, esta superficie solo ofrece un preview
fail-closed, sin credenciales ni transporte de escritura propios.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from scripts.lease_activity_collector import collect_activity
from scripts.lease_auto_release import Decision
from scripts.lease_auto_release_run import decision_from_snapshot
from scripts.lease_release_executor import Snapshot, _trusted

UTC_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
ACTIVE = frozenset({"estado: reservado", "estado: en revisión",
                    "estado: requiere recuperación"})


@dataclass(frozen=True)
class IntegrationPreview:
    """No lleva UUID/SHA ni permite elevar resultados a autorización."""
    issue: int
    state: str
    action: str
    reason: str

    @property
    def release_authorized(self) -> bool:
        return False


def _unknown(issue: int, reason: str) -> IntegrationPreview:
    return IntegrationPreview(issue, "UNKNOWN", "unknown", reason)


def preview_integrated_activity(api: Any, port: Any, issue: Any,
                                *, now: Any) -> IntegrationPreview:
    """Cruza dos lecturas completas sin inferir inactividad ni escribir.

    collect_activity sólo acredita presencia reciente; una ausencia de push
    no es prueba de inactividad. Port.read autentica adicionalmente #767,
    fase, reviews, cuota y marker V3 en su propia frontera. Exigimos exacta
    coincidencia de las identidades en ambas superficies; el preview jamás
    autoriza mark_recovery, release o transiciones de Coordinación.
    """
    if type(issue) is not int or issue <= 0:
        return _unknown(0, "invalid_issue")
    if type(now) is not datetime or now.tzinfo is None:
        return _unknown(issue, "invalid_clock")
    try:
        if now.utcoffset() is None:
            return _unknown(issue, "invalid_clock")
        report = collect_activity(api, issue, now=now)
        if (type(report) is not dict
                or report.get("evidence_complete") is not True
                or report.get("issue_number") != issue
                or report.get("status") not in ACTIVE
                or type(report.get("ci_running")) is not bool
                or type(report.get("last_activity_at")) is not str
                or UTC_STAMP.fullmatch(report["last_activity_at"]) is None):
            return _unknown(issue, "collector_unknown")
        last = datetime.fromisoformat(
            report["last_activity_at"].replace("Z", "+00:00"))
        if last > now.astimezone(timezone.utc):
            return _unknown(issue, "future_activity")
        snapshot = port.read(issue)
        if (not _trusted(snapshot) or snapshot.marker.get("active") is not True
                or snapshot.issue != issue
                or snapshot.now.astimezone(timezone.utc) != now.astimezone(timezone.utc)
                or report.get("repo") != getattr(api, "repo", None)
                or snapshot.repository_id != report.get("repository_id")
                or snapshot.owner != report.get("owner")
                or snapshot.reservation_id != report.get("lease_id")
                or snapshot.branch != report.get("branch")
                or snapshot.branch_sha != report.get("branch_sha")
                or snapshot.status != report.get("status")
                or snapshot.last_activity_at.astimezone(timezone.utc) != last
                or snapshot.ci_running != report["ci_running"]
                or type(report.get("rate_remaining")) is not int
                or type(report.get("rate_limit")) is not int
                or snapshot.rate_limit != report["rate_limit"]
                or snapshot.rate_remaining > report["rate_remaining"]):
            return _unknown(issue, "inconsistent_authenticated_sources")
        decision: Decision = decision_from_snapshot(snapshot)
        # Un preview no es autoridad: aunque ambos lectores devuelvan
        # datos positivos, nunca expone una acción que pueda liberar V3.
        if type(decision) is not Decision:
            return _unknown(issue, "invalid_decision")
        if decision.action not in ("unknown", "wait"):
            return _unknown(issue, "inactivity_not_proven")
        return IntegrationPreview(issue, "read_only", decision.action,
                                  decision.reason)
    except Exception:
        # Sin nombres de usuario, payloads, headers ni tokens en errores.
        return _unknown(issue, "unverifiable_integration")
