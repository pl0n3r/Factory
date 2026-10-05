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

    def test_v2_validator_fails_closed_on_unsafe_contract_shapes(self) -> None:
        cases = []

        unsupported = copy.deepcopy(self.contract)
        unsupported["version"] = 3
        cases.append(("unsupported_version", unsupported))

        missing_live = copy.deepcopy(self.contract)
        missing_live["live_status"] = None
        cases.append(("missing_live_status", missing_live))

        missing_compatibility = copy.deepcopy(self.contract)
        missing_compatibility["compatibility"] = None
        cases.append(("missing_compatibility", missing_compatibility))

        refresh_commits = copy.deepcopy(self.contract)
        refresh_commits["live_status"]["commits_for_refresh"] = True
        cases.append(("refresh_commits", refresh_commits))

        unknown_tables = copy.deepcopy(self.contract)
        unknown_tables["live_status"]["unknown_placeholder_tables"] = True
        cases.append(("unknown_tables", unknown_tables))

        progress_rendering = copy.deepcopy(self.contract)
        progress_rendering["live_status"]["renders_progress_readiness"] = True
        cases.append(("progress_rendering", progress_rendering))

        incompatible_transition = copy.deepcopy(self.contract)
        incompatible_transition["compatibility"]["accepted_versions_during_migration"] = [2]
        cases.append(("incompatible_transition", incompatible_transition))

        generated_status = copy.deepcopy(self.contract)
        generated_status["content_policy"]["v2_has_generated_status_blocks"] = True
        cases.append(("generated_status", generated_status))

        no_legacy_blocks = copy.deepcopy(self.contract)
        no_legacy_blocks["derived_blocks"] = None
        validate_readme(self.v2_readme, no_legacy_blocks, self.metadata, {}, None)

        for name, contract in cases:
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_readme(self.v2_readme, contract, self.metadata, {}, None)

    def test_v2_validator_requires_nonempty_readme_and_live_destinations(self) -> None:
        with self.assertRaises(ValueError):
            validate_readme("   ", self.contract, self.metadata, {}, None)

        missing_actions = self.v2_readme.replace(
            "https://github.com/pl0n3r/Factory/actions",
            "https://example.test/ci",
        )
        with self.assertRaises(ValueError):
            validate_readme(missing_actions, self.contract, self.metadata, {}, None)

        missing_releases = self.v2_readme.replace(
            "https://github.com/pl0n3r/Factory/releases/latest",
            "https://github.com/pl0n3r/Factory/tags",
        )
        with self.assertRaises(ValueError):
            validate_readme(missing_releases, self.contract, self.metadata, {}, None)

        missing_orchestrator = self.v2_readme.replace(
            "https://control.condorapp.com.co/",
            "https://github.com/pl0n3r/Factory/issues",
        )
        with self.assertRaises(ValueError):
            validate_readme(
                missing_orchestrator,
                self.contract,
                self.metadata,
                {},
                None,
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
