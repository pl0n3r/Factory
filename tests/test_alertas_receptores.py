"""Deterministic and adversarial checks for offline alert recipient resolution."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "alertas_receptores.py"
SPEC = importlib.util.spec_from_file_location("factory_alertas_receptores", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("recipient contract unavailable")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AlertasReceptoresTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = MODULE.load_config()

    def test_resuelve_receptores_activos(self) -> None:
        """AC-01: owner is sole default; repo/severity/date/active truly filter."""
        self.assertEqual(1, len(self.base["receptores"]))
        selected = MODULE.resolve(self.base, "pl0n3r/Factory", "critical", "2026-10-30T12:00:00Z")
        self.assertEqual(["owner"], [row["id"] for row in selected])
        self.assertEqual("FACTORY_ALERT_OWNER_DESTINATION", selected[0]["secreto_ref"])
        for repo in MODULE.REPOS:
            self.assertEqual(["owner"], [r["id"] for r in MODULE.resolve(self.base, repo, "info", "2026-10-31T00:00:00Z")])
        self.assertEqual([], MODULE.resolve(self.base, "pl0n3r/Factory", "warning", "2026-10-29T23:59:59Z"))
        inactive = deepcopy(self.base)
        inactive["receptores"][0]["activo"] = False
        self.assertEqual([], MODULE.resolve(inactive, "pl0n3r/Factory", "critical", "2026-10-30T12:00:00Z"))
        scoped = deepcopy(self.base)
        scoped["receptores"][0].update({"repos": ["pl0n3r/GrindFlow"], "gravedades": ["critical"], "hasta": "2026-11-01T00:00:00Z"})
        self.assertEqual([], MODULE.resolve(scoped, "pl0n3r/Factory", "critical", "2026-10-30T12:00:00Z"))
        self.assertEqual([], MODULE.resolve(scoped, "pl0n3r/GrindFlow", "warning", "2026-10-30T12:00:00Z"))
        self.assertEqual(["owner"], [r["id"] for r in MODULE.resolve(scoped, "pl0n3r/GrindFlow", "critical", "2026-10-31T23:59:59Z")])
        self.assertEqual([], MODULE.resolve(scoped, "pl0n3r/GrindFlow", "critical", "2026-11-01T00:00:00Z"))

    def test_rechaza_configuracion_invalida(self) -> None:
        """Duplicates, unknown scopes, forged flags and invalid windows fail closed."""
        variants = []
        for field, value in [
            ("activo", 1), ("repos", ["*"] * 2),
            ("repos", ["*", "pl0n3r/Factory"]),
            ("repos", ["pl0n3r/NoExiste"]),
            ("gravedades", ["critical", "critical"]),
            ("gravedades", ["emergency"]),
            ("desde", "2026-02-30T00:00:00Z"),
            ("desde", "2026-10-30T00:00:00+00:00"),
            ("hasta", "2026-10-30T00:00:00Z"),
            ("secreto_ref", "owner@example.test"),
            ("secreto_ref", "https://example.test"),
            ("nombre", "contact@example.test"),
            ("canal", "arbitrary"),
        ]:
            case = deepcopy(self.base)
            case["receptores"][0][field] = value
            variants.append(case)
        duplicated = deepcopy(self.base)
        duplicated["receptores"].append(deepcopy(duplicated["receptores"][0]))
        variants.append(duplicated)
        extra = deepcopy(self.base)
        extra["receptores"][0]["token"] = "SYNTHETIC_NEVER_ECHO"
        variants.append(extra)
        for case in variants:
            with self.subTest(case=case["receptores"][0]):
                with self.assertRaises(MODULE.ConfigError):
                    MODULE.resolve(case, "pl0n3r/Factory", "critical", "2026-10-30T12:00:00Z")
        with self.assertRaises(MODULE.ConfigError):
            MODULE.resolve(self.base, "pl0n3r/Bad", "critical", "2026-10-30T12:00:00Z")
        with self.assertRaises(MODULE.ConfigError):
            MODULE.resolve(self.base, "pl0n3r/Factory", "Bad", "2026-10-30T12:00:00Z")

    def test_documento_y_cli_no_exponen_secretos(self) -> None:
        """CLI outputs metadata only; duplicate JSON keys and secrets fail shut."""
        data = json.dumps(self.base).replace('"version": 1', '"version": 1, "version": 1', 1)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "recipients.yml"
            path.write_text(data, encoding="utf-8")
            with self.assertRaises(MODULE.ConfigError):
                MODULE.load_config(path)
            path.write_text(json.dumps(self.base), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--repo", "pl0n3r/Factory", "--gravedad", "critical", "--instante", "2026-10-30T12:00:00Z"], capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(["owner"], [r["id"] for r in json.loads(result.stdout)["receptores"]])
            self.assertNotIn("SYNTHETIC_NEVER_ECHO", result.stdout)
            rejected = subprocess.run(
                [sys.executable, str(SCRIPT), "--config", str(path),
                 "--repo", "pl0n3r/Factory", "--gravedad", "critical",
                 "--instante", "2026-10-30T12:00:00Z"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(2, rejected.returncode)
            self.assertIn("unrecognized arguments", rejected.stderr)
            self.assertEqual("", rejected.stdout)
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("import requests", source)
        self.assertNotIn("socket", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("smtp", source.lower())

    def test_esquema_y_documentacion_coinciden(self) -> None:
        """JSON/YAML 1.2 schema constrains all fields and is no-send by design."""
        schema = json.loads((ROOT / "alertas" / "receptores.schema.json").read_text())
        self.assertEqual(set(schema["required"]), MODULE.TOP)
        self.assertFalse(schema["additionalProperties"])
        item = schema["properties"]["receptores"]["items"]
        self.assertEqual(set(item["required"]), MODULE.FIELDS)
        self.assertEqual(set(item["properties"]), MODULE.FIELDS)
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(set(item["properties"]["canal"]["enum"]), MODULE.CANALES)
        self.assertEqual(set(item["properties"]["gravedades"]["items"]["enum"]), MODULE.GRAVEDADES)
        self.assertIn("no envía", (ROOT / "docs" / "alertas-receptores.md").read_text())


if __name__ == "__main__":
    unittest.main()
