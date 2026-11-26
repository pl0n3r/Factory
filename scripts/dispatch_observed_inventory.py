"""Pure bridge from #2221 evidence to the existing offline selector (#2249)."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from scripts.dispatch_inventory import (
    OFFLINE_CANDIDATE_KEYS, OFFLINE_SHA, offline_proposal_from_snapshot,
)
from scripts.salud_cola import diagnose_queue
from scripts.salud_cola_global_observar import fingerprint, quota
from scripts.salud_cola_github import REPOSITORIES, require_stable_github_sweeps
from scripts.salud_cola_snapshot import LABEL_STATE, assemble_inventory
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch

MAX_AGE_SECONDS = 120
OBS_KEYS = {
    "version", "scope", "policy_sha", "started_at", "finished_at", "writes",
    "authority", "capacity", "counts", "fingerprints", "status", "reason",
    "open_total", "available_total", "blocked_causes",
}
ACTIVE_STATES = {"reserved", "in_review", "recovery_required"}
DEPENDENCY_KEY = re.compile(r"(?:%s)#[1-9][0-9]{0,7}" % "|".join(map(re.escape, REPOSITORIES)))


def require(condition):
    if not condition:
        raise ValueError("unverified_observed_inventory")


def shape(value, keys):
    return type(value) is dict and set(value) == keys


def timestamp(value):
    require(type(value) is str and len(value) <= 40)
    parsed = datetime.fromisoformat(value)
    require(parsed.utcoffset() == timezone.utc.utcoffset(None))
    return parsed


def fresh(value, start, now):
    moment = timestamp(value)
    require(start <= moment <= now)
    require((now - moment).total_seconds() <= MAX_AGE_SECONDS)
    return moment


def paths(value):
    require(type(value) is list and len(value) <= 100)
    require(all(type(path) is str for path in value))
    require(len(set(value)) == len(value))
    # The canonical selector checks path syntax for candidates and active claims.
    from scripts.dispatch_inventory import _offline_claims
    return _offline_claims(value, name="observed_claims")


def stable_repository(repo, source, expected, start, now):
    require(shape(source, {"identity", "first", "second", "leases", "observed_at"}))
    fresh(source["observed_at"], start, now)
    identity = source["identity"]
    require(type(identity) is int and identity > 0)
    report = require_stable_github_sweeps(repo, source["first"], source["second"])
    require(fingerprint([identity, report]) == expected)
    states = {}
    for page in report["pages"]:
        for issue in page["issues"]:
            if not issue["pull_request"]:
                require(len(issue["labels"]) == 1)
                states[f"{repo}#{issue['number']}"] = LABEL_STATE[issue["labels"][0]]
    # No recovery-required reservation is silently treated as free.
    active = {key for key, state in states.items() if state in ACTIVE_STATES}
    require(type(source["leases"]) is dict and set(source["leases"]) == active)
    active_paths = set()
    for row in source["leases"].values():
        require(shape(row, {"claims", "verified"}))
        require(row["verified"] is True)
        claim = paths(row["claims"])
        require(bool(claim))
        active_paths.update(claim)
    require(len(active_paths) <= 100)
    return report, states, active_paths


def candidate_row(key, repo, item, active_paths, start, now, policy_sha, checkout_sha, digest):
    require(shape(item, {"candidate", "task", "dependency_states", "observed_at",
                         "policy_sha", "checkout_sha", "fingerprint"}))
    fresh(item["observed_at"], start, now)
    require(item["policy_sha"] == policy_sha and item["checkout_sha"] == checkout_sha)
    require(item["fingerprint"] == digest)
    row, task = item["candidate"], item["task"]
    require(shape(row, OFFLINE_CANDIDATE_KEYS))
    require(shape(task, {"key", "repository_ref", "priority", "claims", "depends_on"}))
    require(row["key"] == task["key"] == key)
    require(row["repository_ref"] == task["repository_ref"] == f"pl0n3r/{repo}")
    require(row["priority"] == task["priority"])
    require(row["policy_verified"] is True and row["evidence_verified"] is True)
    require(bool(paths(row["claims"])) and paths(row["claims"]) == paths(task["claims"]))
    require(paths(row["active_claims"]) == active_paths)
    deps = item["dependency_states"]
    require(type(task["depends_on"]) is list and all(
        type(dep) is str and DEPENDENCY_KEY.fullmatch(dep) is not None for dep in task["depends_on"]
    ))
    require(type(deps) is dict and len(task["depends_on"]) == len(deps))
    require(set(task["depends_on"]) == set(deps) and key not in deps)
    require(all(state in ("completed", "open") for state in deps.values()))
    require(type(row["dependencies_open"]) is list and sorted(row["dependencies_open"]) ==
            sorted(dep for dep, state in deps.items() if state == "open"))
    return row


def proposal_from_observation(observation, evidence, *, checkout_sha, policy_sha, now):
    """Only synthetic/offline evidence; caller authenticates sources and clock.

    Missing evidence, inconsistent census or selector rejection never yields
    READY, NO_WORK or a live order. No I/O or side effects occur here.
    """
    unknown = {
        "version": 1, "decision": "UNKNOWN", "reason": "unverified_observed_inventory",
        "selected": None, "order_proposal": None, "sent_count": 0,
        "execution": "OFFLINE_ONLY", "authority": "snapshot_only_not_verified_for_live",
    }
    try:
        require(type(checkout_sha) is str and len(checkout_sha) == 40
                and all(char in "0123456789abcdef" for char in checkout_sha))
        require(type(policy_sha) is str and OFFLINE_SHA.fullmatch(policy_sha) is not None)
        require(shape(observation, OBS_KEYS))
        require(observation["status"] == "OBSERVED_GLOBAL_ONLY"
                and observation["reason"] == "capacity_not_observed")
        require(type(observation["version"]) is int and observation["version"] == 1
                and type(observation["writes"]) is int and observation["writes"] == 0
                and observation["authority"] == "unchanged" and observation["capacity"] is None)
        require(observation["scope"] == list(REPOSITORIES)
                and observation["policy_sha"] == checkout_sha)
        clock = timestamp(now)
        started = timestamp(observation["started_at"])
        finished = fresh(observation["finished_at"], started, clock)
        require((finished - started).total_seconds() <= MAX_AGE_SECONDS)
        require(shape(evidence, {"repositories", "candidates", "rate_limit",
                                 "kill_switch_issue", "kill_switch_observed_at", "seen_idempotency_keys"}))
        require(shape(evidence["repositories"], set(REPOSITORIES)))
        require(shape(observation["fingerprints"], set(REPOSITORIES)))
        require(shape(observation["counts"], set(REPOSITORIES)))
        budget = evidence["rate_limit"]
        require(shape(budget, {"limit", "remaining"}))
        quota(budget["limit"], budget["remaining"])
        fresh(evidence["kill_switch_observed_at"], finished, clock)
        switch = evaluate_unattended_kill_switch(evidence["kill_switch_issue"])
        require(switch.state == "RUNNING" and not switch.global_pause)
        reports, projects, rows = [], [], []
        available, open_keys, identities = set(), set(), set()
        candidates = evidence["candidates"]
        require(type(candidates) is dict and 0 < len(candidates) <= 100)
        for repo in REPOSITORIES:
            digest = observation["fingerprints"][repo]
            require(type(digest) is str and OFFLINE_SHA.fullmatch(digest) is not None)
            report, states, active = stable_repository(
                repo, evidence["repositories"][repo], digest, finished, clock,
            )
            identity = evidence["repositories"][repo]["identity"]
            require(identity not in identities)
            identities.add(identity)
            open_keys.update(states)
            reports.append(report)
            leaves = []
            for key, state in states.items():
                if state != "available":
                    continue
                require(key in candidates)
                row = candidate_row(key, repo, candidates[key], active, finished,
                                    clock, policy_sha, checkout_sha, digest)
                available.add(key)
                rows.append(row)
                leaves.append({"key": key, "title": key, "state": "available",
                               "priority": row["priority"], "source_refs": [f"issue:{key}"]})
            # This is a candidate-only projection, NOT a full work inventory.
            projects.append({"repository_ref": f"pl0n3r/{repo}", "leaves": leaves, "narrative": []})
        require(available == set(candidates))
        for item in candidates.values():
            require(all((dep in open_keys) == (state == "open")
                        for dep, state in item["dependency_states"].items()))
        diagnosis = diagnose_queue(assemble_inventory(reports, None, budget))
        require(all(type(counts) is dict and all(type(n) is int for n in counts.values())
                    for counts in observation["counts"].values()))
        require(observation["counts"] == {
            repo: diagnosis["repositories"][repo]["counts"] for repo in REPOSITORIES
        })
        for field in ("open_total", "available_total"):
            require(type(observation[field]) is int and observation[field] == diagnosis[field])
        require(type(observation["blocked_causes"]) is dict and all(
            type(n) is int for n in observation["blocked_causes"].values()))
        require(observation["blocked_causes"] == diagnosis["blocked_cause_totals"])
        receipt = offline_proposal_from_snapshot({
            "version": 1, "policy_sha": policy_sha,
            "kill_switch": {"version": 1, "state": switch.state, "owner": "pl0n3r"},
            "projects": projects, "candidates": rows,
            "seen_idempotency_keys": evidence["seen_idempotency_keys"],
        }, policy_sha=policy_sha)
        if receipt["decision"] in ("PROPOSED", "REPLAY"):
            return receipt
        return {**unknown, "reason": "no_safe_candidate"}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return unknown
