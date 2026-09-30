import json
import tempfile
import unittest
from pathlib import Path

from scripts.politica_kit import (
    PolicyError,
    count_review_rounds,
    load_policy,
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

    def test_optional_reviewer_preserves_existing_round_policy(self):
        lines = [review(review_id=i, login="review-bot") for i in (1, 2, 3)]
        self.assertEqual(resolve_required_review_bot("", ""), "")
        validate_required_bot_review(lines, "", "")
        self.assertEqual(count_review_rounds(lines), 3)
        validate_rounds(3, 3)

    def test_repository_reviewer_configuration_cannot_be_downgraded_by_caller_input(self):
        configured = "coderabbitai[bot]"
        self.assertEqual(resolve_required_review_bot("", configured), configured)
        self.assertEqual(
            resolve_required_review_bot(configured, configured),
            configured,
        )
        with self.assertRaises(PolicyError):
            resolve_required_review_bot("other-bot", configured)
        with self.assertRaises(PolicyError):
            resolve_required_review_bot(configured, "")

    def test_green_checks_without_required_final_review_fail_closed(self):
        with self.assertRaises(PolicyError):
            validate_required_bot_review([], "coderabbitai[bot]", HEAD)

    def test_policy_is_confined_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"version": 1, "review_round_limit": 3, "decisions": []}
            (root / "decisiones.yml").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_policy(Path("decisiones.yml"), root=root)["version"], 1)
            with self.assertRaises(PolicyError):
                load_policy(Path("../decisiones.yml"), root=root)

if __name__ == "__main__":
    unittest.main()
