"""Factory Lab: shadow mode, stable comparison and promotion contract."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from evolution.constitution import ConstitutionError, validate_candidate
from evolution.fitness import FitnessError, compare_fitness


LAB_VERSION = 1
SHADOW_MODE = "shadow"
STABLE_BASELINE = "stable"


class FactoryLabError(ValueError):
    """Invalid or unsafe Factory Lab input."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validated_sha(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise FactoryLabError(f"{field} debe ser SHA-1 lowercase exacto")
    return value


def _validated_metrics(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise FactoryLabError(f"{field} debe ser vector no vacío")
    try:
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise FactoryLabError(f"{field} debe ser JSON finito") from exc
    return value


def evaluate_shadow(
    *,
    stable_sha: Any,
    candidate_sha: Any,
    stable_metrics: Any,
    candidate_metrics: Any,
    constitution_candidate: Any,
) -> dict[str, Any]:
    """Evaluate one candidate without mutating stable or external state."""
    stable = _validated_sha(stable_sha, "stable_sha")
    candidate = _validated_sha(candidate_sha, "candidate_sha")
    if stable == candidate:
        raise FactoryLabError("candidate_sha debe diferir de stable_sha")

    baseline = _validated_metrics(stable_metrics, "stable_metrics")
    candidate_vector = _validated_metrics(candidate_metrics, "candidate_metrics")

    try:
        constitution_fingerprint = validate_candidate(constitution_candidate)
    except ConstitutionError as exc:
        raise FactoryLabError("candidato viola Constitution") from exc

    try:
        fitness = compare_fitness(
            baseline=baseline,
            candidate=candidate_vector,
        )
    except FitnessError as exc:
        raise FactoryLabError("fitness inválido") from exc

    promotion_ready = (
        fitness["can_claim_improvement"] is True
        and fitness["claim"] == "improved"
        and not fitness["protected_regressions"]
        and not fitness["missing_dimensions"]
    )

    result = {
        "version": LAB_VERSION,
        "mode": SHADOW_MODE,
        "mutation_allowed": False,
        "external_writes": [],
        "baseline": {
            "name": STABLE_BASELINE,
            "sha": stable,
            "metrics_fingerprint": _stable_hash(baseline),
        },
        "candidate": {
            "sha": candidate,
            "metrics_fingerprint": _stable_hash(candidate_vector),
            "constitution_fingerprint": constitution_fingerprint,
        },
        "fitness": fitness,
        "promotion": {
            "ready": promotion_ready,
            "requires": [
                "constitution:valid",
                "fitness:improved",
                "fitness:no-protected-regressions",
                "fitness:no-missing-dimensions",
            ],
            "execution": "not-performed",
        },
    }
    result["fingerprint"] = _stable_hash(result)
    return result


def promotion_contract(shadow_result: Any) -> dict[str, Any]:
    """Convert a valid shadow result into a non-executing promotion contract."""
    if not isinstance(shadow_result, dict):
        raise FactoryLabError("shadow_result inválido")
    required = {
        "version",
        "mode",
        "mutation_allowed",
        "external_writes",
        "baseline",
        "candidate",
        "fitness",
        "promotion",
        "fingerprint",
    }
    if set(shadow_result) != required:
        raise FactoryLabError("shadow_result incompleto o con campos extra")
    expected = dict(shadow_result)
    fingerprint = expected.pop("fingerprint")
    if not isinstance(fingerprint, str) or fingerprint != _stable_hash(expected):
        raise FactoryLabError("shadow_result fingerprint no coincide")
    if shadow_result["mode"] != SHADOW_MODE:
        raise FactoryLabError("promoción exige shadow mode")
    if shadow_result["mutation_allowed"] is not False:
        raise FactoryLabError("shadow mode no puede mutar")
    if shadow_result["external_writes"] != []:
        raise FactoryLabError("shadow mode no puede escribir externamente")
    if shadow_result["baseline"].get("name") != STABLE_BASELINE:
        raise FactoryLabError("promoción exige baseline stable")
    if shadow_result["promotion"].get("ready") is not True:
        raise FactoryLabError("evidencia insuficiente para promoción")

    contract = {
        "version": LAB_VERSION,
        "shadow_fingerprint": fingerprint,
        "stable_sha": shadow_result["baseline"]["sha"],
        "candidate_sha": shadow_result["candidate"]["sha"],
        "constitution_fingerprint": shadow_result["candidate"][
            "constitution_fingerprint"
        ],
        "fitness_fingerprint": shadow_result["fitness"]["fingerprint"],
        "requires_human_or_authorized_promotion": True,
        "execution": "not-performed",
    }
    contract["fingerprint"] = _stable_hash(contract)
    return contract
