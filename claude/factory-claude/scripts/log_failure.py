#!/usr/bin/env python3
"""Hook PostToolUseFailure: registra errores de herramientas en JSONL.

Idempotente (una línea por tool_use_id), acotado (rota a 500 líneas), sin
secretos (solo nombre de herramienta y primeros 300 caracteres del error) y
sin salida: nunca puede crear bucles ni bloquear.
"""
import json
import os
import sys

MAX_LINES = 500


def log_dir(root):
    """`.git/` nunca se rastrea; `.claude/` solo si el repo no tiene directorio .git."""
    git = os.path.join(root, ".git")
    return os.path.join(git if os.path.isdir(git) else os.path.join(root, ".claude"), "factory-claude")


def record(event):
    return {
        "id": event.get("tool_use_id", ""),
        "tool": event.get("tool_name", ""),
        "error": str(event.get("error", ""))[:300],
        "session": event.get("session_id", ""),
    }


def append(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    if rec["id"] and any(f'"id": "{rec["id"]}"' in l for l in lines):
        return False
    lines.append(json.dumps(rec, ensure_ascii=False))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines[-MAX_LINES:]) + "\n")
    return True


def main():
    try:
        event = json.load(sys.stdin)
        root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or "."
        append(os.path.join(log_dir(root), "errores.jsonl"), record(event))
    except (ValueError, OSError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
