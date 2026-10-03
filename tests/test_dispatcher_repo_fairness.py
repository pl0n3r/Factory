#!/usr/bin/env python3
import unittest

from scripts.dispatcher_v2 import (
    Candidate,
    RepoFairnessContext,
    select_after_take_failure,
    select_next,
)


class DispatcherRepoFairnessTests(unittest.TestCase):
    def test_third_consecutive_dispatch_prefers_other_repo_with_free_ready_work(self):
        factory = Candidate(
            key="factory-new",
            priority="high",
            continuity=10,
            metadata={
                "repository_ref": "pl0n3r/Factory",
                "ready_since": "2026-10-03T22:55:00+00:00",
            },
        )
        condor = Candidate(
            key="condor-new",
            priority="high",
            metadata={
                "repository_ref": "pl0n3r/Condor",
                "ready_since": "2026-10-03T22:56:00+00:00",
            },
        )
        grindflow = Candidate(
            key="grindflow-new",
            priority="high",
            metadata={
                "repository_ref": "pl0n3r/GrindFlow",
                "ready_since": "2026-10-03T22:57:00+00:00",
            },
        )
        context = RepoFairnessContext(
            recent_dispatch_repos=(
                "pl0n3r/Factory",
                "pl0n3r/Factory",
                "pl0n3r/Factory",
            ),
            now="2026-10-03T23:00:00+00:00",
        )

        selected = select_next(
            [factory, condor, grindflow],
            fairness_context=context,
        )

        self.assertIsNotNone(selected)
        self.assertNotEqual(selected.metadata["repository_ref"], "pl0n3r/Factory")
        self.assertEqual(selected.key, "condor-new")

    def test_critical_available_work_wins_over_rotation(self):
        critical = Candidate(
            key="factory-critical",
            priority="critical",
            metadata={"repository_ref": "pl0n3r/Factory"},
        )
        other_repo_high = Candidate(
            key="condor-high",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        context = RepoFairnessContext(
            recent_dispatch_repos=(
                "pl0n3r/Factory",
                "pl0n3r/Factory",
                "pl0n3r/Factory",
            ),
            now="2026-10-03T23:00:00+00:00",
        )

        selected = select_next(
            [other_repo_high, critical],
            fairness_context=context,
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, "factory-critical")

    def test_stale_available_item_rises_after_threshold(self):
        stale = Candidate(
            key="condor-stale",
            priority="high",
            metadata={
                "repository_ref": "pl0n3r/Condor",
                "ready_since": "2026-10-03T22:20:00+00:00",
            },
        )
        newer = Candidate(
            key="factory-newer",
            priority="high",
            continuity=100,
            unlock_impact=100,
            metadata={
                "repository_ref": "pl0n3r/Factory",
                "ready_since": "2026-10-03T22:50:00+00:00",
            },
        )
        context = RepoFairnessContext(
            now="2026-10-03T23:00:00+00:00",
            starvation_minutes=30,
        )

        selected = select_next([newer, stale], fairness_context=context)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, "condor-stale")

    def test_take_failure_on_format_skips_to_next_candidate_same_cycle(self):
        malformed = Candidate(
            key="factory-malformed",
            priority="high",
            unlock_impact=100,
            metadata={"repository_ref": "pl0n3r/Factory"},
        )
        condor = Candidate(
            key="condor-next",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        grindflow = Candidate(
            key="grindflow-next",
            priority="medium",
            metadata={"repository_ref": "pl0n3r/GrindFlow"},
        )

        result = select_after_take_failure(
            [malformed, condor, grindflow],
            failed_key="factory-malformed",
            fairness_context=RepoFairnessContext(
                now="2026-10-03T23:00:00+00:00"
            ),
        )

        self.assertTrue(result["continue_same_cycle"])
        self.assertFalse(result["declare_no_work"])
        self.assertEqual(result["repair"]["action"], "mark_format_repair")
        self.assertEqual(
            result["repair"]["dedup_key"],
            "take-format:factory-malformed",
        )
        self.assertEqual(result["selected"], "condor-next")


    def test_fairness_context_validation_and_age_edges_fail_closed(self):
        candidate = Candidate(
            key="factory-ready",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Factory"},
        )
        invalid_contexts = (
            (
                RepoFairnessContext(consecutive_limit=True),
                "consecutive_limit must be a positive integer",
            ),
            (
                RepoFairnessContext(starvation_minutes=0),
                "starvation_minutes must be a positive integer",
            ),
            (
                RepoFairnessContext(recent_dispatch_repos=("unknown/repo",)),
                "history must contain canonical repositories only",
            ),
            (
                RepoFairnessContext(failed_take_keys=frozenset({""})),
                "failed_take_keys must contain non-empty strings",
            ),
            (
                RepoFairnessContext(now="2026-10-03T23:00:00"),
                "fairness now must be an offset-aware ISO timestamp",
            ),
        )

        for context, message in invalid_contexts:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    select_next([candidate], fairness_context=context)

        future = Candidate(
            key="condor-future",
            priority="high",
            metadata={
                "repository_ref": "pl0n3r/Condor",
                "ready_since": "2026-10-03T23:01:00+00:00",
            },
        )
        with self.assertRaisesRegex(
            ValueError,
            "candidate ready_since cannot be in the future",
        ):
            select_next(
                [future],
                fairness_context=RepoFairnessContext(
                    now="2026-10-03T23:00:00+00:00",
                ),
            )

        selected = select_next(
            [candidate],
            fairness_context=RepoFairnessContext(
                recent_dispatch_repos=("pl0n3r/Factory",),
            ),
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, "factory-ready")


if __name__ == "__main__":
    unittest.main()
