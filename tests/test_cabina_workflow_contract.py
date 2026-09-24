import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/cabina.yml").read_text(encoding="utf-8")


class CabinaWorkflowContractTests(unittest.TestCase):
    def test_pages_permissions_are_job_scoped_and_actions_pinned(self):
        self.assertIn("permissions:\\n  contents: read", WORKFLOW)
        self.assertIn("permissions:\\n      pages: write\\n      id-token: write", WORKFLOW)
        self.assertIn("schedule:", WORKFLOW)
        self.assertIn("cron: '7 * * * *'", WORKFLOW)
        uses = re.findall(r"uses:\\s+([^\\s]+)", WORKFLOW)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40}$")

    def test_pages_publication_requires_explicit_opt_in(self):
        guard = "vars.FACTORY_CABINA_PUBLICA == 'true'"
        self.assertIn(
            "if: ${{ github.event_name != 'schedule' || "
            "vars.FACTORY_CABINA_PUBLICA == 'true' }}",
            WORKFLOW,
        )
        self.assertGreaterEqual(WORKFLOW.count(f"if: ${{{{ {guard} }}}}"), 3)
        self.assertRegex(
            WORKFLOW,
            rf"(?s)name: Preparar Pages\\s+if: \\$\\{{\\{{ {re.escape(guard)} \\}}\\}}"
            r".*?uses: actions/configure-pages@",
        )
        self.assertRegex(
            WORKFLOW,
            rf"(?s)name: Empaquetar artefacto Pages\\s+if: \\$\\{{\\{{ {re.escape(guard)} \\}}\\}}"
            r".*?uses: actions/upload-pages-artifact@",
        )
        self.assertRegex(
            WORKFLOW,
            rf"(?s)publicar:\\s+name: Publicar en Pages\\s+needs: generar\\s+"
            rf"if: \\$\\{{\\{{ {re.escape(guard)} \\}}\\}}",
        )


if __name__ == "__main__":
    unittest.main()
