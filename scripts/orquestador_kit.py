#!/usr/bin/env python3
"""Contrato puro del orquestador central de Factory."""
from __future__ import annotations

import hashlib
import json
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
    suffix = " -->"
    count = body.count(prefix)
    if count == 0:
        if name in body:
            raise PlanError(f"Marker {name} malformado.")
        return None
    if count != 1:
        raise PlanError(f"Debe existir un único marker {name}.")
    start = body.index(prefix) + len(prefix)
    end = body.find(suffix, start)
    if end < 0:
        raise PlanError(f"Marker {name} malformado.")
    return body[start:end].strip()


def _valid_key(value: Any) -> str:
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
    if raw["version"] != 1:
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


def _claim_parts(path: str) -> tuple[tuple[str, ...], bool]:
    is_dir = path.endswith("/")
    base = path[:-1] if is_dir else path
    return tuple(base.split("/")), is_dir


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
    if not isinstance(raw, dict) or set(raw) != required or raw["version"] != 1:
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
        other_marker = (
            active_task_snapshots.get(other_number)
            if active_task_snapshots is not None
            else parse_task_marker(str(other.get("body") or ""))
        )
        if other_marker is None:
            detail = (
                "no tiene claims fijados"
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
        if overlap:
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
