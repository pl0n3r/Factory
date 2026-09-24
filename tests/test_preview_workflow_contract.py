import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REUSABLE = (ROOT / ".github/workflows/preview.yml").read_text(encoding="utf-8")
TEMPLATE_CI = (ROOT / "template/.github/workflows/ci.yml").read_text(encoding="utf-8")
DOC = (ROOT / "docs/preview-preproduccion.md").read_text(encoding="utf-8")


class PreviewWorkflowContractTests(unittest.TestCase):
    def test_reusable_is_read_only_and_pinned(self):
        self.assertIn("name: Preview preproducción", REUSABLE)
        self.assertIn("permissions:\n  contents: read", REUSABLE)
        self.assertNotIn("\n  secrets:", REUSABLE)
        self.assertNotIn("DEPLOY_TOKEN:", REUSABLE)
        self.assertIn("persist-credentials: false", REUSABLE)
        self.assertIn("timeout-minutes: 20", REUSABLE)
        self.assertIn("concurrency:", REUSABLE)
        self.assertIn("github.event.pull_request.head.sha", REUSABLE)
        uses = re.findall(r"uses:\s+([^\s]+)", REUSABLE)
        external = [value for value in uses if not value.startswith("./")]
        for value in external:
            self.assertRegex(value, r"@[0-9a-f]{40}$")

    def test_template_validar_depends_on_ci_and_preview(self):
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/preview.yml@v1",
            TEMPLATE_CI,
        )
        self.assertIn("needs: [ci, preview]", TEMPLATE_CI)
        self.assertIn("name: Validar", TEMPLATE_CI)
        self.assertIn("success|skipped", TEMPLATE_CI)

    def test_contract_documents_same_adapters_and_no_live_resources(self):
        self.assertIn("deploy_kit.py::run_pipeline", DOC)
        for adapter in ("build", "backup", "migrate", "deploy", "rollback"):
            self.assertIn(f"ops/factory/{adapter}", DOC)
        self.assertIn("FACTORY_PREVIEW=1", DOC)
        self.assertIn("FACTORY_SYNTHETIC_DATA=1", DOC)
        self.assertIn("Nunca deben tocar recursos live en preview", DOC)


if __name__ == "__main__":
    unittest.main()
