import json
import tempfile
import unittest
from pathlib import Path

from scripts.read_version import VersionError, canonical_source, read_version

class T(unittest.TestCase):
    def _root(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "config").mkdir()
        return root

    def test_real_consumer_shapes_without_executing_php(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            php = root / "config/version.php"

            php.write_text(
                "<?php return ['version' => '0.1.32'];",
                encoding="utf-8",
            )
            self.assertEqual(
                read_version("config/version.php", "auto", "version", root=root),
                "0.1.32",
            )

            php.write_text(
                "<?php return ['number' => '0.1.122'];",
                encoding="utf-8",
            )
            self.assertEqual(
                read_version("config/version.php", "auto", "number", root=root),
                "0.1.122",
            )

            php.write_text(
                "<?php const BRVTAL_APP_VERSION = '0.1.51'; "
                "file_put_contents('/tmp/should-not-run','x');",
                encoding="utf-8",
            )
            self.assertEqual(
                read_version(
                    "config/version.php",
                    "auto",
                    "BRVTAL_APP_VERSION",
                    root=root,
                ),
                "0.1.51",
            )

            (root / "config/version.json").write_text(
                json.dumps({"version": "0.1.0"}),
                encoding="utf-8",
            )
            self.assertEqual(
                read_version(
                    "config/version.json",
                    "auto",
                    "version",
                    root=root,
                ),
                "0.1.0",
            )

    def test_source_is_closed_allowlist(self):
        self.assertEqual(
            canonical_source("config/version.php"),
            Path("config/version.php"),
        )
        for source in (
            "../version.php",
            "/tmp/version.php",
            "custom/version.php",
            "config/../version.php",
        ):
            with self.subTest(source=source):
                with self.assertRaises(VersionError):
                    canonical_source(source)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            real = root / "real.php"
            real.write_text("<?php return ['version'=>'1.2.3'];", encoding="utf-8")
            (root / "config/version.php").symlink_to(real)
            with self.assertRaises(VersionError):
                read_version("config/version.php", "auto", "version", root=root)

    def test_invalid_key_or_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            (root / "config/version.php").write_text(
                "<?php return ['version'=>'not-semver'];",
                encoding="utf-8",
            )
            with self.assertRaises(VersionError):
                read_version("config/version.php", "auto", "version", root=root)
            with self.assertRaises(VersionError):
                read_version("config/version.php", "auto", "../version", root=root)
