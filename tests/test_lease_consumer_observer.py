"""Contrato de observación local V3: solo GET y ninguna autorización."""
from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.lease_auto_release_integration import (
    _GhReadOnlyAPI, IntegrationPreview, local_active_issue_ids,
    observe_issue_cli,
)

ROOT = Path(__file__).resolve().parents[1]


class LeaseConsumerObserverTests(unittest.TestCase):
    def test_repository_identity_is_bound_to_local_caller(self):
        repo = "pl0n3r/ControlBot"
        preview = IntegrationPreview(837, "read_only", "wait", "protected_or_active_work")
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": repo}):
            with patch.object(
                _GhReadOnlyAPI, "request",
                return_value={"id": 203, "full_name": repo},
            ) as request:
                with patch("scripts.lease_github_port.LeaseGithubPort") as port:
                    with patch(
                        "scripts.lease_auto_release_integration.preview_integrated_activity",
                        return_value=preview,
                    ):
                        result = observe_issue_cli(837)
        self.assertIs(result, preview)
        request.assert_called_once_with("GET", "/repos/pl0n3r/ControlBot")
        self.assertIs(port.call_args.kwargs["armed"], False)
        self.assertEqual(port.call_args.kwargs["concurrency_group"],
                         "factory-coordination-203")
        self.assertFalse(result.release_authorized)
        for untrusted in ("attacker/ControlBot", "pl0n3r/UNKNOWN",
                          "pl0n3r/ControlBot/other"):
            with self.subTest(untrusted=untrusted):
                with patch.dict(os.environ, {"GITHUB_REPOSITORY": untrusted}):
                    self.assertEqual(observe_issue_cli(837).state, "UNKNOWN")

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": repo}):
            with patch.object(
                _GhReadOnlyAPI, "request",
                return_value={"id": 203, "full_name": "pl0n3r/Factory"},
            ):
                self.assertEqual(observe_issue_cli(837).state, "UNKNOWN")

    def test_get_only_local_token_denies_mutations_and_unknown_sources(self):
        api = _GhReadOnlyAPI("pl0n3r/brvtal")
        with patch("subprocess.run") as run:
            run.return_value.stdout = "{}"
            result = api.request("GET", "/repos/pl0n3r/brvtal")
            self.assertEqual(result, {})
            api.request("GET", "/repos/pl0n3r/Factory/issues/767")
            self.assertEqual(run.call_count, 2)
            for method, path in (
                ("POST", "/repos/pl0n3r/brvtal/issues"),
                ("PATCH", "/repos/pl0n3r/brvtal/issues/9"),
                ("DELETE", "/repos/pl0n3r/brvtal/issues/9"),
                ("GET", "/repos/pl0n3r/Factory/issues/1382"),
                ("GET", "/repos/pl0n3r/Condor"),
                ("GET", "/repos/pl0n3r/brvtal/../../secrets"),
                ("GET", "/repos/pl0n3r/brvtal/issues?state=open"),
                ("GET", "https://api.github.com/repos/pl0n3r/brvtal"),
            ):
                with self.subTest(method=method, path=path):
                    with self.assertRaises(PermissionError):
                        api.request(method, path)
            self.assertEqual(run.call_count, 2)
        with self.assertRaises(PermissionError):
            _GhReadOnlyAPI("outside/repository")

        a = {"number": 9, "state": "open",
             "labels": [{"name": "status: in review"}]}
        b = {"number": 12, "state": "open",
             "labels": [{"name": "estado: reservado"}]}
        self.assertEqual(local_active_issue_ids([[a, b]], "pl0n3r/brvtal"),
                         [9, 12])
        self.assertIsNone(local_active_issue_ids([[a, a]], "pl0n3r/brvtal"))
        self.assertIsNone(local_active_issue_ids([[a]], "outsider/repo"))
        self.assertIsNone(local_active_issue_ids([[{"number": 1}]],
                                                  "pl0n3r/Factory"))
        self.assertIsNone(local_active_issue_ids([], "pl0n3r/Factory"))
        self.assertEqual(local_active_issue_ids([[{
            "number": 1, "state": "open", "labels": [],
        }]], "pl0n3r/Factory"), [])

    def test_scheduled_caller_template_is_read_only_and_off(self):
        caller = (ROOT / "template/.github/workflows/"
                  "observador-reservas-consumidor.yml").read_text()
        reusable = (ROOT / ".github/workflows/"
                    "observador-reservas-consumidor.yml").read_text()
        self.assertIn("workflow_call:", reusable)
        self.assertIn("schedule:", caller)
        # No usar la misma clave en caller y reusable; bloquearía el subworkflow.
        self.assertIn("group: lease-consumer-caller-${{ github.repository_id }}", caller)
        self.assertNotIn("group: factory-coordination-${{ github.repository_id }}", caller)
        self.assertIn("group: factory-coordination-${{ github.repository_id }}", reusable)
        self.assertIn("uses: pl0n3r/Factory/.github/workflows/"
                      "observador-reservas-consumidor.yml@v1", caller)
        for document in (caller, reusable):
            self.assertIn("contents: read", document)
            self.assertIn("issues: read", document)
            self.assertIn("checks: read", document)
            self.assertNotIn("issues: write", document)
            self.assertNotIn("pull-requests: write", document)
            self.assertNotIn("contents: write", document)
            self.assertNotIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'true'",
                             document)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'",
                      reusable)
        self.assertIn("release_authorized", reusable)
        self.assertIn("terminal_certified", reusable)
        self.assertIn("upload-artifact@", reusable)

    def test_phase_a_artifacts_never_enable_mutation(self):
        valid = IntegrationPreview(9, "read_only", "wait",
                                   "protected_or_active_work", 1,
                                   "issue_comment")
        for preview in (valid, IntegrationPreview(9, "UNKNOWN", "unknown",
                                                  "inactivity_not_proven")):
            self.assertFalse(preview.release_authorized)
            self.assertFalse(preview.lock_verified)
            self.assertFalse(preview.cas_verified)
        workflow = (ROOT / ".github/workflows/"
                    "observador-reservas-consumidor.yml").read_text()
        self.assertIn("mutations: 0", workflow)
        self.assertIn("release_authorized: false", workflow)
        self.assertIn("terminal_certified: false", workflow)
        self.assertNotIn("gh api --method", workflow)
        self.assertNotIn("gh issue edit", workflow)
        self.assertNotIn("gh pr merge", workflow)


if __name__ == "__main__":
    unittest.main()
