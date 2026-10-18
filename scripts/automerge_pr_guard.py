#!/usr/bin/env python3
"""Guard de auto-merge Factory: evidencia exact-SHA, de solo lectura y fail-closed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import uuid
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPO = "pl0n3r/Factory"
# SonarCloud lists project PRs in a single bounded response; 536 were observed.
# The transport independently rejects responses larger than 1 MiB.
MAX_SONAR_PR_INVENTORY = 1000
HEX_SHA = re.compile(r"[0-9a-f]{40}\Z")
SWITCH_HEADER = re.compile(r"<!--\s*factory-unattended-kill-switch\b", re.I)
SWITCH_MARKER = re.compile(r"<!--\s*factory-unattended-kill-switch\s+(\{[^\n]*\})\s*-->", re.I)
WINDOW_HEADER = re.compile(r"<!--\s*factory\s*-\s*release\s*-\s*window\b", re.I)
WINDOW_MARKER = re.compile(r"<!--\s*factory-release-window\s+(\{[^\n]*\})\s*-->", re.I)
EXECUTED_MARKER = re.compile(r"<!--\s*factory-release-executed\s+(\{[^\n]*\})\s*-->", re.I)
EXECUTED_HEADER = re.compile(r"<!--\s*factory\s*-\s*release\s*-\s*executed\b", re.I)
# CodeRabbit's category-anchored Security & Privacy / Major finding denotes
# a potentially high-severity security issue. Do not confuse it with
# unqualified Major maintainability or functional-correctness observations.
# Search for CodeRabbit finding labels, not casual discussion of how
# "high", "critical", or "rate limited" classifications work. Anchor each
# finding to its own Markdown line; keep explicit security-Major blocking.
SEVERE = re.compile(
    r"""^[ \t]*(?:[-*+>][ \t]+|\#{1,6}[ \t]+){0,2}(?:
        (?:(?:\`?[0-9]{1,6}(?:-[0-9]{1,6})?\`?
          |Line[ \t]+[0-9]{1,6}(?:-[0-9]{1,6})?
          |[A-Za-z0-9_./-]+\.(?:py|yml|yaml):[0-9]{1,6}(?:-[0-9]{1,6})?
          |Found[ \t]+an[ \t]+issue)[ \t]*:[ \t]*)?[*_]{0,2}(?:🔒[ \t]*)?Security[ \t]*&(?:amp;)?[ \t]*Privacy[*_]{0,2}
        [ \t]*\|[ \t]*[*_]{0,2}(?:🟠[ \t]*)?Major(?:\b|(?=[*_]))
      | (?:(?:\`?[0-9]{1,6}(?:-[0-9]{1,6})?\`?
          |Line[ \t]+[0-9]{1,6}(?:-[0-9]{1,6})?
          |[A-Za-z0-9_./-]+\.(?:py|yml|yaml):[0-9]{1,6}(?:-[0-9]{1,6})?
          |Found[ \t]+an[ \t]+issue)[ \t]*:[ \t]*)?[*_]{0,2}(?!No\b|Found[ \t]+no\b|Review\b)(?:[🔒🩺🎯][ \t]*|⚠️?[ \t]*)?(?!Maintainability\b|Code[ \t]+Smell\b)[A-Za-z][^\n|\`:\d]{1,48}[*_]{0,2}[ \t]*\|[ \t]*[*_]{0,2}(?:🔴[ \t]*)?(?:Critical|High)(?![A-Za-z0-9/])
      | (?:(?:\`?[0-9]{1,6}(?:-[0-9]{1,6})?\`?
             |Line[ \t]+[0-9]{1,6}(?:-[0-9]{1,6})?
             |[A-Za-z0-9_./-]+\.(?:py|yml|yaml):[0-9]{1,6}(?:-[0-9]{1,6})?
           )[ \t]*:[ \t]*)?[*_]{0,2}(?:Security[ \t]+)?(?:HIGH|CRITICAL|P0|P1|SEVERE|BLOCKER)[*_]{0,2}
        [ \t]+(?:security|severity|vulnerabilit(?:y|ies)|flaw|issue|finding|risk|bug
                |command[ \t]+injection|remote[ \t]+command[ \t]+execution
                |sql[ \t]+injection|(?:stored|reflected)[ \t]+xss|xss|ssrf
                |privilege[ \t]+escalation|authentication[ \t]+bypass
                |auth[ \t]+bypass)\b
      | \[(?:P0|P1)\][ \t]+\S
      | (?:\[[ xX]\][ \t]+)?[*_]{0,2}🔴[ \t]+[*_]{0,2}(?:HIGH|CRITICAL)[*_]{0,2}
        (?:[ \t]*:[*_]{0,2}[ \t]*|[ \t]+)
        (?:security[ \t]+vulnerabilit(?:y|ies)|security[ \t]+risk|
           sql[ \t]+injection|ssrf|xss|privilege[ \t]+escalation|
           remote[ \t]+command[ \t]+execution|command[ \t]+injection|
           authentication[ \t]+bypass|auth[ \t]+bypass)\b
      | [*_]{0,2}\[(?:P0|P1)\][*_]{0,2}[ \t]+
        (?:privilege[ \t]+escalation|sql[ \t]+injection|ssrf|xss|
           command[ \t]+injection|remote[ \t]+command[ \t]+execution|
           authentication[ \t]+bypass|auth[ \t]+bypass|
           security[ \t]+vulnerabilit(?:y|ies))\b
      | [*_]{0,2}(?:Security[ \t]*[-:][ \t]*)?
        (?:HIGH|CRITICAL|P0|P1)[*_]{0,2}
        (?:
          [ \t]*:[*_]{0,2}[ \t]*\S
          | -[ \t]*(?:risk|vulnerabilit(?:y|ies)|issue|flaw|bug)\b
        )
      | [*_]{0,2}BLOCKER(?:[*_]{0,2}[ \t]*:|[ \t]*:[*_]{0,2})[ \t]*[*_]{0,2}
        (?:security(?:[ \t]+(?:vulnerabilit(?:y|ies)|risk|flaw|issue|bug))?
         |vulnerabilit(?:y|ies)
         |remote[ \t]+command[ \t]+execution
         |command[ \t]+injection
         |sql[ \t]+injection
         |(?:stored|reflected)[ \t]+xss
         |xss
         |ssrf
         |privilege[ \t]+escalation
         |authentication[ \t]+bypass
         |auth[ \t]+bypass)\b
      | [*_]{0,2}(?:Severity|Priority)(?:[*_]{0,2}[ \t]*:|[ \t]*:[*_]{0,2})[ \t]*[*_]{0,2}(?:HIGH|CRITICAL|P0|P1|BLOCKER)(?:\b|(?=[*_]))
    )""",
    re.I | re.M | re.X,
)
# A completed review must not be rejected because a policy snippet says
# "rate limited" or an advisory says "files skipped due to trivial changes".
# Actual skipped/incomplete review notices begin on their own Markdown line.
SKIPPED = re.compile(
    r"""^[ \t]*(?:[-*+>][ \t]+|\#{1,6}[ \t]+){0,2}\*{0,2}(?:
        Review(?:[ \t]+\w+){0,3}[ \t]+skipp?ed
      | skipp?ed(?:[ \t]+\w+){0,3}[ \t]+review
      | skip[ \t]+review
      | (?:Draft[ \t]+PR[ \t]+)?not[ \t]+reviewed
      | Review(?:[ \t]+was)?[ \t]+not[ \t]+(?:performed|completed|available)
      | (?:CodeRabbit[ \t]+)?(?:could[ \t]+not|cannot|unable[ \t]+to)[ \t]+review
      | manual[ \t]+review[ \t]+required
      | review[ \t]+rate[\s._-]*limit(?:ed|ing)?
      | rate[._-]limit(?:ed|ing)?
      | rate[ \t]+limit[ \t]+(?:reached|exceeded)
      | review[ \t]+disabled
      | reviews?(?:[ \t]+(?:has|have)[ \t]+been)?[ \t]+(?:paused|suspended)
    )\b""",
    re.I | re.M | re.X,
)
UNFINISHED_REVIEW = re.compile(
    r"^[ \t]*(?:[-*+>][ \t]+|\#{1,6}[ \t]+){0,2}[*_]{0,2}"
    r"(?:reviews?|analysis|scan)[ \t]+(?:is[ \t]+)?"
    r"(?:pending|queued|waiting|in[ \t-]+progress|awaiting|cancell?ed|not[ \t-]+complete|paused|suspended)(?:\b|(?=[*_]))[*_]{0,2}",
    re.I | re.M,
)
# CodeRabbit reports an aborted/rejected review action in an HTML summary,
# not necessarily in a GitHub review or commit-status description. Treat the
# exact structural notice as incomplete without matching ordinary prose.
ACTION_NOT_COMPLETED = re.compile(
    r"^[ \t]*<summary>[ \t]*(?:<strong>[ \t]*)?(?:⚠️[ \t]*)?"
    r"Action[ \t]+not[ \t]+completed[ \t]*(?:</strong>[ \t]*)?</summary>[ \t]*$",
    re.I | re.M,
)
# A plain-text CodeRabbit failure may arrive without the HTML <summary>.
# Anchor the notice at the beginning of a line to avoid treating discussion
# of "Action not completed" as a failed review event.
ACTION_NOT_COMPLETED_TEXT = re.compile(
    r"^[ \t]*(?:[-*+>][ \t]+|\#{1,6}[ \t]+){0,2}[*_]{0,2}"
    r"(?:⚠️[ \t]*)?Action[ \t]+not[ \t]+completed[*_]{0,2}"
    r"(?:[ \t]*[:.!]|[ \t]*$)",
    re.I | re.M,
)


# Accept CodeRabbit warning/checklist decorations only at the start of a line.
# Never remove inline words: explanatory prose is not an actual skip notice.
REVIEW_NOTICE_DECORATION = re.compile(
    r"^[ \t]*(?:[-*+>][ \t]+|\#{1,6}[ \t]+){0,2}"
    r"(?:\[[ xX]\][ \t]+(?:[*_]{0,2}(?:⚠️?|🚨)[ \t]+)?"
    r"|[*_]{0,2}(?:⚠️?|🚨)[ \t]+)",
    re.M,
)


def review_incomplete_notice(body):
    """Recognize explicit incomplete-review notices, not policy prose."""
    body = REVIEW_NOTICE_DECORATION.sub("", body)
    return bool(SKIPPED.search(body) or UNFINISHED_REVIEW.search(body)
                or ACTION_NOT_COMPLETED.search(body)
                or ACTION_NOT_COMPLETED_TEXT.search(body))


def severe_finding(body):
    """Detect severity headings even with task-list or warning prefixes."""
    return bool(SEVERE.search(body) or
                SEVERE.search(REVIEW_NOTICE_DECORATION.sub("", body)))


RESERVATION_HEADER = re.compile(r"<!--\s*condor-reserva\b", re.I)
RESERVATION_MARKER = re.compile(r"<!--\s*condor-reserva\s+(\{[^\n]*\})\s*-->", re.I)
TASK_HEADER = re.compile(r"<!--\s*factory-plan-task\b", re.I)
TASK_MARKER = re.compile(r"<!--\s*factory-plan-task\s+(\{[^\n]*\})\s*-->", re.I)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
CANONICAL_BRANCH = re.compile(r"trabajo/issue-([1-9][0-9]*)\Z")
CLOSING_ISSUE = re.compile(r"\b(?:closes|fixes|resolves)\s+#([1-9][0-9]*)\b", re.I)
REQUIRED = ("Validar", "SonarCloud Code Analysis", "CodeQL",
            "Sonar Coverage = published", "SonarQube Cloud Analysis Method = CI-based")
# Check-run names alone do not authenticate the publisher. Slugs were
# verified against actual Factory check-runs on the GitHub API (PR #1373).
REQUIRED_APPS = {
    "Validar": "github-actions",
    "SonarCloud Code Analysis": "sonarqubecloud",
    "CodeQL": "github-advanced-security",
    "Sonar Coverage = published": "github-actions",
    "SonarQube Cloud Analysis Method = CI-based": "github-actions",
}
ISSUE_STATUS_LABELS = frozenset({
    "estado: disponible", "estado: reservado", "estado: requiere recuperación",
    "estado: en revisión", "estado: completado", "estado: cancelado",
    "estado: bloqueado",
})
ACTIVE_ISSUE_STATES = frozenset({"estado: reservado", "estado: en revisión"})

# PR metadata is independent proof that the PR claims the same bot V3 lease.
# The coordinator writes both the visible line and hidden marker on recovery.
PR_LEASE_HIDDEN_HEADER = re.compile(r"<!--\s*condor-reserva-id\b", re.I)
PR_LEASE_HIDDEN = re.compile(r"<!--\s*condor-reserva-id:\s*([0-9a-f-]{36})\s*-->", re.I)
PR_LEASE_VISIBLE_HEADER = re.compile(r"(?im)^Reserva\s*:")
PR_LEASE_VISIBLE = re.compile(r"(?im)^Reserva:\s*([0-9a-f-]{36})\s*$")


class Denied(Exception):
    """Imposible acreditar todas las condiciones de fusión."""


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Denied("duplicate_json_key")
        result[key] = value
    return result


def parse_marker(body, starts, pattern):
    if type(body) is not str or len(starts.findall(body)) != 1:
        raise Denied("ambiguous_marker")
    matches = pattern.findall(body)
    if len(matches) != 1:
        raise Denied("malformed_marker")
    try:
        return json.loads(matches[0], object_pairs_hook=unique)
    except (ValueError, TypeError) as exc:
        raise Denied("invalid_marker_json") from exc


def acceptance_fingerprint(body):
    """Huella compatible con aceptacion_kit.contract_fingerprint, sin I/O."""
    if type(body) is not str or not 1 <= len(body) <= 200000:
        raise Denied("acceptance_body_invalid")
    headings = ("### Contexto", "### Alcance", "### Fuera de alcance",
                "### Criterios de aceptación", "### Contrato ejecutable")
    lines = body.splitlines()

    def section(heading):
        positions = [i for i, line in enumerate(lines) if line.strip() == heading]
        if len(positions) != 1:
            raise Denied("acceptance_heading_invalid")
        start = positions[0] + 1
        end = next((i for i in range(start, len(lines))
                    if lines[i].startswith("### ")), len(lines))
        content = "\n".join(lines[start:end]).strip()
        if not content:
            raise Denied("acceptance_section_empty")
        return content

    for heading in headings:
        section(heading)
    human = {}
    for line in section("### Criterios de aceptación").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ["):
            continue
        matched = re.fullmatch(r"- \[[ xX]\] \[(AC-[0-9]{2})\] (.{1,500})", stripped)
        if matched is None or matched.group(1) in human:
            raise Denied("acceptance_human_invalid")
        human[matched.group(1)] = matched.group(2).strip()
    if not 1 <= len(human) <= 20:
        raise Denied("acceptance_human_missing")

    prefix, suffix = "<!-- factory-acceptance ", " -->"
    if body.count(prefix) != 1:
        raise Denied("acceptance_marker_ambiguous")
    start = body.index(prefix) + len(prefix)
    end = body.find(suffix, start)
    if end < 0:
        raise Denied("acceptance_marker_malformed")
    try:
        machine = json.loads(body[start:end].strip(), object_pairs_hook=unique)
    except (ValueError, TypeError) as exc:
        raise Denied("acceptance_machine_json_invalid") from exc
    if (type(machine) is not dict or set(machine) != {"version", "criteria"}
            or type(machine["version"]) is not int or machine["version"] != 1
            or type(machine["criteria"]) is not list
            or not 1 <= len(machine["criteria"]) <= 20):
        raise Denied("acceptance_machine_invalid")
    criteria, seen = [], set()
    test_target = re.compile(
        r"((?:tests|metricas|seguridad|lecciones|producto)/test_[A-Za-z0-9_/-]+\.py)::"
        r"([A-Za-z_][A-Za-z0-9_]*)::(test_[A-Za-z0-9_]+)\Z")
    for row in machine["criteria"]:
        if type(row) is not dict or set(row) != {"id", "kind", "target"}:
            raise Denied("acceptance_machine_row_invalid")
        criterion, kind, target = row["id"], row["kind"], row["target"]
        if (type(criterion) is not str or re.fullmatch(r"AC-[0-9]{2}", criterion) is None
                or criterion in seen or type(kind) is not str
                or kind not in ("test", "check") or type(target) is not str):
            raise Denied("acceptance_machine_row_invalid")
        if kind == "test":
            matched = test_target.fullmatch(target)
            if matched is None:
                raise Denied("acceptance_test_target_invalid")
            parts = matched.group(1).split("/")
            if any(p in ("", ".", "..") for p in parts):
                raise Denied("acceptance_test_path_invalid")
        elif (re.fullmatch(r"[^\r\n]{1,120}", target) is None
              or target in ("Validar", "Criterios de aceptación")):
            raise Denied("acceptance_check_target_invalid")
        seen.add(criterion)
        criteria.append({"id": criterion, "kind": kind, "target": target})
    if set(human) != seen:
        raise Denied("acceptance_ids_mismatch")
    canonical = {
        "human": [{"id": i, "description": human[i]} for i in sorted(human)],
        "machine": sorted(criteria, key=lambda row: row["id"]),
    }
    payload = json.dumps(canonical, ensure_ascii=False,
                         separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_switch(issue):
    if (type(issue) is not dict or issue.get("number") != 767
            or issue.get("url") != "https://api.github.com/repos/pl0n3r/Factory/issues/767"
            or issue.get("repository_url") != "https://api.github.com/repos/pl0n3r/Factory"
            or issue.get("state") != "closed" or type(issue.get("user")) is not dict
            or issue["user"].get("login") != "pl0n3r"):
        raise Denied("switch_source_invalid")
    marker = parse_marker(issue.get("body"), SWITCH_HEADER, SWITCH_MARKER)
    if (type(marker) is not dict or set(marker) != {"version", "state", "owner"}
            or type(marker["version"]) is not int or marker["version"] != 1
            or marker["state"] != "RUNNING" or marker["owner"] != "pl0n3r"):
        raise Denied("switch_not_running")


def verify_pr(snapshot, expected):
    pr = snapshot.get("pr")
    if type(pr) is not dict:
        raise Denied("pr_invalid")
    head, base = pr.get("head"), pr.get("base")
    branch = head.get("ref") if type(head) is dict else None
    match = CANONICAL_BRANCH.fullmatch(branch) if type(branch) is str else None
    pr_body = pr.get("body")
    issue_links = CLOSING_ISSUE.findall(pr_body) if type(pr_body) is str else []
    if (match is None or issue_links != [match.group(1)]):
        raise Denied("branch_issue_link_noncanonical")
    # A pending GitHub auto-merge is mutable future authority. A clean
    # preflight cannot validate or revoke an already queued merge.
    if "auto_merge" not in pr:
        raise Denied("pr_auto_merge_state_unknown")
    if pr["auto_merge"] is not None:
        raise Denied("preexisting_deferred_auto_merge")
    if (pr.get("state") != "open" or pr.get("draft") is not False
            or pr.get("mergeable") is not True
            or type(head) is not dict or type(base) is not dict
            or type(head.get("repo")) is not dict
            or type(head["repo"].get("full_name")) is not str
            or head["repo"]["full_name"].lower() != REPO.lower()
            or head["repo"].get("fork") is not False
            or head.get("sha") != expected
            or base.get("ref") != "main" or base.get("sha") != snapshot.get("main_sha")
            or type(snapshot.get("main_sha")) is not str
            or HEX_SHA.fullmatch(snapshot["main_sha"]) is None):
        raise Denied("pr_head_or_base_changed")



def issue_labels(issue):
    if type(issue) is not dict or type(issue.get("labels")) is not list:
        raise Denied("issue_labels_unknown")
    labels = issue["labels"]
    if any(type(v) is not dict or type(v.get("name")) is not str for v in labels):
        raise Denied("issue_labels_unknown")
    return {v["name"] for v in labels}


def coordination_statuses(issue):
    """Treat all status/state families as authority-bearing, including unknowns.

    A closed dependency is not completed if it simultaneously carries an
    unknown or blocking state; a currently reserved issue is equally ambiguous.
    """
    return {name for name in issue_labels(issue)
            if name in ISSUE_STATUS_LABELS
            or re.match(r"(?i)^(?:estado|status|state)\s*:", name)}


def verify_pr_lease_binding(body, expected_id):
    """Mirror the coordinator's V3 PR binding, denying ambiguity fail-closed.

    Both exact markers may coexist because rewrite_pull_reservation() emits
    them together. A stale value, malformed header, or absence denies.
    """
    if type(body) is not str or type(expected_id) is not str:
        raise Denied("pr_reservation_metadata_missing")
    hidden_headers = PR_LEASE_HIDDEN_HEADER.findall(body)
    visible_headers = PR_LEASE_VISIBLE_HEADER.findall(body)
    hidden_values = PR_LEASE_HIDDEN.findall(body)
    visible_values = PR_LEASE_VISIBLE.findall(body)
    if (len(hidden_headers) != len(hidden_values)
            or len(visible_headers) != len(visible_values)
            or len(hidden_values) > 1 or len(visible_values) > 1
            or not (hidden_values or visible_values)):
        raise Denied("pr_reservation_metadata_ambiguous")
    if any(value.lower() != expected_id.lower()
           for value in hidden_values + visible_values):
        raise Denied("pr_reservation_session_mismatch")


def verify_reservation(snapshot):
    """La rama canónica no sustituye una V3 auténtica y vigente del bot."""
    pr, issue = snapshot.get("pr"), snapshot.get("issue")
    if type(pr) is not dict or type(pr.get("head")) is not dict:
        raise Denied("reservation_pr_missing")
    branch = pr["head"].get("ref")
    match = CANONICAL_BRANCH.fullmatch(branch) if type(branch) is str else None
    if match is None:
        raise Denied("reservation_branch_invalid")
    number = int(match.group(1))
    # Recognized reservation plus an unknown state is conflicting evidence.
    # Do not treat unknown estado/status/state labels as harmless metadata.
    statuses = coordination_statuses(issue)
    if (type(issue) is not dict or type(issue.get("number")) is not int
            or issue["number"] != number or issue.get("state") != "open"
            or "pull_request" in issue
            or issue.get("url") != f"https://api.github.com/repos/{REPO}/issues/{number}"
            or issue.get("repository_url") != f"https://api.github.com/repos/{REPO}"
            or type(issue.get("user")) is not dict
            or issue["user"].get("login") != "pl0n3r"
            or len(statuses) != 1 or not statuses <= ACTIVE_ISSUE_STATES):
        raise Denied("reservation_issue_not_reserved")
    task = parse_marker(issue.get("body"), TASK_HEADER, TASK_MARKER)
    if type(task) is not dict or type(task.get("version")) is not int or task["version"] != 1 or task.get("owner") != "pl0n3r":
        raise Denied("reservation_task_invalid")
    paths, deps = task.get("paths"), task.get("depends_on")
    if (type(paths) is not list or not 1 <= len(paths) <= 100
            or any(type(x) is not str or not x or x.startswith("/") or ".." in x.split("/") for x in paths)
            or len(set(paths)) != len(paths)
            or type(deps) is not list or len(deps) > 20
            or any(type(n) is not int or n <= 0 or n == number for n in deps)
            or len(set(deps)) != len(deps)):
        raise Denied("reservation_task_claims_invalid")
    comments = snapshot.get("lease_comments")
    if type(comments) is not list or not 1 <= len(comments) <= 500:
        raise Denied("reservation_history_incomplete")
    history = []
    for c in comments:
        if type(c) is not dict or type(c.get("user")) is not dict or type(c.get("body")) is not str:
            raise Denied("reservation_comment_invalid")
        if not RESERVATION_HEADER.search(c["body"]):
            continue
        if c["user"].get("login") != "github-actions[bot]":
            raise Denied("reservation_source_untrusted")
        history.append(parse_marker(c["body"], RESERVATION_HEADER, RESERVATION_MARKER))
    if not history:
        raise Denied("reservation_bot_marker_missing")
    lease = history[-1]
    if type(lease) is not dict:
        raise Denied("reservation_marker_invalid")
    rid = lease.get("reservation_id")
    try:
        parsed_id = uuid.UUID(rid) if type(rid) is str else None
    except (ValueError, AttributeError, TypeError):
        parsed_id = None
    pinned_acceptance_sha = acceptance_fingerprint(issue["body"])
    pinned_task_sha = hashlib.sha256(json.dumps(
        task, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")).hexdigest()
    if (type(lease.get("version")) is not int or lease["version"] != 3
            or lease.get("active") is not True
            or lease.get("owner") != "pl0n3r"
            or lease.get("branch") != branch
            or parsed_id is None or parsed_id.version not in {4, 5}
            or lease.get("acceptance_sha256") != pinned_acceptance_sha
            or lease.get("task_marker_sha256") != pinned_task_sha
            or lease.get("task_paths") != paths
            or lease.get("task_depends_on") != deps
            or type(lease.get("acceptance_sha256")) is not str
            or SHA256.fullmatch(lease["acceptance_sha256"]) is None
            or type(lease.get("task_marker_sha256")) is not str
            or SHA256.fullmatch(lease["task_marker_sha256"]) is None):
        raise Denied("reservation_v3_inactive_or_changed")
    verify_pr_lease_binding(pr.get("body"), rid)
    dependency_rows = snapshot.get("dependencies")
    if type(dependency_rows) is not list or len(dependency_rows) != len(deps):
        raise Denied("reservation_dependencies_unknown")
    by_number = {}
    for row in dependency_rows:
        if (type(row) is not dict or type(row.get("number")) is not int
                or row["number"] in by_number):
            raise Denied("reservation_dependency_invalid")
        by_number[row["number"]] = row
    if set(by_number) != set(deps):
        raise Denied("reservation_dependencies_mismatch")
    for row in by_number.values():
        if (row.get("state") != "closed"
                or row.get("state_reason") != "completed"
                or coordination_statuses(row) != {"estado: completado"}):
            raise Denied("reservation_dependency_not_completed")
    changed = snapshot.get("files")
    if (type(changed) is not list or not 1 <= len(changed) <= 100
            or type(pr.get("changed_files")) is not int
            or pr["changed_files"] != len(changed)):
        raise Denied("reservation_changed_files_incomplete")
    seen = set()
    for item in changed:
        if type(item) is not dict or type(item.get("filename")) is not str:
            raise Denied("reservation_file_invalid")
        path, old = item["filename"], item.get("previous_filename")
        # A PR-controlled .github workflow could forge a green "Validar"
        # check with the same github-actions app slug as trusted CI. Until
        # workflow identity and unchanged definitions are attested, such
        # PRs need an independent trusted integration path, never auto-merge.
        if any(type(value) is str and value.startswith(".github/")
               for value in (path, old)):
            raise Denied("ci_definition_changed_by_pr")
        if path in seen or path not in paths or (old is not None and old not in paths):
            raise Denied("reservation_paths_exceeded")
        seen.add(path)


def verify_ancestry(compare, main_sha):
    # GitHub puede declarar mergeable una rama que está detrás de main.
    # Asegurar reconciliación exacta, fijada al main observado en este snapshot.
    if (type(compare) is not dict
            or compare.get("status") != "ahead"
            or type(compare.get("behind_by")) is not int
            or compare["behind_by"] != 0
            or type(compare.get("ahead_by")) is not int
            or compare["ahead_by"] < 1
            or type(compare.get("base_commit")) is not dict
            or compare["base_commit"].get("sha") != main_sha
            or type(compare.get("merge_base_commit")) is not dict
            or compare["merge_base_commit"].get("sha") != main_sha):
        raise Denied("branch_not_reconciled_exact_main")


def verify_checks(checks, expected):
    # GitHub retains older check attempts on the same HEAD. The authoritative
    # result is the run with the highest check-run ID, as in aceptacion_kit.
    if (type(checks) is not dict or type(checks.get("total_count")) is not int
            or type(checks.get("check_runs")) is not list
            or checks["total_count"] != len(checks["check_runs"])
            or not 0 <= checks["total_count"] <= 500):
        raise Denied("incomplete_checks")
    found = {}
    seen_ids = set()
    for row in checks["check_runs"]:
        if (type(row) is not dict or type(row.get("name")) is not str
                or type(row.get("id")) is not int or row["id"] < 1
                or row["id"] in seen_ids
                or row.get("head_sha") != expected):
            raise Denied("check_identity_invalid")
        seen_ids.add(row["id"])
        if row["name"] in REQUIRED:
            old = found.get(row["name"])
            if old is None or row["id"] > old["id"]:
                found[row["name"]] = row
    for name, issuer in REQUIRED_APPS.items():
        row = found.get(name)
        if (type(row) is not dict or type(row.get("app")) is not dict
                or row["app"].get("slug") != issuer):
            raise Denied("required_check_publisher_unknown_or_untrusted")
        if row.get("status") != "completed" or row.get("conclusion") != "success":
            raise Denied("required_check_unknown_or_failed")



def verify_sonar_evidence(sonar, checks, expected, number):
    """D-069: the green check is not evidence that 26 annotations are minor."""
    if (type(number) is not int or not 1 <= number <= 1000000
            or type(sonar) is not dict or sonar.get("project") != "pl0n3r_factory"
            or sonar.get("pull_request") != str(number)
            or sonar.get("sha") != expected
            or type(sonar.get("total")) is not int
            or not 0 <= sonar["total"] <= 500
            or type(sonar.get("issues")) is not list
            or len(sonar["issues"]) != sonar["total"]):
        raise Denied("sonar_evidence_unknown_or_stale")
    # Reuse the authenticated, exact-SHA SonarCloud check (never a user check).
    rows = [row for row in checks["check_runs"]
            if row["name"] == "SonarCloud Code Analysis"]
    newest = max(rows, key=lambda row: row["id"])
    output = newest.get("output")
    if (type(output) is not dict
            or type(output.get("annotations_count")) is not int
            or output["annotations_count"] != sonar["total"]):
        raise Denied("sonar_issue_count_unknown_or_mismatch")
    keys = set()
    for issue in sonar["issues"]:
        if type(issue) is not dict:
            raise Denied("sonar_issue_invalid")
        key = issue.get("key")
        if (type(key) is not str or not key or key in keys
                or issue.get("project") != "pl0n3r_factory"
                or issue.get("pullRequest") != str(number)):
            raise Denied("sonar_issue_identity_unknown")
        keys.add(key)
        kind = issue.get("type")
        if kind not in ("BUG", "VULNERABILITY", "CODE_SMELL"):
            raise Denied("sonar_issue_type_unknown")
        impacts = issue.get("impacts")
        if impacts is not None:
            if type(impacts) is not list or not impacts:
                raise Denied("sonar_impacts_unknown")
            for impact in impacts:
                if (type(impact) is not dict
                        or impact.get("softwareQuality") not in
                        ("SECURITY", "RELIABILITY", "MAINTAINABILITY")
                        or impact.get("severity") not in
                        ("BLOCKER", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")):
                    raise Denied("sonar_impact_unclassified")
                if (impact["softwareQuality"] in ("SECURITY", "RELIABILITY")
                        and impact["severity"] in ("BLOCKER", "CRITICAL", "HIGH")):
                    raise Denied("sonar_high_critical_new_code")
        if impacts is not None:
            # A legacy BUG/VULNERABILITY with only MAINTAINABILITY impacts
            # has no matching reliability/security impact, at any severity.
            # Treat the contradictory classification as UNKNOWN, not clean.
            # MQR impact precedence still applies to mixed-quality findings.
            if (kind in ("BUG", "VULNERABILITY")
                    and all(impact["softwareQuality"] == "MAINTAINABILITY"
                            for impact in impacts)):
                raise Denied("sonar_type_quality_conflict")
            # Sonar Multi-Quality Rule Mode uses impacts as the authoritative
            # classification. Its legacy top-level severity can disagree:
            # e.g. reliability LOW with legacy BLOCKER. Never turn that into
            # a false HIGH/CRITICAL finding.
            continue
        # Legacy classification applies only if no MQR impacts are supplied.
        severity = issue.get("severity")
        if (type(severity) is not str or severity not in
                ("BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO",
                 "HIGH", "MEDIUM", "LOW")):
            raise Denied("sonar_severity_unknown")
        # Legacy MAJOR is ambiguous for bugs/vulnerabilities: fail closed.
        if kind in ("BUG", "VULNERABILITY") and severity in (
                "BLOCKER", "CRITICAL", "HIGH", "MAJOR"):
            raise Denied("sonar_high_critical_or_ambiguous_new_code")


def verify_coderabbit_status(payload, expected, history):
    """A green commit status can still indicate that CodeRabbit skipped review.

    This source is independent of pull-request reviews and comments. It must
    not be ignored merely because an earlier clean review exists on the SHA.
    """
    if (type(payload) is not dict or payload.get("sha") != expected
            or type(payload.get("statuses")) is not list
            or type(payload.get("total_count")) is not int
            or not 0 <= payload["total_count"] <= 100
            or len(payload["statuses"]) != payload["total_count"]):
        raise Denied("coderabbit_commit_status_incomplete")
    ids = set()
    latest = None
    for row in payload["statuses"]:
        if (type(row) is not dict or type(row.get("id")) is not int
                or row["id"] < 1 or row["id"] in ids
                or type(row.get("context")) is not str):
            raise Denied("commit_status_identity_invalid")
        ids.add(row["id"])
        if row["context"] == "CodeRabbit":
            if latest is None or row["id"] > latest["id"]:
                latest = row
    if latest is None:
        raise Denied("coderabbit_commit_status_missing")
    # The combined /status response omits `creator`. Anyone with commit-status
    # write permission can publish the string context='CodeRabbit'. Authenticate
    # the historical status source from GET /commits/{sha}/statuses, which does
    # include each status's GitHub `creator`, and cross-check both snapshots.
    if type(history) is not list or not 1 <= len(history) <= 500:
        raise Denied("coderabbit_status_history_incomplete")
    seen_history_ids = set()
    history_latest = None
    for row in history:
        if (type(row) is not dict or type(row.get("id")) is not int
                or row["id"] <= 0 or row["id"] in seen_history_ids
                or type(row.get("context")) is not str):
            raise Denied("coderabbit_status_history_invalid")
        seen_history_ids.add(row["id"])
        if row["context"] == "CodeRabbit":
            if (type(row.get("creator")) is not dict
                    or row["creator"].get("login") != "coderabbitai[bot]"):
                raise Denied("coderabbit_status_publisher_untrusted")
            # /status hides older entries for the same context. A later green
            # entry on the same immutable HEAD cannot prove that an earlier
            # HIGH/CRITICAL finding was fixed or investigated.
            description = row.get("description")
            if type(description) is not str or not description.strip():
                raise Denied("coderabbit_historical_status_unknown")
            if severe_finding(description):
                raise Denied("coderabbit_historical_severe_unresolved")
            if history_latest is None or row["id"] > history_latest["id"]:
                history_latest = row
    if (history_latest is None or latest["id"] != history_latest["id"]
            or latest.get("state") != history_latest.get("state")
            or latest.get("description") != history_latest.get("description")):
        raise Denied("coderabbit_status_history_mismatch")
    description = latest.get("description")
    if (latest.get("state") != "success"
            or type(description) is not str or not description.strip()
            or severe_finding(description)
            or review_incomplete_notice(description)):
        raise Denied("coderabbit_commit_status_skipped_or_failed")


def verify_review(reviews, comments, issue_comments, expected, now):
    if (type(reviews) is not list or type(comments) is not list
            or type(issue_comments) is not list
            or len(reviews) > 500 or len(comments) > 500
            or len(issue_comments) > 500):
        raise Denied("review_evidence_incomplete")
    clean = False
    substantive_times = []
    for row in reviews:
        if type(row) is not dict or type(row.get("user")) is not dict:
            raise Denied("review_invalid")
        if row.get("state") not in {"APPROVED", "COMMENTED", "DISMISSED", "CHANGES_REQUESTED"}:
            raise Denied("review_state_unknown")
        # D-069: the review state alone is not a veto in construction.
        # A known HIGH/CRITICAL finding from *any* reviewer is a veto,
        # whether the review state is COMMENTED, APPROVED or CHANGES_REQUESTED.
        detail = row.get("body")
        if row.get("state") == "CHANGES_REQUESTED" and (
                type(detail) is not str or not detail.strip()):
            raise Denied("changes_requested_severity_unknown")
        if type(detail) is str and severe_finding(detail):
            raise Denied("review_high_or_critical")
        if row.get("state") == "DISMISSED":
            # Una revisión anulada no es evidencia de seguridad válida,
            # incluso si el snapshot contiene otra revisión favorable.
            raise Denied("dismissed_review")
        if row["user"].get("login") != "coderabbitai[bot]":
            continue
        # A CodeRabbit finding without authenticated commit identity cannot
        # be safely classified as historical; fail closed instead.
        commit_id = row.get("commit_id")
        if type(commit_id) is not str or HEX_SHA.fullmatch(commit_id) is None:
            raise Denied("coderabbit_review_commit_unknown")
        if commit_id != expected:
            # A different commit SHA does not prove a prior HIGH/CRITICAL
            # finding has been resolved. Fail closed absent authenticated
            # resolution evidence for that finding.
            body = row.get("body")
            if (type(body) is not str or not body.strip()
                    or severe_finding(body)):
                raise Denied("prior_coderabbit_severe_review_unresolved")
            continue
        body = row.get("body")
        # A blank exact-HEAD CodeRabbit review is UNKNOWN even when another
        # review of this same SHA was previously substantive and clean.
        if type(body) is not str or not body.strip():
            raise Denied("coderabbit_review_body_unknown")
        if (row.get("state") in ("APPROVED", "COMMENTED", "CHANGES_REQUESTED") and type(body) is str
                and body.strip() and not review_incomplete_notice(body)
                and not severe_finding(body)):
            # An exact-HEAD review without a verifiable submission time is
            # incomplete evidence, not an authorization to merge. GitHub
            # supplies submitted_at on published reviews; drafts/PENDING do
            # not count as substantive reviews.
            submitted = row.get("submitted_at")
            if type(submitted) is not str:
                raise Denied("coderabbit_review_timestamp_unknown")
            try:
                reviewed = datetime.fromisoformat(submitted.replace("Z", "+00:00"))
            except ValueError as exc:
                raise Denied("coderabbit_review_timestamp_invalid") from exc
            if reviewed.tzinfo is None or reviewed.utcoffset() is None:
                raise Denied("coderabbit_review_timezone_unknown")
            if reviewed.astimezone(timezone.utc) > now.astimezone(timezone.utc):
                raise Denied("coderabbit_review_timestamp_in_future")
            clean = True
            substantive_times.append(reviewed.astimezone(timezone.utc))
        elif type(body) is str and (review_incomplete_notice(body)
                                        or severe_finding(body)):
            raise Denied("review_skipped_or_severe")
    if not clean:
        raise Denied("substantive_coderabbit_review_missing")
    for row in comments:
        if type(row) is not dict or type(row.get("user")) is not dict:
            raise Denied("review_comment_invalid")
        # D-069: inline security findings from ANY authenticated reviewer
        # must block, including older commits not proven remediated. A clean
        # CodeRabbit summary cannot silence a third-party inline HIGH/CRITICAL.
        body = row.get("body")
        if type(body) is not str or not body.strip():
            raise Denied("review_inline_finding_unknown")
        if severe_finding(body):
            raise Denied("review_finding_unknown_or_severe")
        if row["user"].get("login") == "coderabbitai[bot]":
            commit_id = row.get("commit_id")
            if type(commit_id) is not str or HEX_SHA.fullmatch(commit_id) is None:
                raise Denied("coderabbit_inline_commit_unknown")
            body = row.get("body")
            # An older inline HIGH/CRITICAL finding is not automatically
            # remediated by a newer clean review of the branch.
            if type(body) is not str or severe_finding(body):
                raise Denied("review_finding_unknown_or_severe")
            if commit_id == expected and review_incomplete_notice(body):
                raise Denied("review_finding_unknown_or_skipped")
    # CodeRabbit publica "Review skipped" en la conversación del Issue/PR,
    # NO en /pulls/{number}/comments (solo comentarios inline de revisión).
    # Un marcador sin SHA verificable sigue siendo evidencia UNKNOWN: negar.
    for row in issue_comments:
        if type(row) is not dict or type(row.get("user")) is not dict:
            raise Denied("issue_comment_invalid")
        body = row.get("body")
        if type(body) is not str or not body.strip():
            raise Denied("issue_comment_body_unknown")
        if severe_finding(body):
            raise Denied("issue_comment_severe")
        if row["user"].get("login") != "coderabbitai[bot]":
            continue
        if review_incomplete_notice(body):
            # No dejar bloqueado para siempre un skip del PR en DRAFT si
            # después existe review real del MISMO SHA, posterior a ese skip.
            # Sin tiempos confiables: UNKNOWN y falla cerrado.
            # CodeRabbit edits summaries in place; creation is not evidence
            # that the latest skip predates the substantive exact-HEAD review.
            # Missing or malformed updated_at must fail closed.
            updated = row.get("updated_at")
            try:
                skipped_at = datetime.fromisoformat(
                    updated.replace("Z", "+00:00")
                ) if type(updated) is str else None
            except ValueError:
                skipped_at = None
            if (skipped_at is None or skipped_at.tzinfo is None
                    or not any(t > skipped_at.astimezone(timezone.utc)
                               for t in substantive_times)):
                raise Denied("coderabbit_skipped_not_superseded")


def verify_freeze(windows, now):
    if type(windows) is not list or len(windows) > 100:
        raise Denied("release_window_inventory_unknown")
    for row in windows:
        if type(row) is not dict or type(row.get("issue")) is not dict:
            raise Denied("release_gate_invalid")
        issue, comments = row["issue"], row.get("comments")
        if type(comments) is not list:
            raise Denied("release_comments_incomplete")
        body = issue.get("body")
        if type(body) is not str:
            raise Denied("release_gate_body_unknown")
        if not WINDOW_HEADER.search(body):
            continue
        marker = parse_marker(body, WINDOW_HEADER, WINDOW_MARKER)
        # Mirror release_window.py::_window_from_body. An incomplete window,
        # reversed interval or excessive TTL cannot be treated as expired and
        # therefore safe simply because expires_at is in the past.
        if (type(marker) is not dict
                or set(marker) != {"version", "sha", "opened_at", "expires_at"}
                or type(marker.get("version")) is not int or marker["version"] != 1
                or type(marker.get("sha")) is not str
                or HEX_SHA.fullmatch(marker["sha"]) is None
                or any(type(marker[k]) is not str for k in ("opened_at", "expires_at"))):
            raise Denied("release_window_marker_invalid")
        try:
            opened = datetime.fromisoformat(marker["opened_at"].replace("Z", "+00:00"))
            expires = datetime.fromisoformat(marker["expires_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise Denied("release_window_clock_invalid") from exc
        if (opened.tzinfo is None or opened.utcoffset() is None
                or expires.tzinfo is None or expires.utcoffset() is None):
            raise Denied("release_window_timezone_invalid")
        if expires <= opened or expires - opened > timedelta(minutes=120):
            raise Denied("release_window_interval_invalid")
        executed = False
        terminal_runs = set()
        for c in comments:
            if type(c) is not dict:
                raise Denied("release_comment_invalid")
            # A terminal execution marker is authoritative only from the
            # canonical bot. Apply release_window._execution's strict rule:
            # exactly one complete marker per bot comment; conflicting runs
            # are ambiguous even if one otherwise looks valid.
            if (type(c.get("user")) is not dict
                    or c["user"].get("login") != "github-actions[bot]"):
                continue
            body = c.get("body")
            if type(body) is not str:
                raise Denied("release_comment_body_unknown")
            matches = EXECUTED_MARKER.findall(body)
            header_count = len(EXECUTED_HEADER.findall(body))
            if (header_count or matches) and (header_count != 1 or len(matches) != 1):
                raise Denied("release_execution_marker_ambiguous_or_incomplete")
            for data in matches:
                try:
                    parsed = json.loads(data, object_pairs_hook=unique)
                except (ValueError, TypeError) as exc:
                    raise Denied("release_execution_marker_invalid") from exc
                if (type(parsed) is not dict
                        or set(parsed) != {"version", "sha", "run_id", "executed_at"}
                        or type(parsed["version"]) is not int or parsed["version"] != 1
                        or type(parsed["sha"]) is not str or parsed["sha"] != marker["sha"]
                        or type(parsed["run_id"]) is not int or parsed["run_id"] < 1
                        or type(parsed["executed_at"]) is not str):
                    raise Denied("release_execution_marker_invalid")
                try:
                    executed_time = datetime.fromisoformat(
                        parsed["executed_at"].replace("Z", "+00:00")
                    )
                except ValueError as exc:
                    raise Denied("release_execution_clock_invalid") from exc
                if executed_time.tzinfo is None or executed_time.utcoffset() is None:
                    raise Denied("release_execution_timezone_invalid")
                # A terminal marker predating this window cannot release a
                # later freeze, even if its SHA and run ID look valid.
                if executed_time.astimezone(timezone.utc) < opened.astimezone(timezone.utc):
                    raise Denied("release_execution_precedes_window")
                if executed_time.astimezone(timezone.utc) > now.astimezone(timezone.utc):
                    raise Denied("release_execution_timestamp_in_future")
                terminal_runs.add((parsed["sha"], parsed["run_id"]))
                if len(terminal_runs) > 1:
                    raise Denied("release_execution_conflicting_runs")
                executed = True
        if now <= expires.astimezone(timezone.utc) and not executed:
            raise Denied("release_freeze_active")


def verify(snapshot, expected, now):
    if type(expected) is not str or HEX_SHA.fullmatch(expected) is None:
        raise Denied("head_unknown")
    if type(snapshot) is not dict:
        raise Denied("evidence_missing")
    verify_switch(snapshot.get("switch"))
    verify_pr(snapshot, expected)
    verify_reservation(snapshot)
    verify_ancestry(snapshot.get("compare"), snapshot.get("main_sha"))
    verify_checks(snapshot.get("checks"), expected)
    pr = snapshot.get("pr")
    number = pr.get("number") if type(pr) is dict else None
    verify_sonar_evidence(snapshot.get("sonar_evidence"), snapshot.get("checks"),
                          expected, number)
    verify_coderabbit_status(snapshot.get("commit_status"), expected,
                             snapshot.get("status_history"))
    verify_review(snapshot.get("reviews"), snapshot.get("comments"),
                  snapshot.get("issue_comments"), expected, now)
    verify_freeze(snapshot.get("windows"), now)


def github_urlopen(req, timeout=12):
    """Use a non-redirecting GitHub transport, preserving unit-test isolation."""
    return build_opener(_NoGitHubRedirect).open(req, timeout=timeout)


def get(token, path, *, include_link=False):
    req = Request("https://api.github.com" + path, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "factory-automerge-guard",
        "Authorization": "Bearer " + token,
    })
    try:
        with github_urlopen(req, timeout=12) as response:
            body = response.read(1048577)
            paged_checks = re.fullmatch(
                r"/repos/pl0n3r/Factory/commits/[0-9a-f]{40}/check-runs"
                r"\?per_page=100&page=[1-5]", path
            ) is not None
            paged_records = re.fullmatch(
                r"/repos/pl0n3r/Factory/(?:pulls/[1-9][0-9]*/(?:files|reviews|comments)"
                r"|issues/[1-9][0-9]*/comments|commits/[0-9a-f]{40}/statuses)\?per_page=100&page=[1-5]", path
            ) is not None
            # A short REST list page is only terminal if GitHub does not
            # explicitly advertise a next page. Otherwise a later high/critical
            # finding could be silently skipped by the bounded reader.
            has_next = re.search(
                r'\brel\s*=\s*(?:"next"|next)(?=[\s,;]|$)',
                response.headers.get("Link", ""), re.I,
            ) is not None
            if len(body) > 1048576 or (not (paged_checks or paged_records) and has_next):
                raise Denied("api_page_incomplete")
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise Denied("github_transport_unknown") from exc
    try:
        result = json.loads(body.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise Denied("api_payload_invalid") from exc
    if paged_records and has_next and (type(result) is not list or len(result) < 100):
        raise Denied("api_short_page_with_next_link")
    # The same contradiction is unsafe for check-runs: total_count may report
    # all five required checks as success while Link advertises more attempts.
    if paged_checks and has_next:
        if (type(result) is not dict
                or type(result.get("check_runs")) is not list
                or type(result.get("total_count")) is not int):
            raise Denied("api_check_page_link_unverifiable")
        # Link rel=next overrides any apparently-complete total_count.
        # Even a full 100-row page cannot prove a terminal inventory if
        # GitHub says another page exists beyond the declared total.
        page = int(path.rsplit("page=", 1)[1])
        if (len(result["check_runs"]) < 100
                or result["total_count"] <= page * 100):
            raise Denied("api_check_page_next_link_contradicts_total")
    if include_link:
        if not paged_records or type(result) is not list:
            raise Denied("api_page_link_context_invalid")
        return result, has_next
    return result



def get_paginated_records(token, endpoint):
    """Read bounded complete GitHub REST list pages, fail closed on drift.

    Applies to PR files, PR reviews/inline comments, PR Issue comments,
    lease Issue comments and release Issue comments. A full page is never
    assumed terminal; two scans are required when the boundary is reached.
    """
    if (type(endpoint) is not str or re.fullmatch(
            r"/repos/pl0n3r/Factory/(?:pulls/[1-9][0-9]*/(?:files|reviews|comments)"
            r"|issues/[1-9][0-9]*/comments|commits/[0-9a-f]{40}/statuses)", endpoint) is None):
        raise Denied("paginated_endpoint_untrusted")

    def scan():
        rows, seen = [], set()
        for page in range(1, 6):
            page_rows, has_next = get(
                token, endpoint + f"?per_page=100&page={page}", include_link=True
            )
            if (type(page_rows) is not list or len(page_rows) > 100
                    or type(has_next) is not bool):
                raise Denied("record_page_invalid")
            # GitHub's Link header is an evidence claim, not decoration.
            # Never accept an empty advertised follow-up as a complete
            # inventory: a high/critical review could have been omitted.
            if page > 1 and not page_rows:
                raise Denied("record_announced_next_page_empty")
            if has_next and len(page_rows) != 100:
                raise Denied("record_page_link_contradictory")
            for row in page_rows:
                if type(row) is not dict:
                    raise Denied("record_page_identity_duplicate_or_missing")
                if endpoint.endswith("/files"):
                    # /pulls/{number}/files supplies filename, NOT an ID.
                    value = row.get("filename")
                    if type(value) is not str or not value:
                        raise Denied("record_page_identity_duplicate_or_missing")
                    key = ("file", value)
                else:
                    value = row.get("id")
                    if type(value) is not int or value <= 0:
                        raise Denied("record_page_identity_duplicate_or_missing")
                    key = ("id", value)
                if key in seen:
                    raise Denied("record_page_identity_duplicate_or_missing")
                seen.add(key)
            rows.extend(page_rows)
            if not has_next:
                if len(page_rows) == 100:
                    # A full page is ambiguous if GitHub omits Link rel=next:
                    # page 2 may contain a severe review/finding not yet read.
                    # Independently check the next bounded page rather than
                    # trusting a missing pagination header as completion.
                    if page == 5:
                        raise Denied("record_inventory_over_bound")
                    probe_rows, probe_more = get(
                        token, endpoint + f"?per_page=100&page={page + 1}",
                        include_link=True,
                    )
                    if (type(probe_rows) is not list
                            or type(probe_more) is not bool
                            or probe_rows or probe_more):
                        raise Denied("record_page_missing_next_link")
                return rows
        raise Denied("record_inventory_over_bound")

    first = scan()
    if len(first) >= 100 and first != scan():
        raise Denied("record_inventory_changed_between_reads")
    return first


def get_check_runs(token, root, expected):
    """Read up to 500 exact-HEAD check runs, rejecting split/unstable pages.

    GitHub keeps past attempts on the same SHA. One page can omit required
    evidence; concatenating moving pages can omit a newly failing run. For
    multi-page inventories require two byte-equivalent bounded scans.
    """
    if type(expected) is not str or HEX_SHA.fullmatch(expected) is None:
        raise Denied("check_head_invalid")
    path = root + f"/commits/{expected}/check-runs?per_page=100"

    def scan():
        total = None
        rows = []
        seen = set()
        for page_number in range(1, 6):
            response = get(token, path + f"&page={page_number}")
            if (type(response) is not dict
                    or type(response.get("total_count")) is not int
                    or not 0 <= response["total_count"] <= 500
                    or type(response.get("check_runs")) is not list):
                raise Denied("check_inventory_invalid")
            if total is None:
                total = response["total_count"]
            if response["total_count"] != total:
                raise Denied("check_inventory_count_changed")
            page_rows = response["check_runs"]
            required_length = min(100, total - len(rows))
            if required_length <= 0 or len(page_rows) != required_length:
                # Empty inventores are still complete (and the required-check
                # verifier will fail); no other short page is safe to accept.
                if not (page_number == 1 and total == 0 and not page_rows):
                    raise Denied("check_inventory_page_truncated")
            for row in page_rows:
                if (type(row) is not dict or type(row.get("id")) is not int
                        or row["id"] <= 0 or row["id"] in seen):
                    raise Denied("check_inventory_duplicate_or_invalid_id")
                seen.add(row["id"])
            rows.extend(page_rows)
            if len(rows) == total:
                # A declared exact-full boundary (100, 200, ...) with no
                # rel=next may hide a later failed check-run. Independently
                # probe the next page before treating this inventory as final.
                if total and total % 100 == 0:
                    if page_number == 5:
                        raise Denied("check_inventory_exceeds_bound")
                    probe = get(token, path + f"&page={page_number + 1}")
                    if (type(probe) is not dict
                            or type(probe.get("total_count")) is not int
                            or probe["total_count"] != total
                            or type(probe.get("check_runs")) is not list
                            or probe["check_runs"]):
                        raise Denied("check_page_missing_next_link")
                return {"total_count": total, "check_runs": rows}
        raise Denied("check_inventory_exceeds_bound")

    first = scan()
    if first["total_count"] >= 100 and first != scan():
        raise Denied("check_inventory_changed_between_reads")
    return first



class _NoSonarRedirect(HTTPRedirectHandler):
    """Do not forward a Sonar Bearer token to a redirect target."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _NoGitHubRedirect(_NoSonarRedirect):
    """Refuse GitHub API redirects instead of forwarding GH_TOKEN."""


def sonar_api_get(token, route, params):
    """Read-only authenticated SonarQube Cloud query; no user-controlled host."""
    if type(token) is not str or not token.strip():
        raise Denied("sonar_token_missing")
    request = Request(
        "https://sonarcloud.io/api/" + route + "?" + urlencode(params),
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/json",
                 "User-Agent": "factory-sonar-security-gate/1"})
    try:
        with build_opener(_NoSonarRedirect).open(request, timeout=12) as response:
            raw = response.read(1048577)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise Denied("sonar_transport_unknown") from exc
    if len(raw) > 1048576:
        raise Denied("sonar_payload_too_large")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise Denied("sonar_payload_invalid") from exc
    if type(result) is not dict:
        raise Denied("sonar_payload_invalid")
    return result


def get_sonar_evidence(number, expected):
    """Pin SonarCloud PR analysis SHA, enumerate every new unresolved issue."""
    token = os.environ.get("SONAR_TOKEN")
    data = sonar_api_get(token, "project_pull_requests/list",
                         {"project": "pl0n3r_factory"})
    prs = data.get("pullRequests")
    if type(prs) is not list or len(prs) > MAX_SONAR_PR_INVENTORY:
        raise Denied("sonar_pr_inventory_unknown")
    matches = [x for x in prs if type(x) is dict and x.get("key") == str(number)]
    if len(matches) != 1:
        raise Denied("sonar_pr_identity_unknown")
    pr = matches[0]
    commit = pr.get("commit")
    if (type(commit) is not dict or commit.get("sha") != expected
            or pr.get("base") != "main"):
        raise Denied("sonar_analysis_sha_unknown_or_stale")
    all_issues = []
    count = None
    for page in range(1, 6):
        response = sonar_api_get(token, "issues/search", {
            "componentKeys": "pl0n3r_factory", "pullRequest": str(number),
            "inNewCodePeriod": "true", "resolved": "false",
            "ps": "100", "p": str(page)})
        paging = response.get("paging")
        entries = response.get("issues")
        if (type(paging) is not dict or type(entries) is not list
                or type(paging.get("total")) is not int
                or paging.get("pageIndex") != page
                or paging.get("pageSize") != 100):
            raise Denied("sonar_issue_page_unknown")
        if count is None:
            count = paging["total"]
        if count != paging["total"] or not 0 <= count <= 500:
            raise Denied("sonar_issue_inventory_incomplete")
        needed = min(100, count - len(all_issues))
        if len(entries) != needed:
            raise Denied("sonar_issue_page_incomplete")
        all_issues.extend(entries)
        if len(all_issues) == count:
            # Re-check the analysis identity after the paginated issue read.
            # Fail closed if a later Sonar scan changed the source during GETs.
            after = sonar_api_get(token, "project_pull_requests/list",
                                  {"project": "pl0n3r_factory"})
            later = after.get("pullRequests")
            if type(later) is not list or len(later) > MAX_SONAR_PR_INVENTORY:
                raise Denied("sonar_pr_analysis_changed_during_pagination")
            matches_after = [row for row in later
                             if type(row) is dict and row.get("key") == str(number)]
            if len(matches_after) != 1 or matches_after[0] != pr:
                raise Denied("sonar_pr_analysis_changed_during_pagination")
            return {"project": "pl0n3r_factory",
                    "pull_request": str(number),
                    "sha": expected, "total": count, "issues": all_issues}
    raise Denied("sonar_issue_inventory_over_bound")


def snapshot(token, number, expected):
    root = "/repos/" + REPO
    pr = get(token, root + f"/pulls/{number}")
    files = get_paginated_records(token, root + f"/pulls/{number}/files")
    switch = get(token, "/repos/pl0n3r/Factory/issues/767")
    checks = get_check_runs(token, root, expected)
    sonar_evidence = get_sonar_evidence(number, expected)
    commit_status = get(token, root + f"/commits/{expected}/status")
    status_history = get_paginated_records(token, root + f"/commits/{expected}/statuses")
    reviews = get_paginated_records(token, root + f"/pulls/{number}/reviews")
    comments = get_paginated_records(token, root + f"/pulls/{number}/comments")
    issue_comments = get_paginated_records(token, root + f"/issues/{number}/comments")
    head = pr.get("head") if type(pr) is dict else None
    branch = head.get("ref") if type(head) is dict else None
    match = CANONICAL_BRANCH.fullmatch(branch) if type(branch) is str else None
    if match is None:
        raise Denied("reservation_branch_invalid")
    issue_number = int(match.group(1))
    issue = get(token, root + f"/issues/{issue_number}")
    lease_comments = get_paginated_records(token, root + f"/issues/{issue_number}/comments")
    task = parse_marker(issue.get("body") if type(issue) is dict else None,
                        TASK_HEADER, TASK_MARKER)
    depends = task.get("depends_on") if type(task) is dict else None
    if (type(depends) is not list or len(depends) > 20
            or any(type(n) is not int or n <= 0 for n in depends)):
        raise Denied("reservation_deps_invalid")
    dependencies = [get(token, root + f"/issues/{n}") for n in depends]
    main = get(token, root + "/branches/main")
    main_sha = main.get("commit", {}).get("sha") if type(main) is dict else None
    if type(main_sha) is not str or HEX_SHA.fullmatch(main_sha) is None:
        raise Denied("main_sha_unknown")
    compare = get(token, root + "/compare/" + main_sha + "..." + expected)
    # Canonical release windows may appear in Issues indexed only by title,
    # especially when their marker is malformed/spaced. Search both trusted
    # discovery surfaces and deny drift in overlapping authenticated results.
    queries = (
        'repo:pl0n3r/Factory is:issue "factory-release-window" in:body',
        'repo:pl0n3r/Factory is:issue "decisión en espera" in:title',
    )
    by_number = {}
    for query in queries:
        search = get(token, "/search/issues?q=" + quote(query) + "&per_page=100")
        if (type(search) is not dict or search.get("incomplete_results") is not False
                or type(search.get("total_count")) is not int
                or not 0 <= search["total_count"] <= 100
                or type(search.get("items")) is not list
                or len(search["items"]) != search["total_count"]):
            raise Denied("release_gate_search_incomplete")
        seen = set()
        for window_issue in search["items"]:
            if (type(window_issue) is not dict
                    or type(window_issue.get("number")) is not int
                    or window_issue["number"] <= 0
                    or window_issue["number"] in seen
                    or "pull_request" in window_issue
                    or type(window_issue.get("body")) is not str):
                raise Denied("release_gate_identity_invalid")
            number = window_issue["number"]
            seen.add(number)
            previous = by_number.get(number)
            if previous is not None:
                if any(previous.get(key) != window_issue.get(key)
                       for key in ("body", "state", "title", "updated_at")):
                    raise Denied("release_gate_search_changed")
            else:
                by_number[number] = window_issue
    windows = []
    for window_issue in by_number.values():
        # A documentation hit without a release marker cannot authorize
        # anything; an alternate spelling WITH window intent remains in the
        # inventory for fail-closed parsing by verify_freeze.
        body = window_issue["body"]
        if not WINDOW_HEADER.search(body):
            continue
        if len(windows) >= 100:
            raise Denied("release_window_inventory_over_bound")
        rows = get_paginated_records(token, root + f"/issues/{window_issue['number']}/comments")
        if type(rows) is not list:
            raise Denied("release_comments_invalid")
        windows.append({"issue": window_issue, "comments": rows})
    return {"switch": switch, "pr": pr, "issue": issue, "lease_comments": lease_comments,
            "dependencies": dependencies, "files": files, "compare": compare, "checks": checks, "commit_status": commit_status,
            "status_history": status_history, "sonar_evidence": sonar_evidence,
            "reviews": reviews,
            "comments": comments, "issue_comments": issue_comments, "windows": windows,
            "main_sha": main_sha}



# workflow_run is privileged. The event only wakes the checker; it never grants
# authority to merge. The exact PR HEAD is read again from GitHub, and the
# complete V3 / CI / review / release guard still runs twice before merging.
TRUSTED_WORKFLOW_RUNS = frozenset({"CI factory", "Sonar CI-based", "Evidencia CodeQL"})


def validate_workflow_run_event(event):
    """Return the sole canonical issue/PR number or deny an untrusted trigger."""
    if type(event) is not dict or event.get("action") != "completed":
        raise Denied("workflow_run_action_invalid")
    repo = event.get("repository")
    run = event.get("workflow_run")
    if (type(repo) is not dict or repo.get("full_name") != REPO
            or repo.get("default_branch") != "main" or type(run) is not dict
            or run.get("name") not in TRUSTED_WORKFLOW_RUNS
            or run.get("event") != "pull_request"
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or type(run.get("repository")) is not dict
            or run["repository"].get("full_name") != REPO
            or type(run.get("head_repository")) is not dict
            or run["head_repository"].get("full_name") != REPO
            or type(run.get("head_sha")) is not str
            or HEX_SHA.fullmatch(run["head_sha"]) is None):
        raise Denied("workflow_run_untrusted_or_incomplete")
    ref = run.get("head_branch")
    match = CANONICAL_BRANCH.fullmatch(ref) if type(ref) is str else None
    pull_requests = run.get("pull_requests")
    if (match is None or type(pull_requests) is not list
            or len(pull_requests) != 1
            or type(pull_requests[0]) is not dict
            or type(pull_requests[0].get("number")) is not int
            or pull_requests[0]["number"] <= 0):
        raise Denied("workflow_run_pr_mapping_ambiguous")
    # GitHub PR numbers are independent of their associated Issue numbers.
    # The Issue identity comes from ref; the PR is authenticated via REST below.
    return pull_requests[0]["number"], ref


def resolve_workflow_run(token, event):
    """Resolve current HEAD via authenticated GitHub, never the event's SHA."""
    number, ref = validate_workflow_run_event(event)
    pr = get(token, f"/repos/{REPO}/pulls/{number}")
    if type(pr) is not dict:
        raise Denied("workflow_run_pr_unknown")
    head, base = pr.get("head"), pr.get("base")
    if (pr.get("number") != number or pr.get("state") != "open"
            or pr.get("draft") is not False or type(head) is not dict
            or type(base) is not dict or head.get("ref") != ref
            or base.get("ref") != "main"
            or type(head.get("repo")) is not dict
            or head["repo"].get("full_name") != REPO
            or head["repo"].get("fork") is not False
            or type(head.get("sha")) is not str
            or HEX_SHA.fullmatch(head["sha"]) is None):
        raise Denied("workflow_run_pr_identity_changed")
    return number, head["sha"]



def validate_pull_request_review_event(event):
    """Accept review submissions only as a wake-up signal for a current internal PR."""
    if type(event) is not dict or event.get("action") != "submitted":
        raise Denied("pull_request_review_action_invalid")
    repo = event.get("repository")
    review = event.get("review")
    pr = event.get("pull_request")
    if (type(repo) is not dict or repo.get("full_name") != REPO
            or repo.get("default_branch") != "main"
            or type(review) is not dict
            or type(review.get("state")) is not str
            or review.get("state") not in {"approved", "changes_requested", "commented"}
            or type(review.get("user")) is not dict
            or type(review["user"].get("login")) is not str
            or not review["user"]["login"]
            or type(pr) is not dict):
        raise Denied("pull_request_review_untrusted_or_incomplete")
    number = pr.get("number")
    head, base = pr.get("head"), pr.get("base")
    if (type(number) is not int or isinstance(number, bool) or number <= 0
            or pr.get("state") != "open" or pr.get("draft") is not False
            or type(head) is not dict or type(base) is not dict
            or type(head.get("ref")) is not str
            or CANONICAL_BRANCH.fullmatch(head["ref"]) is None
            or type(head.get("sha")) is not str
            or HEX_SHA.fullmatch(head["sha"]) is None
            or type(head.get("repo")) is not dict
            or head["repo"].get("full_name") != REPO
            or head["repo"].get("fork") is not False
            or base.get("ref") != "main"
            or (type(base.get("repo")) is dict
                and base["repo"].get("full_name") != REPO)):
        raise Denied("pull_request_review_pr_mapping_invalid")
    return number, head["ref"]


def resolve_pull_request_review(token, event):
    """Resolve current HEAD from authenticated REST; event SHAs never grant authority."""
    number, ref = validate_pull_request_review_event(event)
    pr = get(token, f"/repos/{REPO}/pulls/{number}")
    if type(pr) is not dict:
        raise Denied("pull_request_review_pr_unknown")
    head, base = pr.get("head"), pr.get("base")
    if (pr.get("number") != number or pr.get("state") != "open"
            or pr.get("draft") is not False or type(head) is not dict
            or type(base) is not dict or head.get("ref") != ref
            or base.get("ref") != "main"
            or type(head.get("repo")) is not dict
            or head["repo"].get("full_name") != REPO
            or head["repo"].get("fork") is not False
            or type(head.get("sha")) is not str
            or HEX_SHA.fullmatch(head["sha"]) is None):
        raise Denied("pull_request_review_pr_identity_changed")
    return number, head["sha"]

def main():
    try:
        token = os.environ.get("GH_TOKEN")
        resolver_modes = {
            "--resolve-workflow-run": resolve_workflow_run,
            "--resolve-pull-request-review": resolve_pull_request_review,
        }
        if len(sys.argv) == 2 and sys.argv[1] in resolver_modes:
            mode = sys.argv[1]
            if (not token
                    or str(os.environ.get("GITHUB_REPOSITORY") or "") != REPO):
                raise Denied("event_resolver_environment_invalid")
            event_path = os.environ.get("GITHUB_EVENT_PATH")
            if not event_path:
                raise Denied("event_resolver_event_missing")
            with open(event_path, encoding="utf-8") as stream:
                event = json.load(stream, object_pairs_hook=unique)
            number, sha = resolver_modes[mode](token, event)
            print(f"pr_number={number}")
            print(f"pr_sha={sha}")
            print(f"pr_url=https://github.com/{REPO}/pull/{number}")
            return 0
        if len(sys.argv) != 1:
            raise Denied("unexpected_arguments")
        sha = os.environ.get("PR_SHA", "")
        number = int(os.environ.get("PR_NUMBER", "0"))
        if (not token or str(os.environ.get("GITHUB_REPOSITORY") or "").lower() != REPO.lower()
                or HEX_SHA.fullmatch(sha) is None or not 1 <= number <= 1000000):
            raise Denied("environment_invalid")
        # Dos lecturas independientes antes de habilitar el merge. Sin escribir checks.
        for _ in range(2):
            verify(snapshot(token, number, sha), sha, datetime.now(timezone.utc))
    except (Denied, ValueError, TypeError, KeyError, OSError) as exc:
        reason = str(exc) if type(exc) is Denied else "input_invalid"
        print("AUTOMERGE_DENIED: " + reason, file=sys.stderr)
        return 1
    print("AUTOMERGE_PREFLIGHT_OK " + sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
