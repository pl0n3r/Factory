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
import json
import re
from typing import Any

from scripts.lease_release_executor import (
    SESSION_RE, SHA, RecoveryLabelProof, RecoveryNoteProof, Snapshot,
    _trusted, _note_ok, _recovery_label_ok, _utc,
)
from scripts.aceptacion_kit import contract_fingerprint
from scripts.coordinar_trabajo import reservation_from_text

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

    def __init__(self, api: Any) -> None:
        self._api = api

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

    def recovery_note(self, issue: int, expected: Any) -> RecoveryNoteProof:
        """GET-only: verifica nota de bot y reserva exacta, nunca CAS.

        Se permite leer/probar esta evidencia, pero read/lock/append/status
        continúan desarmados. Un proof aislado NO acredita inactividad.
        """
        try:
            repo = getattr(self._api, "repo", None)
            if (type(expected) is not Snapshot or type(issue) is not int
                    or issue != expected.issue or not _trusted(expected, allow_partial=True)
                    or type(repo) is not str
                    or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is None):
                raise ValueError("untrusted_expected")
            calls = 0
            def get(endpoint: str) -> Any:
                nonlocal calls
                calls += 1
                if calls > 32:
                    raise ValueError("request_budget")
                return self._api.request("GET", endpoint)

            def running_with_budget() -> bool:
                # #767 también cuesta una petición autenticada; las dos
                # lecturas deben compartir el límite de 32 y la reserva
                # mínima del 20 % con el resto de la prueba.
                nonlocal calls
                calls += 1
                if calls > 32:
                    raise ValueError("request_budget")
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
                    or type(initial.get("labels")) is not list
                    or type(initial.get("assignees")) is not list
                    or len(initial["assignees"]) != 1
                    or type(initial["assignees"][0]) is not dict
                    or initial["assignees"][0].get("login") != expected.owner):
                raise ValueError("issue_mismatch")
            state_labels = [
                z.get("name") for z in initial["labels"]
                if type(z) is dict and type(z.get("name")) is str
                and z["name"].startswith("estado:")
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
                    or remaining - calls < 0
                    or (remaining - calls) * 5 < limit):
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
            if (type(issue) is not int or type(expected) is not Snapshot
                    or issue != expected.issue
                    or expected.status != "estado: requiere recuperación"):
                raise ValueError("invalid_recovery")
            note = self.recovery_note(issue, expected)
            if note.count != 1:
                raise ValueError("missing_note")
            repo = getattr(self._api, "repo", None)
            if (type(repo) is not str
                    or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
                    is None):
                raise ValueError("invalid_repo")
            base = f"/repos/{repo}/issues/{issue}/events"

            def read_timeline() -> list[dict[str, Any]]:
                rows: list[dict[str, Any]] = []
                seen: set[int] = set()
                for page in range(1, 6):
                    path = f"{base}?per_page=100&page={page}"
                    batch = self._api.request("GET", path)
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
                        sentinel = self._api.request(
                            "GET", f"{base}?per_page=100&page={page + 1}")
                        if type(sentinel) is not list or sentinel:
                            raise ValueError("incomplete_timeline")
                        return rows
                raise ValueError("timeline_over_limit")

            first = read_timeline()
            proof = _verified_recovery_timeline(first, note, expected)
            if read_timeline() != first:
                raise ValueError("timeline_changed")
            if self.recovery_note(issue, expected) != note:
                raise ValueError("note_changed")
            return proof
        except Exception:
            raise PortNotArmed("authenticated_timeline_proof_unavailable") from None

    def status(self, issue: int, state: str, expected: Any) -> None:
        raise PortNotArmed("mutation_disabled")
