import copy
import json
import unittest
from pathlib import Path

from performance.contract import (
    ALLOWED_ACTIONS,
    ESCALATION_CONDITIONS,
    OPERATORS,
    UNITS,
    PerformanceContractError,
    canonical_performance_contract,
    validate_performance_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def metric(metric_id="latency_p95", unit="ms", baseline=180, budget=250):
    return {
        "id": metric_id,
        "label": metric_id.replace("_", " "),
        "baseline": {"value": baseline, "unit": unit, "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": budget, "unit": unit},
        "window": {"duration_seconds": 300, "min_samples": 20},
        "freshness": {"max_age_seconds": 900},
        "evidence": {"source": "ci", "ref": "run:36496695374", "observed_at": "2026-09-28T20:00:00Z"},
        "allowed_actions": ["diagnose", "observe", "benchmark"],
        "escalation_conditions": ["architecture_change", "cost_change"],
    }


def contract(project="condor", metrics=None):
    return {
        "version": 1,
        "project": project,
        "surfaces": [{"id": "inventory", "label": "Inventory", "metrics": metrics or [metric()]}],
    }


class PerformanceContractTests(unittest.TestCase):
    def test_project_specific_surfaces_and_metrics_are_valid(self):
        condor = validate_performance_contract(contract())
        brvtal = validate_performance_contract(
            contract("brvtal", [metric("asset_bytes", "bytes", 500_000, 800_000)])
        )
        self.assertEqual(condor["project"], "condor")
        self.assertEqual(condor["surfaces"][0]["metrics"][0]["budget"]["value"], 250)
        self.assertEqual(brvtal["surfaces"][0]["metrics"][0]["budget"]["value"], 800_000)
        self.assertNotEqual(canonical_performance_contract(condor), canonical_performance_contract(brvtal))

    def test_baseline_budget_window_freshness_and_evidence_are_required(self):
        for field in ("baseline", "budget", "window", "freshness", "evidence"):
            payload = contract()
            del payload["surfaces"][0]["metrics"][0][field]
            with self.subTest(field=field), self.assertRaises(PerformanceContractError):
                validate_performance_contract(payload)
        payload = contract()
        payload["surfaces"][0]["metrics"][0]["freshness"]["max_age_seconds"] = 0
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)

    def test_invalid_unknown_or_sensitive_input_fails_closed_without_echo(self):
        cases = []
        payload = contract(); payload["surfaces"][0]["metrics"][0]["extra"] = True; cases.append(payload)
        payload = contract(); payload["surfaces"][0]["metrics"][0]["baseline"]["value"] = float("nan"); cases.append(payload)
        payload = contract(); payload["surfaces"][0]["metrics"][0]["budget"]["unit"] = "s"; cases.append(payload)
        payload = contract(); payload["surfaces"][0]["metrics"][0]["baseline"]["observed_at"] = "2026-09-28T20:00:00"; cases.append(payload)
        secret = "token=supersecretvalue"
        payload = contract(); payload["surfaces"][0]["metrics"][0]["label"] = secret; cases.append(payload)
        for payload in cases:
            with self.subTest(payload=str(payload)[:40]), self.assertRaises(PerformanceContractError) as ctx:
                validate_performance_contract(payload)
            self.assertNotIn("supersecretvalue", str(ctx.exception))

    def test_actions_and_escalations_are_closed_deterministic_and_non_authorizing(self):
        payload = contract()
        first = validate_performance_contract(payload)
        reverse = copy.deepcopy(payload)
        reverse["surfaces"][0]["metrics"][0]["allowed_actions"].reverse()
        reverse["surfaces"][0]["metrics"][0]["escalation_conditions"].reverse()
        second = validate_performance_contract(reverse)
        self.assertEqual(first, second)
        self.assertNotIn("write_production", ALLOWED_ACTIONS)
        self.assertNotIn("change_authority", ALLOWED_ACTIONS)
        invalid = contract()
        invalid["surfaces"][0]["metrics"][0]["allowed_actions"] = ["write_production"]
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(invalid)

    def test_schema_validator_and_docs_share_contract_v1(self):
        schema = json.loads((ROOT / "performance" / "contract.schema.json").read_text())
        docs = (ROOT / "docs" / "performance-contract.md").read_text()
        self.assertEqual(schema["properties"]["version"]["const"], 1)
        self.assertEqual(set(schema["$defs"]["unit"]["enum"]), UNITS)
        self.assertEqual(set(schema["$defs"]["budget"]["properties"]["operator"]["enum"]), OPERATORS)
        metric_props = schema["$defs"]["metric"]["properties"]
        self.assertEqual(set(metric_props["allowed_actions"]["items"]["enum"]), ALLOWED_ACTIONS)
        self.assertEqual(set(metric_props["escalation_conditions"]["items"]["enum"]), ESCALATION_CONDITIONS)
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["metric"]["additionalProperties"])
        for issue in ("#311", "#312", "#313"):
            self.assertIn(issue, docs)
        self.assertIn("no concede autoridad", docs)


if __name__ == "__main__":
    unittest.main()
