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
    def test_all_callers_match_reusable_least_privilege(self):
        expected = {"contents: read", "issues: write", "pull-requests: read"}
        for name in ("sync", "validar-issue", "validar-pr", "sweep"):
            self.assertEqual(permissions(name), expected)

    def test_template_keeps_factory_v1_and_least_privilege(self):
        for name in ("sync", "validar-issue", "validar-pr", "sweep"):
            block = job_block(name)
            self.assertIn("uses: pl0n3r/factory/.github/workflows/etiquetas.yml@v1", block)
            self.assertIn("contents: read", block)
            self.assertIn("issues: write", block)
        for forbidden in (
            "contents: write", "actions: write", "checks: write",
            "id-token: write", "secrets: inherit",
        ):
            self.assertNotIn(forbidden, WF)

    def test_permission_distribution_is_exact_and_regression_safe(self):
        distribution = {
            name: permissions(name)
            for name in ("sync", "validar-issue", "validar-pr", "sweep")
        }
        self.assertFalse(
            [name for name, perms in distribution.items() if "pull-requests: write" in perms]
        )
        self.assertEqual(WF.count("pull-requests: write"), 0)
        self.assertEqual(WF.count("pull-requests: read"), 4)
        self.assertIn("mode: validate", job_block("validar-pr"))
        self.assertIn("issue_number: ${{ github.event.pull_request.number }}", job_block("validar-pr"))


if __name__ == "__main__":
    unittest.main()
