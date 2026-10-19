#!/usr/bin/env python3
"""Adaptador GitHub del Port de liberaciones V3.

Por defecto es GET-only: `inspect`/`recovery_*` sólo observan y
RECENT_ACTIVITY acredita una observación positiva acotada, nunca inactividad.
Las escrituras (`read` completo, `lock`, `append`, `status`) exigen
`armed=True` explícito y una API autenticada; el lock es el grupo de
concurrency de Coordinación y cada escritura es CAS sobre UUID/SHA/marker/pin.
Ningún merge ni dispatch lo arma: lo decide el runner con su feature flag.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from math import ceil
import base64
import hashlib
import json
import re
from typing import Any, Callable

from scripts.lease_release_executor import (
    ACTIVE, AVAILABLE, RECOVERY, SESSION_RE, SHA, RecoveryLabelProof, RecoveryNoteProof, Snapshot,
    _trusted, _note_ok, _recovery_label_ok, _utc,
)
from scripts.aceptacion_kit import contract_fingerprint
from scripts.coordinar_trabajo import reservation_from_text
from scripts.politica_kit import parse_phase_payload
from scripts.orquestador_kit import parse_task_marker, task_marker_fingerprint

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
    lease_id: str | None = None
    branch_sha: str | None = None
    last_activity_at: str | None = None
    libera_en_min: int | None = None  # Cota inferior; nunca autoridad.

    @property
    def release_authorized(self) -> bool:
        """El inspector no emite permisos de release, ni con kwargs forzados."""
        return False


_RECENT_STATES = frozenset({
    "estado: reservado", "estado: en revisión", "estado: requiere recuperación",
})
_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


def _recent_report_ok(report: Any, issue: int, repo: Any, now: Any) -> bool:
    """Defensa adicional del límite inspector/collector; nunca ausencia."""
    if (type(report) is not dict or report.get("evidence_complete") is not True
            or type(report.get("status")) is not str
            or report["status"] not in _RECENT_STATES
            or type(repo) is not str or type(report.get("repo")) is not str
            or report["repo"] != repo
            or type(report.get("issue_number")) is not int
            or report["issue_number"] != issue
            or type(report.get("repository_id")) is not int
            or report["repository_id"] <= 0
            or type(report.get("owner")) is not str
            or not report["owner"]
            or type(report.get("branch")) is not str
            or report["branch"] != f"trabajo/issue-{issue}"
            or type(report.get("lease_id")) is not str
            or SESSION_RE.fullmatch(report["lease_id"]) is None
            or type(report.get("branch_sha")) is not str
            or SHA.fullmatch(report["branch_sha"]) is None
            or type(report.get("ci_running")) is not bool
            or type(report.get("rate_limit")) is not int
            or type(report.get("rate_remaining")) is not int
            or report["rate_limit"] <= 0 or report["rate_remaining"] < 0
            or report["rate_remaining"] > report["rate_limit"]
            # El GET final al switch #767 aún consume una petición.
            # Una cuota exactamente del 20 % antes de ese GET no es
            # suficiente para acreditar el presupuesto del ciclo entero.
            or (report["rate_remaining"] - 1) * 5 < report["rate_limit"]
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


def _pinned_task_fingerprint(body: Any) -> str:
    """Pin del plan sin claves JSON dobles ni encabezados ocultos.

    parse_task_marker() sigue siendo la fuente de verdad del esquema V1,
    pero su parser JSON estándar acepta claves duplicadas. El Port
    autenticado debe rechazar ambigüedad antes de comprobar el pin V3.
    """
    if type(body) is not str:
        raise ValueError("invalid_task_body")
    headers = re.findall(
        r"<!--\s*factory-plan-task\b", body, flags=re.IGNORECASE)
    if len(headers) != 1:
        raise ValueError("ambiguous_task_marker")
    match = re.search(r"<!-- factory-plan-task (\{[^\r\n]*\}) -->", body)
    if match is None:
        raise ValueError("malformed_task_marker")

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate_task_key")
            obj[key] = value
        return obj

    raw = json.loads(match.group(1), object_pairs_hook=unique_keys)
    parsed = parse_task_marker(body)
    if type(raw) is not dict or parsed != raw:
        raise ValueError("untrusted_task_marker")
    pin = task_marker_fingerprint(parsed)
    if type(pin) is not str:
        raise ValueError("task_pin_unavailable")
    return pin


def _verified_recovery_timeline(events: Any, note: Any, expected: Any) -> RecoveryLabelProof:
    """Prueba pura de etiquetado por bot: no demuestra lock ni CAS."""
    if (type(events) is not list or type(expected) is not Snapshot
            or not _note_ok(note, expected) or note.count != 1):
        raise ValueError("untrusted_timeline")
    matches: list[datetime] = []
    for event in events:
        if type(event) is not dict or type(event.get("event")) is not str:
            raise ValueError("invalid_event")
        if event["event"] not in ("labeled", "unlabeled"):
            continue
        label = event.get("label")
        if type(label) is not dict or type(label.get("name")) is not str:
            raise ValueError("missing_label")
        if label["name"] != "estado: requiere recuperación":
            continue
        author = event.get("actor")
        stamp = event.get("created_at")
        if (type(author) is not dict
                or type(author.get("login")) is not str
                or author["login"] != "github-actions[bot]"
                or type(author.get("type")) is not str
                or author["type"] != "Bot" or type(stamp) is not str
                or _STAMP.fullmatch(stamp) is None):
            raise ValueError("untrusted_label_actor_or_time")
        at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if at > _utc(expected.now):
            raise ValueError("future_event")
        if event["event"] == "unlabeled":
            raise ValueError("recovery_relabelled")
        matches.append(at)
    if len(matches) != 1:
        raise ValueError("recovery_label_count")
    proof = RecoveryLabelProof(
        complete=True, authenticated=True, count=1,
        owner=expected.owner, reservation_id=expected.reservation_id,
        branch=expected.branch, branch_sha=expected.branch_sha,
        label="estado: requiere recuperación", created_at=matches[0],
        author="github-actions[bot]",
    )
    if not _recovery_label_ok(note, proof, expected):
        raise ValueError("label_not_bound_to_note_and_snapshot")
    return proof


class LeaseGithubPort:
    """Adaptador inyectado: únicamente GET sobre una API autenticada.

    No importa tokens, no abre sockets y no acepta que el caller proporcione
    otro origen para el interruptor global. Una excepción se reduce a UNKNOWN
    sin exponer cuerpos, URLs con credenciales ni detalles privados.
    """

    def __init__(self, api: Any, *, armed: bool = False,
                 concurrency_group: str | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self._api = api
        # Escritura SOLO con armed=True explícito; el valor por defecto
        # conserva el Port GET-only y ningún merge/dispatch lo activa.
        self._armed = armed is True
        self._group = concurrency_group
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _need_armed(self) -> None:
        if (not self._armed or getattr(self._api, "authenticated", False) is not True):
            raise PortNotArmed("mutation_disabled")

    def _pages(self, path: str) -> list[Any]:
        """Lista completa paginada con página centinela vacía; si no, error."""
        rows: list[Any] = []
        for page in range(1, 11):
            batch = self._api.request("GET", f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
            if type(batch) is not list or len(batch) > 100:
                raise ValueError("invalid_page")
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise ValueError("pagination_over_limit")

    def _running(self) -> bool:
        obj = self._api.request("GET", GLOBAL_SWITCH)
        # El marcador RUNNING no basta si #767 fue reabierto: exigir el
        # estado cerrado de la fuente canónica antes de leer otras reservas.
        if type(obj) is not dict or obj.get("state") != "closed":
            return False
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
            # Cota inferior: 30 minutos inactivo + 10 de gracia. La prueba
            # positiva de actividad NO permite declarar ausencia de actividad.
            activity = datetime.fromisoformat(
                report["last_activity_at"].replace("Z", "+00:00"))
            seconds = (activity + timedelta(minutes=40)
                       - now.astimezone(timezone.utc)).total_seconds()
            if seconds <= 0:
                return invalid
            # Volver a leer #767: RUNNING no es un permiso duradero.
            if not self._running():
                return invalid
            return Inspection(
                RECENT, issue,
                lease_id=report["lease_id"],
                branch_sha=report["branch_sha"],
                last_activity_at=report["last_activity_at"],
                libera_en_min=ceil(seconds / 60),
            )
        except Exception:
            return invalid

    def read(self, issue: int) -> Snapshot:
        """Snapshot estricto: CI activo prohíbe toda mutación."""
        return self._read_snapshot(issue, observation_only=False)

    def read_observation(self, issue: int) -> Snapshot:
        """Vista de diagnóstico; no concede autoridad de escritura."""
        return self._read_snapshot(issue, observation_only=True)

    def _read_snapshot(self, issue: int, *, observation_only: bool) -> Snapshot:
        """Verifica la misma evidencia; solo diagnóstico admite veto CI."""
        try:
            # Observación autenticada no necesita armar una capacidad mutante.
            # read()/lock()/append()/status() conservan el guard estricto.
            if observation_only:
                if getattr(self._api, "authenticated", False) is not True:
                    raise PortNotArmed("unauthenticated_observation")
            else:
                self._need_armed()
            if type(issue) is not int or issue <= 0 or not self._running():
                raise ValueError("untrusted_scope")
            now = self._clock()
            repo_name = getattr(self._api, "repo", None)
            latest = self._latest_bot_marker(repo_name, issue)
            api = self._api
            if latest is not None and latest[1].get("active") is False:
                # Marker de liberación ya publicado (estado parcial): el
                # recolector sólo entiende reservas activas, así que se
                # evalúa la actividad SIN ese comentario del bot.
                api = _WithoutComment(self._api, issue, latest[0])
            report = collect_activity(api, issue, now=now)
            if (type(report) is not dict or report.get("evidence_complete") is not True
                    or report.get("status") not in ACTIVE
                    or report.get("issue_number") != issue):
                raise ValueError("incomplete_activity")
            repo = report["repo"]
            issue_obj = self._api.request("GET", f"/repos/{repo}/issues/{issue}")
            if (type(issue_obj) is not dict or issue_obj.get("state") != "open"
                    or "pull_request" in issue_obj):
                raise ValueError("issue_not_open")
            lease_id, branch = report["lease_id"], report["branch"]
            marker = latest[1] if latest is not None else None
            if (marker is None or marker.get("reservation_id") != lease_id
                    or marker.get("branch") != branch
                    or marker.get("owner") != report["owner"]):
                raise ValueError("marker_mismatch")
            pin = _pinned_task_fingerprint(issue_obj.get("body"))
            if pin != marker.get("task_marker_sha256"):
                raise ValueError("task_pin_mismatch")
            last = datetime.fromisoformat(report["last_activity_at"].replace("Z", "+00:00"))
            status = report["status"]
            since = None
            if status == RECOVERY:
                since = self._recovery_since(repo, issue)
            owner_recovered = since is not None and last > since
            fingerprint = hashlib.sha256(json.dumps({
                "issue": issue, "lease": lease_id, "sha": report["branch_sha"],
                "status": status, "marker": marker, "pin": pin,
                "activity": report["last_activity_at"],
            }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            snapshot = Snapshot(
                issue=issue, repository_id=report["repository_id"],
                reservation_id=lease_id, owner=report["owner"], branch=branch,
                branch_sha=report["branch_sha"], status=status,
                phase=self._phase(repo), now=now, last_activity_at=last,
                recovery_since=since, marker=marker, fingerprint=fingerprint,
                complete=True, authenticated=True, issue_open=True,
                kill_switch_running=self._running(),
                ci_running=report["ci_running"] is True,
                changes_requested=self._changes_requested(repo, branch),
                owner_recovered=owner_recovered,
                rate_remaining=report["rate_remaining"],
                rate_limit=report["rate_limit"],
            )
            if not _trusted(snapshot, allow_partial=True):
                if not (observation_only and snapshot.ci_running is True
                        and _trusted(replace(snapshot, ci_running=False),
                                     allow_partial=True)):
                    raise ValueError("untrusted_snapshot")
            return snapshot
        except PortNotArmed:
            raise
        except Exception:
            raise PortNotArmed("complete_inactivity_proof_unavailable") from None

    def _latest_bot_marker(self, repo: Any, issue: int) -> tuple[int, dict[str, Any]] | None:
        """(id del comentario, marker) del último marker V3 de github-actions[bot]."""
        found = None
        for comment in self._pages(f"/repos/{repo}/issues/{issue}/comments"):
            user = comment.get("user") if type(comment) is dict else None
            if (type(user) is dict and user.get("login") == "github-actions[bot]"
                    and user.get("type") == "Bot"):
                marker = _bot_marker(comment.get("body"), allow_inactive=True)
                if marker is not None and type(comment.get("id")) is int:
                    found = (comment["id"], marker)  # el último autenticado manda
        return found

    def _phase(self, repo: str) -> str:
        meta = self._api.request("GET", f"/repos/{repo}/contents/datos.yml")
        if (type(meta) is not dict or meta.get("encoding") != "base64"
                or type(meta.get("content")) is not str):
            raise ValueError("phase_unavailable")
        return parse_phase_payload(base64.b64decode(meta["content"]).decode("utf-8"))

    def _recovery_since(self, repo: str, issue: int) -> datetime:
        events = self._pages(f"/repos/{repo}/issues/{issue}/events")
        stamps = [e["created_at"] for e in events
                  if type(e) is dict and e.get("event") == "labeled"
                  and (e.get("label") or {}).get("name") == RECOVERY
                  and (e.get("actor") or {}).get("login") == "github-actions[bot]"]
        if not stamps or _STAMP.fullmatch(stamps[-1]) is None:
            raise ValueError("recovery_event_missing")
        return datetime.fromisoformat(stamps[-1].replace("Z", "+00:00"))

    def _changes_requested(self, repo: str, branch: str) -> bool:
        from urllib.parse import quote

        head = quote(f"{repo.split('/')[0]}:{branch}", safe="")
        pulls = self._pages(f"/repos/{repo}/pulls?state=open&head={head}")
        blocked = False
        for pull in pulls:
            latest: dict[str, str] = {}
            for review in self._pages(f"/repos/{repo}/pulls/{pull['number']}/reviews"):
                latest[(review.get("user") or {}).get("login", "")] = review.get("state", "")
            blocked = blocked or "CHANGES_REQUESTED" in latest.values()
        return blocked

    def lock(self, group: str) -> Any:
        """Lock compartido con Coordinación = su grupo de concurrency de Actions.

        No crea un lock propio: exige que ESTE proceso corra bajo el mismo
        grupo `factory-coordination-<repo_id>` (declarado por el workflow).
        La verificación es inmediata, no al entrar al `with`.
        """
        self._need_armed()
        repo = getattr(self._api, "repo", None)
        meta = self._api.request("GET", f"/repos/{repo}")
        expected = f"factory-coordination-{meta.get('id') if type(meta) is dict else None}"
        if group != expected or self._group != expected:
            raise PortNotArmed("shared_v3_cas_lock_not_implemented")
        return nullcontext()

    def _cas(self, issue: int, expected: Any, *, same_fingerprint: bool) -> Snapshot:
        """Relee y exige mismo SHA/UUID/pin (identidad) antes de escribir."""
        current = self.read(issue)
        if (type(expected) is not Snapshot or current.issue != expected.issue
                or (current.repository_id, current.owner, current.reservation_id,
                    current.branch, current.branch_sha)
                != (expected.repository_id, expected.owner, expected.reservation_id,
                    expected.branch, expected.branch_sha)
                or current.status != expected.status
                or current.marker != expected.marker
                or (same_fingerprint and current.fingerprint != expected.fingerprint)):
            raise PortNotArmed("cas_conflict")
        return current

    def append(self, issue: int, body: str, expected: Any) -> None:
        self._need_armed()
        current = self._cas(issue, expected, same_fingerprint=True)
        if type(body) is not str or not 1 <= len(body) <= 4000:
            raise PortNotArmed("invalid_body")
        if body.startswith("<!-- condor-reserva "):
            want = dict(current.marker)
            want.update(active=False, reason="auto-inactivity-release")
            if _bot_marker(body, allow_inactive=True) != want:
                raise PortNotArmed("marker_not_canonical")
        elif not body.startswith("<!-- factory-lease-recovery "):
            raise PortNotArmed("body_not_allowed")
        repo = getattr(self._api, "repo")
        self._api.request("POST", f"/repos/{repo}/issues/{issue}/comments",
                          {"body": body})

    def recovery_note(self, issue: int, expected: Any, *,
                      _budget: list[int] | None = None) -> RecoveryNoteProof:
        """GET-only: verifica nota de bot y reserva exacta, nunca CAS.

        Se permite leer/probar esta evidencia, pero read/lock/append/status
        continúan desarmados. Un proof aislado NO acredita inactividad.
        """
        try:
            repo = getattr(self._api, "repo", None)
            if (not isinstance(expected, Snapshot) or (isinstance(issue, bool) or not isinstance(issue, int))
                    or issue != expected.issue or not _trusted(expected, allow_partial=True)
                    or type(repo) is not str
                    or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is None):
                raise ValueError("untrusted_expected")
            # La prueba compuesta nota→timeline→nota comparte un solo
            # presupuesto de GET. No reiniciarlo durante la relectura.
            if _budget is None:
                _budget = [0]
            if (type(_budget) is not list or len(_budget) != 1
                    or type(_budget[0]) is not int
                    or not 0 <= _budget[0] <= 32):
                raise ValueError("invalid_request_budget")
            calls = 0
            def charge() -> None:
                nonlocal calls
                calls += 1
                _budget[0] += 1
                if calls > 32 or _budget[0] > 32:
                    raise ValueError("request_budget")

            def get(endpoint: str) -> Any:
                charge()
                return self._api.request("GET", endpoint)

            def running_with_budget() -> bool:
                # Cada GET al #767 usa exactamente el mismo presupuesto
                # que el resto de lecturas, incluidas las de timeline.
                charge()
                return self._running()

            if not running_with_budget():
                raise ValueError("global_pause")
            quota = get("/rate_limit")
            core = quota.get("resources", {}).get("core", {}) if type(quota) is dict else {}
            remaining, limit = core.get("remaining"), core.get("limit")
            if (type(remaining) is not int or type(limit) is not int
                    or limit <= 0 or remaining > limit or remaining < 0
                    or remaining * 5 < limit):
                raise ValueError("quota")
            base = f"/repos/{repo}"
            identity = get(base)
            if (type(identity) is not dict or identity.get("full_name") != repo
                    or type(identity.get("id")) is not int
                    or identity["id"] != expected.repository_id):
                raise ValueError("repo_mismatch")
            path = f"{base}/issues/{issue}"
            initial = get(path)
            if (type(initial) is not dict or initial.get("state") != "open"
                    or type(initial.get("number")) is not int
                    or initial["number"] != issue
                    or type(initial.get("comments")) is not int
                    or not 1 <= initial["comments"] <= 500
                    or type(initial.get("updated_at")) is not str
                    or type(initial.get("body")) is not str
                    # El pin de aceptación de la V3 debe corresponder al
                    # contrato ejecutable REAL del Issue, no solo a la nota.
                    or contract_fingerprint(initial["body"]) !=
                       expected.marker["acceptance_sha256"]
                    # El pin de claims también pertenece al cuerpo ACTUAL
                    # del Issue; una edición del plan después de /tomar
                    # invalida el proof aunque la aceptación no cambie.
                    or _pinned_task_fingerprint(initial["body"]) !=
                       expected.marker["task_marker_sha256"]
                    or type(initial.get("labels")) is not list
                    # No ignorar etiquetas de tipo inesperado: son parte
                    # de la evidencia exacta que debe mantenerse íntegra.
                    or any(type(label) is not dict
                           or type(label.get("name")) is not str
                           or not label["name"]
                           for label in initial["labels"])
                    # GitHub label names are case-insensitive. Alias
                    # de Unicode/caja no puede fingir otro estado legítimo.
                    or len({label["name"].casefold()
                            for label in initial["labels"]})
                       != len(initial["labels"])
                    or type(initial.get("assignees")) is not list
                    or len(initial["assignees"]) != 1
                    or type(initial["assignees"][0]) is not dict
                    or type(initial["assignees"][0].get("login")) is not str
                    or initial["assignees"][0]["login"] != expected.owner):
                raise ValueError("issue_mismatch")
            state_labels = [
                z.get("name") for z in initial["labels"]
                if type(z) is dict and type(z.get("name")) is str
                and z["name"].casefold().startswith("estado:")
            ]
            if len(state_labels) != 1 or state_labels[0] != expected.status:
                raise ValueError("state_mismatch")
            branch_path = f"{base}/git/ref/heads/{expected.branch}"
            ref = get(branch_path)
            branch_sha = ref.get("object", {}).get("sha") if type(ref) is dict else None
            if branch_sha != expected.branch_sha:
                raise ValueError("branch_mismatch")
            total = initial["comments"]

            def read_comments() -> list[dict[str, Any]]:
                # La misma paginación se repite antes de aceptar el proof:
                # una edición de marker/nota puede no cambiar updated_at.
                comments: list[dict[str, Any]] = []
                seen: set[int] = set()
                for page in range(1, 7):
                    rows = get(f"{path}/comments?per_page=100&page={page}")
                    if type(rows) is not list or len(rows) > 100:
                        raise ValueError("page_invalid")
                    for comment in rows:
                        if (type(comment) is not dict
                                or type(comment.get("id")) is not int
                                or comment["id"] <= 0 or comment["id"] in seen
                                or type(comment.get("body")) is not str
                                or type(comment.get("user")) is not dict
                                or type(comment["user"].get("login")) is not str):
                            raise ValueError("comment_invalid")
                        seen.add(comment["id"])
                        comments.append(comment)
                    if len(comments) > total:
                        raise ValueError("count_overrun")
                    if len(rows) < 100:
                        if len(comments) != total:
                            raise ValueError("count_incomplete")
                        sentinel = get(f"{path}/comments?per_page=100&page={page + 1}")
                        if type(sentinel) is not list or sentinel:
                            raise ValueError("page_sentinel")
                        return comments
                raise ValueError("pagination_exhausted")

            comments = read_comments()
            active_markers: list[tuple[int, dict[str, Any]]] = []
            notes: list[tuple[int, dict[str, Any], datetime, str]] = []
            keys = {
                "version", "reservation_id", "owner", "branch", "branch_sha",
                "last_activity_at", "acceptance_sha256", "task_marker_sha256",
            }
            def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                result: dict[str, Any] = {}
                for name, val in pairs:
                    if name in result:
                        raise ValueError("duplicate_json_key")
                    result[name] = val
                return result
            for comment in comments:
                author = comment["user"]
                body = comment["body"]
                # read_comments() ya exige login str; impedir que un
                # subtipo comparable a texto suplante el tipo Bot de API.
                is_bot = (type(author.get("type")) is str
                          and author["login"] == "github-actions[bot]"
                          and author["type"] == "Bot")
                # Un solo encabezado V3 sospechoso por comentario. Un
                # duplicado (incluso truncado o con mayúsculas) no debe
                # esconderse detrás de un marker válido.
                marker_heads = re.findall(
                    r"<!--\s*condor-reserva\b", body, flags=re.IGNORECASE)
                if marker_heads:
                    if not is_bot or len(marker_heads) != 1:
                        raise ValueError("untrusted_marker_actor_or_count")
                    marker_match = re.search(
                        r"<!-- condor-reserva (\{[^\n]*\}) -->", body)
                    if marker_match is None:
                        raise ValueError("malformed_v3_marker")
                    # El parser V3 compartido comprueba schema/claims. La
                    # lectura estricta adicional rechaza claves JSON dobles
                    # que json.loads ordinario resolvería silenciosamente.
                    raw_marker = json.loads(
                        marker_match.group(1),
                        object_pairs_hook=no_duplicate_keys)
                    payload = reservation_from_text(body)
                    if type(raw_marker) is not dict or payload != raw_marker:
                        raise ValueError("malformed_v3_marker")
                    active_markers.append((comment["id"], payload))
                # Contar incluso los encabezados malformados antes de
                # aceptar una nota legítima: un segundo encabezado con
                # otra caja o truncado debe fallar cerrado.
                note_heads = re.findall(
                    r"<!--\s*factory-lease-recovery\b", body,
                    flags=re.IGNORECASE)
                if not note_heads:
                    continue
                if not is_bot or len(note_heads) != 1:
                    raise ValueError("untrusted_note_actor_or_count")
                match = re.search(
                    r"<!-- factory-lease-recovery (\{[^\n]*\}) -->", body)
                if match is None:
                    raise ValueError("malformed_recovery_note")
                note = json.loads(match.group(1), object_pairs_hook=no_duplicate_keys)
                if (type(note) is not dict or set(note) != keys
                        or type(note["version"]) is not int or note["version"] != 1):
                    raise ValueError("malformed_recovery_payload")
                stamp = comment.get("created_at")
                if (type(stamp) is not str
                        or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp) is None
                        or comment.get("updated_at") != stamp):
                    raise ValueError("untrusted_note_timestamp")
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                notes.append((comment["id"], note, when, author["login"]))
            if not active_markers:
                raise ValueError("missing_v3_marker")
            current_id, current_marker = max(
                active_markers, key=lambda row: row[0])
            if current_marker != expected.marker:
                raise ValueError("stale_v3_marker")
            # Una V3 terminal no puede resucitar con el MISMO UUID; sólo
            # se recupera con otra reserva bot. Incluso antes de un marker
            # terminal, la identidad y los pins del UUID son inmutables.
            identity_fields = (
                "version", "owner", "reservation_id", "branch",
                "acceptance_sha256", "task_marker_sha256",
                "task_paths", "task_depends_on",
            )
            for previous_id, previous in active_markers:
                if (previous_id < current_id
                        and previous["reservation_id"] == expected.reservation_id):
                    if (any(previous[key] != current_marker[key]
                            for key in identity_fields)
                            or (current_marker["active"]
                                and previous["active"] is False)):
                        raise ValueError("resurrected_or_rebound_v3_uuid")
            # La recuperación de /tomar conserva notas legítimas de otras
            # leases. Ignorar solo las anteriores a la V3 vigente y
            # asociadas a un marker bot auténtico, jamás notas huérfanas.
            previous_markers: dict[str, list[tuple[int, dict[str, Any]]]] = {}
            for comment_id, marker in active_markers:
                if (comment_id < current_id
                        and marker["reservation_id"] != expected.reservation_id):
                    previous_markers.setdefault(
                        marker["reservation_id"], []).append((comment_id, marker))
            current_notes: list[tuple[datetime, str]] = []
            old_seen: set[str] = set()
            for note_id, note, when, actor in notes:
                if note["reservation_id"] == expected.reservation_id:
                    if (note_id <= current_id
                            or note["owner"] != expected.owner
                            or note["branch"] != expected.branch
                            or note["branch_sha"] != expected.branch_sha
                            or note["last_activity_at"] != _utc(
                                expected.last_activity_at).isoformat()
                            or note["acceptance_sha256"] !=
                               expected.marker["acceptance_sha256"]
                            or note["task_marker_sha256"] !=
                               expected.marker["task_marker_sha256"]):
                        raise ValueError("recovery_identity_drift")
                    current_notes.append((when, actor))
                    continue
                old = previous_markers.get(note["reservation_id"], [])
                # La misma lease antigua puede haber publicado active:false
                # después de su nota. No confundir ese marker terminal con
                # un origen huérfano: debe existir un marker ANTERIOR a
                # la nota, y TODOS los markers de ese UUID conservan pins.
                if (not old or note["reservation_id"] in old_seen
                        or not note_id < current_id
                        or not any(marker_id < note_id
                                   for marker_id, _ in old)
                        or any(
                            note["owner"] != marker["owner"]
                            or note["branch"] != marker["branch"]
                            or note["acceptance_sha256"] !=
                               marker["acceptance_sha256"]
                            or note["task_marker_sha256"] !=
                               marker["task_marker_sha256"]
                            for _, marker in old)
                        or type(note["branch_sha"]) is not str
                        or SHA.fullmatch(note["branch_sha"]) is None
                        or type(note["last_activity_at"]) is not str
                        or re.fullmatch(
                            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00",
                            note["last_activity_at"]) is None):
                    raise ValueError("historical_note_untrusted")
                old_seen.add(note["reservation_id"])
            if len(current_notes) > 1:
                raise ValueError("duplicate_current_note")
            final = get(path)
            ref_after = get(branch_path)
            if (type(final) is not dict
                    or final.get("state") != "open"
                    or final.get("number") != issue
                    or final.get("comments") != total
                    or final.get("updated_at") != initial["updated_at"]
                    # El contrato puede editarse dentro del mismo segundo.
                    # No confiar solo en updated_at para su integridad.
                    or final.get("body") != initial["body"]
                    # La fecha API puede tener resolución de segundos:
                    # un cambio simultáneo de etiqueta/asignado nunca
                    # hereda el proof autenticado del snapshot anterior.
                    or final.get("labels") != initial["labels"]
                    or final.get("assignees") != initial["assignees"]
                    or type(ref_after) is not dict
                    or ref_after.get("object", {}).get("sha") != expected.branch_sha
                    or read_comments() != comments
                    or not running_with_budget()
                    # La cuota remanente debe cubrir TODAS las
                    # lecturas del proof compuesto, no solo este método.
                    or remaining - _budget[0] < 0
                    or (remaining - _budget[0]) * 5 < limit):
                raise ValueError("recheck_mismatch")
            found = len(current_notes)
            proof = RecoveryNoteProof(
                complete=True, authenticated=True, count=found,
                owner=expected.owner, reservation_id=expected.reservation_id,
                branch=expected.branch, branch_sha=expected.branch_sha,
                last_activity_at=expected.last_activity_at,
                acceptance_sha256=expected.marker["acceptance_sha256"],
                task_marker_sha256=expected.marker["task_marker_sha256"],
                created_at=current_notes[0][0] if found else None,
                author=current_notes[0][1] if found else None,
            )
            if not _note_ok(proof, expected):
                raise ValueError("recovery_note_ineligible")
            return proof
        except Exception:
            # Fail-closed y sin exponer payload, token, body ni URL secreta.
            raise PortNotArmed("authenticated_recovery_proof_unavailable") from None

    def recovery_label(self, issue: int, expected: Any) -> RecoveryLabelProof:
        """Evidencia GET-only; jamás confundir una etiqueta con autorización."""
        try:
            if ((isinstance(issue, bool) or not isinstance(issue, int)) or not isinstance(expected, Snapshot)
                    or issue != expected.issue
                    or expected.status != "estado: requiere recuperación"):
                raise ValueError("invalid_recovery")
            budget = [0]
            note = self.recovery_note(issue, expected, _budget=budget)
            if note.count != 1 or budget[0] > 32:
                raise ValueError("missing_note")
            repo = getattr(self._api, "repo", None)
            if (type(repo) is not str
                    or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
                    is None):
                raise ValueError("invalid_repo")
            base = f"/repos/{repo}/issues/{issue}/events"

            def timeline_get(path: str) -> Any:
                budget[0] += 1
                if budget[0] > 32:
                    raise ValueError("request_budget")
                return self._api.request("GET", path)

            def read_timeline() -> list[dict[str, Any]]:
                rows: list[dict[str, Any]] = []
                seen: set[int] = set()
                for page in range(1, 6):
                    path = f"{base}?per_page=100&page={page}"
                    batch = timeline_get(path)
                    if type(batch) is not list or len(batch) > 100:
                        raise ValueError("invalid_page")
                    for event in batch:
                        if (type(event) is not dict
                                or type(event.get("id")) is not int
                                or event["id"] <= 0 or event["id"] in seen):
                            raise ValueError("duplicate_event")
                        seen.add(event["id"])
                        rows.append(event)
                    if len(batch) < 100:
                        sentinel = timeline_get(
                            f"{base}?per_page=100&page={page + 1}")
                        if type(sentinel) is not list or sentinel:
                            raise ValueError("incomplete_timeline")
                        return rows
                raise ValueError("timeline_over_limit")

            first = read_timeline()
            proof = _verified_recovery_timeline(first, note, expected)
            if read_timeline() != first:
                raise ValueError("timeline_changed")
            if (self.recovery_note(issue, expected, _budget=budget) != note
                    or budget[0] > 32):
                raise ValueError("note_changed_or_request_budget")
            return proof
        except Exception:
            raise PortNotArmed("authenticated_timeline_proof_unavailable") from None

    def status(self, issue: int, state: str, expected: Any) -> None:
        self._need_armed()
        if state not in (RECOVERY, AVAILABLE):
            raise PortNotArmed("state_not_allowed")
        current = self._cas(issue, expected, same_fingerprint=True)
        if state == AVAILABLE and (current.marker.get("active") is not False
                                   or current.status != RECOVERY):
            raise PortNotArmed("release_requires_inactive_marker")
        repo = getattr(self._api, "repo")
        issue_obj = self._api.request("GET", f"/repos/{repo}/issues/{issue}")
        names = [l["name"] for l in issue_obj["labels"]]
        labels = [n for n in names if n not in ACTIVE] + [state]
        self._api.request("PATCH", f"/repos/{repo}/issues/{issue}", {"labels": labels})


class _WithoutComment:
    """Vista GET de la API que omite un comentario (y su cuenta) del Issue."""

    def __init__(self, api: Any, issue: int, comment_id: int) -> None:
        self._api, self._issue, self._id = api, issue, comment_id
        self.repo = getattr(api, "repo", None)
        self.authenticated = getattr(api, "authenticated", False)

    def request(self, method: str, path: str, *rest: Any) -> Any:
        if method != "GET" or rest:
            raise PortNotArmed("mutation_disabled")
        result = self._api.request("GET", path)
        base = f"/repos/{self.repo}/issues/{self._issue}"
        if path.startswith(f"{base}/comments") and type(result) is list:
            return [c for c in result if not (type(c) is dict and c.get("id") == self._id)]
        if path == base and type(result) is dict and type(result.get("comments")) is int:
            return {**result, "comments": result["comments"] - 1}
        return result


def _bot_marker(body: Any, *, allow_inactive: bool = False) -> dict[str, Any] | None:
    """Marker V3 de un comentario; None si ausente o ambiguo (claves duplicadas)."""
    if type(body) is not str:
        return None
    matches = re.findall(r"<!-- condor-reserva (\{[^\r\n]*\}) -->", body)
    if len(matches) != 1:
        return None

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate_key")
            out[key] = value
        return out

    try:
        parsed = json.loads(matches[0], object_pairs_hook=unique)
    except ValueError:
        return None
    if type(parsed) is not dict or parsed.get("version") != 3:
        return None
    if parsed.get("active") is False and not allow_inactive:
        return None
    return parsed
