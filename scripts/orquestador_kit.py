#!/usr/bin/env python3
"""Contrato puro del orquestador central de Factory."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any

PLAN_MARKER = "factory-plan"
TASK_MARKER = "factory-plan-task"
MAX_BODY = 200_000
MAX_TASKS = 50
MAX_PATHS = 50
ACTIVE_STATUSES = {
    "estado: reservado",
    "estado: en revisión",
    "estado: requiere recuperación",
    "status: reserved",
    "status: in review",
    "status: recovery required",
}

CONDOR_PRIVACY_DERIVED_CLAIMS = (
    "tests/php/Privacy/PrivacyAsCodeTest.php",
    "docs/privacidad/aviso-privacidad.md",
    "docs/privacidad/canal-derechos.md",
    "docs/privacidad/politica-tratamiento.md",
    "docs/privacidad/registro-tratamientos.md",
    "docs/privacidad/retencion.md",
    "docs/privacidad/terminos-condiciones.md",
)


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class PlannedTask:
    key: str
    title: str
    owner: str
    paths: tuple[str, ...]
    depends_on: tuple[str, ...]


def _extract_marker(body: str, name: str) -> str | None:
    if not isinstance(body, str) or len(body) > MAX_BODY:
        raise PlanError("El cuerpo del Issue es inválido o demasiado grande.")
    prefix = f"<!-- {name} "
    html_prefix = f"<!-- {name}"
    suffix = " -->"
    canonical_starts: list[int] = []
    search_from = 0

    while True:
        start = body.find(html_prefix, search_from)
        if start < 0:
            break
        boundary = start + len(html_prefix)
        if (
            boundary == len(body)
            or body[boundary].isspace()
            or body.startswith("-->", boundary)
        ):
            if body.startswith(prefix, start):
                canonical_starts.append(start)
            else:
                raise PlanError(f"Marker {name} malformado.")
        search_from = boundary

    if not canonical_starts:
        return None
    if len(canonical_starts) != 1:
        raise PlanError(f"Debe existir un único marker {name}.")
    start = canonical_starts[0] + len(prefix)
    end = body.find(suffix, start)
    if end < 0:
        raise PlanError(f"Marker {name} malformado.")
    return body[start:end].strip()


def validate_task_key(value: Any) -> str:
    """Valida la identidad canónica compartida por plan y factory-plan-task."""
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 32
        or not value.isascii()
        or not value[0].isalpha()
        or not value[0].isupper()
        or any(not (char.isupper() or char.isdigit() or char in "_-") for char in value)
    ):
        raise PlanError("task.key debe usar identificador ASCII mayúsculo de hasta 32 caracteres.")
    return value


def _valid_key(value: Any) -> str:
    """Compatibilidad interna: delega en la única autoridad de task.key."""
    return validate_task_key(value)


def _valid_owner(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 39
        or not value.isascii()
        or value.startswith("-")
        or value.endswith("-")
        or "--" in value
        or any(not (char.isalnum() or char == "-") for char in value)
    ):
        raise PlanError("task.owner debe ser un login GitHub válido.")
    return value


def _valid_title(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value.strip()) <= 120
        or "\n" in value
        or "\r" in value
    ):
        raise PlanError("task.title debe ser una línea de 1..120 caracteres.")
    return value.strip()


def _valid_path(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 240
        or value.startswith("/")
        or value.startswith("./")
        or "\\" in value
        or any(char in value for char in ("\n", "\r", "\x00", "*", "?", "[", "]", "{", "}"))
    ):
        raise PlanError("task.paths contiene una ruta no canónica.")
    is_dir = value.endswith("/")
    base = value[:-1] if is_dir else value
    parts = base.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise PlanError("task.paths contiene una ruta no canónica.")
    return value


def _parse_task(raw: Any) -> PlannedTask:
    if not isinstance(raw, dict) or set(raw) != {
        "key", "title", "owner", "paths", "depends_on"
    }:
        raise PlanError(
            "Cada task debe contener exactamente key, title, owner, paths y depends_on."
        )
    paths = raw["paths"]
    deps = raw["depends_on"]
    if (
        not isinstance(paths, list)
        or not 1 <= len(paths) <= MAX_PATHS
        or not isinstance(deps, list)
        or len(deps) > MAX_TASKS
    ):
        raise PlanError("paths/depends_on fuera de límites.")
    valid_paths = tuple(_valid_path(value) for value in paths)
    if len(set(valid_paths)) != len(valid_paths):
        raise PlanError("Una tarea no puede reclamar la misma ruta dos veces.")
    valid_deps = tuple(_valid_key(value) for value in deps)
    if len(set(valid_deps)) != len(valid_deps):
        raise PlanError("depends_on contiene duplicados.")
    key = _valid_key(raw["key"])
    if key in valid_deps:
        raise PlanError("Una tarea no puede depender de sí misma.")
    return PlannedTask(
        key=key,
        title=_valid_title(raw["title"]),
        owner=_valid_owner(raw["owner"]),
        paths=valid_paths,
        depends_on=valid_deps,
    )


def parse_plan(body: str) -> list[PlannedTask]:
    payload = _extract_marker(body, PLAN_MARKER)
    if payload is None:
        raise PlanError("El épico debe declarar un marker factory-plan.")
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PlanError("factory-plan contiene JSON inválido.") from exc
    if not isinstance(raw, dict) or set(raw) != {"version", "tasks"}:
        raise PlanError("factory-plan debe contener version y tasks.")
    if type(raw["version"]) is not int or raw["version"] != 1:
        raise PlanError("factory-plan requiere version=1.")
    tasks_raw = raw["tasks"]
    if not isinstance(tasks_raw, list) or not 1 <= len(tasks_raw) <= MAX_TASKS:
        raise PlanError(f"factory-plan debe contener 1..{MAX_TASKS} tareas.")
    tasks = [_parse_task(item) for item in tasks_raw]
    by_key = {task.key: task for task in tasks}
    if len(by_key) != len(tasks):
        raise PlanError("task.key debe ser único.")
    for task in tasks:
        unknown = set(task.depends_on) - set(by_key)
        if unknown:
            raise PlanError(
                f"{task.key} depende de tareas inexistentes: {', '.join(sorted(unknown))}."
            )
    topological_order(tasks)
    _validate_parallel_claims(tasks)
    return tasks


def topological_order(tasks: list[PlannedTask]) -> list[PlannedTask]:
    by_key = {task.key: task for task in tasks}
    pending = {task.key: set(task.depends_on) for task in tasks}
    result: list[PlannedTask] = []
    while pending:
        ready = sorted(key for key, deps in pending.items() if not deps)
        if not ready:
            raise PlanError("El grafo de dependencias contiene un ciclo.")
        for key in ready:
            result.append(by_key[key])
            del pending[key]
        completed = set(ready)
        for deps in pending.values():
            deps.difference_update(completed)
    return result


def _collision_key(path: str) -> str:
    """Identidad conservadora de un archivo en sistemas multiplataforma."""
    return unicodedata.normalize(
        "NFC", unicodedata.normalize("NFC", path).casefold()
    )


def _claim_parts(path: str) -> tuple[tuple[str, ...], bool]:
    is_dir = path.endswith("/")
    base = path[:-1] if is_dir else path
    return tuple(_collision_key(part) for part in base.split("/")), is_dir


def claims_overlap(left: str, right: str) -> bool:
    left_parts, left_dir = _claim_parts(left)
    right_parts, right_dir = _claim_parts(right)
    if left_parts == right_parts:
        return True
    if left_dir and len(left_parts) < len(right_parts):
        return right_parts[: len(left_parts)] == left_parts
    if right_dir and len(right_parts) < len(left_parts):
        return left_parts[: len(right_parts)] == right_parts
    return False



def verified_changed_file_overlap(
    left_claims: tuple[str, ...],
    right_claims: tuple[str, ...],
    *,
    left_files: list[str] | None,
    right_files: list[str] | None,
    left_head: str,
    right_head: str,
    left_evidence_head: str,
    right_evidence_head: str,
    left_complete: bool,
    right_complete: bool,
    other_issue: int,
    other_lease: str,
) -> dict[str, object]:
    """Análisis puro y puntual; no concede ni amplía una reserva."""
    def result(safe: bool, reason: str, files: list[str] | None = None) -> dict[str, object]:
        return {"safe": safe, "reason": reason, "files": files or [],
                "other_issue": other_issue, "other_lease": other_lease}

    if (
        type(other_issue) is not int or other_issue < 1
        or not isinstance(other_lease, str) or not other_lease
        or not isinstance(left_claims, (tuple, list))
        or not isinstance(right_claims, (tuple, list))
        or not left_claims or not right_claims
    ):
        return result(False, "identity_or_claims_invalid")
    try:
        left = tuple(_valid_path(path) for path in left_claims)
        right = tuple(_valid_path(path) for path in right_claims)
    except (PlanError, TypeError):
        return result(False, "claims_invalid")

    if not any(claims_overlap(a, b) for a in left for b in right):
        return result(True, "declared_claims_disjoint")

    heads = (left_head, right_head, left_evidence_head, right_evidence_head)
    if any(not isinstance(s, str) or len(s) not in (40, 64) or
           any(c not in "0123456789abcdef" for c in s) for s in heads):
        return result(False, "sha_missing_or_invalid")
    if (left_head != left_evidence_head or right_head != right_evidence_head
            or left_complete is not True or right_complete is not True):
        return result(False, "diff_stale_or_incomplete")

    if (not isinstance(left_files, list) or not isinstance(right_files, list)
            or not left_files or not right_files
            or len(left_files) > 500 or len(right_files) > 500):
        return result(False, "changed_files_missing_or_excessive")
    try:
        lf = tuple(_valid_path(path) for path in left_files)
        rf = tuple(_valid_path(path) for path in right_files)
    except (PlanError, TypeError):
        return result(False, "changed_files_invalid")
    if (any(path.endswith("/") for path in (*lf, *rf))
            or len({_collision_key(p) for p in lf}) != len(lf)
            or len({_collision_key(p) for p in rf}) != len(rf)):
        return result(False, "changed_files_noncanonical")
    if (any(not any(claims_overlap(path, c) for c in left) for path in lf)
            or any(not any(claims_overlap(path, c) for c in right) for path in rf)):
        return result(False, "changed_file_outside_claim")

    left_keys = {_collision_key(p) for p in lf}
    right_keys = {_collision_key(p) for p in rf}
    collisions = sorted(
        {p for p in lf if _collision_key(p) in right_keys}
        | {p for p in rf if _collision_key(p) in left_keys}
    )
    if collisions:
        return result(False, "shared_changed_files", collisions)
    return result(True, "verified_disjoint_changed_files")



def verified_new_file_claim_against_active_diff(
    candidate_paths: list[str] | tuple[str, ...],
    active_paths: list[str] | tuple[str, ...],
    *,
    active_files: list[str] | None,
    active_head: str,
    evidence_head: str,
    diff_complete: bool,
    active_issue: int,
    active_lease: str,
) -> dict[str, object]:
    """Prueba conservadora de archivos exactos frente a una lease V3.

    Solo una propuesta con claims por ARCHIVO puede usarse antes de que exista
    su rama: no infiere futuros archivos modificados por un claim de directorio.
    """
    def outcome(safe: bool, reason: str, collisions: list[str] | None = None):
        return {
            "safe": safe, "reason": reason, "files": collisions or [],
            "active_issue": active_issue, "active_lease": active_lease,
            "active_head": active_head,
        }

    if (
        type(active_issue) is not int or active_issue < 1
        or not isinstance(active_lease, str) or not active_lease
        or not isinstance(candidate_paths, (tuple, list)) or not candidate_paths
        or not isinstance(active_paths, (tuple, list)) or not active_paths
    ):
        return outcome(False, "identity_or_claims_missing")
    try:
        candidate = tuple(_valid_path(p) for p in candidate_paths)
        active = tuple(_valid_path(p) for p in active_paths)
    except (PlanError, TypeError):
        return outcome(False, "claims_invalid")
    if (
        any(p.endswith("/") for p in candidate)
        or len({_collision_key(p) for p in candidate}) != len(candidate)
    ):
        return outcome(False, "candidate_requires_exact_unique_files")
    if (
        not isinstance(active_head, str) or len(active_head) not in (40, 64)
        or any(c not in "0123456789abcdef" for c in active_head)
        or evidence_head != active_head or diff_complete is not True
    ):
        return outcome(False, "diff_sha_stale_or_incomplete")
    if (
        not isinstance(active_files, list) or not active_files
        or len(active_files) > 3000
    ):
        return outcome(False, "diff_missing_or_unbounded")
    try:
        changed = tuple(_valid_path(p) for p in active_files)
    except (PlanError, TypeError):
        return outcome(False, "diff_files_invalid")
    if (
        any(p.endswith("/") for p in changed)
        or len({_collision_key(p) for p in changed}) != len(changed)
        or any(not any(claims_overlap(p, c) for c in active) for p in changed)
    ):
        return outcome(False, "changed_files_outside_active_claims")
    candidate_keys = {_collision_key(p) for p in candidate}
    changed_keys = {_collision_key(p) for p in changed}
    collisions = sorted(
        {p for p in candidate if _collision_key(p) in changed_keys}
        | {p for p in changed if _collision_key(p) in candidate_keys}
    )
    if collisions:
        return outcome(False, "file_already_modified_by_active_branch", collisions)
    return outcome(True, "candidate_files_disjoint_from_verified_active_diff")



def expand_derived_claims(
    repository_ref: str,
    tasks: list[PlannedTask],
) -> list[PlannedTask]:
    """Expande claims deterministas allowlisted antes de materializar el plan."""
    if not isinstance(repository_ref, str) or not repository_ref.strip():
        raise PlanError("repository_ref inválido para derivar claims.")

    is_condor = repository_ref.strip().lower() == "pl0n3r/condor"
    expanded: list[PlannedTask] = []
    for task in tasks:
        paths = [_valid_path(path) for path in task.paths]
        if is_condor and "datos.yml" in paths:
            for derived in CONDOR_PRIVACY_DERIVED_CLAIMS:
                if not any(claims_overlap(existing, derived) for existing in paths):
                    paths.append(derived)

        if len(paths) > MAX_PATHS:
            raise PlanError(
                f"{task.key} excede MAX_PATHS tras expandir claims derivados."
            )
        expanded.append(
            PlannedTask(
                key=task.key,
                title=task.title,
                owner=task.owner,
                paths=tuple(paths),
                depends_on=task.depends_on,
            )
        )

    _validate_parallel_claims(expanded)
    return expanded


def tasks_overlap(left: PlannedTask, right: PlannedTask) -> list[str]:
    overlaps: set[str] = set()
    for left_path in left.paths:
        for right_path in right.paths:
            if claims_overlap(left_path, right_path):
                overlaps.add(f"{left_path} ↔ {right_path}")
    return sorted(overlaps)


def _depends_transitively(
    key: str,
    ancestor: str,
    by_key: dict[str, PlannedTask],
) -> bool:
    stack = list(by_key[key].depends_on)
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == ancestor:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(by_key[current].depends_on)
    return False


def _validate_parallel_claims(tasks: list[PlannedTask]) -> None:
    by_key = {task.key: task for task in tasks}
    for index, left in enumerate(tasks):
        for right in tasks[index + 1:]:
            overlap = tasks_overlap(left, right)
            if not overlap:
                continue
            ordered = (
                _depends_transitively(left.key, right.key, by_key)
                or _depends_transitively(right.key, left.key, by_key)
            )
            if not ordered:
                raise PlanError(
                    f"{left.key} y {right.key} reclaman rutas solapadas sin dependencia: "
                    + ", ".join(overlap)
                )


def build_task_marker(
    *,
    epic: int,
    task: PlannedTask,
    order: int,
    roles: list[str],
    dependency_issues: list[int],
) -> str:
    payload = {
        "version": 1,
        "epic": epic,
        "task_key": task.key,
        "order": order,
        "owner": task.owner,
        "roles": sorted(roles),
        "depends_on": dependency_issues,
        "paths": list(task.paths),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return f"<!-- {TASK_MARKER} {encoded} -->"


def parse_task_marker(body: str) -> dict[str, Any] | None:
    payload = _extract_marker(body, TASK_MARKER)
    if payload is None:
        return None
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PlanError("factory-plan-task contiene JSON inválido.") from exc
    required = {
        "version", "epic", "task_key", "order", "owner",
        "roles", "depends_on", "paths",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise PlanError("factory-plan-task tiene esquema inválido.")
    if type(raw["version"]) is not int or raw["version"] != 1:
        raise PlanError("factory-plan-task tiene esquema inválido.")
    _valid_key(raw["task_key"])
    _valid_owner(raw["owner"])
    if (
        isinstance(raw["epic"], bool)
        or not isinstance(raw["epic"], int)
        or raw["epic"] < 1
        or isinstance(raw["order"], bool)
        or not isinstance(raw["order"], int)
        or raw["order"] < 1
    ):
        raise PlanError("factory-plan-task contiene epic/order inválidos.")
    if (
        not isinstance(raw["roles"], list)
        or not raw["roles"]
        or not all(isinstance(role, str) and role for role in raw["roles"])
        or not isinstance(raw["depends_on"], list)
        or not all(
            isinstance(number, int) and not isinstance(number, bool) and number > 0
            for number in raw["depends_on"]
        )
        or not isinstance(raw["paths"], list)
        or not raw["paths"]
    ):
        raise PlanError("factory-plan-task contiene listas inválidas.")
    raw["paths"] = [_valid_path(path) for path in raw["paths"]]
    return raw


def task_marker_fingerprint(marker: dict[str, Any] | None) -> str | None:
    """Fija la identidad semántica de un factory-plan-task canónico."""
    if marker is None:
        return None
    canonical = json.dumps(
        marker,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def issue_label_names(issue: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for label in issue.get("labels", []):
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
        elif isinstance(label, str):
            names.add(label)
    return names


def _active_other_issues(
    current_issue: dict[str, Any],
    open_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Devuelve las otras líneas activas que compiten por el mismo repositorio."""
    current_number = current_issue.get("number")
    return [
        issue
        for issue in open_issues
        if issue.get("number") != current_number
        and bool(issue_label_names(issue) & ACTIVE_STATUSES)
    ]


def parallel_compatibility_evidence(
    current_issue: dict[str, Any],
    open_issues: list[dict[str, Any]],
    active_task_snapshots: dict[int, dict[str, Any]] | None = None,
) -> list[str]:
    """Explica qué líneas activas son compatibles por claims fijados."""
    marker = parse_task_marker(str(current_issue.get("body") or ""))
    if marker is None:
        return []

    evidence: list[str] = []
    for other in _active_other_issues(current_issue, open_issues):
        other_number = other.get("number")
        if not isinstance(other_number, int):
            continue
        other_marker = (
            active_task_snapshots.get(other_number)
            if active_task_snapshots is not None
            else parse_task_marker(str(other.get("body") or ""))
        )
        if other_marker is None:
            continue
        overlap = {
            (left, right)
            for left in marker["paths"]
            for right in other_marker["paths"]
            if claims_overlap(left, right)
        }
        if overlap:
            continue
        current_paths = ", ".join(marker["paths"])
        other_paths = ", ".join(other_marker["paths"])
        evidence.append(
            f"#{other_number}: claims disjuntos "
            f"(candidato=[{current_paths}]; activo=[{other_paths}])"
        )
    return evidence


def reservation_blockers(
    current_issue: dict[str, Any],
    open_issues: list[dict[str, Any]],
    actor: str,
    dependency_states: dict[int, dict[str, Any]] | None = None,
    active_task_snapshots: dict[int, dict[str, Any]] | None = None,
    active_dependency_states: dict[int, dict[int, dict[str, Any]]] | None = None,
    active_reservation_numbers: set[int] | None = None,
    verified_file_independence: set[int] | None = None,
) -> list[str]:
    marker = parse_task_marker(str(current_issue.get("body") or ""))
    active_others = _active_other_issues(current_issue, open_issues)

    if marker is None:
        return [
            (
                f"trabajo no planificado no puede compartir repositorio "
                f"con tarea activa #{other.get('number')}"
            )
            for other in active_others
        ]

    blockers: list[str] = []
    if marker["owner"] != actor:
        blockers.append(
            f"tarea planificada para @{marker['owner']}, no para @{actor}"
        )
    if dependency_states is None:
        open_numbers = {
            issue.get("number")
            for issue in open_issues
            if isinstance(issue.get("number"), int)
        }
        pending = sorted(
            number for number in marker["depends_on"] if number in open_numbers
        )
    else:
        pending = sorted(
            number
            for number in marker["depends_on"]
            if (
                number not in dependency_states
                or dependency_states[number].get("state") != "closed"
                or dependency_states[number].get("state_reason") != "completed"
            )
        )
    if pending:
        blockers.append(
            "dependencias no completadas: "
            + ", ".join(f"#{number}" for number in pending)
        )

    current_paths = marker["paths"]
    for other in active_others:
        other_number = other.get("number")
        if not isinstance(other_number, int):
            continue
        if (
            active_task_snapshots is not None
            and active_reservation_numbers is not None
            and other_number not in active_reservation_numbers
        ):
            # Un label activo sin una reserva confiable no constituye autoridad
            # para bloquear claims de trabajo nuevo. La reconciliación del Issue
            # puede ocurrir después sin convertir estado parcial en una reserva.
            continue

        other_marker = (
            active_task_snapshots.get(other_number)
            if active_task_snapshots is not None
            else parse_task_marker(str(other.get("body") or ""))
        )
        if other_marker is None:
            detail = (
                "tiene reserva activa sin claims fijados"
                if active_task_snapshots is not None
                else "no está planificada"
            )
            blockers.append(
                f"tarea activa #{other_number} {detail}; "
                "no se puede demostrar independencia"
            )
            continue

        if active_dependency_states is not None:
            states = active_dependency_states.get(other_number, {})
            pending_active = sorted(
                number
                for number in other_marker["depends_on"]
                if (
                    number not in states
                    or states[number].get("state") != "closed"
                    or states[number].get("state_reason") != "completed"
                )
            )
            if pending_active:
                blockers.append(
                    f"tarea activa #{other_number} tiene dependencias no completadas: "
                    + ", ".join(f"#{number}" for number in pending_active)
                )

        overlap = sorted({
            f"{left} ↔ {right}"
            for left in current_paths
            for right in other_marker["paths"]
            if claims_overlap(left, right)
        })
        if overlap and other_number not in (verified_file_independence or set()):
            blockers.append(
                f"colisión con tarea activa #{other_number}: " + ", ".join(overlap)
            )
    return blockers


def render_graph(
    epic: int,
    tasks: list[PlannedTask],
    issue_numbers: dict[str, int],
    roles: dict[str, list[str]],
) -> str:
    order = topological_order(tasks)
    lines = [
        f"<!-- factory-plan-report:{epic} -->",
        f"## Grafo de ejecución · épico #{epic}",
        "",
        "```mermaid",
        "graph TD",
    ]
    for position, task in enumerate(order, 1):
        number = issue_numbers[task.key]
        role_text = ", ".join(roles[task.key])
        lines.append(
            f"  {task.key}: {position}. #{number} · @{task.owner} · {role_text}"
        )
    for task in order:
        for dependency in task.depends_on:
            lines.append(f"  {dependency} --> {task.key}")
    lines.extend([
        "```",
        "",
        "| Orden | Issue | Owner | Roles | Paths |",
        "| ---: | --- | --- | --- | --- |",
    ])
    for position, task in enumerate(order, 1):
        lines.append(
            f"| {position} | #{issue_numbers[task.key]} · {task.key} | "
            f"@{task.owner} | {', '.join(roles[task.key])} | "
            f"{'<br>'.join(task.paths)} |"
        )
    return "\n".join(lines) + "\n"
