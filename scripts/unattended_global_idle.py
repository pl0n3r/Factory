#!/usr/bin/env python3
"""Prueba pura y fail-closed de idle global sobre los repos canónicos."""
from __future__ import annotations

import re

CANONICAL_REPOSITORIES = (
    "pl0n3r/Factory",
    "pl0n3r/Condor",
    "pl0n3r/GrindFlow",
    "pl0n3r/brvtal",
    "pl0n3r/ControlBot",
    "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
)
SNAPSHOT_FIELDS = frozenset({"version", "repositories"})
REPOSITORY_FIELDS = frozenset(
    {
        "repository",
        "freshness",
        "ready",
        "reserved",
        "reviewing",
        "ambiguous",
        "source_ref",
    }
)
PROOF_FIELDS = frozenset({"version", "idle_global", "reasons", "provenance"})
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,199}$")


class GlobalIdleValidationError(ValueError):
    """El snapshot/proof no cumple el contrato cerrado de idle global."""


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise GlobalIdleValidationError(f"invalid_{field}")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not REF_RE.fullmatch(value):
        raise GlobalIdleValidationError(f"invalid_{field}")
    return value


def _text_list(value: object, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not REF_RE.fullmatch(item) for item in value)
    ):
        raise GlobalIdleValidationError(f"invalid_{field}")
    if len(value) != len(set(value)):
        raise GlobalIdleValidationError(f"duplicate_{field}")
    return sorted(value)


def validate_global_idle_proof(value: object) -> dict[str, object]:
    """Valida la prueba consumida por 4C; nunca deriva Presence."""
    if not isinstance(value, dict) or set(value) != PROOF_FIELDS:
        raise GlobalIdleValidationError("invalid_global_idle_proof_shape")
    if type(value.get("version")) is not int or value["version"] != 1:
        raise GlobalIdleValidationError("invalid_global_idle_proof_version")
    idle_global = _bool(value.get("idle_global"), "idle_global")
    reasons = _text_list(value.get("reasons"), "global_idle_reasons")
    provenance = _text_list(value.get("provenance"), "global_idle_provenance")
    if idle_global and reasons:
        raise GlobalIdleValidationError("idle_global_with_reasons")
    if idle_global and len(provenance) != len(CANONICAL_REPOSITORIES):
        raise GlobalIdleValidationError("idle_global_incomplete_provenance")
    if not idle_global and not reasons:
        raise GlobalIdleValidationError("non_idle_without_reason")
    return {
        "version": 1,
        "idle_global": idle_global,
        "reasons": reasons,
        "provenance": provenance,
    }


def evaluate_global_idle_snapshot(snapshot: object) -> dict[str, object]:
    """Demuestra idle solo con cobertura exacta, freshness fresh y cero trabajo observable."""
    if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_FIELDS:
        raise GlobalIdleValidationError("invalid_global_idle_snapshot_shape")
    if type(snapshot.get("version")) is not int or snapshot["version"] != 1:
        raise GlobalIdleValidationError("invalid_global_idle_snapshot_version")
    rows = snapshot.get("repositories")
    if not isinstance(rows, list):
        raise GlobalIdleValidationError("invalid_global_idle_repositories")

    by_repo: dict[str, dict[str, object]] = {}
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) != REPOSITORY_FIELDS:
            raise GlobalIdleValidationError("invalid_global_idle_repository_shape")
        repository = _text(raw.get("repository"), "repository")
        if repository in by_repo:
            raise GlobalIdleValidationError("duplicate_global_idle_repository")
        freshness = raw.get("freshness")
        if freshness not in {"fresh", "stale", "unknown"}:
            raise GlobalIdleValidationError("invalid_global_idle_freshness")
        source_ref = _text(raw.get("source_ref"), "source_ref")
        by_repo[repository] = {
            "repository": repository,
            "freshness": freshness,
            "ready": _bool(raw.get("ready"), "ready"),
            "reserved": _bool(raw.get("reserved"), "reserved"),
            "reviewing": _bool(raw.get("reviewing"), "reviewing"),
            "ambiguous": _bool(raw.get("ambiguous"), "ambiguous"),
            "source_ref": source_ref,
        }

    canonical = set(CANONICAL_REPOSITORIES)
    observed = set(by_repo)
    reasons: list[str] = []
    for repository in sorted(canonical - observed):
        reasons.append(f"missing_repository:{repository}")
    for repository in sorted(observed - canonical):
        reasons.append(f"unexpected_repository:{repository}")

    provenance: list[str] = []
    for repository in CANONICAL_REPOSITORIES:
        row = by_repo.get(repository)
        if row is None:
            continue
        provenance.append(f"{repository}:{row['source_ref']}:{row['freshness']}")
        if row["freshness"] != "fresh":
            reasons.append(f"repository_not_fresh:{repository}")
        if row["ambiguous"]:
            reasons.append(f"repository_ambiguous:{repository}")
        for field in ("ready", "reserved", "reviewing"):
            if row[field]:
                reasons.append(f"repository_{field}:{repository}")

    proof = {
        "version": 1,
        "idle_global": not reasons,
        "reasons": sorted(reasons),
        "provenance": sorted(provenance),
    }
    return validate_global_idle_proof(proof)
