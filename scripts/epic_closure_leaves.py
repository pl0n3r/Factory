#!/usr/bin/env python3
"""Genera hojas de cierre o mapeo para épicas sin hojas abiertas.

Fail-closed, sin mutaciones por defecto. No cierra épicas ni inventa evidencia.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    from .issue_contract_preflight import evaluate_issue_body
    from .unattended_kill_switch import evaluate_unattended_kill_switch
except ImportError:
    from issue_contract_preflight import evaluate_issue_body
    from unattended_kill_switch import evaluate_unattended_kill_switch

API = "https://api.github.com"
MARKER = "factory-epic-closure"
TASK = re.compile(r"<!--\s*factory-plan-task\s+(\{[^<>]*\})\s*-->")
CLOSURE = re.compile(r"<!--\s*factory-epic-closure\s+(\{[^<>]*\})\s*-->")
EPIC = re.compile(r"^\s*(?:epic|épica|roadmap)\b", re.I)
CRITERION = re.compile(r"^\s*-\s*\[([ xX])\]\s*(?:\[(AC-\d{2})\])?\s*(\S.*)$", re.M)
EVIDENCE = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:commit/[0-9a-fA-F]{40}|pull/[1-9]\d*|actions/runs/[1-9]\d*|issues/[1-9]\d*#issuecomment-[1-9]\d*)"
)
EXCLUDE = ("decisión", "decision", "del dueño", "owner-only", "human-only",
           "live", "go-live", "legal", "gasto", "spend", "payment", "pago")
MAX_ISSUES = 5000


class EpicError(ValueError):
    pass


@dataclass(frozen=True)
class Proposal:
    epic: int
    kind: str
    title: str
    body: str


def _labels(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels", [])
    if not isinstance(labels, list):
        raise EpicError("Labels ilegibles")
    if any(not isinstance(row, (dict, str)) for row in labels):
        raise EpicError("Label inválida")
    return {
        str(row.get("name", "") if isinstance(row, dict) else row).casefold()
        for row in labels
    }


def _excluded(issue: dict[str, Any]) -> bool:
    title = str(issue.get("title") or "").casefold()
    return any(any(word in label for word in EXCLUDE) for label in _labels(issue)) or title.startswith(
        ("decisión:", "decision:", "decisión del dueño", "owner:")
    )


def _task_parent(issue: dict[str, Any]) -> int | None:
    body = issue.get("body") or ""
    if not isinstance(body, str):
        raise EpicError("Body ilegible")
    found = TASK.findall(body)
    if not found:
        return None
    if len(found) != 1:
        raise EpicError("Marker factory-plan-task ambiguo")
    try:
        data = json.loads(found[0])
    except ValueError as exc:
        raise EpicError("Marker factory-plan-task malformado") from exc
    if not isinstance(data, dict) or type(data.get("epic")) is not int or data["epic"] < 1:
        raise EpicError("Parent inválido")
    return data["epic"]


def _existing(issue: dict[str, Any]) -> int | None:
    body = issue.get("body") or ""
    if not isinstance(body, str):
        raise EpicError("Body ilegible")
    found = CLOSURE.findall(body)
    if not found:
        return None
    if len(found) != 1:
        raise EpicError("Marker de cierre duplicado")
    try:
        data = json.loads(found[0])
    except ValueError as exc:
        raise EpicError("Marker de cierre inválido") from exc
    if (not isinstance(data, dict) or set(data) != {"version", "epic", "kind"}
        or type(data["version"]) is not int or data["version"] != 1
        or type(data["epic"]) is not int or data["epic"] < 1
        or data["kind"] not in ("cierre", "mapeo")):
        raise EpicError("Marker de cierre inválido")
    return data["epic"]


def _kind(body: str) -> str:
    section = re.search(r"(?mi)^#{2,4}\s+Criterios de aceptación\s*$", body)
    if section:
        tail = body[section.end():]
        heading = re.search(r"(?m)^#{2,4}\s+", tail)
        body = tail[:heading.start()] if heading else tail
    found = list(CRITERION.finditer(body))
    if not found:
        return "mapeo"
    return ("cierre" if all(row.group(1).lower() == "x"
            or EVIDENCE.search(row.group(3)) for row in found) else "mapeo")


def make_leaf(epic: dict[str, Any], kind: str, repo: str, check: str) -> Proposal:
    number = epic["number"]
    if type(number) is not int or number < 1 or kind not in ("cierre", "mapeo"):
        raise EpicError("Épica o tipo inválido")
    if (not isinstance(check, str) or not 1 <= len(check) <= 120
        or "\n" in check or check in ("Validar", "Criterios de aceptación")):
        raise EpicError("Check de aceptación inválido")
    action = "cerrar" if kind == "cierre" else "mapear"
    title = f"ops(epic): {action} épica #{number} con evidencia canónica"
    task = {"version": 1, "epic": number,
            "task_key": f"EPIC_{number}_{'CLOSE' if kind == 'cierre' else 'MAP'}",
            "order": number, "owner": "pl0n3r", "roles": ["ingenieria-software", "qa"],
            "depends_on": [], "paths": [f"docs/epic-evidence/{number}-{kind}.md"]}
    marker = {"version": 1, "epic": number, "kind": kind}
    action_text = (
        "Contrastar todos los AC y evidencias con el SHA actual de main; comprobar "
        "que no haya hojas abiertas ni puertas humanas, documentar cada prueba y "
        "cerrar la épica como completed únicamente en construcción."
        if kind == "cierre" else
        "Dividir los criterios técnicos pendientes mediante factory-epic-splitter "
        "en hojas con aceptación ejecutable; registrar en la épica los pendientes "
        "que solo pueda resolver el dueño, sin crear hojas automáticas para ellos."
    )
    acceptance = {"version": 1, "criteria": [
        {"id": "AC-01", "kind": "check", "target": check},
        {"id": "AC-02", "kind": "check", "target": check},
    ]}
    encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    body = (
        f"### Contexto\nParent: [{repo}#{number}](https://github.com/{repo}/issues/{number}). "
        f"Hoja candidata de {kind}; no demuestra aceptación.\n\n"
        f"### Alcance\n- {action_text}\n- Conservar UNKNOWN ante evidencia ilegible.\n\n"
        "### Fuera de alcance\n- Live, gasto, datos reales, publicación, "
        "secrets, deploy y pruebas inventadas.\n\n"
        "### Criterios de aceptación\n"
        "- [ ] [AC-01] Evidencia y dependencias verificadas contra main.\n"
        f"- [ ] [AC-02] Resultado de {kind} documentado sin saltar puertas humanas.\n\n"
        f"### Contrato ejecutable\n<!-- factory-acceptance {encode(acceptance)} -->\n\n"
        f"### Rutas reclamadas\n- docs/epic-evidence/{number}-{kind}.md\n\n"
        f"<!-- factory-plan-task {encode(task)} -->\n"
        f"<!-- {MARKER} {encode(marker)} -->\n\n"
        "### Riesgo y reversión\nReversible por reclasificación de la hoja, "
        "sin cierre automático del padre.\n"
    )
    evaluate_issue_body(body)
    return Proposal(number, kind, title, body)


def proposals(issues: list[dict[str, Any]], repo: str, check: str) -> list[Proposal]:
    if not isinstance(issues, list) or len(issues) > MAX_ISSUES:
        raise EpicError("Listado de issues incompleto")
    numbers, referenced, active, existing = set(), set(), set(), set()
    for issue in issues:
        if not isinstance(issue, dict) or type(issue.get("number")) is not int:
            raise EpicError("Issue inválido")
        number = issue["number"]
        if number in numbers:
            raise EpicError("Issue duplicado")
        numbers.add(number)
        if issue.get("pull_request"):
            continue
        parent = _task_parent(issue)
        if parent is not None:
            referenced.add(parent)
            if issue.get("state") == "open":
                active.add(parent)
        previous = _existing(issue)
        if previous is not None:
            existing.add(previous)
    result = []
    for issue in issues:
        if issue.get("state") != "open" or issue.get("pull_request"):
            continue
        number = issue["number"]
        if number not in referenced and not EPIC.search(str(issue.get("title") or "")):
            continue
        if number in active or number in existing or _excluded(issue):
            continue
        result.append(make_leaf(issue, _kind(str(issue.get("body") or "")), repo, check))
    return sorted(result, key=lambda item: item.epic)


class Github:
    def __init__(self, token: str, repo: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise EpicError("Repositorio inválido")
        self.repo, self.token = repo, token

    def request(self, path: str, data: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/repos/") or ".." in path:
            raise EpicError("Ruta GitHub inválida")
        encoded = None if data is None else json.dumps(data).encode("utf-8")
        headers = {"Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(API + path, data=encoded, headers=headers,
                                     method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read(4_000_000))
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
            raise EpicError("API de GitHub no legible") from exc

    def read_all(self) -> list[dict[str, Any]]:
        result = []
        for page in range(1, 52):
            rows = self.request(f"/repos/{self.repo}/issues?state=all&per_page=100&page={page}")
            if not isinstance(rows, list):
                raise EpicError("Paginación ilegible")
            result.extend(rows)
            if len(result) > MAX_ISSUES:
                raise EpicError("Límite de issues excedido")
            if len(rows) < 100:
                return result
        raise EpicError("Listado truncado")

    def verify_switch(self) -> None:
        decision = evaluate_unattended_kill_switch(
            self.request("/repos/pl0n3r/Factory/issues/767")
        )
        if decision.global_pause or decision.state != "RUNNING":
            raise EpicError("Factory #767 no está acreditado RUNNING")

    def create(self, item: Proposal) -> int:
        data = self.request(f"/repos/{self.repo}/issues", {
            "title": item.title, "body": item.body,
            "labels": ["tipo: infraestructura", "prioridad: media",
                       "estado: disponible", "rol: ingenieria-software", "rol: qa"],
        })
        number = data.get("number") if isinstance(data, dict) else None
        if type(number) is not int or number < 1:
            raise EpicError("Creación no confirmada")
        return number


def run(api: Github, *, apply: bool, check: str, limit: int) -> list[dict[str, Any]]:
    if not 1 <= limit <= 25:
        raise EpicError("Límite fuera de rango")
    result = []
    for item in proposals(api.read_all(), api.repo, check)[:limit]:
        entry = {"epic": item.epic, "kind": item.kind, "status": "proposed"}
        if apply:
            api.verify_switch()
            current = {p.epic: p for p in proposals(api.read_all(), api.repo, check)}
            if item.epic not in current or current[item.epic].kind != item.kind:
                entry["status"] = "skipped_changed"
            else:
                entry["number"] = api.create(item)
                entry["status"] = "created"
        result.append(entry)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--acceptance-check", default="Tests de scripts")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not os.getenv("GH_TOKEN"):
        parser.error("GH_TOKEN requerido para --apply")
    try:
        items = run(Github(os.getenv("GH_TOKEN", ""), args.repo),
                    apply=args.apply, check=args.acceptance_check, limit=args.limit)
    except (EpicError, ValueError) as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, "apply": args.apply, "items": items}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
