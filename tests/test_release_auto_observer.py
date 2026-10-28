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
    trusted = {
        "Validar": {"slug": "github-actions", "id": 15368},
        "SonarCloud Code Analysis": {"slug": "sonarqubecloud", "id": 12526},
        "CodeQL": {"slug": "github-advanced-security", "id": 57789},
    }
    checks = [
        {"name": n, "id": idx + 1, "head_sha": SHA, "status": "completed",
         "conclusion": "success", "app": trusted[n].copy()}
        for idx, n in enumerate(("Validar", "SonarCloud Code Analysis", "CodeQL"))
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
        self.assertIn('TRIGGERING_ACTOR: ${{ github.triggering_actor }}', wf)
        self.assertIn('test "$TRIGGERING_ACTOR" = "$OWNER"', wf)
        self.assertIn('REF: ${{ github.ref }}', wf)
        self.assertIn('test "$REF" = refs/heads/main', wf)
        self.assertNotIn('github.ref_name', wf)
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


    def test_marker_parser_is_strict_about_duplicates_and_json(self):
        from scripts.release_auto_observer import _marker

        name = "factory-human-decision"
        valid = '<!-- factory-human-decision {"version":2,"option":"A"} -->'
        self.assertEqual({"version": 2, "option": "A"}, _marker(valid, name))
        for invalid in (
            None, "", 5, valid + "\n" + valid,
            "<!-- factory-human-decision {invalid json} -->",
            '<!-- factory-human-decision {"option":"A"} -->\n<!-- factory-human-decision {} -->',
            '<!-- wrong-marker {"version":2} -->',
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(_marker(invalid, name))

    def test_strict_check_evidence_rejects_incomplete_and_wrong_types(self):
        from scripts.release_auto_observer import _latest_checks

        self.assertEqual(3, len(_latest_checks(fixture(), SHA)))
        for pages in (
            None, [], {}, [None], [{"total_count": "3", "check_runs": []}],
            [{"total_count": 4, "check_runs": []}],
            [{"total_count": -1, "check_runs": []}],
            [{"total_count": 3, "check_runs": None}],
            [{"total_count": 3, "check_runs": [False] * 3}],
            [{"total_count": 3, "check_runs": [{"name": 4}] * 3}],
            [{"total_count": 0, "check_runs": []}] * 5,
            [{"total_count": 3, "check_runs": fixture()["checks"][0]["check_runs"][:-1]}],
        ):
            with self.subTest(pages=repr(pages)[:90]):
                case = fixture()
                case["checks"] = pages
                self.assertIsNone(_latest_checks(case, SHA))
                self.assertEqual("BLOCKED", evaluate_bundle(case)["state"])

        for key, value in (("id", "invalid"), ("head_sha", "not-sha"),
                           ("app", None), ("app", {"slug": "github-actions", "id": 0}),
                           ("app", {"slug": "untrusted", "id": 15368}),
                           ("app", {"slug": "github-actions", "id": True})):
            case = fixture()
            case["checks"][0]["check_runs"][0][key] = value
            self.assertIsNone(_latest_checks(case, SHA))

    def test_paginated_check_evidence_and_latest_identity(self):
        from scripts.release_auto_observer import _latest_checks

        data = fixture()
        rows = data["checks"][0]["check_runs"]
        newer = {**rows[0], "id": 100, "status": "completed", "conclusion": "failure"}
        data["checks"] = [
            {"total_count": 4, "check_runs": rows[:2]},
            {"total_count": 4, "check_runs": [rows[2], newer]},
        ]
        normalized = _latest_checks(data, SHA)
        self.assertEqual(3, len(normalized))
        self.assertEqual("failure", next(v for v in normalized if v["name"] == "Validar")["conclusion"])
        self.assertEqual("BLOCKED", evaluate_bundle(data)["state"])
        data["checks"][1]["total_count"] = 5
        self.assertIsNone(_latest_checks(data, SHA))

        # Un ID repetido, incluso entre páginas, nunca es una reejecución válida.
        repeated = fixture()
        original = repeated["checks"][0]["check_runs"]
        repeated["checks"] = [
            {"total_count": 4, "check_runs": original},
            {"total_count": 4, "check_runs": [{**original[0], "conclusion": "failure"}]},
        ]
        self.assertIsNone(_latest_checks(repeated, SHA))
        self.assertEqual("BLOCKED", evaluate_bundle(repeated)["state"])

        # La evidencia SARIF auxiliar no sustituye el check CodeQL real.
        different = fixture()
        real = different["checks"][0]["check_runs"]
        other = {**real[2], "id": 99, "name": "CodeQL Actions SARIF",
                 "app": {"slug": "github-actions", "id": 15368},
                 "conclusion": "failure"}
        different["checks"] = [{"total_count": 4, "check_runs": real + [other]}]
        checks = _latest_checks(different, SHA)
        self.assertEqual("success", next(c for c in checks if c["name"] == "CodeQL")["conclusion"])
        real[2]["name"] = "CodeQL Actions SARIF"
        self.assertIsNone(_latest_checks(different, SHA))

    def test_collector_rejects_bad_inputs_and_handles_check_pagination(self):
        from scripts.release_auto_observer import collect

        for issue, sha in (("", SHA), ("0", SHA), ("../secrets", SHA), ("1595", "bad")):
            with self.subTest(issue=issue):
                with self.assertRaises(ValueError):
                    collect(issue, sha)

        values = [
            fixture()["main"], fixture()["tag"], fixture()["gate"],
            fixture()["comments"], fixture()["switch"], fixture()["rate"],
            {"total_count": 4, "check_runs": [{"id": 1}, {"id": 2}]},
            {"total_count": 4, "check_runs": [{"id": 3}, {"id": 4}]},
        ]
        with patch("scripts.release_auto_observer._get", side_effect=values) as get:
            result = collect("1595", SHA)
            self.assertEqual(2, len(result["checks"]))
            self.assertEqual(8, get.call_count)
            self.assertEqual("/rate_limit", get.call_args_list[5].args[0])
            self.assertTrue(get.call_args_list[-1].args[0].endswith("&page=2"))

    def test_cli_stays_blocked_when_sources_are_missing_or_fail(self):
        import contextlib
        import io

        from scripts.release_auto_observer import main

        good_env = {
            "GITHUB_REPOSITORY": "pl0n3r/Factory",
            "GITHUB_SHA": SHA,
            "RELEASE_GATE_ISSUE": "1595",
        }
        for changes, error in (
            ({"GITHUB_REPOSITORY": "other/repo"}, None),
            ({}, OSError("offline")),
        ):
            with self.subTest(changes=changes):
                with patch.dict("os.environ", {**good_env, **changes}, clear=True):
                    with patch("scripts.release_auto_observer.collect", side_effect=error):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            self.assertEqual(0, main())
                        result = json.loads(stdout.getvalue())
                        self.assertEqual("BLOCKED", result["state"])
                        self.assertEqual(0, result["mutations"])
                        self.assertFalse(result["authorizes_release"])

        with patch.dict("os.environ", good_env, clear=True):
            with patch("scripts.release_auto_observer.collect", return_value=fixture()):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(0, main())
                report = json.loads(stdout.getvalue())
                self.assertEqual("security_freeze_or_protected_tag_not_attested", report["reason"])
                self.assertNotIn("comments", report)


if __name__ == "__main__":
    unittest.main()
