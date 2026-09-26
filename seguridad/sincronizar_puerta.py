#!/usr/bin/env python3
"""Sincroniza invalid-gate sin sobrescribir etiquetas de otros escritores."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from urllib.parse import quote

MARKER = "<!-- factory-invalid-gate -->"
OWNED = "<!-- factory-invalid-gate-owner:bot -->"
BOT = "github-actions[bot]"
BLOCKED = "estado: bloqueado"
AVAILABLE = "estado: disponible"


def gh_api(method: str, path: str, payload: dict | None = None):
    command = ["gh", "api"]
    if method == "GET" and ("?per_page=" in path):
        command += ["--paginate", "--slurp"]
    if method != "GET":
        command += ["--method", method]
    command.append(path)
    if payload is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        capture_output=True,
        text=True,
        check=True,
    )
    value = json.loads(result.stdout) if result.stdout.strip() else None
    if method == "GET" and "?per_page=" in path:
        # --slurp devuelve una lista de páginas (cada página es una lista).
        return [item for page in value for item in page]
    return value


def issue_labels(api, base: str) -> set[str]:
    return {label["name"] for label in api("GET", base)["labels"]}


def comments_for(api, base: str) -> list[dict]:
    return api("GET", f"{base}/comments?per_page=100")


def bot_comment(api, base: str) -> dict | None:
    return next(
        (
            comment for comment in comments_for(api, base)
            if comment.get("user", {}).get("login") == BOT
            and comment.get("body", "").startswith(MARKER)
        ),
        None,
    )


def last_block_actor(api, base: str) -> str | None:
    events = api("GET", f"{base}/events?per_page=100")
    relevant = (
        event for event in reversed(events)
        if event.get("label", {}).get("name") == BLOCKED
        and event.get("event") in ("labeled", "unlabeled")
    )
    last = next(relevant, None)
    if last is None or last["event"] != "labeled":
        return None
    return last.get("actor", {}).get("login")


def add_label(api, base: str, label: str) -> None:
    api("POST", f"{base}/labels", {"labels": [label]})


def remove_label(api, base: str, label: str) -> None:
    api("DELETE", f"{base}/labels/{quote(label, safe='')}")


def sync_invalid(api, repository: str, issue: int, reason: str) -> None:
    base = f"repos/{repository}/issues/{issue}"
    labels = issue_labels(api, base)
    existing = bot_comment(api, base)
    # Un bloqueo previo del dueño no se reclama como propio.
    if BLOCKED in labels:
        owned = bool(
            existing and OWNED in existing["body"]
            and last_block_actor(api, base) == BOT
        )
    else:
        # Solo se cambian las etiquetas de estado; no PATCH de toda la lista.
        for label in labels:
            if label.startswith("estado: "):
                remove_label(api, base, label)
        add_label(api, base, BLOCKED)
        owned = True

    message = (
        f"{MARKER}\n"
        + (f"{OWNED}\n" if owned else "")
        + f"⛔ Puerta humana inválida. Motivo de validación: {reason}"
    )
    if existing:
        if existing["body"] != message:
            api("PATCH", f"repos/{repository}/issues/comments/{existing['id']}", {"body": message})
    else:
        api("POST", f"{base}/comments", {"body": message})


def sync_valid(api, repository: str, issue: int) -> None:
    base = f"repos/{repository}/issues/{issue}"
    comment = bot_comment(api, base)
    if not comment or OWNED not in comment["body"]:
        return
    if BLOCKED not in issue_labels(api, base):
        return
    # Además del marker, comprobar el último actor que aplicó el bloqueo actual.
    if last_block_actor(api, base) != BOT:
        return
    remove_label(api, base, BLOCKED)
    # Nunca reemplazar etiquetas ajenas, ni restaurar si otro agente puso estado.
    if not any(
        name.startswith("estado: ") for name in issue_labels(api, base)
    ):
        add_label(api, base, AVAILABLE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("invalid", "valid"))
    args = parser.parse_args()
    repository = os.environ["REPOSITORIO"]
    issue = int(os.environ["ISSUE"])
    if args.action == "invalid":
        sync_invalid(gh_api, repository, issue, os.environ["REASON"])
    else:
        sync_valid(gh_api, repository, issue)


if __name__ == "__main__":
    main()
