"""Regresiones del paquete jurídico y el monitor fail-closed."""
import shutil
import tempfile
from pathlib import Path
import unittest
from scripts.generar_revision_juridica import (
    ROOT, SOURCES, INDEX, PACK, RevisionError, metadata,
    check, expected, generate, main,
)

class RevisionJuridicaTests(unittest.TestCase):
    def test_generated_artifacts_are_current(self):
        """AC-01: ocho copias exactas, índice, paquete y workflow seguro."""
        self.assertEqual(len(SOURCES), 8)
        self.assertEqual(check(ROOT), [])
        self.assertEqual(len(expected(ROOT, *metadata(ROOT))), 10)
        packet = (ROOT / PACK).read_bytes()
        for source in SOURCES:
            with self.subTest(source=source):
                self.assertEqual((ROOT / "revision-juridica" / source).read_bytes(),
                                 (ROOT / source).read_bytes())
                self.assertIn(("## Fuente: " + source).encode("utf-8"), packet)
        self.assertIn(b"documented_not_legally_approved", packet)
        self.assertEqual(main(["--check"]), 0)
        workflow = (ROOT / ".github/workflows/revision-juridica-sync.yml").read_text()
        for key in ("schedule:", "branches: [main]", "contents: read",
                    "issues: write", "revision-juridica-desfase",
                    "scripts/generar_revision_juridica.py --check",
                    "gh issue list", "gh issue create", "estado: disponible",
                    "factory-acceptance", "factory-plan-task",
                    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"):
            with self.subTest(key=key):
                self.assertIn(key, workflow)
        for forbidden in ("pull_request:", "contents: write", "git push"):
            self.assertNotIn(forbidden, workflow)

    def _fixture(self, temp):
        root = Path(temp)
        for name in [*SOURCES, "config/version.json"]:
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
        generate(root, "2026-10-18T02:10:00Z", "a987aad534434de910335479e218818ced8ee1aa")
        return root

    def test_check_is_read_only_and_detects_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._fixture(temp)
            packet = (root / PACK).read_bytes()
            self.assertEqual(main(["--check"], root=root), 0)
            self.assertEqual((root / PACK).read_bytes(), packet)
            source = root / SOURCES[0]
            source.write_bytes(source.read_bytes() + b"\nNEW\n")
            self.assertEqual(main(["--check"], root=root), 1)
            self.assertEqual((root / PACK).read_bytes(), packet)
            self.assertIn(PACK, check(root))
            generate(root, "2026-10-18T02:10:00Z", "a987aad534434de910335479e218818ced8ee1aa")
            self.assertEqual(check(root), [])

    def test_missing_source_and_extra_file_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._fixture(temp)
            (root / SOURCES[0]).unlink()
            with self.assertRaises(RevisionError):
                check(root)
        with tempfile.TemporaryDirectory() as temp:
            root = self._fixture(temp)
            (root / "revision-juridica/extra.txt").write_text("unknown")
            self.assertIn("revision-juridica/extra.txt", check(root))
            with self.assertRaises(RevisionError):
                generate(root, "2026-10-18T02:10:00Z", "a987aad534434de910335479e218818ced8ee1aa")

    def test_corrupt_index_or_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._fixture(temp)
            (root / INDEX).write_text("corrupt")
            self.assertEqual(main(["--check"], root=root), 1)
        with tempfile.TemporaryDirectory() as temp:
            root = self._fixture(temp)
            p = root / "revision-juridica" / SOURCES[0]
            p.unlink()
            p.symlink_to(root / SOURCES[0])
            with self.assertRaises(RevisionError):
                check(root)

if __name__ == "__main__":
    unittest.main()
