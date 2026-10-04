#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERAL = (ROOT / ".github/workflows/etiquetas.yml").read_text(encoding="utf-8")
PR = (ROOT / ".github/workflows/etiquetas-pr.yml").read_text(encoding="utf-8")

EXPECTED_GENERAL = {"contents: read", "issues: write", "pull-requests: read"}
EXPECTED_PR = {"contents: read", "issues: write", "pull-requests: write"}


def job_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
    )
    if match is None:
        raise AssertionError(f"No se encontró el job {name}")
    return match.group("body")


def job_permissions(text: str, name: str) -> set[str]:
    block = job_block(text, name)
    match = re.search(
        r"(?ms)^    permissions:\n(?P<permissions>(?:^      [^\n]+\n)+)",
        block,
    )
    if match is None:
        raise AssertionError(f"No se encontró permissions de {name}")
    return {line.strip() for line in match.group("permissions").splitlines()}


class EtiquetasWorkflowContractTests(unittest.TestCase):
    def test_modes_and_language_are_closed(self):
        self.assertIn('case "$MODE" in sync|validate|sweep)', GENERAL)
        self.assertIn('case "$MODE" in validate)', PR)
        for workflow in (GENERAL, PR):
            self.assertIn('case "$LANGUAGE" in es|en)', workflow)

    def test_uses_published_factory_catalog_by_language_not_path(self):
        for workflow, name in ((GENERAL, "etiquetas"), (PR, "etiquetas-pr")):
            block = job_block(workflow, name)
            self.assertIn("repository: pl0n3r/factory", block)
            self.assertIn("labels_kit.py", block)
            self.assertIn("ref: v1", block)
            self.assertIn("--language", block)
            self.assertNotIn("--catalog", block)
        self.assertNotIn("inputs.kit_ref", GENERAL)
        self.assertNotIn("inputs.kit_ref", PR)

    def test_reusable_envelope_is_compatible_with_read_only_issue_sweep_and_sync_callers(self):
        self.assertEqual(job_permissions(GENERAL, "etiquetas"), EXPECTED_GENERAL)
        self.assertNotIn("pull-requests: write", GENERAL)
        self.assertNotIn("  etiquetas-pr:\n", GENERAL)
        self.assertIn("Sincronizar catálogo", GENERAL)
        self.assertIn("Barrer trabajo abierto", GENERAL)
        self.assertIn("Validar Issue o PR", GENERAL)

    def test_pr_write_authority_is_isolated_to_pr_callers_only(self):
        self.assertEqual(job_permissions(PR, "etiquetas-pr"), EXPECTED_PR)
        self.assertEqual(PR.count("pull-requests: write"), 1)
        self.assertNotIn("pull-requests: write", GENERAL)
        block = job_block(PR, "etiquetas-pr")
        self.assertIn(
            "if: inputs.mode == 'validate' && github.event_name == 'pull_request'",
            block,
        )
        for forbidden in (
            "checks: write",
            "actions: write",
            "id-token: write",
            "contents: write",
        ):
            self.assertNotIn(forbidden, block)

    def test_non_pr_job_remains_read_only(self):
        block = job_block(GENERAL, "etiquetas")
        self.assertEqual(job_permissions(GENERAL, "etiquetas"), EXPECTED_GENERAL)
        self.assertIn(
            "if: inputs.mode != 'validate' || github.event_name != 'pull_request'",
            block,
        )
        self.assertNotIn("pull-requests: write", block)
        self.assertIn("Detectar merges con Etiquetas no verde", block)

    def test_pr_and_non_pr_jobs_keep_labels_check_name(self):
        general = job_block(GENERAL, "etiquetas")
        pr = job_block(PR, "etiquetas-pr")
        self.assertIn("name: Labels", general)
        self.assertIn("name: Labels", pr)
        self.assertEqual(GENERAL.count("    name: Labels\n"), 1)
        self.assertEqual(PR.count("    name: Labels\n"), 1)

    def test_pr_validate_keeps_safe_label_inheritance_without_changing_sweep(self):
        pr = job_block(PR, "etiquetas-pr")
        general = job_block(GENERAL, "etiquetas")

        self.assertIn("plan-validation", pr)
        self.assertIn("linked_issue:$linked[0]", pr)
        self.assertIn(
            'gh api --method POST "repos/$REPOSITORIO/issues/$ISSUE_NUMBER/labels"',
            pr,
        )
        self.assertIn("<!-- factory-label-validation -->", pr)
        self.assertNotIn("sweep-plan", pr)
        self.assertNotIn("factory-auto-unlabeled", pr)
        self.assertNotIn("Detectar merges con Etiquetas no verde", pr)

        self.assertIn("sweep-plan", general)
        self.assertIn("<!-- factory-auto-unlabeled -->", general)
        self.assertIn("pr_label_governance.py alert-plan", general)
        self.assertIn("commits/$head_sha/check-runs?per_page=100", general)
        self.assertIn("curl --fail --silent --show-error", general)
        self.assertIn("^[0-9a-f]{40}$", general)
        self.assertIn(".[:25]", general)

    def test_validate_issue_path_stays_on_general_job(self):
        general = job_block(GENERAL, "etiquetas")
        self.assertIn("name: Validar Issue o PR", general)
        self.assertIn("if: inputs.mode == 'validate'", general)
        self.assertIn("plan-validation", general)
        self.assertIn("pull-requests: read", general)
        self.assertNotIn("pull-requests: write", general)

    def test_sweep_routes_merge_alerts_to_linked_issue_without_pr_write(self):
        block = job_block(GENERAL, "etiquetas")
        self.assertIn('closing-reference --language "$LANGUAGE"', block)
        self.assertIn(
            "linked_issue=\"$(jq -r '.number // empty' <<<\"$closing_json\")\"",
            block,
        )
        self.assertIn(
            'gh api --paginate "repos/$REPOSITORIO/issues/$linked_issue/comments?per_page=100"',
            block,
        )
        self.assertIn(
            'gh api --method POST "repos/$REPOSITORIO/issues/$linked_issue/comments"',
            block,
        )
        self.assertNotIn(
            'gh api --method POST "repos/$REPOSITORIO/issues/$number/comments"',
            block,
        )
        self.assertNotIn("pull-requests: write", block)

    def test_metadata_permissions_remain_least_privilege(self):
        for workflow in (GENERAL, PR):
            self.assertIn("permissions:\n  contents: read", workflow)
            self.assertNotIn("contents: write", workflow)
            self.assertNotIn("actions: write", workflow)
            self.assertNotIn("checks: write", workflow)
            self.assertNotIn("id-token: write", workflow)
            self.assertNotIn("secrets: inherit", workflow)
        self.assertEqual(PR.count("pull-requests: write"), 1)
        self.assertEqual(GENERAL.count("pull-requests: write"), 0)

    def test_validate_and_sweep_lifecycle_remains_bounded(self):
        general = job_block(GENERAL, "etiquetas")
        self.assertIn("plan-validation", general)
        self.assertIn("sweep-plan", general)
        self.assertIn(
            "group: labels-${{ github.repository }}-${{ inputs.mode }}-${{ inputs.issue_number }}",
            GENERAL,
        )
        self.assertIn(
            "group: labels-pr-${{ github.repository }}-${{ inputs.issue_number }}",
            PR,
        )
        self.assertNotIn("github.run_id", GENERAL)
        self.assertNotIn("github.run_id", PR)
        self.assertIn("select(.number != $auto)", general)
        self.assertIn("auto-create.json", general)
        self.assertIn("auto-update.json", general)
        self.assertIn("auto-close.json", general)
        self.assertNotIn("-f state=open --input", general)

    def test_external_actions_are_sha_pinned(self):
        actions = re.findall(
            r"^\s*uses:\s*([^\s]+)",
            GENERAL + "\n" + PR,
            flags=re.MULTILINE,
        )
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
