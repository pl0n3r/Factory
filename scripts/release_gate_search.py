#!/usr/bin/env python3
"""Fail-closed cross-check of paginated release-gate Issue search snapshots.

The workflow already reads Search Issues twice. This independent guard ensures
both page bodies represent exactly the normalized inventory passed to freeze.
No API calls or writes to the repository are performed by this module.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PAGE_SIZE = 100
MAX_RESULTS = 200
FIELDS = ("number", "state", "title", "body", "updated_at")


class SearchEvidenceError(ValueError):
    """The remote inventory is not sufficiently complete to decide a freeze."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous JSON, including duplicate keys in nested issue records."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SearchEvidenceError("duplicate evidence field")
        result[key] = value
    return result


def _issue(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("pull_request") is not None:
        raise SearchEvidenceError("invalid issue record")
    number, state = value.get("number"), value.get("state")
    title, body, stamp = (value.get(key) for key in ("title", "body", "updated_at"))
    if (type(number) is not int or number <= 0 or state not in ("open", "closed")
            or type(title) is not str or not title.strip()
            or type(body) is not str or type(stamp) is not str):
        raise SearchEvidenceError("noncanonical issue fields")
    try:
        instant = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
        if instant.strftime("%Y-%m-%dT%H:%M:%SZ") != stamp:
            raise ValueError("noncanonical UTC")
    except ValueError as exc:
        raise SearchEvidenceError("noncanonical issue timestamp") from exc
    return {key: value[key] for key in FIELDS}


def verified_inventory(first: Any, second: Any, published: Any) -> list[dict[str, Any]]:
    """Reject missing, contradictory, incomplete, duplicated or changed pages."""
    if not isinstance(first, dict):
        raise SearchEvidenceError("missing first page")
    count = first.get("total_count")
    if type(count) is not int or not 0 <= count <= MAX_RESULTS:
        raise SearchEvidenceError("invalid or excessive result count")
    expected_pages = 2 if count > PAGE_SIZE else 1
    if (expected_pages == 2 and not isinstance(second, dict)) or (
            expected_pages == 1 and second is not None):
        raise SearchEvidenceError("missing or unexpected second page")
    pages = (first, second) if expected_pages == 2 else (first,)
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, page in enumerate(pages):
        if (not isinstance(page, dict) or page.get("incomplete_results") is not False
                or type(page.get("total_count")) is not int
                or page["total_count"] != count or type(page.get("items")) is not list):
            raise SearchEvidenceError("incomplete or inconsistent search page")
        items = page["items"]
        if len(items) != min(PAGE_SIZE, count - index * PAGE_SIZE):
            raise SearchEvidenceError("truncated or oversized search page")
        for item in items:
            normalized = _issue(item)
            if normalized["number"] in seen:
                raise SearchEvidenceError("duplicate issue number")
            seen.add(normalized["number"])
            result.append(normalized)
    if len(result) != count:
        raise SearchEvidenceError("incomplete issue inventory")
    if (type(published) is not list or len(published) != count
            or any(type(row) is not dict or set(row) != set(FIELDS)
                   for row in published) or published != result):
        raise SearchEvidenceError("verified inventory differs from raw pages")
    return result



# CLI evidence is produced by the protected release workflow. Never turn an
# arbitrary command-line path into a filesystem read: the three arguments must
# match one complete, fixed snapshot from the same pass.
_TRUSTED_SNAPSHOTS = {
    ("/tmp/release-search-p1-1.json",
     "/tmp/release-search-p2-1.json",
     "/tmp/release-search-verified-1.json"): (
        Path("/tmp/release-search-p1-1.json"),
        Path("/tmp/release-search-p2-1.json"),
        Path("/tmp/release-search-verified-1.json")),
    ("/tmp/release-search-p1-2.json",
     "/tmp/release-search-p2-2.json",
     "/tmp/release-search-verified-2.json"): (
        Path("/tmp/release-search-p1-2.json"),
        Path("/tmp/release-search-p2-2.json"),
        Path("/tmp/release-search-verified-2.json")),
}
_MAX_EVIDENCE_BYTES = 2_000_000


def _read_trusted_evidence(path: Path) -> Any:
    """Only a regular, non-symlink snapshot; bounded even if it grows during IO."""
    # O_NONBLOCK stops a replaced FIFO from hanging before its type is checked.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_EVIDENCE_BYTES:
            raise SearchEvidenceError("untrusted evidence file")
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            fd = -1
            raw = stream.read(_MAX_EVIDENCE_BYTES + 1)
        if len(raw) > _MAX_EVIDENCE_BYTES:
            raise SearchEvidenceError("oversized evidence file")
        return json.loads(raw, object_pairs_hook=_unique_object)
    finally:
        if fd >= 0:
            os.close(fd)


def _main(paths: list[str]) -> int:
    if len(paths) != 3:
        raise SearchEvidenceError("expected page-one, page-two and verified-inventory files")
    trusted = _TRUSTED_SNAPSHOTS.get(tuple(paths))
    if trusted is None:
        raise SearchEvidenceError("invalid evidence file path")
    try:
        p1, p2, inventory = (_read_trusted_evidence(path) for path in trusted)
    except (OSError, ValueError, UnicodeError) as exc:
        raise SearchEvidenceError("unreadable search evidence") from exc
    verified_inventory(p1, p2, inventory)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main(sys.argv[1:]))
    except SearchEvidenceError as exc:
        print("::error::Search Issues evidence rejected: " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
