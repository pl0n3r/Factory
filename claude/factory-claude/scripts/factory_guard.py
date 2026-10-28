#!/usr/bin/env python3
"""Hook PreToolUse(Bash): guardas ejecutables de PLAN-AGENTES.md.

Solo bloquea tres cosas: saltarse la protección de rama (`--admin`, push
directo/forzado a main), fusionar sin `Validar` verde y pedir CodeRabbit antes
de tiempo o por segunda vez. Todo lo demás pasa. Python 3 stdlib, sin red salvo
`gh` para leer checks del PR.
"""
import datetime
import json
import os
import re
import subprocess
import sys

ALLOW = ("allow", "")
CODERABBIT_REQUEST = re.compile(r"@coderabbitai\s+(full\s+review|review|resume)", re.I)
GH_PR_MERGE = re.compile(r"\bgh\s+pr\s+merge\b")
GH_COMMENT = re.compile(r"\bgh\s+(pr|issue)\s+comment\b")
PUSH_MAIN = re.compile(r"\bgit\s+push\b[^\n;&|]*\b(main|master)\b")
PUSH_FORCE = re.compile(r"\bgit\s+push\b[^\n;&|]*(\s-f\b|--force(?!-with-lease))")


def _pr_ref(command):
    for token in re.findall(r"\bgh\s+pr\s+(?:merge|comment)\s+(\S+)", command):
        if not token.startswith("-"):
            return token
    return ""


def gh_pr_state(pr_ref):
    """Devuelve (checks, comments) del PR o lanza RuntimeError."""
    base = ["gh", "pr"]
    ref = [pr_ref] if pr_ref else []
    try:
        checks = subprocess.run(base + ["checks"] + ref + ["--json", "name,state,bucket"],
                                capture_output=True, text=True, timeout=30)
        view = subprocess.run(base + ["view"] + ref + ["--json", "comments"],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(str(exc)) from exc
    # `gh pr checks` sale con 8 si hay checks pendientes: el JSON sigue siendo válido.
    if view.returncode != 0 or not checks.stdout.strip():
        raise RuntimeError((checks.stderr or view.stderr or "sin salida").strip()[:200])
    return json.loads(checks.stdout), json.loads(view.stdout).get("comments", [])


def ci_is_green(checks):
    if not checks:
        return False
    validar = [c for c in checks if c.get("name") in ("Validar", "validate")]
    if not validar or any(c.get("bucket") != "pass" for c in validar):
        return False
    return all(c.get("bucket") in ("pass", "skipping") for c in checks)


def coderabbit_already_requested(comments):
    return any(CODERABBIT_REQUEST.search(c.get("body", "") or "") for c in comments)


def evaluate(command, fetch_state=gh_pr_state):
    """Decisión pura: ('allow'|'deny', razón). `fetch_state` se inyecta en tests."""
    if GH_PR_MERGE.search(command):
        if re.search(r"(\s|^)--admin\b", command):
            return "deny", "PLAN-AGENTES: prohibido `gh pr merge --admin`; la protección de rama no se salta."
        try:
            checks, _ = fetch_state(_pr_ref(command))
        except RuntimeError as exc:
            return "deny", f"Merge bloqueado: no se pudo verificar CI ({exc}). Estado UNKNOWN falla cerrado."
        if not ci_is_green(checks):
            return "deny", "Merge bloqueado: `Validar` y los demás checks deben estar en verde sobre el HEAD del PR."
    if GH_COMMENT.search(command) and CODERABBIT_REQUEST.search(command):
        try:
            checks, comments = fetch_state(_pr_ref(command))
        except RuntimeError as exc:
            return "deny", f"CodeRabbit: no se pudo verificar CI ({exc}); no se solicita revisión a ciegas."
        if coderabbit_already_requested(comments):
            return "deny", "CodeRabbit ya fue solicitado en este PR: se pide UNA sola vez."
        if not ci_is_green(checks):
            return "deny", "CodeRabbit solo se solicita con el PR definitivo y el CI completamente verde."
    if PUSH_FORCE.search(command) and PUSH_MAIN.search(command):
        return "deny", "Push forzado a main prohibido."
    if PUSH_MAIN.search(command) and not re.search(r"trabajo/issue-\d+", command):
        return "deny", "main está protegido: trabaja en `trabajo/issue-N` y abre un PR."
    return ALLOW


def log_decision(decision, reason, command):
    """Registra cada bloqueo con marca de tiempo (sin el comando completo: puede traer secretos)."""
    try:
        root = os.environ.get("CLAUDE_PROJECT_DIR") or "."
        path = os.path.join(root, ".claude", "factory-claude", "decisiones.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                 "decision": decision, "reason": reason, "cmd": command.split()[:3]}) + "\n")
    except OSError:
        pass


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # entrada ilegible: no bloquear operaciones legítimas
    if event.get("tool_name") != "Bash":
        return 0
    decision, reason = evaluate((event.get("tool_input") or {}).get("command", ""))
    if decision == "deny":
        log_decision(decision, reason, (event.get("tool_input") or {}).get("command", ""))
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
