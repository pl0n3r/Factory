#!/usr/bin/env python3
"""Smoke post-Factory@v1 de solo lectura: CI exact-main y health, o NO-GO."""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

PRODUCTOS = (
    "pl0n3r/Condor", "pl0n3r/GrindFlow", "pl0n3r/brvtal",
    "pl0n3r/ControlBot", "pl0n3r/AutoFactory", "pl0n3r/FactoryRunner",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
SEMVER = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
MAX_BYTES = 512 * 1024


def github_get(path: str) -> dict[str, Any]:
    """Solo rutas generadas internamente desde PRODUCTOS (nunca URLs externas)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Factory-Smoke/1"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request("https://api.github.com" + path, headers=headers)
    try:
        with urlopen(request, timeout=8) as response:
            content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("github_response_too_large")
        data = json.loads(content)
    except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("github_evidence_unavailable") from exc
    if not isinstance(data, dict):
        raise ValueError("github_payload_invalid")
    return data


def _index_inventory(inventory: Any) -> dict[str, dict[str, Any]] | None:
    if not isinstance(inventory, dict) or set(inventory) != {"products"}:
        return None
    entries = inventory["products"]
    if not isinstance(entries, list) or len(entries) != len(PRODUCTOS):
        return None
    indexed: dict[str, dict[str, Any]] = {}
    for row in entries:
        if not isinstance(row, dict) or set(row) != {"repository", "phase", "origin", "version"}:
            return None
        name = row["repository"]
        if not isinstance(name, str) or name not in PRODUCTOS or name in indexed:
            return None
        indexed[name] = row
    return indexed if set(indexed) == set(PRODUCTOS) else None


def _main_sha(prefix: str, fetch: Callable[[str], dict[str, Any]]) -> str:
    ref = fetch(prefix + "/git/ref/heads/main")
    obj = ref.get("object")
    sha = obj.get("sha") if isinstance(obj, dict) else None
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("main_sha_missing")
    return sha


def _verified_ci(name: str, fetch: Callable[[str], dict[str, Any]]) -> tuple[str, str]:
    owner, repository = name.split("/", 1)
    prefix = f"/repos/{owner}/{repository}"
    metadata = fetch(prefix)
    if (metadata.get("full_name") != name or metadata.get("default_branch") != "main"
            or metadata.get("archived") is True):
        raise ValueError("repository_identity_unknown")
    sha = _main_sha(prefix, fetch)
    checks = fetch(prefix + "/commits/" + sha + "/check-runs?per_page=100")
    runs = checks.get("check_runs")
    if (not isinstance(runs, list) or type(checks.get("total_count")) is not int
            or checks["total_count"] != len(runs)):
        raise ValueError("checks_incomplete")
    candidates = [run for run in runs if isinstance(run, dict) and run.get("name") == "Validar"]
    if not candidates or not all(type(run.get("id")) is int for run in candidates):
        raise ValueError("canonical_ci_missing")
    latest = max(candidates, key=lambda run: run["id"])
    if (latest.get("head_sha") != sha or latest.get("status") != "completed"
            or latest.get("conclusion") != "success"
            or not isinstance(latest.get("app"), dict)
            or latest["app"].get("slug") != "github-actions"):
        raise ValueError("canonical_ci_not_green")
    return prefix, sha


def _one_product(
    name: str, row: dict[str, Any],
    fetch: Callable[[str], dict[str, Any]],
    health: Callable[..., dict[str, Any]],
) -> dict[str, str]:
    result = {"repository": name, "ci": "UNKNOWN", "health": "UNKNOWN", "status": "NO-GO"}
    phase = row["phase"]
    if phase not in ("construccion", "live"):
        return {**result, "reason": "phase_unknown"}
    if phase == "construccion":
        if row["origin"] is not None or row["version"] is not None:
            return {**result, "reason": "prelive_metadata_inconsistent"}
        result["health"] = "NO_APLICA"
    elif (not isinstance(row["origin"], str) or not isinstance(row["version"], str)
          or not SEMVER.fullmatch(row["version"])):
        return {**result, "reason": "live_evidence_missing"}
    try:
        prefix, sha = _verified_ci(name, fetch)
        result["ci"] = "success"
        if phase == "live":
            health(row["origin"], "/health", row["version"], sha, require_schema=False)
            result["health"] = "success"
        if _main_sha(prefix, fetch) != sha:
            raise ValueError("main_moved")
        result["status"] = "GO"
    except (ValueError, KeyError, TypeError, AttributeError, OSError, RuntimeError):
        result["status"] = "NO-GO"
        result["reason"] = "evidence_unverified"
    return result


def evaluate(
    inventory: Any, *,
    fetch: Callable[[str], dict[str, Any]] = github_get,
    health: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Una omisión, evidencia parcial o cambio de identidad produce NO-GO."""
    if health is None:
        from scripts.runtime_health import check_health
        health = check_health
    indexed = _index_inventory(inventory)
    if indexed is None:
        return {"decision": "NO-GO", "reason": "inventory_incomplete_or_invalid", "products": []}
    products = [_one_product(name, indexed[name], fetch, health) for name in PRODUCTOS]
    return {"decision": "GO" if all(p["status"] == "GO" for p in products) else "NO-GO", "products": products}


def main(argv: list[str] | None = None) -> int:
    """Leer JSON únicamente de stdin: no aceptar rutas/URLs inyectadas por CLI."""
    if argv is None:
        argv = sys.argv[1:]
    try:
        if argv:
            raise ValueError("cli_arguments_not_allowed")
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("inventory_too_large")
        report = evaluate(json.loads(raw))
    except (OSError, ValueError):
        report = {"decision": "NO-GO", "reason": "inventory_unavailable", "products": []}
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["decision"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
