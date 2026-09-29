#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.8."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate108Tests(unittest.TestCase):
    """Fija versión, capacidad requerida y frontera humana de publicación."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_8(self) -> None:
        """La fuente canónica declara exactamente 1.0.8."""
        payload = json.loads(
            (self.root / "config" / "version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.8"})

    def test_candidate_contains_post_merge_incident_contract(self) -> None:
        """El candidato incluye código y documentación del lifecycle post-merge."""
        coordinator = (
            self.root / "scripts" / "coordinar_trabajo.py"
        ).read_text(encoding="utf-8")
        docs = (self.root / "docs" / "orquestador.md").read_text(encoding="utf-8")

        for content in (coordinator, docs):
            self.assertIn("factory-issue-lifecycle", content)
            self.assertIn("post_merge_validation", content)

    def test_candidate_is_metadata_only_release_preparation(self) -> None:
        """Publicar sigue requiriendo dispatch, SHA exacto y gate humano."""
        workflow = (
            self.root / ".github" / "workflows" / "release-bootstrap.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("expected_sha:", workflow)
        self.assertIn("gate_issue:", workflow)
        self.assertNotIn("\npush:", workflow)


if __name__ == "__main__":
    unittest.main()
