#!/usr/bin/env python3
"""Candidate-only automatic release preflight: authenticated GET, never publish.

Factory #1080 / #2075-A authorizes DEVELOPMENT only. This module deliberately
contains no write API call, branch update, tag movement or release capability.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
from typing import Any, Callable

REPO = "pl0n3r/Factory"
SHA = re.compile(r"[a-f0-9]{40}\Z")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
MARKER = re.compile(r"<!--\s*factory-unattended-kill-switch\s+(\{[^\n<>]*\})\s*-->")
BUNDLE_FIELDS = frozenset({
    "checkout_sha", "phase", "main", "tag", "switch", "freeze",
    "release_gates", "rate", "candidate_version", "published_version",
    "compare", "ruleset", "checks", "consumer_compatibility", "watchdog",
})
TRUSTED_APPS = {
    "Validar": ("github-actions", 15368),
    "SonarCloud Code Analysis": ("sonarqubecloud", 12526),
    "CodeQL": ("github-advanced-security", 57789),
}
MACHINERY = (
    ".github/workflows/release", "scripts/release_", "seguridad/",
    "docs/release", ".github/workflows/politica", "config/permissions",
)


class PreflightError(ValueError):
    """Incomplete or untrusted evidence cannot progress a release."""


def _blocked(reason: str) -> dict[str, Any]:
    return {"state": "BLOCKED", "reason": reason,
            "authorizes_release": False, "mutations": 0, "tag_writes": 0,
            "release_writes": 0}


def _read_only(reason: str) -> dict[str, Any]:
    return {"state": "REVIEW_ONLY", "reason": reason,
            "authorizes_release": False, "mutations": 0, "tag_writes": 0,
            "release_writes": 0}


def _semver(value: object) -> tuple[int, int, int] | None:
    if type(value) is not str or len(value) > 64 or not VERSION.fullmatch(value):
        return None
    return tuple(map(int, value.split(".")))


def _trusted_evidence(row: object, sha: str) -> bool:
    return (type(row) is dict and row.get("authenticated") is True
            and row.get("head_sha") == sha and row.get("status") == "completed"
            and row.get("conclusion") == "success")


def evaluate_inventory(bundle: object) -> dict[str, Any]:
    """Reduce a full REST inventory; a positive result is STILL read-only.

    The caller is responsible for authenticating transport. In tests all inputs
    are synthetic, and no output conveys permission to execute any mutation.
    """
    if type(bundle) is not dict or set(bundle) != BUNDLE_FIELDS:
        return _blocked("inventory_missing_or_ambiguous")
    sha = bundle["checkout_sha"]
    if type(sha) is not str or not SHA.fullmatch(sha):
        return _blocked("sha_invalid")
    main = bundle["main"]
    if (type(main) is not dict or main.get("name") != "main"
            or main.get("protected") is not True
            or type(main.get("commit")) is not dict
            or main["commit"].get("sha") != sha):
        return _blocked("main_identity_or_protection_unknown")
    ref = bundle["tag"]
    if (type(ref) is not dict or ref.get("ref") != "refs/tags/v1"
            or type(ref.get("object")) is not dict
            or ref["object"].get("type") != "commit"
            or type(ref["object"].get("sha")) is not str
            or not SHA.fullmatch(ref["object"]["sha"])):
        return _blocked("v1_identity_unknown")
    if ref["object"]["sha"] == sha:
        return _blocked("candidate_already_distributed")
    ruleset = bundle["ruleset"]
    if (type(ruleset) is not dict or ruleset.get("id") != 23958613
            or ruleset.get("enforcement") != "active"
            or ruleset.get("target") != "tag"):
        return _blocked("v1_ruleset_unknown")
    switch = bundle["switch"]
    if (type(switch) is not dict or switch.get("number") != 767
            or switch.get("state") != "closed"
            or type(switch.get("user")) is not dict
            or switch["user"].get("login") != "pl0n3r"
            or type(switch.get("body")) is not str):
        return _blocked("kill_switch_unverified")
    matches = MARKER.findall(switch["body"])
    if len(matches) != 1 or len(re.findall(r"<!--\s*factory-unattended-kill-switch\b", switch["body"])) != 1:
        return _blocked("kill_switch_unverified")
    try:
        marker = json.loads(matches[0])
    except (TypeError, ValueError):
        return _blocked("kill_switch_unverified")
    if marker != {"version": 1, "state": "RUNNING", "owner": "pl0n3r"}:
        return _blocked("kill_switch_unverified")
    freeze = bundle["freeze"]
    if type(freeze) is not dict or freeze.get("number") != 921 or freeze.get("state") != "closed":
        return _blocked("release_frozen_or_unknown")
    gates = bundle["release_gates"]
    if type(gates) is not list or len(gates) >= 100 or gates:
        return _blocked("release_gate_open_or_inventory_incomplete")
    rate = bundle["rate"]
    core = rate.get("resources", {}).get("core") if type(rate) is dict and type(rate.get("resources")) is dict else None
    if (type(core) is not dict or type(core.get("limit")) is not int
            or type(core.get("remaining")) is not int or core["limit"] <= 0
            or not 0 <= core["remaining"] <= core["limit"]
            or core["remaining"] * 5 < core["limit"]
            or (core["limit"] >= 5000 and core["remaining"] < 1200)):
        return _blocked("api_budget_unknown_or_low")
    candidate, published = _semver(bundle["candidate_version"]), _semver(bundle["published_version"])
    if candidate is None or published is None or candidate[0] != published[0] or candidate <= published:
        return _blocked("semver_invalid_or_not_forward")
    comparison = bundle["compare"]
    if (type(comparison) is not dict or comparison.get("status") != "ahead"
            or type(comparison.get("ahead_by")) is not int
            or type(comparison.get("behind_by")) is not int
            or comparison["ahead_by"] <= 0 or comparison["behind_by"] != 0
            or type(comparison.get("files")) is not list
            or not comparison["files"] or len(comparison["files"]) >= 300):
        return _blocked("compare_unknown_or_truncated")
    for changed in comparison["files"]:
        if type(changed) is not dict or type(changed.get("filename")) is not str:
            return _blocked("compare_files_invalid")
        if changed["filename"].startswith(MACHINERY):
            return _blocked("release_or_security_machinery_changed")
    if bundle["phase"] != "construccion":
        return _blocked("live_or_phase_unverified")
    runs = bundle["checks"]
    if type(runs) is not dict or set(runs) != set(TRUSTED_APPS):
        return _blocked("checks_missing")
    for name, identity in TRUSTED_APPS.items():
        row = runs[name]
        if not _trusted_evidence(row, sha):
            return _blocked("checks_not_terminal_green_exact_sha")
        app = row.get("app")
        if type(app) is not dict or (app.get("slug"), app.get("id")) != identity:
            return _blocked("check_app_identity_unknown")
    for name in ("consumer_compatibility", "watchdog"):
        if not _trusted_evidence(bundle[name], sha):
            return _blocked(name + "_not_independently_attested")
    return _read_only("candidate_evidence_ready_for_future_policy_review")


def _get(path: str) -> object:
    """The only real transport is gh api with an explicit GET method."""
    if not path.startswith("/repos/pl0n3r/Factory/") and path != "/rate_limit":
        raise PreflightError("noncanonical_api_path")
    result = subprocess.run(
        ["gh", "api", "-X", "GET", path], capture_output=True,
        text=True, timeout=20, check=True,
    )
    if len(result.stdout) > 1_000_000:
        raise PreflightError("api_response_too_large")
    return json.loads(result.stdout)


def _version(contents: object) -> str:
    if (type(contents) is not dict or contents.get("type") != "file"
            or contents.get("encoding") != "base64"
            or type(contents.get("content")) is not str
            or len(contents["content"]) > 8000):
        raise PreflightError("version_source_unknown")
    try:
        decoded = base64.b64decode(contents["content"], validate=True)
        if len(decoded) > 4096:
            raise ValueError("version too large")
        obj = json.loads(decoded)
    except (ValueError, UnicodeError) as exc:
        raise PreflightError("version_source_invalid") from exc
    if type(obj) is not dict or set(obj) != {"version"} or _semver(obj["version"]) is None:
        raise PreflightError("version_source_invalid")
    return obj["version"]


def _check_run(payload: object, name: str) -> dict:
    if (type(payload) is not dict or type(payload.get("total_count")) is not int
            or not 1 <= payload["total_count"] <= 100
            or type(payload.get("check_runs")) is not list
            or len(payload["check_runs"]) != payload["total_count"]):
        raise PreflightError("check_response_incomplete")
    rows = payload["check_runs"]
    if any(type(r) is not dict or r.get("name") != name or type(r.get("id")) is not int for r in rows):
        raise PreflightError("check_record_ambiguous")
    result = max(rows, key=lambda r: r["id"])
    app = result.get("app")
    return {"head_sha": result.get("head_sha"), "status": result.get("status"),
            "conclusion": result.get("conclusion"), "authenticated": True,
            "app": {"slug": app.get("slug"), "id": app.get("id")} if type(app) is dict else None}


def collect_inventory(checkout_sha: str, phase: str, get: Callable[[str], object] = _get) -> dict[str, Any]:
    """Collect bounded REST GET facts. Consumer/health attestations stay UNKNOWN."""
    if type(checkout_sha) is not str or SHA.fullmatch(checkout_sha) is None:
        return _blocked("sha_invalid")
    if phase != "construccion":
        return _blocked("live_or_phase_unverified")
    root = "/repos/" + REPO
    try:
        main = get(root + "/branches/main")
        tag = get(root + "/git/ref/tags/v1")
        switch = get(root + "/issues/767")
        freeze = get(root + "/issues/921")
        gates = get(root + "/issues?state=open&labels=factory-release&per_page=100")
        rate = get("/rate_limit")
        ruleset = get(root + "/rulesets/23958613")
        candidate_version = _version(get(root + "/contents/config/version.json?ref=" + checkout_sha))
        published_version = _version(get(root + "/contents/config/version.json?ref=v1"))
        compare = get(root + "/compare/v1..." + checkout_sha)
        checks = {}
        for name in TRUSTED_APPS:
            from urllib.parse import quote
            payload = get(root + "/commits/" + checkout_sha
                          + "/check-runs?filter=latest&per_page=100&check_name="
                          + quote(name, safe=""))
            checks[name] = _check_run(payload, name)
        bundle = {
            "checkout_sha": checkout_sha, "phase": phase,
            "main": main, "tag": tag, "switch": switch, "freeze": freeze,
            "release_gates": gates, "rate": rate, "candidate_version": candidate_version,
            "published_version": published_version, "compare": compare,
            "ruleset": ruleset, "checks": checks,
            "consumer_compatibility": None, "watchdog": None,
        }
        return evaluate_inventory(bundle)
    except (PreflightError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError, ValueError, TypeError, KeyError):
        return _blocked("rest_source_unavailable_or_invalid")
