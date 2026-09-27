import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "readme" / "contract.json"
TEMPLATE = ROOT / "readme" / "template.md"
DOCS = ROOT / "docs" / "readme-contract.md"


class ReadmeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")

    def test_contract_v1_requires_common_sections(self):
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

    def test_readme_does_not_duplicate_roadmap_or_changelog(self):
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


if __name__ == "__main__":
    unittest.main()
