#!/usr/bin/env python3
"""Factory #2093: read-only consumer evidence, never release authorization.

An individual consumer's green main CI cannot establish compatibility with a
different, unpublished Factory candidate. Caller-supplied proof is NOT a
cryptographic or independently authenticated attestation.
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import Any, Callable

CONSUMERS = (
    "pl0n3r/Condor",
    "pl0n3r/GrindFlow",
    "pl0n3r/brvtal",
    "pl0n3r/ControlBot",
    "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
CI_NAMES = frozenset(("Validar", "validate"))
GITHUB_ACTIONS = {"slug": "github-actions", "id": 15368}
PROOF_FIELDS = frozenset((
    "repository", "candidate_sha", "run_id", "status", "conclusion", "source",
))
WATCHDOG_FIELDS = frozenset((
    "candidate_sha", "run_id", "status", "conclusion", "source",
))


def _sha(value: object) -> bool:
    return type(value) is str and SHA.fullmatch(value) is not None


def _report(reason: str, *, review_only: bool = False,
            observed: int = 0, synthetic: bool = False) -> dict[str, Any]:
    return {
        "state": "REVIEW_ONLY" if review_only else "BLOCKED",
        "reason": reason,
        "observed_consumers": observed,
        "synthetic": synthetic,
        "evidence_authenticated": False,
        "authorizes_release": False,
        "mutations": 0,
        "tag_writes": 0,
        "release_writes": 0,
    }


def _get(path: str) -> object:
    """Authenticated GitHub REST transport, strictly GET and bounded response."""
    if (type(path) is not str or not path.startswith("/repos/pl0n3r/")
            or not 1 <= len(path) <= 256
            or not re.fullmatch(r"/repos/pl0n3r/[A-Za-z0-9_-]+/"
                                r"(branches/main|commits/[a-f0-9]{40}/check-runs"
                                r"\?filter=latest&per_page=100)", path)):
        raise ValueError("unsupported_github_rest_path")
    completed = subprocess.run(
        ["gh", "api", "-X", "GET", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=12,
    )
    if len(completed.stdout) > 262144:
        raise ValueError("github_rest_payload_unbounded")
    return json.loads(completed.stdout.decode("utf-8"))


def _verified_ci(payload: object, expected_sha: str) -> bool:
    if type(payload) is not dict or set(payload) != {"total_count", "check_runs"}:
        return False
    rows = payload["check_runs"]
    if (type(payload["total_count"]) is not int
            or not 0 <= payload["total_count"] <= 100
            or type(rows) is not list or len(rows) > 100
            or payload["total_count"] != len(rows)):
        return False
    matching = [r for r in rows if type(r) is dict and r.get("name") in CI_NAMES]
    if len(matching) != 1:
        return False
    row = matching[0]
    app = row.get("app")
    return (
        row.get("head_sha") == expected_sha
        and row.get("status") == "completed"
        and row.get("conclusion") == "success"
        and type(app) is dict
        and app.get("slug") == GITHUB_ACTIONS["slug"]
        and app.get("id") == GITHUB_ACTIONS["id"]
    )


def collect_consumer_ci(get: Callable[[str], object] = _get) -> dict[str, Any]:
    """At most twelve fixed REST GETs; never mistakes main CI for candidate proof."""
    observed = 0
    try:
        for repository in CONSUMERS:
            root = "/repos/" + repository
            branch = get(root + "/branches/main")
            if (type(branch) is not dict or branch.get("name") != "main"
                    or branch.get("protected") is not True
                    or type(branch.get("commit")) is not dict
                    or not _sha(branch["commit"].get("sha"))):
                return _report("consumer_main_identity_or_protection_unknown",
                               observed=observed)
            sha = branch["commit"]["sha"]
            checks = get(root + "/commits/" + sha
                         + "/check-runs?filter=latest&per_page=100")
            if not _verified_ci(checks, sha):
                return _report("consumer_ci_unknown_or_not_green", observed=observed)
            observed += 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError,
            UnicodeError):
        return _report("consumer_rest_source_unavailable", observed=observed)
    # The six consumer CIs are NOT a compatibility test for the Factory candidate.
    # No candidate-bound receipts or independently authenticated watchdog exist here.
    return _report("candidate_compatibility_and_watchdog_unknown",
                   observed=observed)


def _proof(value: object, candidate: str, repository: str | None = None) -> bool:
    allowed = PROOF_FIELDS if repository is not None else WATCHDOG_FIELDS
    if type(value) is not dict or set(value) != allowed:
        return False
    if repository is not None and value["repository"] != repository:
        return False
    return (
        value["candidate_sha"] == candidate
        and type(value["run_id"]) is int and value["run_id"] > 0
        and value["status"] == "completed"
        and value["conclusion"] == "success"
        and value["source"] == "independent"
    )


def evaluate_fixture(snapshot: object, *, synthetic: bool = False) -> dict[str, Any]:
    """Schema regression ONLY: REVIEW_ONLY is confined to explicit test fixtures."""
    if not synthetic:
        return _report("untrusted_caller_evidence")
    if type(snapshot) is not dict or set(snapshot) != {
            "candidate_sha", "consumers", "watchdog"}:
        return _report("snapshot_missing_or_ambiguous", synthetic=True)
    candidate = snapshot["candidate_sha"]
    if not _sha(candidate):
        return _report("candidate_sha_invalid", synthetic=True)
    consumers = snapshot["consumers"]
    if type(consumers) is not list or len(consumers) != len(CONSUMERS):
        return _report("consumer_inventory_missing_or_unbounded", synthetic=True)
    seen: set[str] = set()
    for item in consumers:
        if type(item) is not dict:
            return _report("consumer_proof_invalid", synthetic=True)
        repository = item.get("repository")
        if type(repository) is not str or repository not in CONSUMERS or repository in seen:
            return _report("consumer_identity_duplicate_or_unknown", synthetic=True)
        if not _proof(item, candidate, repository):
            return _report("consumer_proof_invalid_or_stale", synthetic=True)
        seen.add(repository)
    if seen != set(CONSUMERS):
        return _report("consumer_inventory_incomplete", synthetic=True)
    if not _proof(snapshot["watchdog"], candidate):
        return _report("watchdog_proof_invalid_or_stale", synthetic=True)
    return _report("synthetic_schema_only_no_release_authority",
                   review_only=True, observed=6, synthetic=True)
