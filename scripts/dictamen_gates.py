#!/usr/bin/env python3
"""Read-only exact-SHA GO/NO-GO verdict for Factory release candidates.

GO is *evidence*, not an instruction to publish or alter the Factory@v1 tag.
Every required check must have an exact-SHA, completed/success latest run.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Callable
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

REPO = "pl0n3r/Factory"
CHECKS = ("Validar", "SonarCloud Code Analysis", "CodeQL")
ISSUERS = {
    "Validar": ("github-actions", 15368),
    "SonarCloud Code Analysis": ("sonarqubecloud", 12526),
    "CodeQL": ("github-advanced-security", 57789),
}
SHA = re.compile(r"^[0-9a-f]{40}$")
API = "https://api.github.com"
PAGE_SIZE = 100
MAX_PAGES = 10
COLOMBIA = ZoneInfo("America/Bogota")


class EvidenceError(ValueError):
    """The provided API evidence cannot support a GO decision."""


def _now() -> str:
    return datetime.now(COLOMBIA).strftime("%Y-%m-%d %I:%M:%S %p %Z")


def _get_json(path: str) -> dict[str, Any]:
    """GET a constrained Factory check-run endpoint; never perform mutations."""
    if not re.fullmatch(
        r"/repos/pl0n3r/Factory/commits/[a-f0-9]{40}/check-runs\?per_page=100&page=(?:[1-9]|10)",
        path,
    ):
        raise EvidenceError("ruta GitHub no autorizada")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "factory-dictamen-gates/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # A private token, when available to the operator/CI, never enters output.
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urlopen(Request(API + path, headers=headers, method="GET"), timeout=15) as response:
            if response.status != 200:
                raise EvidenceError("API GitHub no disponible")
            data = response.read(2_000_001)
    except OSError as exc:
        raise EvidenceError("no se pudo consultar API GitHub") from exc
    if len(data) > 2_000_000:
        raise EvidenceError("respuesta GitHub demasiado grande")
    try:
        result = json.loads(data, object_pairs_hook=_unique_fields)
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError("JSON GitHub no verificable") from exc
    if type(result) is not dict:
        raise EvidenceError("formato GitHub inválido")
    return result


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in pairs:
        if key in fields:
            raise EvidenceError("JSON con claves duplicadas")
        fields[key] = value
    return fields


def _page_rows(payload: Any, expected_total: int | None, collected: int) -> tuple[int, list[Any]]:
    """Check the complete, stable, bounded GitHub checks page before using it."""
    if type(payload) is not dict or type(payload.get("total_count")) is not int:
        raise EvidenceError("paginación GitHub inválida")
    total = payload["total_count"]
    rows = payload.get("check_runs")
    if total < 0 or total > MAX_PAGES * PAGE_SIZE or type(rows) is not list:
        raise EvidenceError("resultados GitHub no verificables")
    if expected_total is not None and total != expected_total:
        raise EvidenceError("páginas incompletas o inconsistentes")
    if len(rows) != min(PAGE_SIZE, total - collected):
        raise EvidenceError("páginas incompletas o inconsistentes")
    return total, rows


def _append_page(rows: list[Any], ids: set[int], all_runs: list[dict[str, Any]]) -> None:
    """Reject invalid or duplicate run IDs across all pages."""
    for row in rows:
        if type(row) is not dict or type(row.get("id")) is not int or row["id"] <= 0:
            raise EvidenceError("check-run inválido")
        if row["id"] in ids:
            raise EvidenceError("check-run duplicado")
        ids.add(row["id"])
        all_runs.append(row)


def collect(sha: str, get_json: Callable[[str], Any] = _get_json) -> list[dict[str, Any]]:
    if type(sha) is not str or SHA.fullmatch(sha) is None:
        raise EvidenceError("SHA candidato inválido")
    all_runs: list[dict[str, Any]] = []
    expected_total: int | None = None
    ids: set[int] = set()
    for page in range(1, MAX_PAGES + 1):
        payload = get_json(f"/repos/{REPO}/commits/{sha}/check-runs?per_page={PAGE_SIZE}&page={page}")
        total, rows = _page_rows(payload, expected_total, len(all_runs))
        expected_total = total
        _append_page(rows, ids, all_runs)
        if len(all_runs) == total:
            return all_runs
    raise EvidenceError("inventario de checks incompleto")

def _run_problem(row: Any, sha: str, ids: set[int]) -> str | None:
    """Return a fail-closed reason for malformed, cross-SHA or forged checks."""
    if type(row) is not dict or type(row.get("id")) is not int or row["id"] <= 0:
        return "check_malformado"
    if row["id"] in ids:
        return "check_duplicado"
    ids.add(row["id"])
    name = row.get("name")
    if type(name) is not str or type(row.get("head_sha")) is not str or row["head_sha"] != sha:
        return "check_sin_SHA_exacto"
    if name in CHECKS:
        app = row.get("app")
        if type(app) is not dict or (app.get("slug"), app.get("id")) != ISSUERS[name]:
            return "check_emisor_no_confiable"
    return None


def evaluate(sha: str, runs: Any, checked_at: str | None = None) -> dict[str, Any]:
    """Select latest run per required check; any ambiguity must become NO-GO."""
    stamp = checked_at if checked_at is not None else _now()
    details: dict[str, dict[str, Any]] = {}
    result: dict[str, Any] = {
        "status": "NO-GO", "candidate_sha": sha, "checked_at_colombia": stamp,
        "checks": details, "authorizes_release": False,
    }
    if type(sha) is not str or SHA.fullmatch(sha) is None or type(runs) is not list:
        result["reason"] = "evidencia_inválida"
        return result
    latest: dict[str, dict[str, Any]] = {}
    ids: set[int] = set()
    for row in runs:
        problem = _run_problem(row, sha, ids)
        if problem:
            result["reason"] = problem
            return result
        name = row["name"]
        if name in CHECKS and (name not in latest or row["id"] > latest[name]["id"]):
            latest[name] = row
    for name in CHECKS:
        entry = latest.get(name)
        details[name] = {
            "status": entry.get("status") if entry else "missing",
            "conclusion": entry.get("conclusion") if entry else None,
            "head_sha": entry.get("head_sha") if entry else None,
        }
    if all(x["status"] == "completed" and x["conclusion"] == "success" for x in details.values()):
        result["status"] = "GO"
        result["reason"] = "checks_exact_SHA_terminal_success"
    else:
        result["reason"] = "check_pendiente_cancelado_omitido_fallido_o_ausente"
    return result

def verdict(sha: str, get_json: Callable[[str], Any] = _get_json) -> dict[str, Any]:
    try:
        return evaluate(sha, collect(sha, get_json))
    except EvidenceError:
        return {
            "status": "NO-GO", "candidate_sha": sha, "checked_at_colombia": _now(),
            "checks": {}, "reason": "evidencia_GitHub_no_verificable", "authorizes_release": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dictamen solo-lectura de puertas exact-SHA de Factory")
    parser.add_argument("--sha", required=True, help="SHA exacto de 40 caracteres del candidato")
    args = parser.parse_args(argv)
    report = verdict(args.sha)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
