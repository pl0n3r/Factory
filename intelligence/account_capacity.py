"""Estimador puro y conservador de capacidad de envío por cuenta."""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any


CAPACITY_VERSION = 1
STATUSES = {"UNKNOWN", "FRESH", "STALE"}
CONFIDENCE = {"none", "low", "medium", "high"}
MAX_OBSERVATIONS = 1000
MAX_DIMENSION_CHARS = 120


class AccountCapacityError(ValueError):
    """El contrato de telemetría o política es inválido."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _integer(value: Any, field: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise AccountCapacityError(f"{field} inválido")
    return value
def _dimension(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AccountCapacityError(f"{field} inválido")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > MAX_DIMENSION_CHARS
        or "\n" in value
        or "\r" in value
    ):
        raise AccountCapacityError(f"{field} inválido")
    return normalized


def _normalize_budget(value: Any) -> dict[str, int]:
    expected = {"max_messages", "window_seconds", "min_interval_seconds"}
    if not isinstance(value, dict) or set(value) != expected:
        raise AccountCapacityError("fallback_budget debe usar esquema cerrado")
    maximum = _integer(value["max_messages"], "fallback_budget.max_messages", minimum=0)
    window = _integer(value["window_seconds"], "fallback_budget.window_seconds", minimum=1)
    interval = _integer(
        value["min_interval_seconds"],
        "fallback_budget.min_interval_seconds",
        minimum=1,
    )
    minimum_interval = window if maximum == 0 else (window + maximum - 1) // maximum
    if interval < minimum_interval:
        raise AccountCapacityError("fallback_budget permite un ritmo superior a su máximo")
    return {
        "max_messages": maximum,
        "window_seconds": window,
        "min_interval_seconds": interval,
    }
def _normalize_observation(value: Any, *, now: int) -> dict[str, Any]:
    expected = {
        "accepted",
        "limited",
        "window_seconds",
        "reset_after_seconds",
        "observed_at",
        "model",
        "reasoning",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise AccountCapacityError("observation debe usar esquema cerrado")
    accepted = _integer(value["accepted"], "observation.accepted", minimum=0)
    if type(value["limited"]) is not bool:
        raise AccountCapacityError("observation.limited inválido")
    window = _integer(value["window_seconds"], "observation.window_seconds", minimum=1)
    observed_at = _integer(value["observed_at"], "observation.observed_at", minimum=0)
    if observed_at > now:
        raise AccountCapacityError("observation.observed_at no puede estar en el futuro")

    reset = value["reset_after_seconds"]
    if reset is not None:
        reset = _integer(reset, "observation.reset_after_seconds", minimum=1)
    if not value["limited"] and reset is not None:
        raise AccountCapacityError("reset_after_seconds solo aplica a eventos de límite")

    return {
        "accepted": accepted,
        "limited": value["limited"],
        "window_seconds": window,
        "reset_after_seconds": reset,
        "observed_at": observed_at,
        "model": _dimension(value["model"], "observation.model"),
        "reasoning": _dimension(value["reasoning"], "observation.reasoning"),
    }
def _normalize_request(value: Any, *, now: int) -> dict[str, Any]:
    expected = {"version", "ttl_seconds", "fallback_budget", "observations"}
    if not isinstance(value, dict) or set(value) != expected:
        raise AccountCapacityError("request debe usar esquema cerrado")
    if type(value["version"]) is not int or value["version"] != CAPACITY_VERSION:
        raise AccountCapacityError("request.version no soportada")
    ttl = _integer(value["ttl_seconds"], "ttl_seconds", minimum=1)
    observations = value["observations"]
    if not isinstance(observations, list) or len(observations) > MAX_OBSERVATIONS:
        raise AccountCapacityError("observations inválida")
    normalized = [
        _normalize_observation(item, now=now)
        for item in observations
    ]
    normalized.sort(
        key=lambda item: (
            item["observed_at"],
            item["limited"],
            item["accepted"],
            item["window_seconds"],
            item["reset_after_seconds"] or 0,
            item["model"] or "",
            item["reasoning"] or "",
        )
    )
    return {
        "version": CAPACITY_VERSION,
        "ttl_seconds": ttl,
        "fallback_budget": _normalize_budget(value["fallback_budget"]),
        "observations": normalized,
    }


def _with_fingerprint(result: dict[str, Any]) -> dict[str, Any]:
    output = dict(result)
    output["fingerprint"] = _stable_hash(result)
    return output
def _fallback_result(
    *,
    status: str,
    budget: dict[str, int],
    observed_at: int | None,
    expires_at: int | None,
    sample_count: int,
) -> dict[str, Any]:
    return _with_fingerprint(
        {
            "version": CAPACITY_VERSION,
            "status": status,
            "confidence": "none",
            "budget": dict(budget),
            "observed_safe_max": None,
            "observed_at": observed_at,
            "expires_at": expires_at,
            "sample_count": sample_count,
            "limited_count": 0,
            "source": "conservative-default",
        }
    )


def _confidence(fresh: list[dict[str, Any]], limited: list[dict[str, Any]]) -> str:
    if len(fresh) < 2:
        return "low"
    if limited and len({item["accepted"] for item in limited}) > 1:
        return "low"
    if len(fresh) >= 5 and len(limited) >= 2:
        return "high"
    return "medium"


def _effective_window(item: dict[str, Any]) -> int:
    reset = item["reset_after_seconds"]
    return max(item["window_seconds"], reset or 0)


def _select_conservative_observation(
    rows: list[dict[str, Any]], *, use_reset_window: bool
) -> tuple[dict[str, Any], int]:
    def evidence_window(item: dict[str, Any]) -> int:
        return _effective_window(item) if use_reset_window else item["window_seconds"]

    selected = min(
        rows,
        key=lambda item: (
            Fraction(item["accepted"], evidence_window(item)),
            -item["observed_at"],
            item["accepted"],
            evidence_window(item),
        ),
    )
    return selected, evidence_window(selected)


def estimate_account_capacity(request: Any, *, now: int) -> dict[str, Any]:
    """Compila un presupuesto conservador desde telemetría agregada."""
    now = _integer(now, "now", minimum=0)
    data = _normalize_request(request, now=now)
    observations = data["observations"]
    fallback = data["fallback_budget"]
    ttl = data["ttl_seconds"]

    if not observations:
        return _fallback_result(
            status="UNKNOWN",
            budget=fallback,
            observed_at=None,
            expires_at=None,
            sample_count=0,
        )
    latest = max(item["observed_at"] for item in observations)
    fresh = [
        item
        for item in observations
        if now - item["observed_at"] <= ttl
    ]
    if not fresh:
        return _fallback_result(
            status="STALE",
            budget=fallback,
            observed_at=latest,
            expires_at=latest + ttl,
            sample_count=len(observations),
        )

    limited = [item for item in fresh if item["limited"]]
    if limited:
        evidence, window = _select_conservative_observation(
            limited, use_reset_window=True
        )
        source = "observed-limit"
    else:
        evidence, window = _select_conservative_observation(
            fresh, use_reset_window=False
        )
        source = "observed-success"

    safe_max = evidence["accepted"]
    interval = window if safe_max == 0 else (window + safe_max - 1) // safe_max
    result = {
        "version": CAPACITY_VERSION,
        "status": "FRESH",
        "confidence": _confidence(fresh, limited),
        "budget": {
            "max_messages": safe_max,
            "window_seconds": window,
            "min_interval_seconds": interval,
        },
        "observed_safe_max": safe_max,
        "observed_at": max(item["observed_at"] for item in fresh),
        "expires_at": max(item["observed_at"] for item in fresh) + ttl,
        "sample_count": len(fresh),
        "limited_count": len(limited),
        "source": source,
    }
    return _with_fingerprint(result)
