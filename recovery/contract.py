"""Recovery Manifest v1: contrato 3-2-1-1-0 por proyecto."""
from __future__ import annotations

from collections.abc import Mapping
import json, re
from typing import Any

VERSION = 1
SOURCE_STATES = frozenset({"REQUIRED", "NOT_APPLICABLE"})
COLD_COPY = frozenset({"google_drive", "NOT_APPLICABLE"})
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_SENSITIVE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}|\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=])",
    re.IGNORECASE,
)


class RecoveryContractError(ValueError):
    """Recovery Manifest inválido."""


def validate_recovery_manifest(payload: Any) -> dict[str, Any]:
    _size_and_sensitive(payload)
    fields = {
        "version", "project", "target", "protection", "retention",
        "sources", "offsite", "encryption", "restore_drill",
    }
    data = _map(payload, fields, "manifest")
    if type(data["version"]) is not int or data["version"] != VERSION:
        raise RecoveryContractError("version debe ser 1.")
    project = data["project"]
    if not isinstance(project, str) or _PROJECT.fullmatch(project) is None:
        raise RecoveryContractError("project inválido.")

    target = _positive_map(data["target"], {"rpo_minutes", "rto_minutes"}, "target")
    protection = _validated_protection(data["protection"])

    retention = _nonnegative_map(
        data["retention"], {"hourly", "daily", "weekly", "monthly"}, "retention"
    )
    if not any(retention.values()):
        raise RecoveryContractError("retention requiere al menos una ventana activa.")

    sources = _map(data["sources"], {"database", "media", "repository"}, "sources")
    normalized_sources = {}
    for key in ("database", "media", "repository"):
        value = sources[key]
        if not _valid_catalog_value(value, SOURCE_STATES):
            raise RecoveryContractError("sources contiene estado fuera del catálogo.")
        normalized_sources[key] = value
    if "REQUIRED" not in normalized_sources.values():
        raise RecoveryContractError("al menos una source debe ser REQUIRED.")

    offsite = _map(data["offsite"], {"object_storage", "cold_copy"}, "offsite")
    if (offsite["object_storage"] != "REQUIRED"
            or not _valid_catalog_value(offsite["cold_copy"], COLD_COPY)):
        raise RecoveryContractError("offsite incompatible con contrato 3-2-1-1-0.")

    encryption = _map(data["encryption"], {"required", "key_material"}, "encryption")
    if encryption != {"required": True, "key_material": "EXTERNAL_ONLY"}:
        raise RecoveryContractError("encryption debe ser obligatorio con key material externo.")

    drill = _map(data["restore_drill"], {"cadence_days"}, "restore_drill")
    cadence = drill["cadence_days"]
    if type(cadence) is not int or not 1 <= cadence <= 365:
        raise RecoveryContractError("restore_drill.cadence_days fuera de límites.")

    return {
        "version": VERSION, "project": project, "target": target,
        "protection": protection, "retention": retention,
        "sources": normalized_sources,
        "offsite": {
            "object_storage": "REQUIRED", "cold_copy": offsite["cold_copy"]
        },
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": cadence},
    }


def _valid_catalog_value(value: Any, allowed: frozenset[str]) -> bool:
    """Rechaza enums JSON no-string antes de consultar un frozenset."""
    return type(value) is str and value in allowed


def _validated_protection(value: Any) -> dict[str, int]:
    """Enforce exact JSON integer constants, never bool or float aliases."""
    expected = {
        "copies": 3, "media_types": 2, "offsite_copies": 1,
        "immutable_copies": 1, "undetected_restore_failures": 0,
    }
    protection = _map(value, set(expected), "protection")
    if any(type(protection[key]) is not int or protection[key] != expected[key]
           for key in expected):
        raise RecoveryContractError("protection debe cumplir exactamente 3-2-1-1-0.")
    return expected


def canonical_recovery_manifest(payload: Any) -> str:
    return json.dumps(
        validate_recovery_manifest(payload), ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    )


def _map(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise RecoveryContractError(f"{label} contiene campos faltantes o no permitidos.")
    return value


def _positive_map(value: Any, expected: set[str], label: str) -> dict[str, int]:
    raw = _map(value, expected, label)
    result = {}
    for key in sorted(expected):
        item = raw[key]
        if type(item) is not int or not 1 <= item <= 525_600:
            raise RecoveryContractError(f"{label} contiene valor fuera de límites.")
        result[key] = item
    return result


def _nonnegative_map(value: Any, expected: set[str], label: str) -> dict[str, int]:
    raw = _map(value, expected, label)
    result = {}
    for key in ("hourly", "daily", "weekly", "monthly"):
        item = raw[key]
        if type(item) is not int or not 0 <= item <= 100_000:
            raise RecoveryContractError(f"{label} contiene valor fuera de límites.")
        result[key] = item
    return result


def _size_and_sensitive(payload: Any) -> None:
    # Encode inside the same trust boundary: a JSON unicode surrogate can
    # serialize to str yet raise UnicodeEncodeError during UTF-8 encoding.
    # Raise the public error OUTSIDE except to avoid retaining raw __context__.
    encoded = None
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        size = len(encoded.encode("utf-8"))
    except (TypeError, ValueError):
        encoded = None
    if encoded is None:
        raise RecoveryContractError("manifest debe ser JSON finito.")
    if size > 100_000:
        raise RecoveryContractError("manifest excede tamaño máximo.")
    if _SENSITIVE.search(encoded):
        raise RecoveryContractError("manifest contiene forma sensible no permitida.")
