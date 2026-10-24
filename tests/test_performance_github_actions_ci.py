"""Regresión de ingestión GET-only desde runs auténticos FactoryRunner."""
import copy
import json
from pathlib import Path
import unittest

from performance.github_actions_ci import (
    PerformanceCiObservationError,
    evaluate_factoryrunner_ci_run,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "performance" / "contracts" / "factoryrunner.json"
EVALUATED = "2026-10-24T16:27:00Z"


class FactoryRunnerCiObservationTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        # Identidad y marcas de tiempo leídas del API autenticado de Actions.
        self.current = {
            "id": 40029930158,
            "name": "CI",
            "event": "push",
            "head_branch": "main",
            "head_sha": "789a312d7520e9813835f99d8c4e5de5ee22cb2a",
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
            "run_started_at": "2026-10-23T21:53:07Z",
            "updated_at": "2026-10-23T21:56:09Z",
            "repository": {"full_name": "pl0n3r/FactoryRunner"},
        }

    def evaluate(self, snapshot=None, *, evaluated_at=EVALUATED):
        return evaluate_factoryrunner_ci_run(
            self.contract,
            self.current if snapshot is None else snapshot,
            evaluated_at=evaluated_at,
        )

    def test_real_main_ci_breach_uses_exact_contract_without_rebaseline(self):
        result = self.evaluate()
        detection = result["detection"]
        self.assertEqual(detection["observed"]["value"], 182)
        self.assertEqual(detection["classification"], "PERF_DEGRADATION")
        self.assertEqual(detection["evidence_state"], "CURRENT")
        self.assertEqual(detection["budget"], {"operator": "lte", "unit": "s", "value": 120})
        self.assertEqual(detection["baseline"]["value"], 124)
        self.assertEqual(detection["delta"], 58)
        self.assertEqual(result["performance_status"]["status"], "DEGRADED")
        self.assertFalse(result["create_work_item"])
        self.assertFalse(result["execute_actions"])
        self.assertFalse(result["candidate_terminal"])
        self.assertEqual(result["authority"], "unchanged")
        self.assertEqual(result["triage"]["role_hints"], ["qa", "sre"])
        self.assertEqual(
            detection["evidence_ref"],
            "github:pl0n3r/FactoryRunner/actions/runs/40029930158/attempts/1",
        )

    def test_actual_earlier_ci_is_breach_not_fake_after(self):
        earlier = copy.deepcopy(self.current)
        earlier.update({
            "id": 40012602637,
            "head_sha": "ace49488a307e1e4b779b68be4e382358d92ce81",
            "run_started_at": "2026-10-23T19:35:32Z",
            "updated_at": "2026-10-23T19:38:19Z",
        })
        result = self.evaluate(earlier)
        self.assertEqual(result["detection"]["observed"]["value"], 167)
        self.assertEqual(result["performance_status"]["status"], "DEGRADED")
        self.assertFalse(result["create_work_item"])

    def test_noncanonical_runs_and_mismatched_identity_fail_closed(self):
        modifications = [
            {"event": "pull_request"}, {"head_branch": "feature"},
            {"conclusion": "failure"}, {"status": "in_progress"},
            {"name": "CodeQL"}, {"repository": {"full_name": "other/FactoryRunner"}},
            {"head_sha": "not-a-sha"}, {"id": True},
            {"id": 0}, {"run_attempt": False}, {"run_attempt": 0},
            {"run_started_at": None}, {"updated_at": "2026-10-24"},
            {"updated_at": "2026-10-23T21:53:06Z"},
        ]
        for patch in modifications:
            with self.subTest(patch=patch):
                snapshot = copy.deepcopy(self.current)
                snapshot.update(patch)
                with self.assertRaises(PerformanceCiObservationError):
                    self.evaluate(snapshot)

    def test_stale_run_is_not_healthy_and_authority_never_expands(self):
        result = self.evaluate(evaluated_at="2026-11-02T16:27:00Z")
        self.assertEqual(result["detection"]["classification"], "PERF_REVIEW")
        self.assertEqual(result["performance_status"]["status"], "UNKNOWN")
        self.assertFalse(result["create_work_item"])
        self.assertFalse(result["execute_actions"])

    def test_adapter_does_not_perform_side_effects_or_claim_prod_success(self):
        source = (ROOT / "performance" / "github_actions_ci.py").read_text(encoding="utf-8")
        for forbidden in ("requests.post", "urllib.request", "subprocess.run", "gh api", "actions/workflows/dispatches"):
            self.assertNotIn(forbidden, source)
        result = self.evaluate()
        self.assertFalse(result["candidate_terminal"])
        self.assertEqual(result["detection"]["identity"]["release"], "ci")


if __name__ == "__main__":
    unittest.main()
