import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class KitSecurityBoundaryTests(unittest.TestCase):
    def test_root_decisions_are_canonical_and_active(self):
        root = json.loads((ROOT / "decisiones.yml").read_text(encoding="utf-8"))
        template = json.loads((ROOT / "template/decisiones.yml").read_text(encoding="utf-8"))
        self.assertEqual(root["version"], 1)
        self.assertEqual(root["review_round_limit"], 3)
        self.assertGreaterEqual(len(root["decisions"]), 5)
        self.assertTrue(all(item["status"] == "active" for item in root["decisions"]))
        self.assertEqual(
            {item["id"] for item in root["decisions"]},
            {item["id"] for item in template["decisions"]},
        )

    def test_agent_core_requires_decisions_and_memory(self):
        text = (ROOT / "agentes/NUCLEO.md").read_text(encoding="utf-8")
        self.assertIn("decisiones.yml", text)
        self.assertIn("lecciones/", text)
        self.assertIn("no se revierte", text)

    def test_factory_ci_runs_optional_component_suites(self):
        text = (ROOT / ".github/workflows/factory-ci.yml").read_text(encoding="utf-8")
        for directory in ("metricas", "seguridad", "lecciones", "producto"):
            self.assertIn(f"-d {directory}", text)
        self.assertIn("python3 scripts/politica_kit.py </dev/null", text)
        self.assertNotIn("--file decisiones.yml", text)

    def test_template_health_never_fakes_release_evidence(self):
        text = (ROOT / "template/public/health.php").read_text(encoding="utf-8")
        self.assertNotIn("str_repeat('0', 40)", text)
        self.assertIn("construction-stub", text)
        self.assertIn("'release_sha' => $releaseSha !== '' ? $releaseSha : null", text)

    def test_write_capable_workflows_execute_published_kit(self):
        for name in ("coordinacion.yml", "etiquetas.yml", "release.yml", "deploy.yml", "observar.yml"):
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertNotIn("inputs.kit_ref", text, name)
            self.assertIn("ref: v1", text, name)

    def test_policy_cannot_choose_alternate_decisions_file(self):
        text = (ROOT / ".github/workflows/politica.yml").read_text(encoding="utf-8")
        self.assertNotIn("decisions_path:", text)
        self.assertNotIn("inputs.kit_ref", text)
        self.assertNotIn("--file", text)
        self.assertIn("ref: v1", text)

    def test_version_source_is_closed_in_reusable_ci(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("config/version.php|config/version.json", text)
        self.assertIn("version_source no permitido", text)

    def test_factory_ci_forces_https_on_actionlint_redirects(self):
        text = (ROOT / ".github/workflows/factory-ci.yml").read_text(encoding="utf-8")
        self.assertIn("--proto '=https'", text)
        self.assertIn("--proto-redir '=https'", text)

    def test_template_composer_lock_matches_manifest(self):
        composer = json.loads((ROOT / "template/composer.json").read_text(encoding="utf-8"))
        lock = json.loads((ROOT / "template/composer.lock").read_text(encoding="utf-8"))
        relevant = {
            key: composer[key]
            for key in (
                "name", "version", "require", "require-dev", "conflict",
                "replace", "provide", "minimum-stability", "prefer-stable",
                "repositories", "extra",
            )
            if key in composer
        }
        encoded = json.dumps(
            dict(sorted(relevant.items())),
            separators=(",", ":"),
            ensure_ascii=False,
        ).replace("/", "\\/")
        expected = hashlib.md5(encoded.encode("utf-8")).hexdigest()
        self.assertEqual(lock["content-hash"], expected)
        self.assertEqual(lock["packages"], [])
        self.assertEqual(lock["packages-dev"], [])
        self.assertEqual(lock["platform"]["php"], composer["require"]["php"])

