import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = (ROOT / "docs/reusable-release-rollback.md").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "docs/release-bootstrap.md").read_text(encoding="utf-8")


class ReusableReleaseRollbackTests(unittest.TestCase):
    def test_runbook_has_evidence_target_action_and_verification(self):
        for required in (
            "affected_factory_sha=<SHA afectado>",
            "stable_factory_sha=<SHA estable objetivo>",
            "refs/tags/v1 -> <stable_factory_sha>",
            "materializar jobs",
            "startup_failure",
        ):
            self.assertIn(required, RUNBOOK)

    def test_runbook_preserves_human_admin_tag_boundary(self):
        self.assertIn("no autoriza", RUNBOOK)
        self.assertIn("acción humana/administrativa", RUNBOOK)
        self.assertIn("OWNER", RUNBOOK)
        self.assertIn("puerta vigente de Factory", RUNBOOK)
        self.assertNotIn("agente puede mover", RUNBOOK.lower())

    def test_runbook_requires_real_consumer_recovery_evidence(self):
        self.assertIn("evidencia nueva de consumidor", RUNBOOK)
        self.assertIn("Los runs fallidos previos al rollback **no prueban recuperación**", RUNBOOK)
        self.assertIn("al menos un consumidor afectado", RUNBOOK)
        self.assertIn("Factory no sustituye evidencia de consumidor", RUNBOOK)

    def test_release_bootstrap_links_rollback_runbook(self):
        self.assertIn("docs/reusable-release-rollback.md", BOOTSTRAP)
        self.assertIn("startup_failure", BOOTSTRAP)


if __name__ == "__main__":
    unittest.main()
