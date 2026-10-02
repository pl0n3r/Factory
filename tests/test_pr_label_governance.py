#!/usr/bin/env python3
import json
import unittest

from scripts.pr_label_governance import (
    GITHUB_ACTIONS_INTEGRATION_ID,
    REQUIRED_CONTEXT,
    RULESET_TARGET_REPOSITORIES,
    audit_repository,
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


if __name__ == "__main__":
    unittest.main()
