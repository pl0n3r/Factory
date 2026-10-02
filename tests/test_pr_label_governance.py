#!/usr/bin/env python3
import io
import json
import sys
import unittest
from unittest.mock import patch

from scripts.pr_label_governance import (
    GITHUB_ACTIONS_INTEGRATION_ID,
    GovernanceError,
    REQUIRED_CONTEXT,
    RULESET_TARGET_REPOSITORIES,
    _audit_document,
    audit_repository,
    main,
    merged_pr_alert_plan,
    owner_commands,
    uniform_ruleset_payload,
)


class PrLabelGovernanceTests(unittest.TestCase):
    def test_audit_classifies_required_etiquetas_or_unknown(self):
        grindflow = audit_repository(
            "GrindFlow",
            rulesets=[
                {
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                    "rules": [
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "Etiquetas", "integration_id": 15368},
                                    {"context": "validate", "integration_id": 15368},
                                ]
                            },
                        }
                    ],
                }
            ],
            branch_protection=None,
        )
        self.assertEqual(grindflow["status"], "required")
        self.assertIn("Etiquetas", grindflow["observed_contexts"])

        condor = audit_repository(
            "Condor",
            rulesets=[
                {
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                    "rules": [
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "Validar", "integration_id": 15368},
                                    {"context": "SonarCloud Code Analysis", "integration_id": 12526},
                                ]
                            },
                        }
                    ],
                }
            ],
            branch_protection=None,
        )
        self.assertEqual(condor["status"], "unknown")
        self.assertFalse(condor["branch_protection_visible"])

        factory_runner = audit_repository(
            "FactoryRunner",
            rulesets=[],
            branch_protection={"required_status_checks": {"contexts": [], "checks": []}},
        )
        self.assertEqual(factory_runner["status"], "missing")

    def test_uniform_ruleset_payload_and_owner_commands(self):
        payload = uniform_ruleset_payload()
        self.assertEqual(payload["name"], "factory-required-labels")
        self.assertEqual(payload["target"], "branch")
        self.assertEqual(payload["enforcement"], "active")
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        parameters = payload["rules"][0]["parameters"]
        self.assertFalse(parameters["strict_required_status_checks_policy"])
        checks = parameters["required_status_checks"]
        self.assertEqual(
            checks,
            [{"context": REQUIRED_CONTEXT, "integration_id": GITHUB_ACTIONS_INTEGRATION_ID}],
        )
        commands = owner_commands()
        self.assertIn("ruleset-payload", commands[0])
        self.assertEqual(len(commands), len(RULESET_TARGET_REPOSITORIES) + 1)
        for repository in RULESET_TARGET_REPOSITORIES:
            self.assertTrue(any(f"repos/pl0n3r/{repository}/rulesets" in command for command in commands))
        self.assertFalse(any("repos/pl0n3r/GrindFlow/rulesets" in command for command in commands))
        self.assertFalse(any("PATCH" in command or "DELETE" in command for command in commands))
        json.dumps(payload)

    def test_merged_pr_with_failed_etiquetas_emits_single_alert(self):
        document = {
            "pr": {
                "number": 82,
                "merged_at": "2026-10-02T05:49:45Z",
                "head": {"sha": "2fd240f570c41e21f8089bcc0862c363695c11bb"},
            },
            "check_runs": [
                {
                    "id": 110721665380,
                    "name": "validar-pr / Labels",
                    "status": "completed",
                    "conclusion": "failure",
                    "started_at": "2026-10-02T05:40:05Z",
                    "completed_at": "2026-10-02T05:40:09Z",
                    "details_url": "https://github.com/pl0n3r/FactoryRunner/actions/runs/36969956948/job/110721665380",
                }
            ],
            "comments": [],
        }
        first = merged_pr_alert_plan(document)
        self.assertEqual(first["action"], "create")
        self.assertIn("pr=82", first["body"])
        self.assertIn("`failure`", first["body"])

        document["comments"] = [{"body": first["body"]}]
        second = merged_pr_alert_plan(document)
        self.assertEqual(second, {"action": "noop", "reason": "already_alerted", "pr": 82})

    def test_later_success_suppresses_old_failure(self):
        document = {
            "pr": {
                "number": 10,
                "merged_at": "2026-10-02T05:49:45Z",
                "head": {"sha": "a" * 40},
            },
            "check_runs": [
                {
                    "id": 1,
                    "name": "validar-pr / Labels",
                    "status": "completed",
                    "conclusion": "failure",
                    "completed_at": "2026-10-02T05:40:09Z",
                },
                {
                    "id": 2,
                    "name": "validar-pr / Labels",
                    "status": "completed",
                    "conclusion": "success",
                    "completed_at": "2026-10-02T05:41:09Z",
                },
            ],
            "comments": [],
        }
        self.assertEqual(
            merged_pr_alert_plan(document),
            {"action": "noop", "reason": "label_check_green", "pr": 10},
        )

    def test_audit_handles_visible_sources_and_rejects_malformed_evidence(self):
        protected = audit_repository(
            "Factory",
            rulesets=[
                {
                    "target": "tag",
                    "enforcement": "active",
                    "rules": [],
                },
                {
                    "target": "branch",
                    "enforcement": "disabled",
                    "rules": [],
                },
                {
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {"ref_name": {"include": ["refs/heads/release"]}},
                    "rules": [],
                },
            ],
            branch_protection={
                "required_status_checks": {
                    "contexts": ["Validar"],
                    "checks": [{"context": "Etiquetas"}],
                }
            },
        )
        self.assertEqual(protected["status"], "required")
        self.assertEqual(protected["observed_contexts"], ["Etiquetas", "Validar"])

        unknown = audit_repository(
            "AutoFactory",
            rulesets=None,
            branch_protection={"required_status_checks": None},
        )
        self.assertEqual(unknown["status"], "unknown")
        self.assertFalse(unknown["rulesets_visible"])
        self.assertTrue(unknown["branch_protection_visible"])

        with self.assertRaises(GovernanceError):
            audit_repository("unknown", rulesets=[], branch_protection={})
        with self.assertRaises(GovernanceError):
            audit_repository("Factory", rulesets={}, branch_protection={})
        with self.assertRaises(GovernanceError):
            audit_repository("Factory", rulesets=[None], branch_protection={})
        with self.assertRaises(GovernanceError):
            audit_repository("Factory", rulesets=[], branch_protection=[])
        with self.assertRaises(GovernanceError):
            audit_repository(
                "Factory",
                rulesets=[],
                branch_protection={"required_status_checks": []},
            )
        ignored_rule = audit_repository(
            "Factory",
            rulesets=[{
                "target": "branch",
                "enforcement": "active",
                "rules": [None],
            }],
            branch_protection={},
        )
        self.assertEqual(ignored_rule["status"], "missing")
        with self.assertRaises(GovernanceError):
            audit_repository(
                "Factory",
                rulesets=[{
                    "target": "branch",
                    "enforcement": "active",
                    "rules": [{
                        "type": "required_status_checks",
                        "parameters": {"required_status_checks": {}},
                    }],
                }],
                branch_protection={},
            )

    def test_owner_commands_and_audit_document_fail_closed(self):
        with self.assertRaises(GovernanceError):
            owner_commands(["Factory", "not-a-repo"])
        with self.assertRaises(GovernanceError):
            _audit_document([])
        with self.assertRaises(GovernanceError):
            _audit_document({"repositories": [None]})
        with self.assertRaises(GovernanceError):
            _audit_document({
                "repositories": [{
                    "name": "Factory",
                    "rulesets": [],
                    "branch_protection": {},
                    "extra": True,
                }]
            })

        result = _audit_document({
            "repositories": [{
                "name": "Factory",
                "rulesets": [],
                "branch_protection": {
                    "required_status_checks": {
                        "contexts": ["Etiquetas"],
                        "checks": [],
                    }
                },
            }]
        })
        self.assertEqual(result[0]["status"], "required")

    def test_alert_plan_validates_inputs_and_noop_states(self):
        base = {
            "pr": {
                "number": 7,
                "merged_at": "2026-10-02T05:49:45Z",
                "head": {"sha": "a" * 40},
            },
            "check_runs": [],
            "comments": [],
        }
        with self.assertRaises(GovernanceError):
            merged_pr_alert_plan(None)
        with self.assertRaises(GovernanceError):
            merged_pr_alert_plan({"pr": {}, "check_runs": []})
        for bad_pr in (None, {"number": True, "head": {"sha": "a" * 40}}, {"number": 0, "head": {"sha": "a" * 40}}):
            document = dict(base)
            document["pr"] = bad_pr
            with self.assertRaises(GovernanceError):
                merged_pr_alert_plan(document)
        for bad_head in (None, {}, {"sha": "short"}):
            document = dict(base)
            document["pr"] = {
                "number": 7,
                "merged_at": "2026-10-02T05:49:45Z",
                "head": bad_head,
            }
            with self.assertRaises(GovernanceError):
                merged_pr_alert_plan(document)

        not_merged = json.loads(json.dumps(base))
        not_merged["pr"]["merged_at"] = None
        self.assertEqual(
            merged_pr_alert_plan(not_merged),
            {"action": "noop", "reason": "not_merged", "pr": 7},
        )
        self.assertEqual(
            merged_pr_alert_plan(base),
            {"action": "noop", "reason": "no_label_check", "pr": 7},
        )

        pending = json.loads(json.dumps(base))
        pending["check_runs"] = [{"name": "Labels", "status": "in_progress"}]
        self.assertEqual(
            merged_pr_alert_plan(pending),
            {"action": "noop", "reason": "label_check_not_terminal", "pr": 7},
        )

        green = json.loads(json.dumps(base))
        green["check_runs"] = [{
            "id": 2,
            "name": "Etiquetas",
            "status": "completed",
            "conclusion": "success",
            "started_at": "2026-10-02T05:40:00Z",
        }]
        self.assertEqual(
            merged_pr_alert_plan(green),
            {"action": "noop", "reason": "label_check_green", "pr": 7},
        )

        with self.assertRaises(GovernanceError):
            oversized = json.loads(json.dumps(base))
            oversized["check_runs"] = [None] * 501
            merged_pr_alert_plan(oversized)

    def test_alert_plan_accepts_label_name_variants_and_fallback_fields(self):
        for name in ("Etiquetas", "Labels", "validar-pr / Labels"):
            with self.subTest(name=name):
                document = {
                    "pr": {
                        "number": 9,
                        "merged_at": "2026-10-02T05:49:45Z",
                        "head": {"sha": "b" * 40},
                    },
                    "check_runs": [
                        {"name": "not-labels", "status": "completed", "conclusion": "failure"},
                        {
                            "name": name,
                            "status": "completed",
                            "conclusion": None,
                            "completed_at": None,
                            "started_at": None,
                            "id": None,
                            "details_url": None,
                        },
                    ],
                    "comments": [None, {"body": 123}],
                }
                result = merged_pr_alert_plan(document)
                self.assertEqual(result["action"], "create")
                self.assertIn("unknown", result["body"])
                self.assertIn("sin details_url", result["body"])

    def test_cli_commands_and_error_path(self):
        cases = [
            (["pr_label_governance.py", "ruleset-payload"], "", "factory-required-labels"),
            (["pr_label_governance.py", "owner-commands"], "", "commands"),
            (
                ["pr_label_governance.py", "audit"],
                json.dumps({
                    "repositories": [{
                        "name": "Factory",
                        "rulesets": [],
                        "branch_protection": {
                            "required_status_checks": {
                                "contexts": ["Etiquetas"],
                                "checks": [],
                            }
                        },
                    }]
                }),
                "repositories",
            ),
            (
                ["pr_label_governance.py", "alert-plan"],
                json.dumps({
                    "pr": {"number": 1, "merged_at": None, "head": {"sha": "c" * 40}},
                    "check_runs": [],
                    "comments": [],
                }),
                "not_merged",
            ),
        ]
        for argv, stdin, expected in cases:
            with self.subTest(argv=argv):
                output = io.StringIO()
                with patch.object(sys, "argv", argv), patch.object(sys, "stdin", io.StringIO(stdin)), patch.object(sys, "stdout", output):
                    self.assertEqual(main(), 0)
                self.assertIn(expected, output.getvalue())

        error = io.StringIO()
        with patch.object(sys, "argv", ["pr_label_governance.py", "audit"]), patch.object(sys, "stdin", io.StringIO("{")), patch.object(sys, "stderr", error):
            self.assertEqual(main(), 2)
        self.assertIn("ERROR:", error.getvalue())


if __name__ == "__main__":
    unittest.main()
