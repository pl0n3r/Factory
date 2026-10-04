#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.10."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


class ReleaseCandidate1010Tests(unittest.TestCase):
    """Fija el rollout del contrato de permisos de Etiquetas y la puerta de release."""

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

    def test_candidate_is_at_least_1_0_10(self) -> None:
        """Las versiones posteriores conservan como mínimo la capacidad de 1.0.10."""
        payload = json.loads(
            (self.root / "config" / "version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        self.assertRegex(payload["version"], r"^\d+\.\d+\.\d+$")
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 10))

    def test_candidate_contains_labels_metadata_permission_contract(self) -> None:
        """Los reusables y el template conservan least privilege compatible."""
        reusable = (
            self.root / ".github" / "workflows" / "etiquetas.yml"
        ).read_text(encoding="utf-8")
        pr_reusable = (
            self.root / ".github" / "workflows" / "etiquetas-pr.yml"
        ).read_text(encoding="utf-8")
        template = (
            self.root / "template" / ".github" / "workflows" / "etiquetas.yml"
        ).read_text(encoding="utf-8")

        reusable_permissions = self._job_permissions(reusable, "etiquetas")
        self.assertEqual(
            reusable_permissions,
            {"contents: read", "issues: write", "pull-requests: read"},
        )
        self.assertNotIn("pull-requests: write", reusable)

        pr_write = {"contents: read", "issues: write", "pull-requests: write"}
        self.assertEqual(
            self._job_permissions(pr_reusable, "etiquetas-pr"),
            pr_write,
        )
        self.assertEqual(
            self._job_permissions(template, "validar-pr"),
            pr_write,
        )

        read_only = {"contents: read", "issues: write", "pull-requests: read"}
        for job in ("sync", "validar-issue", "sweep"):
            self.assertEqual(self._job_permissions(template, job), read_only)

        self.assertEqual(template.count("pull-requests: write"), 1)
        self.assertEqual(template.count("pull-requests: read"), 3)
        self.assertEqual(
            template.count("uses: pl0n3r/factory/.github/workflows/etiquetas.yml@v1"),
            3,
        )
        self.assertEqual(
            template.count("uses: pl0n3r/factory/.github/workflows/etiquetas-pr.yml@v1"),
            1,
        )

    def test_candidate_keeps_human_release_boundary(self) -> None:
        """Preparar 1.0.10 no mueve tags ni elimina la puerta exact-SHA."""
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
