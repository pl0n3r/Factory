#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.17."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1017Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_17(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.17"})

    def test_candidate_packages_performance_classifier_boundary(self) -> None:
        classifier = (
            self.root / "performance/classifier.py"
        ).read_text(encoding="utf-8")
        cli = (
            self.root / "scripts/performance-classify.py"
        ).read_text(encoding="utf-8")
        regressions = (
            self.root / "tests/test_performance_classifier.py"
        ).read_text(encoding="utf-8")

        for token in (
            "from performance.detector import detect_performance",
            "detect_performance(canonical, raw, evaluated_at=evaluated)",
            '"authority": "unchanged"',
            '"execute_actions": False',
            '"create_work_item": False',
        ):
            self.assertIn(token, classifier)

        self.assertIn("classification_authority", classifier)
        self.assertIn("Producer classification must be null.", classifier)
        self.assertIn("performance-classify: invalid or unsafe input", cli)
        for token in (
            'self.assertEqual(result["summary"]["total"], 10)',
            '"PERF_INFO": 6',
            '"PERF_REVIEW": 4',
            '"CURRENT": 6',
            '"UNKNOWN": 4',
        ):
            self.assertIn(token, regressions)

    def test_candidate_preserves_sonar_hardening(self) -> None:
        cli = (
            self.root / "scripts/performance-classify.py"
        ).read_text(encoding="utf-8")
        classifier = (
            self.root / "performance/classifier.py"
        ).read_text(encoding="utf-8")
        sonar = (
            self.root / ".github/workflows/sonar.yml"
        ).read_text(encoding="utf-8")

        for token in (
            "from scripts.safe_io import SafeIOError, read_repo_text, write_repo_text",
            "read_repo_text(path, root=ROOT)",
            "write_repo_text(args.output, payload, root=ROOT)",
        ):
            self.assertIn(token, cli)
        self.assertNotIn("path.read_text(", cli)
        self.assertNotIn("args.output.write_text(", cli)
        self.assertIn("def _identity(", classifier)
        self.assertIn("def _nonempty(", classifier)
        self.assertIn("-Dsonar.qualitygate.wait=true", sonar)
        self.assertIn(
            "-Dsonar.python.coverage.reportPaths=build/coverage/python.xml",
            sonar,
        )

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (
            self.root / ".github/workflows/release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        expected_sha_token = "EXPECTED_SHA: $" + "{{ inputs.expected_sha }}"
        gate_issue_token = "GATE_ISSUE: $" + "{{ inputs.gate_issue }}"
        for token in (
            "workflow_dispatch:",
            "expected_sha:",
            "gate_issue:",
            "needs: preflight",
            expected_sha_token,
            gate_issue_token,
        ):
            self.assertIn(token, workflow)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
