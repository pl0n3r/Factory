"""Pruebas offline del enlace CI auténtico → Readiness → Team Compiler."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from performance.ci_professional_report import diagnose_factoryrunner_ci_professionals
from performance.github_actions_ci import PerformanceCiObservationError

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "performance" / "contracts" / "factoryrunner.json"
NOW = "2026-10-24T20:00:00Z"


class CiProfessionalReportTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        # GET autenticado: FactoryRunner push/main CI #40119747013.
        self.run = {
            "id": 40119747013, "name": "CI", "event": "push",
            "head_branch": "main",
            "head_sha": "33277d549a82e9cba5371982d1d80e43e06bd0d5",
            "status": "completed", "conclusion": "success",
            "run_attempt": 1, "run_started_at": "2026-10-24T18:13:54Z",
            "updated_at": "2026-10-24T18:16:04Z",
            "repository": {"full_name": "pl0n3r/FactoryRunner"},
        }

    def report(self, run=None, *, evaluated_at=NOW):
        return diagnose_factoryrunner_ci_professionals(
            self.contract, self.run if run is None else run,
            evaluated_at=evaluated_at,
        )

    def test_real_ci_regression_recommends_professionals_with_exact_readiness(self):
        result = self.report()
        self.assertEqual(result["classification"], "PERF_DEGRADATION")
        self.assertEqual(result["status"], "DEGRADED")
        self.assertEqual(result["evidence_state"], "CURRENT")
        self.assertEqual(result["readiness"]["status"], "DEGRADED")
        self.assertEqual(result["team"]["decision"], "TEAM_RECOMMENDED")
        self.assertEqual(result["team"]["primary"], "sre")
        self.assertTrue({"sre", "qa"}.issubset(result["team"]["roles"]))
        self.assertEqual(result["identity"]["sha"], self.run["head_sha"])
        self.assertIn(
            "github:pl0n3r/FactoryRunner/actions/runs/40119747013/attempts/1",
            result["evidence_refs"],
        )
        self.assertFalse(result["candidate_terminal"])

    def test_healthy_ci_yields_no_assignment_or_fake_adoption(self):
        # Escenario sintético de 110 s; NO se afirma un AFTER auténtico.
        healthy = copy.deepcopy(self.run)
        healthy["run_started_at"] = "2026-10-24T18:14:14Z"
        result = self.report(healthy)
        self.assertEqual(result["classification"], "PERF_INFO")
        self.assertEqual(result["status"], "HEALTHY")
        self.assertEqual(result["team"]["decision"], "NO_ASSIGNMENT")
        self.assertEqual(result["team"]["roles"], [])
        self.assertIs(result["adopt"], False)
        self.assertIs(result["candidate_terminal"], False)

    def test_stale_ci_returns_unknown_and_no_assignment(self):
        stale = self.report(evaluated_at="2026-11-02T20:00:00Z")
        self.assertEqual(stale["evidence_state"], "STALE")
        self.assertEqual(stale["status"], "UNKNOWN")
        self.assertEqual(stale["readiness"]["status"], "UNKNOWN")
        self.assertEqual(stale["team"]["decision"], "NO_ASSIGNMENT")
        self.assertEqual(stale["team"]["roles"], [])
        for field in ("execute_actions", "create_work_item", "dispatch", "adopt"):
            self.assertIs(stale[field], False)

    def test_noncanonical_or_missing_provenance_fails_closed(self):
        invalid = (
            {"event": "pull_request"}, {"head_branch": "testing"},
            {"status": "in_progress"}, {"conclusion": "failure"},
            {"name": "CodeQL"}, {"id": 0}, {"run_attempt": False},
            {"head_sha": "unknown"}, {"repository": {"full_name": "other/repo"}},
            {"run_started_at": "not-a-time"},
            {"updated_at": "2026-10-24T18:13:53Z"},
        )
        for fields in invalid:
            with self.subTest(fields=fields):
                run = copy.deepcopy(self.run)
                run.update(fields)
                with self.assertRaises(PerformanceCiObservationError):
                    self.report(run)

    def test_output_minimal_and_nonexecuting(self):
        source = (ROOT / "performance" / "ci_professional_report.py").read_text(
            encoding="utf-8"
        )
        run = copy.deepcopy(self.run)
        secret = "noncanonical-private-metadata"
        run["extra_private_payload"] = secret
        result = self.report(run)
        self.assertNotIn(secret, repr(result))
        self.assertEqual(result["authority"], "unchanged")
        self.assertEqual(result["team"]["authority"], "unchanged")
        self.assertEqual(result["version"], 1)
        for field in ("execute_actions", "create_work_item", "dispatch",
                      "adopt", "candidate_terminal"):
            self.assertIs(result[field], False)
        for forbidden in ("requests.post", "urllib.request", "subprocess.run",
                          "gh api", "create_work_item("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
