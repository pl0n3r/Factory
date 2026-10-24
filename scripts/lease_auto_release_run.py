#!/usr/bin/env python3
"""Runner inyectable para reservas V3, desconectado del cron mutante.

Sin transporte GitHub, credenciales, lectura de variables de entorno ni
entrypoint operativo. El feature flag, la puerta de mutación y dry-run son
controles separados: ninguno se infiere de un resultado del decisor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any

from scripts.lease_github_port import Inspection, LeaseGithubPort, RECENT, UNKNOWN

from scripts.lease_auto_release import Decision, Evidence, decide
from scripts.lease_release_executor import (
    Result, Snapshot, _eligible, _trusted, execute,
)
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch


# Sólo motivos enumerados; los mensajes externos no se convierten en logs.
_OBSERVER_UNKNOWN_REASONS = frozenset({
    "collector_unknown", "future_activity", "inconsistent_authenticated_sources",
    "review_evidence_unknown", "review_veto_inconsistent", "invalid_decision",
    "inactivity_not_proven", "unverifiable_integration", "invalid_clock",
    "repository_not_authorized", "repository_identity_unknown", "observer_failed",
})


def sanitized_unknown_observer_reason(raw: Any, issue: int) -> str:
    """Preserva una causa UNKNOWN de whitelist sin conferir autoridad."""
    fallback = "unverifiable_observation"
    if type(raw) is not str or len(raw) > 4096 or type(issue) is not int or issue <= 0:
        return fallback

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    try:
        record = json.loads(raw, object_pairs_hook=unique_keys)
    except (TypeError, ValueError):
        return fallback
    if (type(record) is not dict
            or set(record) != {
                "issue", "state", "action", "reason", "activity_age_minutes",
                "activity_source", "release_authorized", "lock_verified",
                "cas_verified", "mutations",
            }
            or type(record["issue"]) is not int or record["issue"] != issue
            or record["state"] != "UNKNOWN" or record["action"] != "unknown"
            or type(record["reason"]) is not str
            or record["reason"] not in _OBSERVER_UNKNOWN_REASONS
            or record["activity_age_minutes"] is not None
            or record["activity_source"] is not None
            or record["release_authorized"] is not False
            or record["lock_verified"] is not False
            or record["cas_verified"] is not False
            or type(record["mutations"]) is not int or record["mutations"] != 0):
        return fallback
    return record["reason"]


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
    @property
    def release_authorized(self) -> bool:
        # Read-only por construcción: no puede inyectarse True en __init__
        # ni con dataclasses.replace().
        return False


@dataclass(frozen=True)
class RecentActivityObservation:
    """Resumen público mínimo: nunca incluye UUID, owner ni cuerpos."""
    issue: int
    state: str
    libera_en_min: int | None
    @property
    def release_authorized(self) -> bool:
        # Read-only por construcción: no puede inyectarse True en __init__
        # ni con dataclasses.replace().
        return False


@dataclass(frozen=True)
class RecentActivityReport:
    """Lectura positiva individual; no certifica inactividad ni CAS."""
    state: str
    observations: tuple[RecentActivityObservation, ...]
    @property
    def release_authorized(self) -> bool:
        # Read-only por construcción: no puede inyectarse True en __init__
        # ni con dataclasses.replace().
        return False


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


@dataclass(frozen=True)
class PhaseACandidateAudit:
    """Conciliación offline no autoritativa: nunca aprueba activación."""
    status: str
    valid_cycles: int
    observed_minutes: int
    hypothetical_releases: int
    qa_correct: int

    @property
    def release_authorized(self) -> bool:
        return False


def evaluate_phase_a_candidate(
    manifests: Any, run_receipts: Any, qa_reviews: Any, *, repository: Any,
) -> PhaseACandidateAudit:
    """Evalúa 24 h / 100 ciclos sin convertir un artefacto en autoridad.

    Cada run_receipt DEBE obtenerse separadamente de GitHub autenticado por QA.
    Este evaluador puro NO autentica su origen ni comprueba pushes negativos;
    incluso el resultado candidato requiere validación humana y puertas V3.
    """
    reject = PhaseACandidateAudit("invalid_evidence", 0, 0, 0, 0)
    if (type(repository) is not str
            or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None
            or type(manifests) is not list or not 1 <= len(manifests) <= 500
            or type(run_receipts) is not list
            or len(run_receipts) != len(manifests)
            or type(qa_reviews) is not list or len(qa_reviews) > 2000):
        return reject

    receipts: dict[int, dict[str, Any]] = {}
    dates = []
    release_keys = set()
    for receipt in run_receipts:
        if type(receipt) is not dict:
            return reject
        run = receipt.get("id")
        when = receipt.get("completed_at")
        if (type(run) is not int or run <= 0 or run in receipts
                or receipt.get("repository") != repository
                or receipt.get("event") != "schedule"
                or receipt.get("status") != "completed"
                or receipt.get("conclusion") != "success"
                or receipt.get("artifact_attested") is not True
                or type(receipt.get("head_sha")) is not str
                or re.fullmatch(r"[a-f0-9]{40}", receipt["head_sha"]) is None
                or type(when) is not str
                or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", when) is None):
            return reject
        try:
            at = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            return reject
        dates.append(at)
        receipts[run] = receipt

    observed_runs = set()
    row_keys = {
        "issue", "state", "action", "reason", "activity_age_minutes",
        "activity_source", "release_authorized", "lock_verified",
        "cas_verified", "mutations",
    }
    for m in manifests:
        if type(m) is not dict:
            return reject
        run_id = m.get("run_id")
        if (type(run_id) is not str or not run_id.isascii()
                or re.fullmatch(r"[1-9][0-9]*", run_id) is None):
            return reject
        run = int(run_id)
        receipt = receipts.get(run)
        rows = m.get("issues")
        if (receipt is None or run in observed_runs
                or m.get("schema_version") != 1
                or type(m.get("schema_version")) is not int
                or m.get("repository") != repository
                or m.get("head_sha") != receipt["head_sha"]
                or m.get("status") != "candidate_terminal"
                or m.get("terminal_certified") is not False
                or m.get("release_authorized") is not False
                or type(m.get("mutations")) is not int or m["mutations"] != 0
                or type(m.get("valid_observations")) is not int
                or type(m.get("unknown_observations")) is not int
                or m["unknown_observations"] != 0
                or type(rows) is not list or not 1 <= len(rows) <= 10
                or m["valid_observations"] != len(rows)):
            return reject
        observed_runs.add(run)
        seen_issues = set()
        for row in rows:
            if (type(row) is not dict or set(row) != row_keys
                    or type(row.get("issue")) is not int or row["issue"] <= 0
                    or row["issue"] in seen_issues
                    or row.get("state") != "read_only"
                    or row.get("action") not in ("wait", "mark_recovery", "release")
                    or type(row.get("reason")) is not str
                    or re.fullmatch(r"[a-z][a-z0-9_]{0,79}", row["reason"]) is None
                    or row.get("release_authorized") is not False
                    or row.get("lock_verified") is not False
                    or row.get("cas_verified") is not False
                    or type(row.get("mutations")) is not int
                    or row["mutations"] != 0):
                return reject
            age, source = row.get("activity_age_minutes"), row.get("activity_source")
            if (age is not None and (type(age) is not int or not 0 <= age <= 525600)
                    or source not in (None, "reservation_marker", "workflow_push",
                                      "issue_comment", "repository_push")):
                return reject
            # Las reglas de decisión del decisor son condiciones NECESARIAS,
            # no pruebas de una auditoría negativa completa. Un manifiesto
            # que dice release a los 7 minutos contradice el umbral real,
            # incluso si un registro de QA lo llama "correct".
            if row["action"] == "mark_recovery" and (
                    row["reason"] != "inactive_30_minutes"
                    or type(age) is not int or age < 30 or source is None):
                return reject
            if row["action"] == "release" and (
                    row["reason"] != "inactive_after_recovery_grace"
                    or type(age) is not int or age < 40 or source is None):
                return reject
            # Sólo motivos del decisor para una V3 activa en construcción.
            # Ningún nombre de motivo inventado acredita un ciclo de QA.
            if row["action"] == "wait":
                if row["reason"] not in (
                        "activity_window", "recovery_grace",
                        "protected_or_active_work"):
                    return reject
                if row["reason"] == "activity_window" and (
                        type(age) is not int or age >= 30 or source is None):
                    return reject
                if row["reason"] == "recovery_grace" and (
                        type(age) is not int or age < 30 or source is None):
                    return reject
            seen_issues.add(row["issue"])
            if row["action"] == "release":
                release_keys.add((run, row["issue"]))

    reviewed = set()
    false_positive = False
    for qa in qa_reviews:
        if (type(qa) is not dict or set(qa) != {
                "run_id", "issue", "verdict", "evidence_ref"}
                or type(qa.get("run_id")) is not int
                or type(qa.get("issue")) is not int
                or (qa["run_id"], qa["issue"]) not in release_keys
                or (qa["run_id"], qa["issue"]) in reviewed
                or qa.get("verdict") not in ("correct", "incorrect")
                or type(qa.get("evidence_ref")) is not str
                or not 8 <= len(qa["evidence_ref"]) <= 256):
            return reject
        reviewed.add((qa["run_id"], qa["issue"]))
        false_positive |= qa["verdict"] == "incorrect"
    period = int((max(dates) - min(dates)) / timedelta(minutes=1))
    status = (
        "false_positive" if false_positive else
        "qa_incomplete" if reviewed != release_keys else
        "insufficient_observation" if len(observed_runs) < 100 or period < 1440 else
        "candidate_only"
    )
    return PhaseACandidateAudit(
        status, len(observed_runs), period, len(release_keys),
        sum(qa["verdict"] == "correct" for qa in qa_reviews),
    )


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
    # Cota conservadora: un execute() puede liberar una reserva y requiere
    # comentario+etiqueta atómicos. Nunca intentar más de tres por ciclo
    # mutante, incluso con fallos parciales o decisiones contradictorias.
    max_attempts = len(issues) if dry_run else 3
    mutation_attempts = 0
    results: list[tuple[int, Result]] = []
    for issue in sorted(issues):
        if mutation_attempts >= max_attempts:
            results.append((issue, Result("wait", "cycle_write_cap")))
            continue
        result = execute(
            issue, port, decision_from_snapshot,
            feature_enabled=True, dry_run=dry_run,
        )
        results.append((issue, result))
        if result.write_state != "none":
            mutation_attempts += 1
    return CycleReport(state, tuple(results))
