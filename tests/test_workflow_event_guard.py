from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class WorkflowEventGuardTests(unittest.TestCase):
    def text(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_code_executing_reusables_guard_privileged_events_before_checkout(self) -> None:
        guarded = {
            "ci.yml": "Rechazar eventos privilegiados",
            "preview.yml": "Rechazar eventos privilegiados",
            "aceptacion.yml": "Rechazar eventos privilegiados",
            "deploy.yml": "Validar contexto de despliegue",
            "release.yml": "Validar contexto confiable",
            "observar.yml": "Validar contexto confiable",
        }
        for name, marker in guarded.items():
            with self.subTest(workflow=name):
                text = self.text(name)
                self.assertIn(marker, text)
                self.assertIn("actions/checkout@", text)
                self.assertLess(text.index(marker), text.index("actions/checkout@"))

        for name in ("ci.yml", "preview.yml", "aceptacion.yml"):
            text = self.text(name)
            self.assertIn("permissions: {}", text)
            self.assertIn("needs: event_guard", text)
            cache_lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip().startswith("cache-mode:")
            ]
            self.assertEqual(cache_lines, ["cache-mode: read"])

        forbidden = ("pull_request_target", "workflow_run", "issue_comment")
        ci = self.text("ci.yml")
        guard = ci[ci.index("Rechazar eventos privilegiados"):ci.index("  preflight:")]
        for event in forbidden:
            self.assertNotIn(f"{event})", guard)

    def test_consumer_commands_strip_cache_credentials_without_candidate_runner_dependency(self) -> None:
        ci = self.text("ci.yml")
        self.assertNotIn(".factory/scripts/consumer_ci.py", ci)
        self.assertIn("composer validate --strict", ci)
        self.assertIn('scripts=payload.get("scripts")', ci)
        self.assertIn('isinstance(scripts, dict) and "test" in scripts', ci)
        self.assertIn("npm test --if-present", ci)
        self.assertIn("npm run build --if-present", ci)
        retry = (ROOT / "scripts" / "ci_retry.py").read_text(encoding="utf-8")
        for key in (
            "ACTIONS_CACHE_URL",
            "ACTIONS_RUNTIME_TOKEN",
            "ACTIONS_RESULTS_URL",
            "ACTIONS_CACHE_SERVICE_V2",
        ):
            self.assertGreaterEqual(ci.count(f"-u {key}"), 3)
            self.assertIn(key, retry)
        self.assertIn("env=environment", retry)

    def test_factory_kit_checkout_never_executes_an_arbitrary_input_ref(self) -> None:
        ci = self.text("ci.yml")
        self.assertNotIn(r"ref: ${{ inputs.kit_ref }}", ci)
        self.assertEqual(ci.count("ref: v1"), 2)
        trusted_ref = r"ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}"
        self.assertEqual(ci.count(trusted_ref), 2)
        self.assertIn('KIT_REF: ${{ inputs.kit_ref }}', ci)
        self.assertIn('PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}', ci)
        self.assertIn("Los consumidores solo pueden ejecutar Factory Kit desde el canal protegido v1", ci)
        self.assertIn("Factory solo admite kit_ref=v1 o el SHA exacto del evento", ci)

    def test_consumer_code_jobs_disable_cache_access(self) -> None:
        ci = self.text("ci.yml")
        cache_env = (
            "ACTIONS_CACHE_URL: ''",
            "ACTIONS_RUNTIME_TOKEN: ''",
            "ACTIONS_RESULTS_URL: ''",
            "ACTIONS_CACHE_SERVICE_V2: ''",
        )
        for step_name in ("Instalar Composer bloqueado", "Instalar npm bloqueado"):
            start = ci.index(f"- name: {step_name}")
            end = ci.find("\n      - name:", start + 1)
            block = ci[start:] if end == -1 else ci[start:end]
            self.assertIn("uses: ./.factory/actions/retry", block)
            for entry in cache_env:
                self.assertIn(entry, block)

    def test_privacy_reusables_are_read_only_cache_consumers(self) -> None:
        for name in ("privacidad.yml", "auditoria-privacidad.yml"):
            with self.subTest(workflow=name):
                text = self.text(name)
                cache_lines = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip().startswith("cache-mode:")
                ]
                self.assertEqual(cache_lines, ["cache-mode: read"])
                self.assertIn("actions/checkout@", text)

    def test_factory_lint_only_ignores_actionlint_cache_mode_parser_gap(self) -> None:
        workflow = self.text("factory-ci.yml")
        self.assertIn(
            """-ignore 'unexpected key "cache-mode" for "workflow" section'""",
            workflow,
        )
        self.assertNotIn("-ignore 'cache-mode'", workflow)

    def test_guard_allows_current_non_privileged_events(self) -> None:
        ci = self.text("ci.yml")
        self.assertIn("pull_request|push|merge_group", ci)
        self.assertIn("workflow_dispatch)", ci)
        self.assertIn('REPOSITORY: ${{ github.repository }}', ci)
        self.assertIn('FACTORY_RELEASE_BOOTSTRAP: ${{ inputs.factory_release_bootstrap }}', ci)
        self.assertIn('[[ "$REPOSITORY" == "pl0n3r/factory" && "$FACTORY_RELEASE_BOOTSTRAP" == "true" ]]', ci)
        self.assertIn(
            "if: inputs.stack != 'node' && (github.event_name == 'pull_request' || github.event_name == 'merge_group')",
            ci,
        )
        self.assertIn(
            "if: inputs.node_enabled && (github.event_name == 'pull_request' || github.event_name == 'merge_group')",
            ci,
        )
        self.assertNotIn(
            "if: github.event_name == 'pull_request' || github.event_name == 'push' || github.event_name == 'merge_group'\n    runs-on: ubuntu-latest\n    timeout-minutes: 20",
            ci,
        )
        release = self.text("release-bootstrap.yml")
        self.assertEqual(release.count("factory_release_bootstrap: true"), 2)
        for name in ("preview.yml", "aceptacion.yml"):
            text = self.text(name)
            self.assertIn('[[ "$EVENT_NAME" == "pull_request" ]]', text)
        deploy = self.text("deploy.yml")
        self.assertIn("workflow_dispatch|push)", deploy)

    def test_write_capable_push_does_not_run_consumer_php_or_node(self) -> None:
        ci = self.text("ci.yml")
        php = ci[ci.index("  php:"):ci.index("  node:")]
        node = ci[ci.index("  node:"):ci.index("  validar:")]
        self.assertIn("pull_request", php)
        self.assertIn("merge_group", php)
        self.assertNotIn("github.event_name == 'push'", php)
        self.assertIn("pull_request", node)
        self.assertIn("merge_group", node)
        self.assertNotIn("github.event_name == 'push'", node)

    def test_factory_ci_keeps_edited_for_open_pr_revalidation(self) -> None:
        workflow = self.text("factory-ci.yml")
        self.assertIn(
            "types: [opened, synchronize, reopened, edited]",
            workflow,
        )

    def test_factory_coordination_skips_closed_or_merged_prs(self) -> None:
        workflow = self.text("factory-ci.yml")
        self.assertIn(
            "if: github.event_name == 'pull_request' && github.event.pull_request.state == 'open'",
            workflow,
        )

    def test_factory_acceptance_skips_closed_or_merged_prs_but_keeps_always(self) -> None:
        workflow = self.text("factory-ci.yml")
        self.assertIn(
            "if: always() && github.event_name == 'pull_request' && github.event.pull_request.state == 'open'",
            workflow,
        )

    def test_factory_aggregate_accepts_skipped_post_merge_jobs(self) -> None:
        workflow = self.text("factory-ci.yml")
        validar = workflow[workflow.index("  validar:"):]
        self.assertIn("if: always()", validar)
        self.assertIn("success|skipped", validar)
        self.assertIn("Gate con resultado $r", validar)

    def test_factory_coordination_rechecks_live_pr_state_before_lease_validation(self) -> None:
        workflow = self.text("factory-ci.yml")
        coordination = workflow[workflow.index("  coordinacion:"):workflow.index("  acceptance:")]
        self.assertIn("name: Comprobar estado live del PR", coordination)
        self.assertIn("id: pr_live", coordination)
        self.assertIn('gh api "repos/$REPOSITORIO/pulls/$PR" --jq '.state'', coordination)
        self.assertIn('open) echo "is_open=true" >> "$GITHUB_OUTPUT"', coordination)
        self.assertIn('closed)', coordination)
        validation = coordination[coordination.index("- name: Validar reserva, rama y colisiones"):]
        self.assertIn("if: steps.pr_live.outputs.is_open == 'true'", validation)
        self.assertIn("coordinar_trabajo.py validar-pr", validation)
        self.assertLess(
            coordination.index("name: Comprobar estado live del PR"),
            coordination.index("coordinar_trabajo.py validar-pr"),
        )

    def test_factory_acceptance_rechecks_live_pr_state_before_issue_evidence(self) -> None:
        workflow = self.text("factory-ci.yml")
        acceptance = workflow[workflow.index("  acceptance:"):workflow.index("  validar:")]
        self.assertIn("pull-requests: read", acceptance)
        self.assertIn("name: Comprobar estado live del PR", acceptance)
        self.assertIn('gh api "repos/$REPOSITORIO/pulls/$PR" --jq '.state'', acceptance)
        self.assertIn("if: steps.pr_live.outputs.is_open == 'true'", acceptance)
        evidence = acceptance[acceptance.index("- name: Construir evidencia del Issue y SHA"):]
        self.assertIn("if: steps.pr_live.outputs.is_open == 'true'", evidence)
        self.assertLess(
            acceptance.index("name: Comprobar estado live del PR"),
            acceptance.index("Construir evidencia del Issue y SHA"),
        )

    def test_live_pr_guard_keeps_open_pr_validation_fail_closed(self) -> None:
        workflow = self.text("factory-ci.yml")
        self.assertEqual(workflow.count("name: Comprobar estado live del PR"), 2)
        self.assertGreaterEqual(
            workflow.count("if: steps.pr_live.outputs.is_open == 'true'"),
            5,
        )
        self.assertIn('*) echo "::error::Estado live inesperado para PR #$PR: $state"; exit 1 ;;', workflow)
        self.assertIn("coordinar_trabajo.py validar-pr", workflow)
        self.assertIn("python3 scripts/aceptacion_kit.py", workflow)
        self.assertIn(
            "if: github.event_name == 'pull_request' && github.event.pull_request.state == 'open'",
            workflow,
        )
        self.assertIn(
            "if: always() && github.event_name == 'pull_request' && github.event.pull_request.state == 'open'",
            workflow,
        )

    def test_docs_define_event_contract(self) -> None:
        agents = (ROOT / "AGENTES.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "arquitectura-tecnica.md").read_text(encoding="utf-8")
        for text in (agents, architecture):
            self.assertIn("pull_request_target", text)
            self.assertIn("workflow_run", text)
            self.assertIn("issue_comment", text)
            self.assertIn("pull_request", text)
            self.assertIn("push", text)


if __name__ == "__main__":
    unittest.main()
