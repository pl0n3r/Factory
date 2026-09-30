#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.11."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts import coordinar_trabajo as coordinator


class ReleaseCandidate1011Tests(unittest.TestCase):
    """Fija los dos repairs y conserva la puerta humana de publicación."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    @staticmethod
    def _job_permissions(workflow: str, job: str) -> set[str]:
        block = re.search(
            rf"(?ms)^  {re.escape(job)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
            workflow,
        )
        if block is None:
            raise AssertionError(f"No se encontró el job {job}")
        match = re.search(
            r"(?ms)^    permissions:\n(?P<permissions>(?:^      [^\n]+\n)+)",
            block.group("body"),
        )
        if match is None:
            raise AssertionError(f"No se encontró permissions en {job}")
        return {line.strip() for line in match.group("permissions").splitlines()}

    def tearDown(self) -> None:
        coordinator.configure_profile("es")

    def test_candidate_version_is_1_0_11(self) -> None:
        payload = json.loads(
            (self.root / "config" / "version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.11"})

    def test_candidate_contains_labels_startup_fix(self) -> None:
        reusable = (
            self.root / ".github" / "workflows" / "etiquetas.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            self._job_permissions(reusable, "etiquetas"),
            {"contents: read", "issues: write", "pull-requests: read"},
        )
        self.assertNotIn("pull-requests: write", reusable)

    def test_candidate_contains_profile_invariant_contract_renewal(self) -> None:
        for profile in ("es", "en"):
            with self.subTest(profile=profile):
                coordinator.configure_profile(profile)
                reservation_id = "d9a43506-7ffb-4721-94ee-f16a493cb744"
                self.assertEqual(
                    coordinator.parse_comment_command(
                        f"/renovar-contrato {reservation_id}"
                    ),
                    ("renovar-contrato", reservation_id),
                )
        coordinator.configure_profile("en")
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_comment_command("/renovar-contrato no-es-uuid")

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (
            self.root / ".github" / "workflows" / "release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("expected_sha:", workflow)
        self.assertIn("gate_issue:", workflow)
        self.assertIn("needs: preflight", workflow)
        self.assertIsNone(re.search(r"(?m)^\s{2}push\s*:", workflow))


if __name__ == "__main__":
    unittest.main()
