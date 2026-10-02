#!/usr/bin/env python3
"""Gobernanza fail-closed para el check de etiquetas de PRs.

El módulo es deliberadamente puro: clasifica evidencia ya obtenida de GitHub,
produce el payload administrativo que solo puede aplicar el dueño y genera el
plan idempotente de alerta para un PR fusionado con el check de etiquetas rojo.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable

OWNER = "pl0n3r"
REPOSITORIES = (
    "Factory",
    "Condor",
    "GrindFlow",
    "brvtal",
    "ControlBot",
    "AutoFactory",
    "FactoryRunner",
)
RULESET_TARGET_REPOSITORIES = tuple(
    repository for repository in REPOSITORIES if repository != "GrindFlow"
)
REQUIRED_CONTEXT = "Etiquetas"
GITHUB_ACTIONS_INTEGRATION_ID = 15368
RULESET_NAME = "factory-required-labels"
ALERT_MARKER_PREFIX = "<!-- factory-pr-label-governance-alert"
MAX_ITEMS = 500


class GovernanceError(ValueError):
    pass


def _bounded_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise GovernanceError(f"{field} debe ser una lista acotada.")
    return value


def _ruleset_applies_to_default_branch(ruleset: Any) -> bool:
    if not isinstance(ruleset, dict):
        raise GovernanceError("ruleset inválido.")
    if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
        return False
    conditions = ruleset.get("conditions") or {}
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
    if not isinstance(ref_name, dict):
        return True
    includes = ref_name.get("include")
    return not (
        isinstance(includes, list)
        and includes
        and "~DEFAULT_BRANCH" not in includes
    )


def _required_status_checks(rule: Any) -> list[Any]:
    if not isinstance(rule, dict):
        raise GovernanceError("ruleset rule inválida.")
    if rule.get("type") != "required_status_checks":
        return []
    parameters = rule.get("parameters") or {}
    checks = (
        parameters.get("required_status_checks")
        if isinstance(parameters, dict)
        else None
    )
    if checks is None:
        return []
    return _bounded_list(checks, "required_status_checks")


def _status_contexts_from_rulesets(rulesets: Any) -> set[str]:
    if rulesets is None:
        return set()
    contexts: set[str] = set()
    for ruleset in _bounded_list(rulesets, "rulesets"):
        if not _ruleset_applies_to_default_branch(ruleset):
            continue
        for rule in _bounded_list(ruleset.get("rules") or [], "ruleset.rules"):
            for check in _required_status_checks(rule):
                context = check.get("context") if isinstance(check, dict) else None
                if isinstance(context, str):
                    contexts.add(context)
    return contexts


def _status_contexts_from_branch_protection(branch_protection: Any) -> set[str]:
    if branch_protection is None:
        return set()
    if not isinstance(branch_protection, dict):
        raise GovernanceError("branch_protection inválido.")
    required = branch_protection.get("required_status_checks")
    if required is None:
        return set()
    if not isinstance(required, dict):
        raise GovernanceError("required_status_checks inválido.")
    contexts: set[str] = set()
    raw_contexts = required.get("contexts") or []
    for context in _bounded_list(raw_contexts, "branch_protection.contexts"):
        if isinstance(context, str):
            contexts.add(context)
    checks = required.get("checks") or []
    for check in _bounded_list(checks, "branch_protection.checks"):
        if isinstance(check, dict) and isinstance(check.get("context"), str):
            contexts.add(check["context"])
    return contexts


def audit_repository(
    repository: str,
    *,
    rulesets: Any,
    branch_protection: Any,
) -> dict[str, Any]:
    if repository not in REPOSITORIES:
        raise GovernanceError("Repositorio fuera de la cola canónica.")
    ruleset_contexts = _status_contexts_from_rulesets(rulesets)
    protection_contexts = _status_contexts_from_branch_protection(branch_protection)
    contexts = sorted(ruleset_contexts | protection_contexts)
    if REQUIRED_CONTEXT in contexts:
        status = "required"
    elif rulesets is None or branch_protection is None:
        status = "unknown"
    else:
        status = "missing"
    return {
        "repository": f"{OWNER}/{repository}",
        "status": status,
        "required_context": REQUIRED_CONTEXT,
        "observed_contexts": contexts,
        "rulesets_visible": rulesets is not None,
        "branch_protection_visible": branch_protection is not None,
    }


def uniform_ruleset_payload() -> dict[str, Any]:
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {
            "ref_name": {
                "include": ["~DEFAULT_BRANCH"],
                "exclude": [],
            }
        },
        "rules": [
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": False,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [
                        {
                            "context": REQUIRED_CONTEXT,
                            "integration_id": GITHUB_ACTIONS_INTEGRATION_ID,
                        }
                    ],
                },
            }
        ],
    }


def owner_commands(
    repositories: Iterable[str] = RULESET_TARGET_REPOSITORIES,
) -> list[str]:
    commands = [
        "python3 scripts/pr_label_governance.py ruleset-payload > /tmp/factory-required-labels.json"
    ]
    for repository in repositories:
        if repository not in REPOSITORIES:
            raise GovernanceError("Repositorio fuera de la cola canónica.")
        commands.append(
            "gh api --method POST "
            f"repos/{OWNER}/{repository}/rulesets "
            "--input /tmp/factory-required-labels.json"
        )
    return commands


def _is_label_check(name: Any) -> bool:
    if not isinstance(name, str):
        return False
    normalized = name.strip()
    return normalized == REQUIRED_CONTEXT or normalized == "Labels" or normalized.endswith(" / Labels")


def _check_sort_key(check: dict[str, Any]) -> tuple[str, str, int]:
    completed = check.get("completed_at") if isinstance(check.get("completed_at"), str) else ""
    started = check.get("started_at") if isinstance(check.get("started_at"), str) else ""
    identifier = check.get("id") if isinstance(check.get("id"), int) else 0
    return completed, started, identifier


def _validated_alert_identity(document: Any) -> tuple[dict[str, Any], int, str]:
    if not isinstance(document, dict) or set(document) != {"pr", "check_runs", "comments"}:
        raise GovernanceError("Documento de alerta inválido.")
    pr = document["pr"]
    if not isinstance(pr, dict):
        raise GovernanceError("PR inválido.")
    number = pr.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise GovernanceError("Número de PR inválido.")
    head = pr.get("head")
    if not isinstance(head, dict) or not isinstance(head.get("sha"), str) or len(head["sha"]) != 40:
        raise GovernanceError("HEAD de PR inválido.")
    return pr, number, head["sha"]


def _latest_label_check(check_runs: Any) -> dict[str, Any] | None:
    candidates = [
        item
        for item in _bounded_list(check_runs, "check_runs")
        if isinstance(item, dict) and _is_label_check(item.get("name"))
    ]
    return max(candidates, key=_check_sort_key) if candidates else None


def _comments_contain_marker(comments: Any, marker: str) -> bool:
    for comment in _bounded_list(comments, "comments"):
        body = comment.get("body") if isinstance(comment, dict) else None
        if isinstance(body, str) and body.startswith(marker):
            return True
    return False


def merged_pr_alert_plan(document: Any) -> dict[str, Any]:
    pr, number, head_sha = _validated_alert_identity(document)
    merged_at = pr.get("merged_at")
    if not merged_at:
        return {"action": "noop", "reason": "not_merged", "pr": number}

    latest = _latest_label_check(document["check_runs"])
    if latest is None:
        return {"action": "noop", "reason": "no_label_check", "pr": number}
    if latest.get("status") != "completed":
        return {"action": "noop", "reason": "label_check_not_terminal", "pr": number}
    if latest.get("conclusion") == "success":
        return {"action": "noop", "reason": "label_check_green", "pr": number}

    marker = f"{ALERT_MARKER_PREFIX} pr={number} -->"
    if _comments_contain_marker(document["comments"], marker):
        return {"action": "noop", "reason": "already_alerted", "pr": number}

    check_name = latest.get("name") if isinstance(latest.get("name"), str) else "unknown"
    conclusion = latest.get("conclusion") if isinstance(latest.get("conclusion"), str) else "unknown"
    details_url = latest.get("details_url") if isinstance(latest.get("details_url"), str) else ""
    body = (
        f"{marker}\n"
        "⚠️ Gobernanza de etiquetas: este PR fue fusionado sin una señal verde posterior "
        "del check canónico de etiquetas.\n\n"
        f"- PR: #{number}\n"
        f"- merge: `{merged_at}`\n"
        f"- HEAD: `{head_sha}`\n"
        f"- check observado: `{check_name}` → `{conclusion}`\n"
        f"- evidencia: {details_url or 'sin details_url'}\n\n"
        "Esta alerta es idempotente y no modifica rulesets ni intenta revertir el merge."
    )
    return {
        "action": "create",
        "reason": "merged_with_non_green_labels",
        "pr": number,
        "body": body,
    }


def _audit_document(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or set(document) != {"repositories"}:
        raise GovernanceError("Documento de auditoría inválido.")
    entries = _bounded_list(document["repositories"], "repositories")
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "rulesets", "branch_protection"}:
            raise GovernanceError("Entrada de auditoría inválida.")
        result.append(
            audit_repository(
                entry["name"],
                rulesets=entry["rulesets"],
                branch_protection=entry["branch_protection"],
            )
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("audit", "ruleset-payload", "owner-commands", "alert-plan"),
    )
    args = parser.parse_args()
    try:
        if args.command == "ruleset-payload":
            payload = uniform_ruleset_payload()
        elif args.command == "owner-commands":
            payload = {"commands": owner_commands()}
        elif args.command == "audit":
            payload = {"repositories": _audit_document(json.load(sys.stdin))}
        else:
            payload = merged_pr_alert_plan(json.load(sys.stdin))
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    except (GovernanceError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
