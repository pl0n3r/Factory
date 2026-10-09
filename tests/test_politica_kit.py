import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts import politica_kit as policy
from scripts.politica_kit import (
    PolicyError,
    _read_bounded_lines,
    count_review_rounds,
    load_policy,
    load_reviewer_policy,
    parse_reviewer_policy,
    resolve_required_review_bot,
    validate_rate_limit_fallback,
    validate_required_bot_review,
    validate_required_bot_review_or_fallback,
    validate_rounds,
)

HEAD = "a" * 40


def review(*, review_id=1, login="coderabbitai[bot]", user_type="Bot",
           commit_id=HEAD, state="COMMENTED", body="Revisión sustantiva"):
    return json.dumps({
        "id": review_id,
        "state": state,
        "body": body,
        "commit_id": commit_id,
        "user": {"type": user_type, "login": login},
    })


def comment(*, comment_id=1, login="coderabbitai[bot]", user_type="Bot",
            source_commit=HEAD, covered_commit=HEAD, kind="reviewed",
            body_prefix="", marker=True):
    body = body_prefix
    if marker:
        payload = {
            "sourceCommitId": source_commit,
            "coveredCommitId": covered_commit,
            "kind": kind,
        }
        body += (
            "<!-- final_review_risk_coverage:"
            + json.dumps(payload, separators=(",", ":"))
            + " -->"
        )
    return json.dumps({
        "id": comment_id,
        "body": body,
        "user": {"type": user_type, "login": login},
    })


def rate_limit_comment(*, comment_id, created_at, login="coderabbitai[bot]",
                       updated_at=None, body="Review rate limited.", head_sha=None):
    if head_sha:
        body += f"\nReviewed exact HEAD {head_sha}."
    payload = {
        "id": comment_id,
        "body": body,
        "created_at": created_at,
        "user": {"type": "Bot", "login": login},
    }
    if updated_at is not None:
        payload["updated_at"] = updated_at
    return json.dumps(payload)


def owner_review_retry(*, comment_id=201, created_at="2026-10-04T05:02:00Z",
                       association="OWNER", body="@coderabbitai review"):
    return json.dumps({
        "id": comment_id,
        "body": body,
        "created_at": created_at,
        "author_association": association,
        "user": {"type": "User", "login": "pl0n3r"},
    })


def check(*, check_id, name, conclusion="success", status="completed",
          head_sha=HEAD, completed_at="2026-10-04T05:00:00Z"):
    return json.dumps({
        "id": check_id,
        "name": name,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "completed_at": completed_at,
    })


def green_gate_checks(*, head_sha=HEAD):
    names = (
        "validate",
        "SonarCloud Code Analysis",
        "CodeQL",
        "tests",
        "validar-pr / Validar coordinación",
        "privacidad / Privacidad como código",
    )
    return [
        check(check_id=index, name=name, head_sha=head_sha)
        for index, name in enumerate(names, start=10)
    ]


def review_thread(*, resolved=False, login="coderabbitai"):
    return json.dumps({
        "isResolved": resolved,
        "comments": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [{"author": {"login": login}}],
        },
    })



def sha_less_fixture():
    """Secuencia reducida de GrindFlow #413, con payloads reales de timeline REST."""
    prior = json.loads(rate_limit_comment(
        comment_id=200, created_at="2026-10-04T05:00:00Z",
    ))
    owner = json.loads(owner_review_retry(
        comment_id=201, created_at="2026-10-04T05:02:00Z",
    ))
    bot = json.loads(rate_limit_comment(
        comment_id=202, created_at="2026-10-04T05:02:08Z",
        updated_at="2026-10-04T05:02:19Z",
        body=("<!-- This is an auto-generated reply by CodeRabbit -->\n"
              "<!-- CodeRabbit review command invocation: v2:sample -->\n"
              "Review rate limited."),
    ))
    comments = [json.dumps(owner), json.dumps(bot), json.dumps(prior)]

    def event(item):
        return {
            "event": "commented", "id": item["id"], "body": item["body"],
            "created_at": item["created_at"],
            "author_association": item.get("author_association", "NONE"),
            "user": item["user"],
            "actor": {"login": item["user"]["login"]},
        }

    timeline = [
        {"event": "committed", "sha": "b" * 40},
        {"event": "committed", "sha": HEAD},
        event(prior),
        event(owner),
        {"event": "mentioned", "actor": {"login": "coderabbitai"}},
        event(bot),
    ]
    return comments, timeline


def sha_less_validate(comments, timeline, *, phase="construccion",
                      checks=None, reviews=None, threads=None, run_attempt=2):
    return validate_rate_limit_fallback(
        required_review_bot="coderabbitai[bot]",
        head_sha=HEAD,
        head_committed_at="2026-10-04T04:59:00Z",
        phase=phase,
        review_lines=reviews if reviews is not None else [],
        comment_lines=comments,
        check_lines=checks if checks is not None else green_gate_checks(),
        thread_lines=threads if threads is not None else [],
        timeline_lines=([json.dumps(event) for event in timeline]
                        if timeline is not None else None),
        run_attempt=run_attempt,
    )


class T(unittest.TestCase):
    def test_sha_less_rate_limit_accepts_only_authenticated_timeline_exact_head_owner_retry(self):
        comments, timeline = sha_less_fixture()
        self.assertEqual(sha_less_validate(comments, timeline),
                         (202, "2026-10-04T05:02:08Z"))
        # La misma respuesta del bot, sin timeline, nunca habilita fallback.
        with self.assertRaises(PolicyError):
            sha_less_validate(comments, None)
        # La ruta alternativa no está disponible en el primer intento.
        with self.assertRaises(PolicyError):
            sha_less_validate(comments, timeline, run_attempt=1)

    def test_sha_less_rate_limit_rejects_stale_head_force_push_missing_timeline_and_non_owner(self):
        comments, events = sha_less_fixture()
        cases = {}
        stale = [dict(x) for x in events]
        stale[1] = {"event": "committed", "sha": "c" * 40}
        cases["HEAD antiguo"] = (comments, stale)
        force = [dict(x) for x in events]
        force.insert(3, {"event": "head_ref_force_pushed", "sha": HEAD})
        cases["force push"] = (comments, force)
        previous = [dict(x) for x in events]
        previous.append({"event": "committed", "sha": HEAD})
        cases["respuestas anteriores a HEAD"] = (comments, previous)
        cases["timeline ausente"] = (comments, None)
        cases["timeline vacía"] = (comments, [])
        cases["timeline truncada"] = (comments, events[2:])
        cases["comentario falso"] = (comments, events[:-1] + [
            {**events[-1], "actor": {"login": "pl0n3r"}}])
        cases["timestamp incoherente"] = (comments, events[:-1] + [
            {**events[-1], "created_at": "2026-10-04T05:01:00Z"}])
        owner = json.loads(comments[0])
        owner["author_association"] = "MEMBER"
        cases["reintento no OWNER"] = ([json.dumps(owner), comments[1]], events)
        bot = json.loads(comments[1])
        bot["user"]["type"] = "User"
        cases["respuesta fabricada"] = ([comments[0], json.dumps(bot)], events)
        for label, (candidate_comments, candidate_timeline) in cases.items():
            with self.subTest(label=label), self.assertRaises(PolicyError):
                sha_less_validate(candidate_comments, candidate_timeline)

    def test_sha_less_rate_limit_rejects_missing_initial_rate_limit_and_ambiguous_triggers(self):
        comments, events = sha_less_fixture()
        # Sin rate-limit inicial previo al comando OWNER.
        no_initial = [e for e in events if e.get("id") != 200]
        no_initial_comments = [c for c in comments if json.loads(c)["id"] != 200]
        with self.assertRaises(PolicyError):
            sha_less_validate(no_initial_comments, no_initial)
        # Dos comandos OWNER competidores.
        owner = json.loads(comments[0])
        second = {**owner, "id": 203, "created_at": "2026-10-04T05:02:03Z"}
        extra = dict(events[3], id=203, created_at="2026-10-04T05:02:03Z")
        with self.subTest(label="múltiples OWNER"), self.assertRaises(PolicyError):
            sha_less_validate(comments + [json.dumps(second)],
                              events[:4] + [extra] + events[4:])
        # Trigger OWNER editado después de publicarse.
        edited = {**owner, "updated_at": "2026-10-04T05:03:00Z"}
        with self.subTest(label="OWNER editado"), self.assertRaises(PolicyError):
            sha_less_validate([json.dumps(edited), comments[1], comments[2]], events)
        # Respuesta fuera de la ventana de 120 s.
        late = json.loads(comments[1])
        late["created_at"] = "2026-10-04T05:09:00Z"
        late_event = dict(events[-1], created_at="2026-10-04T05:09:00Z")
        with self.subTest(label="respuesta tardía"), self.assertRaises(PolicyError):
            sha_less_validate([comments[0], json.dumps(late), comments[2]],
                              events[:-1] + [late_event])

    def test_marker_exact_head_con_rate_limit_en_el_cuerpo_no_cuenta_como_cobertura(self):
        marker = ('<!-- final_review_risk_coverage:{"sourceCommitId":"' + "b" * 40
                  + '","coveredCommitId":"' + HEAD + '","kind":"reviewed"} -->')
        contradictory = {
            "user": {"type": "Bot", "login": "coderabbitai[bot]"},
            "body": "Review rate limited.\n" + marker,
        }
        from scripts.politica_kit import _comment_has_exact_head_coverage
        self.assertFalse(_comment_has_exact_head_coverage(
            contradictory, required_review_bot="coderabbitai[bot]", head_sha=HEAD))

    def test_sha_less_rate_limit_rejects_live_open_findings_and_red_gates(self):
        comments, timeline = sha_less_fixture()
        conditions = (
            {"phase": "live"},
            {"threads": [review_thread()]},
            {"checks": green_gate_checks() + [
                check(check_id=200, name="CodeQL", conclusion="failure")]},
            {"reviews": [review(state="CHANGES_REQUESTED")]},
            {"checks": green_gate_checks() + [
                check(check_id=200, name="SonarCloud Code Analysis",
                      status="in_progress", conclusion=None)]},
        )
        for args in conditions:
            with self.subTest(args=args), self.assertRaises(PolicyError):
                sha_less_validate(comments, timeline, **args)

    def test_empty_commented_bot_reviews_do_not_count(self):
        lines = [
            review(review_id=1, body="**Actionable comments posted: 2**"),
            review(review_id=2, body=""),
            review(review_id=3, body="   "),
        ]
        self.assertEqual(count_review_rounds(lines), 1)

    def test_substantive_and_terminal_bot_reviews_count(self):
        lines = [
            review(review_id=1, login="review-bot", body="Hallazgo accionable"),
            review(review_id=2, login="review-bot", state="APPROVED", body=""),
            review(review_id=3, login="review-bot", state="CHANGES_REQUESTED", body=""),
        ]
        self.assertEqual(count_review_rounds(lines), 3)
        self.assertEqual(count_review_rounds(lines + [lines[-1]]), 3)

    def test_real_round_limit_still_fails_closed(self):
        lines = [review(review_id=i, login="review-bot", body=f"Hallazgo {i}") for i in (1, 2, 3, 4)]
        rounds = count_review_rounds(lines)
        self.assertEqual(rounds, 4)
        with self.assertRaises(PolicyError):
            validate_rounds(rounds, 3)

    def test_required_bot_review_on_exact_head_passes(self):
        validate_required_bot_review([review()], "coderabbitai[bot]", HEAD)

    def test_required_bot_comment_coverage_on_exact_head_passes(self):
        validate_required_bot_review(
            [],
            "coderabbitai[bot]",
            HEAD,
            comment_lines=[comment()],
        )

    def test_required_bot_comment_rejects_stale_malformed_rate_limit_or_wrong_bot(self):
        malformed = json.dumps({
            "id": 7,
            "body": (
                '<!-- final_review_risk_coverage:'
                '{"sourceCommitId":"bad","coveredCommitId":"' + HEAD + '","kind":"reviewed"} -->'
            ),
            "user": {"type": "Bot", "login": "coderabbitai[bot]"},
        })
        cases = (
            [comment(covered_commit="b" * 40)],
            [malformed],
            [comment(login="other-bot")],
            [comment(user_type="User")],
            [comment(kind="summarized")],
            [comment(marker=False, body_prefix="Full review finished.")],
            [comment(marker=False, body_prefix="Review rate limited.")],
        )
        for comment_lines in cases:
            with self.subTest(comment_lines=comment_lines):
                with self.assertRaises(PolicyError):
                    validate_required_bot_review(
                        [],
                        "coderabbitai[bot]",
                        HEAD,
                        comment_lines=comment_lines,
                    )

    def test_required_bot_review_rejects_missing_wrong_non_bot_or_stale(self):
        cases = (
            [],
            [review(login="other-bot")],
            [review(user_type="User")],
            [review(commit_id="b" * 40)],
            [review(state="CHANGES_REQUESTED", body="Hallazgo pendiente")],
            [review(state="DISMISSED")],
        )
        for lines in cases:
            with self.subTest(lines=lines):
                with self.assertRaises(PolicyError):
                    validate_required_bot_review(lines, "coderabbitai[bot]", HEAD)

    def test_base_required_reviewer_cannot_be_disabled_by_empty_caller(self):
        base = parse_reviewer_policy(json.dumps({
            "version": 1, "required_review_bot": "coderabbitai[bot]"
        }))
        self.assertEqual(
            resolve_required_review_bot(base, ""),
            "coderabbitai[bot]",
        )
        with self.assertRaises(PolicyError):
            validate_required_bot_review([], resolve_required_review_bot(base, ""), HEAD)

    def test_base_required_reviewer_rejects_mismatch_or_candidate_downgrade(self):
        base = parse_reviewer_policy(json.dumps({
            "version": 1, "required_review_bot": "coderabbitai[bot]"
        }))
        with self.assertRaises(PolicyError):
            resolve_required_review_bot(base, "other-bot")
        self.assertEqual(resolve_required_review_bot(base, ""), "coderabbitai[bot]")

    def test_optional_reviewer_preserves_backward_compatibility_without_base_requirement(self):
        self.assertEqual(parse_reviewer_policy(None), "")
        self.assertEqual(
            parse_reviewer_policy(json.dumps({"version": 1, "required_review_bot": None})),
            "",
        )
        self.assertEqual(resolve_required_review_bot("", ""), "")
        self.assertEqual(resolve_required_review_bot("", "review-bot"), "review-bot")
        lines = [review(review_id=i, login="review-bot") for i in (1, 2, 3)]
        validate_required_bot_review(lines, "", "")
        validate_rounds(count_review_rounds(lines), 3)

    def test_invalid_base_policy_fails_closed(self):
        invalid = (
            "{}",
            '{"version":2,"required_review_bot":null}',
            '{"version":1,"required_review_bot":""}',
            '{"version":1,"required_review_bot":"bad bot"}',
            '{"version":1,"required_review_bot":null,"extra":true}',
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(PolicyError):
                    parse_reviewer_policy(payload)

    def test_single_rate_limit_is_not_enough_to_pass(self):
        comments = [
            rate_limit_comment(
                comment_id=101,
                created_at="2026-10-04T05:00:00Z",
            ),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                conclusion="failure",
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False
        ) as handle:
            handle.write(json.dumps({"phase": "construccion"}))
            phase_path = Path(handle.name)
        self.addCleanup(lambda: phase_path.unlink(missing_ok=True))

        with self.assertRaisesRegex(PolicyError, "único rate limit"):
            validate_required_bot_review_or_fallback(
                [],
                "coderabbitai[bot]",
                HEAD,
                head_committed_at="2026-10-04T04:59:00Z",
                comment_lines=comments,
                check_lines=checks,
                thread_lines=[],
                phase_file=phase_path,
            )

    def test_acceptance_check_does_not_create_policy_cycle(self):
        base_checks = green_gate_checks()
        cases = (
            check(
                check_id=90,
                name=policy.ACCEPTANCE_CHECK_NAME,
                status="in_progress",
                conclusion=None,
            ),
            check(
                check_id=91,
                name=policy.ACCEPTANCE_CHECK_NAME,
                status="completed",
                conclusion="failure",
            ),
        )
        for acceptance_check in cases:
            with self.subTest(acceptance_check=acceptance_check):
                policy.validate_other_gates_green(
                    base_checks + [acceptance_check],
                    head_sha=HEAD,
                )

    def test_non_acceptance_pending_gate_still_fails_closed(self):
        checks = green_gate_checks() + [
            check(
                check_id=90,
                name="security / external gate",
                status="in_progress",
                conclusion=None,
            ),
        ]
        with self.assertRaisesRegex(PolicyError, "Check pendiente"):
            policy.validate_other_gates_green(checks, head_sha=HEAD)

    def test_independent_test_gate_remains_required_when_acceptance_is_ignored(self):
        checks = [
            line
            for line in green_gate_checks()
            if json.loads(line)["name"] != "tests"
        ]
        checks.append(
            check(
                check_id=90,
                name=policy.ACCEPTANCE_CHECK_NAME,
                status="completed",
                conclusion="success",
            )
        )
        with self.assertRaisesRegex(PolicyError, "tests"):
            policy.validate_other_gates_green(checks, head_sha=HEAD)

    def test_rate_limit_plus_failed_retry_passes_in_construction_when_other_gates_green(self):
        comments = [
            rate_limit_comment(
                comment_id=101,
                created_at="2026-10-04T05:00:00Z",
            ),
            rate_limit_comment(
                comment_id=102,
                created_at="2026-10-04T05:02:00Z",
            ),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                conclusion="failure",
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False
        ) as handle:
            handle.write(json.dumps({"phase": "construccion"}))
            phase_path = Path(handle.name)
        self.addCleanup(lambda: phase_path.unlink(missing_ok=True))

        result = validate_required_bot_review_or_fallback(
            [],
            "coderabbitai[bot]",
            HEAD,
            head_committed_at="2026-10-04T04:59:00Z",
            comment_lines=comments,
            check_lines=checks,
            thread_lines=[],
            phase_file=phase_path,
        )
        self.assertTrue(result["review_fallback"])
        self.assertEqual(result["rate_limit_comment_id"], 102)
        self.assertEqual(
            result["rate_limit_created_at"],
            "2026-10-04T05:02:00Z",
        )
        self.assertEqual(result["phase"], "construccion")

    def test_in_place_rate_limit_update_plus_owner_retry_passes_in_construction(self):
        comments = [
            rate_limit_comment(
                comment_id=101,
                created_at="2026-10-04T04:50:00Z",
                updated_at="2026-10-04T05:03:00Z",
                body="Review limit reached.",
                head_sha=HEAD,
            ),
            owner_review_retry(),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                conclusion="failure",
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]
        result = validate_rate_limit_fallback(
            required_review_bot="coderabbitai[bot]",
            head_sha=HEAD,
            head_committed_at="2026-10-04T04:59:00Z",
            phase="construccion",
            review_lines=[],
            comment_lines=comments,
            check_lines=checks,
            thread_lines=[],
        )
        self.assertEqual(result, (101, "2026-10-04T05:03:00Z"))

    def test_rerun_attempt_accepts_owner_retry_and_exact_head_rate_limit_without_visible_old_policy_failure(self):
        comments = [
            owner_review_retry(created_at="2026-10-04T05:02:00Z"),
            rate_limit_comment(
                comment_id=301,
                created_at="2026-10-04T05:03:00Z",
                head_sha=HEAD,
            ),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                status="in_progress",
                conclusion=None,
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False
        ) as handle:
            handle.write(json.dumps({"phase": "construccion"}))
            phase_path = Path(handle.name)
        self.addCleanup(lambda: phase_path.unlink(missing_ok=True))

        result = validate_required_bot_review_or_fallback(
            [],
            "coderabbitai[bot]",
            HEAD,
            head_committed_at="2026-10-04T04:59:00Z",
            comment_lines=comments,
            check_lines=checks,
            thread_lines=[],
            phase_file=phase_path,
            run_attempt=2,
        )
        self.assertTrue(result["review_fallback"])
        self.assertEqual(result["rate_limit_comment_id"], 301)
        self.assertEqual(result["rate_limit_created_at"], "2026-10-04T05:03:00Z")

    def test_first_attempt_still_requires_visible_failed_policy_check(self):
        comments = [
            owner_review_retry(created_at="2026-10-04T05:02:00Z"),
            rate_limit_comment(
                comment_id=301,
                created_at="2026-10-04T05:03:00Z",
                head_sha=HEAD,
            ),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                status="in_progress",
                conclusion=None,
            ),
        ]
        with self.assertRaises(PolicyError):
            validate_rate_limit_fallback(
                required_review_bot="coderabbitai[bot]",
                head_sha=HEAD,
                head_committed_at="2026-10-04T04:59:00Z",
                phase="construccion",
                review_lines=[],
                comment_lines=comments,
                check_lines=checks,
                thread_lines=[],
                run_attempt=1,
            )

    def test_rerun_attempt_without_owner_retry_or_exact_head_rate_limit_fails_closed(self):
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                status="in_progress",
                conclusion=None,
            ),
        ]
        valid_owner = owner_review_retry(created_at="2026-10-04T05:02:00Z")
        valid_rate = rate_limit_comment(
            comment_id=301,
            created_at="2026-10-04T05:03:00Z",
            head_sha=HEAD,
        )
        cases = (
            {
                "comments": [valid_rate],
                "reviews": [],
                "threads": [],
                "phase": "construccion",
                "checks": checks,
            },
            {
                "comments": [
                    owner_review_retry(association="MEMBER"),
                    valid_rate,
                ],
                "reviews": [],
                "threads": [],
                "phase": "construccion",
                "checks": checks,
            },
            {
                "comments": [
                    valid_owner,
                    rate_limit_comment(
                        comment_id=302,
                        created_at="2026-10-04T05:03:00Z",
                    ),
                ],
                "reviews": [],
                "threads": [],
                "phase": "construccion",
                "checks": checks,
            },
            {
                "comments": [
                    valid_owner,
                    rate_limit_comment(
                        comment_id=303,
                        created_at="2026-10-04T05:01:00Z",
                        head_sha=HEAD,
                    ),
                ],
                "reviews": [],
                "threads": [],
                "phase": "construccion",
                "checks": checks,
            },
            {
                "comments": [valid_owner, valid_rate],
                "reviews": [],
                "threads": [review_thread()],
                "phase": "construccion",
                "checks": checks,
            },
            {
                "comments": [valid_owner, valid_rate],
                "reviews": [
                    review(
                        review_id=77,
                        state="CHANGES_REQUESTED",
                        body="Finding bloqueante",
                    )
                ],
                "threads": [],
                "phase": "construccion",
                "checks": checks,
            },
            {
                "comments": [valid_owner, valid_rate],
                "reviews": [],
                "threads": [],
                "phase": "live",
                "checks": checks,
            },
            {
                "comments": [valid_owner, valid_rate],
                "reviews": [],
                "threads": [],
                "phase": "construccion",
                "checks": checks + [
                    check(
                        check_id=120,
                        name="security / external gate",
                        conclusion="failure",
                    )
                ],
            },
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(PolicyError):
                    validate_rate_limit_fallback(
                        required_review_bot="coderabbitai[bot]",
                        head_sha=HEAD,
                        head_committed_at="2026-10-04T04:59:00Z",
                        phase=case["phase"],
                        review_lines=case["reviews"],
                        comment_lines=case["comments"],
                        check_lines=case["checks"],
                        thread_lines=case["threads"],
                        run_attempt=2,
                    )

    def test_invalid_run_attempt_fails_closed(self):
        for value in (0, -1, True, "2", None):
            with self.subTest(value=value):
                with self.assertRaises(PolicyError):
                    validate_required_bot_review_or_fallback(
                        [],
                        "",
                        "",
                        head_committed_at="",
                        comment_lines=[],
                        check_lines=[],
                        thread_lines=[],
                        phase_file=None,
                        run_attempt=value,
                    )

        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(policy._run_attempt_from_env(), 1)
        with patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "2"}, clear=True):
            self.assertEqual(policy._run_attempt_from_env(), 2)
        for raw in ("", "0", "-1", "abc"):
            with self.subTest(raw=raw):
                with patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": raw}, clear=True):
                    with self.assertRaises(PolicyError):
                        policy._run_attempt_from_env()

        class Options:
            required_review_bot = ""
            base_policy_file = ""
            head_sha = ""
            head_committed_at = ""
            comments_file = ""
            checks_file = ""
            threads_file = ""
            phase_file = ""

        fake_policy = {"version": 1, "review_round_limit": 3, "decisions": []}
        with (
            patch.object(policy, "args", return_value=Options()),
            patch.object(policy, "load_policy", return_value=fake_policy),
            patch.object(
                policy,
                "validate_required_bot_review_or_fallback",
                return_value={"review_fallback": False},
            ) as validator,
            patch("sys.stdin", __import__("io").StringIO("")),
            patch("sys.stdout", new_callable=__import__("io").StringIO),
            patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "3"}, clear=True),
        ):
            self.assertEqual(policy.main(), 0)
            self.assertEqual(validator.call_args.kwargs["run_attempt"], 3)

        with (
            patch.object(policy, "args", return_value=Options()),
            patch("sys.stdin", __import__("io").StringIO("")),
            patch("sys.stderr", new_callable=__import__("io").StringIO) as stderr,
            patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "0"}, clear=True),
        ):
            self.assertEqual(policy.main(), 1)
            self.assertIn("GITHUB_RUN_ATTEMPT", stderr.getvalue())

    def test_in_place_rate_limit_update_without_owner_retry_stays_blocked(self):
        comments = [
            rate_limit_comment(
                comment_id=101,
                created_at="2026-10-04T04:50:00Z",
                updated_at="2026-10-04T05:03:00Z",
                body="Review limit reached.",
                head_sha=HEAD,
            ),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                conclusion="failure",
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]
        with self.assertRaisesRegex(PolicyError, "OWNER"):
            validate_rate_limit_fallback(
                required_review_bot="coderabbitai[bot]",
                head_sha=HEAD,
                head_committed_at="2026-10-04T04:59:00Z",
                phase="construccion",
                review_lines=[],
                comment_lines=comments,
                check_lines=checks,
                thread_lines=[],
            )

    def test_in_place_rate_limit_rejects_stale_update_non_owner_retry_open_finding_or_live(self):
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                conclusion="failure",
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]
        valid_bot = rate_limit_comment(
            comment_id=101,
            created_at="2026-10-04T04:50:00Z",
            updated_at="2026-10-04T05:03:00Z",
            body="Review limit reached.",
            head_sha=HEAD,
        )
        cases = (
            {
                "phase": "construccion",
                "comments": [
                    rate_limit_comment(
                        comment_id=101,
                        created_at="2026-10-04T04:50:00Z",
                        updated_at="2026-10-04T05:01:30Z",
                        body="Review limit reached.",
                        head_sha=HEAD,
                    ),
                    owner_review_retry(),
                ],
                "threads": [],
            },
            {
                "phase": "construccion",
                "comments": [valid_bot, owner_review_retry(association="MEMBER")],
                "threads": [],
            },
            {
                "phase": "construccion",
                "comments": [valid_bot, owner_review_retry()],
                "threads": [review_thread()],
            },
            {
                "phase": "live",
                "comments": [valid_bot, owner_review_retry()],
                "threads": [],
            },
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(PolicyError):
                    validate_rate_limit_fallback(
                        required_review_bot="coderabbitai[bot]",
                        head_sha=HEAD,
                        head_committed_at="2026-10-04T04:59:00Z",
                        phase=case["phase"],
                        review_lines=[],
                        comment_lines=case["comments"],
                        check_lines=checks,
                        thread_lines=case["threads"],
                    )

    def test_rate_limit_fallback_never_applies_with_open_blocking_finding_or_other_phase_or_other_head(self):
        comments = [
            rate_limit_comment(
                comment_id=101,
                created_at="2026-10-04T05:00:00Z",
            ),
            rate_limit_comment(
                comment_id=102,
                created_at="2026-10-04T05:02:00Z",
            ),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                conclusion="failure",
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]

        cases = (
            {
                "phase": "construccion",
                "check_lines": checks,
                "thread_lines": [review_thread()],
            },
            {
                "phase": "live",
                "check_lines": checks,
                "thread_lines": [],
            },
            {
                "phase": "construccion",
                "check_lines": checks,
                "thread_lines": [],
                "review_lines": [
                    review(
                        review_id=77,
                        state="CHANGES_REQUESTED",
                        body="Finding bloqueante",
                    )
                ],
            },
            {
                "phase": "construccion",
                "check_lines": green_gate_checks(head_sha="b" * 40) + [
                    check(
                        check_id=99,
                        name=policy.POLICY_CHECK_NAME,
                        conclusion="failure",
                        head_sha="b" * 40,
                        completed_at="2026-10-04T05:01:00Z",
                    ),
                ],
                "thread_lines": [],
            },
        )
        for case in cases:
            with self.subTest(phase=case["phase"]):
                with self.assertRaises(PolicyError):
                    validate_rate_limit_fallback(
                        required_review_bot="coderabbitai[bot]",
                        head_sha=HEAD,
                        head_committed_at="2026-10-04T04:59:00Z",
                        phase=case["phase"],
                        review_lines=case.get("review_lines", []),
                        comment_lines=comments,
                        check_lines=case["check_lines"],
                        thread_lines=case["thread_lines"],
                    )

    def test_rate_limit_before_head_commit_is_not_exact_head_evidence(self):
        comments = [
            rate_limit_comment(
                comment_id=101,
                created_at="2026-10-04T04:57:00Z",
            ),
            rate_limit_comment(
                comment_id=102,
                created_at="2026-10-04T04:58:00Z",
            ),
        ]
        checks = green_gate_checks() + [
            check(
                check_id=99,
                name=policy.POLICY_CHECK_NAME,
                conclusion="failure",
                completed_at="2026-10-04T05:01:00Z",
            ),
        ]
        with self.assertRaisesRegex(PolicyError, "único rate limit"):
            validate_rate_limit_fallback(
                required_review_bot="coderabbitai[bot]",
                head_sha=HEAD,
                head_committed_at="2026-10-04T04:59:00Z",
                phase="construccion",
                review_lines=[],
                comment_lines=comments,
                check_lines=checks,
                thread_lines=[],
            )

    def test_green_checks_without_required_final_review_fail_closed(self):
        with self.assertRaises(PolicyError):
            validate_required_bot_review(
                [],
                "coderabbitai[bot]",
                HEAD,
                comment_lines=[
                    comment(marker=False, body_prefix="CodeRabbit status: success")
                ],
            )

    def test_coderabbit_grindflow_209_coverage_fixture_is_exact_head_only(self):
        reviewed_sha = "43bcfaaed89a8679bf871e2dbe1c0f8cf64369f6"
        next_head = "42a6908129ce2ba8a9c3fb2048a6425d5d8ce71e"
        stale_comment = comment(
            source_commit=reviewed_sha,
            covered_commit=reviewed_sha,
            body_prefix="Review limit reached. ",
        )
        with self.assertRaises(PolicyError):
            validate_required_bot_review(
                [],
                "coderabbitai[bot]",
                next_head,
                comment_lines=[stale_comment],
            )
        exact_comment = comment(
            source_commit=reviewed_sha,
            covered_commit=next_head,
            body_prefix="Full review finished. ",
        )
        validate_required_bot_review(
            [],
            "coderabbitai[bot]",
            next_head,
            comment_lines=[exact_comment],
        )

    def test_duplicate_comment_markers_are_ambiguous_and_rejected(self):
        first = json.loads(comment())
        second = json.loads(comment(comment_id=2))
        duplicate = json.dumps({
            "id": 11,
            "body": first["body"] + "\n" + second["body"],
            "user": {"type": "Bot", "login": "coderabbitai[bot]"},
        })
        with self.assertRaises(PolicyError):
            validate_required_bot_review(
                [],
                "coderabbitai[bot]",
                HEAD,
                comment_lines=[duplicate],
            )

    def test_comment_marker_schema_is_closed(self):
        extra_field = json.dumps({
            "id": 9,
            "body": (
                "<!-- final_review_risk_coverage:"
                + json.dumps({
                    "sourceCommitId": HEAD,
                    "coveredCommitId": HEAD,
                    "kind": "reviewed",
                    "extra": True,
                }, separators=(",", ":"))
                + " -->"
            ),
            "user": {"type": "Bot", "login": "coderabbitai[bot]"},
        })
        with self.assertRaises(PolicyError):
            validate_required_bot_review(
                [],
                "coderabbitai[bot]",
                HEAD,
                comment_lines=[extra_field],
            )


    def test_path_boundary_exception_assertions_are_single_invocation(self):
        outside = Path(__file__).resolve()
        with self.assertRaises(PolicyError):
            load_reviewer_policy(outside)
        with self.assertRaises(PolicyError):
            _read_bounded_lines(outside, max_bytes=1024, noun="comentarios")



    def test_policy_parsers_and_main_cover_fail_closed_edges(self):
        self.assertEqual(parse_reviewer_policy(None), "")
        invalid_payloads = (
            "x" * (policy.MAX_REVIEWER_POLICY_BYTES + 1),
            "{",
            "[]",
            json.dumps({"version": 2, "required_review_bot": None}),
            json.dumps({"version": 1, "required_review_bot": "not a bot!"}),
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload[:20]):
                with self.assertRaises(PolicyError):
                    parse_reviewer_policy(payload)
        self.assertEqual(
            parse_reviewer_policy(
                json.dumps({"version": 1, "required_review_bot": None})
            ),
            "",
        )

        for base, caller in (("bad!", ""), ("", "bad!")):
            with self.subTest(base=base, caller=caller):
                with self.assertRaises(PolicyError):
                    resolve_required_review_bot(base, caller)

        with self.assertRaises(PolicyError):
            policy._parse_ndjson(["{"], noun="Review")
        with self.assertRaises(PolicyError):
            policy._parse_ndjson([json.dumps([])], noun="Review")
        too_long = json.dumps({"id": 1, "x": "y" * policy.MAX_EVIDENCE_ITEM_BYTES})
        with self.assertRaises(PolicyError):
            policy._parse_ndjson([too_long], noun="Review")
        duplicate = json.dumps({"id": 7, "state": "COMMENTED"})
        self.assertEqual(len(policy._parse_ndjson([duplicate, duplicate], noun="Review")), 1)

        invalid_login = review(login="x" * 101)
        with self.assertRaisesRegex(PolicyError, "Identidad"):
            count_review_rounds([invalid_login])

        with self.assertRaisesRegex(PolicyError, "Reviewer-bot"):
            validate_required_bot_review([], "bad!", HEAD)
        with self.assertRaisesRegex(PolicyError, "HEAD"):
            validate_required_bot_review([], "coderabbitai[bot]", "bad")

        class Options:
            required_review_bot = ""
            base_policy_file = ""
            head_sha = ""
            head_committed_at = ""
            comments_file = ""
            checks_file = ""
            threads_file = ""
            phase_file = ""

        fake_policy = {"version": 1, "review_round_limit": 3, "decisions": []}
        with (
            patch.object(policy, "args", return_value=Options()),
            patch.object(policy, "load_policy", return_value=fake_policy),
            patch("sys.stdin", policy.io.StringIO("") if hasattr(policy, "io") else __import__("io").StringIO("")),
            patch("sys.stdout", new_callable=__import__("io").StringIO),
        ):
            self.assertEqual(policy.main(), 0)

        with (
            patch.object(policy, "args", return_value=Options()),
            patch.object(policy, "load_policy", side_effect=PolicyError("boom")),
            patch("sys.stdin", __import__("io").StringIO("")),
            patch("sys.stderr", new_callable=__import__("io").StringIO) as stderr,
        ):
            self.assertEqual(policy.main(), 1)
            self.assertIn("ERROR: boom", stderr.getvalue())

        oversized = "x" * (policy.MAX_REVIEWS_BYTES + 1)
        with (
            patch.object(policy, "args", return_value=Options()),
            patch("sys.stdin", __import__("io").StringIO(oversized)),
            patch("sys.stderr", new_callable=__import__("io").StringIO),
        ):
            self.assertEqual(policy.main(), 1)

    def test_policy_is_confined_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"version": 1, "review_round_limit": 3, "decisions": []}
            (root / "decisiones.yml").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_policy(Path("decisiones.yml"), root=root)["version"], 1)
            with self.assertRaises(PolicyError):
                load_policy(Path("../decisiones.yml"), root=root)


class PolicyKitPathBoundaryTests(unittest.TestCase):
    def _temp_file(self, payload: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
        )
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        with handle:
            handle.write(payload)
        return Path(handle.name)

    def test_reviewer_policy_rejects_non_temp_file(self):
        outside = Path(__file__).resolve()
        with self.assertRaises(PolicyError):
            load_reviewer_policy(outside)

        valid = self._temp_file(json.dumps({
            "version": 1,
            "required_review_bot": "coderabbitai[bot]",
        }))
        self.assertEqual(
            load_reviewer_policy(valid),
            "coderabbitai[bot]",
        )

    def test_comments_reader_rejects_non_temp_file(self):
        outside = Path(__file__).resolve()
        with self.assertRaises(PolicyError):
            _read_bounded_lines(
                outside,
                max_bytes=1024,
                noun="comentarios",
            )

        valid = self._temp_file("uno\ndos\n")
        self.assertEqual(
            _read_bounded_lines(
                valid,
                max_bytes=1024,
                noun="comentarios",
            ),
            ["uno", "dos"],
        )

    def test_exception_assertions_have_single_throwing_invocation(self):
        outside = Path(__file__).resolve()
        with self.assertRaises(PolicyError):
            load_reviewer_policy(outside)
        with self.assertRaises(PolicyError):
            _read_bounded_lines(outside, max_bytes=1024, noun="comentarios")

    def test_temp_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "evidencia"
            try:
                link.symlink_to(Path(__file__).resolve())
            except OSError as exc:
                self.skipTest(f"symlink no disponible: {exc}")
            with self.assertRaises(PolicyError):
                _read_bounded_lines(
                    link,
                    max_bytes=1024,
                    noun="comentarios",
                )


if __name__ == "__main__":
    unittest.main()