#!/usr/bin/env python3
"""Regresión del contrato de arranque caller↔reusable para Etiquetas."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REUSABLE = (ROOT / ".github/workflows/etiquetas.yml").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "template/.github/workflows/etiquetas.yml").read_text(encoding="utf-8")
EXPECTED_GENERAL = {"contents: read", "issues: write", "pull-requests: read"}
EXPECTED_PR_VALIDATE = {"contents: read", "issues: write", "pull-requests: write"}


def job_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        text,
    )
    if match is None:
        raise AssertionError(f"No se encontró el job {name}")
    return match.group("body")


def permissions(text: str, name: str) -> set[str]:
    block = job_block(text, name)
    match = re.search(
        r"(?ms)^    permissions:\n(?P<permissions>(?:^      [^\n]+\n)+)",
        block,
    )
    if match is None:
        raise AssertionError(f"No se encontró permissions en {name}")
    return {line.strip() for line in match.group("permissions").splitlines()}


class LabelsReusableStartupTests(unittest.TestCase):
    def test_reusable_contract_is_valid_for_pull_request_callers(self) -> None:
        self.assertEqual(permissions(REUSABLE, "etiquetas"), EXPECTED_GENERAL)
        self.assertEqual(permissions(REUSABLE, "etiquetas-pr"), EXPECTED_PR_VALIDATE)
        self.assertNotIn("pull-requests: write", job_block(REUSABLE, "etiquetas"))
        self.assertEqual(
            job_block(REUSABLE, "etiquetas-pr").count("pull-requests: write"),
            1,
        )

    def test_template_caller_uses_mode_scoped_permissions(self) -> None:
        for name in ("sync", "validar-issue", "sweep"):
            with self.subTest(job=name):
                self.assertEqual(permissions(TEMPLATE, name), EXPECTED_GENERAL)
        self.assertEqual(permissions(TEMPLATE, "validar-pr"), EXPECTED_PR_VALIDATE)
        self.assertIn("uses: pl0n3r/factory/.github/workflows/etiquetas.yml@v1", TEMPLATE)
        self.assertEqual(TEMPLATE.count("pull-requests: write"), 1)

    def test_caller_and_reusable_permissions_match_by_mode(self) -> None:
        mapping = {
            "sync": "etiquetas",
            "validar-issue": "etiquetas",
            "validar-pr": "etiquetas-pr",
            "sweep": "etiquetas",
        }
        for caller_name, reusable_name in mapping.items():
            with self.subTest(caller=caller_name, reusable=reusable_name):
                caller = permissions(TEMPLATE, caller_name)
                reusable = permissions(REUSABLE, reusable_name)
                self.assertEqual(
                    caller,
                    reusable,
                    msg=f"{caller_name} no coincide con {reusable_name}: {caller} vs {reusable}",
                )

        self.assertEqual(REUSABLE.count("pull-requests: write"), 1)
        self.assertEqual(TEMPLATE.count("pull-requests: write"), 1)
        self.assertNotIn("pull-requests: write", job_block(REUSABLE, "etiquetas"))

    def test_modes_remain_closed_timed_and_fail_closed(self) -> None:
        self.assertIn("workflow_call:", REUSABLE)
        self.assertIn("timeout-minutes: 8", REUSABLE)
        self.assertIn('case "$MODE" in sync|validate|sweep)', REUSABLE)
        self.assertIn('case "$LANGUAGE" in es|en)', REUSABLE)
        self.assertIn("persist-credentials: false", REUSABLE)
        self.assertIn("repository: pl0n3r/factory", REUSABLE)
        self.assertNotIn("secrets: inherit", REUSABLE)
        self.assertNotIn("contents: write", REUSABLE)
        self.assertNotIn("actions: write", REUSABLE)
        self.assertNotIn("checks: write", REUSABLE)
        self.assertNotIn("id-token: write", REUSABLE)


if __name__ == "__main__":
    unittest.main()
