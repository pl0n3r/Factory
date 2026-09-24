"""Regresiones del control de seguridad de Factory."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest


from seguridad.resiliencia import ValidationError, audit_workflow, validate_manifest


NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


def sample_manifest():
    return {
        "version": 1,
        "project": "pl0n3r/factory",
        "identities": {
            "ci": "github-app:factory-ci",
            "deploy": "github-app:factory-deploy",
            "observer": "github-app:factory-observer",
        },
        "checks": {
            key: {"verified_at": "2026-09-23T10:00:00Z", "evidence_ref": f"audit:{key}-20260923"}
            for key in ("repo_backup", "secrets_escrow", "token_rotation", "restore_drill")
        },
    }


class WorkflowSecurityTests(unittest.TestCase):
    def test_safe_sha_and_job_scoped_write(self):
        audit_workflow("""on:
  pull_request:
permissions:
  contents: read
jobs:
  publish:
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
      - uses: ./actions/local
""")

    def test_current_repository_workflows_are_auditable(self):
        root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        for path in sorted((*root.glob("*.yml"), *root.glob("*.yaml"))):
            with self.subTest(path=path.name):
                audit_workflow(path.read_text(encoding="utf-8"))

    def test_floating_action_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("steps:\n  - uses: actions/checkout@main\n")

    def test_untrusted_privileged_trigger_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("on:\n  pull_request_target:\n")

    def test_inline_privileged_trigger_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("on: [pull_request, pull_request_target]\n")

    def test_flow_privileged_trigger_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("on: {pull_request_target: {}}\n")

    def test_quoted_write_all_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow('permissions: "write-all"\n')

    def test_quoted_privileged_trigger_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("on:\n  'pull_request_target':\n")

    def test_scalar_privileged_trigger_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("on: pull_request_target\n")

    def test_list_privileged_trigger_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("on:\n  - pull_request_target\n")

    def test_permissions_alias_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("permissions: *write_permissions\n")

    def test_permissions_anchor_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("permissions: &write_permissions\n  contents: write\n")

    def test_folded_uses_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("steps:\n  - uses: >-\n      actions/checkout@main\n")

    def test_missing_uses_value_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("steps:\n  - uses:\n")

    def test_flow_global_write_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("permissions: {contents: write}\n")

    def test_global_write_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("permissions:\n  contents: write\njobs:\n  check:\n    steps: []\n")

    def test_write_all_rejected(self):
        with self.assertRaises(ValidationError):
            audit_workflow("permissions: write-all\n")


class RecoveryEvidenceTests(unittest.TestCase):
    def test_valid_evidence(self):
        validate_manifest(sample_manifest(), now=NOW)

    def test_distinct_identities(self):
        data = sample_manifest()
        data["identities"]["deploy"] = data["identities"]["ci"]
        with self.assertRaises(ValidationError):
            validate_manifest(data, now=NOW)

    def test_extra_secret_field_rejected(self):
        data = sample_manifest()
        data["checks"]["secrets_escrow"]["token"] = "never-commit-this"
        with self.assertRaises(ValidationError) as captured:
            validate_manifest(data, now=NOW)
        self.assertNotIn("never-commit-this", str(captured.exception))

    def test_missing_restore_evidence(self):
        data = sample_manifest()
        del data["checks"]["restore_drill"]
        with self.assertRaises(ValidationError):
            validate_manifest(data, now=NOW)

    def test_stale_restore_evidence(self):
        data = sample_manifest()
        data["checks"]["restore_drill"]["verified_at"] = "2025-01-01T00:00:00Z"
        with self.assertRaises(ValidationError):
            validate_manifest(data, now=NOW)

    def test_future_evidence(self):
        data = sample_manifest()
        data["checks"]["restore_drill"]["verified_at"] = (NOW + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.assertRaises(ValidationError):
            validate_manifest(data, now=NOW)

    def test_manifest_never_prints_json_on_invalid(self):
        data = sample_manifest()
        data["secret"] = "an-arbitrary-secret"
        with self.assertRaises(ValidationError) as captured:
            validate_manifest(data, now=NOW)
        self.assertNotIn("an-arbitrary-secret", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
