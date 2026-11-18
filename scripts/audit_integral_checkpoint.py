#!/usr/bin/env python3
"""Checkpoint de auditoría puramente offline: nunca coordina ni acredita producción."""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    from scripts.work_inventory import CANONICAL_REPOSITORIES
except ModuleNotFoundError:  # Ejecución directa desde scripts/
    from work_inventory import CANONICAL_REPOSITORIES
SHA = re.compile(r"[0-9a-f]{40}\Z")
AC = re.compile(r"AC-[0-9]{2}\Z")
CLAIM = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?\Z")
REF = re.compile(r"https://github\.com/pl0n3r/(?:Factory|Condor|GrindFlow|brvtal|ControlBot|AutoFactory|FactoryRunner)"
                 r"/(?:issues/[0-9]+|pull/[0-9]+|actions/runs/[0-9]+|commit/[0-9a-f]{40})(?:#issuecomment-[0-9]+)?\Z")
STATES = {"available", "reserved", "in_review", "blocked", "completed"}
PENDING = {"deployment", "migration", "smoke", "rollback", "approval", "backup", "identity", "other"}
PR_STATES = {"open", "draft", "merged"}
QA_STATES = {"success", "pending", "failure", "unknown"}
PROD_STATES = {"VALIDATED_IN_PRODUCTION", "PENDING", "UNKNOWN"}
def fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError("schema_invalid")
    return value
def number(value):
    if type(value) is not int or value < 1:
        raise ValueError("issue_invalid")
    return value
def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("sha_invalid")
    return value
def ref(value):
    if not isinstance(value, str) or not REF.fullmatch(value):
        raise ValueError("reference_invalid")
    return value
def instant(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise ValueError("timestamp_invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("timestamp_invalid") from exc
def fresh(value, as_of):
    moment = instant(value)
    if not timedelta(0) <= as_of - moment <= timedelta(hours=24):
        raise ValueError("evidence_stale")
def evidence(value, *, status_key, valid_states, as_of, expected_sha):
    fields(value, {"sha", "observed_at", "ref", status_key})
    if value[status_key] not in valid_states:
        raise ValueError("evidence_state_invalid")
    if sha(value["sha"]) != expected_sha:
        raise ValueError("sha_mismatch")
    fresh(value["observed_at"], as_of)
    ref(value["ref"])
    return value[status_key]
def dependency(value):
    if not isinstance(value, str) or value.count("#") != 1:
        raise ValueError("dependency_invalid")
    repo, issue = value.split("#")
    if repo not in CANONICAL_REPOSITORIES or not issue.isascii() or not issue.isdecimal():
        raise ValueError("dependency_invalid")
    return f"{repo}#{number(int(issue))}"
def claim(value):
    if (not isinstance(value, str) or len(value) > 180
            or not CLAIM.fullmatch(value) or any(p in {".", ".."} for p in value.split("/"))):
        raise ValueError("claim_invalid")
    return value
def overlaps(left, right):
    a, b = left.rstrip("/"), right.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")
def empty(repo, reason):
    return {"repo": repo, "sha": None, "status": "unknown", "reasons": [reason], "issues": [], "incidents": [], "refs": []}
def leaf(raw, repo_sha, as_of):
    fields(raw, {"issue", "state", "required_ac", "acceptance", "depends_on",
                 "claims", "pr", "qa", "production", "ref"})
    issue = number(raw["issue"])
    if raw["state"] not in STATES:
        raise ValueError("state_invalid")
    link = ref(raw["ref"])
    required = raw["required_ac"]
    ac = raw["acceptance"]
    if (not isinstance(required, list) or not required or len(required) > 30
            or any(not isinstance(a, str) or not AC.fullmatch(a) for a in required)
            or len(set(required)) != len(required) or not isinstance(ac, list)):
        raise ValueError("acceptance_invalid")
    observed = []
    for row in ac:
        fields(row, {"id", "status", "ref"})
        if row["id"] not in required or row["status"] not in {"passed", "pending", "failed", "unknown"}:
            raise ValueError("acceptance_invalid")
        ref(row["ref"])
        observed.append(row["id"])
    if len(observed) != len(set(observed)) or set(observed) != set(required):
        raise ValueError("acceptance_missing")
    deps, claims = raw["depends_on"], raw["claims"]
    if (not isinstance(deps, list) or len(deps) > 100 or not isinstance(claims, list)
            or not claims or len(claims) > 100):
        raise ValueError("schema_invalid")
    deps = [dependency(x) for x in deps]
    claims = [claim(x) for x in claims]
    if (len(set(deps)) != len(deps) or len(set(claims)) != len(claims)
            or any(overlaps(a, b) for i, a in enumerate(claims) for b in claims[i + 1:])):
        raise ValueError("duplicate_entry")
    pr = raw["pr"]
    if pr is not None:
        fields(pr, {"number", "state", "sha", "ref"})
        number(pr["number"])
        if pr["state"] not in PR_STATES:
            raise ValueError("pr_invalid")
        sha(pr["sha"])
        ref(pr["ref"])
    if raw["state"] == "completed" and (pr is None or pr["state"] != "merged"):
        raise ValueError("merge_unverified")
    qa_expected = repo_sha if pr is None or pr["state"] == "merged" else pr["sha"]
    qa = evidence(raw["qa"], status_key="status", valid_states=QA_STATES,
                  as_of=as_of, expected_sha=qa_expected)
    prod = raw["production"]
    fields(prod, {"state", "sha", "observed_at", "ref", "pending"})
    pending = prod["pending"]
    if (not isinstance(pending, list) or len(pending) > 20
            or any(not isinstance(v, str) or v not in PENDING for v in pending)):
        raise ValueError("production_pending_invalid")
    prod_state = evidence({k: v for k, v in prod.items() if k != "pending"},
                          status_key="state", valid_states=PROD_STATES,
                          as_of=as_of, expected_sha=repo_sha)
    if prod_state == "VALIDATED_IN_PRODUCTION" and pending:
        raise ValueError("production_contradiction")
    reasons = []
    if raw["state"] == "blocked":
        reasons.append("issue_blocked")
    if any(row["status"] == "failed" for row in ac) or qa == "failure":
        reasons.append("qa_failed")
    if pending or prod_state == "PENDING":
        reasons.append("production_pending")
    if qa == "unknown" or prod_state == "UNKNOWN" or any(row["status"] == "unknown" for row in ac):
        raise ValueError("evidence_unknown")
    if raw["state"] == "completed" and (qa != "success" or
            prod_state != "VALIDATED_IN_PRODUCTION" or
            any(row["status"] != "passed" for row in ac)):
        reasons.append("acceptance_not_terminal")
    state = ("blocked" if reasons else "auditable" if raw["state"] == "completed"
             else "auditoria_open")
    refs = [link] + [row["ref"] for row in ac] + [raw["qa"]["ref"], prod["ref"]]
    if pr:
        refs.append(pr["ref"])
    return ({"issue": issue, "status": state, "reasons": sorted(set(reasons)), "sha": qa_expected,
             "pr": pr["number"] if pr else None, "qa": qa,
             "production": "verified" if prod_state == "VALIDATED_IN_PRODUCTION" else "pending",
             "refs": sorted(set(refs))}, deps, claims, raw["state"])
def build(snapshot):
    fields(snapshot, {"version", "as_of", "kill_switch", "repositories"})
    if type(snapshot["version"]) is not int or snapshot["version"] != 1:
        raise ValueError("version_invalid")
    as_of = instant(snapshot["as_of"])
    if snapshot["kill_switch"] not in {"RUNNING", "PAUSED", "UNKNOWN"}:
        raise ValueError("kill_switch_invalid")
    raw = snapshot["repositories"]
    if not isinstance(raw, list) or len(raw) != 7:
        raise ValueError("seven_repositories_required")
    by_repo = {}
    for row in raw:
        if not isinstance(row, dict) or row.get("repo") not in CANONICAL_REPOSITORIES:
            raise ValueError("repository_invalid")
        if row["repo"] in by_repo:
            raise ValueError("repository_duplicate")
        by_repo[row["repo"]] = row
    results, tasks = [], {}
    for repo in CANONICAL_REPOSITORIES:
        try:
            source = fields(by_repo[repo], {"repo", "sha", "observed_at", "ref", "leaves", "incidents"})
            repo_sha = sha(source["sha"])
            fresh(source["observed_at"], as_of)
            link = ref(source["ref"])
            if (not isinstance(source["leaves"], list) or len(source["leaves"]) > 100
                    or not isinstance(source["incidents"], list) or len(source["incidents"]) > 100):
                raise ValueError("schema_invalid")
            issue_rows, incident_rows = [], []
            for raw_leaf in source["leaves"]:
                key = raw_leaf.get("issue") if isinstance(raw_leaf, dict) else None
                try:
                    item, deps, claims, state = leaf(raw_leaf, repo_sha, as_of)
                    item_key = f"{repo}#{item['issue']}"
                    if item_key in tasks:
                        tasks[item_key][0]["status"] = "unknown"
                        tasks[item_key][0]["reasons"] = ["duplicate_issue"]
                        item["status"], item["reasons"] = "unknown", ["duplicate_issue"]
                    tasks[item_key] = (item, deps, claims, state)
                except (ValueError, TypeError) as exc:
                    code = str(exc) if str(exc) in {
                        "acceptance_missing", "sha_mismatch", "evidence_stale", "merge_unverified",
                        "evidence_unknown", "production_contradiction"} else "invalid_leaf"
                    item = {"issue": key if type(key) is int and key > 0 else None,
                            "status": "unknown", "reasons": [code], "sha": None,
                            "pr": None, "qa": "unknown", "production": "unknown", "refs": []}
                issue_rows.append(item)
            seen_incidents = set()
            for incident in source["incidents"]:
                fields(incident, {"issue", "state", "ref"})
                ident = number(incident["issue"])
                if ident in seen_incidents or incident["state"] not in {"open", "resolved"}:
                    raise ValueError("incident_invalid")
                seen_incidents.add(ident)
                incident_rows.append({"issue": ident, "state": incident["state"], "ref": ref(incident["ref"])})
            results.append({"repo": repo, "sha": repo_sha, "status": "auditable", "reasons": [],
                            "issues": sorted(issue_rows, key=lambda x: x["issue"] or 0),
                            "incidents": sorted(incident_rows, key=lambda x: x["issue"]), "refs": [link]})
        except (ValueError, TypeError) as exc:
            code = str(exc) if str(exc) == "evidence_stale" else "source_invalid"
            results.append(empty(repo, code))
    for key, (item, _, paths, state) in tasks.items():
        if item["status"] == "unknown":
            continue
        for other, (_, _, peer_paths, other_state) in tasks.items():
            if (key != other and key.split("#")[0] == other.split("#")[0]
                    and state != "completed" and other_state != "completed"
                    and any(overlaps(a, b) for a in paths for b in peer_paths)):
                item["status"] = "blocked"
                item["reasons"] = sorted(set(item["reasons"] + ["claim_conflict"]))
    def has_cycle(start, node, visited):
        if node in visited:
            return node == start
        item = tasks.get(node)
        return bool(item) and any(has_cycle(start, dep, visited | {node})
                                  for dep in item[1])
    for key, (item, deps, _, _) in tasks.items():
        if item["status"] != "unknown" and any(has_cycle(key, dep, {key}) for dep in deps):
            item["status"] = "blocked"
            item["reasons"] = sorted(set(item["reasons"] + ["dependency_cycle"]))
    for _ in tasks:
        for key, (item, deps, _, _) in tasks.items():
            if item["status"] == "unknown":
                continue
            for dep in deps:
                linked = tasks.get(dep)
                if linked is None or linked[0]["status"] == "unknown":
                    item["status"], item["reasons"] = "unknown", ["dependency_unknown"]
                elif dep == key or linked[3] != "completed" or linked[0]["status"] != "auditable":
                    item["status"] = "blocked"
                    item["reasons"] = sorted(set(item["reasons"] + ["dependency_open"]))
    for row in results:
        if snapshot["kill_switch"] != "RUNNING":
            row["status"], row["reasons"] = "unknown", ["kill_switch_not_running"]
            for item in row["issues"]:
                item["status"], item["reasons"] = "unknown", ["kill_switch_not_running"]
            continue
        if row["status"] == "unknown":
            continue
        states = [item["status"] for item in row["issues"]]
        if any(x["state"] == "open" for x in row["incidents"]):
            states.append("blocked")
            row["reasons"].append("open_incident")
        row["status"] = next((v for v in ("unknown", "blocked", "auditoria_open")
                              if v in states), "auditable")
    return {"version": 1, "as_of": snapshot["as_of"], "kill_switch": snapshot["kill_switch"], "repositories": results}
def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        if args != ["audit-integral-fixture.json"]:
            raise ValueError("invalid_fixture")
        path = Path.cwd() / "audit-integral-fixture.json"
        if path.suffix != ".json" or path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError("invalid_fixture")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        output = build(snapshot)
        rc = 0
    except (ValueError, OSError, TypeError, RecursionError):
        output = {"version": 1, "status": "unknown", "reasons": ["invalid_fixture"], "repositories": [
            empty(repo, "invalid_fixture") for repo in CANONICAL_REPOSITORIES]}
        rc = 2
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return rc
if __name__ == "__main__":
    raise SystemExit(main())
