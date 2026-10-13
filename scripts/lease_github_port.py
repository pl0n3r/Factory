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
    SESSION_RE, SHA, RecoveryNoteProof, Snapshot, _trusted, _note_ok, _utc,
)
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

            if not self._running():
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
            comments: list[dict[str, Any]] = []
            seen: set[int] = set()
            total = initial["comments"]
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
                    # Una página terminal corta no basta sin página centinela.
                    sentinel = get(f"{path}/comments?per_page=100&page={page + 1}")
                    if type(sentinel) is not list or sentinel:
                        raise ValueError("page_sentinel")
                    break
            else:
                raise ValueError("pagination_exhausted")
            active_markers: list[tuple[int, dict[str, Any]]] = []
            notes: list[tuple[datetime, str]] = []
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
                is_bot = (author["login"] == "github-actions[bot]"
                          and author.get("type") == "Bot")
                if "<!-- condor-reserva " in body:
                    if not is_bot:
                        raise ValueError("untrusted_marker_actor")
                    payload = reservation_from_text(body)
                    if payload is None:
                        raise ValueError("malformed_v3_marker")
                    active_markers.append((comment["id"], payload))
                if "<!-- factory-lease-recovery " not in body:
                    continue
                if not is_bot or body.count("<!-- factory-lease-recovery ") != 1:
                    raise ValueError("untrusted_note_actor")
                match = re.search(
                    r"<!-- factory-lease-recovery (\{[^\n]*\}) -->", body)
                if match is None:
                    raise ValueError("malformed_recovery_note")
                note = json.loads(match.group(1), object_pairs_hook=no_duplicate_keys)
                if (type(note) is not dict or set(note) != keys
                        or type(note["version"]) is not int or note["version"] != 1
                        or note["owner"] != expected.owner
                        or note["reservation_id"] != expected.reservation_id
                        or note["branch"] != expected.branch
                        or note["branch_sha"] != expected.branch_sha
                        or note["last_activity_at"] != _utc(
                            expected.last_activity_at).isoformat()
                        or note["acceptance_sha256"] != expected.marker["acceptance_sha256"]
                        or note["task_marker_sha256"] != expected.marker["task_marker_sha256"]):
                    raise ValueError("recovery_identity_drift")
                stamp = comment.get("created_at")
                if (type(stamp) is not str
                        or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp) is None
                        or comment.get("updated_at") != stamp):
                    raise ValueError("untrusted_note_timestamp")
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                notes.append((when, author["login"]))
            if (len(active_markers) == 0
                    or max(active_markers, key=lambda row: row[0])[1] != expected.marker
                    or len(notes) > 1):
                raise ValueError("marker_or_note_count")
            final = get(path)
            ref_after = get(branch_path)
            if (type(final) is not dict
                    or final.get("state") != "open"
                    or final.get("number") != issue
                    or final.get("comments") != total
                    or final.get("updated_at") != initial["updated_at"]
                    or type(ref_after) is not dict
                    or ref_after.get("object", {}).get("sha") != expected.branch_sha
                    or not self._running()
                    or remaining - calls < 0
                    or (remaining - calls) * 5 < limit):
                raise ValueError("recheck_mismatch")
            found = len(notes)
            proof = RecoveryNoteProof(
                complete=True, authenticated=True, count=found,
                owner=expected.owner, reservation_id=expected.reservation_id,
                branch=expected.branch, branch_sha=expected.branch_sha,
                last_activity_at=expected.last_activity_at,
                acceptance_sha256=expected.marker["acceptance_sha256"],
                task_marker_sha256=expected.marker["task_marker_sha256"],
                created_at=notes[0][0] if found else None,
                author=notes[0][1] if found else None,
            )
            if not _note_ok(proof, expected):
                raise ValueError("recovery_note_ineligible")
            return proof
        except Exception:
            # Fail-closed y sin exponer payload, token, body ni URL secreta.
            raise PortNotArmed("authenticated_recovery_proof_unavailable") from None

    def recovery_label(self, issue: int, expected: Any) -> Any:
        raise PortNotArmed("authenticated_timeline_proof_unavailable")

    def status(self, issue: int, state: str, expected: Any) -> None:
        raise PortNotArmed("mutation_disabled")
