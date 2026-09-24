"""Regresiones del control de seguridad de Factory."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest


from seguridad.resiliencia import (
    ValidationError,
    audit_workflow,
    validate_legacy_manifest,
    validate_manifest,
)


NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


def recovery_checks():
    return {
        key: {
            "verified_at": "2026-09-23T10:00:00Z",
            "evidence_ref": f"audit:{key}-20260923",
        }
        for key in ("repo_backup", "secrets_escrow", "token_rotation", "restore_drill")
    }


def sample_manifest():
    return {
        "version": 2,
        "project": "pl0n3r/factory",
        "execution_mechanisms": {
            "ci": "github-token:ephemeral",
            "observer": "github-token:ephemeral",
            "deploy": "hostinger:git",
        },
        "cross_repo_write": {"required_mechanism": "github-app"},
        "checks": recovery_checks(),
    }


def sample_legacy_manifest():
    return {
        "version": 1,
        "project": "pl0n3r/factory",
        "identities": {
            "ci": "github-app:factory-ci",
            "deploy": "github-app:factory-deploy",
            "observer": "github-app:factory-observer",
        },
        "checks": recovery_checks(),
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
    def test_v2_uses_owner_approved_capability_model(self):
        data = sample_manifest()
        validate_manifest(data, now=NOW)

        data["cross_repo_write"] = {
            "required_mechanism": "github-token:ephemeral"
        }
        with self.assertRaisesRegex(ValidationError, "GitHub App dedicada"):
            validate_manifest(data, now=NOW)

    def test_v2_rejects_unapproved_mechanism_or_secret_without_leak(self):
        unapproved = sample_manifest()
        unapproved["execution_mechanisms"]["ci"] = "pat:never-print-this"
        with self.assertRaises(ValidationError) as captured:
            validate_manifest(unapproved, now=NOW)
        self.assertNotIn("never-print-this", str(captured.exception))

        extra = sample_manifest()
        extra["execution_mechanisms"]["token"] = "another-secret"
        with self.assertRaises(ValidationError) as captured:
            validate_manifest(extra, now=NOW)
        self.assertNotIn("another-secret", str(captured.exception))

    def test_v1_is_migration_only_and_still_validates_recovery_age(self):
        legacy = sample_legacy_manifest()
        with self.assertRaisesRegex(ValidationError, "v1 obsoleto"):
            validate_manifest(legacy, now=NOW)

        validate_legacy_manifest(legacy, now=NOW)
        legacy["checks"]["restore_drill"]["verified_at"] = "2025-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValidationError, "evidencia vencida o futura"):
            validate_legacy_manifest(legacy, now=NOW)

    def test_runbook_matches_current_capability_model(self):
        runbook = (
            Path(__file__).resolve().parents[1] / "docs" / "resiliencia-fabrica.md"
        ).read_text(encoding="utf-8")
        self.assertIn("github-token:ephemeral", runbook)
        self.assertIn("hostinger:git", runbook)
        self.assertIn("escritura cross-repo", runbook)
        self.assertIn("GitHub App dedicada", runbook)
        self.assertIn("--manifest-stdin", runbook)
        self.assertIn("v1", runbook)
        self.assertIn("migración", runbook)
        self.assertNotIn("GitHub Apps distintas", runbook)
        self.assertNotIn("--manifest /ruta", runbook)

    def test_tanda1_handoff_marks_closed_gates(self):
        handoff = (
            Path(__file__).resolve().parents[1] / "docs" / "tanda1-handoff.md"
        ).read_text(encoding="utf-8")
        for issue in ("#9", "#10", "#12"):
            self.assertIn(issue, handoff)
        self.assertIn("#9 — puertas de decisión humana · CERRADO", handoff)
        self.assertIn("#10 — resiliencia del dueño y de la fábrica · CERRADO", handoff)
        self.assertIn("#12 — cumplimiento técnico de datos/licencias · CERRADO", handoff)
        self.assertNotIn("mantener #9 abierto/bloqueado", handoff)
        self.assertNotIn("mantener #10 abierto/bloqueado", handoff)
        self.assertNotIn("mantener #12 abierto/bloqueado", handoff)

    def test_tanda1_handoff_uses_current_capability_model(self):
        handoff = (
            Path(__file__).resolve().parents[1] / "docs" / "tanda1-handoff.md"
        ).read_text(encoding="utf-8")
        self.assertIn("github-token:ephemeral", handoff)
        self.assertIn("hostinger:git", handoff)
        self.assertIn("escritura cross-repo", handoff)
        self.assertIn("GitHub App dedicada", handoff)
        self.assertNotIn("tres GitHub Apps obligatorias", handoff)
        self.assertNotIn("tres identidades", handoff)

    def test_tanda1_handoff_preserves_legal_and_pages_boundaries(self):
        handoff = (
            Path(__file__).resolve().parents[1] / "docs" / "tanda1-handoff.md"
        ).read_text(encoding="utf-8")
        self.assertIn("#53 — revisión jurídica humana · SEPARADA", handoff)
        self.assertIn("no equivale a afirmar aprobación jurídica", handoff)
        self.assertIn("#35 — exposición pública de la cabina · SEPARADA", handoff)
        self.assertIn("#35 no bloquea el cierre técnico de TANDA 1", handoff)

    def test_tanda1_handoff_keeps_release_unpublished(self):
        handoff = (
            Path(__file__).resolve().parents[1] / "docs" / "tanda1-handoff.md"
        ).read_text(encoding="utf-8")
        self.assertIn("#13 — épico de madurez · ABIERTO", handoff)
        self.assertIn("#54", handoff)
        self.assertIn("#71", handoff)
        self.assertIn("v1.0.0", handoff)
        self.assertIn("no publicado y no autorizado", handoff)

    def test_valid_evidence(self):
        validate_manifest(sample_manifest(), now=NOW)

    def test_distinct_identities(self):
        data = sample_legacy_manifest()
        data["identities"]["deploy"] = data["identities"]["ci"]
        with self.assertRaises(ValidationError):
            validate_legacy_manifest(data, now=NOW)

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
