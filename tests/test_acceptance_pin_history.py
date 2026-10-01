#!/usr/bin/env python3
"""Regresiones para preservar el pin v2 tras cerrar una reserva."""

from __future__ import annotations

import unittest

from scripts import coordinar_trabajo as coordinator


OWNER = "pl0n3r"
BRANCH = "trabajo/issue-655"
RID = "72210439-1337-4656-99cf-51b465d1c45d"
PIN = "d" * 64


def trusted(body: str) -> dict:
    return {"user": {"login": coordinator.TRUSTED_MARKER_LOGIN}, "body": body}


def marker(
    *,
    owner: str = OWNER,
    reservation_id: str = RID,
    branch: str = BRANCH,
    active: bool,
    reason: str,
    pin: str | None = None,
) -> dict:
    return trusted(
        coordinator.reservation_marker(
            owner,
            reservation_id,
            branch,
            active,
            reason,
            pin,
        )
    )


class _CommentsApi:
    def __init__(self, comments):
        self.comments = comments

    def issue_comments(self, _issue_number):
        return self.comments


class AcceptancePinHistoryTests(unittest.TestCase):
    def test_inactive_pr_merged_preserves_same_chain_v2_pin(self) -> None:
        comments = [
            marker(active=True, reason="tomar", pin=PIN),
            marker(active=False, reason="pr-merged"),
        ]
        latest = coordinator.latest_reservation(comments)
        self.assertIsNotNone(latest)
        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "pr-merged")
        self.assertEqual(latest["acceptance_sha256"], PIN)

        for path in (
            ".github/workflows/factory-ci.yml",
            ".github/workflows/aceptacion.yml",
        ):
            text = open(path, encoding="utf-8").read()
            self.assertIn("latest_reservation", text)
            self.assertIn('reservation.get("acceptance_sha256")', text)

    def test_closed_chain_does_not_reactivate_lease(self) -> None:
        comments = [
            marker(active=True, reason="tomar", pin=PIN),
            marker(active=False, reason="pr-merged"),
        ]
        latest = coordinator.latest_reservation(comments)
        self.assertFalse(latest["active"])
        self.assertIsNone(coordinator.active_reservation(_CommentsApi(comments), 655))

    def test_cross_chain_pin_is_rejected(self) -> None:
        other_rid = "11111111-1111-4111-8111-111111111111"
        cases = [
            [marker(active=True, reason="tomar", pin=PIN, reservation_id=other_rid),
             marker(active=False, reason="pr-merged")],
            [marker(active=True, reason="tomar", pin=PIN, branch="trabajo/issue-999"),
             marker(active=False, reason="pr-merged")],
            [marker(active=True, reason="tomar", pin=PIN, owner="otro"),
             marker(active=False, reason="pr-merged")],
        ]
        for comments in cases:
            with self.subTest(comments=comments):
                latest = coordinator.latest_reservation(comments)
                self.assertNotIn("acceptance_sha256", latest)

    def test_missing_v2_pin_fails_closed(self) -> None:
        comments = [
            marker(active=True, reason="tomar"),
            marker(active=False, reason="pr-merged"),
        ]
        latest = coordinator.latest_reservation(comments)
        self.assertNotIn("acceptance_sha256", latest)

        released = [
            marker(active=True, reason="tomar", pin=PIN),
            marker(active=False, reason="liberar"),
        ]
        self.assertNotIn(
            "acceptance_sha256",
            coordinator.latest_reservation(released),
        )


if __name__ == "__main__":
    unittest.main()
