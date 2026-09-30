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
        self.assertIn("jobs:\n  resolve:",text)
        self.assertIn("\n  prepare:\n    needs: resolve",text)
        self.assertIn("\n  apply:\n    needs: [resolve, prepare]",text)
        prepare=text.split("\n  prepare:",1)[1].split("\n  apply:",1)[0]
        apply=text.split("\n  apply:",1)[1]
        self.assertNotIn("FACTORY_PROVISION_TOKEN",prepare)
        self.assertIn("FACTORY_PROVISION_TOKEN",apply)
        self.assertIn("Publicar entrega preparada",prepare)
        self.assertIn("Descargar entrega preparada",apply)

    def test_privileged_job_never_checks_out_or_executes_consumer(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        apply=text.split("\n  apply:",1)[1]
        self.assertNotIn("repository: ${{ needs.resolve.outputs.repo }}",apply)
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
        block=text.split("repository: ${{ needs.resolve.outputs.repo }}",1)[1].split("path: consumer",1)[0]
        self.assertIn("ref: main",block)

    def test_expected_main_sha_is_not_checkout_ref(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("ref: ${{ needs.resolve.outputs.sha }}",text)
        self.assertIn("EXPECTED_MAIN_SHA: ${{ needs.resolve.outputs.sha }}",text)

    def test_expected_main_sha_remains_runtime_guard(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_MAIN_SHA: ${{ needs.resolve.outputs.sha }}",text)
        self.assertIn("python3 runtime/scripts/bootstrap_coordination.py --prepare --consumer-root consumer",text)
        block=text.split("repository: ${{ needs.resolve.outputs.repo }}",1)[1].split("path: consumer",1)[0]
        self.assertIn("ref: main",block)
        self.assertNotIn("needs.resolve.outputs.sha",block)

    def test_artifact_download_stays_under_runner_temp(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        apply=text.split("\n  apply:",1)[1]
        self.assertIn("path: ${{ runner.temp }}/factory-bootstrap-delivery",apply)
        self.assertIn("FACTORY_PREPARED_DIR: ${{ runner.temp }}/factory-bootstrap-delivery",apply)
        self.assertNotIn("path: .\n",apply)
        self.assertNotIn("FACTORY_PREPARED_DIR: .",apply)


    def test_cross_main_fix_does_not_expand_permissions_or_inputs(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read",text)
        for field in ("target_repository:","target_issue:","expected_main_sha:","governance_ref:","idempotency_key:"):
            self.assertEqual(text.count(field),1)
        for forbidden in ("contents: write","pull-requests: write","issues: write"):
            self.assertNotIn(forbidden,text)
        self.assertEqual(text.count("FACTORY_PROVISION_TOKEN:"),1)
        self.assertIn("[[ \"$ACTOR\" == \"$OWNER\" ]]",text)


    def test_manual_dispatch_contract_is_preserved(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        manual=text.split("workflow_dispatch:",1)[1].split("permissions:",1)[0]
        for field in ("target_repository:","target_issue:","expected_main_sha:","governance_ref:","idempotency_key:"):
            self.assertIn(field,manual)
        self.assertIn('EVENT_NAME: ${{ github.event_name }}',text)
        self.assertIn('if [[ "$EVENT_NAME" == "workflow_dispatch" ]]',text)
        self.assertIn('[[ "$ACTOR" == "$OWNER" ]]',text)
        self.assertIn('[[ "$REF" == "refs/heads/$DEFAULT_BRANCH" ]]',text)

    def test_owner_issue_comment_can_resolve_bootstrap_request(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("issue_comment:\n    types: [created]",text)
        self.assertIn('COMMENT_BODY: ${{ github.event.comment.body || \'\' }}',text)
        self.assertIn('elif [[ "$EVENT_NAME" == "issue_comment" ]]',text)
        self.assertIn(r'^/bootstrap-coordination\ (pl0n3r/[A-Za-z0-9_.-]{1,100})\ ([1-9][0-9]*)\ ([0-9a-f]{40})$',text)
        self.assertIn('target_repository="${BASH_REMATCH[1]}"',text)
        self.assertIn("repo=%s\\nissue=%s\\nsha=%s",text)

    def test_comment_transport_fails_closed_for_untrusted_or_malformed_requests(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        resolve=text.split("\n  resolve:",1)[1].split("\n  prepare:",1)[0]
        self.assertIn('[[ "$ACTOR" == "$OWNER" ]]',resolve)
        self.assertIn('[[ -z "$COMMENT_PR_URL" ]]',resolve)
        self.assertIn('comando bootstrap inválido',resolve)
        self.assertIn('repositorio inválido',resolve)
        self.assertIn('issue inválido',resolve)
        self.assertIn('sha inválido',resolve)
        self.assertNotIn("actions/checkout@",resolve)

    def test_comment_transport_fixes_governance_and_derives_idempotency(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        resolve=text.split("\n  resolve:",1)[1].split("\n  prepare:",1)[0]
        self.assertIn('governance_ref="pl0n3r/factory@v1"',resolve)
        self.assertIn("sha256sum",resolve)
        self.assertIn('[[ "$governance_ref" == "pl0n3r/factory@v1" ]]',resolve)
        self.assertIn('[[ "$idempotency_key" =~ ^[0-9a-f]{64}$ ]]',resolve)
        self.assertNotIn("COMMENT_GOVERNANCE",resolve)
        self.assertNotIn("COMMENT_IDEMPOTENCY",resolve)

    def test_prepare_and_apply_consume_resolved_request_outputs(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        prepare=text.split("\n  prepare:",1)[1].split("\n  apply:",1)[0]
        apply=text.split("\n  apply:",1)[1]
        for output in ("repo","issue","sha","governance","idempotency"):
            self.assertIn(f"needs.resolve.outputs.{output}",prepare)
            self.assertIn(f"needs.resolve.outputs.{output}",apply)
        self.assertIn("needs: resolve",prepare)
        self.assertIn("needs: [resolve, prepare]",text)

    def test_comment_transport_does_not_expand_permissions_or_checkout_before_authority(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read",text)
        for forbidden in ("contents: write","pull-requests: write","issues: write"):
            self.assertNotIn(forbidden,text)
        resolve=text.split("\n  resolve:",1)[1].split("\n  prepare:",1)[0]
        self.assertNotIn("uses:",resolve)
        self.assertLess(text.index("Resolver solicitud y validar autoridad"),text.index("actions/checkout@"))
        self.assertEqual(text.count("FACTORY_PROVISION_TOKEN:"),1)

    def test_non_bootstrap_issue_comments_are_skipped_before_resolve(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        guard=text.split("\n  resolve:",1)[1].split("\n    runs-on:",1)[0]
        self.assertIn("if: >-",guard)
        self.assertIn("github.event_name == 'workflow_dispatch'",guard)
        self.assertIn("github.event_name == 'issue_comment'",guard)
        self.assertIn("github.actor == github.repository_owner",guard)
        self.assertIn("startsWith(github.event.comment.body, '/bootstrap-coordination ')",guard)
        self.assertNotIn("contains(",guard)

    def test_bootstrap_entry_guard_preserves_authorized_paths_and_fail_closed_validation(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        guard=text.split("\n  resolve:",1)[1].split("\n    runs-on:",1)[0]
        resolve=text.split("\n  resolve:",1)[1].split("\n  prepare:",1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'",guard)
        self.assertIn("github.actor == github.repository_owner",guard)
        self.assertIn("startsWith(github.event.comment.body, '/bootstrap-coordination ')",guard)
        self.assertIn('[[ "$ACTOR" == "$OWNER" ]]',resolve)
        self.assertIn('[[ -z "$COMMENT_PR_URL" ]]',resolve)
        self.assertIn(r'^/bootstrap-coordination\ (pl0n3r/[A-Za-z0-9_.-]{1,100})\ ([1-9][0-9]*)\ ([0-9a-f]{40})$',resolve)
        self.assertIn("comando bootstrap inválido",resolve)

    def test_bootstrap_entry_guard_does_not_expand_permissions_or_secrets(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        guard=text.split("\n  resolve:",1)[1].split("\n    runs-on:",1)[0]
        self.assertIn("permissions:\n  contents: read",text)
        for forbidden in ("contents: write","pull-requests: write","issues: write"):
            self.assertNotIn(forbidden,text)
        for field in ("target_repository:","target_issue:","expected_main_sha:","governance_ref:","idempotency_key:"):
            self.assertEqual(text.count(field),1)
        self.assertEqual(text.count("FACTORY_PROVISION_TOKEN:"),1)
        self.assertNotIn("secrets.",guard)

if __name__=="__main__":
    unittest.main()
