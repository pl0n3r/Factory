"""Build-ahead encryption orchestration; NO production crypto implementation.

Only explicitly marked test doubles are accepted. No key or plaintext may be
written to the serialized artifact. A real vetted AEAD adapter and security
review are required before any external transfer.
"""
from __future__ import annotations

import base64
import re
from collections.abc import Mapping

_IDENT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z")


class EncryptionContractError(ValueError):
    """Safe error: do not include provider exceptions or input data."""


def _validated(project: object, key_ref: object, backend: object) -> None:
    if (not isinstance(project, str) or _IDENT.fullmatch(project) is None
            or not isinstance(key_ref, str) or _IDENT.fullmatch(key_ref) is None
            or getattr(backend, "simulation_only", None) is not True
            or not callable(getattr(backend, "seal", None))
            or not callable(getattr(backend, "open", None))):
        raise EncryptionContractError("Untrusted key or crypto backend.")


def seal_backup(project: str, key_ref: str, data: bytes, keys: object, backend: object) -> dict:
    """Exercise sealed-artifact rotation using an injected fake, no real keys."""
    _validated(project, key_ref, backend)
    if not isinstance(data, bytes) or len(data) > 8_000_000:
        raise EncryptionContractError("Invalid backup bytes.")
    try:
        key_handle = keys.resolve(key_ref)
        sealed = backend.seal(data, key_handle, project.encode("ascii"))
        if not isinstance(sealed, bytes) or sealed == data or not 8 <= len(sealed) <= 12_000_000:
            raise ValueError("Invalid simulated seal")
    except Exception:
        raise EncryptionContractError("Encryption simulation failed.") from None
    return {"version": 1, "project": project, "key_ref": key_ref,
            "payload_b64": base64.b64encode(sealed).decode("ascii"),
            "simulation_only": True, "external_transfer_allowed": False}


def open_backup(project: str, artifact: Mapping, keys: object, backend: object) -> bytes:
    """Requires the historical key handle even after the active key rotates."""
    if not isinstance(artifact, Mapping) or set(artifact) != {
        "version", "project", "key_ref", "payload_b64",
        "simulation_only", "external_transfer_allowed"
    } or artifact["version"] != 1 or artifact["project"] != project or artifact["simulation_only"] is not True or artifact["external_transfer_allowed"] is not False:
        raise EncryptionContractError("Invalid sealed artifact.")
    _validated(project, artifact["key_ref"], backend)
    payload = artifact["payload_b64"]
    if not isinstance(payload, str) or len(payload) > 16_000_000:
        raise EncryptionContractError("Invalid sealed artifact.")
    try:
        sealed = base64.b64decode(payload, validate=True)
        plain = backend.open(sealed, keys.resolve(artifact["key_ref"]), project.encode("ascii"))
        if not isinstance(plain, bytes):
            raise ValueError("Invalid opened bytes")
        return plain
    except Exception:
        raise EncryptionContractError("Decrypt simulation failed.") from None
