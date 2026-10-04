#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/etiquetas.yml").read_text(encoding="utf-8")


def job_block(name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        WF,
    )
    if match is None:
        raise AssertionError(f"No se encontró el job {name}")
    return match.group("body")


def job_permissions(name: str) -> set[str]:
    block = job_block(name)
    match = re.search(
        r"(?ms)^    permissions:\n(?P<permissions>(?:^      [^\n]+\n)+)",
        block,
    )
    if match is None:
        raise AssertionError(f"No se encontró permissions de {name}")
    return {line.strip() for line in match.group("permissions").splitlines()}


class EtiquetasWorkflowContractTests(unittest.TestCase):
    def test_modes_and_language_are_closed(self):
        self.assertIn('case "$MODE" in sync|validate|sweep)', WF)
        self.assertIn('case "$LANGUAGE" in es|en)', WF)

    def test_uses_published_factory_catalog_by_language_not_path(self):
        for name in ("etiquetas", "etiquetas-pr"):
            block = job_block(name)
            self.assertIn("repository: pl0n3r/factory", block)
            self.assertIn("labels_kit.py", block)
            self.assertIn("ref: v1", block)
            self.assertIn("--language", block)
            self.assertNotIn("--catalog", block)
        self.assertNotIn("inputs.kit_ref", WF)

    def test_pr_validate_job_has_minimum_write_authority(self):
        self.assertEqual(
            job_permissions("etiquetas-pr"),
            {"contents: read", "issues: write", "pull-requests: write"},
        )
        block = job_block("etiquetas-pr")
        self.assertIn(
            "if: inputs.mode == 'validate' && github.event_name == 'pull_request'",
            block,
        )
        self.assertNotIn("checks: write", block)
        self.assertNotIn("actions: write", block)
        self.assertNotIn("id-token: write", block)
        self.assertNotIn("contents: write", block)

    def test_non_pr_job_remains_read_only(self):
        self.assertEqual(
            job_permissions("etiquetas"),
            {"contents: read", "issues: write", "pull-requests: read"},
        )
        block = job_block("etiquetas")
        self.assertIn(
            "if: inputs.mode != 'validate' || github.event_name != 'pull_request'",
            block,
        )
        self.assertNotIn("pull-requests: write", block)
        self.assertIn("Sincronizar catálogo", block)
        self.assertIn("Barrer trabajo abierto", block)
        self.assertIn("Detectar merges con Etiquetas no verde", block)

    def test_pr_and_non_pr_jobs_are_mutually_exclusive_and_keep_labels_check_name(self):
        general = job_block("etiquetas")
        pr = job_block("etiquetas-pr")
        self.assertIn("name: Labels", general)
        self.assertIn("name: Labels", pr)
        self.assertIn(
            "inputs.mode != 'validate' || github.event_name != 'pull_request'",
            general,
        )
        self.assertIn(
            "inputs.mode == 'validate' && github.event_name == 'pull_request'",
            pr,
        )
        self.assertEqual(WF.count("    name: Labels\n"), 2)

    def test_pr_validate_keeps_safe_label_inheritance_without_changing_sweep(self):
        pr = job_block("etiquetas-pr")
        general = job_block("etiquetas")

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
        general = job_block("etiquetas")
        self.assertIn("name: Validar Issue o PR", general)
        self.assertIn("if: inputs.mode == 'validate'", general)
        self.assertIn("plan-validation", general)
        self.assertIn("pull-requests: read", general)
        self.assertNotIn("pull-requests: write", general)

    def test_sweep_routes_merge_alerts_to_linked_issue_without_pr_write(self):
        block = job_block("etiquetas")
        self.assertIn('closing-reference --language "$LANGUAGE"', block)
        self.assertIn(
            'linked_issue="$(jq -r \' .number // empty\' <<<"$closing_json")"'.replace("' .", "'."),
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
        self.assertIn("permissions:\n  contents: read", WF)
        self.assertNotIn("contents: write", WF)
        self.assertNotIn("actions: write", WF)
        self.assertNotIn("checks: write", WF)
        self.assertNotIn("id-token: write", WF)
        self.assertNotIn("secrets: inherit", WF)
        self.assertEqual(WF.count("pull-requests: write"), 1)

    def test_validate_and_sweep_lifecycle_remains_bounded(self):
        general = job_block("etiquetas")
        self.assertIn("plan-validation", general)
        self.assertIn("sweep-plan", general)
        self.assertIn(
            "group: labels-${{ github.repository }}-${{ inputs.mode }}-${{ inputs.issue_number }}",
            WF,
        )
        self.assertNotIn("github.run_id", WF)
        self.assertIn("select(.number != $auto)", general)
        self.assertIn("auto-create.json", general)
        self.assertIn("auto-update.json", general)
        self.assertIn("auto-close.json", general)
        self.assertNotIn("-f state=open --input", general)

    def test_external_actions_are_sha_pinned(self):
        actions = re.findall(r"^\s*uses:\s*([^\s]+)", WF, flags=re.MULTILINE)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
