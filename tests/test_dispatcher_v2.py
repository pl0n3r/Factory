#!/usr/bin/env python3
import unittest

from scripts.dispatcher_v2 import (
    Candidate,
    authority_class,
    classify_readiness,
    dispatch_record,
    parallel_ready,
    select_next,
)


class DispatcherV2Tests(unittest.TestCase):
    def test_readiness_excludes_blocked_candidates_with_structured_reasons(self):
        candidate = Candidate(
            key="blocked",
            dependencies_open=("dep",),
            incompatible_reservation=True,
            pending_human_gate=True,
            claims=frozenset({"scripts/a.py"}),
            active_claims=frozenset({"scripts/a.py"}),
        )
        state = classify_readiness(candidate)
        self.assertFalse(state.ready)
        self.assertEqual(
            set(state.reasons),
            {
                "open_dependencies",
                "incompatible_reservation",
                "pending_human_gate",
                "claim_overlap",
            },
        )

    def test_authority_hierarchy_is_deterministic(self):
        candidates = [
            Candidate(key="medium", priority="medium"),
            Candidate(key="high", priority="high"),
            Candidate(key="critical", priority="critical"),
            Candidate(key="decision", owner_decision_resolved=True),
            Candidate(key="active", active_fix=True),
            Candidate(key="incident", incident=True),
            Candidate(key="health", health=True),
        ]
        selected = select_next(candidates)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, "health")
        self.assertEqual(authority_class(selected), "health")

    def test_active_fix_beats_parallel_equivalent_work(self):
        fix = Candidate(key="fix", active_fix=True, active_pr="#160", continuity=10)
        parallel = Candidate(
            key="parallel",
            priority="critical",
            equivalent_active_fix="fix",
        )
        selected = select_next([parallel, fix])
        self.assertEqual(selected.key, "fix")
        self.assertIn(
            "equivalent_active_fix_exists",
            classify_readiness(parallel).reasons,
        )

    def test_auto_prefix_does_not_imply_incident(self):
        unclassified = Candidate(key="review", title="[AUTO] privacy review", priority="high")
        structured = Candidate(
            key="real",
            title="[AUTO] health",
            auto_class="AUTO_INCIDENT",
            priority="medium",
        )
        self.assertEqual(authority_class(unclassified), "high")
        self.assertFalse(classify_readiness(unclassified).ready)
        self.assertIn(
            "unclassified_auto_needs_review",
            classify_readiness(unclassified).reasons,
        )
        self.assertEqual(authority_class(structured), "incident")
        self.assertEqual(select_next([unclassified, structured]).key, "real")

    def test_ready_leaf_beats_epic_umbrella(self):
        epic = Candidate(
            key="epic",
            priority="critical",
            is_epic=True,
            ready_children=("leaf",),
        )
        leaf = Candidate(key="leaf", priority="critical")
        self.assertFalse(classify_readiness(epic).ready)
        self.assertEqual(select_next([epic, leaf]).key, "leaf")

    def test_tiebreak_order_is_unlock_transversal_continuity_risk_age(self):
        base = dict(priority="high")
        candidates = [
            Candidate(key="age", ready_age=999, **base),
            Candidate(key="risk", effort=0, risk=0, **base),
            Candidate(key="continuity", continuity=1, **base),
            Candidate(key="transversal", transversal_impact=1, **base),
            Candidate(key="unlock", unlock_impact=1, **base),
        ]
        self.assertEqual(select_next(candidates).key, "unlock")

        same_unlock = [
            Candidate(key="local", unlock_impact=1, **base),
            Candidate(key="shared", unlock_impact=1, transversal_impact=1, **base),
        ]
        self.assertEqual(select_next(same_unlock).key, "shared")

    def test_aging_prevents_starvation_within_same_class_only(self):
        aged_high = Candidate(key="aged-high", priority="high", displaced_cycles=3)
        equivalent_high = Candidate(key="equivalent-high", priority="high")
        higher_impact_high = Candidate(
            key="higher-impact-high",
            priority="high",
            unlock_impact=1,
        )
        critical = Candidate(key="critical", priority="critical")

        self.assertEqual(select_next([aged_high, equivalent_high]).key, "aged-high")
        self.assertEqual(select_next([aged_high, higher_impact_high]).key, "higher-impact-high")
        self.assertEqual(select_next([aged_high, critical]).key, "critical")

    def test_parallel_ready_set_requires_disjoint_claims(self):
        candidates = [
            Candidate(key="a", priority="high", claims=frozenset({"x"})),
            Candidate(key="b", priority="high", claims=frozenset({"x"})),
            Candidate(key="c", priority="high", claims=frozenset({"y"})),
            Candidate(key="blocked", priority="high", dependencies_open=("z",)),
        ]
        selected = parallel_ready(candidates)
        keys = {candidate.key for candidate in selected}
        self.assertIn("c", keys)
        self.assertEqual(len(keys & {"a", "b"}), 1)
        self.assertNotIn("blocked", keys)

    def test_dispatch_emits_feedback_telemetry(self):
        candidates = [
            Candidate(
                key="chosen",
                priority="high",
                unlock_impact=2,
                ready_age=120,
                displaced_cycles=1,
                active_pr="#99",
                claims=frozenset({"scripts/a.py"}),
            ),
            Candidate(key="other", priority="high"),
            Candidate(key="excluded", priority="high", pending_human_gate=True),
        ]
        record = dispatch_record(candidates)
        self.assertEqual(record["selected"], "chosen")
        self.assertEqual(record["selected_class"], "high")
        self.assertIn("other", record["ready_not_selected"])
        self.assertEqual(record["excluded"]["excluded"], ["pending_human_gate"])
        self.assertEqual(record["candidates"]["chosen"]["active_pr"], "#99")
        self.assertEqual(record["candidates"]["chosen"]["ready_age"], 120)


    def test_dispatch_record_rejects_duplicate_candidate_keys(self):
        with self.assertRaisesRegex(ValueError, "candidate keys must be unique"):
            dispatch_record([
                Candidate(key="same", priority="high"),
                Candidate(key="same", priority="medium"),
            ])

    def test_regression_scenarios_match_known_factory_cases(self):
        brvtal_681 = Candidate(
            key="brvtal#681",
            health=True,
            auto_class="AUTO_INCIDENT",
            blocked=True,
            fallback_safe=False,
        )
        condor_223 = Candidate(
            key="condor#223",
            title="[AUTO] privacy review",
            auto_class="AUTO_REVIEW",
            priority="medium",
        )
        factory_160 = Candidate(
            key="factory#160",
            active_fix=True,
            active_pr="#160",
        )
        controlbot_epic = Candidate(
            key="controlbot-epic",
            priority="critical",
            is_epic=True,
            ready_children=("controlbot-leaf",),
        )
        controlbot_leaf = Candidate(key="controlbot-leaf", priority="critical")

        self.assertFalse(classify_readiness(brvtal_681).ready)
        self.assertEqual(authority_class(condor_223), "medium")
        self.assertEqual(authority_class(factory_160), "active_fix")
        self.assertEqual(
            select_next([controlbot_epic, controlbot_leaf]).key,
            "controlbot-leaf",
        )


if __name__ == "__main__":
    unittest.main()
