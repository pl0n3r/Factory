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

    def test_commented_php_versions_do_not_override_active_value(self):
        cases = [
            ("// ['version'=>'1.0.28']\nreturn ['version'=>'1.0.29'];",
             "auto", "version", "1.0.29"),
            ("# ['version'=>'1.0.28']\nreturn ['version'=>'1.0.29'];",
             "php-array", "version", "1.0.29"),
            ("/* ['version'=>'1.0.28'] */ return ['version'=>'1.0.29'];",
             "php-array", "version", "1.0.29"),
            ("// const BRVTAL_APP_VERSION='0.1.140';\n"
             "const BRVTAL_APP_VERSION='0.1.141';",
             "php-const", "BRVTAL_APP_VERSION", "0.1.141"),
            ("# const BRVTAL_APP_VERSION='0.1.140';\n"
             "const BRVTAL_APP_VERSION='0.1.141';",
             "auto", "BRVTAL_APP_VERSION", "0.1.141"),
            ("/* const BRVTAL_APP_VERSION='0.1.140'; */"
             " const BRVTAL_APP_VERSION='0.1.141';",
             "php-const", "BRVTAL_APP_VERSION", "0.1.141"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            path = root / "config/version.php"
            for source, fmt, key, expected in cases:
                with self.subTest(source=source, fmt=fmt):
                    path.write_text("<?php " + source, encoding="utf-8")
                    self.assertEqual(
                        read_version("config/version.php", fmt, key, root=root),
                        expected,
                    )
            for source in (
                "<?php /* ['version'=>'1.0.28'] */ return [];",
                "<?php // const BRVTAL_APP_VERSION='0.1.140';",
            ):
                path.write_text(source, encoding="utf-8")
                with self.assertRaises(VersionError):
                    read_version("config/version.php", "auto", "version", root=root)

    def test_php_string_literals_cannot_supply_fake_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            path = root / "config/version.php"
            cases = [
                ("<?php $note=\"retired: ['version'=>'1.0.28']\";"
                 " return ['version'=>'1.0.29'];", "version", "1.0.29"),
                ("<?php $note=\"const BRVTAL_APP_VERSION='1.0.1';\";"
                 " const BRVTAL_APP_VERSION='1.0.2';",
                 "BRVTAL_APP_VERSION", "1.0.2"),
                ("<?php ?> const BRVTAL_APP_VERSION='1.0.9';"
                 " <?php const BRVTAL_APP_VERSION='1.0.3';",
                 "BRVTAL_APP_VERSION", "1.0.3"),
            ]
            for source, key, expected in cases:
                with self.subTest(key=key, source=source):
                    path.write_text(source, encoding="utf-8")
                    self.assertEqual(
                        read_version("config/version.php", "auto", key, root=root),
                        expected,
                    )
            path.write_text(
                "<?php $s=\"return ['version'=>'9.9.9'];\";",
                encoding="utf-8",
            )
            with self.assertRaises(VersionError):
                read_version("config/version.php", "auto", "version", root=root)

    def test_conflicting_active_php_versions_fail_closed(self):
        cases = [
            ("return ['version'=>'1.0.1']; return ['version'=>'1.0.2'];",
             "version"),
            ("const BRVTAL_APP_VERSION='1.0.1';"
             " const BRVTAL_APP_VERSION='1.0.2';", "BRVTAL_APP_VERSION"),
            ("return ['version'=>'1.0.1']; const version='1.0.2';",
             "version"),
            ("return ['version'=>'1.0.1';", "version"),
            ("return ['version'=>'1.0.1']", "version"),
            ("/* unterminated ", "version"),
            ("return ['version'=>123];", "version"),
            ("return ['version'=>'1.0.1']; <<<HEREDOC", "version"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            path = root / "config/version.php"
            for source, key in cases:
                with self.subTest(source=source):
                    path.write_text("<?php " + source, encoding="utf-8")
                    with self.assertRaises(VersionError):
                        read_version("config/version.php", "auto", key, root=root)
            path.write_text(
                "<?php return ['number'=>'2.3.4','version'=>'1.2.3'];",
                encoding="utf-8",
            )
            self.assertEqual(
                read_version("config/version.php", "auto", "number", root=root),
                "2.3.4",
            )
            (root / "config/version.json").write_text(
                '{"version":"4.5.6"}', encoding="utf-8",
            )
            self.assertEqual(
                read_version("config/version.json", "auto", "version", root=root),
                "4.5.6",
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
