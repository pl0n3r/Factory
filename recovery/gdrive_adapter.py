"""Copia fría Google Drive, solo con transporte inyectado (fake en pruebas).

No se conecta a Google, no cifra datos y no representa un backup real.
La autorización de restauración productiva pertenece a otra puerta.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Any

from recovery.contract import RecoveryContractError, validate_recovery_manifest

_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_BYTES = 10_000_000


class ColdCopyError(ValueError):
    """Fallo cerrado sin exponer payloads, credenciales ni excepciones del transporte."""


def _reference(value: object) -> str:
    if (type(value) is not str or _REFERENCE.fullmatch(value) is None
            or ".." in value):
        raise ColdCopyError("invalid_reference")
    return value


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ColdCopyError("invalid_clock")
    return value.astimezone(timezone.utc)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeDriveTransport:
    """Almacén efímero en memoria; jamás usa red, archivos ni APIs de Google."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.writes = 0

    def put_if_absent(self, namespace: str, key: str, content: bytes,
                      expiry: datetime, _credential: str) -> datetime:
        position = (namespace, key)
        if position not in self.objects:
            self.objects[position] = {
                "content": bytes(content), "expiry": expiry,
            }
            self.writes += 1
        return self.objects[position]["expiry"]

    def read(self, namespace: str, key: str, _credential: str) -> bytes:
        if (namespace, key) not in self.objects:
            raise KeyError("object_not_found")
        return bytes(self.objects[(namespace, key)]["content"])

    def purge_expired(self, namespace: str, current: datetime,
                      _credential: str) -> int:
        doomed = [
            position for position, item in self.objects.items()
            if position[0] == namespace and item["expiry"] <= current
        ]
        for position in doomed:
            del self.objects[position]
        return len(doomed)


class GDriveColdCopy:
    """Orquesta bytes simulados; el proveedor real NO está implementado."""

    def __init__(self, manifest: object, *, transport: object,
                 secret_provider: object, credential_ref: str,
                 now: datetime, restore_authorizer: object = None) -> None:
        try:
            checked = validate_recovery_manifest(manifest)
        except (RecoveryContractError, TypeError, ValueError):
            raise ColdCopyError("invalid_manifest") from None
        if checked["offsite"]["cold_copy"] != "google_drive":
            raise ColdCopyError("cold_copy_not_enabled")
        self.project = checked["project"]
        self.namespace = "recovery:" + self.project
        self.transport = transport
        self.secret_provider = secret_provider
        self.credential_ref = _reference(credential_ref)
        self.now = _utc(now)
        self.restore_authorizer = restore_authorizer

    def _transport(self, method: str, *args: object) -> Any:
        # No material del proveedor entra en errores, evidencia ni estado persistido.
        try:
            secret = self.secret_provider.resolve(self.credential_ref)
            if type(secret) is not str or not secret:
                raise ValueError("invalid_secret")
            return getattr(self.transport, method)(*args, secret)
        except Exception:
            raise ColdCopyError("cold_copy_transport_unavailable") from None

    def upload(self, object_ref: str, payload: bytes, expected_sha256: str,
               *, retention_days: int) -> dict[str, object]:
        ref = _reference(object_ref)
        if type(payload) is not bytes or len(payload) > _MAX_BYTES:
            raise ColdCopyError("invalid_payload")
        if type(expected_sha256) is not str or not _SHA256.fullmatch(expected_sha256):
            raise ColdCopyError("invalid_checksum")
        source_digest = _digest(payload)
        if source_digest != expected_sha256:
            raise ColdCopyError("source_checksum_mismatch")
        if type(retention_days) is not int or not 1 <= retention_days <= 365:
            raise ColdCopyError("invalid_retention")
        key = ref + ":" + source_digest
        expiry = self.now + timedelta(days=retention_days)
        stored_expiry = self._transport(
            "put_if_absent", self.namespace, key, payload, expiry,
        )
        if not isinstance(stored_expiry, datetime):
            raise ColdCopyError("invalid_remote_evidence")
        stored_expiry = _utc(stored_expiry)
        remote = self._transport("read", self.namespace, key)
        if type(remote) is not bytes or _digest(remote) != source_digest:
            raise ColdCopyError("remote_checksum_mismatch")
        return {
            "version": 1, "provider": "google_drive",
            "role": "cold_copy", "project": self.project,
            "namespace": self.namespace, "object_id": key,
            "source_sha256": source_digest, "remote_sha256": _digest(remote),
            "retention_until": stored_expiry.isoformat(),
            "evidence": "FAKE_VERIFIED_ONLY", "real_restore_authorized": False,
        }

    def materialize_fake(self, object_ref: str, expected_sha256: str,
                         *, purpose: str) -> bytes:
        """Solo devuelve bytes de prueba tras autorización inyectada verificable."""
        ref = _reference(object_ref)
        if (type(expected_sha256) is not str
                or not _SHA256.fullmatch(expected_sha256)):
            raise ColdCopyError("invalid_checksum")
        if purpose != "offline_restore_test":
            raise ColdCopyError("restore_not_authorized")
        decision = {
            "project": self.project, "namespace": self.namespace,
            "object_ref": ref, "checksum_sha256": expected_sha256,
            "purpose": purpose,
        }
        try:
            allowed = (callable(self.restore_authorizer)
                       and self.restore_authorizer(dict(decision)) is True)
        except Exception:
            allowed = False
        if not allowed:
            raise ColdCopyError("restore_not_authorized")
        content = self._transport(
            "read", self.namespace, ref + ":" + expected_sha256,
        )
        if type(content) is not bytes or _digest(content) != expected_sha256:
            raise ColdCopyError("remote_checksum_mismatch")
        return content

    def expire_fake(self, *, at: datetime) -> int:
        """Retención simulada y limitada al namespace de este proyecto."""
        current = _utc(at)
        deleted = self._transport("purge_expired", self.namespace, current)
        if type(deleted) is not int or deleted < 0:
            raise ColdCopyError("invalid_remote_evidence")
        return deleted
