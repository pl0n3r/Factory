#!/usr/bin/env python3
"""Smoke post-Factory@v1 de solo lectura: evidencia exact-main o NO-GO."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PRODUCTOS = (
    "pl0n3r/Condor", "pl0n3r/GrindFlow", "pl0n3r/brvtal",
    "pl0n3r/ControlBot", "pl0n3r/AutoFactory", "pl0n3r/FactoryRunner",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
MAX_BYTES = 512 * 1024


def github_get(path: str) -> dict[str, Any]:
    """Solo rutas canónicas preconstruidas; nunca leer un URL del inventario."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Factory-Smoke/1"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request("https://api.github.com" + path, headers=headers)
    try:
        with urlopen(req, timeout=8) as response:
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ValueError("github_response_too_large")
            data = json.loads(content)
    except (HTTPError, URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("github_evidence_unavailable") from exc
    if not isinstance(data, dict):
        raise ValueError("github_payload_invalid")
    return data


def evaluate(
    inventory: Any,
    *,
    fetch: Callable[[str], dict[str, Any]] = github_get,
    health: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Toda omisión, error o identidad inestable bloquea la publicación."""
    if health is None:
        from scripts.runtime_health import check_health
        health = check_health
    entries = inventory.get("products") if isinstance(inventory, dict) and set(inventory) == {"products"} else None
    if not isinstance(entries, list) or len(entries) != len(PRODUCTOS):
        return {"decision": "NO-GO", "reason": "inventory_incomplete", "products": []}
    indexed: dict[str, dict[str, Any]] = {}
    for row in entries:
        if not isinstance(row, dict) or set(row) != {"repository", "phase", "origin", "version"}:
            return {"decision": "NO-GO", "reason": "inventory_invalid", "products": []}
        name = row.get("repository")
        if not isinstance(name, str) or name in indexed or name not in PRODUCTOS:
            return {"decision": "NO-GO", "reason": "inventory_invalid", "products": []}
        indexed[name] = row
    if set(indexed) != set(PRODUCTOS):
        return {"decision": "NO-GO", "reason": "inventory_incomplete", "products": []}
    outcomes = []
    for name in PRODUCTOS:
        row = indexed[name]
        result: dict[str, str] = {"repository": name, "ci": "UNKNOWN", "health": "UNKNOWN", "status": "NO-GO"}
        phase = row["phase"]
        if phase not in ("construccion", "live"):
            result["reason"] = "phase_unknown"
            outcomes.append(result)
            continue
        if phase == "construccion":
            if row["origin"] is not None or row["version"] is not None:
                result["reason"] = "prelive_metadata_inconsistent"
                outcomes.append(result)
                continue
            result["health"] = "NO_APLICA"
        elif (not isinstance(row["origin"], str) or not isinstance(row["version"], str)
              or not SEMVER.fullmatch(row["version"])):
            result["reason"] = "live_evidence_missing"
            outcomes.append(result)
            continue
        try:
            owner, repo = name.split("/", 1)
            prefix = f"/repos/{owner}/{repo}"
            metadata = fetch(prefix)
            if metadata.get("full_name") != name or metadata.get("default_branch") != "main" or metadata.get("archived") is True:
                raise ValueError("repository_identity_unknown")
            ref = fetch(prefix + "/git/ref/heads/main")
            sha = ref.get("object", {}).get("sha") if isinstance(ref.get("object"), dict) else None
            if not isinstance(sha, str) or not SHA.fullmatch(sha):
                raise ValueError("main_sha_missing")
            checks = fetch(prefix + "/commits/" + sha + "/check-runs?per_page=100")
            runs = checks.get("check_runs")
            if not isinstance(runs, list) or type(checks.get("total_count")) is not int or checks["total_count"] != len(runs):
                raise ValueError("checks_incomplete")
            candidates = [c for c in runs if isinstance(c, dict) and c.get("name") == "Validar"]
            if not candidates or not all(type(c.get("id")) is int for c in candidates):
                raise ValueError("canonical_ci_missing")
            latest = max(candidates, key=lambda x: x["id"])
            if (latest.get("head_sha") != sha or latest.get("status") != "completed"
                    or latest.get("conclusion") != "success" or
                    not isinstance(latest.get("app"), dict) or latest["app"].get("slug") != "github-actions"):
                raise ValueError("canonical_ci_not_green")
            result["ci"] = "success"
            if phase == "live":
                health(row["origin"], "/health", row["version"], sha, require_schema=False)
                result["health"] = "success"
            # Detectar movimiento de main durante la observación; no usar evidencia vieja.
            final_ref = fetch(prefix + "/git/ref/heads/main")
            if final_ref.get("object", {}).get("sha") != sha:
                raise ValueError("main_moved")
            result["status"] = "GO"
        except (ValueError, KeyError, TypeError, OSError, RuntimeError):
            result["status"] = "NO-GO"
            result["reason"] = "evidence_unverified"
        outcomes.append(result)
    return {"decision": "GO" if all(x["status"] == "GO" for x in outcomes) else "NO-GO", "products": outcomes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="JSON de fases explícitas por producto; no debe incluir secretos")
    args = parser.parse_args(argv)
    try:
        with Path(args.inventory).open("rb") as f:
            raw = f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("inventory_too_large")
        inventory = json.loads(raw)
        report = evaluate(inventory)
    except (OSError, ValueError, UnicodeError):
        report = {"decision": "NO-GO", "reason": "inventory_unavailable", "products": []}
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["decision"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
