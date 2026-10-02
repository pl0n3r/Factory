#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/etiquetas.yml").read_text(encoding="utf-8")


def labels_job_permissions():
    match = re.search(
        r"(?ms)^  etiquetas:\n.*?^    permissions:\n"
        r"(?P<permissions>(?:^      [^\n]+\n)+)^    steps:\n",
        WF,
    )
    if match is None:
        raise AssertionError("No se encontró el bloque permissions del job Labels")
    return match.group("permissions")


class EtiquetasWorkflowContractTests(unittest.TestCase):
    def test_modes_and_language_are_closed(self):
        self.assertIn('case "$MODE" in sync|validate|sweep)', WF)
        self.assertIn('case "$LANGUAGE" in es|en)', WF)
        self.assertIn("issues: write", WF)

    def test_uses_published_factory_catalog_by_language_not_path(self):
        self.assertIn("repository: pl0n3r/factory", WF)
        self.assertIn("labels_kit.py", WF)
        self.assertIn("ref: v1", WF)
        self.assertIn("--language", WF)
        self.assertNotIn("--catalog", WF)
        self.assertNotIn("inputs.kit_ref", WF)

    def test_pr_validation_uses_metadata_only_permissions(self):
        self.assertEqual(
            labels_job_permissions(),
            "      contents: read\n"
            "      issues: write\n"
            "      pull-requests: read\n",
        )

    def test_pr_validation_grants_write_for_safe_label_inheritance(self):
        permissions = labels_job_permissions()
        self.assertIn("issues: write", permissions)
        self.assertIn("pull-requests: read", permissions)
        self.assertNotIn("pull-requests: write", permissions)
        self.assertIn('gh api --method POST "repos/$REPOSITORIO/issues/$ISSUE_NUMBER/labels"', WF)
        self.assertIn("linked_issue:$linked[0]", WF)

    def test_metadata_permissions_remain_least_privilege(self):
        permissions = labels_job_permissions()
        self.assertEqual(
            set(line.strip() for line in permissions.splitlines()),
            {"contents: read", "issues: write", "pull-requests: read"},
        )
        self.assertIn("permissions:\n  contents: read", WF)
        self.assertNotIn("contents: write", WF)
        self.assertNotIn("actions: write", WF)
        self.assertNotIn("checks: read", permissions)
        self.assertNotIn("checks: write", WF)
        self.assertNotIn("pull-requests: write", WF)
        self.assertNotIn("id-token: write", WF)
        self.assertNotIn("secrets: inherit", WF)

    def test_validate_and_sweep_lifecycle_remains_metadata_only(self):
        self.assertIn("name: Labels", WF)
        self.assertIn("plan-validation", WF)
        self.assertIn("sweep-plan", WF)
        self.assertIn("<!-- factory-label-validation -->", WF)
        self.assertIn("<!-- factory-auto-unlabeled -->", WF)
        self.assertIn("linked_issue:$linked[0]", WF)
        self.assertIn("group: labels-${{ github.repository }}-${{ inputs.mode }}-${{ inputs.issue_number }}", WF)
        self.assertNotIn("github.run_id", WF)
        self.assertIn("select(.number != $auto)", WF)
        self.assertIn("auto-create.json", WF)
        self.assertIn("auto-update.json", WF)
        self.assertIn("auto-close.json", WF)
        self.assertNotIn('-f state=open --input', WF)
        self.assertIn("repository: pl0n3r/factory", WF)
        self.assertIn("pr_label_governance.py alert-plan", WF)
        self.assertIn("commits/$head_sha/check-runs?per_page=100", WF)
        self.assertIn("curl --fail --silent --show-error", WF)
        self.assertIn("^[0-9a-f]{40}$", WF)
        self.assertNotIn('gh api "repos/$REPOSITORIO/commits/$head_sha/check-runs', WF)
        self.assertIn(".[:25]", WF)

    def test_external_actions_are_sha_pinned(self):
        actions = re.findall(r"^\s*uses:\s*([^\s]+)", WF, flags=re.MULTILINE)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
