"""Tests use an in-memory opaque fake. This is NOT real encryption."""
import json
import unittest
from collections.abc import Mapping
from hashlib import sha256
from recovery.encryption import EncryptionContractError, open_backup, seal_backup


class FakeKeys:
    def __init__(self):
        self.material = {"epoch1": b"fake-secret-epoch-1"}
        self.active = "epoch1"

    def resolve(self, ref):
        return self.material[ref]

    def rotate(self):
        self.material["epoch2"] = b"fake-secret-epoch-2"
        self.active = "epoch2"


class OpaqueInMemoryFake:
    simulation_only = True

    def __init__(self):
        self.items = {}

    def seal(self, data, key, aad):
        # A deterministic opaque reference for unit tests, NOT ciphertext.
        opaque = sha256(key + aad + data).digest()
        self.items[opaque] = (data, key, aad)
        return opaque

    def open(self, token, key, aad):
        data, saved_key, saved_aad = self.items[token]
        if saved_key != key or saved_aad != aad:
            raise ValueError("fake authentication failed")
        return data


class RecoveryEncryptionTests(unittest.TestCase):
    def test_rotated_key_registry_restores_historical_artifact(self):
        keys = FakeKeys(); fake = OpaqueInMemoryFake()
        original = seal_backup("grindflow", keys.active, b"old backup", keys, fake)
        keys.rotate()
        current = seal_backup("grindflow", keys.active, b"new backup", keys, fake)
        self.assertEqual(open_backup("grindflow", original, keys, fake), b"old backup")
        self.assertEqual(open_backup("grindflow", current, keys, fake), b"new backup")
        self.assertTrue(original["simulation_only"])
        self.assertFalse(current["external_transfer_allowed"])
        with self.assertRaises(EncryptionContractError):
            open_backup("condor", original, keys, fake)
        del keys.material["epoch1"]
        with self.assertRaises(EncryptionContractError):
            open_backup("grindflow", original, keys, fake)

    def test_secret_material_never_enters_artifact_or_error(self):
        keys = FakeKeys(); fake = OpaqueInMemoryFake()
        plaintext = b"top private payload"
        artifact = seal_backup("grindflow", "epoch1", plaintext, keys, fake)
        serialized = json.dumps(artifact)
        self.assertNotIn(plaintext.decode(), serialized)
        self.assertNotIn(keys.material["epoch1"].decode(), serialized)
        fake.items.clear()
        with self.assertRaises(EncryptionContractError) as error:
            open_backup("grindflow", artifact, keys, fake)
        self.assertNotIn(plaintext.decode(), str(error.exception))
        self.assertNotIn(keys.material["epoch1"].decode(), str(error.exception))
        with self.assertRaises(EncryptionContractError):
            seal_backup("grindflow", "epoch1", plaintext, keys, object())
        self.assertFalse(artifact["external_transfer_allowed"])

        # JSON booleans/floats must never masquerade as schema version 1.
        for bad_version in (True, False, 1.0, "1", None):
            with self.subTest(bad_version=bad_version):
                with self.assertRaises(EncryptionContractError) as caught:
                    open_backup("grindflow", {**artifact, "version": bad_version}, keys, fake)
                self.assertEqual(str(caught.exception), "Invalid sealed artifact.")
        self.assertEqual(artifact["version"], 1)

        class MaliciousArtifact(Mapping):
            def __len__(self):
                return 6
            def __iter__(self):
                raise RuntimeError("sensitive-artifact-sentinel")
            def __getitem__(self, key):
                raise RuntimeError("sensitive-artifact-sentinel")

        with self.assertRaises(EncryptionContractError) as caught:
            open_backup("grindflow", MaliciousArtifact(), keys, fake)
        self.assertNotIn("sensitive-artifact-sentinel", str(caught.exception))

        class MaliciousBackend:
            @property
            def simulation_only(self):
                raise RuntimeError("sensitive-backend-sentinel")

        for call in (
            lambda: seal_backup("grindflow", "epoch1", plaintext, keys, MaliciousBackend()),
            lambda: open_backup("grindflow", artifact, keys, MaliciousBackend()),
        ):
            with self.assertRaises(EncryptionContractError) as caught:
                call()
            self.assertNotIn("sensitive-backend-sentinel", str(caught.exception))
