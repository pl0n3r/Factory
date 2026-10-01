"""Proyección pura del estimador de capacidad a un contrato portable v1."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import re
from typing import Any


POLICY_VERSION = 1
CAPACITY_VERSION = 1
CAPACITY_STATUSES = frozenset({"UNKNOWN", "FRESH", "STALE"})
CAPACITY_CONFIDENCE = frozenset({"none", "low", "medium", "high"})
CAPACITY_SOURCES = frozenset({
    "conservative-default",
    "observed-limit",
    "observed-success",
})
CAPACITY_FIELDS = frozenset({
    "version",
    "status",
    "confidence",
    "budget",
    "observed_safe_max",
    "observed_at",
    "expires_at",
    "sample_count",
    "limited_count",
    "source",
    "fingerprint",
})
BUDGET_FIELDS = frozenset({
    "max_messages",
    "window_seconds",
    "min_interval_seconds",
})
_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class AccountCapacityPolicyError(ValueError):
    """La evidencia no puede proyectarse de forma segura al contrato v1."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise AccountCapacityPolicyError(f"{field} inválido")
    return value


def _javascript_safe_integer(value: int, field: str, *, multiplier: int = 1) -> int:
    maximum = ((1 << 53) - 1) // multiplier
    if value > maximum:
        raise AccountCapacityPolicyError(f"{field} excede entero seguro JavaScript")
    return value


def _nullable_integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    return _integer(value, field)


def _closed_mapping(value: Any, expected: frozenset[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise AccountCapacityPolicyError(f"{field} debe usar esquema cerrado")
    return value


def _account_alias(value: Any) -> str:
    if not isinstance(value, str) or not _ALIAS.fullmatch(value) or "@" in value:
        raise AccountCapacityPolicyError("account_alias debe ser un alias local opaco")
    return value


def _fingerprint(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise AccountCapacityPolicyError(f"{field} inválido")
    return value


def _budget(value: Any) -> dict[str, int]:
    row = _closed_mapping(value, BUDGET_FIELDS, "capacity.budget")
    maximum = _javascript_safe_integer(
        _integer(row["max_messages"], "capacity.budget.max_messages"),
        "capacity.budget.max_messages",
    )
    window = _javascript_safe_integer(
        _integer(
            row["window_seconds"],
            "capacity.budget.window_seconds",
            minimum=1,
        ),
        "capacity.budget.window_seconds",
        multiplier=1000,
    )
    interval = _javascript_safe_integer(
        _integer(
            row["min_interval_seconds"],
            "capacity.budget.min_interval_seconds",
            minimum=1,
        ),
        "capacity.budget.min_interval_seconds",
        multiplier=1000,
    )
    minimum_interval = window if maximum == 0 else (window + maximum - 1) // maximum
    if interval < minimum_interval:
        raise AccountCapacityPolicyError("capacity.budget permite un ritmo incoherente")
    return {
        "max_messages": maximum,
        "window_seconds": window,
        "min_interval_seconds": interval,
    }


def _capacity(value: Any, *, now: int) -> dict[str, Any]:
    row = _closed_mapping(value, CAPACITY_FIELDS, "capacity")
    if row["version"] != CAPACITY_VERSION or type(row["version"]) is not int:
        raise AccountCapacityPolicyError("capacity.version no soportada")
    status = row["status"]
    if status not in CAPACITY_STATUSES:
        raise AccountCapacityPolicyError("capacity.status inválido")
    if row["confidence"] not in CAPACITY_CONFIDENCE:
        raise AccountCapacityPolicyError("capacity.confidence inválida")
    source = row["source"]
    if source not in CAPACITY_SOURCES:
        raise AccountCapacityPolicyError("capacity.source inválido")

    budget = _budget(row["budget"])
    observed_safe_max = _nullable_integer(
        row["observed_safe_max"], "capacity.observed_safe_max"
    )
    observed_at = _nullable_integer(row["observed_at"], "capacity.observed_at")
    expires_at = _nullable_integer(row["expires_at"], "capacity.expires_at")
    if observed_at is not None:
        _javascript_safe_integer(
            observed_at,
            "capacity.observed_at",
            multiplier=1000,
        )
    if expires_at is not None:
        _javascript_safe_integer(
            expires_at,
            "capacity.expires_at",
            multiplier=1000,
        )
    sample_count = _integer(row["sample_count"], "capacity.sample_count")
    limited_count = _integer(row["limited_count"], "capacity.limited_count")
    if limited_count > sample_count:
        raise AccountCapacityPolicyError("capacity.limited_count excede sample_count")
    capacity_fingerprint = _fingerprint(row["fingerprint"], "capacity.fingerprint")
    fingerprint_payload = {
        key: row[key]
        for key in CAPACITY_FIELDS
        if key != "fingerprint"
    }
    try:
        expected_fingerprint = _stable_hash(fingerprint_payload)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AccountCapacityPolicyError(
            "capacity.fingerprint no corresponde a la evidencia"
        ) from exc
    if capacity_fingerprint != expected_fingerprint:
        raise AccountCapacityPolicyError(
            "capacity.fingerprint no corresponde a la evidencia"
        )

    if observed_at is not None and observed_at > now:
        raise AccountCapacityPolicyError("capacity.observed_at no puede estar en el futuro")
    if observed_at is None:
        if expires_at is not None:
            raise AccountCapacityPolicyError("capacity.expires_at sin observed_at")
    elif expires_at is None or expires_at <= observed_at:
        raise AccountCapacityPolicyError("capacity.expires_at incoherente")

    if status == "UNKNOWN":
        if (
            observed_at is not None
            or expires_at is not None
            or observed_safe_max is not None
            or sample_count != 0
            or limited_count != 0
            or source != "conservative-default"
        ):
            raise AccountCapacityPolicyError("capacity UNKNOWN incoherente")
    elif status == "STALE":
        if (
            observed_at is None
            or expires_at is None
            or observed_safe_max is not None
            or source != "conservative-default"
        ):
            raise AccountCapacityPolicyError("capacity STALE incoherente")
    else:
        if (
            observed_at is None
            or expires_at is None
            or observed_safe_max is None
            or observed_safe_max != budget["max_messages"]
            or source == "conservative-default"
            or sample_count == 0
        ):
            raise AccountCapacityPolicyError("capacity FRESH incoherente")

    return {
        "status": status,
        "budget": budget,
        "observed_at": observed_at,
        "expires_at": expires_at,
        "source": source,
        "capacity_fingerprint": capacity_fingerprint,
    }


def project_account_capacity_policy(
    capacity: Any,
    *,
    account_alias: str,
    now: int,
) -> dict[str, Any]:
    """Proyecta evidencia de capacidad sin I/O y falla cerrado ante stale/unknown."""
    now = _integer(now, "now")
    alias = _account_alias(account_alias)
    normalized = _capacity(capacity, now=now)

    status = normalized["status"]
    expires_at = normalized["expires_at"]
    authoritative = status == "FRESH" and expires_at is not None and expires_at > now
    if status == "FRESH" and not authoritative:
        status = "STALE"

    projected_budget = None
    if authoritative:
        budget = normalized["budget"]
        projected_budget = {
            "limit": budget["max_messages"],
            "windowMs": budget["window_seconds"] * 1000,
            "minIntervalMs": budget["min_interval_seconds"] * 1000,
        }

    result = {
        "version": POLICY_VERSION,
        "accountAlias": alias,
        "status": status,
        "budget": projected_budget,
        "observedAt": (
            None
            if normalized["observed_at"] is None
            else normalized["observed_at"] * 1000
        ),
        "expiresAt": None if expires_at is None else expires_at * 1000,
        "source": normalized["source"],
        "capacityFingerprint": normalized["capacity_fingerprint"],
    }
    return {**result, "fingerprint": _stable_hash(result)}
