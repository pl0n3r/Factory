"""Offline acceptance for plan-only Factory #1080 cutover."""
from __future__ import annotations

import copy
import socket
import subprocess
import unittest
from unittest.mock import patch

from scripts.release_auto_cutover_plan import plan_cutover

SHA = "a" * 40
PREVIOUS = "b" * 40


def fixture() -> dict:
    """Construct synthetic coherent future provenance, not an actual receipt."""
    return {
        "candidate_sha": SHA,
        "main_sha": SHA,
        "published_sha": PREVIOUS,
        "phase": "construccion",
        "release_machinery_changed": False,
        "policy_gate": "2075-product-direction-A",
        "candidate_report": {
            "candidate_sha": SHA,
            "state": "REVIEW_ONLY",
            "reason": "candidate_evidence_ready_for_future_policy_review",
            "authorizes_release": False,
            "mutations": 0, "tag_writes": 0, "release_writes": 0,
        },
        "consumer_report": {
            "candidate_sha": SHA,
            "state": "REVIEW_ONLY", "reason": "verified_independent_receipts",
            "observed_consumers": 6, "synthetic": False,
            "evidence_authenticated": True, "authorizes_release": False,
            "mutations": 0, "tag_writes": 0, "release_writes": 0,
        },
        "receipt": {"candidate_sha": SHA, "source": "independent", "run_id": 42},
    }


class ReleaseAutoCutoverPlanTests(unittest.TestCase):
    def assertHold(self, changes: dict) -> None:
        """Verify every rejected case is inert and has no usable steps."""
        sample = fixture()
        sample.update(changes)
        output = plan_cutover(sample)
        self.assertEqual("HOLD", output["state"])
        self.assertEqual([], output["steps"])
        self.assertIs(output["authorizes_release"], False)
        self.assertEqual(0, output["tag_writes"])

    def test_rechaza_evidencia_incompleta_sintetica_y_sha_incoherente(self) -> None:
        self.assertEqual("HOLD", plan_cutover(None)["state"])
        self.assertEqual("HOLD", plan_cutover({})["state"])
        for change in (
            {"candidate_sha": "no-sha"}, {"main_sha": PREVIOUS},
            {"published_sha": SHA}, {"extra": True},
            {"candidate_report": None}, {"consumer_report": None},
            {"candidate_report": {**fixture()["candidate_report"], "candidate_sha": PREVIOUS}},
            {"consumer_report": {**fixture()["consumer_report"], "candidate_sha": PREVIOUS}},
            {"candidate_report": {k:v for k,v in fixture()["candidate_report"].items() if k != "candidate_sha"}},
            {"consumer_report": {k:v for k,v in fixture()["consumer_report"].items() if k != "candidate_sha"}},
            {"receipt": None},
            {"consumer_report": {**fixture()["consumer_report"], "synthetic": True}},
            {"consumer_report": {**fixture()["consumer_report"], "evidence_authenticated": False}},
            {"consumer_report": {**fixture()["consumer_report"], "state": "BLOCKED"}},
            {"consumer_report": {**fixture()["consumer_report"], "observed_consumers": 5}},
            {"receipt": {**fixture()["receipt"], "candidate_sha": PREVIOUS}},
            {"receipt": {**fixture()["receipt"], "run_id": True}},
        ):
            with self.subTest(change=change):
                self.assertHold(change)

    def test_decision_de_producto_no_es_permiso_de_release(self) -> None:
        for change in (
            {"phase": "live"}, {"phase": "UNKNOWN"},
            {"release_machinery_changed": True},
            {"release_machinery_changed": None},
            {"policy_gate": "2075-product-direction-B"},
            {"policy_gate": "factory-release-A"},
            {"candidate_report": {**fixture()["candidate_report"], "authorizes_release": True}},
        ):
            with self.subTest(change=change):
                self.assertHold(change)

    def test_plan_solo_descriptivo_determinista_y_reversible(self) -> None:
        sample = fixture()
        copy_before = copy.deepcopy(sample)
        output = plan_cutover(sample)
        self.assertEqual("PLAN_ONLY", output["state"])
        self.assertEqual(5, len(output["steps"]))
        self.assertEqual(PREVIOUS, output["steps"][-1]["sha"])
        self.assertTrue(output["requires_owner_for_current_policy"])
        self.assertFalse(output["authorizes_release"])
        for _ in range(8):
            self.assertEqual(output, plan_cutover(sample))
        self.assertEqual(copy_before, sample)

    def test_cero_efectos_ni_autorizacion(self) -> None:
        with (patch("builtins.open", side_effect=AssertionError("filesystem")),
              patch.object(socket, "create_connection", side_effect=AssertionError("network")),
              patch.object(subprocess, "run", side_effect=AssertionError("command"))):
            for value in (None, {}, fixture()):
                result = plan_cutover(value)
                self.assertEqual(0, result["mutations"])
                self.assertEqual(0, result["release_writes"])
                self.assertEqual(0, result["tag_writes"])
                self.assertFalse(result["authorizes_release"])


if __name__ == "__main__":
    unittest.main()
