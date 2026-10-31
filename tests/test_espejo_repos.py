"""Regresiones de espejo offline: git local y almacenamiento S3 simulado."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.espejo_repos import (
    REPOSITORIES, MirrorError, GitHubSource, S3Store, _digest,
    _file_secret, export_all, make_bundle, restore_one,
)

SNAPSHOT = "20261031T140000Z-012345abcdef"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.writes: list[str] = []

    def put(self, key: str, content: bytes) -> None:
        if key in self.objects:
            raise MirrorError("Objeto inmutable ya publicado.")
        self.objects[key] = content
        self.writes.append(key)

    def get(self, key: str) -> bytes:
        return self.objects[key]


class SyntheticSource:
    def __init__(self, repository: Path) -> None:
        self.repository = repository
        self.calls: list[str] = []

    def capture(self, repo: str) -> tuple[bytes, list[dict], list[dict]]:
        self.calls.append(repo)
        return (
            make_bundle(str(self.repository)),
            [{"number": 10, "title": "Fixture", "state": "closed",
              "mirror_comments": [{"body": "solo prueba"}]}],
            [{"number": 11, "title": "PR sintético", "state": "merged",
              "mirror_reviews": [{"state": "APPROVED"}],
              "mirror_files": [{"filename": "README.md"}]}],
        )


class EspejoReposTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        self._git("init", str(self.repo))
        self._git("-C", str(self.repo), "config", "user.email", "qa@example.test")
        self._git("-C", str(self.repo), "config", "user.name", "QA")
        (self.repo / "README.md").write_text("contenido de prueba\n", encoding="utf-8")
        self._git("-C", str(self.repo), "add", "README.md")
        self._git("-C", str(self.repo), "commit", "-m", "fixture")
        self._git("-C", str(self.repo), "tag", "v1.0.0")
        self.source = SyntheticSource(self.repo)
        self.store = MemoryStore()

    def _git(self, *args: str) -> str:
        p = subprocess.run(["git", *args], check=True, capture_output=True,
                           text=True, timeout=30)
        return p.stdout.strip()

    def _export(self) -> dict:
        rows = export_all(self.source, self.store, (REPOSITORIES[0],),
                          snapshot=SNAPSHOT)
        self.assertEqual(1, len(rows))
        return rows[0]

    def test_criterio_principal(self) -> None:
        """Exporta código+issues+PRs versionados y restaura con SHA verificable."""
        row = self._export()
        self.assertEqual([REPOSITORIES[0]], self.source.calls)
        self.assertEqual(4, len(self.store.writes))
        self.assertTrue(self.store.writes[-1].endswith("/manifest.json"))
        manifest_bytes = self.store.get(row["key"])
        self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), row["sha256"])
        manifest = json.loads(manifest_bytes)
        self.assertEqual(1, manifest["format"])
        self.assertEqual(REPOSITORIES[0], manifest["repo"])
        self.assertEqual(SNAPSHOT, manifest["snapshot"])
        for item in manifest["objects"].values():
            content = self.store.get(item["key"])
            self.assertEqual(len(content), item["size"])
            self.assertEqual(_digest(content), item["sha256"])
        restored = self.root / "result"
        result = restore_one(self.store, row["key"], row["sha256"], restored)
        self.assertTrue(result["verified"])
        self.assertEqual(
            "contenido de prueba",
            self._git("--git-dir", str(restored / "repository.git"),
                      "show", "HEAD:README.md"),
        )
        self.assertIn("refs/tags/v1.0.0",
                      self._git("--git-dir", str(restored / "repository.git"),
                                "show-ref", "--tags"))
        self.assertEqual("Fixture",
                         json.loads((restored / "issues.json").read_text())[0]["title"])
        self.assertEqual("PR sintético",
                         json.loads((restored / "pulls.json").read_text())[0]["title"])
        self.assertEqual(manifest_bytes, (restored / "manifest.json").read_bytes())

    def test_integrity_failure_never_creates_restore_destination(self) -> None:
        row = self._export()
        manifest = json.loads(self.store.get(row["key"]))
        bundle_key = manifest["objects"]["repository.bundle"]["key"]
        self.store.objects[bundle_key] += b"alterado"
        destination = self.root / "not-created"
        with self.assertRaisesRegex(MirrorError, "Integridad"):
            restore_one(self.store, row["key"], row["sha256"], destination)
        self.assertFalse(destination.exists())

    def test_manifest_tamper_or_wrong_expected_hash_fails_closed(self) -> None:
        row = self._export()
        path = self.root / "not-created"
        with self.assertRaisesRegex(MirrorError, "Huella"):
            restore_one(self.store, row["key"], "0" * 64, path)
        self.store.objects[row["key"]] += b" "
        with self.assertRaisesRegex(MirrorError, "Huella"):
            restore_one(self.store, row["key"], row["sha256"], path)
        self.assertFalse(path.exists())

    def test_existing_destination_cannot_be_replaced(self) -> None:
        row = self._export()
        dest = self.root / "exists"
        dest.mkdir()
        sentinel = dest / "sentinel"
        sentinel.write_text("preservar")
        with self.assertRaisesRegex(MirrorError, "Destino"):
            restore_one(self.store, row["key"], row["sha256"], dest)
        self.assertEqual("preservar", sentinel.read_text())

    def test_unknown_repositories_and_traversal_are_rejected(self) -> None:
        for repos in (("pl0n3r/Unknown",), (REPOSITORIES[0], REPOSITORIES[0]), ()):
            with self.subTest(repos=repos), self.assertRaises(MirrorError):
                export_all(self.source, self.store, repos, snapshot=SNAPSHOT)
        with self.assertRaises(MirrorError):
            export_all(self.source, self.store, (REPOSITORIES[0],),
                       prefix="../secrets", snapshot=SNAPSHOT)
        with self.assertRaises(MirrorError):
            export_all(self.source, self.store, (REPOSITORIES[0],),
                       snapshot="invalid")
        with self.assertRaises(MirrorError):
            make_bundle("https://evil.example/repository.git")

    def test_metadata_versioned_and_manifest_is_published_last(self) -> None:
        a = self._export()
        b = export_all(self.source, self.store, (REPOSITORIES[1],),
                       snapshot="20261031T140100Z-012345abcdef")[0]
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual(8, len(self.store.writes))
        self.assertTrue(self.store.writes[3].endswith("manifest.json"))
        self.assertTrue(self.store.writes[7].endswith("manifest.json"))
        self.assertEqual(REPOSITORIES[0],
                         json.loads(self.store.get(a["key"]))["repo"])
        self.assertEqual(REPOSITORIES[1],
                         json.loads(self.store.get(b["key"]))["repo"])

    def test_partial_upload_never_publishes_manifest(self) -> None:
        class FailingStore(MemoryStore):
            def put(self, key: str, content: bytes) -> None:
                if key.endswith("pulls.json"):
                    raise MirrorError("Almacén no disponible.")
                super().put(key, content)
        storage = FailingStore()
        with self.assertRaises(MirrorError):
            export_all(self.source, storage, (REPOSITORIES[0],), snapshot=SNAPSHOT)
        self.assertFalse(any(x.endswith("manifest.json") for x in storage.writes))

    def test_private_file_contract_and_https_fail_closed(self) -> None:
        secret = self.root / "token"
        secret.write_text("value\n", encoding="utf-8")
        secret.chmod(0o600)
        with patch.dict(os.environ, {"TEST_SECRET_FILE": str(secret)}):
            self.assertEqual("value", _file_secret("TEST_SECRET_FILE"))
            secret.chmod(0o644)
            with self.assertRaises(MirrorError):
                _file_secret("TEST_SECRET_FILE")
        with self.assertRaises(MirrorError):
            S3Store("http://example.com", "bucket", "us-west-004", "id", "secret")
        with self.assertRaises(MirrorError):
            S3Store("https://user:pass@example.com", "bucket",
                    "us-west-004", "id", "secret")

    def test_gh_api_rejects_untrusted_routes_without_network(self) -> None:
        api = GitHubSource("synthetic")
        for route in ("https://evil.example", "repos/x/y/issues",
                      "repos/pl0n3r/Factory/actions",
                      "repos/pl0n3r/Factory/issues/../../secrets"):
            with self.subTest(route=route), self.assertRaises(MirrorError):
                api._page(route, 1)


if __name__ == "__main__":
    unittest.main()
