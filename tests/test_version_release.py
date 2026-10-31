import json
import re
import unittest
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parents[1] / "config" / "version.json"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _tuple(version):
    return tuple(int(part) for part in SEMVER.fullmatch(version).groups())


class VersionReleaseTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))

    def test_version_es_semantica(self):
        self.assertRegex(self.data["version"], SEMVER)

    def test_criterio_principal(self):
        # 1.0.44 ya está publicada como v1.0.44: la candidata debe ser mayor para poder abrir la ventana de release.
        self.assertGreater(_tuple(self.data["version"]), (1, 0, 44))

    def test_solo_declara_version(self):
        self.assertEqual(set(self.data), {"version"})


if __name__ == "__main__":
    unittest.main()
