import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/bootstrap-coordination.yml"

class BootstrapCoordinationWorkflowTests(unittest.TestCase):
    def test_consumer_preparation_has_no_provision_secret(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Preparar contrato del consumidor sin secretos",text)
        self.assertIn("--prepare --consumer-root consumer",text)
        prepare=text.split("- name: Preparar contrato del consumidor sin secretos",1)[1].split(
            "- name: Crear rama y PR bootstrap desde entrega preparada",1
        )[0]
        self.assertNotIn("FACTORY_PROVISION_TOKEN",prepare)
        self.assertIn("persist-credentials: false",text)
        apply=text.split("- name: Crear rama y PR bootstrap desde entrega preparada",1)[1]
        self.assertIn("FACTORY_PROVISION_TOKEN",apply)
        self.assertIn("--apply-prepared",apply)
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


    def test_preparation_and_apply_use_separate_jobs(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("jobs:\n  prepare:",text)
        self.assertIn("\n  apply:\n    needs: prepare",text)
        prepare=text.split("\n  prepare:",1)[1].split("\n  apply:",1)[0]
        apply=text.split("\n  apply:",1)[1]
        self.assertNotIn("FACTORY_PROVISION_TOKEN",prepare)
        self.assertIn("FACTORY_PROVISION_TOKEN",apply)
        self.assertIn("Publicar entrega preparada",prepare)
        self.assertIn("Descargar entrega preparada",apply)

    def test_privileged_job_never_checks_out_or_executes_consumer(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        apply=text.split("\n  apply:",1)[1]
        self.assertNotIn("repository: ${{ inputs.target_repository }}",apply)
        self.assertNotIn("--consumer-root",apply)
        self.assertNotIn("readme-dashboard.py",apply)
        self.assertIn("python3 runtime/scripts/bootstrap_coordination.py --apply-prepared",apply)

    def test_artifact_handoff_is_sha_pinned_without_permission_expansion(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",text)
        self.assertIn("actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0",text)
        self.assertIn("include-hidden-files: true",text)
        self.assertIn("permissions:\n  contents: read",text)
        self.assertNotIn("contents: write",text)
        self.assertNotIn("pull-requests: write",text)
        self.assertNotIn("issues: write",text)

    def test_consumer_checkout_uses_fixed_main(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        block=text.split("repository: ${{ inputs.target_repository }}",1)[1].split("path: consumer",1)[0]
        self.assertIn("ref: main",block)

    def test_expected_main_sha_is_not_checkout_ref(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("ref: ${{ inputs.expected_main_sha }}",text)
        self.assertIn("EXPECTED_MAIN_SHA: ${{ inputs.expected_main_sha }}",text)

if __name__=="__main__":
    unittest.main()
