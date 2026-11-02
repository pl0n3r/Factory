"""Regresiones de espejo offline: git local y almacenamiento S3 simulado."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

from scripts.espejo_repos import (
    REPOSITORIES, MirrorError, GitHubSource, S3Store, _digest,
    _file_secret, export_all, make_bundle, restore_one, main,
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


    def test_s3_signing_and_https_transport_are_explicit(self) -> None:
        store = S3Store("https://s3.us-west-004.backblazeb2.com",
                        "factory-mirror", "us-west-004", "fake-id", "fake-secret")
        class Transport:
            def __init__(self) -> None:
                self.calls = []
            def open(self, request, timeout=0):
                self.calls.append(request)
                if request.get_method() == "GET":
                    return io.BytesIO(b"contenido remoto")
                return io.BytesIO(b"")
        transport = Transport()
        store._http = transport
        store.put("mirror/version/test.bin", b"contenido")
        self.assertEqual(b"contenido remoto", store.get("mirror/version/test.bin"))
        self.assertEqual(2, len(transport.calls))
        put = transport.calls[0]
        self.assertEqual("PUT", put.get_method())
        self.assertEqual(b"contenido", put.data)
        self.assertTrue(put.full_url.startswith("https://s3.us-west-004.backblazeb2.com/factory-mirror/"))
        self.assertIn("Authorization", put.headers)
        self.assertIn("AWS4-HMAC-SHA256", put.headers["Authorization"])
        self.assertIn("X-amz-content-sha256", put.headers)
        self.assertEqual(_digest(b"contenido"), put.headers["X-amz-content-sha256"])
        self.assertEqual("GET", transport.calls[1].get_method())
        with self.assertRaises(MirrorError):
            store._request("DELETE", "mirror/a")
        with self.assertRaises(MirrorError):
            store.get("../secret")
        with self.assertRaises(MirrorError):
            store.get("mirror//escape")

    def test_s3_transport_error_is_sanitized(self) -> None:
        store = S3Store("https://s3.example.test", "bucket", "us-west-004",
                        "testid", "testsecret")
        class Broken:
            def open(self, request, timeout=0):
                raise OSError("fake-secret-should-not-leak")
        store._http = Broken()
        with self.assertRaises(MirrorError) as err:
            store.put("mirror/a", b"abc")
        self.assertNotIn("fake-secret", str(err.exception))
        for endpoint, bucket, region in (
            ("https://user@evil.example", "bucket", "us-west-004"),
            ("https://s3.example.test/path", "bucket", "us-west-004"),
            ("https://s3.example.test", "BAD BUCKET", "us-west-004"),
            ("https://s3.example.test", "bucket", "BAD REGION"),
        ):
            with self.subTest(endpoint=endpoint, bucket=bucket, region=region):
                with self.assertRaises(MirrorError):
                    S3Store(endpoint, bucket, region, "fake", "fake")

    def test_github_page_pagination_and_content_validation(self) -> None:
        api = GitHubSource("synthetic")
        class Transport:
            def __init__(self, payloads):
                self.payloads = list(payloads)
                self.paths = []
            def open(self, req, timeout=0):
                self.paths.append(req.full_url)
                return io.BytesIO(self.payloads.pop(0))
        t = Transport([json.dumps([{"number": i} for i in range(100)]).encode(),
                       b'[{"number": 101}, {"number": 102}]'])
        api._http = t
        all_issues = api._all("repos/pl0n3r/Factory/issues")
        self.assertEqual(102, len(all_issues))
        self.assertEqual(2, len(t.paths))
        self.assertIn("page=2", t.paths[-1])
        self.assertEqual("Bearer synthetic", t.paths[0] and "Bearer synthetic")
        for data in (b'{"message":"forbidden"}', b'null', b'[1,2]',
                     b'[{}] trailing', b"\xff"):
            api._http = Transport([data])
            with self.subTest(data=data), self.assertRaises(MirrorError):
                api._page("repos/pl0n3r/Factory/issues", 1)

    def test_github_capture_archives_conversation_metadata(self) -> None:
        api = GitHubSource("synthetic")
        calls = []
        def listing(path):
            calls.append(path)
            if path.endswith("/issues"):
                return [
                    {"number": 1, "title": "un issue"},
                    {"number": 2, "pull_request": {"url": "example"}},
                ]
            if path.endswith("/pulls"):
                return [{"number": 2, "title": "un PR"}]
            if path.endswith("/reviews"):
                return [{"state": "COMMENTED"}]
            if path.endswith("/files"):
                return [{"filename": "a.py"}]
            return [{"body": "comentario"}]
        api._all = listing
        with patch("scripts.espejo_repos.make_bundle", return_value=b"bundle") as clone:
            archive, issues, pulls = api.capture(REPOSITORIES[0])
        clone.assert_called_once()
        self.assertEqual(b"bundle", archive)
        self.assertEqual(1, len(issues))
        self.assertEqual("comentario", issues[0]["mirror_comments"][0]["body"])
        self.assertEqual("COMMENTED", pulls[0]["mirror_reviews"][0]["state"])
        self.assertEqual("a.py", pulls[0]["mirror_files"][0]["filename"])
        self.assertEqual(7, len(calls))
        self.assertIn("repos/pl0n3r/Factory/pulls/2/comments", calls)
        with self.assertRaises(MirrorError):
            api.capture("pl0n3r/noncanonical")

    def test_restore_rejects_broken_manifest_structure_before_writing(self) -> None:
        row = self._export()
        valid = json.loads(self.store.get(row["key"]))
        variants = []
        changed = dict(valid); changed["format"] = 9; variants.append(changed)
        changed = dict(valid); changed["repo"] = "pl0n3r/unknown"; variants.append(changed)
        changed = dict(valid); changed["snapshot"] = "../../unsafe"; variants.append(changed)
        changed = dict(valid); changed["objects"] = {}; variants.append(changed)
        changed = dict(valid); changed["extra"] = 1; variants.append(changed)
        for index, invalid in enumerate(variants):
            raw = (json.dumps(invalid) + "\n").encode()
            self.store.objects[row["key"]] = raw
            with self.subTest(index=index), self.assertRaises(MirrorError):
                restore_one(self.store, row["key"], _digest(raw),
                            self.root / ("bad-" + str(index)))
            self.assertFalse((self.root / ("bad-" + str(index))).exists())
        with self.assertRaises(MirrorError):
            restore_one(self.store, "../manifest.json", "a" * 64,
                        self.root / "bad-metadata")
        with self.assertRaises(MirrorError):
            restore_one(self.store, row["key"], "nothash", self.root / "bad-hash")

    def test_restore_rejects_invalid_object_metadata_and_json(self) -> None:
        row = self._export()
        original = json.loads(self.store.get(row["key"]))
        for case in ("wrong-key", "wrong-size", "wrong-digest", "invalid-json"):
            manifest = json.loads(json.dumps(original))
            issue = manifest["objects"]["issues.json"]
            if case == "wrong-key":
                issue["key"] = "other/object.json"
            elif case == "wrong-size":
                issue["size"] += 1
            elif case == "wrong-digest":
                issue["sha256"] = "e" * 64
            else:
                target = issue["key"]
                self.store.objects[target] = b"{}"
                issue["size"] = 2
                issue["sha256"] = _digest(b"{}")
            raw = (json.dumps(manifest) + "\n").encode()
            self.store.objects[row["key"]] = raw
            dest = self.root / ("bad-objects-" + case)
            with self.subTest(case=case), self.assertRaises(MirrorError):
                restore_one(self.store, row["key"], _digest(raw), dest)
            self.assertFalse(dest.exists())
            self.store.objects[original["objects"]["issues.json"]["key"]] = (
                json.dumps([{"number": 10}]) + "\n").encode()
            # Reestablecer el contenido original y su huella antes de la siguiente variante.
            source_row = self.source.capture(REPOSITORIES[0])[1]
            self.store.objects[original["objects"]["issues.json"]["key"]] = (
                json.dumps(source_row, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode()

    def test_export_rejects_invalid_source_payload(self) -> None:
        class BrokenSource:
            def capture(self, repo):
                return "", [], []
        with self.assertRaises(MirrorError):
            export_all(BrokenSource(), self.store, (REPOSITORIES[0],),
                       snapshot=SNAPSHOT)
        class HugeSource:
            def capture(self, repo):
                return b"ok", {"not": "a list"}, []
        with self.assertRaisesRegex(MirrorError, "Metadatos"):
            export_all(HugeSource(), self.store, (REPOSITORIES[0],),
                       snapshot=SNAPSHOT)
        with self.assertRaises(MirrorError):
            export_all(self.source, self.store, (REPOSITORIES[0],),
                       prefix="mirror//bad", snapshot=SNAPSHOT)

    def test_cli_export_restore_with_mocked_dependencies(self) -> None:
        opts = {
            "B2_S3_ENDPOINT": "https://s3.example.test",
            "B2_S3_BUCKET": "factory",
            "B2_S3_REGION": "us-west-004",
        }
        with patch.dict(os.environ, opts):
            with patch("scripts.espejo_repos._file_secret", return_value="fake"):
                with patch("scripts.espejo_repos.S3Store") as storage:
                    with patch("scripts.espejo_repos.GitHubSource") as api:
                        with patch("scripts.espejo_repos.export_all",
                                   return_value=[{"repo": REPOSITORIES[0]}]) as exp:
                            with patch("sys.stdout", new_callable=io.StringIO) as output:
                                self.assertEqual(0, main(["export", "--prefix", "further"]))
                                self.assertIn(REPOSITORIES[0], output.getvalue())
                                exp.assert_called_once()
                                api.assert_called_once()
                        with patch("scripts.espejo_repos.restore_one",
                                   return_value={"verified": True}) as restore:
                            with patch("sys.stdout", new_callable=io.StringIO) as output:
                                self.assertEqual(0, main([
                                    "restore", "--manifest-key", "mirror/x/manifest.json",
                                    "--manifest-sha256", "0" * 64,
                                    "--destination", str(self.root / "restore"),
                                ]))
                                self.assertIn("verified", output.getvalue())
                                restore.assert_called_once()
        with patch("scripts.espejo_repos._file_secret",
                   side_effect=MirrorError("Falta archivo privado: B2_KEY_ID_FILE")):
            with patch("sys.stderr", new_callable=io.StringIO) as errors:
                self.assertEqual(2, main(["export"]))
                self.assertIn("Espejo detenido", errors.getvalue())

    def test_secret_file_invalid_missing_symlink_and_multiline(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MirrorError):
                _file_secret("MISSING_FILE")
        secret = self.root / "secret"
        secret.write_text("one\ntwo", encoding="utf-8")
        secret.chmod(0o600)
        with patch.dict(os.environ, {"SAMPLE_FILE": str(secret)}):
            with self.assertRaises(MirrorError):
                _file_secret("SAMPLE_FILE")
            link = self.root / "alias"
            link.symlink_to(secret)
            with patch.dict(os.environ, {"SAMPLE_FILE": str(link)}):
                with self.assertRaises(MirrorError):
                    _file_secret("SAMPLE_FILE")
            secret.write_text("x" * 4097, encoding="utf-8")
            with self.assertRaises(MirrorError):
                _file_secret("SAMPLE_FILE")
            secret.write_text("", encoding="utf-8")
            with self.assertRaises(MirrorError):
                _file_secret("SAMPLE_FILE")


if __name__ == "__main__":
    unittest.main()
