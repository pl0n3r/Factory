#!/usr/bin/env python3
"""Hook SessionStart: informa el estado del kill switch global (Factory#767).

Solo informa (contexto adicional); nunca modifica el marker. Fallo de lectura
= UNKNOWN, que PLAN-AGENTES trata como pausa fail-closed para mutar GitHub.
"""
import json
import re
import subprocess
import sys

MARKER = re.compile(r"<!--\s*factory-unattended-kill-switch\s+(\{.*?\})\s*-->", re.S)


def parse_kill_switch(issue):
    """Devuelve ('RUNNING'|'PAUSED'|'UNKNOWN', razón) a partir del JSON del Issue."""
    login = ((issue.get("user") or {}).get("login") or "")
    if login != "pl0n3r":
        return "UNKNOWN", "creador inesperado del Issue #767"
    markers = MARKER.findall(issue.get("body") or "")
    if len(markers) != 1:
        return "UNKNOWN", f"marker ausente o duplicado ({len(markers)})"
    try:
        data = json.loads(markers[0])
    except ValueError:
        return "UNKNOWN", "marker con JSON inválido"
    if data.get("version") != 1 or data.get("owner") != "pl0n3r" or data.get("state") not in ("RUNNING", "PAUSED"):
        return "UNKNOWN", "marker con versión/owner/estado inválidos"
    return data["state"], "marker válido"


def fetch_issue():
    out = subprocess.run(["gh", "api", "repos/pl0n3r/Factory/issues/767"],
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:200] or "gh falló")
    return json.loads(out.stdout)


def message(state, reason):
    if state == "RUNNING":
        return "Kill switch Factory#767: RUNNING."
    return (f"PAUSADO: kill switch global no está en RUNNING ({state}: {reason}). "
            "No hagas mutaciones en GitHub (comentarios de despacho, /tomar, ramas, PRs, código) hasta verificarlo.")


def main():
    try:
        state, reason = parse_kill_switch(fetch_issue())
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        state, reason = "UNKNOWN", f"fuente ilegible: {exc}"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": message(state, reason)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
