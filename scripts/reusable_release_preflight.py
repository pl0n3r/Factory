#!/usr/bin/env python3
"""Fail-closed preflight of Factory reusable permission envelopes against consumers."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from scripts.reusable_permission_compat import compare_permissions

CANONICAL_CONSUMERS = frozenset(
    {
        "pl0n3r/Condor",
        "pl0n3r/ControlBot",
        "pl0n3r/FactoryRunner",
        "pl0n3r/GrindFlow",
        "pl0n3r/brvtal",
        "pl0n3r/AutoFactory",
    }
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
WORKFLOW_PATH_RE = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")
REUSABLE_REF_RE = re.compile(
    r"^pl0n3r/factory/\.github/workflows/([A-Za-z0-9._-]+\.ya?ml)@v1$",
    re.IGNORECASE,
)
KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MAX_INPUT = 10_000_000
MAX_WORKFLOW_BYTES = 300_000
MAX_WORKFLOWS_PER_REPOSITORY = 100


class ReusableReleasePreflightError(ValueError):
    """Evidence is absent, stale, ambiguous or outside the closed contract."""


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ReusableReleasePreflightError(f"{field} inválido.")
    return value


def _closed_mapping(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ReusableReleasePreflightError(f"{label} fuera del contrato.")
    return value


def _indent(line: str, label: str) -> int:
    prefix = line[: len(line) - len(line.lstrip(" \t"))]
    if "\t" in prefix:
        raise ReusableReleasePreflightError(f"{label}: tabs de indentación no soportados.")
    return len(prefix)


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _mapping_block(
    lines: list[str],
    start: int,
    parent_indent: int,
    label: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    child_indent = parent_indent + 2
    index = start + 1
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        indent = _indent(raw, label)
        if indent <= parent_indent:
            break
        if indent != child_indent:
            raise ReusableReleasePreflightError(
                f"{label}: mapping de permisos anidado/ambiguo."
            )
        body = raw[indent:]
        if ":" not in body:
            raise ReusableReleasePreflightError(f"{label}: entrada de permisos inválida.")
        key, value = body.split(":", 1)
        key = key.strip()
        value = _clean_scalar(value.split(" #", 1)[0])
        if not KEY_RE.fullmatch(key) or not value:
            raise ReusableReleasePreflightError(f"{label}: permiso inválido.")
        if key in result:
            raise ReusableReleasePreflightError(f"{label}: permiso duplicado {key}.")
        result[key] = value
        index += 1
    return result


def _top_level_permissions(lines: list[str], label: str) -> dict[str, str]:
    matches: list[int] = []
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent(raw, label) == 0 and stripped.startswith("permissions:"):
            if stripped != "permissions:":
                raise ReusableReleasePreflightError(
                    f"{label}: permissions escalar no soportado."
                )
            matches.append(index)
    if len(matches) > 1:
        raise ReusableReleasePreflightError(f"{label}: permissions top-level ambiguo.")
    return _mapping_block(lines, matches[0], 0, label) if matches else {}


def _job_blocks(lines: list[str], label: str) -> list[tuple[str, int, int]]:
    jobs_index = None
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent(raw, label) == 0 and stripped == "jobs:":
            if jobs_index is not None:
                raise ReusableReleasePreflightError(f"{label}: jobs ambiguo.")
            jobs_index = index
    if jobs_index is None:
        raise ReusableReleasePreflightError(f"{label}: falta jobs.")

    blocks: list[tuple[str, int, int]] = []
    index = jobs_index + 1
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        indent = _indent(raw, label)
        if indent == 0:
            break
        if indent == 2 and stripped.endswith(":") and ":" not in stripped[:-1]:
            name = stripped[:-1].strip()
            if not KEY_RE.fullmatch(name):
                raise ReusableReleasePreflightError(f"{label}: job inválido.")
            end = index + 1
            while end < len(lines):
                candidate = lines[end]
                candidate_stripped = candidate.strip()
                if not candidate_stripped or candidate_stripped.startswith("#"):
                    end += 1
                    continue
                candidate_indent = _indent(candidate, label)
                if candidate_indent <= 1:
                    break
                if (
                    candidate_indent == 2
                    and candidate_stripped.endswith(":")
                    and ":" not in candidate_stripped[:-1]
                ):
                    break
                end += 1
            blocks.append((name, index, end))
            index = end
            continue
        index += 1

    if not blocks:
        raise ReusableReleasePreflightError(f"{label}: jobs vacío.")
    return blocks


def _job_scalar(
    lines: list[str],
    start: int,
    end: int,
    key: str,
    label: str,
) -> str | None:
    prefix = f"{key}:"
    matches: list[str] = []
    for index in range(start + 1, end):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent(raw, label) != 4 or not stripped.startswith(prefix):
            continue
        value = _clean_scalar(stripped[len(prefix) :].split(" #", 1)[0])
        if not value:
            raise ReusableReleasePreflightError(f"{label}: {key} vacío.")
        matches.append(value)
    if len(matches) > 1:
        raise ReusableReleasePreflightError(f"{label}: {key} ambiguo.")
    return matches[0] if matches else None


def _job_permissions(
    lines: list[str],
    start: int,
    end: int,
    top_level: dict[str, str],
    label: str,
) -> dict[str, str]:
    matches: list[int] = []
    for index in range(start + 1, end):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent(raw, label) == 4 and stripped.startswith("permissions:"):
            if stripped != "permissions:":
                raise ReusableReleasePreflightError(
                    f"{label}: permissions escalar no soportado."
                )
            matches.append(index)
    if len(matches) > 1:
        raise ReusableReleasePreflightError(f"{label}: permissions de job ambiguo.")
    if not matches:
        return dict(top_level)
    return _mapping_block(lines, matches[0], 4, label)


def _caller_invocations(content: str, label: str) -> list[dict[str, Any]]:
    lines = content.splitlines()
    top_level = _top_level_permissions(lines, label)
    invocations: list[dict[str, Any]] = []
    for job, start, end in _job_blocks(lines, label):
        uses = _job_scalar(lines, start, end, "uses", label)
        if uses is None:
            continue
        match = REUSABLE_REF_RE.fullmatch(uses)
        if match is None:
            continue
        invocations.append(
            {
                "job": job,
                "reusable_path": f".github/workflows/{match.group(1)}",
                "reusable_ref": uses,
                "permissions": _job_permissions(
                    lines,
                    start,
                    end,
                    top_level,
                    label,
                ),
            }
        )
    return invocations


def _required_envelope(content: str, label: str) -> dict[str, str]:
    lines = content.splitlines()
    top_level = _top_level_permissions(lines, label)
    envelope: dict[str, str] = {}
    ranks = {"none": 0, "read": 1, "write": 2}
    for job, start, end in _job_blocks(lines, label):
        permissions = _job_permissions(lines, start, end, top_level, label)
        checked = compare_permissions(permissions, permissions)
        if checked["reason"] == "invalid_contract":
            raise ReusableReleasePreflightError(f"{label}: permissions desconocidos.")
        for scope, level in permissions.items():
            previous = envelope.get(scope, "none")
            if ranks[level] > ranks[previous]:
                envelope[scope] = level
    return envelope


def _decode_workflow(
    value: Mapping[str, Any],
    consumer_sha: str,
    label: str,
) -> tuple[str, str]:
    path = value.get("path")
    if not isinstance(path, str) or WORKFLOW_PATH_RE.fullmatch(path) is None:
        raise ReusableReleasePreflightError(f"{label}: workflow path inválido.")
    record_sha = _sha(value.get("repository_sha"), f"{label}.repository_sha")
    if record_sha != consumer_sha:
        raise ReusableReleasePreflightError(f"{label}: evidencia stale.")
    blob_sha = _sha(value.get("blob_sha"), f"{label}.blob_sha")
    encoded = value.get("content_b64")
    if not isinstance(encoded, str) or len(encoded) > MAX_WORKFLOW_BYTES * 2:
        raise ReusableReleasePreflightError(f"{label}: contenido inválido.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReusableReleasePreflightError(f"{label}: base64 inválido.") from exc
    if len(raw) > MAX_WORKFLOW_BYTES:
        raise ReusableReleasePreflightError(f"{label}: workflow demasiado grande.")
    expected_blob = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()
    if expected_blob != blob_sha:
        raise ReusableReleasePreflightError(f"{label}: blob SHA no corresponde.")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReusableReleasePreflightError(f"{label}: workflow no es UTF-8.") from exc
    return path, content


def evaluate_payload(payload: Any, root: Path | None = None) -> dict[str, Any]:
    """Validate all six public consumers and compare every Factory@v1 call."""
    root_payload = _closed_mapping(
        payload,
        {"version", "factory_sha", "consumers"},
        "payload",
    )
    if root_payload["version"] != 1:
        raise ReusableReleasePreflightError("version no soportada.")
    factory_sha = _sha(root_payload["factory_sha"], "factory_sha")
    consumers = root_payload["consumers"]
    if not isinstance(consumers, list) or len(consumers) != len(CANONICAL_CONSUMERS):
        raise ReusableReleasePreflightError("inventario de consumidores incompleto.")

    seen_repositories: set[str] = set()
    calls: list[dict[str, Any]] = []
    for raw_consumer in consumers:
        consumer = _closed_mapping(
            raw_consumer,
            {"repository", "repository_sha", "workflows"},
            "consumer",
        )
        repository = consumer["repository"]
        if not isinstance(repository, str) or repository not in CANONICAL_CONSUMERS:
            raise ReusableReleasePreflightError("consumer repository desconocido.")
        if repository in seen_repositories:
            raise ReusableReleasePreflightError("consumer repository duplicado.")
        seen_repositories.add(repository)
        repository_sha = _sha(
            consumer["repository_sha"],
            f"{repository}.repository_sha",
        )
        workflows = consumer["workflows"]
        if (
            not isinstance(workflows, list)
            or not workflows
            or len(workflows) > MAX_WORKFLOWS_PER_REPOSITORY
        ):
            raise ReusableReleasePreflightError(
                f"{repository}: inventario de workflows inválido."
            )
        seen_paths: set[str] = set()
        repo_calls = 0
        for index, raw_workflow in enumerate(workflows):
            workflow = _closed_mapping(
                raw_workflow,
                {"path", "blob_sha", "repository_sha", "content_b64"},
                f"{repository}.workflow[{index}]",
            )
            path, workflow_content = _decode_workflow(
                workflow,
                repository_sha,
                f"{repository}.workflow[{index}]",
            )
            if path in seen_paths:
                raise ReusableReleasePreflightError(
                    f"{repository}: workflow duplicado {path}."
                )
            seen_paths.add(path)
            for invocation in _caller_invocations(
                workflow_content,
                f"{repository}:{path}",
            ):
                repo_calls += 1
                calls.append(
                    {
                        "repository": repository,
                        "workflow": path,
                        **invocation,
                    }
                )
        if repo_calls == 0:
            raise ReusableReleasePreflightError(
                f"{repository}: sin caller Factory@v1 verificable."
            )

    if seen_repositories != CANONICAL_CONSUMERS:
        raise ReusableReleasePreflightError("inventario de consumidores incompleto.")
    if not calls:
        raise ReusableReleasePreflightError("sin callers Factory@v1.")

    repo_root = root or Path(__file__).resolve().parents[1]
    envelopes: dict[str, dict[str, str]] = {}
    incompatible: list[dict[str, str]] = []
    for call in sorted(
        calls,
        key=lambda item: (
            item["reusable_path"],
            item["repository"],
            item["workflow"],
            item["job"],
        ),
    ):
        reusable_path = call["reusable_path"]
        if reusable_path not in envelopes:
            candidate = repo_root / reusable_path
            try:
                candidate_content = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise ReusableReleasePreflightError(
                    f"reusable candidato no legible: {reusable_path}."
                ) from exc
            envelopes[reusable_path] = _required_envelope(
                candidate_content,
                f"factory:{reusable_path}",
            )

        result = compare_permissions(
            envelopes[reusable_path],
            call["permissions"],
        )
        if result["reason"] == "invalid_contract":
            raise ReusableReleasePreflightError(
                f"{call['repository']}:{call['workflow']}:{call['job']}: "
                "permission envelope inválido."
            )
        for missing in result["missing"]:
            incompatible.append(
                {
                    "repository": call["repository"],
                    "workflow": call["workflow"],
                    "job": call["job"],
                    "reusable": call["reusable_ref"],
                    "scope": missing["scope"],
                    "required": missing["required"],
                    "granted": missing["granted"],
                }
            )

    incompatible.sort(
        key=lambda item: (
            item["repository"],
            item["workflow"],
            item["job"],
            item["reusable"],
            item["scope"],
        )
    )
    return {
        "version": 1,
        "status": "COMPATIBLE" if not incompatible else "INCOMPATIBLE",
        "compatible": not incompatible,
        "factory_sha": factory_sha,
        "consumer_count": len(seen_repositories),
        "caller_count": len(calls),
        "reusables": sorted(envelopes),
        "incompatible": incompatible,
    }


def main() -> int:
    raw = sys.stdin.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        print("ERROR: payload demasiado grande.", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
        result = evaluate_payload(payload)
    except (json.JSONDecodeError, ReusableReleasePreflightError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
