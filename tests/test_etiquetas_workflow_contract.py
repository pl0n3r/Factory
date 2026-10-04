#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERAL = (ROOT / ".github/workflows/etiquetas.yml").read_text(encoding="utf-8")
PR = (ROOT / ".github/workflows/etiquetas-pr.yml").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "template/.github/workflows/etiquetas.yml").read_text(encoding="utf-8")


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
    def test_reusable_envelope_is_compatible_with_read_only_issue_sweep_and_sync_callers(self):
        self.assertEqual(
            job_permissions(GENERAL, "etiquetas"),
            {"contents: read", "issues: write", "pull-requests: read"},
        )
        self.assertNotIn("pull-requests: write", GENERAL)
        self.assertNotIn("\n  etiquetas-pr:\n", GENERAL)
        for token in (
            "Sincronizar catálogo",
            "Barrer trabajo abierto",
            "Detectar merges con Etiquetas no verde",
        ):
            self.assertIn(token, GENERAL)

    def test_pr_write_authority_is_isolated_to_pr_callers_only(self):
        self.assertEqual(
            job_permissions(PR, "etiquetas-pr"),
            {"contents: read", "issues: write", "pull-requests: write"},
        )
        self.assertEqual(PR.count("pull-requests: write"), 1)
        self.assertNotIn("Barrer trabajo abierto", PR)
        self.assertNotIn("Sincronizar catálogo", PR)
        self.assertNotIn("Detectar merges con Etiquetas no verde", PR)
        self.assertIn("plan-validation", PR)
        self.assertIn("<!-- factory-label-validation -->", PR)
        self.assertIn(
            "if: inputs.mode == 'validate' && github.event_name == 'pull_request'",
            PR,
        )

    def test_template_routes_only_pr_validation_to_write_reusable(self):
        general_ref = "uses: pl0n3r/factory/.github/workflows/etiquetas.yml@v1"
        pr_ref = "uses: pl0n3r/factory/.github/workflows/etiquetas-pr.yml@v1"
        self.assertEqual(TEMPLATE.count(general_ref), 3)
        self.assertEqual(TEMPLATE.count(pr_ref), 1)
        validar_pr = job_block(TEMPLATE, "validar-pr")
        self.assertIn(pr_ref, validar_pr)
        self.assertEqual(
            job_permissions(TEMPLATE, "validar-pr"),
            {"contents: read", "issues: write", "pull-requests: write"},
        )
        for name in ("sync", "validar-issue", "sweep"):
            with self.subTest(job=name):
                block = job_block(TEMPLATE, name)
                self.assertIn(general_ref, block)
                self.assertEqual(
                    job_permissions(TEMPLATE, name),
                    {"contents: read", "issues: write", "pull-requests: read"},
                )

    def test_modes_language_and_factory_checkout_remain_closed(self):
        self.assertIn('case "$MODE" in sync|validate|sweep)', GENERAL)
        self.assertIn('case "$MODE" in validate)', PR)
        for workflow in (GENERAL, PR):
            self.assertIn('case "$LANGUAGE" in es|en)', workflow)
            self.assertIn("repository: pl0n3r/factory", workflow)
            self.assertIn("ref: v1", workflow)
            self.assertIn("persist-credentials: false", workflow)
            self.assertNotIn("secrets: inherit", workflow)
            self.assertNotIn("contents: write", workflow)
            self.assertNotIn("actions: write", workflow)
            self.assertNotIn("checks: write", workflow)
            self.assertNotIn("id-token: write", workflow)

    def test_general_and_pr_paths_keep_visible_labels_check_name(self):
        self.assertIn("name: Labels", job_block(GENERAL, "etiquetas"))
        self.assertIn("name: Labels", job_block(PR, "etiquetas-pr"))
        self.assertEqual(GENERAL.count("    name: Labels\n"), 1)
        self.assertEqual(PR.count("    name: Labels\n"), 1)

    def test_validate_pr_keeps_safe_label_inheritance(self):
        block = job_block(PR, "etiquetas-pr")
        self.assertIn("linked_issue:$linked[0]", block)
        self.assertIn(
            'gh api --method POST "repos/$REPOSITORIO/issues/$ISSUE_NUMBER/labels"',
            block,
        )
        self.assertIn("warning_action", block)
        self.assertNotIn("sweep-plan", block)

    def test_general_validate_issue_stays_read_only_for_pull_requests(self):
        block = job_block(GENERAL, "etiquetas")
        self.assertIn("name: Validar Issue o PR", block)
        self.assertIn("if: inputs.mode == 'validate'", block)
        self.assertIn("plan-validation", block)
        self.assertIn("pull-requests: read", block)
        self.assertNotIn("pull-requests: write", block)

    def test_external_actions_are_sha_pinned(self):
        for workflow in (GENERAL, PR):
            actions = re.findall(r"^\s*uses:\s*([^\s]+)", workflow, flags=re.MULTILINE)
            self.assertTrue(actions)
            for action in actions:
                self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
