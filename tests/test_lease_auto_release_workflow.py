"""Protecciones del workflow de reservas V3, sin ejecución de GitHub real."""
import unittest
from pathlib import Path

from scripts.lease_auto_release_run import run_cycle


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "liberar-reservas.yml"


class DenyTransport:
    def __getattr__(self, name):
        raise AssertionError("OFF must never read or write the Port")


class LeaseAutoReleaseWorkflowTests(unittest.TestCase):
    def test_scheduled_executor_kill_switch_quota_and_shared_lock(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '*/10 * * * *'", text)
        self.assertIn("factory-coordination-{0}", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("permissions:\n  contents: read\n  issues: read", text)
        self.assertNotIn("issues: write", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("pull-requests: read", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertIn("Observador integrado autenticado V3", text)
        self.assertIn("gh api --paginate --slurp", text)
        self.assertIn("inventory_after_switch_recheck", text)
        self.assertIn("lease-observer-switch-before.json", text)
        self.assertIn("lease-observer-switch-after.json", text)
        self.assertIn("lease-observer-issues.json", text)
        self.assertNotIn("unique | sort", text)
        self.assertIn("lease-active-issues.json", text)
        self.assertIn("estado: requiere recuperación", text)
        self.assertIn("len(managed) > 10", text)
        self.assertIn('python3 -m scripts.lease_auto_release_integration "$issue_number"', text)
        self.assertNotIn("scripts.lease_auto_release_integration 1185", text)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", text)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", text)

        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", text)
        self.assertIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn("/repos/pl0n3r/Factory/issues/767", text)
        self.assertIn("inventory_after_switch_recheck", text)
        self.assertIn("remaining * 5 < limit", text)
        self.assertIn("test_lease_auto_release.py", text)
        self.assertIn("run_cycle([1175], NoAccessPort())", text)
        self.assertNotIn("gh api -X POST", text)
        self.assertNotIn("gh api -X PATCH", text)
        self.assertNotIn("gh api -X DELETE", text)
        result = run_cycle([1185], DenyTransport())
        self.assertEqual(result.state, "feature_disabled")
        self.assertEqual(result.results[0][1].reason, "feature_disabled")
        self.assertFalse(result.results[0][1].wrote)


if __name__ == "__main__":
    unittest.main()
