import json
import unittest
from pathlib import Path

from intelligence.derived_views import DerivedViewDriftError, DerivedViewError
from readme.generate_readme import (
    ReadmeEngineError,
    generate_readme,
    validate_project_metadata,
)
from readme.validate_readme import validate_readme


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "readme" / "contract.json"
TEMPLATE = ROOT / "readme" / "template.md"
DOCS = ROOT / "docs" / "readme-contract.md"
REUSABLE_WORKFLOW = ROOT / ".github" / "workflows" / "readme.yml"
TEMPLATE_CALLER = ROOT / "template" / ".github" / "workflows" / "readme-contract.yml"
TEMPLATE_PROJECT = ROOT / "template" / "readme" / "project.json"
TEMPLATE_BOOTSTRAP_README = ROOT / "template" / "README.md"


class ReadmeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Carga una sola vez los artefactos del contrato para la suite."""
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")
        cls.reusable_workflow = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
        cls.template_caller = TEMPLATE_CALLER.read_text(encoding="utf-8")
        cls.template_project = json.loads(TEMPLATE_PROJECT.read_text(encoding="utf-8"))
        cls.template_bootstrap_readme = TEMPLATE_BOOTSTRAP_README.read_text(encoding="utf-8")
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


    def test_reusable_readme_workflow_is_read_only_and_calls_validator(self):
        """El reusable valida con permisos mínimos y sin mutar el caller."""
        workflow = self.reusable_workflow
        self.assertIn("workflow_call:", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("secrets: inherit", workflow)
        self.assertGreaterEqual(
            workflow.count(
                "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
            ),
            2,
        )
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("from readme.validate_readme import validate_readme", workflow)
        self.assertIn("validate_readme(readme_text, contract, metadata, sources)", workflow)

    def test_template_calls_readme_contract_v1(self):
        """El proyecto nuevo consume el reusable únicamente por el canal v1."""
        caller = self.template_caller
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/readme.yml@v1",
            caller,
        )
        self.assertIn("permissions:\n  contents: read", caller)
        self.assertNotIn("secrets:", caller)
        self.assertIn("metadata_path: readme/project.json", caller)

    def test_template_bootstraps_readme_project_metadata(self):
        """La metadata del template coincide exactamente con Contract v1."""
        required = set(self.contract["project_metadata"]["required"])
        forbidden = set(
            self.contract["project_metadata"]["forbidden_operational_fields"]
        )
        self.assertEqual(set(self.template_project), required)
        self.assertTrue(set(self.template_project).isdisjoint(forbidden))
        validate_project_metadata(self.contract, self.template_project)

    def test_template_readme_bootstraps_contract_v1(self):
        """El README del template nace válido y con cockpit UNKNOWN."""
        for section in self.contract["sections"][1:]:
            self.assertIn(f"## {section['title']}", self.template_bootstrap_readme)
        status = self.contract["derived_blocks"]["status"]
        self.assertEqual(
            self.template_bootstrap_readme.count(status["start_marker"]),
            1,
        )
        self.assertEqual(
            self.template_bootstrap_readme.count(status["end_marker"]),
            1,
        )
        self.assertIn("| CI | UNKNOWN |", self.template_bootstrap_readme)
        self.assertNotIn("| CI | GREEN |", self.template_bootstrap_readme)
        validate_readme(
            self.template_bootstrap_readme,
            self.contract,
            self.template_project,
            {},
        )

    def test_reusable_readme_workflow_rejects_missing_required_sections(self):
        """La anatomía Contract v1 también se valida fail-closed."""
        workflow = self.reusable_workflow
        self.assertIn('for section in contract["sections"][1:]:', workflow)
        self.assertIn("readme_text.count(heading) != 1", workflow)
        self.assertIn("sección requerida ausente/duplicada", workflow)
        missing_architecture = self.template_bootstrap_readme.replace(
            "## Arquitectura en 60 segundos",
            "## Arquitectura eliminada",
            1,
        )
        self.assertNotIn("## Arquitectura en 60 segundos", missing_architecture)
        self.assertTrue(
            any(
                f"## {section['title']}" not in missing_architecture
                for section in self.contract["sections"][1:]
            )
        )

    def test_reusable_readme_workflow_fails_closed(self):
        """Paths o evidencia fuera del contrato hacen fallar el reusable."""
        workflow = self.reusable_workflow
        self.assertIn('[[ "$README_PATH" == "README.md" ]]', workflow)
        self.assertIn(
            '[[ "$METADATA_PATH" == "readme/project.json" ]]',
            workflow,
        )
        self.assertIn("''|readme/evidence.json)", workflow)
        self.assertIn("evidence_path no permitido", workflow)
        self.assertIn("set -euo pipefail", workflow)
        self.assertNotIn("continue-on-error: true", workflow)
        self.assertNotIn("gh api", workflow)
        self.assertNotIn("curl ", workflow)


if __name__ == "__main__":
    unittest.main()
