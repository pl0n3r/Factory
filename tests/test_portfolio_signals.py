import copy
import json
import unittest
from pathlib import Path

from portfolio.signals import (
    PortfolioSignalsError,
    explain_tradeoffs,
    validate_portfolio_item,
)


def known(value, ref, *, source="observed", confidence=0.9):
    return {
        "status": "known",
        "value": value,
        "confidence": confidence,
        "source": source,
        "provenance": [ref],
    }


def unknown():
    return {
        "status": "unknown",
        "value": None,
        "confidence": 0,
        "source": None,
        "provenance": [],
    }


def item(
    work_id="pl0n3r/Factory#247-a",
    *,
    priority="high",
    eligible=True,
):
    return {
        "version": 1,
        "work_id": work_id,
        "owner_priority": priority,
        "eligible": eligible,
        "signals": {
            "unlocks": known(
                3,
                "pl0n3r/Factory#247@event:dependencies",
            ),
            "urgency": known(
                "medium",
                "pl0n3r/Factory#247@event:owner-context",
                source="declared",
            ),
            "risk": known(
                "low",
                "pl0n3r/Factory#247@event:risk",
                source="estimated",
                confidence=0.7,
            ),
            "cost": known(
                {
                    "agent_minutes": 40,
                    "ci_minutes": 12,
                    "tokens": 18000,
                },
                "pl0n3r/Factory#7@event:budget",
                source="estimated",
                confidence=0.7,
            ),
            "impact": known(
                {"technical": "high", "product": "medium"},
                "pl0n3r/Factory#6@event:feedback",
                source="declared",
                confidence=0.8,
            ),
            "reversibility": known(
                "reversible",
                "pl0n3r/Factory#247@event:rollback",
                source="declared",
            ),
        },
    }


class PortfolioSignalsTests(unittest.TestCase):
    def test_owner_priority_remains_authoritative(self):
        left = item("pl0n3r/Factory#247-a", priority="high")
        right = item("pl0n3r/Factory#247-b", priority="high")
        report = explain_tradeoffs([right, left])

        self.assertEqual(report["owner_priority"], "high")
        self.assertTrue(report["owner_priority_authoritative"])
        self.assertEqual(report["authority"], "owner_unchanged")
        self.assertIsNone(report["decision"])

        mismatched = item("pl0n3r/Factory#247-c", priority="medium")
        with self.assertRaisesRegex(
            PortfolioSignalsError,
            "misma owner_priority",
        ):
            explain_tradeoffs([left, mismatched])

    def test_signals_have_provenance_and_confidence(self):
        normalized = validate_portfolio_item(item())
        for signal in normalized["signals"].values():
            self.assertIn("confidence", signal)
            self.assertIn("provenance", signal)
            self.assertGreater(signal["confidence"], 0)
            self.assertTrue(signal["provenance"])

    def test_no_magic_score_or_winner_is_required(self):
        report = explain_tradeoffs(
            [
                item("pl0n3r/Factory#247-b"),
                item("pl0n3r/Factory#247-a"),
            ]
        )
        encoded = json.dumps(report, sort_keys=True).lower()
        for forbidden in (
            '"score"',
            '"ranking"',
            '"winner"',
            '"roi"',
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(
            [row["work_id"] for row in report["items"]],
            [
                "pl0n3r/Factory#247-a",
                "pl0n3r/Factory#247-b",
            ],
        )

    def test_tradeoffs_are_explainable_within_same_priority(self):
        first = item("pl0n3r/Factory#247-a")
        second = item("pl0n3r/Factory#247-b")
        second["signals"]["unlocks"] = known(
            7,
            "pl0n3r/Factory#247@event:dependencies-b",
        )
        second["signals"]["risk"] = known(
            "high",
            "pl0n3r/Factory#247@event:risk-b",
            source="estimated",
            confidence=0.6,
        )
        report = explain_tradeoffs([second, first])

        self.assertEqual(len(report["dimensions"]["unlocks"]), 2)
        self.assertEqual(len(report["dimensions"]["risk"]), 2)
        self.assertEqual(
            report["dimensions"]["unlocks"][1]["value"],
            7,
        )
        self.assertEqual(
            report["dimensions"]["risk"][1]["value"],
            "high",
        )

    def test_missing_evidence_yields_uncertainty(self):
        first = item("pl0n3r/Factory#247-a")
        first["signals"]["impact"] = unknown()
        first["signals"]["cost"] = unknown()
        second = item("pl0n3r/Factory#247-b")

        report = explain_tradeoffs([first, second])
        self.assertEqual(
            report["uncertainty"],
            [
                {
                    "work_id": "pl0n3r/Factory#247-a",
                    "signal": "cost",
                },
                {
                    "work_id": "pl0n3r/Factory#247-a",
                    "signal": "impact",
                },
            ],
        )
        self.assertIsNone(
            report["dimensions"]["cost"][0]["value"]
        )
        self.assertIsNone(
            report["dimensions"]["impact"][0]["value"]
        )

        invented = copy.deepcopy(first)
        invented["signals"]["cost"]["value"] = {
            "agent_minutes": 1,
            "ci_minutes": 1,
            "tokens": 1,
        }
        with self.assertRaisesRegex(
            PortfolioSignalsError,
            "unknown no puede inventar",
        ):
            validate_portfolio_item(invented)

    def test_docs_preserve_human_decision_boundary(self):
        text = Path("docs/portfolio-signals.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "prioridad del dueño",
            "sin ranking",
            "unknown",
            "#6",
            "#7",
            "#161",
            "ControlBot",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
