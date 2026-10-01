import json
import tempfile
import unittest
from pathlib import Path

from scripts.politica_kit import (
    PolicyError,
    _read_bounded_lines,
    count_review_rounds,
    load_policy,
    load_reviewer_policy,
    parse_reviewer_policy,
    resolve_required_review_bot,
    validate_required_bot_review,
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


class T(unittest.TestCase):
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

    def test_policy_is_confined_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"version": 1, "review_round_limit": 3, "decisions": []}
            (root / "decisiones.yml").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_policy(Path("decisiones.yml"), root=root)["version"], 1)
            with self.assertRaises(PolicyError):
                load_policy(Path("../decisiones.yml"), root=root)

    def test_path_boundary_exception_assertions_are_single_invocation(self):
        non_temp = Path(__file__).resolve()
        with self.assertRaises(PolicyError):
            load_reviewer_policy(non_temp)
        with self.assertRaises(PolicyError):
            _read_bounded_lines(
                non_temp,
                max_bytes=1024,
                noun="comentarios",
            )


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
        non_temp = Path(__file__).resolve()
        with self.assertRaises(PolicyError):
            load_reviewer_policy(non_temp)

        valid = self._temp_file(json.dumps({
            "version": 1,
            "required_review_bot": "coderabbitai[bot]",
        }))
        self.assertEqual(
            load_reviewer_policy(valid),
            "coderabbitai[bot]",
        )

    def test_comments_reader_rejects_non_temp_file(self):
        non_temp = Path(__file__).resolve()
        with self.assertRaises(PolicyError):
            _read_bounded_lines(
                non_temp,
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
