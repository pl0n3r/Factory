#!/usr/bin/env python3
"""Regresión del contrato de arranque caller↔reusables de Etiquetas."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.reusable_permission_compat import compare_permissions
from scripts.reusable_release_preflight import _required


ROOT = Path(__file__).resolve().parents[1]
GENERAL = (ROOT / ".github/workflows/etiquetas.yml").read_text(encoding="utf-8")
PR = (ROOT / ".github/workflows/etiquetas-pr.yml").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "template/.github/workflows/etiquetas.yml").read_text(encoding="utf-8")

GENERAL_GRANT = {"contents": "read", "issues": "write", "pull-requests": "read"}
PR_GRANT = {"contents": "read", "issues": "write", "pull-requests": "write"}

AFFECTED_CONSUMERS = (
    "pl0n3r/Condor",
    "pl0n3r/ControlBot",
    "pl0n3r/FactoryRunner",
    "pl0n3r/brvtal",
)


def job_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        text,
    )
    if match is None:
        raise AssertionError(f"No se encontró el job {name}")
    return match.group("body")


def permissions(text: str, name: str) -> dict[str, str]:
    block = job_block(text, name)
    match = re.search(
        r"(?ms)^    permissions:\n(?P<permissions>(?:^      [^\n]+\n)+)",
        block,
    )
    if match is None:
        raise AssertionError(f"No se encontró permissions en {name}")
    result = {}
    for line in match.group("permissions").splitlines():
        scope, level = line.strip().split(":", 1)
        result[scope] = level.strip()
    return result


class LabelsReusableStartupTests(unittest.TestCase):
    def test_current_consumer_callers_do_not_trigger_startup_failure_against_new_reusable(self) -> None:
        general_required = _required(GENERAL, "factory:etiquetas.yml")
        pr_required = _required(PR, "factory:etiquetas-pr.yml")
        self.assertEqual(general_required, GENERAL_GRANT)
        self.assertEqual(pr_required, PR_GRANT)

        for repository in AFFECTED_CONSUMERS:
            with self.subTest(repository=repository, reusable="general"):
                result = compare_permissions(general_required, GENERAL_GRANT)
                self.assertTrue(result["compatible"], result)
            with self.subTest(repository=repository, reusable="pr"):
                result = compare_permissions(pr_required, PR_GRANT)
                self.assertTrue(result["compatible"], result)

    def test_template_caller_uses_mode_scoped_reusables_and_permissions(self) -> None:
        for name in ("sync", "validar-issue", "sweep"):
            with self.subTest(job=name):
                block = job_block(TEMPLATE, name)
                self.assertEqual(permissions(TEMPLATE, name), GENERAL_GRANT)
                self.assertIn(
                    "uses: pl0n3r/factory/.github/workflows/etiquetas.yml@v1",
                    block,
                )

        pr = job_block(TEMPLATE, "validar-pr")
        self.assertEqual(permissions(TEMPLATE, "validar-pr"), PR_GRANT)
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/etiquetas-pr.yml@v1",
            pr,
        )

    def test_general_reusable_never_requires_pr_write(self) -> None:
        self.assertNotIn("pull-requests: write", GENERAL)
        self.assertEqual(
            _required(GENERAL, "factory:etiquetas.yml"),
            GENERAL_GRANT,
        )

    def test_pr_reusable_has_single_minimal_write_envelope(self) -> None:
        self.assertEqual(PR.count("pull-requests: write"), 1)
        self.assertEqual(
            _required(PR, "factory:etiquetas-pr.yml"),
            PR_GRANT,
        )
        for forbidden in (
            "contents: write",
            "actions: write",
            "checks: write",
            "id-token: write",
            "secrets: inherit",
        ):
            self.assertNotIn(forbidden, PR)

    def test_reusables_remain_closed_timed_and_fail_closed(self) -> None:
        self.assertIn('case "$MODE" in sync|validate|sweep)', GENERAL)
        self.assertIn('case "$MODE" in validate)', PR)
        for source in (GENERAL, PR):
            self.assertIn("workflow_call:", source)
            self.assertIn("timeout-minutes: 8", source)
            self.assertIn('case "$LANGUAGE" in es|en)', source)
            self.assertIn("persist-credentials: false", source)
            self.assertIn("repository: pl0n3r/factory", source)


if __name__ == "__main__":
    unittest.main()
