"""Factory README Contract v2 adoption and backwards-compatible validation."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from readme.validate_readme import validate_readme

ROOT = Path(__file__).resolve().parents[1]


class ReadmeV2FactoryTests(unittest.TestCase):
    def test_readme_is_contract_v2_without_unknown_blocks(self):
        """AC-01: live links, canonical sections, no v1 placeholders or fake health."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contract = json.loads((ROOT / "readme/contract.json").read_text(encoding="utf-8"))
        metadata = json.loads((ROOT / "readme/projects/factory.json").read_text(encoding="utf-8"))

        self.assertEqual(contract["version"], 2)
        self.assertEqual(readme.count("## Operational Cockpit"), 1)
        headings = re.findall(r"(?m)^## (.+)$", readme)
        self.assertEqual(
            headings,
            [section["title"] for section in contract["sections"][1:]],
        )
        self.assertNotIn("UNKNOWN", readme)
        self.assertNotIn("Progress + Readiness", readme)
        self.assertNotIn("<!-- factory:status", readme)
        self.assertNotIn("<!-- factory:progress-readiness", readme)
        self.assertIn("https://github.com/pl0n3r/Factory/actions/workflows/ci.yml", readme)
        self.assertIn("badge.svg?branch=main", readme)
        self.assertIn("https://github.com/pl0n3r/Factory/releases", readme)
        self.assertIn("https://control.condorapp.com.co/", readme)
        self.assertNotIn("https://www.grindflow.com.co/health", readme)
        self.assertNotIn("TANDA 2 en curso", readme)
        for link in ("PLAN-AGENTES.md", "AGENTES.md", "decisiones.yml"):
            self.assertIn(link, readme)

        validate_readme(readme, contract, metadata, {})

    def test_readme_live_sources_fail_closed_on_legacy_or_untrusted_links(self):
        """Prevent reintroducing v1 tables and untrusted cockpit destinations."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contract = json.loads((ROOT / "readme/contract.json").read_text(encoding="utf-8"))
        metadata = json.loads((ROOT / "readme/projects/factory.json").read_text(encoding="utf-8"))
        for corrupt in (
            readme.replace("## Work Queue", "| main SHA | UNKNOWN |\n\n## Work Queue", 1),
            readme.replace(
                "## Operational Cockpit\n\n",
                "## Operational Cockpit\n\n[fake](https://example.invalid/health)\n\n",
                1,
            ),
        ):
            with self.subTest(corrupt=corrupt[:35]):
                with self.assertRaises(ValueError):
                    validate_readme(corrupt, contract, metadata, {})


if __name__ == "__main__":
    unittest.main()
