#!/usr/bin/env python3
"""Regresiones del contrato de idle global de Factory."""
from __future__ import annotations

import json
import unittest

from scripts.unattended_global_idle import (
    CANONICAL_REPOSITORIES,
    GlobalIdleValidationError,
    evaluate_global_idle_snapshot,
    validate_global_idle_proof,
)


def row(repository: str, **changes):
    value = {
        "repository": repository,
        "freshness": "fresh",
        "ready": False,
        "reserved": False,
        "reviewing": False,
        "ambiguous": False,
        "source_ref": f"github:{repository}#inventory",
    }
    value.update(changes)
    return value


def snapshot(rows=None):
    return {
        "version": 1,
        "repositories": (
            [row(repository) for repository in CANONICAL_REPOSITORIES]
            if rows is None
            else rows
        ),
    }


class UnattendedGlobalIdleTests(unittest.TestCase):
    def test_global_idle_requires_complete_fresh_snapshot_of_all_canonical_repositories(self):
        proof = evaluate_global_idle_snapshot(snapshot())
        self.assertTrue(proof["idle_global"])
        self.assertEqual(proof["reasons"], [])
        self.assertEqual(len(proof["provenance"]), len(CANONICAL_REPOSITORIES))

        missing = evaluate_global_idle_snapshot(
            snapshot([row(repository) for repository in CANONICAL_REPOSITORIES[:-1]])
        )
        self.assertFalse(missing["idle_global"])
        self.assertIn(
            f"missing_repository:{CANONICAL_REPOSITORIES[-1]}",
            missing["reasons"],
        )

    def test_any_active_ready_missing_stale_or_ambiguous_repository_fails_closed(self):
        cases = (
            ("ready", {"ready": True}),
            ("reserved", {"reserved": True}),
            ("reviewing", {"reviewing": True}),
            ("stale", {"freshness": "stale"}),
            ("ambiguous", {"ambiguous": True}),
        )
        for name, changes in cases:
            rows = [row(repository) for repository in CANONICAL_REPOSITORIES]
            rows[2] = row(CANONICAL_REPOSITORIES[2], **changes)
            with self.subTest(name=name):
                proof = evaluate_global_idle_snapshot(snapshot(rows))
                self.assertFalse(proof["idle_global"])
                self.assertTrue(proof["reasons"])

        with self.assertRaises(GlobalIdleValidationError):
            evaluate_global_idle_snapshot(
                {
                    "version": 1,
                    "repositories": [
                        row(CANONICAL_REPOSITORIES[0]),
                        row(CANONICAL_REPOSITORIES[0]),
                    ],
                }
            )

    def test_idle_proof_rejects_forged_seven_entry_provenance(self):
        forged = {
            "version": 1,
            "idle_global": True,
            "reasons": [],
            "provenance": [f"fake/repo-{index}:source:fresh" for index in range(7)],
        }
        with self.assertRaisesRegex(
            GlobalIdleValidationError,
            "idle_global_invalid_provenance",
        ):
            validate_global_idle_proof(forged)

        canonical = evaluate_global_idle_snapshot(snapshot())
        self.assertTrue(validate_global_idle_proof(canonical)["idle_global"])

    def test_global_idle_contract_rejects_invalid_shapes_and_provenance(self):
        canonical = evaluate_global_idle_snapshot(snapshot())
        canonical_provenance = list(canonical["provenance"])

        invalid_proofs = [
            {},
            {"version": 2, "idle_global": True, "reasons": [], "provenance": canonical_provenance},
            {"version": 1, "idle_global": "yes", "reasons": [], "provenance": canonical_provenance},
            {"version": 1, "idle_global": True, "reasons": ["unexpected"], "provenance": canonical_provenance},
            {"version": 1, "idle_global": False, "reasons": [], "provenance": []},
            {
                "version": 1,
                "idle_global": True,
                "reasons": [],
                "provenance": [
                    "pl0n3r/Factory:a:fresh",
                    "pl0n3r/Factory:b:fresh",
                    *[
                        item
                        for item in canonical_provenance
                        if not item.startswith("pl0n3r/Factory:")
                    ],
                ],
            },
            {
                "version": 1,
                "idle_global": True,
                "reasons": [],
                "provenance": [
                    (
                        item[:-len(":fresh")] + ":stale"
                        if item.startswith("pl0n3r/Factory:")
                        else item
                    )
                    for item in canonical_provenance
                ],
            },
            {
                "version": 1,
                "idle_global": True,
                "reasons": [],
                "provenance": canonical_provenance[:-1],
            },
        ]
        for proof in invalid_proofs:
            with self.subTest(proof=proof):
                with self.assertRaises(GlobalIdleValidationError):
                    validate_global_idle_proof(proof)

        invalid_snapshots = [
            [],
            {"version": 2, "repositories": []},
            {"version": 1, "repositories": "not-a-list"},
            {"version": 1, "repositories": [{"repository": "pl0n3r/Factory"}]},
            snapshot([
                row(repository) for repository in CANONICAL_REPOSITORIES[:-1]
            ] + [row(CANONICAL_REPOSITORIES[-1], freshness="future")]),
            snapshot([
                row(repository) for repository in CANONICAL_REPOSITORIES[:-1]
            ] + [row(CANONICAL_REPOSITORIES[-1], ready="yes")]),
            snapshot([
                row(repository) for repository in CANONICAL_REPOSITORIES[:-1]
            ] + [row(CANONICAL_REPOSITORIES[-1], source_ref="bad source")]),
        ]
        for bad_snapshot in invalid_snapshots:
            with self.subTest(snapshot=bad_snapshot):
                with self.assertRaises(GlobalIdleValidationError):
                    evaluate_global_idle_snapshot(bad_snapshot)

        rows = [row(repository) for repository in CANONICAL_REPOSITORIES]
        rows.append(row("pl0n3r/Unexpected"))
        unexpected = evaluate_global_idle_snapshot(snapshot(rows))
        self.assertFalse(unexpected["idle_global"])
        self.assertIn("unexpected_repository:pl0n3r/Unexpected", unexpected["reasons"])

    def test_global_idle_never_fabricates_presence_capacity_heartbeat_or_sessions(self):
        proof = evaluate_global_idle_snapshot(snapshot())
        self.assertEqual(
            set(proof),
            {"version", "idle_global", "reasons", "provenance"},
        )
        serialized = json.dumps(proof, sort_keys=True)
        for forbidden in (
            "presence",
            "capacity",
            "known_slots",
            "eligible_free_slots",
            "heartbeat",
            "sessions",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
