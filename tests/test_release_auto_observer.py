"""Regresiones del observador manual Factory: ninguna fuente o test publica."""
from __future__ import annotations

import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.release_auto_observer import collect, evaluate_bundle

SHA = "a" * 40
TAG = "b" * 40
GATE_MARKER = '{"category":"factory-release"}'
WINDOW_MARKER = '{"version":1,"sha":"' + SHA + '"}'


def fixture() -> dict:
    checks = [
        {"name": n, "id": idx + 1, "head_sha": SHA, "status": "completed",
         "conclusion": "success"}
        for idx, n in enumerate(("Validar", "SonarCloud Code Analysis", "CodeQL Actions SARIF"))
    ]
    return {
        "repository": "pl0n3r/Factory", "checkout_sha": SHA,
        "main": {"name": "main", "protected": True, "commit": {"sha": SHA}},
        "tag": {"ref": "refs/tags/v1", "object": {"type": "commit", "sha": TAG}},
        "rate": {"resources": {"core": {"remaining": 2000, "limit": 5000}}},
        "switch": {"number": 767, "state": "closed", "user": {"login": "pl0n3r"},
                   "body": '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'},
        "gate": {"state": "closed", "body":
                 "<!-- factory-human-gate " + GATE_MARKER + " -->\n"
                 "<!-- factory-release-window " + WINDOW_MARKER + " -->"},
        "comments": [
            {"user": {"login": "pl0n3r"}, "author_association": "OWNER", "body": "/decidir A"},
            {"user": {"login": "github-actions[bot]"},
             "body": '<!-- factory-human-decision {"version":2,"option":"A","gate_sha256":"' +
                     "c" * 64 + '"} -->'},
        ],
        "checks": [{"total_count": 3, "check_runs": checks}],
    }


class ReleaseAutoObserverTests(unittest.TestCase):
    def test_fails_closed_on_incomplete_authentication_and_wrong_sha(self):
        cases = [
            ("repository", "otro/repo"),
            ("checkout_sha", TAG),
            ("main", {"name": "main", "protected": True, "commit": {"sha": TAG}}),
            ("tag", {"ref": "refs/tags/v1", "object": {"type": "tag", "sha": TAG}}),
            ("switch", {"number": 767, "state": "closed", "user": {"login": "pl0n3r"}, "body": ""}),
            ("gate", {"state": "closed", "body": ""}),
            ("comments", []),
            ("checks", [{"total_count": 4, "check_runs": fixture()["checks"][0]["check_runs"]}]),
            ("rate", {"resources": {"core": {"remaining": 3, "limit": 5000}}}),
        ]
        for name, value in cases:
            with self.subTest(name=name):
                case = fixture()
                case[name] = value
                out = evaluate_bundle(case)
                self.assertEqual("BLOCKED", out["state"])
                self.assertFalse(out["authorizes_release"])
                self.assertEqual(0, out["mutations"])
                self.assertNotEqual("security_freeze_or_protected_tag_not_attested", out["reason"])
        self.assertEqual("evidence_missing", evaluate_bundle(None)["reason"])
        self.assertEqual("evidence_missing", evaluate_bundle({})["reason"])

    def test_read_only_api_budget_and_no_write_permission(self):
        wf = (Path(__file__).resolve().parents[1] /
              ".github/workflows/release-auto-observador.yml").read_text()
        self.assertIn("contents: read", wf)
        self.assertIn("checks: read", wf)
        self.assertIn("issues: read", wf)
        for forbidden in ("contents: write", "issues: write", "actions: write",
                          "pull-requests: write", "packages: write",
                          "gh release create", "gh api -X POST", "git push"):
            self.assertNotIn(forbidden, wf)
        with patch("scripts.release_auto_observer.subprocess.run") as proc:
            proc.return_value.stdout = json.dumps({"ok": True})
            collect("1595", SHA)
            self.assertTrue(proc.call_args_list)
            for call in proc.call_args_list:
                cmd = call.args[0]
                self.assertEqual(["gh", "api", "-X", "GET"], cmd[:4])
                self.assertTrue(cmd[4].startswith(("/repos/pl0n3r/Factory/", "/rate_limit")))
        for change in (0, 9, -1, "2000", None):
            case = fixture()
            case["rate"]["resources"]["core"]["remaining"] = change
            self.assertEqual("BLOCKED", evaluate_bundle(case)["state"])

    def test_manual_dispatch_only_and_no_release_authority(self):
        wf = (Path(__file__).resolve().parents[1] /
              ".github/workflows/release-auto-observador.yml").read_text()
        self.assertIn("workflow_dispatch:", wf)
        self.assertNotIn("\n  schedule:", wf)
        self.assertNotIn("\n  push:", wf)
        self.assertNotIn("\n  workflow_run:", wf)
        self.assertIn('ACTOR', wf)
        self.assertIn('OWNER', wf)
        self.assertIn('DEFAULT_BRANCH', wf)
        for case in (fixture(), {"bad": True}):
            out = evaluate_bundle(case)
            self.assertFalse(out["authorizes_release"])
            self.assertEqual(0, out["mutations"])
            self.assertEqual(0, out["tag_writes"])

    def test_stable_report_against_synthetic_fixtures(self):
        case = fixture()
        saved = copy.deepcopy(case)
        result = evaluate_bundle(case)
        self.assertEqual("BLOCKED", result["state"])
        self.assertEqual("security_freeze_or_protected_tag_not_attested",
                         result["reason"])
        self.assertEqual(case, saved)
        for _ in range(5):
            self.assertEqual(result, evaluate_bundle(case))
        case["comments"][0]["body"] = "/decidir B"
        self.assertEqual("human_release_authority_unverified",
                         evaluate_bundle(case)["reason"])


if __name__ == "__main__":
    unittest.main()
