#!/usr/bin/env python3
"""Hook PreToolUse(Edit|Write): comprueba la reserva del Issue de la rama.

En `trabajo/issue-N` bloquea solo si el Issue está cerrado o sin reserva
(`estado: disponible`/`bloqueado`); con red caída o Issue ilegible avisa y
deja pasar para no impedir trabajo legítimo. Fuera de esa rama avisa si se
edita sobre main protegido.
"""
import json
import re
import subprocess
import sys

BRANCH = re.compile(r"^trabajo/issue-(\d+)$")


def current_branch():
    out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=10)
    return out.stdout.strip() if out.returncode == 0 else ""


def fetch_issue(number, repo):
    out = subprocess.run(["gh", "api", f"repos/{repo}/issues/{number}"], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:200] or "gh falló")
    return json.loads(out.stdout)


def origin_repo():
    out = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=10)
    m = re.search(r"github\.com[:/]([^/]+/[^/.\s]+)", out.stdout)
    return m.group(1) if m else ""


def evaluate(branch, fetch=None):
    """('allow'|'warn'|'deny', razón)."""
    if branch in ("main", "master"):
        return "warn", "Estás en main (protegido): crea `trabajo/issue-N` tras `/tomar` antes de editar."
    m = BRANCH.match(branch)
    if not m or fetch is None:
        return "allow", ""
    try:
        issue = fetch(int(m.group(1)))
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return "warn", f"No se pudo verificar la reserva del Issue #{m.group(1)} ({exc})."
    labels = {l.get("name", "") for l in issue.get("labels", [])}
    if issue.get("state") == "closed":
        return "deny", f"El Issue #{m.group(1)} está cerrado: no escribas en su rama."
    for estado in ("estado: disponible", "status: available", "estado: bloqueado", "status: blocked"):
        if estado in labels:
            return "deny", f"El Issue #{m.group(1)} no está reservado ({estado}): usa `/tomar` primero."
    return "allow", ""


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if event.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        return 0
    repo = origin_repo()
    try:
        branch = current_branch()
    except (OSError, subprocess.TimeoutExpired):
        return 0
    fetch = (lambda n: fetch_issue(n, repo)) if repo else None
    decision, reason = evaluate(branch, fetch)
    if decision == "deny":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    elif decision == "warn":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "additionalContext": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
