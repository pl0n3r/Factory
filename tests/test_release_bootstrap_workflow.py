#!/usr/bin/env python3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / ".github/workflows/release-bootstrap.yml").read_text(encoding="utf-8")
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
GUIDE = (ROOT / "docs/release-bootstrap.md").read_text(encoding="utf-8")


class ReleaseBootstrapWorkflowTests(unittest.TestCase):
    def test_candidate_template_runs_before_preflight_read_only(self):
        self.assertIn("uses: ./.github/workflows/ci.yml", BOOTSTRAP)
        self.assertIn("kit_ref: ${{ github.sha }}", BOOTSTRAP)
        self.assertLess(BOOTSTRAP.index("candidate-template:"), BOOTSTRAP.index("preflight:"))
        candidate = BOOTSTRAP.split("candidate-template:", 1)[1].split("preflight:", 1)[0]
        self.assertIn("contents: read", candidate)
        self.assertNotIn("contents: write", candidate)

    def test_reusable_release_dispatch_is_factory_owner_only(self):
        for value in (
            "factory_bootstrap:", "expected_sha:", "workflow_dispatch)",
            '[[ "$REPOSITORY" == "pl0n3r/factory" ]]',
            '[[ "$ACTOR" == "$OWNER" ]]', '[[ "$BOOTSTRAP" == "true" ]]',
            '[[ "$EXPECTED_SHA" == "$GITHUB_SHA" ]]',
        ):
            self.assertIn(value, RELEASE)

    def test_published_v1_is_used_for_release_and_post_selftest(self):
        self.assertIn("uses: pl0n3r/factory/.github/workflows/release.yml@v1", BOOTSTRAP)
        self.assertIn("uses: pl0n3r/factory/.github/workflows/ci.yml@v1", BOOTSTRAP)
        release = BOOTSTRAP.split("\n  release:", 1)[1].split("\n  selftest-published:", 1)[0]
        self.assertNotIn("kit_ref:", release)
        self.assertIn("factory_bootstrap: true", release)

    def test_bootstrap_guide_matches_executable_path(self):
        for value in (
            "Bootstrap release Factory v1.0.0", "factory-release-approval",
            "expected_sha", "gate_issue", "#83", "self-test", "@v1",
            "no crea ningún tag automáticamente",
        ):
            self.assertIn(value, GUIDE)


if __name__ == "__main__":
    unittest.main()
