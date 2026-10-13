"""Regresiones herméticas de Google Drive cold-copy FAKE, Factory #1089."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest
from unittest.mock import patch

from recovery.gdrive_adapter import (
    ColdCopyError, FakeDriveTransport, GDriveColdCopy,
)

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def manifest(project="condor"):
    return {
        "version": 1, "project": project,
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {
            "copies": 3, "media_types": 2, "offsite_copies": 1,
            "immutable_copies": 1, "undetected_restore_failures": 0,
        },
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {
            "database": "REQUIRED", "media": "NOT_APPLICABLE",
            "repository": "REQUIRED",
        },
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "google_drive"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Secrets:
    def __init__(self, value="DUMMY_SECRET_NOT_REAL"):
        self.value = value
        self.calls = 0

    def resolve(self, name: str) -> str:
        self.calls += 1
        if name != "gdrive-cold-copy":
            raise ValueError(self.value)
        return self.value


def instance(project="condor", *, transport=None, secrets=None, allow=False):
    return GDriveColdCopy(
        manifest(project),
        transport=transport if transport is not None else FakeDriveTransport(),
        secret_provider=secrets if secrets is not None else Secrets(),
        credential_ref="gdrive-cold-copy", now=NOW,
        restore_authorizer=(lambda _request: True) if allow else None,
    )


class RecoveryGDriveAdapterTests(unittest.TestCase):
    def test_upload_is_idempotent_by_digest(self):
        fake = FakeDriveTransport()
        drive = instance(transport=fake)
        payload = b"encrypted-fake-bytes-only"
        first = drive.upload("snapshot-001", payload, sha(payload), retention_days=7)
        second = drive.upload("snapshot-001", payload, sha(payload), retention_days=30)
        self.assertEqual(first, second)
        self.assertEqual(fake.writes, 1)
        self.assertEqual(len(fake.objects), 1)
        self.assertEqual(first["source_sha256"], first["remote_sha256"])
        self.assertEqual(first["evidence"], "FAKE_VERIFIED_ONLY")
        self.assertFalse(first["real_restore_authorized"])
        different = drive.upload(
            "snapshot-001", payload + b"-changed", sha(payload + b"-changed"),
            retention_days=7,
        )
        self.assertNotEqual(first["object_id"], different["object_id"])
        self.assertEqual(fake.writes, 2)
        self.assertEqual(drive.namespace, "recovery:condor")

    def test_source_and_remote_checksums_must_match(self):
        fake = FakeDriveTransport()
        drive = instance(transport=fake, allow=True)
        payload = b"verified-content"
        payload_digest = sha(payload)
        with self.assertRaisesRegex(ColdCopyError, "source_checksum_mismatch"):
            drive.upload("snap", payload, "0" * 64, retention_days=7)
        self.assertFalse(fake.objects)
        evidence = drive.upload("snap", payload, payload_digest, retention_days=7)
        fake.objects[(drive.namespace, evidence["object_id"])]["content"] = b"corrupt"
        with self.assertRaisesRegex(ColdCopyError, "remote_checksum_mismatch"):
            drive.materialize_fake(
                "snap", payload_digest, purpose="offline_restore_test",
            )
        with self.assertRaisesRegex(ColdCopyError, "invalid_checksum"):
            drive.materialize_fake("snap", "z" * 64, purpose="offline_restore_test")
        for value in (True, -1, 366):
            with self.subTest(retention=value), self.assertRaises(ColdCopyError):
                drive.upload("snap", payload, payload_digest, retention_days=value)
        for bad in ("../escape", "folder/name", "x" * 129):
            with self.subTest(ref=bad), self.assertRaises(ColdCopyError):
                drive.upload(bad, payload, payload_digest, retention_days=1)

    def test_secret_material_never_enters_error_or_evidence(self):
        # Credential-shaped object refs must be rejected before fake storage,
        # secret lookup or any receipt can echo the supplied identifier.
        for unsafe_ref in (
            "sk-" + "FAKE" * 6,
            "ghp_" + "F" * 24,
            "github_pat_" + "F" * 18,
            "snapshot:sk-" + "F" * 24,
            "snapshot:github_pat_" + "F" * 18,
        ):
            with self.subTest(ref_kind=unsafe_ref[:4]):
                fake = FakeDriveTransport()
                creds = Secrets()
                drive = instance(transport=fake, secrets=creds, allow=True)
                fake_data = b"fake-secret-guard-test"
                with self.assertRaisesRegex(ColdCopyError, "invalid_reference") as rejected:
                    drive.upload(unsafe_ref, fake_data, sha(fake_data), retention_days=7)
                self.assertNotIn(unsafe_ref, str(rejected.exception))
                with self.assertRaisesRegex(ColdCopyError, "invalid_reference"):
                    drive.materialize_fake(
                        unsafe_ref, sha(fake_data), purpose="offline_restore_test",
                    )
                self.assertEqual(fake.writes, 0)
                self.assertEqual(fake.objects, {})
                self.assertEqual(creds.calls, 0)
        sensitive = "VERY_PRIVATE_OAUTH_TOKEN_NOT_REAL"
        secrets = Secrets(sensitive)

        drive = instance(transport=FakeDriveTransport(), secrets=secrets)
        data = b"fake-only"
        data_digest = sha(data)
        # Sustituir un método de la clase no puede convertir este fake en
        # emisor externo; se rechaza incluso antes de pedir credenciales.
        with patch.object(
            FakeDriveTransport, "put_if_absent",
            side_effect=RuntimeError(sensitive),
        ):
            before = secrets.calls
            with self.assertRaisesRegex(
                ColdCopyError, "fake_transport_required",
            ) as observed:
                drive.upload("snap", data, data_digest, retention_days=1)
            self.assertEqual(secrets.calls, before)
        self.assertNotIn(sensitive, str(observed.exception))
        self.assertIsNone(observed.exception.__cause__)
        fake = FakeDriveTransport()
        safe = instance(transport=fake, secrets=secrets)
        evidence = safe.upload("snap", data, data_digest, retention_days=1)
        encoded = json.dumps(evidence, sort_keys=True)
        self.assertNotIn(sensitive, encoded)
        self.assertNotIn(data.decode(), encoded)
        self.assertGreater(secrets.calls, 0)

        class FailingSecrets:
            def resolve(self, _name):
                raise RuntimeError(sensitive)

        bad = instance(transport=FakeDriveTransport(), secrets=FailingSecrets())
        with self.assertRaises(ColdCopyError) as error:
            bad.upload("snap", data, data_digest, retention_days=1)
        self.assertNotIn(sensitive, str(error.exception))
        self.assertIsNone(error.exception.__cause__)
        self.assertIsNone(error.exception.__context__)

        # Una falla dentro del propio fake también debe salir SIN cadena
        # sensible, incluso cuando el error interno contiene un sentinel.
        class ExplodingObjects(dict):
            def __contains__(self, _position):
                raise RuntimeError(sensitive)

        failing_fake = FakeDriveTransport()
        failing_fake.objects = ExplodingObjects()
        failing_drive = instance(transport=failing_fake, secrets=Secrets())
        with self.assertRaisesRegex(
            ColdCopyError, "cold_copy_transport_unavailable",
        ) as transport_error:
            failing_drive.upload("snap", data, data_digest, retention_days=1)
        self.assertNotIn(sensitive, str(transport_error.exception))
        self.assertIsNone(transport_error.exception.__cause__)
        self.assertIsNone(transport_error.exception.__context__)

        invalid = manifest()
        invalid["project"] = "token=VERY_PRIVATE_OAUTH_TOKEN_NOT_REAL"
        manifest_fake = FakeDriveTransport()
        manifest_secrets = Secrets()
        with self.assertRaisesRegex(ColdCopyError, "invalid_manifest") as manifest_error:
            GDriveColdCopy(
                invalid, transport=manifest_fake, secret_provider=manifest_secrets,
                credential_ref="gdrive-cold-copy", now=NOW,
            )
        self.assertEqual(manifest_secrets.calls, 0)
        self.assertIsNone(manifest_error.exception.__cause__)
        self.assertIsNone(manifest_error.exception.__context__)

        # Ningún objeto con API parecida puede sustituir el fake incorporado.
        # En particular, el constructor falla ANTES de consultar secretos.
        class SpyTransport:
            calls = 0

            def put_if_absent(self, *args):
                self.calls += 1
                raise AssertionError("unexpected_transport_call")

            def read(self, *args):
                self.calls += 1
                raise AssertionError("unexpected_transport_call")

            def read_with_expiry(self, *args):
                self.calls += 1
                raise AssertionError("unexpected_transport_call")

            def purge_expired(self, *args):
                self.calls += 1
                raise AssertionError("unexpected_transport_call")

        class UnsafeSubclass(FakeDriveTransport):
            def put_if_absent(self, *args):
                raise AssertionError("subclass_must_not_run")

        valid_manifest = manifest()
        for untrusted in (SpyTransport(), UnsafeSubclass()):
            with self.subTest(transport=type(untrusted).__name__):
                gated_secrets = Secrets()
                with self.assertRaisesRegex(
                    ColdCopyError, "fake_transport_required",
                ):
                    GDriveColdCopy(
                        valid_manifest, transport=untrusted,
                        secret_provider=gated_secrets,
                        credential_ref="gdrive-cold-copy", now=NOW,
                    )
                self.assertEqual(gated_secrets.calls, 0)
                if isinstance(untrusted, SpyTransport):
                    self.assertEqual(untrusted.calls, 0)

        # Se comprueba de nuevo el trust boundary antes de CADA operación.
        # La vista pública no admite reemplazos tras construir el adaptador.
        transport = FakeDriveTransport()
        creds = Secrets()
        drive = instance(transport=transport, secrets=creds)
        with self.assertRaises(AttributeError):
            drive.transport = SpyTransport()
        self.assertIs(drive.transport, transport)
        transport.put_if_absent = lambda *_args: (_ for _ in ()).throw(
            AssertionError("instance_override_reached")
        )
        with self.assertRaisesRegex(ColdCopyError, "fake_transport_required"):
            drive.upload("snap", data, data_digest, retention_days=1)
        self.assertEqual(creds.calls, 0)
        self.assertEqual(transport.writes, 0)
        del transport.put_if_absent

        drive._fake_transport = SpyTransport()
        with self.assertRaisesRegex(ColdCopyError, "fake_transport_required"):
            drive.upload("snap", data, data_digest, retention_days=1)
        self.assertEqual(creds.calls, 0)
        self.assertEqual(drive._fake_transport.calls, 0)

    def test_fake_roundtrip_and_retention_namespace(self):
        fake = FakeDriveTransport()
        first = instance("condor", transport=fake, allow=True)
        second = instance("grindflow", transport=fake, allow=True)
        content = b"fake-test-ciphertext"
        content_digest = sha(content)
        one = first.upload("nightly", content, content_digest, retention_days=1)
        two = second.upload("nightly", content, content_digest, retention_days=7)
        self.assertNotEqual(one["namespace"], two["namespace"])
        self.assertEqual(len(fake.objects), 2)
        self.assertEqual(first.materialize_fake(
            "nightly", content_digest, purpose="offline_restore_test"), content)
        # The same adapter instance must NOT certify stale retention simply
        # because it was constructed before expiry (no sleep or real network).
        with patch("recovery.gdrive_adapter.monotonic", return_value=100.0) as clock:
            same_fake = FakeDriveTransport()
            same = instance("condor", transport=same_fake, allow=True)
            same.upload("same-instance", content, content_digest, retention_days=1)
            clock.return_value = 100.0 + 2 * 24 * 3600
            with self.assertRaisesRegex(ColdCopyError, "expired_remote_copy"):
                same.materialize_fake(
                    "same-instance", content_digest, purpose="offline_restore_test",
                )
            with self.assertRaisesRegex(ColdCopyError, "expired_remote_copy"):
                same.upload("same-instance", content, content_digest, retention_days=7)
            self.assertEqual(same_fake.writes, 1)
        aged = GDriveColdCopy(
            manifest("condor"), transport=fake, secret_provider=Secrets(),
            credential_ref="gdrive-cold-copy", now=NOW + timedelta(days=2),
            restore_authorizer=lambda _request: True,
        )
        # La copia aún existe en memoria, pero ya venció: ni el retry
        # idempotente ni el restore pueden declarar evidencia positiva.
        with self.assertRaisesRegex(ColdCopyError, "expired_remote_copy"):
            aged.upload("nightly", content, content_digest, retention_days=7)
        with self.assertRaisesRegex(ColdCopyError, "expired_remote_copy"):
            aged.materialize_fake(
                "nightly", content_digest, purpose="offline_restore_test")
        self.assertEqual(fake.writes, 2)
        with self.assertRaisesRegex(ColdCopyError, "restore_not_authorized"):
            second.materialize_fake("nightly", content_digest, purpose="live_restore")
        without_approval = instance("condor", transport=fake)
        with self.assertRaisesRegex(ColdCopyError, "restore_not_authorized"):
            without_approval.materialize_fake(
                "nightly", content_digest, purpose="offline_restore_test")
        self.assertEqual(first.expire_fake(at=NOW + timedelta(days=2)), 1)
        self.assertEqual(len(fake.objects), 1)
        self.assertEqual(second.materialize_fake(
            "nightly", content_digest, purpose="offline_restore_test"), content)
        self.assertEqual(second.expire_fake(at=NOW + timedelta(days=2)), 0)
        self.assertEqual(second.expire_fake(at=NOW + timedelta(days=8)), 1)
        self.assertFalse(fake.objects)


if __name__ == "__main__":
    unittest.main()
