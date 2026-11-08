#!/usr/bin/env python3
"""Plan-only exact-SHA cutover for Factory #2095 / #1080.

This pure contract is NOT a release executor and cannot authorize any write.
Claims in a snapshot never become authenticated simply because they pass schema
validation; a future caller must independently verify every cited receipt.
"""
from __future__ import annotations

import re
from typing import Any

SHA = re.compile(r"[0-9a-f]{40}\Z")
FIELDS = frozenset({
    "candidate_sha", "main_sha", "published_sha", "phase",
    "release_machinery_changed", "policy_gate", "candidate_report",
    "consumer_report", "receipt",
})
CANDIDATE_FIELDS = frozenset({
    "state", "reason", "candidate_sha", "authorizes_release", "mutations", "tag_writes",
    "release_writes",
})
CONSUMER_FIELDS = frozenset({
    "state", "reason", "candidate_sha", "observed_consumers", "synthetic",
    "evidence_authenticated", "authorizes_release", "mutations",
    "tag_writes", "release_writes",
})
RECEIPT_FIELDS = frozenset({"candidate_sha", "source", "run_id"})


def _sha(value: object) -> bool:
    """Require an exact lowercase 40-character SHA string."""
    return type(value) is str and SHA.fullmatch(value) is not None


def _result(reason: str, *, steps: tuple[dict[str, str], ...] = ()) -> dict[str, Any]:
    """Return an immutable-authority decision with zero write permissions."""
    return {
        "state": "PLAN_ONLY" if steps else "HOLD",
        "reason": reason,
        "steps": [dict(step) for step in steps],
        "authorizes_release": False,
        "requires_owner_for_current_policy": True,
        "mutations": 0,
        "tag_writes": 0,
        "release_writes": 0,
    }


def plan_cutover(snapshot: object) -> dict[str, Any]:
    """Produce a non-executable proposal; no input can grant release authority.

    PLAN_ONLY is merely a schematic, never a validated evidence receipt. The
    real consumer collector currently returns UNKNOWN and therefore HOLD.
    """
    if type(snapshot) is not dict or set(snapshot) != FIELDS:
        return _result("snapshot_missing_or_ambiguous")
    sha = snapshot["candidate_sha"]
    main, previous = snapshot["main_sha"], snapshot["published_sha"]
    if not all(_sha(x) for x in (sha, main, previous)):
        return _result("sha_invalid")
    if sha != main or sha == previous:
        return _result("candidate_stale_or_already_published")
    if snapshot["phase"] != "construccion":
        return _result("live_or_phase_unknown_requires_human_gate")
    if snapshot["release_machinery_changed"] is not False:
        return _result("release_machinery_changed_or_unknown_requires_human_gate")
    # This is a product-direction authorization to build, not a release vote.
    if snapshot["policy_gate"] != "2075-product-direction-A":
        return _result("product_direction_authority_unknown")

    candidate = snapshot["candidate_report"]
    if (type(candidate) is not dict or set(candidate) != CANDIDATE_FIELDS
            or candidate.get("candidate_sha") != sha
            or candidate.get("state") != "REVIEW_ONLY"
            or candidate.get("reason") != "candidate_evidence_ready_for_future_policy_review"
            or candidate.get("authorizes_release") is not False
            or any(candidate.get(k) != 0 for k in ("mutations", "tag_writes", "release_writes"))):
        return _result("candidate_preflight_not_independently_satisfied")

    consumer = snapshot["consumer_report"]
    if (type(consumer) is not dict or set(consumer) != CONSUMER_FIELDS
            or consumer.get("candidate_sha") != sha
            or consumer.get("state") != "REVIEW_ONLY"
            or consumer.get("reason") != "verified_independent_receipts"
            or consumer.get("observed_consumers") != 6
            or consumer.get("synthetic") is not False
            or consumer.get("evidence_authenticated") is not True
            or consumer.get("authorizes_release") is not False
            or any(consumer.get(k) != 0 for k in ("mutations", "tag_writes", "release_writes"))):
        return _result("consumer_or_watchdog_proof_missing")

    receipt = snapshot["receipt"]
    if (type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS
            or receipt.get("candidate_sha") != sha
            or receipt.get("source") != "independent"
            or type(receipt.get("run_id")) is not int or receipt["run_id"] <= 0):
        return _result("independent_candidate_receipt_missing")

    # No commands, tools, API endpoints or write-capable instructions returned.
    return _result("hypothetical_cutover_sequence_requires_external_authority", steps=(
        {"stage": "revalidate_identity_and_guards", "sha": sha},
        {"stage": "verify_independent_consumer_and_watchdog_receipts", "sha": sha},
        {"stage": "require_separate_release_authorization_under_current_policy", "sha": sha},
        {"stage": "verify_semantic_release_and_protected_channel", "sha": sha},
        {"stage": "verify_post_release_bootstrap_or_revert", "sha": previous},
    ))
