#!/usr/bin/env python3
"""Aviso Factory #1532/A: solo cola canónica completa, sin mutar consumidores."""
from __future__ import annotations

import json
import os
import re
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

from scripts.salud_cola import REPOSITORIES
from scripts.salud_cola_observar import STATE_LABELS
from scripts.salud_cola_publicar import preparar_publicacion
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch

FACTORY = "pl0n3r/Factory"
BOT_MARKER = "<!-- factory-queue-alert "
ALERT_MARKER = re.compile(r'^<!-- factory-queue-alert \{"fingerprint":"([0-9a-f]{64})","version":1\} -->\n')
PAGE_SIZE = 100
MAX_PAGES = 24
MAX_RESPONSE_BYTES = 1048576
ALERT_TITLE = "[AUTO] Aviso de cola sin hojas disponibles (Factory)"
ALERT_LABELS = ["tipo: mejora", "prioridad: media", "estado: bloqueado", "rol: infraestructura"]
ALERT_LOOKUP_LABELS = quote(",".join((ALERT_LABELS[0], ALERT_LABELS[-1])), safe="")


class AlertError(ValueError):
    """Fuente ausente, no verificable, stale o sin autorización: cero escrituras."""


def _quota(api):
    value = api.get("/rate_limit")
    if not isinstance(value, dict):
        raise AlertError("quota_unknown")
    resources = value.get("resources")
    if not isinstance(resources, dict):
        raise AlertError("quota_unknown")
    core = resources.get("core")
    if not isinstance(core, dict):
        raise AlertError("quota_unknown")
    limit, remaining = core.get("limit"), core.get("remaining")
    if (type(limit) is not int or type(remaining) is not int or limit <= 0
            or remaining < 0 or remaining > limit):
        raise AlertError("quota_invalid")
    if remaining * 5 < limit or (limit >= 5000 and remaining < 1200):
        raise AlertError("low_quota")
    return {"limit": limit, "remaining": remaining}


def _pages(api, repo, *, state="open", only_alerts=False):
    if repo != FACTORY and state != "open":
        raise AlertError("foreign_history_forbidden")
    if only_alerts != (repo == FACTORY and state == "all"):
        raise AlertError("unfiltered_alert_history_forbidden")
    label_query = f"&labels={ALERT_LOOKUP_LABELS}" if only_alerts else ""
    for page in range(1, MAX_PAGES + 1):
        path = (f"/repos/{repo}/issues?state={state}{label_query}&per_page={PAGE_SIZE}"
                f"&page={page}")
        items = api.get(path)
        if type(items) is not list or len(items) > PAGE_SIZE:
            raise AlertError("invalid_page")
        yield items
        if len(items) < PAGE_SIZE:
            return
    raise AlertError("pagination_incomplete")


def _count_issue(item, seen, counts, blockers):
    """Clasificar exclusivamente un Issue con exactamente un estado canónico."""
    if type(item) is not dict:
        raise AlertError("invalid_issue")
    if "pull_request" in item:
        return
    number, labels = item.get("number"), item.get("labels")
    if (type(number) is not int or number <= 0 or number in seen
            or type(labels) is not list
            or any(type(x) is not dict or type(x.get("name")) is not str
                   for x in labels)):
        raise AlertError("invalid_issue")
    statuses = [STATE_LABELS[x["name"]] for x in labels
                if x["name"] in STATE_LABELS]
    if len(statuses) != 1:
        raise AlertError("unclassified_issue")
    seen.add(number)
    status = statuses[0]
    counts[status] += 1
    if status == "blocked":
        # Jamás inferir dependencias ejecutables desde texto libre.
        blockers.append({"number": number, "cause": "unknown", "roadmap": False})


def _inventory(api):
    budget = _quota(api)
    rows = []
    for name in REPOSITORIES:
        repo = "pl0n3r/" + name
        meta = api.get("/repos/" + repo)
        if (type(meta) is not dict or meta.get("full_name") != repo
                or meta.get("private") is not False or meta.get("archived") is True):
            raise AlertError("repository_identity_unknown")
        counts = dict.fromkeys(STATE_LABELS.values(), 0)
        seen = set()
        blockers = []
        for items in _pages(api, repo):
            for item in items:
                _count_issue(item, seen, counts, blockers)
        rows.append({"name": name, "complete": True,
                     "open_issues": len(seen), "counts": counts,
                     "blockers": sorted(blockers, key=lambda x: x["number"])})
    _quota(api)  # Evitar publicar justo después de agotar el presupuesto.
    return ({"version": 1, "repositories": rows, "agent_capacity": None,
             "rate_limit": budget},
            {"authenticated": True, "repository_scope": list(REPOSITORIES),
             "identities_verified": True, "pagination_complete": True,
             "checks_complete": True})


def _parse_alert(item):
    """Solo reutilizar avisos con marcador válido y autor bot auténtico."""
    if type(item) is not dict:
        raise AlertError("invalid_alert_page")
    if "pull_request" in item:
        return None
    body = item.get("body")
    if not isinstance(body, str) or not body.startswith(BOT_MARKER):
        return None
    author = item.get("user")
    if (type(author) is not dict or author.get("login") != "github-actions[bot]"
            or author.get("type") != "Bot"):
        raise AlertError("untrusted_alert_author")
    if (not ALERT_MARKER.match(body) or type(item.get("number")) is not int
            or item.get("state") not in ("open", "closed")):
        raise AlertError("alert_marker_invalid")
    return {"number": item["number"], "state": item["state"], "body": body}


def _existing(api):
    alerts = []
    for page in _pages(api, FACTORY, state="all", only_alerts=True):
        for item in page:
            found = _parse_alert(item)
            if found is not None:
                alerts.append(found)
                if len(alerts) > 1:
                    raise AlertError("duplicate_alerts")
    return alerts


def _kill_is_running(api):
    """Reutilizar el parser canónico: origen exacto, claves únicas y un marker."""
    decision = evaluate_unattended_kill_switch(
        api.get("/repos/pl0n3r/Factory/issues/767")
    )
    if decision.global_pause is not False or decision.state != "RUNNING":
        raise AlertError("global_switch_unknown")


def _body(fingerprint, proposal):
    # Los únicos datos remotos publicados son conteos agregados tipados.
    safe = {key: proposal[key] for key in
            ("state", "reason", "open_total", "available_total", "candidate_count")}
    if (safe["state"] != "queue_empty"
            or any(type(safe[key]) is not int for key in
                   ("open_total", "available_total", "candidate_count"))
            or safe["available_total"] != 0):
        raise AlertError("invalid_proposal")
    return (BOT_MARKER + json.dumps({"fingerprint": fingerprint, "version": 1},
                                   sort_keys=True, separators=(",", ":"))
            + " -->\n\nAviso interno de cola; no es un incidente de producción ni "
            "autoriza reservas, despliegue o live.\n\n"
            + json.dumps(safe, sort_keys=True, ensure_ascii=True)
            + "\n\nOrigen: inventario GET autenticado de siete repositorios; "
            "sin nombres de usuarios, cuerpos de Issues ni datos personales.\n")


def _skip(reason):
    return {"status": "SKIPPED", "reason": reason, "writes": 0}


def _publish_notice(api, candidates, body):
    if candidates:
        found = candidates[0]
        if found["state"] != "open":
            return _skip("owner_closed_alert")
        if found["body"] == body:
            return _skip("unchanged_alert")
        live = api.get(f"/repos/{FACTORY}/issues/{found['number']}")
        if (type(live) is not dict or live.get("state") != "open"
                or live.get("body") != found["body"]):
            raise AlertError("stale_existing_alert")
        api.write("PATCH", f"/repos/{FACTORY}/issues/{found['number']}",
                  {"body": body})
        return {"status": "UPDATED", "writes": 1, "number": found["number"]}
    created = api.write("POST", f"/repos/{FACTORY}/issues",
                        {"title": ALERT_TITLE, "body": body,
                         "labels": list(ALERT_LABELS)})
    if (type(created) is not dict or type(created.get("number")) is not int):
        raise AlertError("write_receipt_missing")
    return {"status": "CREATED", "writes": 1, "number": created["number"]}


def ejecutar(api, *, enabled=False):
    """Único efecto máximo, Factory-only; pruebas inyectan cliente sin red."""
    if enabled is not True:
        return _skip("disabled_by_default")
    try:
        first = preparar_publicacion(*_inventory(api))
        if first.get("status") != "DRY_RUN":
            return _skip(first.get("reason", "unverified_inventory"))
        candidates = _existing(api)
        second = preparar_publicacion(*_inventory(api))
        if (second.get("status") != "DRY_RUN"
                or second.get("fingerprint") != first.get("fingerprint")):
            raise AlertError("stale_inventory")
        if candidates != _existing(api):
            raise AlertError("stale_alert_index")
        _kill_is_running(api)
        body = _body(second["fingerprint"], second["proposal"])
        return _publish_notice(api, candidates, body)
    except (ValueError, TypeError, KeyError, OSError):
        return _skip("unverified_or_stale_evidence")


class GitHubAPI:
    """Allowlist estricta: nunca POST/PATCH a consumidor ni DELETE."""
    def __init__(self, token):
        if not token or type(token) is not str:
            raise AlertError("token_unavailable")
        self.token = token

    def request(self, method, path, payload=None):
        allowed_read = (path == "/rate_limit"
                        or re.fullmatch(r"/repos/pl0n3r/(Factory|Condor|GrindFlow|brvtal|ControlBot|AutoFactory|FactoryRunner)", path)
                        or re.fullmatch(r"/repos/pl0n3r/(Factory|Condor|GrindFlow|brvtal|ControlBot|AutoFactory|FactoryRunner)/issues\?state=open&per_page=100&page=([1-9]|1\d|2[0-4])", path)
                        or re.fullmatch(rf"/repos/pl0n3r/Factory/issues\?state=all&labels={ALERT_LOOKUP_LABELS}&per_page=100&page=([1-9]|1\d|2[0-4])", path)
                        or re.fullmatch(r"/repos/pl0n3r/Factory/issues/[1-9]\d*", path))
        allowed_write = ((method == "POST" and path == "/repos/pl0n3r/Factory/issues")
                         or (method == "PATCH" and bool(re.fullmatch(
                             r"/repos/pl0n3r/Factory/issues/[1-9]\d*", path))))
        if not ((method == "GET" and allowed_read and payload is None)
                or (allowed_write and type(payload) is dict)):
            raise AlertError("endpoint_forbidden")
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request("https://api.github.com" + path, data=data, method=method,
                      headers={"Authorization": "Bearer " + self.token,
                               "Accept": "application/vnd.github+json",
                               "Content-Type": "application/json",
                               "User-Agent": "factory-queue-alert",
                               "X-GitHub-Api-Version": "2022-11-28"})
        with urlopen(req, timeout=15) as res:
            if res.status not in ((200, 201) if method != "GET" else (200,)):
                raise AlertError("api_status_unexpected")
            raw = res.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AlertError("response_oversized")
        return json.loads(raw.decode("utf-8"))

    def get(self, path):
        return self.request("GET", path)

    def write(self, method, path, payload):
        return self.request(method, path, payload)


def main():
    enabled = (os.environ.get("GITHUB_REPOSITORY") == FACTORY
               and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
               and os.environ.get("FACTORY_QUEUE_ALERT_ENABLED") == "true")
    if not enabled:
        result = _skip("disabled_by_default")
    else:
        try:
            result = ejecutar(GitHubAPI(os.environ.get("GITHUB_TOKEN")),
                              enabled=True)
        except (OSError, ValueError):
            result = _skip("unverified_or_stale_evidence")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
