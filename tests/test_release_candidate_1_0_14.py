#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.14."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.politica_kit import PolicyError, parse_reviewer_policy, resolve_required_review_bot


class ReleaseCandidate1014Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_14(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.14"})

    def test_candidate_contains_base_sha_reviewer_policy_fix(self) -> None:
        workflow = (
            self.root / ".github/workflows/politica.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "github.event.pull_request.base.sha",
            ".github/factory-policy.json?ref=$CURRENT_BASE",
            "--base-policy-file",
        ):
            self.assertIn(token, workflow)

        base = parse_reviewer_policy(
            '{"version":1,"required_review_bot":"coderabbitai[bot]"}'
        )
        with self.assertRaises(PolicyError):
            parse_reviewer_policy(
                '{"version":1,"required_review_bot":null,"extra":true}'
            )
        self.assertEqual(
            resolve_required_review_bot(base, ""),
            "coderabbitai[bot]",
        )
        self.assertEqual(
            resolve_required_review_bot("", "coderabbitai[bot]"),
            "coderabbitai[bot]",
        )
        with self.assertRaises(PolicyError):
            resolve_required_review_bot(base, "other-bot[bot]")

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (
            self.root / ".github/workflows/release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "workflow_dispatch:",
            "expected_sha:",
            "gate_issue:",
            "needs: preflight",
        ):
            self.assertIn(token, workflow)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
