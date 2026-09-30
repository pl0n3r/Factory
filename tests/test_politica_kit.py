import json
import tempfile
import unittest
from pathlib import Path

from scripts.politica_kit import (
    PolicyError,
    count_review_rounds,
    load_policy,
    validate_required_bot_review,
    validate_rounds,
)


class T(unittest.TestCase):
    def test_empty_commented_bot_reviews_do_not_count(self):
        reviews = [
            {
                "id": 1,
                "state": "COMMENTED",
                "body": "**Actionable comments posted: 2**",
                "user": {"type": "Bot", "login": "coderabbitai[bot]"},
            },
            {
                "id": 2,
                "state": "COMMENTED",
                "body": "",
                "user": {"type": "Bot", "login": "coderabbitai[bot]"},
            },
            {
                "id": 3,
                "state": "COMMENTED",
                "body": "   ",
                "user": {"type": "Bot", "login": "coderabbitai[bot]"},
            },
        ]
        lines = [json.dumps(review) for review in reviews]
        self.assertEqual(count_review_rounds(lines), 1)

    def test_substantive_and_terminal_bot_reviews_count(self):
        reviews = [
            {
                "id": 1,
                "state": "COMMENTED",
                "body": "Hallazgo accionable",
                "user": {"type": "Bot", "login": "review-bot"},
            },
            {
                "id": 2,
                "state": "APPROVED",
                "body": "",
                "user": {"type": "Bot", "login": "review-bot"},
            },
            {
                "id": 3,
                "state": "CHANGES_REQUESTED",
                "body": "",
                "user": {"type": "Bot", "login": "review-bot"},
            },
        ]
        lines = [json.dumps(review) for review in reviews]
        self.assertEqual(count_review_rounds(lines), 3)
        self.assertEqual(count_review_rounds(lines + [lines[-1]]), 3)

    def test_real_round_limit_still_fails_closed(self):
        lines = [
            json.dumps(
                {
                    "id": i,
                    "state": "COMMENTED",
                    "body": f"Hallazgo de ronda {i}",
                    "user": {"type": "Bot", "login": "review-bot"},
                }
            )
            for i in (1, 2, 3, 4)
        ]
        rounds = count_review_rounds(lines)
        self.assertEqual(rounds, 4)
        with self.assertRaises(PolicyError):
            validate_rounds(rounds, 3)

    def test_required_bot_review_on_exact_head_passes(self):
        head = "a" * 40
        lines = [json.dumps({
            "id": 10,
            "state": "COMMENTED",
            "body": "Review final sin hallazgos pendientes",
            "commit_id": head,
            "user": {"type": "Bot", "login": "coderabbitai[bot]"},
        })]
        validate_required_bot_review(lines, "coderabbitai[bot]", head)

    def test_required_bot_review_rejects_missing_wrong_non_bot_or_stale(self):
        head = "a" * 40
        base = {
            "id": 10,
            "state": "COMMENTED",
            "body": "Review final",
            "commit_id": head,
            "user": {"type": "Bot", "login": "coderabbitai[bot]"},
        }
        cases = {
            "missing": [],
            "wrong_login": [{**base, "user": {"type": "Bot", "login": "other[bot]"}}],
            "non_bot": [{**base, "user": {"type": "User", "login": "coderabbitai[bot]"}}],
            "stale": [{**base, "commit_id": "b" * 40}],
            "changes_requested": [{**base, "state": "CHANGES_REQUESTED", "body": ""}],
        }
        for name, reviews in cases.items():
            with self.subTest(name=name), self.assertRaises(PolicyError):
                validate_required_bot_review(
                    [json.dumps(review) for review in reviews],
                    "coderabbitai[bot]",
                    head,
                )

    def test_optional_reviewer_preserves_existing_round_policy(self):
        lines = [
            json.dumps({
                "id": i,
                "state": "COMMENTED",
                "body": f"Ronda {i}",
                "commit_id": "a" * 40,
                "user": {"type": "Bot", "login": "review-bot"},
            })
            for i in (1, 2, 3, 4)
        ]
        validate_required_bot_review(lines, "", "")
        rounds = count_review_rounds(lines)
        self.assertEqual(rounds, 4)
        with self.assertRaises(PolicyError):
            validate_rounds(rounds, 3)

    def test_green_checks_without_required_final_review_fail_closed(self):
        with self.assertRaises(PolicyError):
            validate_required_bot_review([], "coderabbitai[bot]", "a" * 40)

    def test_policy_is_confined_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"version": 1, "review_round_limit": 3, "decisions": []}
            (root / "decisiones.yml").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_policy(Path("decisiones.yml"), root=root)["version"], 1)
            with self.assertRaises(PolicyError):
                load_policy(Path("../decisiones.yml"), root=root)
