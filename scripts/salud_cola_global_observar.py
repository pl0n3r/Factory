#!/usr/bin/env python3
"""Censo horario global GET-only. La evidencia no concede autoridad de despacho."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from scripts.salud_cola import QueueHealthError, diagnose_queue
from scripts.salud_cola_github import (
    GitHubPageError, MAX_PAYLOAD_BYTES, REPOSITORIES, parse_github_issue_page,
    require_stable_github_sweeps,
)
from scripts.salud_cola_snapshot import SnapshotError, assemble_inventory

ROOT = "https://api.github.com"
MAX_PAGES = 24
MAX_SECONDS = 120


class ObservationError(ValueError):
    """Mensajes exclusivamente internos, nunca respuestas HTTP crudas."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ObservationError("redirect_rejected")


def quota(limit, remaining):
    if (type(limit) is not int or type(remaining) is not int
            or not 0 < limit <= 100000000 or not 0 <= remaining <= limit):
        raise ObservationError("quota_unknown")
    if remaining * 5 < limit or (limit >= 5000 and remaining < 1200):
        raise ObservationError("low_quota")
    return {"limit": limit, "remaining": remaining}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GitHubReader:
    """Solo construye URLs canónicas; no sigue ni ejecuta URLs Link."""
    def __init__(self, token, *, opener=None, clock=time.monotonic):
        if not token:
            raise ObservationError("token_unavailable")
        self.token = token
        self.opener = opener if opener is not None else build_opener(ProxyHandler({}), NoRedirect())
        self.clock = clock
        self.deadline = clock() + MAX_SECONDS

    def check_window(self):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise ObservationError("window_expired")
        return remaining

    def get(self, repo=None, page=None):
        if repo is None and page is None:
            path = "/rate_limit"
        elif repo in REPOSITORIES and page is None:
            path = f"/repos/pl0n3r/{repo}"
        elif repo in REPOSITORIES and type(page) is int and 1 <= page <= MAX_PAGES:
            path = f"/repos/pl0n3r/{repo}/issues?state=open&per_page=100&page={page}"
        else:
            raise ObservationError("endpoint_forbidden")
        url = ROOT + path
        req = Request(url, method="GET", headers={
            "Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
            "User-Agent": "factory-global-queue-observer", "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with self.opener.open(req, timeout=min(10, self.check_window())) as res:
                if res.geturl() != url:
                    raise ObservationError("effective_url_mismatch")
                if res.status != 200:
                    raise ObservationError("http_non_200")
                links = res.headers.get_all("Link") or []
                if len(links) > 1:
                    raise ObservationError("ambiguous_link")
                if repo is not None:
                    headers = [res.headers.get_all(key) or [] for key in
                               ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Resource")]
                    if any(len(values) != 1 for values in headers):
                        raise ObservationError("quota_unknown")
                    limit, remaining, resource = (values[0] for values in headers)
                    if (resource != "core" or not re.fullmatch(r"[0-9]{1,9}", limit)
                            or not re.fullmatch(r"[0-9]{1,9}", remaining)):
                        raise ObservationError("quota_unknown")
                    quota(int(limit), int(remaining))
                raw = res.read(MAX_PAYLOAD_BYTES + 1)
        except HTTPError as error:
            reason = {403: "http_forbidden_or_quota", 429: "http_rate_limited"}.get(
                error.code, "http_non_200")
            error.close()
            raise ObservationError(reason) from None
        self.check_window()
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise ObservationError("response_oversized")
        payload = json.loads(raw.decode("utf-8"))
        return {"request_url": url, "status_code": 200,
                "link_header": links[0] if links else None, "payload": payload}

    def budget(self):
        value = self.get()["payload"]
        try:
            core = value["resources"]["core"]
            return quota(core["limit"], core["remaining"])
        except (KeyError, TypeError):
            raise ObservationError("quota_unknown") from None


def capture(reader, repo):
    meta = reader.get(repo)["payload"]
    name = f"pl0n3r/{repo}"
    if (type(meta) is not dict or meta.get("full_name") != name
            or type(meta.get("id")) is not int or meta["id"] <= 0
            or meta.get("archived") is not False):
        raise ObservationError("repository_identity_unknown")
    pages = []
    for page in range(1, MAX_PAGES + 1):
        raw = reader.get(repo, page)
        projection = parse_github_issue_page(
            repo, page, raw["request_url"], raw["status_code"],
            raw["link_header"], raw["payload"])
        # Revalidate the source identity of each row, then discard free text.
        endpoint = f"{ROOT}/repos/{name}"
        minimal = []
        for item, safe in zip(raw["payload"], projection["issues"], strict=True):
            number = safe["number"]
            if (item.get("repository_url") != endpoint
                    or item.get("url") != f"{endpoint}/issues/{number}"):
                raise ObservationError("issue_identity_unknown")
            row = {"number": number, "state": "open",
                   "labels": [{"name": label} for label in safe["labels"]]}
            if safe["pull_request"]:
                if item["pull_request"].get("url") != f"{endpoint}/pulls/{number}":
                    raise ObservationError("pull_request_identity_unknown")
                row["pull_request"] = {"url": f"{endpoint}/pulls/{number}"}
            minimal.append(row)
        pages.append({**raw, "payload": minimal})
        if not projection["has_next"]:
            return meta["id"], pages
    raise ObservationError("pagination_bound")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def observe(reader, policy_sha):
    started = utc_now()
    result = {"version": 1, "scope": list(REPOSITORIES), "policy_sha": None,
              "started_at": started, "writes": 0, "authority": "unchanged",
              "capacity": None, "counts": None, "fingerprints": None}
    try:
        if not isinstance(policy_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", policy_sha):
            raise ObservationError("policy_sha_unknown")
        result["policy_sha"] = policy_sha
        reader.budget()
        first = {repo: capture(reader, repo) for repo in REPOSITORIES}
        reader.budget()
        reports, hashes = [], {}
        for repo in REPOSITORIES:
            identity, pages = capture(reader, repo)
            if identity != first[repo][0]:
                raise ObservationError("repository_identity_drift")
            stable = require_stable_github_sweeps(repo, first[repo][1], pages)
            reports.append(stable)
            hashes[repo] = fingerprint([identity, stable])
        budget = reader.budget()
        reader.check_window()
        diagnosis = diagnose_queue(assemble_inventory(reports, None, budget))
        result.update(status="OBSERVED_GLOBAL_ONLY", reason="capacity_not_observed",
                      fingerprints=hashes, counts={
                          repo: diagnosis["repositories"][repo]["counts"] for repo in REPOSITORIES},
                      open_total=diagnosis["open_total"],
                      available_total=diagnosis["available_total"],
                      blocked_causes=diagnosis["blocked_cause_totals"])
    except ObservationError as error:
        reason = str(error)
        result.update(status="DEFERRED" if reason in ("low_quota", "http_rate_limited")
                      else "UNKNOWN", reason=reason)
    except (GitHubPageError, SnapshotError, QueueHealthError):
        result.update(status="UNKNOWN", reason="incomplete_or_unstable_inventory")
    except (OSError, ValueError, RecursionError):
        result.update(status="UNKNOWN", reason="transport_or_payload_failure")
    result["finished_at"] = utc_now()
    return result


def main():
    if os.environ.get("GITHUB_REPOSITORY") != "pl0n3r/Factory":
        return 2
    try:
        reader = GitHubReader(os.environ.get("GITHUB_TOKEN"))
    except ObservationError:
        # Preserve the typed UNKNOWN envelope for missing authority.
        reader = None
    result = observe(reader, os.environ.get("GITHUB_SHA") if reader else None)
    output = json.dumps(result, sort_keys=True, ensure_ascii=True)
    print(output)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write("\n### Censo global GET-only (no atómico ni autoridad de acción)\n"
                         + "\n```json\n" + output + "\n```\n")
    return 2 if result["status"] == "UNKNOWN" else 0


if __name__ == "__main__":
    sys.exit(main())
