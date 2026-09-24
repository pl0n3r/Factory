#!/usr/bin/env python3
"""Materializa de forma idempotente un factory-plan en Issues hijos."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

if __package__:
    from scripts.coordinar_trabajo import (
        GitHub,
        GitHubError,
        STATUS_AVAILABLE,
        STATUS_RECOVERY,
        STATUS_RESERVED,
        STATUS_REVIEW,
        label_names,
    )
    from scripts.orquestador_kit import (
        PlanError,
        PlannedTask,
        build_task_marker,
        parse_plan,
        parse_task_marker,
        render_graph,
        topological_order,
    )
    from scripts.roles_kit import classify
else:
    from coordinar_trabajo import (
        GitHub,
        GitHubError,
        STATUS_AVAILABLE,
        STATUS_RECOVERY,
        STATUS_RESERVED,
        STATUS_REVIEW,
        label_names,
    )
    from orquestador_kit import (
        PlanError,
        PlannedTask,
        build_task_marker,
        parse_plan,
        parse_task_marker,
        render_graph,
        topological_order,
    )
    from roles_kit import classify

ROLE_COLOR = "5319E7"
REPORT_PREFIX = "<!-- factory-plan-report:"


def _all_issues(api: GitHub) -> list[dict[str, Any]]:
    return [
        issue
        for issue in api.paginate(f"/repos/{api.repo}/issues?state=all")
        if not issue.get("pull_request")
    ]


def _existing_tasks(
    issues: list[dict[str, Any]],
    epic: int,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for issue in issues:
        body = str(issue.get("body") or "")
        try:
            marker = parse_task_marker(body)
        except PlanError as exc:
            if "factory-plan-task" in body:
                raise PlanError(
                    f"Issue #{issue.get('number')} tiene marker de tarea inválido."
                ) from exc
            continue
        if marker is None or marker["epic"] != epic:
            continue
        key = marker["task_key"]
        if key in result:
            raise PlanError(f"Más de un Issue materializa {key} del épico #{epic}.")
        result[key] = issue
    return result


def _inherited_labels(epic: dict[str, Any]) -> list[str]:
    labels = label_names(epic)
    types = sorted(label for label in labels if label.startswith("tipo: "))
    priorities = sorted(
        label for label in labels if label.startswith("prioridad: ")
    )
    if len(types) != 1 or len(priorities) != 1:
        raise PlanError(
            "El épico debe tener exactamente un tipo y una prioridad."
        )
    return types + priorities


def _roles_for(task: PlannedTask, epic: dict[str, Any]) -> list[str]:
    context = {
        "body": "",
        "title": task.title,
        "labels": sorted(label_names(epic)),
        "files": list(task.paths),
    }
    roles, _ = classify(context)
    return roles


def _ensure_role_labels(api: GitHub, roles: list[str]) -> list[str]:
    labels: list[str] = []
    for role in roles:
        name = f"rol: {role}"
        api.ensure_label(
            name,
            ROLE_COLOR,
            f"Rol profesional requerido por el orquestador: {role}.",
        )
        labels.append(name)
    return labels


def _task_body(
    epic: int,
    task: PlannedTask,
    order: int,
    roles: list[str],
    dependency_issues: list[int],
) -> str:
    dependencies = (
        ", ".join(f"#{number}" for number in dependency_issues)
        if dependency_issues
        else "ninguna"
    )
    paths = "\n".join(f"- {path}" for path in task.paths)
    return (
        f"Parte planificada automáticamente del épico #{epic}.\n\n"
        f"Owner: @{task.owner}\n"
        f"Orden: {order}\n"
        f"Roles: {', '.join(roles)}\n"
        f"Dependencias: {dependencies}\n\n"
        "## Rutas reclamadas\n\n"
        f"{paths}\n\n"
        + build_task_marker(
            epic=epic,
            task=task,
            order=order,
            roles=roles,
            dependency_issues=dependency_issues,
        )
    )


def _active(issue: dict[str, Any]) -> bool:
    return bool(
        label_names(issue)
        & {STATUS_RESERVED, STATUS_REVIEW, STATUS_RECOVERY}
    )


def _verify_owner(issue: dict[str, Any], owner: str) -> None:
    assigned = {
        str(item.get("login"))
        for item in issue.get("assignees", [])
        if isinstance(item, dict) and item.get("login")
    }
    if owner not in assigned:
        raise PlanError(f"No fue posible asignar la tarea a @{owner}.")


def _sync_role_labels(
    api: GitHub,
    issue_number: int,
    role_labels: list[str],
    current_labels: set[str],
) -> None:
    wanted = set(role_labels)
    for label in current_labels:
        if label.startswith("rol: ") and label not in wanted:
            api.remove_label(issue_number, label)
    api.add_labels(issue_number, role_labels)


def _upsert_issue(
    api: GitHub,
    *,
    existing: dict[str, Any] | None,
    epic: int,
    task: PlannedTask,
    order: int,
    roles: list[str],
    dependency_issues: list[int],
    inherited_labels: list[str],
) -> dict[str, Any]:
    title = f"[EPIC #{epic}/{task.key}] {task.title}"
    body = _task_body(epic, task, order, roles, dependency_issues)
    role_labels = _ensure_role_labels(api, roles)
    if existing is None:
        payload = {
            "title": title,
            "body": body,
            "assignees": [task.owner],
            "labels": inherited_labels + [STATUS_AVAILABLE] + role_labels,
        }
        created = api.request("POST", f"/repos/{api.repo}/issues", payload)
        if not isinstance(created, dict):
            raise PlanError(f"No se pudo crear {task.key}.")
        _verify_owner(created, task.owner)
        return created

    old_marker = parse_task_marker(str(existing.get("body") or ""))
    new_marker = parse_task_marker(body)
    if _active(existing) and old_marker != new_marker:
        raise PlanError(
            f"Issue #{existing.get('number')} está activo; su plan no puede mutar."
        )
    number = existing.get("number")
    if not isinstance(number, int):
        raise PlanError("Issue materializado sin número válido.")
    api.request(
        "PATCH",
        f"/repos/{api.repo}/issues/{number}",
        {"title": title, "body": body},
    )
    api.request(
        "POST",
        f"/repos/{api.repo}/issues/{number}/assignees",
        {"assignees": [task.owner]},
    )
    api.add_labels(number, inherited_labels)
    _sync_role_labels(api, number, role_labels, label_names(existing))
    refreshed = api.issue(number)
    _verify_owner(refreshed, task.owner)
    return refreshed


def _upsert_report(api: GitHub, epic: int, body: str) -> None:
    marker = f"{REPORT_PREFIX}{epic} -->"
    for comment in api.issue_comments(epic):
        user = comment.get("user")
        if (
            isinstance(comment.get("body"), str)
            and marker in comment["body"].splitlines()
            and isinstance(user, dict)
            and user.get("login") == "github-actions[bot]"
        ):
            comment_id = comment.get("id")
            if isinstance(comment_id, int):
                api.request(
                    "PATCH",
                    f"/repos/{api.repo}/issues/comments/{comment_id}",
                    {"body": body},
                )
                return
    api.comment(epic, body)


def sync_plan(api: GitHub, epic_number: int) -> dict[str, Any]:
    epic = api.issue(epic_number)
    if epic.get("pull_request") or epic.get("state") != "open":
        raise PlanError("El épico debe ser un Issue abierto.")
    tasks = parse_plan(str(epic.get("body") or ""))
    ordered = topological_order(tasks)
    all_issues = _all_issues(api)
    existing = _existing_tasks(all_issues, epic_number)
    planned_keys = {task.key for task in tasks}
    orphaned = sorted(set(existing) - planned_keys)
    if orphaned:
        raise PlanError(
            "No se eliminan tareas ya materializadas: " + ", ".join(orphaned)
        )

    issue_numbers: dict[str, int] = {}
    task_roles: dict[str, list[str]] = {}
    inherited = _inherited_labels(epic)
    for order, task in enumerate(ordered, 1):
        roles = _roles_for(task, epic)
        task_roles[task.key] = roles
        dependencies = [issue_numbers[key] for key in task.depends_on]
        materialized = _upsert_issue(
            api,
            existing=existing.get(task.key),
            epic=epic_number,
            task=task,
            order=order,
            roles=roles,
            dependency_issues=dependencies,
            inherited_labels=inherited,
        )
        number = materialized.get("number")
        if not isinstance(number, int):
            raise PlanError(f"{task.key} quedó sin número de Issue.")
        issue_numbers[task.key] = number

    report = render_graph(epic_number, tasks, issue_numbers, task_roles)
    _upsert_report(api, epic_number, report)
    return {
        "epic": epic_number,
        "tasks": len(tasks),
        "issues": issue_numbers,
        "order": [task.key for task in ordered],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync",))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--epic", type=int, required=True)
    args = parser.parse_args()
    try:
        result = sync_plan(GitHub(args.repo), args.epic)
    except (PlanError, GitHubError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
