#!/usr/bin/env python3
"""Block Factory@v1 releases when a public consumer cannot grant the candidate permissions."""
from __future__ import annotations

import argparse
from http.client import HTTPException, HTTPSConnection
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

from scripts.reusable_permission_compat import compare_permissions

CONSUMERS = (
    "pl0n3r/Condor", "pl0n3r/ControlBot", "pl0n3r/FactoryRunner",
    "pl0n3r/GrindFlow", "pl0n3r/brvtal", "pl0n3r/AutoFactory",
)
SHA = re.compile(r"^[0-9a-f]{40}$")
WF = re.compile(r"^\.github/workflows/[A-Za-z0-9._-]+\.ya?ml$")
REF = re.compile(
    r"^pl0n3r/factory/\.github/workflows/([A-Za-z0-9._-]+\.ya?ml)@([^\s]+)$", re.I
)
API_HOST = "api.github.com"
RAW_HOST = "raw.githubusercontent.com"
RANK = {"none": 0, "read": 1, "write": 2}
USER_AGENT = "factory-release-preflight/1"


class PreflightError(ValueError):
    pass


def _github_json(path):
    connection = HTTPSConnection(API_HOST, timeout=20)
    try:
        connection.request(
            "GET",
            path,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise PreflightError("evidencia GitHub pública ilegible.")
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise PreflightError("evidencia GitHub pública demasiado grande.")
        return json.loads(raw)
    except (OSError, HTTPException, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError("evidencia GitHub pública ilegible.") from exc
    finally:
        connection.close()


def _github_bytes(path):
    connection = HTTPSConnection(RAW_HOST, timeout=20)
    try:
        connection.request("GET", path, headers={"User-Agent": USER_AGENT})
        response = connection.getresponse()
        if response.status != 200:
            raise PreflightError("workflow público ilegible.")
        return response.read(300_001)
    except (OSError, HTTPException) as exc:
        raise PreflightError("workflow público ilegible.") from exc
    finally:
        connection.close()

def _sha(value, label):
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise PreflightError(f"{label} inválido.")
    return value


def collect_inventory(get_json=_github_json, get_bytes=_github_bytes):
    inventory = []
    for repo in CONSUMERS:
        meta = get_json(f"/repos/{repo}")
        branch = meta.get("default_branch") if isinstance(meta, dict) else None
        if not isinstance(branch, str) or not branch:
            raise PreflightError(f"{repo}: default branch inválida.")
        branch_segment = quote(branch, safe="")
        head = f"/repos/{repo}/commits/{branch_segment}"
        first = _sha(get_json(head).get("sha"), f"{repo}.sha")
        tree = get_json(f"/repos/{repo}/git/trees/{first}?recursive=1")
        if not isinstance(tree, dict) or tree.get("truncated") is not False:
            raise PreflightError(f"{repo}: árbol truncado/ilegible.")
        rows = tree.get("tree")
        if not isinstance(rows, list):
            raise PreflightError(f"{repo}: árbol inválido.")
        workflows, seen = [], set()
        for item in rows:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if item.get("type") != "blob" or not isinstance(path, str) or WF.fullmatch(path) is None:
                continue
            if path in seen:
                raise PreflightError(f"{repo}: workflow ambiguo.")
            seen.add(path)
            blob = _sha(item.get("sha"), f"{repo}:{path}.blob")
            raw = get_bytes(f"/{repo}/{first}/{path}")
            if len(raw) > 300_000:
                raise PreflightError(f"{repo}:{path}: contenido demasiado grande.")
            try:
                text = raw.decode()
            except UnicodeDecodeError as exc:
                raise PreflightError(f"{repo}:{path}: no UTF-8.") from exc
            workflows.append({"path": path, "blob_sha": blob, "content": text})
        if _sha(get_json(head).get("sha"), f"{repo}.sha") != first:
            raise PreflightError(f"{repo}: evidencia stale.")
        inventory.append({"repository": repo, "repository_sha": first, "workflows": workflows})
    return inventory


def _indent(line, label):
    prefix = line[: len(line) - len(line.lstrip(" \t"))]
    if "\t" in prefix:
        raise PreflightError(f"{label}: tabs no soportados.")
    return len(prefix)


def _mapping(lines, start, indent, label):
    result = {}
    for raw in lines[start + 1:]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        current = _indent(raw, label)
        if current <= indent:
            break
        if current != indent + 2 or ":" not in raw.strip():
            raise PreflightError(f"{label}: permissions ambiguo.")
        scope, level = raw.strip().split(":", 1)
        level = level.split(" #", 1)[0].strip().strip("'\"")
        if scope in result or not level:
            raise PreflightError(f"{label}: permission inválido.")
        result[scope] = level
    return result


def _jobs(text, label):
    lines, top, jobs_at = text.splitlines(), None, None
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or _indent(raw, label) != 0:
            continue
        if stripped.startswith("permissions:"):
            if top is not None:
                raise PreflightError(f"{label}: permissions top-level inválido.")
            if stripped == "permissions:":
                top = _mapping(lines, i, 0, label)
            elif stripped == "permissions: {}":
                top = {}
            else:
                raise PreflightError(f"{label}: permissions top-level inválido.")
        elif stripped == "jobs:":
            if jobs_at is not None:
                raise PreflightError(f"{label}: jobs ambiguo.")
            jobs_at = i
    if jobs_at is None:
        raise PreflightError(f"{label}: falta jobs.")

    starts, section_end = [], len(lines)
    for i in range(jobs_at + 1, len(lines)):
        raw, stripped = lines[i], lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = _indent(raw, label)
        if indent == 0:
            section_end = i
            break
        if indent == 2 and re.fullmatch(r"[A-Za-z0-9_.-]+:", stripped):
            starts.append((stripped[:-1], i))
    if not starts:
        raise PreflightError(f"{label}: jobs vacío.")

    jobs = []
    for n, (name, start) in enumerate(starts):
        end = starts[n + 1][1] if n + 1 < len(starts) else section_end
        uses, permissions = None, None
        for i in range(start + 1, end):
            raw, stripped = lines[i], lines[i].strip()
            if not stripped or stripped.startswith("#") or _indent(raw, label) != 4:
                continue
            if stripped.startswith("uses:"):
                if uses is not None:
                    raise PreflightError(f"{label}:{name}: uses ambiguo.")
                uses = stripped[5:].strip().strip("'\"")
            elif stripped.startswith("permissions:"):
                if permissions is not None:
                    raise PreflightError(f"{label}:{name}: permissions inválido.")
                if stripped == "permissions:":
                    permissions = _mapping(lines, i, 4, label)
                elif stripped == "permissions: {}":
                    permissions = {}
                else:
                    raise PreflightError(f"{label}:{name}: permissions inválido.")
        jobs.append((
            name,
            uses,
            (dict(top) if top is not None else {}) if permissions is None else permissions,
        ))
    return jobs


def _required(text, label):
    envelope = {}
    for _, _, permissions in _jobs(text, label):
        if compare_permissions(permissions, permissions)["reason"] == "invalid_contract":
            raise PreflightError(f"{label}: permission scope/level desconocido.")
        for scope, level in permissions.items():
            if RANK[level] > RANK.get(envelope.get(scope, "none"), 0):
                envelope[scope] = level
    return envelope


def evaluate_inventory(inventory, factory_sha, root=None):
    _sha(factory_sha, "factory_sha")
    if not isinstance(inventory, list) or len(inventory) != len(CONSUMERS):
        raise PreflightError("inventario de consumidores incompleto.")
    by_repo = {}
    for row in inventory:
        if not isinstance(row, dict) or set(row) != {"repository", "repository_sha", "workflows"}:
            raise PreflightError("consumer fuera del contrato.")
        repo = row["repository"]
        if repo not in CONSUMERS or repo in by_repo:
            raise PreflightError("consumer desconocido/duplicado.")
        _sha(row["repository_sha"], f"{repo}.repository_sha")
        if not isinstance(row["workflows"], list) or not row["workflows"]:
            raise PreflightError(f"{repo}: workflows ausentes.")
        by_repo[repo] = row
    if set(by_repo) != set(CONSUMERS):
        raise PreflightError("inventario de consumidores incompleto.")

    calls = []
    consumer_summaries = []
    for repo in CONSUMERS:
        repo_call_start = len(calls)
        seen = set()
        for wf in by_repo[repo]["workflows"]:
            if not isinstance(wf, dict) or set(wf) != {"path", "blob_sha", "content"}:
                raise PreflightError(f"{repo}: workflow fuera del contrato.")
            path = wf["path"]
            if not isinstance(path, str) or WF.fullmatch(path) is None or path in seen:
                raise PreflightError(f"{repo}: workflow path ambiguo.")
            seen.add(path)
            _sha(wf["blob_sha"], f"{repo}:{path}.blob_sha")
            if not isinstance(wf["content"], str):
                raise PreflightError(f"{repo}:{path}: contenido inválido.")
            marker = "pl0n3r/factory/.github/workflows/"
            if marker not in wf["content"].lower():
                continue
            for job, uses, granted in _jobs(wf["content"], f"{repo}:{path}"):
                match = REF.fullmatch(uses or "")
                if match:
                    reference = match.group(2)
                    if "${{" in reference or "}}" in reference:
                        raise PreflightError(
                            f"{repo}:{path}:{job}: referencia Factory ambigua."
                        )
                    if reference.lower() != "v1":
                        continue
                    calls.append((repo, path, job, uses, match.group(1), granted))
                elif isinstance(uses, str) and uses.lower().startswith(marker):
                    raise PreflightError(
                        f"{repo}:{path}:{job}: referencia Factory ambigua."
                    )
        repo_call_count = len(calls) - repo_call_start
        if repo_call_count == 0:
            raise PreflightError(f"{repo}: sin caller Factory@v1 verificable.")
        consumer_summaries.append({
            "repository": repo,
            "sha": by_repo[repo]["repository_sha"],
            "workflows": len(by_repo[repo]["workflows"]),
            "callers": repo_call_count,
        })

    base, cache, incompatible = root or Path(__file__).resolve().parents[1], {}, []
    for repo, path, job, uses, filename, granted in calls:
        candidate = f".github/workflows/{filename}"
        if candidate not in cache:
            try:
                cache[candidate] = _required((base / candidate).read_text(), f"factory:{candidate}")
            except (OSError, UnicodeError) as exc:
                raise PreflightError(f"reusable candidato ilegible: {candidate}.") from exc
        result = compare_permissions(cache[candidate], granted)
        if result["reason"] == "invalid_contract":
            raise PreflightError(f"{repo}:{path}:{job}: permission envelope inválido.")
        for gap in result["missing"]:
            incompatible.append({
                "repository": repo, "workflow": path, "job": job, "reusable": uses, **gap
            })
    incompatible.sort(key=lambda row: json.dumps(row, sort_keys=True))
    return {
        "version": 1, "status": "COMPATIBLE" if not incompatible else "INCOMPATIBLE",
        "compatible": not incompatible, "factory_sha": factory_sha,
        "consumer_count": len(by_repo), "caller_count": len(calls),
        "reusables": sorted(cache), "consumers": consumer_summaries,
        "incompatible": incompatible,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-sha", required=True)
    args = parser.parse_args()
    try:
        result = evaluate_inventory(collect_inventory(), args.factory_sha)
    except PreflightError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
