#!/usr/bin/env python3
"""Regresiones del pack consumer-neutral del handoff desatendido Factory#799."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "unattended_handoff_v1"
DOC_PATH = ROOT / "docs" / "unattended-handoff-consumer-pack.md"

EXPECTED_PERMISSIONS = {
    "reserve": False,
    "merge": False,
    "deploy": False,
    "spend": False,
    "live": False,
}


def _load(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / f"{name}.json").open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AssertionError(f"fixture {name} must be an object")
    return payload


def _consumer_state(payload: dict[str, object]) -> str:
    """Proyección mínima: no recalcula ranking, 4B, 4C ni autoridad."""

    if payload.get("freshness") == "unknown":
        return "UNKNOWN"
    action = payload.get("action")
    if action in {"ALLOW", "PAUSE", "BLOCKED"}:
        return str(action)
    raise AssertionError("canonical fixture contains unsupported action")


class UnattendedHandoffConsumerPackTests(TestCase):
    def test_consumers_can_distinguish_allow_pause_blocked_unknown_without_recalculation(self):
        expected = {
            "allow": ("ALLOW", "ALLOW", "fresh"),
            "pause": ("PAUSE", "PAUSE", "fresh"),
            "blocked": ("BLOCKED", "BLOCKED", "fresh"),
            "unknown": ("UNKNOWN", "BLOCKED", "unknown"),
        }

        for name, (visible, action, freshness) in expected.items():
            with self.subTest(name=name):
                payload = _load(name)
                self.assertEqual(_consumer_state(payload), visible)
                self.assertEqual(payload["action"], action)
                self.assertEqual(payload["next_transition"], action)
                self.assertEqual(payload["freshness"], freshness)
                self.assertEqual(payload["version"], 1)

        document = DOC_PATH.read_text(encoding="utf-8")
        for fixture in expected:
            self.assertIn(
                f"`tests/fixtures/unattended_handoff_v1/{fixture}.json`",
                document,
            )
        self.assertIn("no vuelve a decidir nada", document)
        self.assertIn("no se deriva una transición nueva", document)
        self.assertIn("recalcular ranking, prioridades 1–7, 4B, 4C", document)
        self.assertIn(
            "`UNKNOWN` **no** amplía el enum de `action` y nunca se convierte en `ALLOW`",
            document,
        )

    def test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority(self):
        for name in ("allow", "pause", "blocked", "unknown"):
            with self.subTest(name=name):
                payload = _load(name)
                self.assertEqual(payload["authority"], "unchanged")
                self.assertEqual(payload["permissions"], EXPECTED_PERMISSIONS)
                self.assertFalse(any(payload["permissions"].values()))

        document = DOC_PATH.read_text(encoding="utf-8")
        for permission in EXPECTED_PERMISSIONS:
            self.assertIn(f"`permissions.{permission}=false`", document)
        self.assertIn("incluso un documento `ALLOW` **no autoriza**", document)
        self.assertIn("no un capability token", document)
        for permission in EXPECTED_PERMISSIONS:
            self.assertNotIn(f"permissions.{permission}=true", document)


if __name__ == "__main__":
    import unittest

    unittest.main()
