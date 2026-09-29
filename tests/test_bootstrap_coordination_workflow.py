import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/bootstrap-coordination.yml"

class BootstrapCoordinationWorkflowTests(unittest.TestCase):
    def test_consumer_preparation_has_no_provision_secret(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Preparar contrato del consumidor sin secretos",text)
        self.assertIn("--prepare /tmp/bootstrap-delivery.json --consumer-root consumer",text)
        prepare=text.split("- name: Preparar contrato del consumidor sin secretos",1)[1].split(
            "- name: Crear rama y PR bootstrap desde entrega preparada",1
        )[0]
        self.assertNotIn("FACTORY_PROVISION_TOKEN",prepare)
        self.assertIn("persist-credentials: false",text)
        apply=text.split("- name: Crear rama y PR bootstrap desde entrega preparada",1)[1]
        self.assertIn("FACTORY_PROVISION_TOKEN",apply)
        self.assertIn("--apply-prepared /tmp/bootstrap-delivery.json",apply)
        self.assertNotIn("--consumer-root",apply)

    def test_permissions_and_human_gates_are_not_expanded(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read",text)
        self.assertIn("workflow_dispatch:",text)
        self.assertIn("cancel-in-progress: false",text)
        self.assertNotIn("factory-human-gate",text)
        self.assertNotIn("pull-requests: write",text)
        self.assertNotIn("issues: write",text)
        self.assertNotIn("contents: write",text)
        self.assertEqual(text.count("FACTORY_PROVISION_TOKEN:"),1)
        self.assertNotIn("github.token",text)

if __name__=="__main__":
    unittest.main()
