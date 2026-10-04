#!/usr/bin/env python3
"""Regresiones mínimas del candidato Factory 1.0.11."""

import json
import re
import unittest
from pathlib import Path

from scripts import coordinar_trabajo as coordinator


class ReleaseCandidate1011Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def tearDown(self) -> None:
        coordinator.configure_profile("es")

    def test_candidate_is_at_least_1_0_11(self) -> None:
        source = self.root / "config" / "version.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        self.assertEqual(set(payload), {"version"})
        self.assertRegex(payload["version"], r"^\d+\.\d+\.\d+$")
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 11))

    def test_candidate_keeps_mode_scoped_labels_permissions(self) -> None:
        reusable = (self.root / ".github/workflows/etiquetas.yml").read_text()
        template = (
            self.root / "template/.github/workflows/etiquetas.yml"
        ).read_text()

        general = re.search(
            r"(?ms)^  etiquetas:\n(?P<body>.*?)(?=^  etiquetas-pr:\n)",
            reusable,
        )
        pr_validate = re.search(
            r"(?ms)^  etiquetas-pr:\n(?P<body>.*)\Z",
            reusable,
        )
        template_pr = re.search(
            r"(?ms)^  validar-pr:\n(?P<body>.*?)(?=^  sweep:\n)",
            template,
        )
        self.assertIsNotNone(general)
        self.assertIsNotNone(pr_validate)
        self.assertIsNotNone(template_pr)

        general_body = general.group("body")
        pr_body = pr_validate.group("body")
        template_pr_body = template_pr.group("body")

        self.assertIn("pull-requests: read", general_body)
        self.assertNotIn("pull-requests: write", general_body)
        self.assertIn("pull-requests: write", pr_body)
        self.assertIn("pull-requests: write", template_pr_body)

        self.assertEqual(reusable.count("pull-requests: write"), 1)
        self.assertEqual(template.count("pull-requests: write"), 1)
        self.assertEqual(template.count("pull-requests: read"), 3)
        for forbidden in (
            "contents: write",
            "actions: write",
            "checks: write",
            "id-token: write",
            "secrets: inherit",
        ):
            self.assertNotIn(forbidden, reusable)
            self.assertNotIn(forbidden, template)

    def test_candidate_contains_profile_invariant_contract_renewal(self) -> None:
        reservation = "0b9040ef-85eb-5c31-b5b9-9722a07675bf"
        expected = ("renovar-contrato", reservation)
        for profile in ("es", "en"):
            coordinator.configure_profile(profile)
            self.assertEqual(
                coordinator.parse_comment_command(f"/renovar-contrato {reservation}"),
                expected,
            )
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_comment_command("/renovar-contrato invalid")

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (self.root / ".github/workflows/release-bootstrap.yml").read_text()
        required = ("workflow_dispatch:", "expected_sha:", "gate_issue:", "needs: preflight")
        self.assertTrue(all(token in workflow for token in required))
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
