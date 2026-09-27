import json
import unittest
from pathlib import Path

from intelligence.derived_views import DerivedViewDriftError, DerivedViewError
from readme.generate_readme import ReadmeEngineError, generate_readme
from readme.validate_readme import validate_readme


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "readme" / "contract.json"
TEMPLATE = ROOT / "readme" / "template.md"
DOCS = ROOT / "docs" / "readme-contract.md"


class ReadmeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Carga una sola vez los artefactos del contrato para la suite."""
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")
        cls.metadata = {
            "name": "Factory",
            "tagline": "Gobernanza reproducible",
            "role": "governance/kit",
            "phase": "construction",
            "roadmap": "GitHub Issues",
            "stack": "Python + GitHub Actions",
        }

    def test_contract_v1_requires_common_sections(self):
        """Exige la anatomía común declarada por README Contract v1."""
        self.assertEqual(self.contract["version"], 1)
        self.assertEqual(self.contract["contract_id"], "factory.readme")
        expected = [
            "hero",
            "operational_cockpit",
            "work_queue",
            "product",
            "architecture",
            "stack",
            "delivery",
            "quality_security",
            "sources_of_truth",
            "local_development",
            "factory_map",
        ]
        self.assertEqual(
            [section["id"] for section in self.contract["sections"]],
            expected,
        )
        for heading in (
            "## Operational Cockpit",
            "## Work Queue",
            "## Qué hace el producto",
            "## Arquitectura en 60 segundos",
            "## Stack e infraestructura",
            "## Ciclo de entrega",
            "## Calidad y seguridad",
            "## Roadmap y fuentes de verdad",
            "## Desarrollo local",
            "## Mapa de la fábrica",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.template)

    def test_contract_v1_separates_human_and_generated_blocks(self):
        """Verifica la frontera entre narrativa humana y bloques derivados."""
        status = self.contract["derived_blocks"]["status"]
        policy = self.contract["content_policy"]
        sections = {row["id"]: row for row in self.contract["sections"]}

        self.assertEqual(sections["operational_cockpit"]["ownership"], "derived")
        self.assertEqual(sections["product"]["ownership"], "human")
        self.assertTrue(policy["generated_only_within_declared_markers"])
        self.assertTrue(policy["preserve_human_content_byte_for_byte"])
        self.assertEqual(self.template.count(status["start_marker"]), 1)
        self.assertEqual(self.template.count(status["end_marker"]), 1)
        self.assertIn("frontera de escritura", self.docs)

    def test_contract_v1_requires_minimal_project_metadata(self):
        """Mantiene mínima y estable la metadata de proyecto requerida."""
        metadata = self.contract["project_metadata"]
        self.assertEqual(
            metadata["required"],
            ["name", "tagline", "role", "phase", "roadmap", "stack"],
        )
        self.assertEqual(metadata["phase_values"], ["construction", "live"])
        forbidden = set(metadata["forbidden_operational_fields"])
        self.assertTrue(
            {"main_sha", "version", "ci", "release", "health", "active_pr"}
            <= forbidden
        )
        self.assertTrue(set(metadata["required"]).isdisjoint(forbidden))
        self.assertIn("`tagline`: propósito breve visible", self.docs)
        self.assertIn("No se versionan manualmente como metadata", self.docs)
        self.assertIn("{{project.stack}}", self.template)
        self.assertIn("| CI | UNKNOWN |", self.template)
        self.assertNotIn("| CI | PENDING |", self.template)

    def test_readme_does_not_duplicate_roadmap_or_changelog(self):
        """Impide que el README replique roadmap o historial de releases."""
        policy = self.contract["content_policy"]
        self.assertEqual(policy["readme_is_not"], ["roadmap", "changelog"])
        self.assertTrue(policy["canonical_sources_are_links_not_copies"])
        self.assertEqual(
            policy["work_queue_labels"],
            ["NOW", "NEXT", "LATER", "BLOCKED"],
        )
        self.assertIn("Esta vista resume; no duplica el Roadmap", self.template)
        self.assertIn("No conserva una copia completa del Roadmap", self.docs)
        self.assertIn("GitHub Releases para entregas", self.docs)


    def test_generation_is_deterministic(self):
        """Mismos inputs generan exactamente el mismo cockpit."""
        sources = {
            "main_sha": {"value": "abc123", "evidence": "git:main"},
            "version": {"value": "1.2.3", "evidence": "config/version"},
            "ci": {"state": "GREEN", "evidence": "check:42"},
            "release": {"value": "v1.2.3", "evidence": "release:1.2.3"},
            "health": {"state": "GREEN", "evidence": "health:sha=abc123"},
        }
        first = generate_readme(self.template, self.contract, self.metadata, sources)
        second = generate_readme(self.template, self.contract, self.metadata, sources)
        self.assertEqual(first, second)

    def test_validator_detects_canonical_status_drift(self):
        """Cambios de SHA, versión, release o estado producen drift."""
        sources = {
            "main_sha": {"value": "abc123", "evidence": "git:main"},
            "version": {"value": "1.2.3", "evidence": "version:file"},
            "ci": {"state": "GREEN", "evidence": "check:42"},
            "release": {"value": "v1.2.3", "evidence": "release:1.2.3"},
        }
        committed = generate_readme(self.template, self.contract, self.metadata, sources)
        validate_readme(committed, self.contract, self.metadata, sources)
        for field, changed in (
            ("main_sha", {"value": "def456", "evidence": "git:main"}),
            ("version", {"value": "1.2.4", "evidence": "version:file"}),
            ("release", {"value": "v1.2.4", "evidence": "release:1.2.4"}),
            ("ci", {"state": "DEGRADED", "evidence": "check:43"}),
        ):
            candidate = dict(sources)
            candidate[field] = changed
            with self.subTest(field=field), self.assertRaises(DerivedViewDriftError):
                validate_readme(committed, self.contract, self.metadata, candidate)

    def test_unknown_health_never_becomes_green(self):
        """Ausencia de evidencia queda UNKNOWN y GREEN sin evidencia falla."""
        generated = generate_readme(
            self.template,
            self.contract,
            self.metadata,
            {"main_sha": "abc123"},
        )
        self.assertIn("| CI | UNKNOWN |", generated)
        self.assertIn("| health | UNKNOWN |", generated)
        self.assertIn("| release | UNKNOWN |", generated)
        with self.assertRaises(ReadmeEngineError):
            generate_readme(
                self.template,
                self.contract,
                self.metadata,
                {"health": {"state": "GREEN"}},
            )

    def test_generated_blocks_preserve_human_content(self):
        """Solo el interior de los markers declarados puede cambiar."""
        marker_start = "<!-- factory:status:start -->"
        marker_end = "<!-- factory:status:end -->"
        prefix, rest = self.template.split(marker_start, 1)
        _, suffix = rest.split(marker_end, 1)
        generated = generate_readme(
            self.template,
            self.contract,
            self.metadata,
            {"version": "1.2.3"},
        )
        generated_prefix, generated_rest = generated.split(marker_start, 1)
        _, generated_suffix = generated_rest.split(marker_end, 1)
        self.assertEqual(prefix, generated_prefix)
        self.assertEqual(suffix, generated_suffix)

    def test_generated_content_rejects_contract_markers(self):
        """Valores operativos no pueden inyectar markers del bloque derivado."""
        end_marker = self.contract["derived_blocks"]["status"]["end_marker"]
        with self.assertRaises(DerivedViewError):
            generate_readme(
                self.template,
                self.contract,
                self.metadata,
                {"active_issue": f"#262 {end_marker}"},
            )

    def test_operational_metadata_rejects_sensitive_fields(self):
        """Campos sensibles o no declarados fallan antes de renderizar."""
        with self.assertRaises(ReadmeEngineError):
            generate_readme(
                self.template,
                self.contract,
                self.metadata,
                {"token": "secret"},
            )
        with self.assertRaises(ReadmeEngineError):
            generate_readme(
                self.template,
                self.contract,
                self.metadata,
                {"deployment_url": "https://example.test"},
            )


if __name__ == "__main__":
    unittest.main()
