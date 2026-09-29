"""Recovery adapters: descriptors declarativos, deterministas y sin I/O externo."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import re
from typing import Any

from recovery.contract import validate_recovery_manifest

PROVIDERS = frozenset({"object_storage", "google_drive"})
OPERATIONS = frozenset({"upload", "materialize", "verify"})
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}|\bgh[pousr]_[A-Za-z0-9]{20,}|"
    r"\bsk-[A-Za-z0-9]{20,}|"
    r"\b(?:password|passwd|secret|token|api[_-]?key|cookie)\s*[:=]|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)


class RecoveryAdapterError(ValueError):
    """Descriptor de adapter Recovery inválido."""


def build_adapter_descriptor(manifest: Any, request: Any) -> dict[str, Any]:
    """Valida manifest/request y devuelve una intención portable, nunca una ejecución."""
    recovery = validate_recovery_manifest(manifest)
    _size_and_sensitive(request)
    data = _map(
        request,
        {"provider", "operation", "object_ref", "checksum_sha256", "idempotency_key"},
        "request",
    )
    provider = _enum(data["provider"], PROVIDERS, "provider")
    operation = _enum(data["operation"], OPERATIONS, "operation")
    object_ref = _opaque(data["object_ref"], "object_ref")
    checksum = data["checksum_sha256"]
    if not isinstance(checksum, str) or _SHA256.fullmatch(checksum) is None:
        raise RecoveryAdapterError("checksum_sha256 inválido.")
    idempotency_key = _opaque(data["idempotency_key"], "idempotency_key")

    if provider == "google_drive" and recovery["offsite"]["cold_copy"] != "google_drive":
        raise RecoveryAdapterError(
            "google_drive no está habilitado por el Recovery Manifest."
        )

    role = "primary_offsite" if provider == "object_storage" else "cold_copy"
    descriptor = {
        "version": 1,
        "project": recovery["project"],
        "provider": provider,
        "role": role,
        "operation": operation,
        "namespace": f"recovery:{recovery['project']}",
        "object_ref": object_ref,
        "checksum_sha256": checksum,
        "idempotency_key": idempotency_key,
        "authority": "unchanged",
        "execute": False,
    }
    descriptor["descriptor_id"] = _fingerprint(descriptor)
    return descriptor


def canonical_adapter_descriptor(manifest: Any, request: Any) -> str:
    """Serialización estable para pipeline/evidence posteriores."""
    return json.dumps(
        build_adapter_descriptor(manifest, request),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def supported_providers() -> tuple[str, ...]:
    """Catálogo cerrado: object storage técnico + Drive cold-copy; nunca iCloud."""
    return tuple(sorted(PROVIDERS))


def _map(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise RecoveryAdapterError(
            f"{label} contiene campos faltantes o no permitidos."
        )
    return value


def _enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise RecoveryAdapterError(f"{label} fuera del catálogo.")
    return value


def _opaque(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or _REF.fullmatch(value) is None
        or ".." in value
        or "://" in value
    ):
        raise RecoveryAdapterError(
            f"{label} debe ser una referencia opaca segura."
        )
    return value


def _fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _size_and_sensitive(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RecoveryAdapterError("request debe ser JSON finito.") from exc
    if len(encoded.encode()) > 50_000:
        raise RecoveryAdapterError("request excede tamaño máximo.")
    if _SENSITIVE.search(encoded):
        raise RecoveryAdapterError(
            "request contiene forma sensible no permitida."
        )
