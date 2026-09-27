import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.codeql_sarif_summary import SUMMARY_PATH, main, summarize


def sarif(rule_id: str, severity: str, result: bool = True) -> dict:
    results = []
    if result:
        results.append(
            {
                "ruleId": rule_id,
                "ruleIndex": 0,
                "level": "warning",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": ".github/workflows/ci.yml"},
                            "region": {"startLine": 113},
                        }
                    }
                ],
            }
        )
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQL",
                        "rules": [
                            {
                                "id": rule_id,
                                "properties": {
                                    "tags": ["security"],
                                    "security-severity": severity,
                                },
                            }
                        ],
                    }
                },
                "results": results,
            }
        ],
    }


class CodeqlSarifSummaryTests(unittest.TestCase):
    def write(self, payload: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False, encoding="utf-8")
        with tmp:
            json.dump(payload, tmp)
        self.addCleanup(Path(tmp.name).unlink, missing_ok=True)
        return Path(tmp.name)

    def test_high_target_rule_is_blocking(self) -> None:
        path = self.write(sarif("actions/cache-poisoning/poisonable-step", "8.1"))
        summary = summarize([path], 7.0, {"actions/cache-poisoning/poisonable-step"})
        self.assertEqual(summary["high_or_critical_count"], 1)
        self.assertEqual(summary["required_zero_rule_count"], 1)
        self.assertEqual(summary["findings"][0]["location"], ".github/workflows/ci.yml:113")

    def test_medium_unrelated_rule_is_not_blocking(self) -> None:
        path = self.write(sarif("actions/example", "6.9"))
        summary = summarize([path], 7.0, {"actions/cache-poisoning/poisonable-step"})
        self.assertEqual(summary["high_or_critical_count"], 0)
        self.assertEqual(summary["required_zero_rule_count"], 0)

    def test_empty_runs_is_rejected_as_incomplete_evidence(self) -> None:
        path = self.write({"version": "2.1.0", "runs": []})
        with self.assertRaisesRegex(ValueError, "no analysis runs"):
            summarize([path], 7.0, {"actions/cache-poisoning/poisonable-step"})

    def test_run_without_tool_driver_name_is_rejected(self) -> None:
        path = self.write({"version": "2.1.0", "runs": [{}]})
        with self.assertRaisesRegex(ValueError, "no tool driver name"):
            summarize([path], 7.0, {"actions/cache-poisoning/poisonable-step"})

    def test_run_without_results_array_is_rejected(self) -> None:
        payload = sarif("actions/example", "6.9", result=False)
        payload["runs"][0].pop("results")
        path = self.write(payload)
        with self.assertRaisesRegex(ValueError, "no results array"):
            summarize([path], 7.0, {"actions/cache-poisoning/poisonable-step"})

    def test_nested_rule_id_is_blocking_without_rule_id_or_index(self) -> None:
        payload = sarif("actions/cache-poisoning/poisonable-step", "8.1")
        result = payload["runs"][0]["results"][0]
        result.pop("ruleId")
        result.pop("ruleIndex")
        result["rule"] = {"id": "actions/cache-poisoning/poisonable-step"}
        path = self.write(payload)
        summary = summarize([path], 7.0, {"actions/cache-poisoning/poisonable-step"})
        self.assertEqual(summary["high_or_critical_count"], 1)
        self.assertEqual(summary["required_zero_rule_count"], 1)

    def test_zero_results_is_valid_evidence(self) -> None:
        path = self.write(sarif("actions/cache-poisoning/poisonable-step", "8.1", result=False))
        summary = summarize([path], 7.0, {"actions/cache-poisoning/poisonable-step"})
        self.assertEqual(summary["analysis_run_count"], 1)
        self.assertEqual(summary["result_count"], 0)
        self.assertEqual(summary["required_zero_rule_count"], 0)

    def test_main_uses_fixed_evidence_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "codeql-results"
            evidence.mkdir()
            (evidence / "actions.sarif").write_text(
                json.dumps(sarif("actions/example", "6.9", result=False)),
                encoding="utf-8",
            )
            with patch("scripts.codeql_sarif_summary.SARIF_DIR", evidence), \
                 patch("scripts.codeql_sarif_summary.SUMMARY_PATH", evidence / "summary.json"), \
                 patch("sys.argv", ["codeql_sarif_summary.py"]):
                self.assertEqual(main(), 0)
            self.assertTrue((evidence / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
