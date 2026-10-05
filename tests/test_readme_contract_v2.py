from __future__ import annotations

import copy
import json
import pathlib
import re
import unittest

from readme.generate_readme import generate_readme
from readme.validate_readme import validate_readme


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "readme" / "contract.json"
TEMPLATE_PATH = ROOT / "readme" / "template.md"
BOOTSTRAP_TEMPLATE_PATH = ROOT / "template" / "README.md"
DOC_PATH = ROOT / "docs" / "readme-contract.md"


class ReadmeContractV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.template = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.bootstrap_template = BOOTSTRAP_TEMPLATE_PATH.read_text(encoding="utf-8")
        self.docs = DOC_PATH.read_text(encoding="utf-8")
        self.metadata = {
            "name": "Factory",
            "tagline": "Kit",
            "role": "governance",
            "phase": "construction",
            "roadmap": "https://github.com/pl0n3r/Factory/issues",
            "stack": "Python",
        }
        self.v2_readme = """# Demo

## Operational Cockpit

[CI](https://github.com/pl0n3r/Factory/actions)
[Release](https://github.com/pl0n3r/Factory/releases/latest)
[Orquestador](https://control.condorapp.com.co/)
"""

    def test_v2_status_block_has_no_unknown_placeholder_tables(self) -> None:
        self.assertEqual(self.contract["version"], 2)
        live = self.contract["live_status"]
        self.assertEqual(live["ownership"], "platform")
        self.assertEqual(live["refresh_mode"], "request_time")
        self.assertFalse(live["commits_for_refresh"])
        self.assertFalse(live["unknown_placeholder_tables"])
        self.assertFalse(live["renders_progress_readiness"])
        self.assertEqual(live["missing_optional_source"], "omit")

        for text in (self.template, self.bootstrap_template):
            with self.subTest(template=text[:40]):
                self.assertNotIn("<!-- factory:status:start -->", text)
                self.assertNotIn("<!-- factory:progress-readiness:start -->", text)
                self.assertNotIn("### Progress + Readiness", text)
                self.assertNotIn("| main SHA | UNKNOWN |", text)
                self.assertNotIn("| Progress | UNKNOWN |", text)
                self.assertNotIn("| Readiness | UNKNOWN |", text)
                self.assertIsNone(re.search(r"\b\d{1,3}%\b", text))

        blocks = self.contract["derived_blocks"]
        self.assertEqual(blocks["status"]["lifecycle"], "legacy_v1_only")
        self.assertEqual(
            blocks["progress_readiness"]["lifecycle"], "legacy_v1_only"
        )

    def test_validator_accepts_v1_and_v2_during_migration(self) -> None:
        validate_readme(self.v2_readme, self.contract, self.metadata, {}, None)

        legacy_contract = copy.deepcopy(self.contract)
        legacy_contract["version"] = 1
        legacy_seed = """# Legacy
<!-- factory:status:start -->
legacy
<!-- factory:status:end -->
<!-- factory:progress-readiness:start -->
legacy
<!-- factory:progress-readiness:end -->
"""
        legacy_readme = generate_readme(
            legacy_seed,
            legacy_contract,
            self.metadata,
            {},
            None,
        )

        validate_readme(
            legacy_readme,
            legacy_contract,
            self.metadata,
            {},
            None,
        )
        validate_readme(
            legacy_readme,
            self.contract,
            self.metadata,
            {},
            None,
        )

    def test_live_badges_use_only_platform_sources_and_no_generated_commits(self) -> None:
        live = self.contract["live_status"]
        self.assertEqual(
            live["required_sources"], ["github_actions", "github_releases"]
        )
        self.assertIn("public_health", live["optional_sources"])
        self.assertIn("controlbot_orchestrator", live["optional_sources"])
        self.assertFalse(live["commits_for_refresh"])

        self.assertIn("img.shields.io/github/actions/workflow/status", self.template)
        self.assertIn("img.shields.io/github/v/release", self.template)
        self.assertIn("/actions", self.template)
        self.assertIn("/releases/latest", self.template)
        self.assertIn("control.condorapp.com.co", self.template)
        self.assertIn("/health", self.template)

    def test_v2_validator_rejects_legacy_rendering_and_progress_snapshot(self) -> None:
        with self.assertRaises(ValueError):
            validate_readme(
                self.v2_readme + "\n### Progress + Readiness\n",
                self.contract,
                self.metadata,
                {},
                None,
            )
        with self.assertRaises(ValueError):
            validate_readme(
                self.v2_readme,
                self.contract,
                self.metadata,
                {},
                {"progress": 50},
            )

    def test_docs_keep_readme_out_of_readiness_authority_and_define_rollback(self) -> None:
        for token in (
            "GitHub Actions",
            "GitHub Releases",
            "/health",
            "ControlBot",
            "progress_readiness.py",
            "v1 → v2",
            "revert",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.docs)
        self.assertRegex(self.docs.lower(), r"no (?:es|tiene) autoridad")
        self.assertIn("commits", self.docs.lower())


if __name__ == "__main__":
    unittest.main()
