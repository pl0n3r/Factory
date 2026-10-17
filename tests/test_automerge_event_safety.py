"""Regresiones del workflow inerte de auto-merge en Fase 1 (#1364)."""
from pathlib import Path
import re
import unittest

from seguridad.resiliencia import ValidationError, audit_workflow


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "automerge.yml"
)


def audit_phase_one_workflow(source: str) -> None:
    """Apply generic auditing plus the exact Fase 1 auto-merge job gate."""
    audit_workflow(source)
    lines = source.splitlines()
    # Phase 1 has a fixed root contract. Duplicate/quoted/space-before-colon
    # YAML root keys can override jobs/on without matching literal "jobs:".
    # Reject them rather than trusting the first block a text parser found.
    root_entries = [
        raw for raw in lines
        if raw.strip() and not raw[0].isspace()
        and not raw.lstrip().startswith("#")
    ]
    if root_entries != [
        "name: Auto-merge cuando esté listo", "on:", "permissions:", "jobs:"
    ]:
        raise ValidationError("automerge fase 1 requiere raíz canónica y on único")
    # A second root "on:" replaces trusted events in YAML while inventory
    # readers that select the first "on:" continue to report safe triggers.
    if lines.count("on:") != 1:
        raise ValidationError("automerge fase 1 requiere un bloque on único")
    # Only the three explicitly inventoried events are allowed. A duplicate
    # or added event changes the authority even if jobs.automerge is inert.
    event_lines = []
    for raw in lines[lines.index("on:") + 1:]:
        if raw.strip() and not raw.lstrip().startswith("#"):
            if not raw[0].isspace():
                break
            if re.match(r"^  \S", raw):
                event_lines.append(raw.rstrip())
    if event_lines != [
        "  pull_request:", "  pull_request_review:", "  workflow_run:"
    ]:
        raise ValidationError("automerge fase 1 tiene eventos no autorizados")
    # Fase 1 permits exactly one inert job. An additional active job could
    # request id-token/issues/actions:write while the disabled automerge job
    # still satisfies its own condition.
    if lines.count("jobs:") != 1:
        raise ValidationError("automerge fase 1 requiere un bloque jobs único")
    jobs = lines[lines.index("jobs:") + 1:]
    active_jobs = []
    for line in jobs:
        if line.strip() and not line.lstrip().startswith("#"):
            if not line[0].isspace():
                break
            if re.match(r"^  \S", line):
                active_jobs.append(line.rstrip())
    if active_jobs != ["  automerge:"]:
        raise ValidationError("automerge fase 1 requiere un único job inerte")
    # Scope the condition to this job, not to any later job in the YAML.
    start = lines.index("  automerge:") + 1
    job_lines = []
    for raw in lines[start:]:
        if raw.strip() and not raw.lstrip().startswith("#"):
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= 2:
                break
        job_lines.append(raw)
    # Comments and step-level conditions cannot certify a disabled job.
    effective = [line.strip() for line in job_lines if line.startswith("    if:")]
    if effective != ["if: ${{ false }}"]:
        raise ValidationError("automerge fase 1 requiere una única condición if: false")
    # AC-04: require exactly one direct job permission mapping; other scopes
    # (including id-token: write) are forbidden even for an inert job.
    headers = [i for i, raw in enumerate(job_lines)
               if raw.startswith("    permissions")
               and not raw.lstrip().startswith("#")]
    if (len(headers) != 1
            or job_lines[headers[0]].strip() != "permissions:"):
        raise ValidationError("automerge fase 1 requiere permisos de solo lectura")
    scopes = []
    for raw in job_lines[headers[0] + 1:]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if len(raw) - len(raw.lstrip(" ")) <= 4:
            break
        scopes.append(raw)
    if scopes != ["      contents: read"]:
        raise ValidationError("automerge fase 1 requiere permisos de solo lectura")

class AutoMergeEventSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_phase_one_workflow_is_inert(self):
        source = self.source
        self.assertIn("permissions:\n  contents: read\njobs:", source)
        self.assertIn("  automerge:\n", source)
        job = source.split("  automerge:\n", 1)[1]
        self.assertEqual(
            [line.strip() for line in job.splitlines() if line.startswith("    if:")],
            ["if: ${{ false }}"],
        )
        self.assertIn("      contents: read", job)
        self.assertNotIn("contents: write", source)
        self.assertNotIn("pull-requests: write", source)
        self.assertNotIn("MERGE_TOKEN", source)
        self.assertNotIn("AUTOMERGE_TOKEN", source)
        self.assertNotIn("gh pr merge", source)
        self.assertNotIn("gh api --method PUT", source)
        self.assertNotIn("/pulls/${number}/merge", source)
        self.assertNotIn("pull_request_target", source)
        self.assertIn("pull_request_review:\n    types: [submitted]", source)
        self.assertIn(
            'workflow_run:\n    workflows: ["CI factory", "Sonar CI-based", "Evidencia CodeQL"]',
            source,
        )
        audit_phase_one_workflow(source)

    def test_comment_only_false_does_not_hide_executable_true_condition(self):
        source = self.source.replace(
            "    if: ${{ false }}",
            "    if: ${{ true }}\n    # if: ${{ false }}",
            1,
        )
        job = source.split("  automerge:\n", 1)[1]
        self.assertEqual(
            [line.strip() for line in job.splitlines() if line.startswith("    if:")],
            ["if: ${{ true }}"],
        )
        self.assertNotEqual(
            [line.strip() for line in job.splitlines() if line.startswith("    if:")],
            ["if: ${{ false }}"],
        )
        with self.assertRaisesRegex(ValidationError, "condición"):
            audit_phase_one_workflow(source)

    def test_extra_or_overriding_event_cannot_rearm_workflow(self):
        # Earlier inventory scans only the first on: and collects a set.
        # Both duplicate roots and extra/duplicate event keys must DENY.
        additions = (
            self.source + "on:\n  workflow_dispatch:\n",
            self.source.replace(
                "  workflow_run:\n",
                "  workflow_dispatch:\n  workflow_run:\n", 1
            ),
            self.source.replace(
                "  workflow_run:\n",
                "  pull_request:\n  workflow_run:\n", 1
            ),
        )
        audit_phase_one_workflow(self.source)
        for source in additions:
            with self.subTest(mutant=source):
                self.assertNotEqual(source, self.source)
                with self.assertRaisesRegex(ValidationError, "on único|eventos"):
                    audit_phase_one_workflow(source)

    def test_alternate_yaml_root_keys_cannot_override_jobs_or_events(self):
        # YAML permits whitespace or quoting around root mapping keys.
        # A second "jobs :" could run an active job while the first stays inert.
        variants = (
            "on :\n  workflow_dispatch:\n",
            '"on":\n  workflow_dispatch:\n',
            "jobs :\n  unattended:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo active\n",
            '"jobs":\n  unattended:\n    runs-on: ubuntu-latest\n'
            '    steps:\n      - run: echo active\n',
        )
        for added in variants:
            with self.subTest(added=added):
                mutant = self.source + added
                with self.assertRaisesRegex(ValidationError, "raíz canónica"):
                    audit_phase_one_workflow(mutant)

    def test_false_condition_in_another_job_does_not_certify_automerge(self):
        # A decoy job with if:false must not mask an enabled automerge job.
        source = self.source.replace("    if: ${{ false }}\n", "", 1) + (
            "  dummy:\n"
            "    if: ${{ false }}\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo dummy\n"
        )
        with self.assertRaisesRegex(ValidationError, "único job|condición"):
            audit_phase_one_workflow(source)

    def test_missing_condition_in_single_job_is_rejected(self):
        # Extra-job rejection must not hide a missing condition on the only job.
        source = self.source.replace("    if: ${{ false }}\n", "", 1)
        with self.assertRaisesRegex(ValidationError, "condición"):
            audit_phase_one_workflow(source)

    def test_additional_active_job_with_write_permissions_is_denied(self):
        # A sibling job with default true can acquire write privileges even
        # when jobs.automerge stays disabled.
        source = self.source + (
            "  unattended_diagnostics:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      id-token: write\n"
            "      issues: write\n"
            "    steps:\n"
            "      - run: echo active\n"
        )
        with self.assertRaisesRegex(ValidationError, "único job"):
            audit_phase_one_workflow(source)

    def test_inert_job_rejects_extra_write_scope(self):
        # Disabled jobs cannot hold write, duplicate, implicit or flow permissions.
        valid = "    permissions:\n      contents: read\n"
        self.assertIn(valid, self.source)
        audit_phase_one_workflow(self.source)
        cases = {
            "id_token_write": valid + "      id-token: write\n",
            "issues_write": valid + "      issues: write\n",
            "flow_write": "    permissions: {contents: read, id-token: write}\n",
            "missing_mapping": "",
            "duplicate_mapping": valid + valid,
        }
        for name, replacement in cases.items():
            with self.subTest(name=name):
                mutated = self.source.replace(valid, replacement, 1)
                self.assertNotEqual(mutated, self.source)
                with self.assertRaisesRegex(ValidationError, "permisos"):
                    audit_phase_one_workflow(mutated)

    def test_attempt_to_restore_merge_authority_is_detected(self):
        source = self.source
        with self.assertRaisesRegex(ValidationError, "permisos de escritura"):
            audit_workflow(
                source.replace(
                    "permissions:\n  contents: read\njobs:",
                    "permissions:\n  contents: write\njobs:",
                    1,
                )
            )
        self.assertNotIn("gh pr merge", source)
        self.assertNotIn("gh api --method PUT", source)


if __name__ == "__main__":
    unittest.main()
