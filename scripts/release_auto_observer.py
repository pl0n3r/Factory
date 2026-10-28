#!/usr/bin/env python3
"""Observación MANUAL de evidencia de release sin autoridad de publicación.

Los datos se leen de rutas REST de solo lectura con el GITHUB_TOKEN del job.
Ni los recibos de GitHub ni un REVIEW_ONLY permiten mover Factory@v1.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from typing import Any

from scripts.release_auto_policy import evaluate as evaluate_policy

REPO = "pl0n3r/Factory"
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
NUMBER_RE = re.compile(r"[1-9][0-9]{0,7}\Z")
REQUIRED = ("Validar", "SonarCloud Code Analysis", "CodeQL")


def _denied(reason: str) -> dict[str, Any]:
    return {
        "state": "BLOCKED", "reason": reason, "repository": REPO,
        "authorizes_release": False, "mutations": 0, "tag_writes": 0,
    }


def _sha(value: object) -> bool:
    return type(value) is str and SHA_RE.fullmatch(value) is not None


def _marker(body: object, name: str) -> dict[str, Any] | None:
    if type(body) is not str:
        return None
    matches = re.findall(r"<!--\s*" + re.escape(name) + r"\s+(\{[^\n<>]*\})\s*-->", body)
    if len(matches) != 1:
        return None
    try:
        obj = json.loads(matches[0])
        return obj if type(obj) is dict else None
    except (TypeError, ValueError):
        return None


def _latest_checks(bundle: dict, sha: str) -> list[dict] | None:
    pages = bundle.get("checks")
    if type(pages) is not list or not pages or len(pages) > 4:
        return None
    rows: list[dict] = []
    total: int | None = None
    for page in pages:
        if type(page) is not dict or type(page.get("check_runs")) is not list:
            return None
        if type(page.get("total_count")) is not int:
            return None
        if total is None:
            total = page["total_count"]
        if total != page["total_count"]:
            return None
        rows.extend(page["check_runs"])
    if total is None or total > len(rows) or total < 0:
        return None
    latest: dict[str, dict] = {}
    for row in rows:
        if type(row) is not dict or type(row.get("name")) is not str:
            return None
        name = row["name"]
        canonical = "CodeQL" if name.startswith("CodeQL") else name
        if canonical not in REQUIRED:
            continue
        if type(row.get("id")) is not int or not _sha(row.get("head_sha")):
            return None
        if canonical not in latest or row["id"] > latest[canonical]["id"]:
            latest[canonical] = row
    if set(latest) != set(REQUIRED):
        return None
    return [
        {"name": name, "head_sha": row["head_sha"],
         "status": row.get("status"), "conclusion": row.get("conclusion"),
         "authenticated": row["head_sha"] == sha}
        for name in REQUIRED for row in [latest[name]]
    ]


def evaluate_bundle(bundle: object) -> dict[str, Any]:
    """Reducir respuestas originales de REST a un reporte corto, sin efectos."""
    if type(bundle) is not dict or set(bundle) != {
        "repository", "checkout_sha", "main", "tag", "gate",
        "comments", "switch", "rate", "checks",
    }:
        return _denied("evidence_missing")
    if bundle["repository"] != REPO or not _sha(bundle["checkout_sha"]):
        return _denied("repository_or_checkout_invalid")
    main, tag = bundle["main"], bundle["tag"]
    if (type(main) is not dict or main.get("name") != "main"
            or main.get("protected") is not True
            or type(main.get("commit")) is not dict
            or not _sha(main["commit"].get("sha"))
            or main["commit"]["sha"] != bundle["checkout_sha"]):
        return _denied("main_sha_unverified")
    ref = tag.get("object") if type(tag) is dict else None
    if (type(tag) is not dict or tag.get("ref") != "refs/tags/v1"
            or type(ref) is not dict or ref.get("type") != "commit"
            or not _sha(ref.get("sha"))):
        return _denied("v1_ref_unverified")
    rate = bundle["rate"]
    core = rate.get("resources", {}).get("core") if type(rate) is dict else None
    if (type(core) is not dict or type(core.get("remaining")) is not int
            or type(core.get("limit")) is not int or core["limit"] <= 0
            or not 100 <= core["remaining"] <= core["limit"]):
        return _denied("api_budget_unknown_or_low")
    switch = bundle["switch"]
    if (type(switch) is not dict or switch.get("number") != 767
            or switch.get("state") != "closed"
            or type(switch.get("user")) is not dict
            or switch["user"].get("login") != "pl0n3r"
            or (_marker(switch.get("body"), "factory-unattended-kill-switch")
                != {"version": 1, "state": "RUNNING", "owner": "pl0n3r"})):
        return _denied("global_switch_unverified")
    gate = bundle["gate"]
    if type(gate) is not dict or gate.get("state") != "closed":
        return _denied("release_gate_not_closed")
    human = _marker(gate.get("body"), "factory-human-gate")
    window = _marker(gate.get("body"), "factory-release-window")
    if (type(human) is not dict or human.get("category") != "factory-release"
            or type(window) is not dict
            or window.get("sha") != bundle["checkout_sha"]):
        return _denied("release_gate_wrong_sha")
    comments = bundle["comments"]
    if type(comments) is not list or len(comments) >= 100:
        return _denied("gate_comments_incomplete")
    owner_vote = any(
        type(c) is dict and c.get("author_association") == "OWNER"
        and (c.get("body") or "").strip() == "/decidir A"
        and type(c.get("user")) is dict and c["user"].get("login") == "pl0n3r"
        for c in comments
    )
    journal = any(
        type(c) is dict and type(c.get("user")) is dict
        and c["user"].get("login") == "github-actions[bot]"
        and (j := _marker(c.get("body"), "factory-human-decision")) is not None
        and j.get("option") == "A" and j.get("version") == 2
        and type(j.get("gate_sha256")) is str
        and re.fullmatch(r"[0-9a-f]{64}", j["gate_sha256"])
        for c in comments
    )
    if not owner_vote or not journal:
        return _denied("human_release_authority_unverified")
    checks = _latest_checks(bundle, bundle["checkout_sha"])
    if checks is None:
        return _denied("check_evidence_missing_or_incomplete")
    # El snapshot no acredita por sí mismo ausencia de hallazgos graves,
    # freeze global ni ejecución exacta; UNKNOWN bloquea deliberadamente.
    policy = {
        "candidate_sha": bundle["checkout_sha"],
        "observed_main_sha": main["commit"]["sha"],
        "published_v1_sha": ref["sha"],
        "v1_tag_protected": None, "evidence_authenticated": True,
        "kill_switch_state": "RUNNING", "freeze_active": None,
        "security_veto": None, "owner_decision": {
            "option": "A", "candidate_sha": bundle["checkout_sha"],
            "category": "factory-release", "journal_verified": True,
            "owner": "pl0n3r",
        }, "checks": checks,
    }
    result = evaluate_policy(policy)
    return _denied("security_freeze_or_protected_tag_not_attested"
                   if result["state"] == "BLOCKED" else "review_only_no_release")


def _get(path: str) -> object:
    """Solo GET a rutas construidas por el programa; ninguna URL arbitraria."""
    raw = subprocess.run(
        ["gh", "api", "-X", "GET", path],
        capture_output=True, text=True, check=True, timeout=20,
    )
    return json.loads(raw.stdout)


def collect(issue: str, checkout_sha: str) -> dict[str, Any]:
    if not NUMBER_RE.fullmatch(issue) or not _sha(checkout_sha):
        raise ValueError("parámetros de observación inválidos")
    prefix = "/repos/" + REPO
    main = _get(prefix + "/branches/main")
    tag = _get(prefix + "/git/ref/tags/v1")
    gate = _get(prefix + "/issues/" + issue)
    comments = _get(prefix + "/issues/" + issue + "/comments?per_page=100")
    switch = _get(prefix + "/issues/767")
    rate = _get("/rate_limit")
    checks = []
    for page in range(1, 5):
        checks.append(_get(prefix + "/commits/" + checkout_sha
                           + "/check-runs?per_page=100&page=" + str(page)))
        if sum(len(v.get("check_runs", [])) for v in checks) >= checks[0].get("total_count", 0):
            break
    return {"repository": REPO, "checkout_sha": checkout_sha, "main": main,
            "tag": tag, "gate": gate, "comments": comments,
            "switch": switch, "rate": rate, "checks": checks}


def main() -> int:
    try:
        if os.environ.get("GITHUB_REPOSITORY") != REPO:
            raise ValueError("repositorio incorrecto")
        issue = os.environ["RELEASE_GATE_ISSUE"]
        checkout_sha = os.environ["GITHUB_SHA"]
        report = evaluate_bundle(collect(issue, checkout_sha))
    except (KeyError, ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError):
        report = _denied("github_source_unknown")
    print(json.dumps(report, sort_keys=True))
    return 0  # NO-GO es un resultado seguro, no un permiso.


if __name__ == "__main__":
    sys.exit(main())
