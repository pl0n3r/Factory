import json
import tempfile
import unittest
from pathlib import Path
from scripts.read_version import VersionError, read_version

class T(unittest.TestCase):
    def test_json_text_and_php_are_data_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "v.json").write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")
            (root / "v.txt").write_text("2.3.4\n", encoding="utf-8")
            (root / "v.php").write_text(
                "<?php return ['version' => '3.4.5']; file_put_contents('/tmp/should-not-run','x');",
                encoding="utf-8",
            )
            self.assertEqual(read_version(Path("v.json"), "json", "version", root=root), "1.2.3")
            self.assertEqual(read_version(Path("v.txt"), "text", "version", root=root), "2.3.4")
            self.assertEqual(read_version(Path("v.php"), "php-array", "version", root=root), "3.4.5")

    def test_invalid_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "v.txt").write_text("nope", encoding="utf-8")
            with self.assertRaises(VersionError):
                read_version(Path("v.txt"), "text", "version", root=root)
            with self.assertRaises(VersionError):
                read_version(Path("../outside.txt"), "text", "version", root=root)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("1.2.3\n", encoding="utf-8")
            (root / "link.txt").symlink_to(root / "real.txt")
            with self.assertRaises(VersionError):
                read_version(Path("link.txt"), "text", "version", root=root)
