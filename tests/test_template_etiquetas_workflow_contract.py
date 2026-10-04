#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / "template/.github/workflows/etiquetas.yml").read_text(encoding="utf-8")


def job_block(name):
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        WF,
    )
    if match is None:
        raise AssertionError(f"No se encontró el job {name}")
    return match.group("body")


def permissions(name):
    block = job_block(name)
    match = re.search(
        r"(?ms)^    permissions:\n(?P<permissions>(?:^      [^\n]+\n)+)",
        block,
    )
    if match is None:
        raise AssertionError(f"No se encontró permissions en {name}")
    return {line.strip() for line in match.group("permissions").splitlines()}


class TemplateEtiquetasWorkflowContractTests(unittest.TestCase):
    def test_only_pr_validation_requests_pull_request_write(self):
        read_only_pr = {"contents: read", "issues: write", "pull-requests: read"}
        pr_write = {"contents: read", "issues: write", "pull-requests: write"}

        for name in ("sync", "validar-issue", "sweep"):
            with self.subTest(job=name):
                self.assertEqual(permissions(name), read_only_pr)
        self.assertEqual(permissions("validar-pr"), pr_write)

        writers = [
            name
            for name in ("sync", "validar-issue", "validar-pr", "sweep")
            if "pull-requests: write" in permissions(name)
        ]
        self.assertEqual(writers, ["validar-pr"])
        self.assertEqual(WF.count("pull-requests: write"), 1)
        self.assertEqual(WF.count("pull-requests: read"), 3)

    def test_template_keeps_factory_v1_and_least_privilege(self):
        general_ref = "uses: pl0n3r/factory/.github/workflows/etiquetas.yml@v1"
        pr_ref = "uses: pl0n3r/factory/.github/workflows/etiquetas-pr.yml@v1"

        for name in ("sync", "validar-issue", "sweep"):
            block = job_block(name)
            self.assertIn(general_ref, block)
            self.assertIn("contents: read", block)
            self.assertIn("issues: write", block)

        pr_block = job_block("validar-pr")
        self.assertIn(pr_ref, pr_block)
        self.assertNotIn(general_ref, pr_block)
        self.assertIn("contents: read", pr_block)
        self.assertIn("issues: write", pr_block)

        self.assertEqual(WF.count(general_ref), 3)
        self.assertEqual(WF.count(pr_ref), 1)

        for forbidden in (
            "contents: write",
            "actions: write",
            "checks: write",
            "id-token: write",
            "secrets: inherit",
        ):
            self.assertNotIn(forbidden, WF)

    def test_pr_validation_grants_write_for_safe_label_inheritance(self):
        pr_permissions = permissions("validar-pr")
        self.assertIn("issues: write", pr_permissions)
        self.assertIn("pull-requests: write", pr_permissions)
        self.assertNotIn("pull-requests: read", pr_permissions)
        self.assertIn("mode: validate", job_block("validar-pr"))
        self.assertIn(
            "issue_number: ${{ github.event.pull_request.number }}",
            job_block("validar-pr"),
        )

    def test_permission_distribution_is_exact_and_regression_safe(self):
        distribution = {
            name: permissions(name)
            for name in ("sync", "validar-issue", "validar-pr", "sweep")
        }
        self.assertEqual(
            [name for name, perms in distribution.items() if "pull-requests: write" in perms],
            ["validar-pr"],
        )
        self.assertEqual(WF.count("pull-requests: write"), 1)
        self.assertEqual(WF.count("pull-requests: read"), 3)
        self.assertNotIn("checks: read", permissions("sweep"))


if __name__ == "__main__":
    unittest.main()
