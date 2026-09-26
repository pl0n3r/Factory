#!/usr/bin/env python3
"""Coordina trabajo concurrente entre sesiones y agentes usando GitHub como árbitro."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

if __package__:
    from scripts.aceptacion_kit import AcceptanceError, contract_fingerprint, parse_contract
    from scripts.orquestador_kit import (
        PlanError,
        parallel_compatibility_evidence,
        parse_task_marker,
        reservation_blockers,
        task_marker_fingerprint,
    )
else:
    from aceptacion_kit import AcceptanceError, contract_fingerprint, parse_contract
    from orquestador_kit import (
        PlanError,
        parallel_compatibility_evidence,
        parse_task_marker,
        reservation_blockers,
        task_marker_fingerprint,
    )


API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
TRUSTED_MARKER_LOGIN = os.getenv(
    "CONDOR_TRUSTED_MARKER_LOGIN",
    "github-actions[bot]",
)

try:
    RESERVATION_STALE_MINUTES = max(
        5,
        int(os.getenv("CONDOR_RESERVATION_STALE_MINUTES", "30")),
    )
except ValueError:
    RESERVATION_STALE_MINUTES = 30

ALLOWED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}

@dataclass(frozen=True)
class CoordinationProfile:
    name: str
    available: str
    reserved: str
    recovery: str
    review: str
    completed: str
    cancelled: str
    blocked: str
    branch_prefix: str
    visible_reservation: str
    marker: str
    hidden_marker: str
    take: str
    force_release: str
    release: str
    transfer: str
    recover: str

PROFILES = {
    "es": CoordinationProfile("es","estado: disponible","estado: reservado","estado: requiere recuperación","estado: en revisión","estado: completado","estado: cancelado","estado: bloqueado","trabajo/issue-","Reserva","condor-reserva","condor-reserva-id","/tomar","/liberar-forzado","/liberar ","/transferir ",""),
    "en": CoordinationProfile("en","status: available","status: reserved","status: recovery required","status: in review","status: completed","status: cancelled","status: blocked","work/issue-","Reservation","brvtal-work-reservation","brvtal-reservation-id","/take","/force-release","/release ","/transfer ","/recover "),
}

SESSION_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
CLOSING_RE = re.compile(r"(?im)\b(?:closes|fixes|resolves)\s+#(\d+)\b")

def configure_profile(name: str) -> CoordinationProfile:
    """Activa uno de los perfiles cerrados y recompone sus contratos derivados."""
    if name not in PROFILES:
        raise RuntimeError(f"Perfil de coordinación no permitido: {name}")
    p = PROFILES[name]
    global PROFILE, STATUS_AVAILABLE, STATUS_RESERVED, STATUS_RECOVERY
    global STATUS_REVIEW, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_BLOCKED
    global STATUS_LABELS, BRANCH_RE, RESERVATION_LINE_RE, RESERVATION_HIDDEN_RE, RESERVATION_RE
    PROFILE = p
    STATUS_AVAILABLE, STATUS_RESERVED, STATUS_RECOVERY = p.available, p.reserved, p.recovery
    STATUS_REVIEW, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_BLOCKED = p.review, p.completed, p.cancelled, p.blocked
    STATUS_LABELS = {
        STATUS_AVAILABLE: ("2DA44E", "Available work."),
        STATUS_RESERVED: ("FBCA04", "Reserved work."),
        STATUS_RECOVERY: ("D93F0B", "Recovery required."),
        STATUS_REVIEW: ("1D76DB", "Work in review."),
        STATUS_COMPLETED: ("0E8A16", "Completed work."),
        STATUS_CANCELLED: ("6E7781", "Cancelled work."),
        STATUS_BLOCKED: ("000000", "Blocked work."),
    }
    BRANCH_RE = re.compile(rf"^{re.escape(p.branch_prefix)}(\d+)$")
    RESERVATION_LINE_RE = re.compile(rf"(?im)^{re.escape(p.visible_reservation)}:\s*({SESSION_RE.pattern[1:-1]})\s*$")
    RESERVATION_HIDDEN_RE = re.compile(rf"<!--\s*{re.escape(p.hidden_marker)}:\s*({SESSION_RE.pattern[1:-1]})\s*-->")
    RESERVATION_RE = re.compile(rf"<!-- {re.escape(p.marker)} (\{{[^}}]*\}}) -->")
    return p

def branch_for_issue(issue_number: int) -> str:
    """Construye la rama canónica del Issue para el perfil activo."""
    return f"{PROFILE.branch_prefix}{issue_number}"

configure_profile("es")


class CoordinationError(RuntimeError):
    """Representa un rechazo seguro de una operación de coordinación."""


@dataclass
class GitHubError(RuntimeError):
    """Representa un error HTTP devuelto por GitHub."""

    status: int
    message: str

    def __str__(self) -> str:
        """Devuelve una representación legible del error de GitHub."""
        return f"GitHub API {self.status}: {self.message}"


class GitHub:
    """Cliente REST mínimo para las operaciones de coordinación requeridas."""

    def __init__(self, repo: str, token: str | None = None) -> None:
        """Inicializa el cliente para un repositorio owner/name."""
        self.repo = repo
        self.token = token or TOKEN
        if not self.token:
            raise CoordinationError("Falta GH_TOKEN/GITHUB_TOKEN para consultar GitHub.")

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        allow: tuple[int, ...] = (),
    ) -> Any:
        """Ejecuta una llamada JSON autenticada a la API de GitHub."""
        url = f"{API_URL}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "condor-coordinacion",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
                return None if not raw else json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code in allow:
                return None
            try:
                message = json.loads(raw).get("message", raw)
            except json.JSONDecodeError:
                message = raw
            raise GitHubError(exc.code, str(message)) from exc

    def paginate(self, path: str) -> list[dict[str, Any]]:
        """Recorre una colección paginada de GitHub y devuelve todos sus elementos."""
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            separator = "&" if "?" in path else "?"
            payload = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(payload, list):
                break
            items.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < 100:
                break
            page += 1
        return items

    def issue(self, number: int) -> dict[str, Any]:
        """Obtiene un Issue por número."""
        payload = self.request("GET", f"/repos/{self.repo}/issues/{number}")
        if not isinstance(payload, dict):
            raise CoordinationError(f"No fue posible leer Issue #{number}.")
        return payload

    def pull(self, number: int) -> dict[str, Any]:
        """Obtiene un Pull Request por número."""
        payload = self.request("GET", f"/repos/{self.repo}/pulls/{number}")
        if not isinstance(payload, dict):
            raise CoordinationError(f"No fue posible leer PR #{number}.")
        return payload

    def comment(self, issue_number: int, body: str) -> None:
        """Publica un comentario en un Issue o Pull Request."""
        self.request(
            "POST",
            f"/repos/{self.repo}/issues/{issue_number}/comments",
            {"body": body},
        )

    def create_failed_check(
        self,
        name: str,
        head_sha: str,
        title: str,
        summary: str,
    ) -> None:
        """Publica un check terminal failure sobre un SHA exacto."""
        self.request(
            "POST",
            f"/repos/{self.repo}/check-runs",
            {
                "name": name,
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "failure",
                "output": {
                    "title": title[:255],
                    "summary": summary[:65_535],
                },
            },
        )

    def ensure_label(self, name: str, color: str, description: str) -> None:
        """Crea un label si todavía no existe."""
        encoded = quote(name, safe="")
        current = self.request(
            "GET",
            f"/repos/{self.repo}/labels/{encoded}",
            allow=(404,),
        )
        if current is None:
            self.request(
                "POST",
                f"/repos/{self.repo}/labels",
                {"name": name, "color": color, "description": description},
            )

    def ensure_status_labels(self) -> None:
        """Asegura que todos los estados de coordinación existan como labels."""
        for name, (color, description) in STATUS_LABELS.items():
            self.ensure_label(name, color, description)

    def add_labels(self, issue_number: int, labels: list[str]) -> None:
        """Añade labels a un Issue."""
        if labels:
            self.request(
                "POST",
                f"/repos/{self.repo}/issues/{issue_number}/labels",
                {"labels": labels},
            )

    def remove_label(self, issue_number: int, label: str) -> None:
        """Retira un label, ignorando que ya no exista."""
        encoded = quote(label, safe="")
        self.request(
            "DELETE",
            f"/repos/{self.repo}/issues/{issue_number}/labels/{encoded}",
            allow=(404,),
        )

    def set_status(self, issue_number: int, status: str | None) -> None:
        """Mantiene un estado visible sin abrir una ventana transitoria sin estado."""
        self.ensure_status_labels()
        if status:
            self.add_labels(issue_number, [status])
        for label in STATUS_LABELS:
            if label != status:
                self.remove_label(issue_number, label)

    def branch_sha(self, branch: str) -> str | None:
        """Devuelve el SHA de una rama o None si no existe."""
        encoded = quote(branch, safe="/")
        payload = self.request(
            "GET",
            f"/repos/{self.repo}/git/ref/heads/{encoded}",
            allow=(404,),
        )
        if not isinstance(payload, dict):
            return None
        obj = payload.get("object")
        return str(obj.get("sha")) if isinstance(obj, dict) and obj.get("sha") else None

    def create_branch(self, branch: str, sha: str) -> bool:
        """Crea una rama de forma atómica; False significa que ya existía."""
        try:
            self.request(
                "POST",
                f"/repos/{self.repo}/git/refs",
                {"ref": f"refs/heads/{branch}", "sha": sha},
            )
        except GitHubError as exc:
            if exc.status == 422:
                return False
            raise
        return True

    def delete_branch(self, branch: str) -> None:
        """Elimina una rama de forma idempotente sin ocultar errores reales."""
        encoded = quote(branch, safe="/")
        try:
            self.request(
                "DELETE",
                f"/repos/{self.repo}/git/refs/heads/{encoded}",
                allow=(404,),
            )
        except GitHubError as exc:
            if exc.status != 422:
                raise
            if self.branch_sha(branch) is not None:
                raise

    def issue_comments(self, issue_number: int) -> list[dict[str, Any]]:
        """Obtiene todos los comentarios de un Issue."""
        return self.paginate(f"/repos/{self.repo}/issues/{issue_number}/comments")

    def open_pulls(self) -> list[dict[str, Any]]:
        """Obtiene todos los Pull Requests abiertos."""
        return self.paginate(f"/repos/{self.repo}/pulls?state=open")

    def open_issues(self) -> list[dict[str, Any]]:
        """Obtiene Issues abiertos, sin incluir Pull Requests."""
        return [
            issue
            for issue in self.paginate(f"/repos/{self.repo}/issues?state=open")
            if not issue.get("pull_request")
        ]

    def pull_files(self, number: int) -> set[str]:
        """Devuelve los archivos modificados por un Pull Request."""
        files = self.paginate(f"/repos/{self.repo}/pulls/{number}/files")
        return {
            str(item["filename"])
            for item in files
            if isinstance(item.get("filename"), str)
        }

    def close_pull(self, number: int) -> None:
        """Cierra un Pull Request sin fusionarlo."""
        self.request(
            "PATCH",
            f"/repos/{self.repo}/pulls/{number}",
            {"state": "closed"},
        )

    def update_pull_body(self, number: int, body: str) -> None:
        """Actualiza metadata de coordinación sin crear un PR nuevo."""
        self.request(
            "PATCH",
            f"/repos/{self.repo}/pulls/{number}",
            {"body": body},
        )

    def commit_timestamp(self, sha: str) -> datetime | None:
        """Obtiene el instante del commit que representa actividad de la rama."""
        payload = self.request("GET", f"/repos/{self.repo}/commits/{sha}")
        if not isinstance(payload, dict):
            return None
        commit = payload.get("commit")
        if not isinstance(commit, dict):
            return None
        for key in ("committer", "author"):
            identity = commit.get(key)
            if isinstance(identity, dict):
                parsed = parse_github_time(identity.get("date"))
                if parsed is not None:
                    return parsed
        return None

    def try_assign(self, issue_number: int, login: str) -> None:
        """Intenta asignar el Issue sin convertir la asignación en requisito duro."""
        self.request(
            "POST",
            f"/repos/{self.repo}/issues/{issue_number}/assignees",
            {"assignees": [login]},
            allow=(404, 422),
        )

    def try_unassign(self, issue_number: int, login: str) -> None:
        """Intenta retirar la asignación del propietario anterior."""
        self.request(
            "DELETE",
            f"/repos/{self.repo}/issues/{issue_number}/assignees",
            {"assignees": [login]},
            allow=(404, 422),
        )


def issue_from_branch(branch: str) -> int | None:
    """Extrae el número de Issue de la rama canónica."""
    match = BRANCH_RE.fullmatch(branch)
    return int(match.group(1)) if match else None


def closing_issues(body: str) -> set[int]:
    """Extrae referencias Closes/Fixes/Resolves del cuerpo de un PR."""
    return {int(value) for value in CLOSING_RE.findall(body or "")}


def reservation_from_pr_body(body: str) -> str | None:
    """Extrae el ID de reserva visible legacy u oculto de un Pull Request."""
    value = body or ""
    match = RESERVATION_HIDDEN_RE.search(value) or RESERVATION_LINE_RE.search(value)
    return match.group(1).lower() if match else None


def new_reservation_id() -> str:
    """Genera un identificador único para una sesión de trabajo."""
    return str(uuid.uuid4())


def parse_github_time(value: Any) -> datetime | None:
    """Convierte timestamps ISO de GitHub a UTC, ignorando valores inválidos."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def reservation_marker(
    owner: str,
    reservation_id: str,
    branch: str,
    active: bool,
    reason: str,
    acceptance_sha256: str | None = None,
    task_marker: dict[str, Any] | None = None,
    task_snapshot: dict[str, Any] | None = None,
) -> str:
    """Serializa un marcador de reserva con aceptación y claims fijados."""
    payload: dict[str, Any] = {
        "version": 1,
        "owner": owner,
        "reservation_id": reservation_id.lower(),
        "branch": branch,
        "active": active,
        "reason": reason,
    }
    if acceptance_sha256 is not None:
        if re.fullmatch(r"[0-9a-f]{64}", acceptance_sha256) is None:
            raise CoordinationError("Fingerprint de aceptación inválido.")
        payload["version"] = 2
        payload["acceptance_sha256"] = acceptance_sha256

    snapshot = task_snapshot
    if task_marker is not None:
        fingerprint = task_marker_fingerprint(task_marker)
        if fingerprint is None:
            raise CoordinationError("Marker planificado inválido.")
        snapshot = {
            "task_marker_sha256": fingerprint,
            "task_paths": list(task_marker["paths"]),
            "task_depends_on": list(task_marker["depends_on"]),
        }
    if snapshot is not None:
        if acceptance_sha256 is None:
            raise CoordinationError("Claims fijados requieren acceptance_sha256.")
        fingerprint = snapshot.get("task_marker_sha256")
        paths = snapshot.get("task_paths")
        dependencies = snapshot.get("task_depends_on")
        if (
            not isinstance(fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            or not isinstance(paths, list)
            or not paths
            or not all(isinstance(path, str) and path for path in paths)
            or not isinstance(dependencies, list)
            or not all(
                isinstance(number, int)
                and not isinstance(number, bool)
                and number > 0
                for number in dependencies
            )
        ):
            raise CoordinationError("Snapshot de task inválido.")
        payload["version"] = 3
        payload["task_marker_sha256"] = fingerprint
        payload["task_paths"] = list(paths)
        payload["task_depends_on"] = list(dependencies)

    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return f"<!-- {PROFILE.marker} {encoded} -->"


def reservation_task_snapshot(
    reservation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Extrae claims fijados de una reserva V3."""
    if not reservation or reservation.get("version") != 3:
        return None
    return {
        "task_marker_sha256": reservation["task_marker_sha256"],
        "task_paths": list(reservation["task_paths"]),
        "task_depends_on": list(reservation["task_depends_on"]),
    }


def reservation_task_marker(
    reservation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Proyecta un snapshot V3 al mínimo requerido por el orquestador."""
    snapshot = reservation_task_snapshot(reservation)
    if snapshot is None:
        return None
    return {
        "paths": snapshot["task_paths"],
        "depends_on": snapshot["task_depends_on"],
    }


def valid_reservation_payload(value: Any) -> bool:
    """Valida esquema y tipos de un marcador de reserva."""
    if not isinstance(value, dict):
        return False
    base = {
        "version",
        "owner",
        "reservation_id",
        "branch",
        "active",
        "reason",
    }
    version = value.get("version")
    if version == 1:
        if set(value) != base:
            return False
    elif version == 2:
        if set(value) != base | {"acceptance_sha256"}:
            return False
    elif version == 3:
        if set(value) != base | {
            "acceptance_sha256",
            "task_marker_sha256",
            "task_paths",
            "task_depends_on",
        }:
            return False
        marker_fingerprint = value.get("task_marker_sha256")
        paths = value.get("task_paths")
        dependencies = value.get("task_depends_on")
        if (
            not isinstance(marker_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", marker_fingerprint) is None
            or not isinstance(paths, list)
            or not paths
            or not all(isinstance(path, str) and path for path in paths)
            or not isinstance(dependencies, list)
            or not all(
                isinstance(number, int)
                and not isinstance(number, bool)
                and number > 0
                for number in dependencies
            )
        ):
            return False
    else:
        return False

    if version in (2, 3):
        fingerprint = value.get("acceptance_sha256")
        if (
            not isinstance(fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
        ):
            return False
    if not isinstance(value.get("owner"), str) or not value["owner"]:
        return False
    reservation_id = value.get("reservation_id")
    if not isinstance(reservation_id, str) or not SESSION_RE.fullmatch(
        reservation_id.lower()
    ):
        return False
    branch = value.get("branch")
    if not isinstance(branch, str) or BRANCH_RE.fullmatch(branch) is None:
        return False
    if not isinstance(value.get("active"), bool):
        return False
    return isinstance(value.get("reason"), str) and bool(value["reason"])

def reservation_from_text(text: str) -> dict[str, Any] | None:
    """Extrae el último marcador de reserva válido de un texto."""
    latest: dict[str, Any] | None = None
    for match in RESERVATION_RE.finditer(text or ""):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if valid_reservation_payload(parsed):
            latest = parsed
    return latest


def latest_reservation(
    comments: list[dict[str, Any]],
    trusted_login: str = TRUSTED_MARKER_LOGIN,
) -> dict[str, Any] | None:
    """Devuelve solo el último marcador publicado por la identidad confiable."""
    latest: dict[str, Any] | None = None
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != trusted_login:
            continue
        parsed = reservation_from_text(str(comment.get("body") or ""))
        if parsed is not None:
            latest = parsed
    return latest


def latest_reservation_timestamp(
    comments: list[dict[str, Any]],
    trusted_login: str = TRUSTED_MARKER_LOGIN,
) -> datetime | None:
    """Devuelve cuándo se publicó o actualizó el último marcador confiable."""
    latest: datetime | None = None
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != trusted_login:
            continue
        if reservation_from_text(str(comment.get("body") or "")) is None:
            continue
        timestamp = parse_github_time(
            comment.get("updated_at") or comment.get("created_at")
        )
        if timestamp is not None:
            latest = timestamp
    return latest


def human_issue_activity_timestamp(
    comments: list[dict[str, Any]],
) -> datetime | None:
    """Toma comentarios humanos útiles, excluyendo comandos de coordinación."""
    latest: datetime | None = None
    for comment in comments:
        user = comment.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if login == TRUSTED_MARKER_LOGIN:
            continue
        body = str(comment.get("body") or "").strip()
        if (
            body == PROFILE.take
            or body == PROFILE.force_release
            or (PROFILE.release and body.startswith(PROFILE.release))
            or (PROFILE.transfer and body.startswith(PROFILE.transfer))
            or (PROFILE.recover and body.startswith(PROFILE.recover))
        ):
            continue
        timestamp = parse_github_time(
            comment.get("updated_at") or comment.get("created_at")
        )
        if timestamp is not None and (latest is None or timestamp > latest):
            latest = timestamp
    return latest


def file_overlaps(
    current_files: set[str],
    others: dict[int, set[str]],
) -> dict[int, list[str]]:
    """Calcula solapamientos exactos de archivos contra otros PR."""
    collisions: dict[int, list[str]] = {}
    for pr_number, files in others.items():
        overlap = sorted(current_files & files)
        if overlap:
            collisions[pr_number] = overlap
    return collisions


def label_names(issue: dict[str, Any]) -> set[str]:
    """Convierte los labels de la API en un conjunto de nombres."""
    result: set[str] = set()
    for label in issue.get("labels", []):
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            result.add(label["name"])
    return result


def authorized(association: str) -> bool:
    """Indica si la asociación del actor permite controlar reservas."""
    return association.upper() in ALLOWED_ASSOCIATIONS


def active_reservation(api: GitHub, issue_number: int) -> dict[str, Any] | None:
    """Obtiene la reserva activa desde metadata publicada por el bot confiable."""
    reservation = latest_reservation(api.issue_comments(issue_number))
    if not reservation or not reservation["active"]:
        return None
    return reservation

def open_pull_records_for_branch(
    api: GitHub,
    branch: str,
) -> list[dict[str, Any]]:
    """Devuelve los PR abiertos que continúan exactamente la rama reservada."""
    result: list[dict[str, Any]] = []
    for pull in api.open_pulls():
        head = pull.get("head")
        if isinstance(head, dict) and head.get("ref") == branch:
            result.append(pull)
    return result


def open_pulls_for_branch(api: GitHub, branch: str) -> list[int]:
    """Lista PR abiertos que usan una rama concreta como head."""
    result: list[int] = []
    for pull in open_pull_records_for_branch(api, branch):
        number = pull.get("number")
        if isinstance(number, int):
            result.append(number)
    return result


def work_activity_timestamp(
    api: GitHub,
    issue_number: int,
    branch: str,
) -> datetime | None:
    """Calcula la señal más reciente sin contar el comando /tomar actual."""
    candidates: list[datetime] = []
    comments = api.issue_comments(issue_number)
    lease_start = latest_reservation_timestamp(comments)
    if lease_start is not None:
        candidates.append(lease_start)
    human_activity = human_issue_activity_timestamp(comments)
    if human_activity is not None:
        candidates.append(human_activity)

    branch_sha = api.branch_sha(branch)
    if branch_sha:
        timestamp = api.commit_timestamp(branch_sha)
        if timestamp is not None:
            candidates.append(timestamp)

    return max(candidates) if candidates else None


def reservation_id(reservation: dict[str, Any] | None) -> str | None:
    """Extrae el UUID de una reserva si existe."""
    if reservation is None:
        return None
    value = reservation.get("reservation_id")
    return str(value) if value is not None else None


def stale_recovery_candidate(
    api: GitHub,
    issue: dict[str, Any],
) -> tuple[int, str, str, str | None] | None:
    """Prepara un candidato stale sin mutar estado ni adquirir locks."""
    number = issue.get("number")
    if not isinstance(number, int) or STATUS_BLOCKED in label_names(issue):
        return None

    branch = branch_for_issue(number)
    initial_reservation = active_reservation(api, number)
    branch_sha = api.branch_sha(branch)
    if not (initial_reservation or branch_sha):
        return None
    if branch_sha is None or not work_is_stale(api, number, branch):
        return None

    return number, branch, branch_sha, reservation_id(initial_reservation)


def recovery_candidate_still_valid(
    api: GitHub,
    number: int,
    branch: str,
    initial_reservation_id: str | None,
) -> bool:
    """Revalida el candidato dentro del lock distribuido."""
    issue = api.issue(number)
    labels = label_names(issue)
    if issue.get("state") != "open" or STATUS_BLOCKED in labels:
        return False
    if STATUS_RECOVERY in labels:
        return False

    current_reservation = active_reservation(api, number)
    if reservation_id(current_reservation) != initial_reservation_id:
        return False
    if not (current_reservation or api.branch_sha(branch)):
        return False

    return work_is_stale(api, number, branch)


def mark_stale_reservation(
    api: GitHub,
    issue: dict[str, Any],
) -> bool:
    """Marca un único candidato stale bajo el lock compartido con /tomar."""
    candidate = stale_recovery_candidate(api, issue)
    if candidate is None:
        return False

    number, branch, branch_sha, initial_reservation_id = candidate
    lock_branch = recovery_lock_branch(number)
    if not api.create_branch(lock_branch, branch_sha):
        return False

    try:
        if not recovery_candidate_still_valid(
            api,
            number,
            branch,
            initial_reservation_id,
        ):
            return False
        api.set_status(number, STATUS_RECOVERY)
        return True
    finally:
        api.delete_branch(lock_branch)


def mark_stale_reservations(api: GitHub) -> int:
    """Marca reservas stale sin liberar, borrar ni reasignar trabajo."""
    marked = sum(
        1
        for issue in api.open_issues()
        if mark_stale_reservation(api, issue)
    )
    print(f"Reservas recuperables marcadas: {marked}")
    return marked


def work_is_stale(
    api: GitHub,
    issue_number: int,
    branch: str,
    *,
    stale_minutes: int = RESERVATION_STALE_MINUTES,
    now: datetime | None = None,
) -> bool:
    """Solo permite recuperar trabajo con evidencia suficiente de inactividad."""
    last_activity = work_activity_timestamp(api, issue_number, branch)
    if last_activity is None:
        return False
    reference = now or datetime.now(timezone.utc)
    return reference - last_activity >= timedelta(minutes=stale_minutes)


def rewrite_pull_reservation(body: str, reservation_id: str) -> str:
    """Actualiza la reserva del PR existente sin perder su descripción."""
    value = body or ""
    visible = f"{PROFILE.visible_reservation}: {reservation_id}"
    hidden = f"<!-- {PROFILE.hidden_marker}: {reservation_id} -->"

    if RESERVATION_LINE_RE.search(value):
        value = RESERVATION_LINE_RE.sub(visible, value)
    else:
        value = value.rstrip() + f"\n\n{visible}"

    if RESERVATION_HIDDEN_RE.search(value):
        value = RESERVATION_HIDDEN_RE.sub(hidden, value)
    else:
        value = value.rstrip() + f"\n\n{hidden}"

    return value + "\n"


def recover_stale_work(
    api: GitHub,
    issue_number: int,
    actor: str,
    branch: str,
    previous: dict[str, Any] | None,
) -> str | None:
    """Recupera trabajo existente conservando rama y PR."""
    reservation_id = new_reservation_id()
    open_pulls = open_pull_records_for_branch(api, branch)
    previous_owner = str(previous["owner"]) if previous else None
    pr_text = (
        ", ".join(
            f"#{pull['number']}"
            for pull in open_pulls
            if isinstance(pull.get("number"), int)
        )
        or "sin PR abierto"
    )
    orphaned = previous is None
    recovery_reason = (
        "recuperacion-huerfana"
        if orphaned
        else "recuperacion-inactividad"
    )
    recovery_message = (
        (
            "Reserva recuperada porque la rama canónica existe sin una "
            "reserva activa. "
        )
        if orphaned
        else (
            f"Reserva recuperada por inactividad de al menos "
            f"{RESERVATION_STALE_MINUTES} minutos. "
        )
    )

    previous_fingerprint = (
        previous.get("acceptance_sha256")
        if isinstance(previous, dict)
        else None
    )
    if previous is None:
        raise CoordinationError(
            "Rama huérfana sin reserva activa: ejecuta "
            "/adoptar-contrato-huerfana para fijar el contrato antes de recuperar."
        )
    acceptance_sha256 = reservation_fingerprint_for_profile(
        api, issue_number, previous, "recuperar"
    )
    task_snapshot = reservation_task_snapshot(previous)
    task_marker = (
        None
        if task_snapshot is not None
        else parse_task_marker(str(api.issue(issue_number).get("body") or ""))
    )

    publish_reservation(
        api,
        issue_number,
        actor,
        reservation_id,
        branch,
        True,
        recovery_reason,
        (
            f"{recovery_message}Se conserva la rama {branch} y {pr_text} "
            "para continuar el trabajo existente sin abrir una "
            "implementación paralela."
        ),
        acceptance_sha256,
        task_marker,
        task_snapshot,
    )

    winner = active_reservation(api, issue_number)
    if not winner or winner["reservation_id"] != reservation_id:
        return None

    api.set_status(
        issue_number,
        STATUS_REVIEW if open_pulls else STATUS_RESERVED,
    )
    api.try_assign(issue_number, actor)
    if previous_owner and previous_owner != actor:
        api.try_unassign(issue_number, previous_owner)

    for pull in open_pulls:
        number = pull.get("number")
        if not isinstance(number, int):
            continue
        body = str(api.pull(number).get("body") or "")
        api.update_pull_body(
            number,
            rewrite_pull_reservation(body, reservation_id),
        )

    print(
        f"Reserva recuperada: Issue #{issue_number} -> {branch} "
        f"(@{actor}, {reservation_id}); se reutiliza {pr_text}."
    )
    return reservation_id


def publish_reservation(
    api: GitHub,
    issue_number: int,
    owner: str,
    reservation_id: str,
    branch: str,
    active: bool,
    reason: str,
    message: str,
    acceptance_sha256: str | None = None,
    task_marker: dict[str, Any] | None = None,
    task_snapshot: dict[str, Any] | None = None,
) -> None:
    """Publica un marcador de reserva y su mensaje humano en un solo comentario."""
    api.comment(
        issue_number,
        (
            f"{reservation_marker(owner, reservation_id, branch, active, reason, acceptance_sha256, task_marker, task_snapshot)}\n"
            f"{message}"
        ),
    )


def ensure_recovery_branch(api: GitHub, branch: str) -> bool:
    """Garantiza la rama canónica sin reemplazar trabajo existente."""
    if api.branch_sha(branch) is not None:
        return True

    main_sha = api.branch_sha("main")
    if not main_sha:
        raise CoordinationError("No fue posible resolver el SHA actual de main.")

    if api.create_branch(branch, main_sha):
        return True
    return api.branch_sha(branch) is not None


def reserve_available_work(
    api: GitHub,
    issue_number: int,
    actor: str,
    branch: str,
    acceptance_sha256: str,
    parallel_evidence: list[str] | None = None,
    task_marker: dict[str, Any] | None = None,
) -> str | None:
    """Crea una reserva nueva para un Issue realmente disponible."""
    main_sha = api.branch_sha("main")
    if not main_sha:
        raise CoordinationError("No fue posible resolver el SHA actual de main.")
    if not api.create_branch(branch, main_sha):
        return None

    reservation_id = new_reservation_id()
    reservation_comment = reservation_marker(
        actor,
        reservation_id,
        branch,
        True,
        "tomar",
        acceptance_sha256,
        task_marker,
    )
    if parallel_evidence:
        reservation_comment += (
            "\n\nCompatibilidad paralela verificada "
            "(dependencias completadas + claims disjuntos):\n"
            + "\n".join(f"- {item}" for item in parallel_evidence)
        )

    try:
        api.set_status(issue_number, STATUS_RESERVED)
        api.try_assign(issue_number, actor)
        api.comment(issue_number, reservation_comment)
    except Exception:
        api.delete_branch(branch)
        api.try_unassign(issue_number, actor)
        try:
            api.set_status(issue_number, STATUS_AVAILABLE)
        except Exception:
            pass
        raise

    print(
        f"Reserva concedida: Issue #{issue_number} -> {branch} "
        f"(@{actor}, {reservation_id})"
    )
    return reservation_id


def recovery_lock_branch(issue_number: int) -> str:
    """Nombra el lock efímero que serializa recuperaciones del mismo Issue."""
    return f"coordinacion/lock-issue-{issue_number}"


def recover_existing_work_if_stale(
    api: GitHub,
    issue_number: int,
    actor: str,
    branch: str,
    current: dict[str, Any] | None,
) -> str | None:
    """Recupera trabajo stale o huérfano bajo un lock distribuido."""
    if current is not None and not work_is_stale(
        api,
        issue_number,
        branch,
    ):
        return None
    if not ensure_recovery_branch(api, branch):
        return None

    branch_sha = api.branch_sha(branch)
    if branch_sha is None:
        return None

    lock_branch = recovery_lock_branch(issue_number)
    if not api.create_branch(lock_branch, branch_sha):
        return None

    try:
        latest = active_reservation(api, issue_number)
        if latest is not None and not work_is_stale(
            api,
            issue_number,
            branch,
        ):
            return None
        return recover_stale_work(
            api,
            issue_number,
            actor,
            branch,
            latest if latest is not None else current,
        )
    finally:
        api.delete_branch(lock_branch)


def recovery_issue_numbers(api: GitHub) -> list[int]:
    """Lista Issues abiertos que deben recuperarse antes de abrir trabajo nuevo."""
    numbers: list[int] = []
    for issue in api.open_issues():
        number = issue.get("number")
        if (
            isinstance(number, int)
            and issue.get("state") == "open"
            and STATUS_BLOCKED not in label_names(issue)
            and STATUS_RECOVERY in label_names(issue)
        ):
            numbers.append(number)
    return sorted(numbers)


def reserve_work(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
) -> str | None:
    """Reserva trabajo nuevo o recupera una reserva realmente inactiva."""
    if not authorized(association):
        raise CoordinationError(
            f"@{actor} no tiene una asociación autorizada para reservar trabajo."
        )

    issue = api.issue(issue_number)
    if issue.get("pull_request"):
        raise CoordinationError("La reserva se ejecuta sobre Issues, no PRs.")
    if issue.get("state") != "open":
        raise CoordinationError(f"Issue #{issue_number} no está abierto.")

    issue_body = str(issue.get("body") or "")
    try:
        parse_contract(issue_body)
        acceptance_sha256 = contract_fingerprint(issue_body)
    except AcceptanceError as exc:
        raise CoordinationError(
            f"Issue #{issue_number} no tiene criterios de aceptación ejecutables válidos: {exc}"
        ) from exc

    labels = label_names(issue)
    if STATUS_BLOCKED in labels:
        print(
            f"Trabajo no reservado: Issue #{issue_number} tiene {STATUS_BLOCKED}."
        )
        return None

    branch = branch_for_issue(issue_number)
    current = (
        active_reservation(api, issue_number)
        if hasattr(api, "issue_comments")
        else None
    )
    branch_sha = (
        api.branch_sha(branch)
        if hasattr(api, "branch_sha")
        else None
    )
    if current or branch_sha:
        return recover_existing_work_if_stale(
            api,
            issue_number,
            actor,
            branch,
            current,
        )

    if STATUS_AVAILABLE not in labels:
        return None

    pending_recovery = recovery_issue_numbers(api)
    if pending_recovery:
        rendered = ", ".join(f"#{number}" for number in pending_recovery)
        print(
            "Trabajo nuevo pospuesto: primero debe recuperarse "
            f"{rendered}."
        )
        return None

    try:
        task_marker = parse_task_marker(str(issue.get("body") or ""))
        dependency_states = (
            {
                number: api.issue(number)
                for number in task_marker["depends_on"]
            }
            if task_marker is not None
            else None
        )
        open_issues = api.open_issues()
        active_task_snapshots: dict[int, dict[str, Any]] | None = None
        active_dependency_states: dict[int, dict[int, dict[str, Any]]] | None = None
        if hasattr(api, "issue_comments"):
            active_task_snapshots = {}
            active_dependency_states = {}
            active_statuses = {
                STATUS_RESERVED,
                STATUS_REVIEW,
                STATUS_RECOVERY,
                "status: reserved",
                "status: in review",
                "status: recovery required",
            }
            for other in open_issues:
                other_number = other.get("number")
                if (
                    not isinstance(other_number, int)
                    or other_number == issue_number
                    or not (label_names(other) & active_statuses)
                ):
                    continue
                other_reservation = active_reservation(api, other_number)
                other_marker = reservation_task_marker(other_reservation)
                if other_marker is not None:
                    active_task_snapshots[other_number] = other_marker
                    active_dependency_states[other_number] = {
                        number: api.issue(number)
                        for number in other_marker["depends_on"]
                    }

        plan_blockers = reservation_blockers(
            issue,
            open_issues,
            actor,
            dependency_states,
            active_task_snapshots,
            active_dependency_states,
        )
    except PlanError as exc:
        raise CoordinationError(
            f"Plan de orquestación inválido en Issue #{issue_number}: {exc}"
        ) from exc
    if plan_blockers:
        details = "\n".join(f"- {item}" for item in plan_blockers)
        raise CoordinationError(
            f"Orquestador bloquea /tomar para Issue #{issue_number}:\n{details}"
        )

    parallel_evidence = parallel_compatibility_evidence(
        issue,
        open_issues,
        active_task_snapshots,
    )

    return reserve_available_work(
        api,
        issue_number,
        actor,
        branch,
        acceptance_sha256,
        parallel_evidence,
        task_marker,
    )

def reservation_fingerprint_for_profile(
    api: GitHub,
    issue_number: int,
    reservation: dict[str, Any],
    operation: str,
) -> str:
    """Devuelve fingerprint v2; EN puede adoptar un marker BRVTAL v1 con contrato válido."""
    pinned = reservation.get("acceptance_sha256")
    if isinstance(pinned, str):
        return pinned
    if PROFILE.name != "en":
        raise CoordinationError(
            f"Reserva legacy v1 en Issue #{issue_number}: ejecuta "
            f"/migrar-contrato {reservation['reservation_id']} antes de {operation}."
        )
    issue = api.issue(issue_number)
    try:
        parse_contract(str(issue.get("body") or ""))
        return contract_fingerprint(str(issue.get("body") or ""))
    except AcceptanceError as exc:
        raise CoordinationError(
            f"Reserva BRVTAL legacy en Issue #{issue_number} sin contrato válido."
        ) from exc


def transfer_work(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
    reservation_id: str,
) -> str | None:
    """Transfiere una reserva a otra sesión del mismo actor mediante un nuevo ID."""
    if not authorized(association):
        raise CoordinationError(
            f"@{actor} no tiene una asociación autorizada para transferir trabajo."
        )
    current = active_reservation(api, issue_number)
    if not current:
        return None
    if current["owner"] != actor or current["reservation_id"] != reservation_id.lower():
        return None

    new_id = new_reservation_id()
    branch = str(current["branch"])
    acceptance_sha256 = reservation_fingerprint_for_profile(
        api, issue_number, current, "transferir"
    )
    open_pulls = open_pull_records_for_branch(api, branch)
    originals: list[tuple[int, str]] = []
    for pull in open_pulls:
        number = pull.get("number")
        if not isinstance(number, int):
            continue
        originals.append((number, str(api.pull(number).get("body") or "")))

    try:
        for number, body in originals:
            api.update_pull_body(
                number,
                rewrite_pull_reservation(body, new_id),
            )
        api.comment(
            issue_number,
            reservation_marker(
                actor,
                new_id,
                branch,
                True,
                "transferir",
                acceptance_sha256,
                task_snapshot=reservation_task_snapshot(current),
            ),
        )
    except Exception:
        for number, body in originals:
            try:
                api.update_pull_body(number, body)
            except Exception:
                pass
        raise

    winner = active_reservation(api, issue_number)
    if not winner or winner["reservation_id"] != new_id:
        for number, body in originals:
            try:
                api.update_pull_body(number, body)
            except Exception:
                pass
        return None

    print(f"Reserva transferida: Issue #{issue_number} -> {new_id}")
    return new_id




def trusted_reservation_history(
    comments: list[dict[str, Any]],
    trusted_login: str = TRUSTED_MARKER_LOGIN,
) -> list[dict[str, Any]]:
    """Devuelve markers confiables en orden de publicación."""
    history: list[dict[str, Any]] = []
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != trusted_login:
            continue
        parsed = reservation_from_text(str(comment.get("body") or ""))
        if parsed is not None:
            history.append(parsed)
    return history


def renewal_successor(
    comments: list[dict[str, Any]],
    reservation_id: str,
    owner: str,
) -> dict[str, Any] | None:
    """Reconoce solo el sucesor inmediato y confiable de una renovación."""
    wanted = reservation_id.lower()
    history = trusted_reservation_history(comments)
    for index in range(len(history) - 1, -1, -1):
        current = history[index]
        if current.get("reservation_id") != wanted:
            continue
        if current.get("owner") != owner:
            return None
        if index + 1 >= len(history):
            return None
        successor = history[index + 1]
        if (
            successor.get("reason") == "renovar-contrato"
            and successor.get("owner") == owner
            and successor.get("branch") == current.get("branch")
            and successor.get("active") is True
            and isinstance(successor.get("acceptance_sha256"), str)
        ):
            return successor
        return None
    return None


def _reconcile_renewal_pull(
    api: GitHub,
    number: int,
    original_body: str,
    requested_id: str,
    new_id: str,
) -> dict[str, Any] | None:
    """Alinea metadata del PR con la reserva ganadora sin pisar terceros."""
    winner = active_reservation(api, issue_from_branch(
        str(api.pull(number).get("head", {}).get("ref") or "")
    ) or 0)
    if winner is None:
        return None

    winner_id = str(winner.get("reservation_id") or "")
    current_body = str(api.pull(number).get("body") or "")
    current_pr_id = reservation_from_pr_body(current_body)

    if winner_id == new_id:
        if current_pr_id != new_id:
            api.update_pull_body(number, rewrite_pull_reservation(current_body, new_id))
        return winner

    if winner_id == requested_id.lower():
        if current_pr_id != requested_id.lower():
            api.update_pull_body(number, original_body)
        return winner

    # Una tercera sesión ganó. No tocar su metadata.
    return winner


def renew_pinned_acceptance(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
    reservation_id: str,
) -> str | None:
    """Renueva v2 con evidencia canónica y reconciliación idempotente."""
    if not authorized(association):
        raise CoordinationError("Actor no autorizado para renovar aceptación.")
    issue = api.issue(issue_number)
    if issue.get("state") != "open":
        raise CoordinationError("Solo se renuevan Issues abiertos.")

    requested_id = reservation_id.lower()
    current = active_reservation(api, issue_number)
    if not current or current.get("owner") != actor:
        raise CoordinationError("Sesión de reserva v2 no vigente o ajena.")

    # Retry del UUID anterior: reconocer únicamente su sucesor inmediato y
    # reconciliar la metadata del PR sin crear una tercera sesión.
    if current.get("reservation_id") != requested_id:
        successor = renewal_successor(
            api.issue_comments(issue_number), requested_id, actor
        )
        if (
            successor is None
            or successor.get("reservation_id") != current.get("reservation_id")
        ):
            raise CoordinationError("Sesión de reserva v2 no vigente o ajena.")
        branch = str(successor["branch"])
        pulls = open_pull_records_for_branch(api, branch)
        if len(pulls) != 1 or not isinstance(pulls[0].get("number"), int):
            raise CoordinationError("Se requiere exactamente un PR abierto de la rama.")
        number = pulls[0]["number"]
        body = str(api.pull(number).get("body") or "")
        if reservation_from_pr_body(body) != successor["reservation_id"]:
            api.update_pull_body(
                number,
                rewrite_pull_reservation(body, str(successor["reservation_id"])),
            )
        print(
            f"Renovación ya vigente: Issue #{issue_number} -> "
            f"{successor['reservation_id']} (reconciliada)."
        )
        return str(successor["reservation_id"])

    old_pin = current.get("acceptance_sha256")
    if not isinstance(old_pin, str):
        raise CoordinationError("La reserva legacy requiere /migrar-contrato.")

    new_pin = contract_fingerprint(str(issue.get("body") or ""))
    new_task_marker = parse_task_marker(str(issue.get("body") or ""))
    new_task_pin = task_marker_fingerprint(new_task_marker)
    old_task_pin = current.get("task_marker_sha256")
    if new_pin == old_pin and new_task_pin == old_task_pin:
        raise CoordinationError("No hay cambio contractual que renovar.")

    branch = branch_for_issue(issue_number)
    if current.get("branch") != branch or not api.branch_sha(branch):
        raise CoordinationError("La rama canónica de la reserva no está disponible.")
    pulls = open_pull_records_for_branch(api, branch)
    if len(pulls) != 1 or not isinstance(pulls[0].get("number"), int):
        raise CoordinationError("Se requiere exactamente un PR abierto de la rama.")

    number = pulls[0]["number"]
    pull = api.pull(number)
    head = pull.get("head")
    sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(sha, str) or not sha or head.get("ref") != branch:
        raise CoordinationError("No fue posible fijar el HEAD exacto del PR.")

    original = str(pull.get("body") or "")
    if reservation_from_pr_body(original) != requested_id:
        raise CoordinationError("La metadata del PR no coincide con la sesión activa.")

    # Evidencia canónica única: el gate agregado queda failure antes de cualquier
    # cambio de sesión. No depende de completar dos POST separados.
    summary = (
        f"Issue #{issue_number}: contrato renovado explícitamente; "
        "la evidencia previa del HEAD no es válida. Ejecuta CI nuevo."
    )
    api.create_failed_check(
        "Validar", sha, "Renovación explícita del contrato", summary
    )

    # Releer tras invalidar para cerrar carreras antes de mutar PR/Issue.
    latest = active_reservation(api, issue_number)
    if (
        not latest
        or latest.get("reservation_id") != requested_id
        or contract_fingerprint(str(api.issue(issue_number).get("body") or ""))
        != new_pin
        or api.pull(number).get("head", {}).get("sha") != sha
    ):
        raise CoordinationError(
            "La sesión, el contrato o el HEAD cambió durante la renovación."
        )

    new_id = new_reservation_id()
    marker = reservation_marker(
        actor,
        new_id,
        branch,
        True,
        "renovar-contrato",
        new_pin,
        new_task_marker,
    )

    try:
        api.update_pull_body(number, rewrite_pull_reservation(original, new_id))
        api.comment(issue_number, marker)
    except Exception as exc:
        # El comentario puede haberse persistido aunque el cliente vea error.
        winner = active_reservation(api, issue_number)
        if winner and winner.get("reservation_id") == new_id:
            _reconcile_renewal_pull(
                api, number, original, requested_id, new_id
            )
            print(
                f"Contrato renovado tras error ambiguo: Issue #{issue_number} -> "
                f"{new_id}."
            )
            return new_id
        if winner and winner.get("reservation_id") == requested_id:
            _reconcile_renewal_pull(
                api, number, original, requested_id, new_id
            )
        # Un tercero ganador se preserva sin sobrescritura.
        raise exc

    winner = _reconcile_renewal_pull(
        api, number, original, requested_id, new_id
    )
    if (
        not winner
        or winner.get("reservation_id") != new_id
        or winner.get("acceptance_sha256") != new_pin
        or reservation_from_pr_body(str(api.pull(number).get("body") or ""))
        != new_id
    ):
        raise CoordinationError(
            "La renovación no pudo reconciliar Issue y PR; HEAD permanece bloqueado."
        )

    print(
        f"Contrato renovado: Issue #{issue_number}, sesión {new_id}, "
        f"fingerprint {old_pin[:12]} -> {new_pin[:12]}; "
        f"PR #{number} reconciliado y Validar invalidado."
    )
    return new_id


def migrate_legacy_reservation(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
    reservation_id: str,
) -> str | None:
    """Convierte explícitamente una reserva legacy v1 a v2 sin mover su sesión."""
    if not authorized(association):
        raise CoordinationError(
            f"@{actor} no tiene una asociación autorizada para migrar trabajo."
        )
    current = active_reservation(api, issue_number)
    if not current:
        return None
    if (
        current["owner"] != actor
        or current["reservation_id"] != reservation_id.lower()
    ):
        return None

    existing = current.get("acceptance_sha256")
    if isinstance(existing, str):
        print(f"Reserva ya migrada: Issue #{issue_number} -> {reservation_id.lower()}")
        return reservation_id.lower()

    issue = api.issue(issue_number)
    fingerprint = contract_fingerprint(str(issue.get("body") or ""))
    branch = str(current["branch"])
    api.comment(
        issue_number,
        reservation_marker(
            actor,
            reservation_id,
            branch,
            True,
            "migrar-contrato",
            fingerprint,
            parse_task_marker(str(issue.get("body") or "")),
        ),
    )
    winner = active_reservation(api, issue_number)
    if (
        not winner
        or winner["reservation_id"] != reservation_id.lower()
        or winner.get("acceptance_sha256") != fingerprint
    ):
        return None
    print(
        f"Contrato migrado explícitamente: Issue #{issue_number} "
        f"-> {reservation_id.lower()}"
    )
    return reservation_id.lower()


def adopt_orphaned_contract(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
) -> str | None:
    """Adopta explícitamente una rama huérfana y fija su contrato actual."""
    if not authorized(association):
        raise CoordinationError(
            f"@{actor} no tiene una asociación autorizada para adoptar trabajo."
        )
    if active_reservation(api, issue_number) is not None:
        raise CoordinationError(
            f"Issue #{issue_number} ya tiene una reserva activa; no es huérfano."
        )

    issue = api.issue(issue_number)
    if issue.get("state") != "open":
        raise CoordinationError(f"Issue #{issue_number} no está abierto.")
    branch = branch_for_issue(issue_number)
    if api.branch_sha(branch) is None:
        raise CoordinationError(
            f"No existe la rama huérfana {branch}; usa /tomar para trabajo nuevo."
        )

    fingerprint = contract_fingerprint(str(issue.get("body") or ""))
    reservation_id = new_reservation_id()
    open_pulls = open_pull_records_for_branch(api, branch)
    publish_reservation(
        api,
        issue_number,
        actor,
        reservation_id,
        branch,
        True,
        "adoptar-contrato-huerfana",
        (
            f"Rama huérfana adoptada explícitamente con contrato fijado; "
            f"se conserva {branch} y "
            + (
                ", ".join(
                    f"PR #{pull['number']}"
                    for pull in open_pulls
                    if isinstance(pull.get("number"), int)
                )
                or "sin PR abierto"
            )
            + "."
        ),
        fingerprint,
        parse_task_marker(str(issue.get("body") or "")),
    )
    winner = active_reservation(api, issue_number)
    if (
        not winner
        or winner["reservation_id"] != reservation_id
        or winner.get("acceptance_sha256") != fingerprint
    ):
        return None

    api.set_status(
        issue_number,
        STATUS_REVIEW if open_pulls else STATUS_RESERVED,
    )
    api.try_assign(issue_number, actor)
    for pull in open_pulls:
        number = pull.get("number")
        if not isinstance(number, int):
            continue
        body = str(api.pull(number).get("body") or "")
        api.update_pull_body(
            number,
            rewrite_pull_reservation(body, reservation_id),
        )

    print(
        f"Rama huérfana adoptada: Issue #{issue_number} "
        f"-> {branch} (@{actor}, {reservation_id})"
    )
    return reservation_id


def release_permission(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
    reservation_id: str | None,
    force: bool,
) -> tuple[dict[str, Any] | None, bool]:
    """Valida si el actor y la sesión pueden liberar una reserva."""
    if not authorized(association):
        raise CoordinationError(
            f"@{actor} no tiene una asociación autorizada para liberar trabajo."
        )

    current = active_reservation(api, issue_number)
    if force:
        repo_owner = api.repo.split("/", 1)[0]
        if actor != repo_owner:
            raise CoordinationError(
                f"Solo @{repo_owner} puede ejecutar /liberar-forzado."
            )
        return current, True

    if not current:
        return None, False

    same_session = (
        current["owner"] == actor
        and reservation_id is not None
        and current["reservation_id"] == reservation_id.lower()
    )
    if not same_session:
        return current, False
    return current, True


def close_pulls_before_release(
    api: GitHub,
    branch: str,
    force: bool,
) -> bool:
    """Cierra PR al forzar o rechaza la liberación normal si siguen abiertos."""
    open_pulls = open_pulls_for_branch(api, branch)
    if open_pulls and not force:
        return False
    for pr_number in open_pulls:
        api.close_pull(pr_number)
    return True


def expose_issue_after_release(api: GitHub, issue_number: int) -> None:
    """Vuelve a exponer el Issue solo si sigue abierto y no está bloqueado."""
    issue = api.issue(issue_number)
    if (
        issue.get("state") == "open"
        and STATUS_BLOCKED not in label_names(issue)
    ):
        api.set_status(issue_number, STATUS_AVAILABLE)


def release_work(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
    reservation_id: str | None,
    force: bool,
) -> None:
    """Libera una reserva respetando propiedad de sesión y orden fail-closed."""
    current, allowed = release_permission(
        api,
        issue_number,
        actor,
        association,
        reservation_id,
        force,
    )
    if not allowed:
        return

    branch = (
        str(current["branch"])
        if current
        else branch_for_issue(issue_number)
    )
    if not close_pulls_before_release(
        api,
        branch,
        force,
    ):
        return

    owner = str(current["owner"]) if current else actor
    session = (
        str(current["reservation_id"])
        if current
        else new_reservation_id()
    )
    api.delete_branch(branch)
    api.comment(
        issue_number,
        reservation_marker(
            owner,
            session,
            branch,
            False,
            "liberacion-forzada" if force else "liberar",
        ),
    )
    expose_issue_after_release(api, issue_number)
    if current:
        api.try_unassign(issue_number, owner)
    print(f"Reserva liberada: Issue #{issue_number}")


def sync_review_status(
    api: GitHub,
    issue_number: int,
    pull: dict[str, Any],
    action: str,
    current: dict[str, Any] | None,
) -> bool:
    """Sincroniza estados de revisión y devuelve si el evento ya fue manejado."""
    review_actions = {"opened", "ready_for_review", "converted_to_draft"}
    if action not in review_actions:
        return False

    issue = api.issue(issue_number)
    if not current or issue.get("state") != "open":
        return True
    if action == "opened" and pull.get("draft"):
        return True

    target = (
        STATUS_RESERVED
        if action == "converted_to_draft"
        else STATUS_REVIEW
    )
    api.set_status(issue_number, target)
    return True


def close_pr_reservation(
    api: GitHub,
    issue_number: int,
    branch: str,
    pull: dict[str, Any],
    current: dict[str, Any] | None,
) -> None:
    """Cierra la reserva y actualiza el Issue al cerrarse un PR."""
    api.delete_branch(branch)
    merged = bool(pull.get("merged"))

    if current:
        api.comment(
            issue_number,
            reservation_marker(
                str(current["owner"]),
                str(current["reservation_id"]),
                branch,
                False,
                "pr-merged" if merged else "pr-cerrado-sin-merge",
            ),
        )
        api.try_unassign(issue_number, str(current["owner"]))

    issue = api.issue(issue_number)
    if merged or issue.get("state") != "open":
        api.set_status(issue_number, STATUS_COMPLETED)
    elif STATUS_BLOCKED not in label_names(issue):
        api.set_status(issue_number, STATUS_AVAILABLE)


def update_pr_state(api: GitHub, pr_number: int, action: str) -> None:
    """Sincroniza labels y reserva con eventos de un PR del mismo repositorio."""
    pull = api.pull(pr_number)
    head = pull.get("head")
    branch = str(head.get("ref") or "") if isinstance(head, dict) else ""
    issue_number = issue_from_branch(branch)
    if issue_number is None:
        return

    current = active_reservation(api, issue_number)
    if sync_review_status(api, issue_number, pull, action, current):
        return
    if action != "closed":
        return
    close_pr_reservation(
        api,
        issue_number,
        branch,
        pull,
        current,
    )

def update_issue_label_state(
    api: GitHub,
    issue_number: int,
    actor: str,
    label: str,
) -> None:
    """Reconcilia un label reservado sin convertirlo en autoridad."""
    if actor == TRUSTED_MARKER_LOGIN or label != STATUS_RESERVED:
        return

    issue = api.issue(issue_number)
    if issue.get("state") != "open":
        status = (
            STATUS_CANCELLED
            if issue.get("state_reason") == "not_planned"
            else STATUS_COMPLETED
        )
        api.set_status(issue_number, status)
        return

    labels = label_names(issue)
    if STATUS_RECOVERY in labels:
        api.set_status(issue_number, STATUS_RECOVERY)
        return
    if STATUS_BLOCKED in labels:
        api.set_status(issue_number, STATUS_BLOCKED)
        return

    branch = branch_for_issue(issue_number)
    current = active_reservation(api, issue_number)
    branch_sha = api.branch_sha(branch)

    if (
        current is not None
        and current.get("branch") == branch
        and branch_sha is not None
    ):
        ready_pull = any(
            pull.get("state", "open") == "open"
            and not pull.get("draft", False)
            and isinstance(pull.get("head"), dict)
            and isinstance(pull["head"].get("repo"), dict)
            and pull["head"]["repo"].get("full_name") == api.repo
            for pull in open_pull_records_for_branch(api, branch)
        )
        api.set_status(
            issue_number,
            STATUS_REVIEW if ready_pull else STATUS_RESERVED,
        )
        return

    api.set_status(issue_number, STATUS_AVAILABLE)

def invalidate_contract_drift_checks(
    api: GitHub,
    issue_number: int,
) -> int:
    """Invalida checks verdes previos si el contrato vivo se aparta de la reserva."""
    issue = api.issue(issue_number)
    reservation = active_reservation(api, issue_number)
    if reservation is None:
        return 0

    pinned = reservation.get("acceptance_sha256")
    reason: str | None = None
    if not isinstance(pinned, str):
        reason = "La reserva activa es legacy y no contiene acceptance_sha256."
    else:
        try:
            current = contract_fingerprint(str(issue.get("body") or ""))
        except AcceptanceError as exc:
            reason = f"El contrato de aceptación es inválido: {exc}"
        else:
            if current != pinned:
                reason = (
                    "El contrato de aceptación cambió después de /tomar; "
                    "la evidencia previa del HEAD quedó stale."
                )

    task_pin = reservation.get("task_marker_sha256")
    if reason is None and isinstance(task_pin, str):
        try:
            current_task_pin = task_marker_fingerprint(
                parse_task_marker(str(issue.get("body") or ""))
            )
        except PlanError as exc:
            reason = f"El contrato factory-plan-task es inválido: {exc}"
        else:
            if current_task_pin != task_pin:
                reason = (
                    "Los claims/dependencias factory-plan-task cambiaron después "
                    "de /tomar; la reserva requiere renovación explícita."
                )

    if reason is None:
        return 0

    branch = str(reservation["branch"])
    invalidated = 0
    for pull in open_pull_records_for_branch(api, branch):
        number = pull.get("number")
        head = pull.get("head")
        sha = head.get("sha") if isinstance(head, dict) else None
        if not isinstance(sha, str) or not sha:
            if isinstance(number, int):
                current_pull = api.pull(number)
                current_head = current_pull.get("head")
                sha = (
                    current_head.get("sha")
                    if isinstance(current_head, dict)
                    else None
                )
        if not isinstance(sha, str) or not sha:
            continue

        summary = (
            f"Issue #{issue_number}: {reason} "
            "Actualiza la reserva/contrato y vuelve a ejecutar CI."
        )
        for check_name in ("Criterios de aceptación", "Validar"):
            api.create_failed_check(
                check_name,
                sha,
                "Contrato de aceptación desactualizado",
                summary,
            )
        invalidated += 1
    return invalidated


def update_issue_state(api: GitHub, issue_number: int, action: str) -> None:
    """Limpia una reserva al cerrar un Issue o restablece su estado al reabrirlo."""
    issue = api.issue(issue_number)
    branch = branch_for_issue(issue_number)
    current = active_reservation(api, issue_number)

    if action == "edited":
        invalidated = invalidate_contract_drift_checks(api, issue_number)
        if invalidated and current and isinstance(
            current.get("task_marker_sha256"), str
        ):
            try:
                current_task_pin = task_marker_fingerprint(
                    parse_task_marker(str(issue.get("body") or ""))
                )
            except PlanError:
                current_task_pin = None
            if current_task_pin != current.get("task_marker_sha256"):
                api.set_status(issue_number, STATUS_RECOVERY)
        return
    if action == "reopened":
        if current and api.branch_sha(branch):
            api.set_status(issue_number, STATUS_RESERVED)
        elif STATUS_BLOCKED not in label_names(issue):
            api.set_status(issue_number, STATUS_AVAILABLE)
        return
    if action != "closed":
        return

    state_reason = issue.get("state_reason")
    status = STATUS_CANCELLED if state_reason == "not_planned" else STATUS_COMPLETED
    if (
        current is None
        and api.branch_sha(branch) is None
        and status in label_names(issue)
    ):
        return

    for pr_number in open_pulls_for_branch(api, branch):
        api.close_pull(pr_number)
    api.delete_branch(branch)

    if current:
        api.comment(
            issue_number,
            reservation_marker(
                str(current["owner"]),
                str(current["reservation_id"]),
                branch,
                False,
                "issue-cerrado",
            ),
        )
        api.try_unassign(issue_number, str(current["owner"]))

    api.set_status(issue_number, status)



def reservation_validation_errors(
    api: GitHub,
    issue: dict[str, Any],
    issue_number: int,
    branch: str,
    body: str,
) -> list[str]:
    """Valida la reserva activa requerida por un Pull Request."""
    errors: list[str] = []
    labels = label_names(issue)
    if not ({STATUS_RESERVED, STATUS_REVIEW} & labels):
        errors.append(
            f"Issue #{issue_number} no tiene una reserva activa visible."
        )
    if api.branch_sha(branch) is None:
        errors.append(f"La rama reservada {branch} no existe.")

    reservation = active_reservation(api, issue_number)
    if not reservation:
        errors.append(
            f"Issue #{issue_number} no tiene marcador de reserva activo y confiable."
        )
        return errors

    if reservation["branch"] != branch:
        errors.append(
            f"El marcador de reserva apunta a {reservation['branch']}, no a {branch}."
        )
    if reservation_from_pr_body(body) != reservation["reservation_id"]:
        errors.append(
            "El PR debe declarar la sesión activa mediante metadata de reserva oculta."
        )

    pinned = reservation.get("acceptance_sha256")
    if not isinstance(pinned, str):
        errors.append(
            f"Issue #{issue_number} usa una reserva legacy sin fingerprint; "
            "ejecuta /migrar-contrato <UUID> o libera y vuelve a /tomar."
        )
        return errors

    try:
        current = contract_fingerprint(str(issue.get("body") or ""))
    except AcceptanceError:
        errors.append(
            f"Issue #{issue_number} tiene un contrato de aceptación inválido."
        )
    else:
        if current != pinned:
            errors.append(
                f"Issue #{issue_number} cambió su contrato de aceptación "
                "después de /tomar; libera y vuelve a reservar."
            )

    task_pin = reservation.get("task_marker_sha256")
    if isinstance(task_pin, str):
        try:
            current_task_pin = task_marker_fingerprint(
                parse_task_marker(str(issue.get("body") or ""))
            )
        except PlanError:
            errors.append(
                f"Issue #{issue_number} tiene factory-plan-task inválido."
            )
        else:
            if current_task_pin != task_pin:
                errors.append(
                    f"Issue #{issue_number} cambió claims/dependencias "
                    "después de /tomar; ejecuta /renovar-contrato <UUID>."
                )
    return errors


def issue_contract_errors(
    api: GitHub,
    issue_number: int,
    branch: str,
    body: str,
    require_reservation: bool,
) -> list[str]:
    """Valida relación con Issue y, cuando aplica, su reserva activa."""
    errors: list[str] = []
    if issue_number not in closing_issues(body):
        errors.append(
            f"El PR debe incluir Closes #{issue_number} (o Fixes/Resolves) en el cuerpo."
        )

    issue = api.issue(issue_number)
    if issue.get("state") != "open":
        errors.append(f"Issue #{issue_number} debe estar abierto durante el PR.")
    if require_reservation:
        errors.extend(
            reservation_validation_errors(
                api,
                issue,
                issue_number,
                branch,
                body,
            )
        )
    return errors


def collision_validation_errors(
    api: GitHub,
    pr_number: int,
) -> list[str]:
    """Detecta archivos solapados contra otros PR abiertos hacia main."""
    current_files = api.pull_files(pr_number)
    others: dict[int, set[str]] = {}
    for other in api.open_pulls():
        other_number = other.get("number")
        if not isinstance(other_number, int) or other_number == pr_number:
            continue
        other_base = other.get("base")
        if isinstance(other_base, dict) and other_base.get("ref") != "main":
            continue
        others[other_number] = api.pull_files(other_number)

    errors: list[str] = []
    for other_pr, files in file_overlaps(current_files, others).items():
        rendered = ", ".join(files)
        errors.append(
            f"Colisión con PR #{other_pr}: ambos modifican {rendered}."
        )
    return errors


def validate_pull(
    api: GitHub,
    pr_number: int,
    require_reservation: bool,
) -> None:
    """Valida destino, reserva, relación con Issue y colisiones de un PR."""
    pull = api.pull(pr_number)
    base = pull.get("base")
    head = pull.get("head")
    branch = str(head.get("ref") or "") if isinstance(head, dict) else ""
    issue_number = issue_from_branch(branch)
    errors: list[str] = []

    if not isinstance(base, dict) or base.get("ref") != "main":
        errors.append("La rama base del PR debe ser main.")

    if issue_number is None:
        errors.append("La rama del PR debe usar el formato canónico trabajo/issue-N.")
    else:
        body = str(pull.get("body") or "")
        errors.extend(
            issue_contract_errors(
                api,
                issue_number,
                branch,
                body,
                require_reservation,
            )
        )

    errors.extend(collision_validation_errors(api, pr_number))
    if errors:
        raise CoordinationError("\n".join(f"- {error}" for error in errors))

    mode = "reserva obligatoria" if require_reservation else "bootstrap"
    print(
        f"Coordinación válida para PR #{pr_number} "
        f"({mode}); sin solapamientos con otros PR abiertos."
    )

def parse_comment_command(body: str) -> tuple[str, str | None]:
    """Interpreta únicamente los comandos públicos del perfil activo."""
    value = body.strip()
    if value == PROFILE.take:
        return "tomar", None
    if value == PROFILE.force_release:
        return "liberar-forzado", None
    if PROFILE.name == "es" and value == "/adoptar-contrato-huerfana":
        return "adoptar-contrato-huerfana", None
    pairs = [(PROFILE.release, "liberar"), (PROFILE.transfer, "transferir")]
    if PROFILE.recover:
        pairs.append((PROFILE.recover, "recuperar"))
    if PROFILE.name == "es":
        pairs += [("/migrar-contrato ", "migrar-contrato"), ("/renovar-contrato ", "renovar-contrato")]
    for prefix, command in pairs:
        if value.startswith(prefix):
            session = value[len(prefix):].strip().lower()
            if not SESSION_RE.fullmatch(session):
                raise CoordinationError(f"El comando {command} requiere un UUID de reserva válido.")
            return command, session
    raise CoordinationError("Comando de coordinación no reconocido.")

def recover_work(api: GitHub, issue_number: int, actor: str, association: str, reservation_id: str) -> str | None:
    """Recupera explícitamente una reserva EN stale con UUID coincidente."""
    if not authorized(association):
        raise CoordinationError(f"@{actor} no tiene una asociación autorizada para recuperar trabajo.")
    current = active_reservation(api, issue_number)
    if current is None or current["reservation_id"] != reservation_id.lower():
        return None
    branch = str(current["branch"])
    if not work_is_stale(api, issue_number, branch):
        return None
    return recover_existing_work_if_stale(api, issue_number, actor, branch, current)
def process_comment(
    api: GitHub,
    issue_number: int,
    actor: str,
    association: str,
    body: str,
) -> None:
    """Ejecuta un comando de comentario ya filtrado por GitHub Actions."""
    command, reservation_id = parse_comment_command(body)
    if command == "tomar":
        reserve_work(api, issue_number, actor, association)
    elif command == "liberar":
        release_work(
            api,
            issue_number,
            actor,
            association,
            reservation_id,
            False,
        )
    elif command == "liberar-forzado":
        release_work(api, issue_number, actor, association, None, True)
    elif command == "recuperar":
        assert reservation_id is not None
        recover_work(api, issue_number, actor, association, reservation_id)
    elif command == "transferir":
        assert reservation_id is not None
        transfer_work(
            api,
            issue_number,
            actor,
            association,
            reservation_id,
        )
    elif command == "migrar-contrato":
        assert reservation_id is not None
        migrate_legacy_reservation(
            api,
            issue_number,
            actor,
            association,
            reservation_id,
        )
    elif command == "renovar-contrato":
        assert reservation_id is not None
        renew_pinned_acceptance(
            api, issue_number, actor, association, reservation_id
        )
    elif command == "adoptar-contrato-huerfana":
        adopt_orphaned_contract(
            api,
            issue_number,
            actor,
            association,
        )


def build_parser() -> argparse.ArgumentParser:
    """Construye la interfaz de línea de comandos del coordinador."""
    parser = argparse.ArgumentParser(description="Coordinación multiagente de la fábrica")
    sub = parser.add_subparsers(dest="command", required=True)

    comment = sub.add_parser("comentario")
    comment.add_argument("--repo", required=True)
    comment.add_argument("--issue", required=True, type=int)
    comment.add_argument("--actor", required=True)
    comment.add_argument("--association", required=True)
    comment.add_argument("--body", required=True)

    pr_event = sub.add_parser("pr-event")
    pr_event.add_argument("--repo", required=True)
    pr_event.add_argument("--pr", required=True, type=int)
    pr_event.add_argument("--action", required=True)

    issue_event = sub.add_parser("issue-event")
    issue_event.add_argument("--repo", required=True)
    issue_event.add_argument("--issue", required=True, type=int)
    issue_event.add_argument("--action", required=True)

    label_event = sub.add_parser("label-event")
    label_event.add_argument("--repo", required=True)
    label_event.add_argument("--issue", required=True, type=int)
    label_event.add_argument("--actor", required=True)
    label_event.add_argument("--label", required=True)

    validate = sub.add_parser("validar-pr")
    validate.add_argument("--repo", required=True)
    validate.add_argument("--pr", required=True, type=int)
    validate.add_argument("--require-reservation", action="store_true")

    sweep = sub.add_parser("marcar-inactivas")
    sweep.add_argument("--repo", required=True)

    return parser


def main() -> int:
    """Despacha el comando solicitado y devuelve un exit code apto para CI."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        configure_profile(os.getenv("FACTORY_COORDINATION_PROFILE", "es"))
        api = GitHub(args.repo)
        if args.command == "comentario":
            process_comment(
                api,
                args.issue,
                args.actor,
                args.association,
                args.body,
            )
        elif args.command == "pr-event":
            update_pr_state(api, args.pr, args.action)
        elif args.command == "issue-event":
            update_issue_state(api, args.issue, args.action)
        elif args.command == "label-event":
            update_issue_label_state(api, args.issue, args.actor, args.label)
        elif args.command == "validar-pr":
            validate_pull(api, args.pr, args.require_reservation)
        elif args.command == "marcar-inactivas":
            mark_stale_reservations(api)
        else:
            parser.error("Comando no soportado.")
    except (CoordinationError, GitHubError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
