#!/usr/bin/env python3
"""Observación de cola local: GET-only, bounded y sin autoridad de despacho."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen

REPO = "pl0n3r/Factory"
MAX_PAGES = 10
PAGE_SIZE = 100
MAX_RESPONSE_BYTES = 1024 * 1024
STATE_LABELS = {
    "estado: disponible": "available",
    "estado: reservado": "reserved",
    "estado: bloqueado": "blocked",
    "estado: planificado": "planned",
    "estado: en revisión": "in_review",
    "estado: requiere recuperación": "recovery_required",
}


class ObservationError(ValueError):
    """Evidencia inválida o incompleta: jamás convertir en saludable."""


def _low_quota(get_json):
    """Validar el presupuesto REST; nunca adivinar cuota si falta evidencia."""
    budget = get_json("/rate_limit")
    if not isinstance(budget, dict) or not isinstance(budget.get("resources"), dict):
        raise ObservationError("quota_unknown")
    core = budget["resources"].get("core")
    if not isinstance(core, dict):
        raise ObservationError("quota_unknown")
    limit, remaining = core.get("limit"), core.get("remaining")
    if (
        type(limit) is not int or type(remaining) is not int
        or limit <= 0 or remaining < 0 or remaining > limit
    ):
        raise ObservationError("quota_invalid")
    return remaining * 5 < limit


def _classify_issue(item, seen, counts):
    """Una fila de GitHub: PR se excluye; Issue inválido falla cerrado."""
    if not isinstance(item, dict):
        raise ObservationError("invalid_item")
    if "pull_request" in item:
        return "pr"
    number, labels = item.get("number"), item.get("labels")
    if (
        type(number) is not int or number <= 0 or number in seen
        or not isinstance(labels, list)
    ):
        raise ObservationError("invalid_or_duplicate_issue")
    seen.add(number)
    if any(not isinstance(x, dict) or not isinstance(x.get("name"), str) for x in labels):
        raise ObservationError("invalid_labels")
    active = [STATE_LABELS[x["name"]] for x in labels if x["name"] in STATE_LABELS]
    if len(active) != 1:
        return "unknown"
    counts[active[0]] += 1
    return "classified"


def _collect_page(items, seen, counts):
    """Validar página antes de acumular censos; nunca combinar estados dudosos."""
    if not isinstance(items, list) or len(items) > PAGE_SIZE:
        raise ObservationError("invalid_page")
    undecidable = 0
    excluded_prs = 0
    for item in items:
        result = _classify_issue(item, seen, counts)
        if result == "pr":
            excluded_prs += 1
        elif result == "unknown":
            undecidable += 1
    return undecidable, excluded_prs


def observe(get_json):
    """Obtener un único censo local con paginación y cuota verificadas."""
    if _low_quota(get_json):
        return {"status": "DEFERRED_LOW_QUOTA", "scope": REPO, "writes": 0}

    counts = dict.fromkeys(STATE_LABELS.values(), 0)
    seen = set()
    undecidable = 0
    excluded_prs = 0
    for page in range(1, MAX_PAGES + 1):
        items = get_json(
            f"/repos/{REPO}/issues?state=open&per_page={PAGE_SIZE}&page={page}"
        )
        page_unknown, page_prs = _collect_page(items, seen, counts)
        undecidable += page_unknown
        excluded_prs += page_prs
        if len(items) < PAGE_SIZE:
            return {
                "status": "UNKNOWN" if undecidable else "OBSERVED_LOCAL_ONLY",
                "scope": REPO,
                "counts": counts,
                "undecidable": undecidable,
                "excluded_prs": excluded_prs,
                "issues": len(seen),
                "pages": page,
                "writes": 0,
            }
    raise ObservationError("pagination_incomplete")

def github_get_json(path):
    """Solo dos familias GET internas; nunca acepta URL arbitraria."""
    if path != "/rate_limit" and not path.startswith(
        f"/repos/{REPO}/issues?state=open&per_page={PAGE_SIZE}&page="
    ):
        raise ObservationError("endpoint_forbidden")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise ObservationError("local_authority_missing")
    request = Request(
        "https://api.github.com" + path,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "factory-queue-health-observer",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise ObservationError("http_non_200")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ObservationError("payload_oversized")
    return json.loads(raw.decode("utf-8"))


def main() -> int:
    """Escribir únicamente stdout y summary local de Actions; cero API writes."""
    if sys.argv[1:] == ["--help"]:
        print("Uso: salud_cola_observar.py [--help] — observación local GET-only")
        return 0
    if sys.argv[1:]:
        print("Argumentos no reconocidos", file=sys.stderr)
        return 2
    try:
        outcome = observe(github_get_json)
    except (OSError, ValueError):
        outcome = {"status": "UNKNOWN", "scope": REPO, "writes": 0}
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(
                "### Factory queue — observación GET-only\n"
                + "\n`" + outcome["status"] + "` — No concede reservas, "
                + "no certifica salud global y no crea incidentes.\n"
            )
    return 2 if outcome["status"] == "UNKNOWN" else 0


if __name__ == "__main__":
    sys.exit(main())
