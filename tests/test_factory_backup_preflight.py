#!/usr/bin/env python3
"""Synthetic local byte-restore preflight; never reads a product backup or uses a provider."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from time import monotonic_ns
import unittest


FIXTURE = b"Factory FSP-02 isolated restore: SYNTHETIC TEST DATA ONLY\n" * 16


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _restore_verified_copy(backup: Path, dest: Path, expected_sha256: str) -> str:
    """Fail closed before writing if the synthetic source copy is altered."""
    if not backup.is_file() or _sha256(backup) != expected_sha256:
        raise ValueError("synthetic local copy checksum mismatch")
    shutil.copyfile(backup, dest)
    restored_sha = _sha256(dest)
    if restored_sha != expected_sha256:
        dest.unlink(missing_ok=True)
        raise ValueError("synthetic local restore checksum mismatch")
    return restored_sha


def run_synthetic_local_drill() -> dict[str, str | int | bool]:
    """Copy bytes, remove original, restore from isolated local copy, measure duration."""
    start_ns = monotonic_ns()
    with TemporaryDirectory(prefix="factory-fsp02-synthetic-") as folder:
        root = Path(folder)
        source = root / "original-fixture.bin"
        backup_dir = root / "local-copy"
        restore_dir = root / "isolated-restore"
        backup_dir.mkdir()
        restore_dir.mkdir()
        backup = backup_dir / "archive.bin"
        restored = restore_dir / "recovered.bin"

        source.write_bytes(FIXTURE)
        original_sha = _sha256(source)
        shutil.copyfile(source, backup)
        if _sha256(backup) != original_sha:
            raise ValueError("synthetic local copy checksum mismatch")
        source.unlink()
        source_absent_before_restore = not source.exists()
        if not source_absent_before_restore:
            raise AssertionError("original fixture must be removed before restore")
        restored_sha = _restore_verified_copy(backup, restored, original_sha)
        bytes_match = restored.read_bytes() == FIXTURE
        if not bytes_match:
            raise ValueError("synthetic local restored bytes mismatch")
        duration_ns = monotonic_ns() - start_ns
        return {
            "scope": "SYNTHETIC_LOCAL_ONLY",
            "sha256": restored_sha,
            "duration_ns": duration_ns,
            "source_absent_before_restore": source_absent_before_restore,
            "bytes_match": bytes_match,
        }


class FactoryBackupPreflightTests(unittest.TestCase):
    def test_physical_local_roundtrip_after_source_deleted(self) -> None:
        result = run_synthetic_local_drill()
        self.assertEqual("SYNTHETIC_LOCAL_ONLY", result["scope"])
        self.assertTrue(result["source_absent_before_restore"])
        self.assertTrue(result["bytes_match"])
        self.assertEqual(hashlib.sha256(FIXTURE).hexdigest(), result["sha256"])

    def test_corrupt_copy_is_rejected_before_restore(self) -> None:
        with TemporaryDirectory(prefix="factory-fsp02-corrupt-") as folder:
            root = Path(folder)
            backup = root / "synthetic-copy.bin"
            restored = root / "should-not-exist.bin"
            backup.write_bytes(FIXTURE)
            checksum = _sha256(backup)
            backup.write_bytes(FIXTURE + b"TAMPERED")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                _restore_verified_copy(backup, restored, checksum)
            self.assertFalse(restored.exists())

    def test_duration_measured_without_product_rpo_rto_claim(self) -> None:
        result = run_synthetic_local_drill()
        self.assertIsInstance(result["duration_ns"], int)
        self.assertGreaterEqual(result["duration_ns"], 0)
        self.assertNotIn("rpo_minutes", result)
        self.assertNotIn("rto_minutes", result)
        self.assertNotIn("backup_verified", result)
        self.assertNotIn("healthy", result)

    def test_preflight_has_no_provider_or_real_backup_dependencies(self) -> None:
        import ast
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(name.name.split(".")[0] for name in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse(imports & {"requests", "httpx", "urllib", "socket", "boto3", "subprocess", "paramiko"})
        self.assertIn("TemporaryDirectory", source)
        self.assertIn("SYNTHETIC_LOCAL_ONLY", source)


if __name__ == "__main__":
    unittest.main()
