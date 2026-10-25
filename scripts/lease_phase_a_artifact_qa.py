#!/usr/bin/env python3
"""Inspector local de ZIPs de Fase A. NUNCA acredita origen ni autoriza release."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile
import zlib
from typing import Any

MAX_ZIP = 65536
MAX_JSON = 32768
FILENAME = "lease-audit-evidence.json"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_RUN = re.compile(r"[1-9][0-9]*\Z")
_REASON = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
_ROW_KEYS = frozenset({
    "issue", "state", "action", "reason", "activity_age_minutes",
    "activity_source", "release_authorized", "lock_verified",
    "cas_verified", "mutations",
})
_SOURCES = {None, "reservation_marker", "workflow_push", "issue_comment", "repository_push"}
_WAITS = {"activity_window", "recovery_grace", "protected_or_active_work"}


class ArtifactQAError(ValueError):
    """Evidencia inválida; nunca contiene bytes del ZIP ni secretos."""


def _pairs_unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactQAError("duplicate_json_key")
        result[key] = value
    return result


def _json(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ArtifactQAError("nonfinite_number")))
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        if isinstance(exc, ArtifactQAError):
            raise
        raise ArtifactQAError("invalid_json") from None


def _metadata(metadata: Any) -> tuple[int, str, str]:
    if type(metadata) is not dict or set(metadata) != {
        "id", "repository", "head_sha", "event", "status", "conclusion"
    }:
        raise ArtifactQAError("metadata_shape")
    run, repo, sha = metadata["id"], metadata["repository"], metadata["head_sha"]
    if (type(run) is not int or run <= 0 or type(repo) is not str or not _REPO.fullmatch(repo)
            or type(sha) is not str or not _SHA.fullmatch(sha)
            or metadata["event"] != "schedule" or metadata["status"] != "completed"
            or metadata["conclusion"] != "success"):
        raise ArtifactQAError("metadata_identity")
    return run, repo, sha


def _validate_rows(rows: Any) -> int:
    if type(rows) is not list or not 1 <= len(rows) <= 10:
        raise ArtifactQAError("row_count")
    seen = set()
    releases = 0
    for row in rows:
        if type(row) is not dict or set(row) != _ROW_KEYS:
            raise ArtifactQAError("row_schema")
        issue, action, reason = row["issue"], row["action"], row["reason"]
        age, source = row["activity_age_minutes"], row["activity_source"]
        if (type(issue) is not int or issue <= 0 or issue in seen
                or row["state"] != "read_only" or action not in ("wait", "mark_recovery", "release")
                or type(reason) is not str or not _REASON.fullmatch(reason)
                or row["release_authorized"] is not False
                or row["lock_verified"] is not False or row["cas_verified"] is not False
                or type(row["mutations"]) is not int or row["mutations"] != 0
                or (age is not None and (type(age) is not int or not 0 <= age <= 525600))
                or (source is not None and type(source) is not str)
                or source not in _SOURCES):
            raise ArtifactQAError("row_not_readonly")
        if action == "mark_recovery" and (reason != "inactive_30_minutes" or type(age) is not int or age < 30 or source is None):
            raise ArtifactQAError("invalid_recovery_candidate")
        if action == "release" and (reason != "inactive_after_recovery_grace" or type(age) is not int or age < 40 or source is None):
            raise ArtifactQAError("invalid_release_candidate")
        if action == "wait" and (reason not in _WAITS
                or reason == "activity_window" and (type(age) is not int or age >= 30 or source is None)
                or reason == "recovery_grace" and (type(age) is not int or age < 30 or source is None)):
            raise ArtifactQAError("invalid_wait_candidate")
        seen.add(issue)
        releases += int(action == "release")
    return releases


def inspect_artifact(zip_bytes: Any, metadata: Any) -> dict[str, Any]:
    """Valida estructura e identidad declarada; NO autentica su procedencia REST."""
    run, repo, sha = _metadata(metadata)
    if type(zip_bytes) is not bytes or not 0 < len(zip_bytes) <= MAX_ZIP:
        raise ArtifactQAError("zip_size")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            items = archive.infolist()
            if len(items) != 1 or items[0].filename != FILENAME:
                raise ArtifactQAError("zip_entries")
            item = items[0]
            mode = (item.external_attr >> 16) & 0o170000
            if (item.is_dir() or mode == stat.S_IFLNK
                    or mode not in (0, stat.S_IFREG)
                    or item.flag_bits & 1
                    or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or not 1 < item.file_size <= MAX_JSON or item.compress_size <= 0
                    or item.file_size > item.compress_size * 64):
                raise ArtifactQAError("unsafe_zip_entry")
            with archive.open(item) as stream:
                data = stream.read(MAX_JSON + 1)
            if len(data) != item.file_size or len(data) > MAX_JSON:
                raise ArtifactQAError("zip_expansion")
    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError, NotImplementedError, zlib.error):
        raise ArtifactQAError("corrupt_zip") from None
    manifest = _json(data)
    if type(manifest) is not dict or set(manifest) != {
        "schema_version", "repository", "head_sha", "run_id", "status",
        "terminal_certified", "release_authorized", "mutations",
        "valid_observations", "unknown_observations", "issues",
    }:
        raise ArtifactQAError("manifest_schema")
    rows = manifest["issues"]
    if (type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
            or manifest["repository"] != repo or manifest["head_sha"] != sha
            or type(manifest["run_id"]) is not str or not _RUN.fullmatch(manifest["run_id"])
            or manifest["run_id"] != str(run)
            or manifest["status"] != "candidate_terminal"
            or manifest["terminal_certified"] is not False or manifest["release_authorized"] is not False
            or type(manifest["mutations"]) is not int or manifest["mutations"] != 0
            or type(manifest["valid_observations"]) is not int
            or type(manifest["unknown_observations"]) is not int
            or manifest["unknown_observations"] != 0
            or type(rows) is not list or manifest["valid_observations"] != len(rows)):
        raise ArtifactQAError("manifest_not_candidate")
    releases = _validate_rows(rows)
    return {
        "status": "MATCHED_CANDIDATE",
        "sha256_json": hashlib.sha256(data).hexdigest(),
        "repository": repo, "run_id": run, "head_sha": sha,
        "valid_observations": len(rows), "hypothetical_releases": releases,
        "artifact_attested": False, "terminal_certified": False,
        "release_authorized": False, "mutations": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        for path, cap in ((args.artifact, MAX_ZIP), (args.run_metadata, 4096)):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
                raise ArtifactQAError("invalid_local_file")
        result = inspect_artifact(args.artifact.read_bytes(), _json(args.run_metadata.read_bytes()))
    except (ArtifactQAError, OSError):
        print(json.dumps({"status": "INVALID_EVIDENCE", "release_authorized": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
