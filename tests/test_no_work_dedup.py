#!/usr/bin/env python3
"""Regresiones de deduplicación NO_WORK global (Factory#904)."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts.no_work_dedup import (
    CANONICAL_SINK,
    NoWorkInventoryError,
    NoWorkPublicationState,
    decide_no_work,
    inventory_fingerprint,
    revalidate_no_work_application,
)

ROOT = Path(__file__).resolve().parents[1]
REPOS = (
    "Factory",
    "Condor",
    "GrindFlow",
    "brvtal",
    "ControlBot",
    "AutoFactory",
    "FactoryRunner",
)


def repo_state() -> dict[str, object]:
    return {
        "available": [],
        "recovery": [],
        "reservations": [],
        "blockers": [],
        "pull_requests": [],
    }


def inventory() -> dict[str, object]:
    repos = {name: repo_state() for name in REPOS}
    repos["Factory"]["blockers"] = [{"issue": 860, "reason": "human-gate"}]
    repos["ControlBot"]["reservations"] = [
        {
            "issue": 634,
            "reservation_id": "lease-634",
            "owner": "pl0n3r",
            "branch": "trabajo/issue-634",
            "active": True,
        }
    ]
    repos["Condor"]["pull_requests"] = [
        {"number": 448, "state": "open", "head_sha": "a" * 40}
    ]
    return {
        "kill_switch": {"state": "RUNNING", "owner": "pl0n3r"},
        "repositories": repos,
        "observed_at": "ignored-by-fingerprint",
    }


def state_after(
    decision,
    *,
    comment_id: int,
    published_at: int,
    observed_at: int | None = None,
) -> NoWorkPublicationState:
    return NoWorkPublicationState(
        comment_id=comment_id,
        fingerprint=decision.fingerprint,
        published_at=published_at,
        observed_at=observed_at,
    )


class NoWorkDedupTests(unittest.TestCase):
    def test_available_and_recovery_reject_malformed_issue_ids(self):
        valid = inventory()
        valid["repositories"]["Factory"]["available"] = [1121, 904]
        reference = inventory_fingerprint(valid)
        valid["repositories"]["Factory"]["available"].reverse()
        self.assertEqual(inventory_fingerprint(valid), reference)

        invalid_values = (True, False, 0, -1, 1.0, "904", None, {}, [1])
        for field in ("available", "recovery"):
            for bad in invalid_values:
                with self.subTest(field=field, bad=repr(bad)):
                    candidate = inventory()
                    candidate["repositories"]["Factory"][field] = [bad]
                    with self.assertRaisesRegex(
                        NoWorkInventoryError, "issue_ids_invalid"
                    ):
                        inventory_fingerprint(candidate)
            duplicate = inventory()
            duplicate["repositories"]["Factory"][field] = [1121, 1121]
            with self.assertRaisesRegex(
                NoWorkInventoryError, "issue_ids_duplicate"
            ):
                inventory_fingerprint(duplicate)

        contradictory = inventory()
        contradictory["repositories"]["Factory"]["available"] = [1121]
        contradictory["repositories"]["Factory"]["recovery"] = [1121]
        with self.assertRaisesRegex(NoWorkInventoryError, "issue_state_conflict"):
            inventory_fingerprint(contradictory)

        distinct = inventory()
        distinct["repositories"]["Factory"]["available"] = [904, 1121]
        distinct["repositories"]["Factory"]["recovery"] = [1102]
        stable = inventory_fingerprint(distinct)
        distinct["repositories"]["Factory"]["available"].reverse()
        self.assertEqual(inventory_fingerprint(distinct), stable)

    def test_live_reservations_require_valid_identity_and_active_bool(self):
        invalid_entries = (
            "lease-plain-text",
            True,
            {},
            {"issue": 1121, "reservation_id": "valid", "active": 1},
            {"issue": 1121, "reservation_id": "valid"},
            {"issue": True, "reservation_id": "valid", "active": True},
            {"issue": 0, "reservation_id": "valid", "active": True},
            {"issue": 1121, "reservation_id": "", "active": True},
            {"issue": 1121, "reservation_id": None, "active": False},
            {"issue": 1121, "issue_number": 1122,
             "reservation_id": "valid", "active": True},
            {"issue": 1, "issue_number": True,
             "reservation_id": "alias", "active": True},
            {"issue": 1, "issue_number": 1.0,
             "reservation_id": "alias", "active": True},
        )
        for entry in invalid_entries:
            with self.subTest(entry=repr(entry)):
                candidate = inventory()
                candidate["repositories"]["ControlBot"]["reservations"] = [entry]
                with self.assertRaisesRegex(
                    NoWorkInventoryError, "reservation_invalid"
                ):
                    inventory_fingerprint(candidate)

        baseline = inventory_fingerprint(inventory())
        inactive = inventory()
        inactive["repositories"]["ControlBot"]["reservations"].append(
            {"issue_number": 1121, "reservation_id": "old", "active": False}
        )
        self.assertEqual(inventory_fingerprint(inactive), baseline)
        active = inventory()
        active["repositories"]["ControlBot"]["reservations"].append(
            {"issue_number": 1121, "reservation_id": "new", "active": True}
        )
        self.assertNotEqual(inventory_fingerprint(active), baseline)

        for conflict in (
            {"issue_number": 1121, "reservation_id": "another", "active": True},
            {"issue_number": 1122, "reservation_id": "new", "active": True},
        ):
            duplicate = inventory()
            duplicate["repositories"]["ControlBot"]["reservations"] = [
                {"issue_number": 1121, "reservation_id": "new", "active": True},
                conflict,
            ]
            with self.subTest(conflict=conflict):
                with self.assertRaisesRegex(
                    NoWorkInventoryError, "reservation_duplicate"
                ):
                    inventory_fingerprint(duplicate)

    def test_valid_inventory_and_scalar_blockers_keep_existing_fingerprint(self):
        base = inventory()
        fingerprint = inventory_fingerprint(base)
        self.assertEqual(inventory_fingerprint(base), fingerprint)

        with_blockers = inventory()
        with_blockers["repositories"]["Factory"]["blockers"].extend(
            [904, {"issue": 1121, "reason": "coordination"}]
        )
        first = inventory_fingerprint(with_blockers)
        with_blockers["repositories"]["Factory"]["blockers"].reverse()
        self.assertEqual(inventory_fingerprint(with_blockers), first)

        for bad_state in ("UNKNOWN", "OPEN", "merged", "", True, None):
            candidate = inventory()
            candidate["repositories"]["Condor"]["pull_requests"][0]["state"] = bad_state
            with self.subTest(pr_state=repr(bad_state)):
                with self.assertRaisesRegex(
                    NoWorkInventoryError, "pull_request_state_invalid"
                ):
                    inventory_fingerprint(candidate)
                with self.assertRaises(NoWorkInventoryError):
                    decide_no_work(candidate, None, 100)
        known_closed = inventory()
        known_closed["repositories"]["Condor"]["pull_requests"][0]["state"] = "closed"
        known_closed["repositories"]["Condor"]["pull_requests"] = []
        closed_baseline = inventory_fingerprint(known_closed)
        known_closed["repositories"]["Condor"]["pull_requests"].append({
            "number": 448, "state": "closed", "head_sha": "a" * 40
        })
        self.assertEqual(inventory_fingerprint(known_closed), closed_baseline)

        for bad in (True, False, 0, -4, "904", None):
            candidate = inventory()
            candidate["repositories"]["Factory"]["blockers"] = [bad]
            with self.subTest(blocker=repr(bad)):
                with self.assertRaisesRegex(
                    NoWorkInventoryError, "blocker_invalid"
                ):
                    inventory_fingerprint(candidate)

        decision = decide_no_work(base, None, 100)
        self.assertEqual((decision.action, decision.sink),
                         ("create", CANONICAL_SINK))
        stored = state_after(decision, comment_id=904_123, published_at=100)
        self.assertEqual(decide_no_work(base, stored, 101).action, "omit")
        self.assertEqual(
            decide_no_work(base, stored, 1900).action, "update"
        )
        self.assertEqual(
            revalidate_no_work_application(decide_no_work(base, stored, 1900),
                                           stored).action,
            "apply",
        )

    def test_ambiguous_inventory_blocks_no_work_decisions(self):
        # A real Issue cannot be simultaneously available and reserved/blocked.
        for kind in ("reservation", "blocker_scalar", "blocker_dict"):
            case = inventory()
            repo = case["repositories"]["Factory"]
            repo["available"] = [1121]
            if kind == "reservation":
                repo["reservations"] = [
                    {"issue": 1121, "reservation_id": "lease-1121", "active": True}
                ]
                code = "available_reserved_conflict"
            else:
                repo["blockers"] = (
                    [1121] if kind == "blocker_scalar"
                    else [{"issue": 1121, "reason": "human"}]
                )
                code = "available_blocker_conflict"
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(NoWorkInventoryError, code):
                    inventory_fingerprint(case)
                with self.assertRaises(NoWorkInventoryError):
                    decide_no_work(case, None, 100)

        for blocker in (
            {}, {"reason": "human"}, {"issue": None}, {"issue": False},
            {"issue": 0}, {"issue": 1121.0}, {"issue": "1121"},
        ):
            case = inventory()
            case["repositories"]["Factory"]["blockers"] = [blocker]
            with self.subTest(blocker=repr(blocker)):
                with self.assertRaisesRegex(NoWorkInventoryError, "blocker_invalid"):
                    inventory_fingerprint(case)
        for dup in ([1121, 1121], [1121, {"issue": 1121, "reason": "human"}]):
            case = inventory()
            case["repositories"]["Factory"]["blockers"] = dup
            with self.subTest(duplicate=repr(dup)):
                with self.assertRaisesRegex(NoWorkInventoryError, "blocker_duplicate"):
                    inventory_fingerprint(case)

        for head in ("a" * 40, "b" * 40):
            case = inventory()
            case["repositories"]["Condor"]["pull_requests"].append(
                {"number": 448, "state": "open", "head_sha": head}
            )
            with self.subTest(repeated_head=head):
                with self.assertRaisesRegex(NoWorkInventoryError, "pull_request_duplicate"):
                    inventory_fingerprint(case)

        for state in ("UNKNOWN", "", True, False, None, 0, [], {}):
            case = inventory()
            case["kill_switch"]["state"] = state
            with self.subTest(kill_state=repr(state)):
                with self.assertRaisesRegex(NoWorkInventoryError, "kill_switch_state_invalid"):
                    inventory_fingerprint(case)
                with self.assertRaises(NoWorkInventoryError):
                    decide_no_work(case, None, 100)

        base = inventory()
        fingerprint = inventory_fingerprint(base)
        paused = inventory()
        paused["kill_switch"]["state"] = "PAUSED"
        self.assertNotEqual(fingerprint, inventory_fingerprint(paused))
        inactive = inventory()
        inactive["repositories"]["Factory"]["reservations"] = [
            {"issue": 1121, "reservation_id": "old", "active": False}
        ]
        self.assertEqual(fingerprint, inventory_fingerprint(inactive))
        # Inactive leases are excluded only after their observation shape is checked.
        inactive["repositories"]["Factory"]["reservations"][0]["observed_at"] = "bad-date"
        with self.assertRaisesRegex(NoWorkInventoryError, "observation_timestamp_invalid"):
            inventory_fingerprint(inactive)

        valid = inventory()
        valid["repositories"]["Factory"]["available"] = [1121]
        valid["repositories"]["Factory"]["blockers"] = [860, {"issue": 904, "reason": "qa"}]
        valid["repositories"]["Factory"]["reservations"] = [
            {"issue": 1102, "reservation_id": "lease-1102", "active": True}
        ]
        valid["repositories"]["Condor"]["pull_requests"].append(
            {"number": 449, "state": "open", "head_sha": "b" * 40}
        )
        stable = inventory_fingerprint(valid)
        valid["repositories"]["Factory"]["blockers"].reverse()
        valid["repositories"]["Condor"]["pull_requests"].reverse()
        self.assertEqual(stable, inventory_fingerprint(valid))
        self.assertEqual(decide_no_work(valid, None, 100).action, "create")

    def test_nonfinite_and_undecodable_inventory_evidence_fails_closed(self):
        from math import inf, nan

        baseline = inventory_fingerprint(inventory())
        for malicious in (nan, inf, -inf):
            for section in ("reservation", "blocker"):
                with self.subTest(value=repr(malicious), section=section):
                    case = inventory()
                    if section == "reservation":
                        case["repositories"]["ControlBot"]["reservations"][0][
                            "material_score"
                        ] = malicious
                    else:
                        case["repositories"]["Factory"]["blockers"][0][
                            "material_score"
                        ] = malicious
                    with self.assertRaisesRegex(
                        NoWorkInventoryError, "inventory_nonfinite_number"
                    ):
                        inventory_fingerprint(case)
                    with self.assertRaises(NoWorkInventoryError):
                        decide_no_work(case, None, 100)

        lone_surrogate = chr(0xD800)
        for place in ("material_value", "material_key", "nested_value"):
            case = inventory()
            marker = case["repositories"]["Factory"]["blockers"][0]
            if place == "material_key":
                marker[lone_surrogate] = "synthetic"
            elif place == "nested_value":
                marker["details"] = ["normal", {"text": lone_surrogate}]
            else:
                marker["details"] = lone_surrogate
            with self.subTest(place=place):
                with self.assertRaisesRegex(
                    NoWorkInventoryError, "inventory_unicode_invalid"
                ):
                    inventory_fingerprint(case)

        good = inventory()
        good["repositories"]["Factory"]["blockers"][0]["material_score"] = 0.5
        good["repositories"]["Factory"]["blockers"][0]["description"] = "éxito"
        self.assertNotEqual(inventory_fingerprint(good), baseline)

    def test_nested_observation_timestamps_do_not_change_fingerprint(self):
        """Cambiar la hora de captura no convierte una lease igual en trabajo nuevo."""
        baseline = inventory_fingerprint(inventory())
        fingerprints = []
        for timestamp in ("2026-10-09T21:00:00Z", "2026-10-09T21:01:00Z"):
            snapshot = inventory()
            lease = snapshot["repositories"]["ControlBot"]["reservations"][0]
            lease.update({
                "observed_at": timestamp,
                "fetched_at": timestamp,
                "observation_metadata": {"updated_at": timestamp},
            })
            blocker = snapshot["repositories"]["Factory"]["blockers"][0]
            blocker.update({
                "captured_at": timestamp,
                "observation_metadata": {"updated_at": timestamp},
            })
            fingerprints.append(inventory_fingerprint(snapshot))
            # Calcular huella no altera el inventario recibido.
            self.assertEqual(lease["observed_at"], timestamp)
            self.assertEqual(blocker["captured_at"], timestamp)
        self.assertEqual(fingerprints, [baseline, baseline])

    def test_nested_reservation_identity_and_blocker_semantics_change_fingerprint(self):
        baseline = inventory_fingerprint(inventory())
        reservation_cases = (
            ("reservation_id", "different-lease"),
            ("owner", "another-agent"),
            ("issue", 999),
            ("branch", "trabajo/issue-999"),
            ("active", False),
            ("claims", ["scripts/different.py"]),
            ("updated_at", "2026-10-09T21:00:00Z"),
            ("unknown_material_field", "new-domain-signal"),
        )
        for field, value in reservation_cases:
            with self.subTest(reservation=field):
                snapshot = inventory()
                snapshot["repositories"]["ControlBot"]["reservations"][0][field] = value
                self.assertNotEqual(inventory_fingerprint(snapshot), baseline)

        for field, value in (
            ("reason", "different-gate"),
            ("condition", "unblock-condition-changed"),
            ("issue", 999),
        ):
            with self.subTest(blocker=field):
                snapshot = inventory()
                snapshot["repositories"]["Factory"]["blockers"][0][field] = value
                self.assertNotEqual(inventory_fingerprint(snapshot), baseline)

        ambiguous = inventory()
        ambiguous["repositories"]["ControlBot"]["reservations"][0][
            "observation_metadata"
        ] = {"reservation_id": "do-not-hide-materiality"}
        with self.assertRaisesRegex(NoWorkInventoryError, "observation_metadata_invalid"):
            inventory_fingerprint(ambiguous)

        invalid_timestamp = inventory()
        invalid_timestamp["repositories"]["Factory"]["blockers"][0][
            "observed_at"
        ] = {"not": "a-timestamp"}
        with self.assertRaisesRegex(NoWorkInventoryError, "observation_timestamp_invalid"):
            inventory_fingerprint(invalid_timestamp)

        for bad in ("not-an-instant", "2026-10-09T21:00:00", "", True, -1):
            with self.subTest(invalid_timestamp=bad):
                invalid = inventory()
                invalid["repositories"]["ControlBot"]["reservations"][0][
                    "observed_at"
                ] = bad
                with self.assertRaisesRegex(
                    NoWorkInventoryError, "observation_timestamp_invalid"
                ):
                    inventory_fingerprint(invalid)

        valid_epoch = inventory()
        valid_epoch["repositories"]["ControlBot"]["reservations"][0][
            "observed_at"
        ] = 1_760_044_800
        self.assertEqual(inventory_fingerprint(valid_epoch), baseline)

    def test_no_work_docs_define_nested_incidental_metadata(self):
        guide = (ROOT / "docs" / "no-work-dedup.md").read_text(encoding="utf-8")
        for signal in (
            "observation_metadata",
            "observed_at",
            "captured_at",
            "fetched_at",
            "updated_at",
            "reservation_id",
            "blockers",
        ):
            with self.subTest(signal=signal):
                self.assertIn(signal, guide)
        self.assertIn("ambigu", guide.lower())
        self.assertIn("campos desconocidos", guide.lower())

    def test_ten_identical_cycles_create_one_comment(self):
        snapshot = inventory()
        previous = None
        actions: list[str] = []
        comment_ids: list[int | None] = []

        for cycle in range(10):
            now = 1_000 + cycle * 60
            decision = decide_no_work(snapshot, previous, now)
            actions.append(decision.action)
            comment_ids.append(decision.comment_id)
            if decision.action == "create":
                previous = state_after(
                    decision,
                    comment_id=904_001,
                    published_at=now,
                )
            elif decision.action == "update":
                previous = state_after(
                    decision,
                    comment_id=previous.comment_id,
                    published_at=now,
                )

        self.assertEqual(actions.count("create"), 1)
        self.assertEqual(actions.count("update"), 0)
        self.assertEqual(actions.count("omit"), 9)
        self.assertEqual(comment_ids[1:], [904_001] * 9)
        self.assertEqual(decision.sink, CANONICAL_SINK)

        refresh = decide_no_work(snapshot, previous, 1_000 + 30 * 60)
        self.assertEqual(
            (refresh.action, refresh.comment_id, refresh.reason),
            ("update", 904_001, "refresh_interval_elapsed"),
        )

    def test_inventory_change_updates_same_canonical_comment(self):
        base = inventory()
        first = decide_no_work(base, None, 10_000)
        previous = state_after(first, comment_id=904_777, published_at=10_000)

        changed = inventory()
        changed["repositories"]["FactoryRunner"]["available"] = [905]
        decision = decide_no_work(changed, previous, 10_060)

        self.assertEqual(decision.action, "update")
        self.assertEqual(decision.comment_id, 904_777)
        self.assertEqual(decision.reason, "inventory_changed")
        self.assertNotEqual(decision.fingerprint, previous.fingerprint)

    def test_fingerprint_tracks_queue_leases_prs_and_kill_switch(self):
        base = inventory()
        base_fingerprint = inventory_fingerprint(base)

        incidental = inventory()
        incidental["observed_at"] = "different"
        incidental["kill_switch"]["owner"] = "ignored-after-canonical-validation"
        incidental["repositories"]["Condor"]["pull_requests"][0]["title"] = "noise"
        incidental["repositories"]["Condor"]["pull_requests"][0]["updated_at"] = "noise"
        self.assertEqual(inventory_fingerprint(incidental), base_fingerprint)

        mutations = []

        available = inventory()
        available["repositories"]["Factory"]["available"] = [904]
        mutations.append(available)

        recovery = inventory()
        recovery["repositories"]["brvtal"]["recovery"] = [700]
        mutations.append(recovery)

        lease = inventory()
        lease["repositories"]["ControlBot"]["reservations"][0]["reservation_id"] = "lease-new"
        mutations.append(lease)

        blocker = inventory()
        blocker["repositories"]["Factory"]["blockers"][0]["reason"] = "other-gate"
        mutations.append(blocker)

        pr_head = inventory()
        pr_head["repositories"]["Condor"]["pull_requests"][0]["head_sha"] = "b" * 40
        mutations.append(pr_head)

        switch = inventory()
        switch["kill_switch"]["state"] = "PAUSED"
        mutations.append(switch)

        for changed in mutations:
            with self.subTest(changed=changed):
                self.assertNotEqual(
                    inventory_fingerprint(changed),
                    base_fingerprint,
                )

        incomplete = inventory()
        del incomplete["repositories"]["AutoFactory"]
        with self.assertRaises(NoWorkInventoryError):
            inventory_fingerprint(incomplete)

        missing_pr_head = inventory()
        del missing_pr_head["repositories"]["Condor"]["pull_requests"][0]["head_sha"]
        with self.assertRaises(NoWorkInventoryError):
            inventory_fingerprint(missing_pr_head)

        malformed_pr = inventory()
        malformed_pr["repositories"]["Condor"]["pull_requests"] = ["PR#448"]
        with self.assertRaises(NoWorkInventoryError):
            inventory_fingerprint(malformed_pr)

    def test_plan_routes_global_no_work_to_factory_904(self):
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertIn("Factory#904", plan)
        self.assertIn("scripts/no_work_dedup.py", plan)
        self.assertIn("create | update | omit", plan)
        self.assertIn("30 min", plan)
        self.assertIn("no se publican nuevos", plan.lower())
        self.assertIn("NO_WORK", plan)

    def test_measurement_caps_new_comments_for_unchanged_inventory(self):
        snapshot = inventory()
        first = decide_no_work(snapshot, None, 0)
        previous = state_after(first, comment_id=904_123, published_at=0)

        decisions = [first]
        for now in (60, 120, 1_799, 1_800, 1_801, 3_600, 3_601):
            decision = decide_no_work(snapshot, previous, now)
            decisions.append(decision)
            if decision.action == "update":
                previous = state_after(
                    decision,
                    comment_id=previous.comment_id,
                    published_at=now,
                )

        self.assertEqual(
            sum(decision.action == "create" for decision in decisions),
            1,
        )
        self.assertTrue(
            all(
                decision.comment_id == 904_123
                for decision in decisions[1:]
                if decision.action in {"update", "omit"}
            )
        )
        self.assertEqual(
            sum(decision.action == "update" for decision in decisions),
            2,
        )

        guide = (ROOT / "docs" / "no-work-dedup.md").read_text(encoding="utf-8")
        self.assertIn("119 comentarios", guide)
        self.assertIn("43.0 comentarios nuevos/h", guide)
        self.assertIn("20:00:19Z", guide)
        self.assertIn("22:46:22Z", guide)
        self.assertIn("0 comentarios nuevos/h", guide)
        self.assertIn("new_no_work_comments_per_hour", guide)

    def test_invalid_and_inactive_inventory_evidence_is_fail_closed(self):
        base = inventory()
        base_fingerprint = inventory_fingerprint(base)

        inactive = inventory()
        inactive["repositories"]["ControlBot"]["reservations"].append(
            {"issue": 999, "reservation_id": "old", "active": False}
        )
        self.assertEqual(inventory_fingerprint(inactive), base_fingerprint)

        closed_pr = inventory()
        closed_pr["repositories"]["Condor"]["pull_requests"].append(
            {"number": 449, "state": "closed", "head_sha": "c" * 40}
        )
        self.assertEqual(inventory_fingerprint(closed_pr), base_fingerprint)

        missing_switch_state = inventory()
        del missing_switch_state["kill_switch"]["state"]
        with self.assertRaisesRegex(NoWorkInventoryError, "kill_switch_missing"):
            inventory_fingerprint(missing_switch_state)

        wrong_repo_field = inventory()
        wrong_repo_field["repositories"]["Factory"]["available"] = "not-a-list"
        with self.assertRaisesRegex(NoWorkInventoryError, "repository_field_invalid"):
            inventory_fingerprint(wrong_repo_field)

        invalid_pr_state = inventory()
        invalid_pr_state["repositories"]["Condor"]["pull_requests"][0]["state"] = None
        with self.assertRaisesRegex(NoWorkInventoryError, "pull_request_state_invalid"):
            inventory_fingerprint(invalid_pr_state)

        invalid_pr_number = inventory()
        invalid_pr_number["repositories"]["Condor"]["pull_requests"][0]["number"] = True
        with self.assertRaisesRegex(NoWorkInventoryError, "pull_request_number_invalid"):
            inventory_fingerprint(invalid_pr_number)

        invalid_pr_head = inventory()
        invalid_pr_head["repositories"]["Condor"]["pull_requests"][0]["head_sha"] = "not-a-sha"
        with self.assertRaisesRegex(NoWorkInventoryError, "pull_request_head_invalid"):
            inventory_fingerprint(invalid_pr_head)

        with self.assertRaisesRegex(NoWorkInventoryError, "now_invalid"):
            decide_no_work(base, None, -1)

        with self.assertRaisesRegex(NoWorkInventoryError, "publication_state_invalid"):
            decide_no_work(base, "not-state", 1)

        first = decide_no_work(base, None, 10)
        previous = state_after(first, comment_id=904_999, published_at=10)
        with self.assertRaisesRegex(NoWorkInventoryError, "time_moved_backwards"):
            decide_no_work(base, previous, 9)

    def test_paused_kill_switch_never_produces_publication_decisions(self):
        active = inventory()
        paused = inventory()
        paused["kill_switch"]["state"] = "PAUSED"

        # Preserve the audit fingerprint for valid PAUSED evidence without
        # offering an actionable create/update/omit NO_WORK decision.
        self.assertNotEqual(
            inventory_fingerprint(paused), inventory_fingerprint(active)
        )
        first = decide_no_work(active, None, 10)
        prior = state_after(first, comment_id=904_901, published_at=10)
        for previous in (None, prior):
            with self.subTest(previous=previous):
                with self.assertRaisesRegex(
                    NoWorkInventoryError, "kill_switch_paused"
                ):
                    decide_no_work(paused, previous, 100)
        self.assertEqual(decide_no_work(active, None, 100).action, "create")
        self.assertEqual(decide_no_work(active, prior, 100).action, "omit")

    def test_stale_inventory_observation_cannot_replace_newer_canonical_state(self):
        snapshot = inventory()
        first = decide_no_work(snapshot, None, 0)
        previous = state_after(
            first,
            comment_id=904_321,
            published_at=0,
            observed_at=0,
        )

        session_b = decide_no_work(
            snapshot,
            previous,
            2_000,
            observed_at=1_000,
        )
        session_a = decide_no_work(
            snapshot,
            previous,
            1_900,
            observed_at=1_500,
        )
        current = state_after(
            session_a,
            comment_id=904_321,
            published_at=1_900,
            observed_at=1_500,
        )

        prewrite = revalidate_no_work_application(session_b, current)
        self.assertEqual(
            (prewrite.action, prewrite.reason),
            ("recompute", "canonical_observation_newer"),
        )

    def test_prewrite_revalidation_requires_same_comment_and_expected_fingerprint(self):
        base = inventory()
        first = decide_no_work(base, None, 100)
        previous = state_after(
            first,
            comment_id=904_654,
            published_at=100,
            observed_at=100,
        )

        changed = inventory()
        changed["repositories"]["FactoryRunner"]["available"] = [1044]
        decision = decide_no_work(changed, previous, 200, observed_at=190)

        exact = revalidate_no_work_application(decision, previous)
        self.assertEqual(exact.action, "apply")

        other_comment = NoWorkPublicationState(
            comment_id=904_655,
            fingerprint=previous.fingerprint,
            published_at=150,
            observed_at=150,
        )
        self.assertEqual(
            revalidate_no_work_application(decision, other_comment).reason,
            "comment_id_changed",
        )

        other_fingerprint = NoWorkPublicationState(
            comment_id=previous.comment_id,
            fingerprint="f" * 64,
            published_at=150,
            observed_at=150,
        )
        self.assertEqual(
            revalidate_no_work_application(decision, other_fingerprint).reason,
            "fingerprint_changed",
        )

    def test_prewrite_rejects_concurrent_refresh_with_same_fingerprint(self):
        snapshot = inventory()
        first = decide_no_work(snapshot, None, 100)
        previous = state_after(
            first, comment_id=904_300, published_at=100, observed_at=100
        )
        pending = decide_no_work(snapshot, previous, 1_900, observed_at=150)
        self.assertEqual(pending.action, "update")
        self.assertEqual(pending.expected_published_at, 100)
        self.assertEqual(
            revalidate_no_work_application(pending, previous).action, "apply"
        )

        # Another session republished the same fingerprint/comment, with
        # an observation not newer than ours. Old guards falsely allowed it.
        concurrent = NoWorkPublicationState(
            comment_id=previous.comment_id,
            fingerprint=previous.fingerprint,
            published_at=1_750,
            observed_at=100,
        )
        result = revalidate_no_work_application(pending, concurrent)
        self.assertEqual((result.action, result.reason),
                         ("recompute", "publication_changed"))

        changed = inventory()
        changed["repositories"]["FactoryRunner"]["available"] = [904]
        pending_changed = decide_no_work(
            changed, previous, 200, observed_at=150
        )
        self.assertEqual(
            revalidate_no_work_application(pending_changed, concurrent).reason,
            "publication_changed",
        )

    def test_equal_or_newer_observation_preserves_create_update_omit_and_single_sink_contract(self):
        base = inventory()
        create = decide_no_work(base, None, 100, observed_at=100)
        self.assertEqual((create.action, create.sink), ("create", CANONICAL_SINK))
        self.assertEqual(
            revalidate_no_work_application(create, None).action,
            "apply",
        )

        previous = state_after(
            create,
            comment_id=904_777,
            published_at=100,
            observed_at=100,
        )
        omit = decide_no_work(base, previous, 120, observed_at=120)
        self.assertEqual((omit.action, omit.sink), ("omit", CANONICAL_SINK))
        self.assertEqual(
            revalidate_no_work_application(omit, previous).action,
            "omit",
        )

        changed = inventory()
        changed["repositories"]["Factory"]["available"] = [1044]
        update = decide_no_work(changed, previous, 130, observed_at=130)
        self.assertEqual(
            (update.action, update.comment_id, update.sink),
            ("update", 904_777, CANONICAL_SINK),
        )
        self.assertEqual(
            revalidate_no_work_application(update, previous).action,
            "apply",
        )

    def test_inventory_fingerprint_remains_independent_of_observation_timestamp(self):
        earlier = inventory()
        later = inventory()
        earlier["observed_at"] = 1
        later["observed_at"] = 9_999

        self.assertEqual(
            inventory_fingerprint(earlier),
            inventory_fingerprint(later),
        )

        first = decide_no_work(earlier, None, 10, observed_at=1)
        second = decide_no_work(later, None, 10_000, observed_at=9_999)
        self.assertEqual(first.fingerprint, second.fingerprint)


if __name__ == "__main__":
    unittest.main()
