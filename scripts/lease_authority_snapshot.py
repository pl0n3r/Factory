"""Auditoría pura de autoridad V3 para un futuro preflight de Coordinación.

El llamador debe aportar TODOS los Issues abiertos y TODOS sus comentarios,
ordenados por ID desde la API autenticada. Este módulo NO consulta GitHub,
NO reserva trabajo y NO habilita paralelismo: la decisión continúa en el bot.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

BOT = "github-actions[bot]"
PREFIX = "<!-- condor-reserva "
MARKER = re.compile(r"\A<!-- condor-reserva (\{[^\r\n]*\}) -->")
SUSPECT_MARKER = re.compile(r"<!--\s*condor-reserva\b", re.IGNORECASE)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ACTIVE_LABELS = frozenset({
    "estado: reservado", "estado: en revisión", "estado: requiere recuperación",
    "status: reserved", "status: in review", "status: recovery required",
})
BASE_KEYS = frozenset({"version", "owner", "reservation_id", "branch", "active", "reason"})
V3_KEYS = BASE_KEYS | {"acceptance_sha256", "task_marker_sha256", "task_paths", "task_depends_on"}


class LeaseSnapshotError(ValueError):
    """Error tipado sin payloads, URLs o datos de clientes."""


@dataclass(frozen=True)
class ActiveLease:
    issue: int
    reservation_id: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class LeaseAudit:
    active: tuple[ActiveLease, ...]
    fingerprint: str


def _reject(reason: str) -> None:
    raise LeaseSnapshotError(reason)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _reject("marker_json_claves_duplicadas")
        result[key] = value
    return result


def _path(path: Any) -> bool:
    # Mismo límite y metacaracteres excluidos por orquestador_kit._valid_path.
    if not isinstance(path, str) or not 1 <= len(path) <= 240:
        return False
    if (path != path.strip() or path.startswith(("/", "./")) or "\\" in path
        or any(char in path for char in ("*", "?", "[", "]", "{", "}"))
        or any(ord(char) < 32 or ord(char) == 127 for char in path)):
        return False
    base = path[:-1] if path.endswith("/") else path
    parts = base.split("/")
    return bool(parts) and all(p not in ("", ".", "..") for p in parts)


def _owner(login: Any) -> bool:
    return (isinstance(login, str) and 1 <= len(login) <= 39 and login.isascii()
            and not login.startswith("-") and not login.endswith("-")
            and "--" not in login
            and all(char.isalnum() or char == "-" for char in login))


def _marker_payload(body: str, number: int) -> dict[str, Any]:
    if body.count(PREFIX) != 1 or len(SUSPECT_MARKER.findall(body)) != 1:
        _reject("marker_ambiguo")
    match = MARKER.match(body)
    if match is None:
        _reject("marker_invalido")
    try:
        marker = json.loads(match.group(1), object_pairs_hook=_unique_pairs)
    except (ValueError, TypeError) as exc:
        raise LeaseSnapshotError("marker_invalido") from exc
    if not isinstance(marker, dict) or type(marker.get("version")) is not int:
        _reject("marker_esquema")
    version = marker["version"]
    expected = (V3_KEYS if version == 3 else
                BASE_KEYS | {"acceptance_sha256"} if version == 2 else
                BASE_KEYS if version == 1 else frozenset())
    if not expected or set(marker) != expected:
        _reject("marker_esquema")
    if (type(marker["active"]) is not bool or not _owner(marker["owner"])
        or not isinstance(marker["reason"], str)
        or not marker["reason"] or marker["branch"] != f"trabajo/issue-{number}"):
        _reject("marker_identidad")
    uid = marker["reservation_id"]
    try:
        if not isinstance(uid, str) or str(UUID(uid)) != uid:
            _reject("marker_uuid")
    except (ValueError, AttributeError, TypeError) as exc:
        raise LeaseSnapshotError("marker_uuid") from exc
    if version in (2, 3) and (not isinstance(marker["acceptance_sha256"], str)
                              or HEX64.fullmatch(marker["acceptance_sha256"]) is None):
        _reject("marker_fingerprint")
    if version != 3:
        if marker["active"]:
            _reject("marker_activo_sin_claims_v3")
        return marker
    paths, deps = marker["task_paths"], marker["task_depends_on"]
    if (not isinstance(marker["task_marker_sha256"], str)
        or HEX64.fullmatch(marker["task_marker_sha256"]) is None
        or not isinstance(paths, list) or not 1 <= len(paths) <= 50
        or any(not _path(path) for path in paths)
        or len({path.casefold() for path in paths}) != len(paths)
        or not isinstance(deps, list) or len(deps) > 50
        or any(type(dep) is not int or dep <= 0 for dep in deps)
        or len(set(deps)) != len(deps)):
        _reject("marker_claims")
    return marker


def _last_bot_marker(comments: Any, issue_number: int) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(comments, list):
        _reject("comentarios_incompletos")
    last_id = 0
    latest: dict[str, Any] | None = None
    digest = hashlib.sha256()
    for comment in comments:
        if not isinstance(comment, dict) or type(comment.get("id")) is not int:
            _reject("comentario_invalido")
        cid = comment["id"]
        if cid <= last_id:
            _reject("comentarios_desordenados")
        last_id = cid
        user, body = comment.get("user"), comment.get("body")
        if not isinstance(user, dict) or not isinstance(body, str):
            _reject("comentario_invalido")
        actor = user.get("login")
        if not isinstance(actor, str) or not actor:
            _reject("comentario_invalido")
        # Incluye /tomar y comentarios no-marker: cualquier edición o nuevo
        # comentario entre snapshots invalida el permiso de publicación.
        body_hash = hashlib.sha256(json.dumps(body, ensure_ascii=True).encode("ascii")).hexdigest()
        identity = json.dumps([cid, actor, body_hash, comment.get("updated_at")],
                              separators=(",", ":"), ensure_ascii=True)
        digest.update(identity.encode("ascii") + b"\n")
        if actor == BOT and SUSPECT_MARKER.search(body):
            current = _marker_payload(body, issue_number)
            if latest is not None and current["reservation_id"] == latest["reservation_id"]:
                immutable = ("version", "owner", "branch", "acceptance_sha256",
                             "task_marker_sha256", "task_paths", "task_depends_on")
                if any(current.get(field) != latest.get(field) for field in immutable):
                    _reject("marker_continuidad")
            latest = current
    return latest, digest.hexdigest()


def _overlap(left: str, right: str) -> bool:
    left, right = left.casefold(), right.casefold()
    return (left == right or (left.endswith("/") and right.startswith(left))
            or (right.endswith("/") and left.startswith(right)))


def audit_active_claims(open_issues: Any, comments_by_issue: Any, *, complete: bool) -> LeaseAudit:
    """No infiere ausencia de leases sin evidencia explícitamente completa."""
    if complete is not True or not isinstance(open_issues, list) or not isinstance(comments_by_issue, dict):
        _reject("inventario_incompleto")
    if any(type(key) is not int or key <= 0 for key in comments_by_issue):
        _reject("inventario_incompleto")
    issue_ids: set[int] = set()
    uuids: set[str] = set()
    active: list[ActiveLease] = []
    normalized: list[dict[str, Any]] = []
    for issue in open_issues:
        if not isinstance(issue, dict) or type(issue.get("number")) is not int:
            _reject("issue_invalido")
        number = issue["number"]
        if number <= 0 or number in issue_ids or issue.get("state") != "open" or "pull_request" in issue:
            _reject("issue_invalido")
        issue_ids.add(number)
        labels = issue.get("labels")
        if not isinstance(labels, list) or any(not isinstance(l, dict) or not isinstance(l.get("name"), str) for l in labels):
            _reject("labels_invalidas")
        label_names = [l["name"] for l in labels]
        if len(set(label_names)) != len(label_names):
            _reject("labels_invalidas")
        if sum(name.startswith(("estado: ", "status: ")) for name in label_names) > 1:
            _reject("labels_estados_conflictivos")
        if number not in comments_by_issue:
            _reject("comentarios_incompletos")
        marker, comments_sha256 = _last_bot_marker(comments_by_issue[number], number)
        if ACTIVE_LABELS.intersection(label_names) and (marker is None or not marker["active"]):
            _reject("estado_activo_sin_marker")
        if marker is not None:
            uid = marker["reservation_id"]
            if uid in uuids:
                _reject("uuid_duplicado")
            uuids.add(uid)
            if marker["active"]:
                # IMPORTANTE: no filtrar por label: incluso BLOCKED retiene claims.
                active.append(ActiveLease(number, uid, tuple(marker["task_paths"])))
        if "body" not in issue or "updated_at" not in issue:
            _reject("issue_incompleto")
        body, updated = issue["body"], issue["updated_at"]
        if (body is not None and not isinstance(body, str)) or (
            not isinstance(updated, str) or not updated
        ):
            _reject("issue_invalido")
        body_hash = hashlib.sha256(json.dumps(body, ensure_ascii=True).encode("ascii")).hexdigest()
        normalized.append({"number": number, "labels": sorted(label_names),
                           "marker": marker, "comments_sha256": comments_sha256,
                           "body_sha256": body_hash, "updated_at": updated})
    if set(comments_by_issue) != issue_ids:
        _reject("inventario_incompleto")
    for position, lease in enumerate(active):
        for other in active[position + 1:]:
            if any(_overlap(a, b) for a in lease.paths for b in other.paths):
                _reject("claims_activas_solapadas")
    normalized.sort(key=lambda row: row["number"])
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return LeaseAudit(tuple(sorted(active, key=lambda lease: lease.issue)),
                      hashlib.sha256(serialized.encode("utf-8")).hexdigest())


def require_unchanged(before: LeaseAudit, after: LeaseAudit) -> None:
    """Veta una concesión si cualquier Issue, label o marker autorizado derivó."""
    if not isinstance(before, LeaseAudit) or not isinstance(after, LeaseAudit):
        _reject("snapshot_invalido")
    if before.fingerprint != after.fingerprint or before.active != after.active:
        _reject("inventario_cambio")
