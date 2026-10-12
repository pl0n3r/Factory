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
from datetime import datetime
from typing import Any
import unicodedata

BOT = "github-actions[bot]"
PREFIX = "<!-- condor-reserva "
MARKER = re.compile(r"\A<!-- condor-reserva (\{[^\r\n]*\}) -->")
SUSPECT_MARKER = re.compile(r"<!--\s*condor-reserva\b", re.IGNORECASE)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SESSION_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
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


def _check_marker_identity(marker: dict[str, Any], number: int) -> None:
    if (type(marker["active"]) is not bool or not _owner(marker["owner"])
            or not isinstance(marker["reason"], str) or not marker["reason"]
            or marker["branch"] != f"trabajo/issue-{number}"
            or (marker["reason"] == "tomar" and not marker["active"])
            or (marker["reason"] == "liberar" and marker["active"])):
        _reject("marker_identidad")
    uid = marker["reservation_id"]
    # La autoridad canónica usa SESSION_RE: UUID v1-v5 y variante RFC4122.
    if type(uid) is not str or SESSION_ID_RE.fullmatch(uid) is None:
        _reject("marker_uuid")


def _check_marker_claims(marker: dict[str, Any], number: int) -> None:
    paths, deps = marker["task_paths"], marker["task_depends_on"]
    if (not isinstance(marker["task_marker_sha256"], str)
            or HEX64.fullmatch(marker["task_marker_sha256"]) is None):
        _reject("marker_claims")
    if (not isinstance(paths, list) or not 1 <= len(paths) <= 50
            or any(not _path(path) for path in paths)):
        _reject("marker_claims")
    if any(_overlap(first, second)
           for index, first in enumerate(paths) for second in paths[index + 1:]):
        _reject("marker_claims")
    if (not isinstance(deps, list) or len(deps) > 50
            or any(type(dep) is not int or dep <= 0 for dep in deps)
            or number in deps or len(set(deps)) != len(deps)):
        _reject("marker_claims")


def _check_marker_schema(marker: Any, number: int) -> None:
    if not isinstance(marker, dict) or type(marker.get("version")) is not int:
        _reject("marker_esquema")
    expected = (V3_KEYS if marker["version"] == 3 else
                BASE_KEYS | {"acceptance_sha256"} if marker["version"] == 2 else
                BASE_KEYS if marker["version"] == 1 else frozenset())
    if not expected or set(marker) != expected:
        _reject("marker_esquema")
    _check_marker_identity(marker, number)
    if marker["version"] in (2, 3):
        digest = marker["acceptance_sha256"]
        if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
            _reject("marker_fingerprint")
    if marker["version"] != 3:
        if marker["active"]:
            _reject("marker_activo_sin_claims_v3")
        return
    _check_marker_claims(marker, number)


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
    _check_marker_schema(marker, number)
    return marker

def _valid_timestamp(value: Any) -> bool:
    """Acepta solo timestamps UTC canónicos de la API, nunca None."""
    if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _comment_fields(comment: Any, previous_id: int) -> tuple[int, str, Any, str, str]:
    """Valida metadatos de comentarios sin asignarles autoridad adicional."""
    if not isinstance(comment, dict) or type(comment.get("id")) is not int:
        _reject("comentario_invalido")
    cid = comment["id"]
    if cid <= previous_id:
        _reject("comentarios_desordenados")
    user, body = comment.get("user"), comment.get("body")
    if not isinstance(user, dict) or not isinstance(body, str):
        _reject("comentario_invalido")
    actor, actor_type = user.get("login"), user.get("type")
    if not isinstance(actor, str) or not actor:
        _reject("comentario_invalido")
    if actor == BOT and actor_type != "Bot":
        _reject("comentario_actor_invalido")
    timestamp = comment.get("updated_at")
    if not _valid_timestamp(timestamp):
        _reject("comentario_fecha_invalida")
    return cid, actor, actor_type, body, timestamp


def _verify_new_uuid(previous: dict[str, Any], current: dict[str, Any]) -> None:
    """Una rotación nunca elimina claims ni cambia fingerprints sin autoridad."""
    stable = ("version", "branch", "acceptance_sha256",
              "task_marker_sha256", "task_paths", "task_depends_on")
    if (not current["active"]
            or any(current.get(field) != previous.get(field) for field in stable)):
        _reject("marker_rotacion")
    if previous["active"]:
        if current["reason"] not in ("transferir", "recuperacion-inactividad"):
            _reject("marker_rotacion")
        if current["owner"] != previous["owner"] and current["reason"] != "recuperacion-inactividad":
            _reject("marker_rotacion")
    elif (current["reason"] not in ("tomar", "recuperacion-inactividad")
          or current["owner"] != previous["owner"]):
        _reject("marker_rotacion")


def _verify_marker_transition(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    observed: set[str],
    released: set[str],
) -> None:
    """Conserva exactamente los vetos de replay y continuidad V3."""
    uid = current["reservation_id"]
    if current["active"] and uid in released:
        _reject("marker_reactivado")
    if previous is None:
        return
    if uid != previous["reservation_id"] and uid in observed:
        _reject("marker_reactivado")
    if uid != previous["reservation_id"]:
        _verify_new_uuid(previous, current)
        return
    immutable = ("version", "owner", "branch", "acceptance_sha256",
                 "task_marker_sha256", "task_paths", "task_depends_on")
    if any(current.get(field) != previous.get(field) for field in immutable):
        _reject("marker_continuidad")
    if not previous["active"] and current["active"]:
        _reject("marker_reactivado")


def _last_bot_marker(
    comments: Any,
    issue_number: int,
    uuid_origins: dict[str, int],
) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(comments, list):
        _reject("comentarios_incompletos")
    last_id = 0
    latest: dict[str, Any] | None = None
    # Un UUID histórico no recupera autoridad por aparecer de nuevo.
    observed_uuids: set[str] = set()
    released_uuids: set[str] = set()
    digest = hashlib.sha256()
    for comment in comments:
        cid, actor, actor_type, body, timestamp = _comment_fields(comment, last_id)
        last_id = cid
        # Compromete TODOS los comentarios en la huella, también /tomar.
        body_hash = hashlib.sha256(json.dumps(body, ensure_ascii=True).encode("ascii")).hexdigest()
        identity = json.dumps([cid, actor, actor_type, body_hash, timestamp],
                              separators=(",", ":"), ensure_ascii=True)
        digest.update(identity.encode("ascii") + b"\n")
        if actor == BOT and SUSPECT_MARKER.search(body):
            current = _marker_payload(body, issue_number)
            _verify_marker_transition(latest, current, observed_uuids, released_uuids)
            uid = current["reservation_id"]
            # El UUID es único en TODO el snapshot, incluidos markers
            # históricos y liberados de otros Issues.
            if uid in uuid_origins and uuid_origins[uid] != issue_number:
                _reject("uuid_duplicado")
            uuid_origins[uid] = issue_number
            if current["active"] is False:
                released_uuids.add(uid)
            observed_uuids.add(uid)
            latest = current
    return latest, digest.hexdigest()


def _overlap(left: str, right: str) -> bool:
    """Alinea archivo/directorio con el orquestador, usando NFC y casefold."""
    left_dir, right_dir = left.endswith("/"), right.endswith("/")
    a = tuple(unicodedata.normalize("NFC", left.rstrip("/")).casefold().split("/"))
    b = tuple(unicodedata.normalize("NFC", right.rstrip("/")).casefold().split("/"))
    if a == b:
        return True
    return ((left_dir and len(a) < len(b) and a == b[:len(a)])
            or (right_dir and len(b) < len(a) and b == a[:len(b)]))


def _issue_number(issue: Any, observed: set[int]) -> int:
    if not isinstance(issue, dict) or type(issue.get("number")) is not int:
        _reject("issue_invalido")
    number = issue["number"]
    if number <= 0 or number in observed or issue.get("state") != "open" or "pull_request" in issue:
        _reject("issue_invalido")
    observed.add(number)
    return number


def _issue_labels(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels")
    if (not isinstance(labels, list)
            or any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
                   for item in labels)):
        _reject("labels_invalidas")
    names = [item["name"] for item in labels]
    if len({name.casefold() for name in names}) != len(names):
        _reject("labels_invalidas")
    if sum(name.casefold().startswith(("estado: ", "status: ")) for name in names) > 1:
        _reject("labels_estados_conflictivos")
    return names


def _issue_body_fingerprint(issue: dict[str, Any]) -> tuple[str, str]:
    if "body" not in issue or "updated_at" not in issue:
        _reject("issue_incompleto")
    body, updated = issue["body"], issue["updated_at"]
    if ((body is not None and not isinstance(body, str))
            or not isinstance(updated, str) or not updated):
        _reject("issue_invalido")
    return hashlib.sha256(json.dumps(body, ensure_ascii=True).encode("ascii")).hexdigest(), updated


def _audit_issue(
    issue: Any,
    comments_by_issue: dict[int, Any],
    issue_ids: set[int],
    uuid_origins: dict[str, int],
    active: list[ActiveLease],
) -> dict[str, Any]:
    number = _issue_number(issue, issue_ids)
    labels = _issue_labels(issue)
    if number not in comments_by_issue:
        _reject("comentarios_incompletos")
    marker, comments_hash = _last_bot_marker(comments_by_issue[number], number, uuid_origins)
    if ACTIVE_LABELS.intersection(name.casefold() for name in labels) and (marker is None or not marker["active"]):
        _reject("estado_activo_sin_marker")
    if marker is not None and marker["active"]:
        # Incluso un Issue BLOCKED debe conservar sus claims activos.
        active.append(ActiveLease(number, marker["reservation_id"],
                                  tuple(marker["task_paths"])))
    body_hash, updated = _issue_body_fingerprint(issue)
    return {"number": number, "labels": sorted(labels),
            "marker": marker, "comments_sha256": comments_hash,
            "body_sha256": body_hash, "updated_at": updated}


def _verify_disjoint_leases(active: list[ActiveLease]) -> None:
    for index, lease in enumerate(active):
        for other in active[index + 1:]:
            if any(_overlap(left, right) for left in lease.paths for right in other.paths):
                _reject("claims_activas_solapadas")


def audit_active_claims(open_issues: Any, comments_by_issue: Any, *, complete: bool) -> LeaseAudit:
    """No infiere ausencia de leases sin evidencia explícitamente completa."""
    if complete is not True or not isinstance(open_issues, list) or not isinstance(comments_by_issue, dict):
        _reject("inventario_incompleto")
    if any(type(key) is not int or key <= 0 for key in comments_by_issue):
        _reject("inventario_incompleto")
    issue_ids: set[int] = set()
    uuid_origins: dict[str, int] = {}
    active: list[ActiveLease] = []
    normalized = [_audit_issue(issue, comments_by_issue, issue_ids, uuid_origins, active)
                  for issue in open_issues]
    if set(comments_by_issue) != issue_ids:
        _reject("inventario_incompleto")
    _verify_disjoint_leases(active)
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
