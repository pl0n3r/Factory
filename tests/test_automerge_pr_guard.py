"""Factory #1364: pruebas puras, sin acceso a GitHub ni secretos."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import json
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("automerge_pr_guard", ROOT / "scripts" / "automerge_pr_guard.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
SHA = "a" * 40
BASE = "b" * 40
NOW = datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc)
MARKER = '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
PATHS = [".github/workflows/automerge.yml", "scripts/automerge_pr_guard.py",
         "tests/test_automerge_pr_guard.py"]
TASK = {"version": 1, "owner": "pl0n3r", "paths": PATHS,
        "depends_on": [1295, 1321], "epic": 1296, "task_key": "F_AUTOMERGE_GUARD", "order": 1,
        "roles": ["ingenieria-software", "qa", "seguridad"]}
ACCEPTANCE_BODY = "### Contexto\nContexto.\n\n### Alcance\nAlcance.\n\n### Fuera de alcance\nFuera de alcance.\n\n### Criterios de aceptación\n- [ ] [AC-01] CI Validar green pero kill switch inválido/PAUSED, freeze activo o rama/HEAD no canónicos: no habilitar auto-merge. Test exacto: `tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_hard_gates_and_sha_mismatch_denied`.\n- [ ] [AC-02] CodeRabbit success `Review skipped` y sin evidencia íntegra de high/critical ⇒ UNKNOWN/denegación; findings graves activos ⇒ denegación. Test exacto: `tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_coderabbit_skipped_or_severe_unknown_denied`.\n- [ ] [AC-03] Preservar tests/producto Validar exact-HEAD y estado libre de conflictos; replay/HTTP error/páginas incompletas no habilitan merge. Test exacto: `tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_checks_and_review_evidence_fail_closed`.\n- [ ] [AC-04] Autorizar solo fusión inmediata por `PUT /repos/{owner}/{repo}/pulls/{number}/merge` con `sha=PR_SHA` y `merge_method=squash`; nunca `--auto` ni `--admin`. Denegar si existe auto-merge previo, la cola está activa/desconocida, cambia el HEAD o la API no confirma `merged=true`. Test: `tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_clean_construction_only_allows_sha_locked_immediate_merge`.\n- [ ] [AC-05] La reevaluación acepta únicamente `pull_request_review: submitted` y `workflow_run: completed` de los tres workflows allowlisted; resuelve PR/HEAD actual por REST autenticado y niega forks, PR no únicos, SHA distinto, workflow/evento no permitido o evidencia incompleta. Test exacto: `tests/test_automerge_event_safety.py::AutoMergeEventSafetyTests::test_no_untrusted_privileged_trigger_or_global_write`.\n- [ ] [AC-06] El inventario canónico refleja únicamente los triggers explícitos de auto-merge y las decisiones de seguridad por evento; no se ocultan cambios del workflow. Test exacto: `tests/test_factory_diet_inventory.py::FactoryDietInventoryTests::test_inventory_lists_every_workflow_with_trigger_and_decision`.\n- [ ] [AC-07] Sonar continúa analizando PR draft sin conceder autoridad de merge; el contrato del workflow de auto-merge refleja los triggers de reevaluación seguros. Test exacto: `tests/test_sonar_ci_analysis_workflow.py::SonarCiAnalysisWorkflowTests::test_draft_pull_request_runs_sonar_without_automerge`.\n\n### Contrato ejecutable\n<!-- factory-acceptance {\"version\":1,\"criteria\":[{\"id\":\"AC-01\",\"kind\":\"test\",\"target\":\"tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_hard_gates_and_sha_mismatch_denied\"},{\"id\":\"AC-02\",\"kind\":\"test\",\"target\":\"tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_coderabbit_skipped_or_severe_unknown_denied\"},{\"id\":\"AC-03\",\"kind\":\"test\",\"target\":\"tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_checks_and_review_evidence_fail_closed\"},{\"id\":\"AC-04\",\"kind\":\"test\",\"target\":\"tests/test_automerge_pr_guard.py::AutoMergePrGuardTests::test_clean_construction_only_allows_sha_locked_immediate_merge\"},{\"id\":\"AC-05\",\"kind\":\"test\",\"target\":\"tests/test_automerge_event_safety.py::AutoMergeEventSafetyTests::test_no_untrusted_privileged_trigger_or_global_write\"},{\"id\":\"AC-06\",\"kind\":\"test\",\"target\":\"tests/test_factory_diet_inventory.py::FactoryDietInventoryTests::test_inventory_lists_every_workflow_with_trigger_and_decision\"},{\"id\":\"AC-07\",\"kind\":\"test\",\"target\":\"tests/test_sonar_ci_analysis_workflow.py::SonarCiAnalysisWorkflowTests::test_draft_pull_request_runs_sonar_without_automerge\"}]} -->\n"
LEASE = {"version": 3, "active": True, "owner": "pl0n3r",
         "branch": "trabajo/issue-1364", "task_paths": PATHS,
         "task_depends_on": [1295, 1321],
         "reservation_id": "a0f85ea8-d865-56f2-905c-6295b5279efa",
         "acceptance_sha256": "930a40695b142be8d0ad78c4a25c4a2f0631d96763e76a9818c70c40c8883f14", "task_marker_sha256": hashlib.sha256(json.dumps(TASK, ensure_ascii=False,
                                                      separators=(",", ":"), sort_keys=True).encode("utf8")).hexdigest(),
         "reason": "recuperacion-inactividad"}
# Keep the synthetic lease pinned to the contract fixture used by these tests.
LEASE["acceptance_sha256"] = mod.acceptance_fingerprint(ACCEPTANCE_BODY)


def comment(payload, author="github-actions[bot]"):
    return {"user": {"login": author},
            "body": "<!-- condor-reserva " + json.dumps(payload) + " -->"}


def evidence():
    return {"switch": {"number": 767, "url": "https://api.github.com/repos/pl0n3r/Factory/issues/767",
                       "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
                       "state": "closed", "user": {"login": "pl0n3r"}, "body": MARKER},
            "pr": {"state": "open", "draft": False, "mergeable": True, "auto_merge": None, "changed_files": 3,
                   "head": {"sha": SHA, "ref": "trabajo/issue-1364", "repo": {"full_name": "pl0n3r/Factory", "fork": False}},
                   "base": {"ref": "main", "sha": BASE},
                   "body": "Closes #1364\n<!-- condor-reserva-id: a0f85ea8-d865-56f2-905c-6295b5279efa -->"}, "main_sha": BASE,
            "compare": {"status": "ahead", "behind_by": 0, "ahead_by": 2,
                        "base_commit": {"sha": BASE}, "merge_base_commit": {"sha": BASE}},
            "checks": {"total_count": len(mod.REQUIRED), "check_runs": [
                {"id": 101 + i, "name": name, "head_sha": SHA, "status": "completed", "conclusion": "success",
                 "app": {"slug": ("sonarqubecloud" if name == "SonarCloud Code Analysis"
                                  else "github-advanced-security" if name == "CodeQL"
                                  else "github-actions")}}
                for i, name in enumerate(mod.REQUIRED)]},
            "commit_status": {"sha": SHA, "total_count": 1, "statuses": [
                {"id": 201, "context": "CodeRabbit", "state": "success",
                 "description": "Review complete"}]},
            "status_history": [{"id": 201, "context": "CodeRabbit", "state": "success",
                                "description": "Review complete",
                                "creator": {"login": "coderabbitai[bot]"}}],
            "reviews": [{"user": {"login": "coderabbitai[bot]"}, "state": "COMMENTED",
                         "commit_id": SHA, "submitted_at": "2026-10-14T03:59:00Z", "body": "Reviewed entire patch; no blocking findings."}],
            "comments": [], "issue_comments": [], "windows": [],
            "issue": {"number": 1364, "url": "https://api.github.com/repos/pl0n3r/Factory/issues/1364",
                      "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
                      "state": "open", "user": {"login": "pl0n3r"},
                      "labels": [{"name": "estado: reservado"}],
                      "body": ACCEPTANCE_BODY + "<!-- factory-plan-task " + json.dumps(TASK) + " -->"},
            "lease_comments": [comment(LEASE)], "files": [{"filename": x} for x in PATHS],
            "dependencies": [{"number": n, "state": "closed", "state_reason": "completed",
                              "labels": [{"name": "estado: completado"}]} for n in [1295, 1321]]}


class AutoMergePrGuardTests(unittest.TestCase):
    def deny(self, data):
        with self.assertRaises(mod.Denied):
            mod.verify(data, SHA, NOW)

    def test_preexisting_deferred_auto_merge_never_authorizes_guard(self):
        """Queued server-side merges must not inherit this preflight authority."""
        mod.verify(evidence(), SHA, NOW)
        for queued in ({"enabled_by": {"login": "pl0n3r"}, "merge_method": "SQUASH"},
                       {}, True, "pending"):
            with self.subTest(queued=queued):
                q = evidence()
                q["pr"]["auto_merge"] = queued
                self.deny(q)
        q = evidence()
        q["pr"].pop("auto_merge")
        self.deny(q)

    def test_coderabbit_unfinished_review_never_authorizes_merge(self):
        # A nominally successful CodeRabbit status/review that explicitly
        # announces pending work cannot substitute for a completed review.
        phrases = (
            "Review pending", "Review in progress", "Analysis queued",
            "Review cancelled", "Scan awaiting", "Review not complete",
        )
        mod.verify(evidence(), SHA, NOW)
        for phrase in phrases:
            with self.subTest(source="commit_status", phrase=phrase):
                q = evidence()
                q["commit_status"]["statuses"][0]["description"] = phrase
                q["status_history"][0]["description"] = phrase
                self.deny(q)
            with self.subTest(source="submitted_review", phrase=phrase):
                q = evidence()
                q["reviews"][0]["body"] = phrase
                self.deny(q)
            with self.subTest(source="issue_comment", phrase=phrase):
                q = evidence()
                q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                        "body": phrase, "created_at": "2026-10-14T03:59:30Z", "updated_at": "2026-10-14T03:59:30Z"}]
                self.deny(q)

        # A later authentic review of the same SHA can supersede a historical
        # pending message, preserving the existing skip supersession behavior.
        q = evidence()
        q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                "body": "Review pending", "created_at": "2026-10-14T03:58:00Z", "updated_at": "2026-10-14T03:58:00Z"}]
        mod.verify(q, SHA, NOW)

    def test_edited_coderabbit_summary_timestamp_is_fail_closed(self):
        # Even if created_at predates a clean review, CodeRabbit's later
        # in-place edit can reintroduce skipped/incomplete evidence.
        mod.verify(evidence(), SHA, NOW)
        for marker in ("Review skipped: manual action required", "Review in progress"):
            with self.subTest(marker=marker):
                q = evidence()
                item = {"user": {"login": "coderabbitai[bot]"},
                        "body": marker,
                        "created_at": "2026-10-14T03:57:00Z",
                        "updated_at": "2026-10-14T03:59:30Z"}
                q["issue_comments"] = [item]
                self.deny(q)  # Review at 03:59 cannot override edit at 03:59:30.
                item["updated_at"] = "2026-10-14T03:58:30Z"
                mod.verify(q, SHA, NOW)
                for invalid in (None, "", "not-a-time", "2026-10-14T03:58:30"):
                    with self.subTest(marker=marker, updated_at=invalid):
                        q2 = evidence()
                        bad = deepcopy(item)
                        if invalid is None:
                            bad.pop("updated_at")
                        else:
                            bad["updated_at"] = invalid
                        q2["issue_comments"] = [bad]
                        self.deny(q2)

    def test_coderabbit_skipped_writing_variants_fail_closed(self):
        # Review success with an explicit non-review is still UNKNOWN, even
        # when a previous CodeRabbit COMMENTED review appears clean.
        mod.verify(evidence(), SHA, NOW)
        variants = (
            "Skipped review: manual action required",
            "Review was skipped due to quota",
            "Review not performed for this change",
            "Review was not completed",
            "CodeRabbit could not review this PR",
            "Unable to review this PR",
        )
        for description in variants:
            with self.subTest(source="commit_status", description=description):
                q = evidence()
                q["commit_status"]["statuses"][0]["description"] = description
                q["status_history"][0]["description"] = description
                self.deny(q)
        for description in ("Skipped review", "Review was skipped", "Review not performed"):
            with self.subTest(source="review", description=description):
                q = evidence()
                q["reviews"][0]["body"] = description
                self.deny(q)
            with self.subTest(source="issue_comment", description=description):
                q = evidence()
                q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                        "body": description,
                                        "created_at": "2026-10-14T04:00:00Z", "updated_at": "2026-10-14T04:00:00Z"}]
                self.deny(q)

    def test_coderabbit_action_not_completed_html_notice_fail_closed(self):
        # Real CodeRabbit bot response when a PR changed during the review.
        # An earlier completed exact-HEAD review cannot hide the failed action.
        bot_reply = (
            "<!-- This is an auto-generated reply by CodeRabbit -->\n"
            "<details>\n"
            "<summary>⚠️ Action not completed</summary>\n\n"
            "Pull request base or head changed.\n"
            "</details>"
        )
        variants = (
            bot_reply,
            "<details>\n<summary>Action not completed</summary>\n</details>",
            "<details>\n<summary><strong>⚠️ Action not completed</strong></summary>\n</details>",
        )
        mod.verify(evidence(), SHA, NOW)
        for notice in variants:
            with self.subTest(notice=notice):
                self.assertTrue(mod.review_incomplete_notice(notice))
                q = evidence()
                q["reviews"][0]["body"] = notice
                self.deny(q)
                q = evidence()
                q["commit_status"]["statuses"][0]["description"] = notice
                q["status_history"][0]["description"] = notice
                self.deny(q)
                q = evidence()
                q["comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                  "commit_id": SHA, "body": notice}]
                self.deny(q)
                q = evidence()
                q["issue_comments"] = [{
                    "user": {"login": "coderabbitai[bot]"},
                    "body": notice,
                    "created_at": "2026-10-14T03:59:30Z",
                    "updated_at": "2026-10-14T03:59:30Z",
                }]
                self.deny(q)
                # A later authenticated substantive review on the SAME SHA
                # may supersede an older incomplete action.
                q["reviews"][0]["submitted_at"] = "2026-10-14T04:00:30Z"
                mod.verify(q, SHA, NOW + timedelta(minutes=2))

        # Mere descriptive prose is not a bot review-state transition.
        prose = "The guide quotes <summary>⚠️ Action not completed</summary> as an example."
        self.assertFalse(mod.review_incomplete_notice(prose))
        q = evidence()
        q["reviews"][0]["body"] = prose
        mod.verify(q, SHA, NOW)
        q = evidence()
        q["issue_comments"] = [{"user": {"login": "other"}, "body": bot_reply}]
        mod.verify(q, SHA, NOW)

    def test_coderabbit_plain_action_not_completed_denied(self):
        """An anchored text error without HTML still means no completed review."""
        notices = (
            "Action not completed: Review rate limited.",
            "⚠️ Action not completed: Pull request base or head changed.",
            "- **Action not completed**: Review rate limited.",
            "> ⚠️ Action not completed: Review rate limited.",
        )
        for notice in notices:
            with self.subTest(notice=notice):
                self.assertTrue(mod.review_incomplete_notice(notice))
                q = evidence()
                q["commit_status"]["statuses"][0]["description"] = notice
                q["status_history"][0]["description"] = notice
                self.deny(q)
                q = evidence()
                q["reviews"][0]["body"] = notice
                self.deny(q)
                q = evidence()
                q["issue_comments"] = [{
                    "user": {"login": "coderabbitai[bot]"},
                    "body": notice,
                    "created_at": "2026-10-14T03:59:30Z",
                    "updated_at": "2026-10-14T03:59:30Z",
                }]
                self.deny(q)
                q["reviews"][0]["submitted_at"] = "2026-10-14T04:00:30Z"
                mod.verify(q, SHA, NOW + timedelta(minutes=2))

        for prose in (
            "The policy discusses Action not completed: Review rate limited.",
            "The guide says that an Action not completed message is possible.",
        ):
            with self.subTest(prose=prose):
                self.assertFalse(mod.review_incomplete_notice(prose))
                q = evidence()
                q["reviews"][0]["body"] = prose
                mod.verify(q, SHA, NOW)

    def test_markdown_wrapped_coderabbit_skips_fail_closed(self):
        # A skip/limit notice after the review must block even when
        # CodeRabbit formats the notice as a list, heading or nested quote.
        mod.verify(evidence(), SHA, NOW)
        notices = (
            "- Review skipped: manual review required",
            "* Review rate limited",
            "+ Review rate-limited",
            "### Review skipped",
            "> - **Review skipped**",
            "## Manual review required",
        )
        for notice in notices:
            with self.subTest(notice=notice, channel="review"):
                q = evidence()
                q["reviews"][0]["body"] = notice
                self.deny(q)
            with self.subTest(notice=notice, channel="conversation"):
                q = evidence()
                q["issue_comments"] = [
                    {"user": {"login": "coderabbitai[bot]"},
                     "body": notice,
                     "created_at": "2026-10-14T03:58:00Z",
                     "updated_at": "2026-10-14T03:59:30Z"}
                ]
                self.deny(q)
            with self.subTest(notice=notice, channel="status"):
                q = evidence()
                q["commit_status"]["statuses"][0]["description"] = notice
                q["status_history"][0]["description"] = notice
                self.deny(q)
        # Mere statements about files skipped from review or rate-limit
        # policies are not evidence that this HEAD was skipped.
        for prose in (
            "- Files skipped from review due to trivial changes.",
            "### Review complete; no high or critical findings.",
            "The guide discusses rate limited plans and skipped reviews.",
        ):
            with self.subTest(prose=prose):
                q = evidence()
                q["issue_comments"] = [
                    {"user": {"login": "coderabbitai[bot]"}, "body": prose}
                ]
                mod.verify(q, SHA, NOW)

    def test_coderabbit_security_major_category_is_blocking(self):
        # A real CodeRabbit Security & Privacy / Major finding must not be
        # downgraded to a nonsecurity "Major" quality advisory.
        finding = "**🔒 Security & Privacy** | **🟠 Major** | **🏗️ Heavy lift**"
        mod.verify(evidence(), SHA, NOW)
        q = evidence()
        q["reviews"][0]["body"] = finding
        self.deny(q)
        q = evidence()
        q["comments"] = [{"user": {"login": "coderabbitai[bot]"},
                          "commit_id": SHA, "body": finding}]
        self.deny(q)
        q = evidence()
        q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                "body": finding}]
        self.deny(q)
        q = evidence()
        q["status_history"][0]["description"] = finding
        q["commit_status"]["statuses"][0]["description"] = finding
        self.deny(q)
        q = evidence()
        q["reviews"][0]["body"] = "**🎯 Functional Correctness** | **🟠 Major**"
        mod.verify(q, SHA, NOW)
        q["reviews"][0]["body"] = "**🩺 Maintainability** | **🟠 Major**"
        mod.verify(q, SHA, NOW)

    def test_coderabbit_security_major_markdown_labels_fail_closed(self):
        # Real findings may be wrapped in Markdown lists, blockquotes or
        # headings. Prose containing the same words is not a finding.
        header = "**🔒 Security & Privacy** | **🟠 Major** | **🏗️ Heavy lift**"
        for finding in ("- " + header, "* " + header, "+ " + header,
                        "> " + header, "### " + header,
                        "> - " + header, "- > " + header,
                        "`9-13`: " + header,
                        "`9-13`: **🔒 Security &amp; Privacy** | **🟠 Major**",
                        "Line 9-13: **🔒 Security &amp; Privacy** | **🟠 Major**",
                        "scripts/automerge_pr_guard.py:31-33: **🔒 Security & Privacy** | **🟠 Major**",
                        "_🔒 Security &amp; Privacy_ | _🟠 Major_",
                        "_⚠️ Potential issue_ | _🔴 Critical_",
                        "`9-13`: **🔒 Security & Privacy** | **🟠 Major**",
                        "9-13: **🔒 Security & Privacy** | **🟠 Major**",
                        "Line 9-13: **🔒 Security &amp; Privacy** | **🟠 Major**",
                        "9-13: " + header):
            with self.subTest(finding=finding, source="review"):
                q = evidence()
                q["reviews"][0]["body"] = finding
                self.deny(q)
            with self.subTest(finding=finding, source="inline"):
                q = evidence()
                q["comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                  "commit_id": SHA, "body": finding}]
                self.deny(q)
            with self.subTest(finding=finding, source="issue_comment"):
                q = evidence()
                q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                        "body": finding}]
                self.deny(q)
            with self.subTest(finding=finding, source="status_history"):
                q = evidence()
                q["status_history"][0]["description"] = finding
                q["commit_status"]["statuses"][0]["description"] = finding
                self.deny(q)
        for advisory in ("- **🩺 Maintainability** | **🟠 Major**",
                         "> - **🩺 Maintainability** | **🟠 Major**",
                         "### **🎯 Functional Correctness** | **🟠 Major**",
                         "CodeRabbit describes Security & Privacy Major findings in its policy."):
            with self.subTest(advisory=advisory):
                q = evidence()
                q["reviews"][0]["body"] = advisory
                mod.verify(q, SHA, NOW)

    def test_coderabbit_prose_does_not_forge_severe_or_skipped_signal(self):
        # CodeRabbit explanations quote severity/rate-limit terms: those
        # mentions are not themselves an authenticated finding or skipped review.
        q = evidence()
        q["reviews"][0]["body"] = (
            "Reviewed entire patch; no critical findings. "
            "Files skipped from review due to trivial changes."
        )
        mod.verify(q, SHA, NOW)
        q = evidence()
        q["reviews"][0]["body"] = "The workflow blocks merges whenever a review is pending."
        mod.verify(q, SHA, NOW)
        q = evidence()
        q["reviews"][0]["body"] = (
            "A policy discussion mentions high, critical, blocker and rate limited."
        )
        mod.verify(q, SHA, NOW)
        q = evidence()
        q["comments"] = [{"user": {"login": "coderabbitai[bot]"},
                          "commit_id": SHA,
                          "body": "The guide discusses High and Critical severities."}]
        mod.verify(q, SHA, NOW)
        q = evidence()
        q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                "body": "Read the guide for rate limited plans and High findings."}]
        mod.verify(q, SHA, NOW)
        q = evidence()
        q["commit_status"]["statuses"][0]["description"] = (
            "Review complete; no high or critical findings."
        )
        q["status_history"][0]["description"] = (
            "Review complete; no high or critical findings."
        )
        mod.verify(q, SHA, NOW)
        # Explicit structured findings / genuine skip notices still deny.
        for finding in ("HIGH security vulnerability identified",
                        "Security HIGH vulnerability", "CRITICAL command injection",
                        "critical flaw", "Severity: HIGH", "Priority: P0",
                        "**🎯 Functional Correctness** | **🔴 Critical**",
                        "**🔒 Security & Privacy** | **🟠 Major**"):
            q = evidence()
            q["reviews"][0]["body"] = finding
            with self.subTest(finding=finding):
                self.deny(q)
        for notice in ("Review rate limited", "rate-limited", "_Review pending_",
                       "Review skipped: manual review required",
                       "Draft PR not reviewed",
                       "Review not performed"):
            q = evidence()
            q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                    "body": notice,
                                    "created_at": "2026-10-14T04:00:00Z",
                                    "updated_at": "2026-10-14T04:00:00Z"}]
            with self.subTest(notice=notice):
                self.deny(q)

    def test_coderabbit_rate_limited_variants_are_not_review_evidence(self):
        # The old regex matched rate-limit but missed rate-limited because
        # the trailing word boundary fell between "limit" and "ed".
        mod.verify(evidence(), SHA, NOW)
        for variant in ("Review rate limited", "Review rate-limited",
                        "Review rate limiting", "rate-limited"):
            with self.subTest(variant=variant):
                q = evidence()
                q["commit_status"]["statuses"][0]["description"] = variant
                q["status_history"][0]["description"] = variant
                self.deny(q)
                q = evidence()
                q["reviews"][0]["body"] = variant
                self.deny(q)
                q = evidence()
                q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                        "body": variant,
                                        "created_at": "2026-10-14T03:59:30Z",
                                        "updated_at": "2026-10-14T03:59:30Z"}]
                self.deny(q)

    def test_coderabbit_status_skipped_cannot_be_green(self):
        # A green commit status carrying skipped/rate-limited evidence is not
        # a completed security review, even with an earlier clean review.
        mod.verify(evidence(), SHA, NOW)
        for description in ("Review rate limited", "Review skipped",
                            "Manual review required", "HIGH vulnerability", "", None):
            with self.subTest(description=description):
                q = evidence()
                q["commit_status"]["statuses"][0]["description"] = description
                self.deny(q)
        for state in ("failure", "error", "pending"):
            with self.subTest(state=state):
                q = evidence()
                q["commit_status"]["statuses"][0]["state"] = state
                self.deny(q)
        q = evidence(); q["commit_status"]["sha"] = BASE; self.deny(q)
        q = evidence(); q.pop("commit_status"); self.deny(q)
        q = evidence(); q["commit_status"]["statuses"] = []; q["commit_status"]["total_count"] = 0; self.deny(q)
        q = evidence(); q["commit_status"]["statuses"].append({
            "id": 202, "context": "CodeRabbit", "state": "success",
            "description": "Review rate limited"})
        q["commit_status"]["total_count"] = 2
        self.deny(q)
        q["commit_status"]["statuses"][0]["id"] = 203
        q["status_history"][0]["id"] = 203
        mod.verify(q, SHA, NOW)

    def test_coderabbit_success_with_pending_review_description_denied(self):
        # Commit status success alone is not completed CodeRabbit analysis.
        for description in (
            "Review pending", "Review in progress", "Analysis queued",
            "Review cancelled", "Review not complete",
        ):
            with self.subTest(description=description):
                row = evidence()
                row["commit_status"]["statuses"][0]["description"] = description
                row["status_history"][0]["description"] = description
                self.deny(row)
        mod.verify(evidence(), SHA, NOW)

    def test_historical_high_severity_status_cannot_be_erased_by_new_green(self):
        # GitHub /status exposes only the newest status for each context;
        # /statuses retains prior CodeRabbit findings for the SAME HEAD.
        # A new "Review complete" status does not change the commit SHA and
        # cannot prove an earlier HIGH/CRITICAL finding was remediated.
        mod.verify(evidence(), SHA, NOW)
        for finding in ("HIGH security vulnerability identified",
                        "CRITICAL vulnerability in request handler"):
            with self.subTest(finding=finding):
                q = evidence()
                q["status_history"].append({
                    "id": 200, "context": "CodeRabbit", "state": "failure",
                    "description": finding,
                    "creator": {"login": "coderabbitai[bot]"},
                })
                self.deny(q)

        # Earlier noncritical skip superseded by a substantive exact-HEAD
        # review is not itself an active serious finding.
        q = evidence()
        q["status_history"].append({
            "id": 200, "context": "CodeRabbit", "state": "success",
            "description": "Review skipped: draft PR",
            "creator": {"login": "coderabbitai[bot]"},
        })
        mod.verify(q, SHA, NOW)

        # An unrelated publisher's HIGH status in another context does not
        # count as a finding attributed to CodeRabbit.
        q = evidence()
        q["status_history"].append({
            "id": 200, "context": "Other CI", "state": "failure",
            "description": "HIGH severity", "creator": {"login": "ci[bot]"},
        })
        mod.verify(q, SHA, NOW)

    def test_coderabbit_status_history_creator_must_be_authenticated(self):
        # GitHub's combined status omits creator. Forging the context name
        # cannot override a real CodeRabbit skipped status on the same SHA.
        q = evidence()
        mod.verify(q, SHA, NOW)
        for creator in ({"login": "attacker"}, {}, None):
            with self.subTest(creator=creator):
                q = evidence()
                q["status_history"][0]["creator"] = creator
                self.deny(q)
        q = evidence()
        q["status_history"] = []
        self.deny(q)
        q = evidence()
        q["status_history"].append({"id": 202, "context": "CodeRabbit",
                                     "state": "success", "description": "Review complete",
                                     "creator": {"login": "attacker"}})
        self.deny(q)
        q = evidence()
        q["status_history"][0]["description"] = "Review skipped"
        self.deny(q)
        q = evidence()
        q["status_history"].append({"id": 300, "context": "ci/test",
                                     "state": "success", "description": "pass",
                                     "creator": {"login": "ci-bot"}})
        mod.verify(q, SHA, NOW)

    def test_coderabbit_status_history_is_paginated_and_permissioned(self):
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text(encoding="utf8")
        lines = workflow.splitlines()
        self.assertIn("    permissions:", lines)
        index = lines.index("    permissions:")
        self.assertEqual(lines[index + 1], "      contents: read")
        self.assertNotIn("statuses: write", workflow)
        q = evidence()
        q.pop("status_history")
        self.deny(q)
    def test_job_permissions_minimal_without_external_yaml_dependency(self):
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text(encoding="utf8")
        lines = workflow.splitlines()
        permission_indices = [i for i, line in enumerate(lines) if line.strip() == "permissions:"]
        self.assertEqual(len(permission_indices), 2, "Fase 1 debe fijar permisos globales y del job")
        for index in permission_indices:
            parent_indent = len(lines[index]) - len(lines[index].lstrip())
            entries = []
            cursor = index + 1
            while cursor < len(lines):
                line = lines[cursor]
                if line.strip() and len(line) - len(line.lstrip()) <= parent_indent:
                    break
                if line.strip() and not line.lstrip().startswith("#"):
                    entries.append(line.strip())
                cursor += 1
            self.assertEqual(entries, ["contents: read"], "Solo se permite contents: read")
        self.assertNotIn("write-all", workflow.lower())
        self.assertNotRegex(workflow, r"(?m)^\s*[^#\n]+:\s*write\b")
        for forbidden in ("MERGE_TOKEN", "AUTOMERGE_TOKEN", "secrets.",
                          "gh api --method PUT", "gh pr merge"):
            self.assertNotIn(forbidden, workflow)
    def test_coderabbit_status_history_endpoint_is_complete(self):
        # GitHub /commits/{sha}/statuses exposes creator, unlike /status.
        import io
        import json as jsonlib
        from email.message import Message
        endpoint = f"/repos/pl0n3r/Factory/commits/{SHA}/statuses"
        class Response:
            def __init__(self, rows, link=""):
                self.rows = rows
                self.headers = Message()
                if link:
                    self.headers["Link"] = link
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return jsonlib.dumps(self.rows).encode()
        rows = [{"id": 600+i, "context": "CodeRabbit", "state": "success",
                 "description": "Review complete", "creator": {"login": "coderabbitai[bot]"}}
                for i in range(101)]
        def fake_urlopen(req, **_kwargs):
            page = int(req.full_url.rsplit("page=", 1)[1])
            link = '<https://api.github.com/next>; rel="next"' if page == 1 else ""
            return Response(rows[:100] if page == 1 else rows[100:], link)
        with patch.object(mod, "urlopen", side_effect=fake_urlopen):
            self.assertEqual(mod.get_paginated_records("token", endpoint), rows)
        with patch.object(mod, "urlopen", return_value=Response(
                rows[:1], '<https://api.github.com/next>; rel="next"')):
            with self.assertRaises(mod.Denied):
                mod.get_paginated_records("token", endpoint)

    def test_unknown_reservation_status_labels_fail_closed(self):
        # An unrecognized state must not be silently ignored by set intersection.
        for state in ("estado: pendiente", "estado: reserva duplicada",
                      "status: blocked", "state: unknown"):
            with self.subTest(state=state):
                q = evidence()
                q["issue"]["labels"].append({"name": state})
                self.deny(q)
        # Unrelated metadata does not affect the verified canonical state.
        q = evidence()
        q["issue"]["labels"].append({"name": "prioridad: crítica"})
        mod.verify(q, SHA, NOW)

    def test_completed_dependency_with_conflicting_state_denied(self):
        # A recognized completed label cannot mask a second blocking or
        # unrecognized status on any reserved task dependency.
        mod.verify(evidence(), SHA, NOW)
        for conflicting in ("estado: pendiente de verificación",
                            "estado: bloqueado", "estado: reservado",
                            "status: awaiting approval", "state: unknown",
                            "ESTADO: requiere intervención humana"):
            with self.subTest(label=conflicting):
                q = evidence()
                q["dependencies"][0]["labels"].append({"name": conflicting})
                self.deny(q)
        q = evidence()
        q["dependencies"][0]["labels"].append({"name": "rol: seguridad"})
        mod.verify(q, SHA, NOW)

    def test_dependency_closed_reason_must_be_completed(self):
        # A closed/not_planned dependency cannot authorize a V3 lease even
        # if its human-readable label still says completed.
        for reason in ("not_planned", None, "reopened", "duplicate"):
            with self.subTest(state_reason=reason):
                q = evidence()
                q["dependencies"][0]["state_reason"] = reason
                self.deny(q)
        q = evidence()
        q["dependencies"][0]["state_reason"] = "completed"
        mod.verify(q, SHA, NOW)

    def test_hard_gates_and_sha_mismatch_denied(self):
        d = evidence()
        for switch in ('PAUSED', 'UNKNOWN', 'RUNNING'):
            q = deepcopy(d)
            q["switch"]["body"] = MARKER.replace('"RUNNING"', f'"{switch}"')
            if switch == 'RUNNING':
                q["switch"]["body"] += MARKER
            self.deny(q)
        for change in ({"draft": True}, {"mergeable": False}):
            q = deepcopy(d); q["pr"].update(change); self.deny(q)
        q = deepcopy(d); q["pr"]["head"]["sha"] = BASE; self.deny(q)
        q = deepcopy(d); q["pr"]["head"]["repo"]["fork"] = True; self.deny(q)
        q = deepcopy(d); q["main_sha"] = SHA; self.deny(q)
        # RED: GitHub informa mergeable=True aunque la rama está detrás de main.
        q = deepcopy(d); q["compare"]["status"] = "diverged"; q["compare"]["behind_by"] = 2; self.deny(q)
        q = deepcopy(d); q["compare"]["merge_base_commit"]["sha"] = "c" * 40; self.deny(q)
        q = deepcopy(d); q.pop("compare"); self.deny(q)
        # Regresiones RED previas: una rama ajena y un Closes ajeno eran aceptados.
        q = deepcopy(d); q["pr"]["head"]["ref"] = "feature/anything"; self.deny(q)
        q = deepcopy(d); q["pr"]["head"]["ref"] = "trabajo/issue-1365"; self.deny(q)
        q = deepcopy(d); q["pr"]["body"] = "Closes #1365"; self.deny(q)
        q = deepcopy(d); q["pr"]["body"] = "Closes #1364\nCloses #1365"; self.deny(q)
        q = deepcopy(d); q["windows"] = [{"issue": {"body": '<!-- factory-release-window {"version":1,"sha":"' + BASE + '","opened_at":"2026-10-14T03:00:00Z","expires_at":"2026-10-14T05:00:00Z"} -->'}, "comments": []}]; self.deny(q)

    def test_coderabbit_skipped_or_severe_unknown_denied(self):
        for body in ("Review skipped: manual review required", "Security HIGH vulnerability", "rate-limit", ""):
            q = evidence(); q["reviews"][0]["body"] = body; self.deny(q)
        q = evidence(); q["reviews"] = []; self.deny(q)
        q = evidence(); q["reviews"][0]["commit_id"] = BASE; self.deny(q)
        q = evidence(); q["reviews"].append({"user": {"login": "other"}, "state": "CHANGES_REQUESTED"}); self.deny(q)
        # Reproducido: un APPROVED + DISMISSED no vuelve a estar aprobado.
        q = evidence(); q["reviews"].append({"user": {"login": "coderabbitai[bot]"},
                                              "state": "DISMISSED", "commit_id": SHA}); self.deny(q)
        q = evidence(); q["reviews"][0]["state"] = "DISMISSED"; self.deny(q)
        for unknown in ("PENDING", "UNKNOWN", None):
            q = evidence(); q["reviews"].append({"user": {"login": "another-reviewer"},
                                                   "state": unknown, "commit_id": SHA})
            self.deny(q)
        q = evidence(); q["comments"] = [{"user": {"login": "coderabbitai[bot]"}, "commit_id": SHA, "body": "critical flaw"}]; self.deny(q)
        # Un comentario skip del PR DRAFT no debe quedar oculto tras una
        # review vieja: únicamente una review posterior del mismo SHA lo supera.
        skipped = {"user": {"login": "coderabbitai[bot]"},
                   "body": "Review skipped: manual review required",
                   "created_at": "2026-10-14T04:02:00Z", "updated_at": "2026-10-14T04:02:00Z"}
        q = evidence()
        q["reviews"][0]["submitted_at"] = "2026-10-14T04:01:59Z"
        q["issue_comments"] = [skipped]
        self.deny(q)
        q["reviews"][0]["submitted_at"] = "2026-10-14T04:02:01Z"
        mod.verify(q, SHA, NOW + timedelta(minutes=3))
        q["reviews"][0]["submitted_at"] = "2026-10-14T04:02:00"
        self.deny(q)

        # Un review favorable no oculta el "review skipped" del Issue/PR general.
        for issue_comment in ("Review skipped: manual review required for this OSS repository",
                              "Draft PR not reviewed", "HIGH severity vulnerability"):
            q = evidence(); q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                                       "body": issue_comment}]
            self.deny(q)

    def test_future_dated_coderabbit_review_cannot_authorize_merge(self):
        # A review's submitted_at must not be after the verification instant.
        # Otherwise a future timestamp can supersede a skip that is still
        # outstanding, even when the timestamp carries a valid timezone.
        for submitted in ("2026-10-14T04:00:01Z", "2026-10-14T05:00:00Z",
                          "2026-10-14T00:00:01-04:00"):
            with self.subTest(submitted=submitted):
                q = evidence()
                q["reviews"][0]["submitted_at"] = submitted
                self.deny(q)
        q = evidence()
        q["issue_comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                "body": "Review skipped: manual review required",
                                "created_at": "2026-10-14T03:59:30Z", "updated_at": "2026-10-14T03:59:30Z"}]
        q["reviews"][0]["submitted_at"] = "2026-10-14T04:00:01Z"
        self.deny(q)

    def test_substantive_review_requires_authenticated_timestamp(self):
        # A valid CodeRabbit review must prove when it was submitted, even
        # when there was no explicit "Review skipped" in the discussion.
        mod.verify(evidence(), SHA, NOW)
        for invalid in (None, "", "unknown", "2026-10-14T04:03:00"):
            with self.subTest(submitted_at=invalid):
                q = evidence()
                if invalid is None:
                    q["reviews"][0].pop("submitted_at")
                else:
                    q["reviews"][0]["submitted_at"] = invalid
                self.deny(q)

    def test_coderabbit_inline_comment_requires_exact_commit_identity(self):
        # A CodeRabbit inline finding with unknown commit cannot safely be
        # dismissed as belonging to a different SHA; fail closed.
        for old in (None, "", "unknown", "0" * 39):
            with self.subTest(commit_id=old):
                q = evidence()
                row = {"user": {"login": "coderabbitai[bot]"},
                       "body": "HIGH security vulnerability"}
                if old is not None:
                    row["commit_id"] = old
                q["comments"] = [row]
                self.deny(q)
        # A valid finding from the current exact HEAD also blocks.
        q = evidence()
        q["comments"] = [{"user": {"login": "coderabbitai[bot]"},
                          "commit_id": SHA, "body": "HIGH security vulnerability"}]
        self.deny(q)
        # A stale commit identity does not establish remediation of HIGH.
        q["comments"][0]["commit_id"] = BASE
        self.deny(q)

    def test_coderabbit_review_unknown_commit_identity_fails_closed(self):
        # A clean review on this HEAD cannot override severe or unknown
        # CodeRabbit review evidence with a missing/invalid commit ID.
        for old in (None, "", "unknown", "0" * 39):
            with self.subTest(commit_id=old):
                q = evidence()
                row = {"user": {"login": "coderabbitai[bot]"},
                       "state": "COMMENTED",
                       "submitted_at": "2026-10-14T03:58:00Z",
                       "body": "HIGH security vulnerability in authentication"}
                if old is not None:
                    row["commit_id"] = old
                q["reviews"].append(row)
                self.deny(q)
        # Historical HIGH findings are not resolved solely by an updated SHA.
        q = evidence()
        q["reviews"].append({"user": {"login": "coderabbitai[bot]"},
                             "state": "COMMENTED", "commit_id": BASE,
                             "submitted_at": "2026-10-14T03:58:00Z",
                             "body": "HIGH security vulnerability in old revision"})
        self.deny(q)

    def test_prior_severe_coderabbit_findings_require_resolution_evidence(self):
        # A later clean exact-HEAD review is not a signed resolution for an
        # earlier HIGH/CRITICAL finding. Neither reviews nor inline findings
        # may be silently discarded by commit_id without resolution proof.
        for source, finding in (
            ("reviews", {"user": {"login": "coderabbitai[bot]"},
                         "state": "COMMENTED", "commit_id": BASE,
                         "submitted_at": "2026-10-14T03:58:00Z",
                         "body": "HIGH severity authentication vulnerability"}),
            ("comments", {"user": {"login": "coderabbitai[bot]"},
                          "commit_id": BASE,
                          "body": "CRITICAL command injection"}),
        ):
            with self.subTest(source=source):
                q = evidence()
                q[source].append(finding)
                self.deny(q)
        # A historical *advisory* remark is not itself a severe unresolved issue.
        q = evidence()
        q["reviews"].append({"user": {"login": "coderabbitai[bot]"},
                             "state": "COMMENTED", "commit_id": BASE,
                             "body": "Minor typo in earlier revision"})
        mod.verify(q, SHA, NOW)

    def test_check_runs_pagination_is_complete_and_stable(self):
        # GitHub retains reruns; after 100 check-runs a single-page fetch
        # rejects legitimate evidence even when the most recent run passed.
        rows = deepcopy(evidence()["checks"]["check_runs"])
        rows.extend({"id": 1000 + i, "name": f"Other {i}",
                     "head_sha": SHA, "status": "completed",
                     "conclusion": "success", "app": {"slug": "github-actions"}}
                    for i in range(100))
        self.assertEqual(len(rows), 105)

        def fake_fetch(_token, path):
            self.assertIn(f"/commits/{SHA}/check-runs?per_page=100&page=", path)
            page = int(path.rsplit("=", 1)[1])
            self.assertIn(page, (1, 2))
            return {"total_count": 105, "check_runs": deepcopy(rows[(page-1)*100:page*100])}

        with patch.object(mod, "get", side_effect=fake_fetch) as getter:
            checks = mod.get_check_runs("token", "/repos/pl0n3r/Factory", SHA)
        self.assertEqual(checks["total_count"], 105)
        self.assertEqual(len(checks["check_runs"]), 105)
        self.assertEqual(getter.call_count, 4)  # two complete snapshots
        mod.verify_checks(checks, SHA)

        # A changed second inventory must never be silently stitched to first.
        calls = [0]
        def unstable(_token, path):
            calls[0] += 1
            page = int(path.rsplit("=", 1)[1])
            result = {"total_count": 105, "check_runs": deepcopy(rows[(page-1)*100:page*100])}
            if calls[0] == 3:
                result["check_runs"][0]["id"] += 10000
            return result
        with patch.object(mod, "get", side_effect=unstable):
            with self.assertRaises(mod.Denied):
                mod.get_check_runs("token", "/repos/pl0n3r/Factory", SHA)

        # Truncated, overlapping or falsely counted pages are unknown.
        def broken(kind):
            def fetch(_token, path):
                page = int(path.rsplit("=", 1)[1])
                data = {"total_count": 105, "check_runs": deepcopy(rows[(page-1)*100:page*100])}
                if page == 2 and kind == "truncated":
                    data["check_runs"].pop()
                if page == 2 and kind == "duplicate":
                    data["check_runs"][0]["id"] = rows[0]["id"]
                if page == 2 and kind == "count_changed":
                    data["total_count"] = 106
                return data
            return fetch
        for kind in ("truncated", "duplicate", "count_changed"):
            with self.subTest(kind=kind), patch.object(mod, "get", side_effect=broken(kind)):
                with self.assertRaises(mod.Denied):
                    mod.get_check_runs("token", "/repos/pl0n3r/Factory", SHA)

    def test_paginated_short_page_with_next_link_denied(self):
        # The presence of Link rel=next proves a short REST page is not terminal.
        # A 1-record first page must not hide a severe finding on page two.
        class Response:
            headers = {"Link": '<https://api.github.com/repos/pl0n3r/Factory/pulls/42/reviews?per_page=100&page=2>; rel="next"'}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size):
                return json.dumps([{"id": 1, "body": "Safe-looking review"}]).encode("utf-8")

        with patch.object(mod, "urlopen", return_value=Response()):
            with self.assertRaises(mod.Denied):
                mod.get_paginated_records(
                    "token", "/repos/pl0n3r/Factory/pulls/42/reviews"
                )

    def test_short_check_run_page_with_next_link_denied(self):
        # A server claiming total_count=5 while advertising page 2 cannot
        # prove that a newer failing attempt is absent. Must deny the merge.
        good = evidence()["checks"]
        class Response:
            headers = {"Link": '<https://api.github.com/repos/pl0n3r/Factory/commits/' + SHA + '/check-runs?per_page=100&page=2>; rel="next"'}
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, _size):
                return json.dumps(good).encode("utf8")
        with patch.object(mod, "urlopen", return_value=Response()):
            with self.assertRaises(mod.Denied):
                mod.get_check_runs("token", "/repos/pl0n3r/Factory", SHA)

    def test_full_check_run_page_with_contradictory_next_link_denied(self):
        # A full page of 100 apparently-successful runs is NOT complete if
        # GitHub advertises another page despite declaring total_count=100.
        # A later failing run could be hidden behind that inconsistency.
        original = deepcopy(evidence()["checks"]["check_runs"])
        runs = original + [
            {"id": 1000 + i, "name": f"Other {i}", "head_sha": SHA,
             "status": "completed", "conclusion": "success",
             "app": {"slug": "github-actions"}}
            for i in range(95)
        ]
        self.assertEqual(len(runs), 100)
        payload = {"total_count": 100, "check_runs": runs}

        class Response:
            headers = {"Link": (
                '<https://api.github.com/repos/pl0n3r/Factory/commits/' + SHA +
                '/check-runs?per_page=100&page=2>; rel="next"'
            )}
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, _size):
                return json.dumps(payload).encode("utf8")

        with patch.object(mod, "urlopen", return_value=Response()):
            with self.assertRaises(mod.Denied):
                mod.get_check_runs("token", "/repos/pl0n3r/Factory", SHA)

    def test_paginated_full_page_link_requires_nonempty_next_page(self):
        """A claimed rel=next is not satisfied by a suddenly empty page.

        Exactly 100 terminal records without rel=next are valid; only the
        contradictory announced second page is an incomplete inventory.
        """
        class Response:
            def __init__(self, records, more):
                self.headers = {"Link": (
                    '<https://api.github.com/repos/pl0n3r/Factory/pulls/42/'
                    'reviews?per_page=100&page=2>; rel="next"' if more else "")}
                self.contents = json.dumps(records).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return self.contents

        url = "/repos/pl0n3r/Factory/pulls/42/reviews"
        first = [{"id": i} for i in range(1, 101)]
        def response_for(announces_more):
            def fetch(request, timeout=12):
                page = int(request.full_url.rsplit("page=", 1)[1])
                return Response(first if page == 1 else [],
                                announces_more if page == 1 else False)
            return fetch

        with patch.object(mod, "urlopen", side_effect=response_for(True)):
            with self.assertRaises(mod.Denied):
                mod.get_paginated_records("token", url)
        with patch.object(mod, "urlopen", side_effect=response_for(False)):
            self.assertEqual(mod.get_paginated_records("token", url), first)

    def test_paged_review_and_comment_histories_complete_and_stable(self):
        # PR review/inline/issue/lease histories can exceed 100. A single
        # first page either blocks progress or misses later security evidence.
        root = "/repos/pl0n3r/Factory"
        endpoints = [
            f"{root}/pulls/1375/files", f"{root}/pulls/1375/reviews",
            f"{root}/pulls/1375/comments", f"{root}/issues/1375/comments",
            f"{root}/issues/1364/comments", f"{root}/issues/992/comments",
        ]
        rows = [{"id": i} for i in range(1, 106)]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                if endpoint.endswith("/files"):
                    item_rows = [{"filename": f"src/file_{i}.py"} for i in range(1, 106)]
                else:
                    item_rows = rows
                called = []
                def get_page(_token, path, *, include_link=False):
                    self.assertTrue(include_link)
                    called.append(path)
                    self.assertTrue(path.startswith(endpoint + "?per_page=100&page="))
                    page = int(path.rsplit("=", 1)[1])
                    batch = deepcopy(item_rows[(page - 1)*100:page*100])
                    return batch, page == 1
                with patch.object(mod, "get", side_effect=get_page):
                    found = mod.get_paginated_records("token", endpoint)
                self.assertEqual(found, item_rows)
                self.assertEqual(len(called), 4)  # two complete scans

        # Exactly 100 records is not a complete inventory until page 2
        # confirms that no more results exist.
        calls = []
        def full_first(_token, path, *, include_link=False):
            self.assertTrue(include_link)
            calls.append(path)
            return (deepcopy(rows[:100]), False) if path.endswith("page=1") else ([], False)
        with patch.object(mod, "get", side_effect=full_first):
            self.assertEqual(mod.get_paginated_records("token", endpoints[1]), rows[:100])
        self.assertEqual(len(calls), 2)

        # Deny missing/overlapping IDs, malformed payloads and changing pages.
        for kind in ("duplicate", "malformed", "changed"):
            count = [0]
            def broken(_token, path, *, include_link=False):
                self.assertTrue(include_link)
                count[0] += 1
                page = int(path.rsplit("=", 1)[1])
                answer = deepcopy(rows[(page - 1)*100:page*100])
                if kind == "duplicate" and page == 2:
                    answer[0]["id"] = 1
                if kind == "malformed" and page == 1:
                    return {"id": 999}, True
                if kind == "changed" and count[0] == 3:
                    answer[0]["id"] = 700
                return answer, page == 1
            with self.subTest(kind=kind), patch.object(mod, "get", side_effect=broken):
                with self.assertRaises(mod.Denied):
                    mod.get_paginated_records("token", endpoints[1])

    def test_lease_v3_cannot_be_omitted_spoofed_or_revoked(self):
        # RED en implementación previa: ningún dato de lease participaba en verify().
        for key in ("issue", "lease_comments", "dependencies", "files"):
            q = evidence(); q.pop(key); self.deny(q)
        q = evidence(); q["issue"]["labels"] = [{"name": "estado: requiere recuperación"}]; self.deny(q)
        q = evidence(); q["issue"]["state"] = "closed"; self.deny(q)
        q = evidence(); q["issue"]["number"] = 999; self.deny(q)
        q = evidence(); q["lease_comments"] = []; self.deny(q)
        q = evidence(); q["lease_comments"][0]["user"]["login"] = "pl0n3r"; self.deny(q)
        q = evidence(); q["lease_comments"].append(comment(dict(LEASE, active=False))); self.deny(q)
        q = evidence(); q["lease_comments"][0] = comment(dict(LEASE, task_paths=["README.md"])); self.deny(q)
        q = evidence(); q["lease_comments"][0] = comment(dict(LEASE, branch="trabajo/issue-999")); self.deny(q)
        q = evidence(); q["files"][0]["filename"] = "secrets/key.txt"; self.deny(q)
        q = evidence(); q["files"][0]["previous_filename"] = "out-of-scope.yml"; self.deny(q)
        q = evidence(); q["pr"]["changed_files"] = 4; self.deny(q)
        q = evidence(); q["dependencies"][0]["state"] = "open"; self.deny(q)
        q = evidence(); q["dependencies"][0]["labels"] = [{"name": "estado: bloqueado"}]; self.deny(q)
        q = evidence(); q["lease_comments"].append(comment(dict(LEASE, active=True), "attacker")); self.deny(q)
        mod.verify(evidence(), SHA, NOW)

    def test_pr_reservation_metadata_must_match_bot_v3(self):
        # Coordinator requires the PR itself to be bound to the current lease.
        # Branch name and closing keyword alone do not prove that identity.
        q = evidence()
        q["pr"]["body"] = "Closes #1364"
        self.deny(q)
        q = evidence()
        q["pr"]["body"] = "Closes #1364\n<!-- condor-reserva-id: 11111111-1111-4111-8111-111111111111 -->"
        self.deny(q)
        q = evidence()
        q["pr"]["body"] = "Closes #1364\nAn arbitrary sentence mentions " + LEASE["reservation_id"]
        self.deny(q)
        q = evidence()
        q["pr"]["body"] = "Closes #1364\n<!-- condor-reserva-id: " + LEASE["reservation_id"] + " -- >"
        self.deny(q)
        # Exact canonical hidden metadata matches the bot V3 lease.
        mod.verify(evidence(), SHA, NOW)
        # Coordinator also supports a visible legacy line if hidden metadata is absent.
        q = evidence()
        q["pr"]["body"] = "Closes #1364\nReserva: " + LEASE["reservation_id"]
        mod.verify(q, SHA, NOW)
        # Coordinator emits both identical values when renewing/recovering a PR.
        q = evidence()
        q["pr"]["body"] += "\nReserva: " + LEASE["reservation_id"]
        mod.verify(q, SHA, NOW)
        # Duplicate or conflicting identifiers are not unambiguous authority.
        q = evidence()
        q["pr"]["body"] += "\n<!-- condor-reserva-id: " + LEASE["reservation_id"] + " -->"
        self.deny(q)
        q = evidence()
        q["pr"]["body"] += "\nReserva: 11111111-1111-4111-8111-111111111111"
        self.deny(q)

    def test_ready_pr_review_status_keeps_valid_v3_authorized(self):
        # Coordinacion moves reserved issues to en revision once a PR is ready.
        # The bot V3 lease, branch and fingerprints must remain authoritative.
        q = evidence()
        q["issue"]["labels"] = [{"name": "estado: en revisión"}]
        mod.verify(q, SHA, NOW)
        # A status change is not a substitute for a legitimate bot lease.
        q["lease_comments"][0] = comment(dict(LEASE, active=False))
        self.deny(q)
        q = evidence()
        q["issue"]["labels"] = [{"name": "estado: bloqueado"}]
        self.deny(q)

    def test_ambiguous_issue_status_labels_fail_closed(self):
        # A current reservation must have exactly one canonical state label.
        # A simultaneous blocked/recovery/completed label cannot be ignored
        # just because reserved or review is also present.
        for valid_state in ("estado: reservado", "estado: en revisión"):
            for unsafe_state in (
                "estado: bloqueado", "estado: requiere recuperación",
                "estado: completado", "estado: cancelado", "estado: disponible",
            ):
                with self.subTest(valid=valid_state, unsafe=unsafe_state):
                    q = evidence()
                    q["issue"]["labels"] = [
                        {"name": valid_state}, {"name": unsafe_state},
                    ]
                    self.deny(q)
        for valid_state in ("estado: reservado", "estado: en revisión"):
            q = evidence()
            q["issue"]["labels"] = [{"name": valid_state}]
            mod.verify(q, SHA, NOW)

        q = evidence()
        q["issue"]["labels"] = [
            {"name": "estado: reservado"},
            {"name": "estado: en revisión"},
        ]
        self.deny(q)

    def test_task_marker_mutation_invalidates_v3_fingerprint(self):
        # A V3 pins the entire semantic task marker, not just its file paths
        # and dependencies. In particular, owner/roles/order cannot silently
        # change while the old lease remains an authorization.
        q = evidence()
        mod.verify(q, SHA, NOW)
        q["issue"]["body"] = q["issue"]["body"].replace(
            '"order": 1', '"order": 2'
        )
        self.deny(q)

    def test_acceptance_edit_invalidates_pinned_v3(self):
        # RED previo: solo se validaba el formato hex del fingerprint, no el contrato.
        q = evidence()
        mod.verify(q, SHA, NOW)
        q["issue"]["body"] = q["issue"]["body"].replace(
            "CI Validar green pero", "CI Validar fallido pero"
        )
        self.deny(q)
        q = evidence()
        q["lease_comments"][0] = comment(dict(LEASE, acceptance_sha256="b" * 64))
        self.deny(q)

    def test_renewed_v3_uuid5_is_valid(self):
        # The canonical coordinator renewal_reservation_id() uses UUIDv5.
        q = evidence()
        renewed = "18e4a094-36e8-5b80-b7ab-2244e5e47f0a"
        q["lease_comments"][0] = comment(dict(LEASE, reservation_id=renewed))
        # A rotated bot lease must also be reflected in the current PR body.
        self.deny(q)
        q["pr"]["body"] = q["pr"]["body"].replace(
            LEASE["reservation_id"], renewed)
        mod.verify(q, SHA, NOW)
        q["lease_comments"][0] = comment(dict(LEASE, reservation_id="not-a-uuid"))
        self.deny(q)

    def test_release_window_snapshot_preserves_reserved_issue(self):
        # Regression: fetching a release-window Issue must not overwrite
        # the PR's reserved task Issue in the snapshot.
        q = evidence()
        window = {"number": 921, "body": '<!-- factory-release-window {"version":1,"sha":"' + BASE + '","opened_at":"2026-10-14T01:00:00Z","expires_at":"2026-10-14T03:00:00Z"} -->'}
        root = "/repos/pl0n3r/Factory"
        paths = {
            root + "/pulls/1364": q["pr"],
            root + "/pulls/1364/files?per_page=100": q["files"],
            "/repos/pl0n3r/Factory/issues/767": q["switch"],
            root + f"/commits/{SHA}/check-runs?per_page=100&page=1": q["checks"],
            root + f"/commits/{SHA}/status": q["commit_status"],
            root + f"/commits/{SHA}/statuses?per_page=100": q["status_history"],
            root + "/pulls/1364/reviews?per_page=100": q["reviews"],
            root + "/pulls/1364/comments?per_page=100": q["comments"],
            root + "/issues/1364/comments?per_page=100": q["lease_comments"],
            root + "/issues/1364": q["issue"],
            root + "/issues/1295": q["dependencies"][0],
            root + "/issues/1321": q["dependencies"][1],
            root + "/branches/main": {"commit": {"sha": BASE}},
            root + f"/compare/{BASE}...{SHA}": q["compare"],
            root + "/issues/921/comments?per_page=100": [],
        }
        def fake_get(_token, path, *, include_link=False):
            if path.startswith("/search/issues?"):
                unrelated = {"number": 922, "body": "Documentation: factory-release-window reference only"}
                return {"incomplete_results": False, "total_count": 2,
                        "items": [window, unrelated]}
            # REST list endpoints expose an id for comments/reviews; PR files
            # instead use filename. Existing pure fixtures omit numeric IDs.
            value = deepcopy(paths[path if "/check-runs?" in path else path.replace("&page=1", "")])
            if type(value) is list and "/files?" not in path:
                for i, item in enumerate(value):
                    item.setdefault("id", 50000 + i)
            return (value, False) if include_link else value

        with patch.object(mod, "get", side_effect=fake_get):
            actual = mod.snapshot("dummy", 1364, SHA)
        self.assertEqual(actual["issue"]["number"], 1364)
        self.assertEqual(actual["windows"][0]["issue"]["number"], 921)
        self.assertEqual(len(actual["windows"]), 1)
        mod.verify(actual, SHA, NOW)

    def test_retried_checks_select_latest_id_fail_closed(self):
        # GitHub returns several attempts of a check with the same name and SHA.
        # Old failed check followed by a later success is a valid retried build.
        q = evidence()
        q["checks"]["check_runs"].append(dict(q["checks"]["check_runs"][0],
                                             id=300, status="completed", conclusion="success"))
        q["checks"]["check_runs"][0]["conclusion"] = "failure"
        q["checks"]["total_count"] += 1
        mod.verify(q, SHA, NOW)
        # A newer failure or non-terminal retry must reject an older success.
        for status, conclusion in (("completed", "failure"), ("in_progress", None)):
            q = evidence()
            q["checks"]["check_runs"].append(dict(q["checks"]["check_runs"][0],
                                                 id=300, status=status, conclusion=conclusion))
            q["checks"]["total_count"] += 1
            self.deny(q)
        # Two attempts with equal IDs cannot prove which is current.
        q = evidence()
        q["checks"]["check_runs"].append(deepcopy(q["checks"]["check_runs"][0]))
        q["checks"]["total_count"] += 1
        self.deny(q)
        # Malformed run IDs make the evidence unknowable.
        for invalid in (None, True, "101", -1):
            q = evidence()
            q["checks"]["check_runs"][0]["id"] = invalid
            self.deny(q)

    def test_required_check_provenance_cannot_be_spoofed(self):
        # Live Factory check-runs #1373: Validar/Coverage/Analysis Method
        # belong to github-actions, Sonar to sonarqubecloud and CodeQL to
        # github-advanced-security. A matching name/result is not authority.
        mod.verify(evidence(), SHA, NOW)
        for name in mod.REQUIRED:
            for altered in ({"slug": "other-app"}, {"slug": "github-actions"},
                            {}, None, {"slug": "sonarqubecloud"}):
                q = evidence()
                expected_app = next(row["app"]["slug"] for row in q["checks"]["check_runs"]
                                    if row["name"] == name)
                if altered == {"slug": expected_app}:
                    continue
                row = next(row for row in q["checks"]["check_runs"] if row["name"] == name)
                row["app"] = altered
                with self.subTest(check=name, app=altered):
                    self.deny(q)
        q = evidence()
        q["checks"]["check_runs"][0].pop("app")
        self.deny(q)
        # A newer spoof must not override an older success from a trusted app.
        q = evidence()
        forged = deepcopy(q["checks"]["check_runs"][0])
        forged.update(id=500, app={"slug": "other-app"})
        q["checks"]["check_runs"].append(forged)
        q["checks"]["total_count"] += 1
        self.deny(q)

    def test_release_terminal_execution_must_not_precede_window(self):
        # A terminal marker for an earlier execution is not authority to
        # unlock a release window that did not exist at that timestamp.
        gate = {"version": 1, "sha": BASE,
                "opened_at": "2026-10-14T03:30:00Z",
                "expires_at": "2026-10-14T05:00:00Z"}
        for executed_at in ("2026-10-14T03:00:00Z",
                            "2026-10-13T22:00:00-05:00"):
            with self.subTest(executed_at=executed_at):
                q = evidence()
                terminal = {"version": 1, "sha": BASE, "run_id": 123,
                            "executed_at": executed_at}
                q["windows"] = [{
                    "issue": {"body": "<!-- factory-release-window "
                              + json.dumps(gate) + " -->"},
                    "comments": [{"user": {"login": "github-actions[bot]"},
                                  "body": "<!-- factory-release-executed "
                                          + json.dumps(terminal) + " -->"}]}]
                self.deny(q)
        # A verified terminal event occurring within its actual window may
        # still unlock that specific window. Do not regress that path.
        q = evidence()
        terminal = {"version": 1, "sha": BASE, "run_id": 123,
                    "executed_at": "2026-10-14T03:59:00Z"}
        q["windows"] = [{
            "issue": {"body": "<!-- factory-release-window "
                      + json.dumps(gate) + " -->"},
            "comments": [{"user": {"login": "github-actions[bot]"},
                          "body": "<!-- factory-release-executed "
                                  + json.dumps(terminal) + " -->"}]}]
        mod.verify(q, SHA, NOW)

    def test_release_titled_spaced_window_is_discovered_and_denied(self):
        """The literal marker search alone misses malformed titled release gates."""
        from urllib.parse import unquote
        q = evidence()
        root = "/repos/pl0n3r/Factory"
        malformed = {"number": 923, "title": (
            "decisión en espera: Factory v1.0.36 sobre HEAD exacto deadbeef"),
            "body": '<!-- factory - release - window '
                    + json.dumps({"version": 1, "sha": BASE,
                                  "opened_at": "2026-10-14T03:00:00Z",
                                  "expires_at": "2026-10-14T05:00:00Z"}) + ' -->'}
        queried = []
        def fake_get(_token, path):
            if path.startswith("/search/issues?"):
                query = unquote(path)
                queried.append(query)
                found = [malformed] if '"decisión en espera" in:title' in query else []
                return {"incomplete_results": False, "total_count": len(found),
                        "items": found}
            if path == root + "/pulls/1364": return q["pr"]
            if path == "/repos/pl0n3r/Factory/issues/767": return q["switch"]
            if path == root + "/issues/1364": return q["issue"]
            if path == root + f"/commits/{SHA}/status": return q["commit_status"]
            if path == root + "/issues/1295": return q["dependencies"][0]
            if path == root + "/issues/1321": return q["dependencies"][1]
            if path == root + "/branches/main": return {"commit": {"sha": BASE}}
            if path == root + f"/compare/{BASE}...{SHA}": return q["compare"]
            raise AssertionError("Unexpected authenticated path: " + path)
        collections = {
            root + "/pulls/1364/files": q["files"],
            root + f"/commits/{SHA}/statuses": q["status_history"],
            root + "/pulls/1364/reviews": q["reviews"],
            root + "/pulls/1364/comments": q["comments"],
            root + "/issues/1364/comments": q["lease_comments"],
            root + "/issues/923/comments": [],
        }
        with patch.object(mod, "get", side_effect=fake_get), \
                patch.object(mod, "get_check_runs", return_value=q["checks"]), \
                patch.object(mod, "get_paginated_records", side_effect=lambda _t, path: deepcopy(collections[path])):
            got = mod.snapshot("token", 1364, SHA)
        self.assertEqual(len(queried), 2)
        self.assertIn(923, [w["issue"]["number"] for w in got["windows"]])
        self.deny(got)

    def test_release_spaced_window_intent_cannot_disappear(self):
        """A malformed/spaced authority marker cannot be interpreted as no freeze."""
        q = evidence()
        q["windows"] = [{"issue": {
            "number": 923, "body": '<!-- factory - release - window '
            + json.dumps({"version": 1, "sha": BASE,
                          "opened_at": "2026-10-14T03:00:00Z",
                          "expires_at": "2026-10-14T05:00:00Z"}) + ' -->'},
            "comments": []}]
        self.deny(q)

    def test_release_window_canonical_schema_and_ttl_fail_closed(self):
        # The canonical release_window.py::_window_from_body requires opened_at,
        # exactly four fields, timezone-aware ordered timestamps and TTL <= 120m.
        # An invalid already-expired marker must not silently unlock auto-merge.
        def window(data):
            q = evidence()
            q["windows"] = [{"issue": {"body": "<!-- factory-release-window "
                                    + json.dumps(data) + " -->"}, "comments": []}]
            return q

        import json
        valid = {"version": 1, "sha": BASE, "opened_at": "2026-10-14T00:00:00Z",
                 "expires_at": "2026-10-14T02:00:00Z"}
        mod.verify(window(valid), SHA, NOW)  # a genuinely expired window
        invalids = [
            {"version": 1, "sha": BASE, "expires_at": "2026-10-14T02:00:00Z"},
            {**valid, "opened_at": "2026-10-14T03:00:00Z"},
            {**valid, "opened_at": "2026-10-13T20:00:00Z"},
            {**valid, "opened_at": "2026-10-14T00:00:00"},
            {**valid, "expires_at": "2026-10-14T02:00:00"},
            {**valid, "untrusted_extension": False},
            {**valid, "version": True},
        ]
        for i, gate in enumerate(invalids):
            with self.subTest(case=i):
                self.deny(window(gate))
        active = dict(valid, opened_at="2026-10-14T03:00:00Z",
                      expires_at="2026-10-14T05:00:00Z")
        self.deny(window(active))

    def test_checks_and_review_evidence_fail_closed(self):
        q = evidence(); q["checks"]["total_count"] += 1; self.deny(q)
        q = evidence(); q["checks"]["check_runs"][0]["conclusion"] = "failure"; self.deny(q)
        q = evidence(); q["checks"]["check_runs"][0]["status"] = "in_progress"; self.deny(q)
        q = evidence(); q["checks"]["check_runs"][0]["head_sha"] = BASE; self.deny(q)
        q = evidence(); q["reviews"] = None; self.deny(q)
        q = evidence(); q["issue_comments"] = None; self.deny(q)
        q = evidence(); q["issue_comments"] = [{"user": "unknown", "body": "ok"}]; self.deny(q)
        # An identical check run ID is ambiguous evidence, even when duplicated.
        q = evidence(); q["checks"]["check_runs"].append(deepcopy(q["checks"]["check_runs"][0])); q["checks"]["total_count"] += 1; self.deny(q)
        q = evidence(); q["windows"] = None; self.deny(q)
        q = evidence(); q["windows"] = [{"issue": {"body": "<!-- factory-release-window nope -->"}, "comments": []}]; self.deny(q)
        # El marcador terminal debe ser auténtico, íntegro y tipado: 0 y True no son run_ids.
        import json
        for changes in ({"run_id": 0}, {"version": True}, {"executed_at": "unknown"},
                        {"executed_at": "2026-10-14T04:30:00"},
                        {"executed_at": "2026-10-14T04:30:00Z"}):
            gate = {"version": 1, "sha": BASE, "opened_at": "2026-10-14T03:00:00Z", "expires_at": "2026-10-14T05:00:00Z"}
            executed = {"version": 1, "sha": BASE, "run_id": 123,
                        "executed_at": "2026-10-14T03:59:00Z"}
            executed.update(changes)
            q = evidence(); q["windows"] = [{
                "issue": {"body": "<!-- factory-release-window " + json.dumps(gate) + " -->"},
                "comments": [{"user": {"login": "github-actions[bot]"},
                              "body": "<!-- factory-release-executed " + json.dumps(executed) + " -->"}]}
            ]; self.deny(q)
        # La marca terminal correcta sí disuelve su propia ventana.
        q = evidence(); q["windows"] = [{
            "issue": {"body": '<!-- factory-release-window {"version":1,"sha":"' + BASE + '","opened_at":"2026-10-14T03:00:00Z","expires_at":"2026-10-14T05:00:00Z"} -->'},
            "comments": [{"user": {"login": "github-actions[bot]"},
                          "body": '<!-- factory-release-executed {"version":1,"sha":"' + BASE + '","run_id":123,"executed_at":"2026-10-14T03:59:00Z"} -->'}]}
        ]; mod.verify(q, SHA, NOW)
        # Una segunda marca terminal malformada NO se puede ignorar,
        # aunque coexista con una marca anterior válida.
        q = evidence(); q["windows"] = [{
            "issue": {"body": '<!-- factory-release-window {"version":1,"sha":"' + BASE + '","opened_at":"2026-10-14T03:00:00Z","expires_at":"2026-10-14T05:00:00Z"} -->'},
            "comments": [{"user": {"login": "github-actions[bot]"},
                          "body": '<!-- factory-release-executed {"version":1,"sha":"' + BASE + '","run_id":123,"executed_at":"2026-10-14T03:59:00Z"} -->'},
                         {"user": {"login": "github-actions[bot]"},
                          "body": '<!-- factory-release-executed malformed -->'}]}
        ]; self.deny(q)
        # Aunque ambos marcadores tengan formato válido, distintos run_id
        # producen un estado terminal ambiguo según release_window.py.
        q = evidence(); q["windows"] = [{
            "issue": {"body": '<!-- factory-release-window {"version":1,"sha":"' + BASE + '","opened_at":"2026-10-14T03:00:00Z","expires_at":"2026-10-14T05:00:00Z"} -->'},
            "comments": [{"user": {"login": "github-actions[bot]"},
                          "body": '<!-- factory-release-executed {"version":1,"sha":"' + BASE + '","run_id":123,"executed_at":"2026-10-14T03:59:00Z"} -->'},
                         {"user": {"login": "github-actions[bot]"},
                          "body": '<!-- factory-release-executed {"version":1,"sha":"' + BASE + '","run_id":124,"executed_at":"2026-10-14T03:59:00Z"} -->'}]}
        ]; self.deny(q)

    def test_clean_construction_only_allows_sha_locked_immediate_merge(self):
        mod.verify(evidence(), SHA, NOW)
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text(encoding="utf8")
        lines = workflow.splitlines()
        self.assertEqual(lines[1], "on:")
        self.assertIn("  pull_request:", lines)
        self.assertTrue(any(line.startswith("    if: " + chr(36) + "{{ false }}") for line in lines))
        self.assertIn("      contents: read", lines)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("python3 scripts/automerge_pr_guard.py", workflow)
        self.assertNotIn("gh api --method PUT", workflow)
        self.assertNotIn("gh pr merge", workflow)
        self.assertNotIn("MERGE_TOKEN", workflow)
        self.assertNotIn("AUTOMERGE_TOKEN", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
    def test_final_guard_runs_after_collision_check_and_before_merge(self):
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text()
        self.assertTrue(any(line.startswith("    if: " + chr(36) + "{{ false }}") for line in workflow.splitlines()))
        self.assertNotIn("python3 scripts/automerge_pr_guard.py", workflow)
        self.assertNotIn("python3 scripts/coordinar_trabajo.py validar-pr", workflow)
        self.assertNotIn("gh api --method PUT", workflow)
        self.assertNotIn("gh pr merge", workflow)
    def test_coordinator_claim_collisions_are_blocked_before_merge(self):
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text(encoding="utf8")
        self.assertTrue(any(line.startswith("    if: " + chr(36) + "{{ false }}") for line in workflow.splitlines()))
        self.assertNotIn("python3 scripts/coordinar_trabajo.py validar-pr", workflow)
        self.assertNotIn("gh api --method PUT", workflow)
        self.assertNotIn("gh pr merge", workflow)
        self.assertNotIn("MERGE_TOKEN", workflow)
    def test_event_resolvers_fail_closed(self):
        # Accept canonical event fixtures first; each negative case below
        # changes exactly one field so that the intended gate is exercised.
        review = pull_request_review_event_example()
        self.assertEqual(
            mod.validate_pull_request_review_event(review),
            (1375, "trabajo/issue-1364"),
        )
        for field, value in (("action", "dismissed"),
                             ("action", "synchronize")):
            changed = deepcopy(review)
            changed[field] = value
            with self.subTest(source="pull_request_review", field=field, value=value):
                with self.assertRaises(mod.Denied):
                    mod.validate_pull_request_review_event(changed)
        with self.assertRaises(mod.Denied):
            mod.validate_pull_request_review_event({})

        run = workflow_run_event_example()
        self.assertEqual(
            mod.validate_workflow_run_event(run),
            (1364, "trabajo/issue-1364"),
        )
        for field, value in (("event", "push"),
                             ("conclusion", "failure"),
                             ("status", "in_progress"),
                             ("name", "Untrusted workflow")):
            changed = deepcopy(run)
            changed["workflow_run"][field] = value
            with self.subTest(source="workflow_run", field=field, value=value):
                with self.assertRaises(mod.Denied):
                    mod.validate_workflow_run_event(changed)
        with self.assertRaises(mod.Denied):
            mod.validate_workflow_run_event({})


def pull_request_review_event_example():
    return {
        "action": "submitted",
        "repository": {"full_name": "pl0n3r/Factory", "default_branch": "main"},
        "review": {"state": "commented", "user": {"login": "coderabbitai[bot]"}},
        "pull_request": {"number": 1375, "state": "open", "draft": False,
                         "head": {"ref": "trabajo/issue-1364", "sha": "c" * 40,
                                  "repo": {"full_name": "pl0n3r/Factory", "fork": False}},
                         "base": {"ref": "main"}},
    }


class PullRequestReviewEventTests(unittest.TestCase):
    def test_review_submission_resolves_current_authenticated_head(self):
        pr = {"number": 1375, "state": "open", "draft": False,
              "head": {"ref": "trabajo/issue-1364", "sha": SHA,
                       "repo": {"full_name": "pl0n3r/Factory", "fork": False}},
              "base": {"ref": "main"}}
        event = pull_request_review_event_example()
        with patch.object(mod, "get", return_value=pr) as get:
            self.assertEqual(mod.resolve_pull_request_review("token", event), (1375, SHA))
        get.assert_called_once_with("token", "/repos/pl0n3r/Factory/pulls/1375")
        self.assertNotEqual(event["pull_request"]["head"]["sha"], SHA)

    def test_review_event_and_pr_identity_fail_closed(self):
        def deny(event):
            with self.assertRaises(mod.Denied):
                mod.validate_pull_request_review_event(event)
        mutations = [
            ("action", "dismissed"),
            ("repository", {"full_name": "attacker/fork", "default_branch": "main"}),
            ("repository", {"full_name": "pl0n3r/Factory", "default_branch": "unsafe"}),
            ("review", None),
            ("review", {"state": "unknown", "user": {"login": "tester"}}),
            ("review", {"state": ["commented"], "user": {"login": "tester"}}),
            ("review", {"state": "commented"}),
        ]
        for field, value in mutations:
            event = pull_request_review_event_example()
            event[field] = value
            with self.subTest(field=field, value=value):
                deny(event)
        mutations = [
            ("number", True), ("number", 0), ("state", "closed"), ("draft", True),
            ("head", {"ref": "not-canonical", "sha": SHA,
                      "repo": {"full_name": "pl0n3r/Factory", "fork": False}}),
            ("head", {"ref": "trabajo/issue-1364", "sha": "bad",
                      "repo": {"full_name": "pl0n3r/Factory", "fork": False}}),
            ("head", {"ref": "trabajo/issue-1364", "sha": SHA,
                      "repo": {"full_name": "attacker/fork", "fork": True}}),
            ("base", {"ref": "release"}),
        ]
        for field, value in mutations:
            event = pull_request_review_event_example()
            event["pull_request"][field] = value
            with self.subTest(pr_field=field, value=value):
                deny(event)

    def test_review_old_webhook_cannot_authorize_changed_pr(self):
        event = pull_request_review_event_example()
        pr = {"number": 1375, "state": "open", "draft": False,
              "head": {"ref": "trabajo/issue-1364", "sha": SHA,
                       "repo": {"full_name": "pl0n3r/Factory", "fork": False}},
              "base": {"ref": "main"}}
        mutations = [
            ("state", "closed"), ("draft", True),
            ("head", dict(pr["head"], ref="trabajo/issue-999")),
            ("base", {"ref": "other"}),
            ("head", dict(pr["head"], sha="invalid")),
        ]
        for key, value in mutations:
            changed = deepcopy(pr)
            changed[key] = value
            with self.subTest(key=key, value=value), patch.object(mod, "get", return_value=changed):
                with self.assertRaises(mod.Denied):
                    mod.resolve_pull_request_review("token", event)


def workflow_run_event_example():
    return {
        'action': 'completed',
        'repository': {'full_name':'pl0n3r/Factory', 'default_branch':'main'},
        'workflow_run': {'name':'Sonar CI-based', 'event':'pull_request',
                         'status':'completed', 'conclusion':'success',
                         'head_repository':{'full_name':'pl0n3r/Factory'},
                         'repository':{'full_name':'pl0n3r/Factory'},
                         'head_sha':'b'*40, 'head_branch':'trabajo/issue-1364',
                         'pull_requests':[{'number':1364}]}
    }


class WorkflowRunEventTests(unittest.TestCase):
    def test_completed_ci_can_resolve_current_exact_head(self):
        pr={'number':1364,'state':'open','draft':False,
            'head':{'ref':'trabajo/issue-1364', 'sha':SHA,
                    'repo':{'full_name':'pl0n3r/Factory','fork':False}},
            'base':{'ref':'main'}}
        with patch.object(mod,'get',return_value=pr) as get:
            self.assertEqual(mod.resolve_workflow_run('test-token',workflow_run_event_example()), (1364,SHA))
        get.assert_called_once_with('test-token','/repos/pl0n3r/Factory/pulls/1364')
        # Important: workflow_run.head_sha could be the synthetic PR merge SHA.
        # The authenticated current PR head and the canonical guard decide.
        self.assertNotEqual(workflow_run_event_example()['workflow_run']['head_sha'], SHA)

    def test_workflow_run_pr_number_is_not_issue_number(self):
        """PR #1375 may close Issue #1364; GitHub allocates both independently."""
        event = workflow_run_event_example()
        event['workflow_run']['pull_requests'] = [{'number': 1375}]
        pr = {'number': 1375, 'state': 'open', 'draft': False,
              'head': {'ref': 'trabajo/issue-1364', 'sha': SHA,
                       'repo': {'full_name': 'pl0n3r/Factory', 'fork': False}},
              'base': {'ref': 'main'}}
        with patch.object(mod, 'get', return_value=pr) as get:
            self.assertEqual(mod.resolve_workflow_run('token', event), (1375, SHA))
        get.assert_called_once_with('token', '/repos/pl0n3r/Factory/pulls/1375')
        # The event's PR identity must still match the REST PR; never accept
        # an event for a different PR or unrelated branch.
        bad = deepcopy(pr)
        bad['number'] = 1376
        with patch.object(mod, 'get', return_value=bad):
            with self.assertRaises(mod.Denied):
                mod.resolve_workflow_run('token', event)
        bad = deepcopy(pr)
        bad['head']['ref'] = 'trabajo/issue-1375'
        with patch.object(mod, 'get', return_value=bad):
            with self.assertRaises(mod.Denied):
                mod.resolve_workflow_run('token', event)

    def test_incomplete_untrusted_and_non_pr_runs_denied(self):
        def deny(event):
            with self.assertRaises(mod.Denied):
                mod.validate_workflow_run_event(event)
        for field,value in [('name','untrusted'),('event','push'),
                            ('status','in_progress'),('conclusion','failure'),
                            ('head_branch','not-canonical'),('head_sha','invalid'),
                            ('pull_requests',[]),('pull_requests',[{'number':1364},{'number':1365}]),
                            ('pull_requests',[{'number':0}]),
                            ('head_repository',{'full_name':'attacker/fork'}),
                            ('repository',{'full_name':'attacker/fork'})]:
            q=workflow_run_event_example();q['workflow_run'][field]=value
            with self.subTest(field=field,value=value):deny(q)
        q=workflow_run_event_example();q['action']='requested';deny(q)
        q=workflow_run_event_example();q['repository']['default_branch']='unsafe';deny(q)
        q=workflow_run_event_example();q['repository']['full_name']='attacker/fork';deny(q)
        q=workflow_run_event_example();q['workflow_run']['pull_requests']=[{'number':True}];deny(q)

    def test_current_pr_mutation_never_inherits_old_ci_authority(self):
        pr={'number':1364,'state':'open','draft':False,
            'head':{'ref':'trabajo/issue-1364','sha':SHA,
                    'repo':{'full_name':'pl0n3r/Factory','fork':False}},
            'base':{'ref':'main'}}
        for path, val in [('state','closed'), ('draft',True), ('head',dict(pr['head'],ref='trabajo/issue-999')),
                          ('base',{'ref':'other'}),('head',dict(pr['head'],sha='invalid'))]:
            q=deepcopy(pr);q[path]=val
            with self.subTest(path=path,value=val):
                with patch.object(mod,'get',return_value=q):
                    with self.assertRaises(mod.Denied):
                        mod.resolve_workflow_run('token',workflow_run_event_example())

    def test_workflow_run_uses_actual_factory_workflow_names(self):
        expected = {"CI factory", "Sonar CI-based", "Evidencia CodeQL"}
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text()
        self.assertEqual(mod.TRUSTED_WORKFLOW_RUNS, expected)
        self.assertIn("workflow_run:", workflow)
        self.assertIn("    if: ${{ false }}", workflow)
        for name in expected:
            event = workflow_run_event_example()
            event["workflow_run"]["name"] = name
            self.assertEqual(mod.validate_workflow_run_event(event), (1364, "trabajo/issue-1364"))
        self.assertNotIn('"CodeQL"', workflow)
    def test_workflow_never_executes_untrusted_head(self):
        workflow = (ROOT / ".github/workflows/automerge.yml").read_text()
        lines = workflow.splitlines()
        self.assertEqual(lines[1], "on:")
        self.assertIn("  pull_request:", lines)
        self.assertTrue(any(line.startswith("    if: " + chr(36) + "{{ false }}") for line in lines))
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("scripts/automerge_pr_guard.py", workflow)
        self.assertNotIn("gh api --method PUT", workflow)
        self.assertNotIn("gh pr merge", workflow)
        self.assertNotIn("MERGE_TOKEN", workflow)
        self.assertNotIn("secrets.", workflow)

class MainCliContractTests(unittest.TestCase):
    """Exercise the real entrypoint contract; mock I/O, not its gate semantics."""

    def test_main_double_checks_exact_head_and_denies_mutation(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from unittest.mock import call
        import os
        import sys

        env = {"GH_TOKEN": "test-token", "GITHUB_REPOSITORY": "pl0n3r/Factory",
               "PR_NUMBER": "1375", "PR_SHA": SHA}
        stdout = StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["guard"]), \
             patch.object(mod, "snapshot", return_value=evidence()) as snapshot, \
             patch.object(mod, "verify") as verify, redirect_stdout(stdout):
            self.assertEqual(mod.main(), 0)
        self.assertEqual(stdout.getvalue(), "AUTOMERGE_PREFLIGHT_OK " + SHA + "\n")
        self.assertEqual(snapshot.call_args_list, [call("test-token", 1375, SHA)] * 2)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual([arguments.args[1] for arguments in verify.call_args_list], [SHA, SHA])

        # A failed second reading must block: first PASS must never be reused.
        stderr = StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["guard"]), \
             patch.object(mod, "snapshot", return_value=evidence()) as snapshot, \
             patch.object(mod, "verify", side_effect=[None, mod.Denied("head_changed")]) as verify, \
             redirect_stderr(stderr):
            self.assertEqual(mod.main(), 1)
        self.assertIn("AUTOMERGE_DENIED: head_changed", stderr.getvalue())
        self.assertEqual(snapshot.call_count, 2)
        self.assertEqual(verify.call_count, 2)

    def test_main_never_treats_invalid_environment_as_authorization(self):
        from contextlib import redirect_stderr
        from io import StringIO
        import os
        import sys

        valid = {"GH_TOKEN": "test-token", "GITHUB_REPOSITORY": "pl0n3r/Factory",
                 "PR_NUMBER": "1375", "PR_SHA": SHA}
        for key, invalid in (("GH_TOKEN", ""), ("GITHUB_REPOSITORY", "other/repo"),
                             ("PR_NUMBER", "nan"), ("PR_NUMBER", "0"),
                             ("PR_SHA", "f" * 39)):
            env = dict(valid, **{key: invalid})
            stderr = StringIO()
            with self.subTest(key=key, invalid=invalid), patch.dict(os.environ, env, clear=True), \
                 patch.object(sys, "argv", ["guard"]), patch.object(mod, "snapshot") as snapshot, \
                 redirect_stderr(stderr):
                self.assertEqual(mod.main(), 1)
                snapshot.assert_not_called()
                self.assertIn("AUTOMERGE_DENIED:", stderr.getvalue())
        with patch.dict(os.environ, valid, clear=True), patch.object(sys, "argv", ["guard", "--unsafe"]), \
             patch.object(mod, "snapshot") as snapshot, redirect_stderr(StringIO()):
            self.assertEqual(mod.main(), 1)
            snapshot.assert_not_called()

    def test_resolver_command_rejects_missing_input_and_uses_authenticated_identity(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from tempfile import NamedTemporaryFile
        import os
        import sys

        env = {"GH_TOKEN": "test-token", "GITHUB_REPOSITORY": "pl0n3r/Factory"}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(sys, "argv", ["guard", "--resolve-workflow-run"]), \
             redirect_stderr(StringIO()):
            self.assertEqual(mod.main(), 1)  # No event input is not authorization.
        with NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as f:
            json.dump(workflow_run_event_example(), f)
            f.flush()
            stdout = StringIO()
            with patch.dict(os.environ, dict(env, GITHUB_EVENT_PATH=f.name), clear=True), \
                 patch.object(sys, "argv", ["guard", "--resolve-workflow-run"]), \
                 patch.object(mod, "resolve_workflow_run", return_value=(1375, SHA)) as resolver, \
                 redirect_stdout(stdout):
                self.assertEqual(mod.main(), 0)
            resolver.assert_called_once()
            self.assertEqual(resolver.call_args.args[0], "test-token")
            self.assertEqual(resolver.call_args.args[1]["workflow_run"]["name"], "Sonar CI-based")
            self.assertEqual(stdout.getvalue(),
                             "pr_number=1375\npr_sha=" + SHA +
                             "\npr_url=https://github.com/pl0n3r/Factory/pull/1375\n")
        with NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as f:
            json.dump(pull_request_review_event_example(), f)
            f.flush()
            stdout = StringIO()
            with patch.dict(os.environ, dict(env, GITHUB_EVENT_PATH=f.name), clear=True), \
                 patch.object(sys, "argv", ["guard", "--resolve-pull-request-review"]), \
                 patch.object(mod, "resolve_pull_request_review", return_value=(1375, SHA)) as resolver, \
                 redirect_stdout(stdout):
                self.assertEqual(mod.main(), 0)
            resolver.assert_called_once()
            self.assertEqual(resolver.call_args.args[0], "test-token")
            self.assertEqual(resolver.call_args.args[1]["action"], "submitted")
            self.assertEqual(stdout.getvalue(),
                             "pr_number=1375\npr_sha=" + SHA +
                             "\npr_url=https://github.com/pl0n3r/Factory/pull/1375\n")


class AutoMergeShellOutcomeTests(unittest.TestCase):
    """Fase 1 no contiene una sección de shell con autoridad de fusión."""

    def test_immediate_merge_authority_is_absent_in_phase_one(self):
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text()
        self.assertIn("    if: ${{ false }}", workflow)
        self.assertNotIn("gh api --method PUT", workflow)
        self.assertNotIn("gh pr merge", workflow)
        self.assertNotIn("MERGE_TOKEN", workflow)
        self.assertNotIn("AUTOMERGE_TOKEN", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)


    def test_event_triggers_are_declared_while_phase_one_stays_inert(self):
        workflow = (ROOT / ".github" / "workflows" / "automerge.yml").read_text(encoding="utf8")
        self.assertIn("if: " + chr(36) + "{{ false }}", workflow)
        for required in (
            "  pull_request:",
            "  pull_request_review:",
            "  workflow_run:",
            '"CI factory"',
            '"Sonar CI-based"',
            '"Evidencia CodeQL"',
        ):
            self.assertIn(required, workflow)
        # Event payload authorization belongs to the authenticated resolver,
        # not to a condition that would violate the literal Phase 1 contract.

if __name__ == "__main__":
    unittest.main()