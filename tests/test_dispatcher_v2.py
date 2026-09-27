#!/usr/bin/env python3
import unittest

from scripts.dispatcher_v2 import (
    Candidate,
    WorkItemReadinessContext,
    adaptive_dispatch_record,
    adapt_candidates_for_adaptive,
    authority_class,
    candidate_from_work_item,
    classify_readiness,
    dispatch_record,
    parallel_ready,
    select_next,
)

from scripts.adaptive_fencing import evaluate_fencing
from scripts.adaptive_replan import decide_replan
from scripts.presence_contract import classify_presence


def work_item(**overrides):
    payload = {
        "work_id": "work-1",
        "origin_mode": "automatic",
        "origin_system": "factory",
        "group_id": "group-1",
        "work_type": "engineering",
        "requested_capabilities": ["python"],
        "required_roles": ["ingenieria-software"],
        "authority_level": "standard",
        "producer_ref": "factory#269",
        "priority_class": "high",
        "depends_on": [],
        "claims": ["scripts/example.py"],
        "policy_ref": "policy/factory",
        "evidence_refs": ["evidence/run-1"],
        "idempotency_key": "same-logical-work",
    }
    payload.update(overrides)
    return payload


def ready_context(**overrides):
    values = {
        "authority_valid": True,
        "policy_valid": True,
        "freshness_valid": True,
        "evidence_valid": True,
    }
    values.update(overrides)
    return WorkItemReadinessContext(**values)


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

    def test_work_item_adapter_preserves_single_dispatch_pipeline(self):
        directed = work_item(
            work_id="directed",
            origin_mode="directed",
            priority_class="medium",
            authority_level="incident",
        )
        automatic = work_item(
            work_id="automatic",
            origin_mode="automatic",
            priority_class="critical",
            authority_level="standard",
        )
        candidates = [
            candidate_from_work_item(directed, ready_context()),
            candidate_from_work_item(automatic, ready_context()),
        ]

        self.assertEqual(select_next(candidates).key, "directed")
        record = dispatch_record(candidates)
        self.assertEqual(record["selected"], "directed")
        self.assertEqual(record["selected_class"], "incident")
        self.assertEqual(
            record["candidates"]["automatic"]["metadata"]["origin_mode"],
            "automatic",
        )
        self.assertEqual(
            len(record["candidates"]["automatic"]["metadata"]["work_fingerprint"]),
            64,
        )

    def test_automatic_work_fails_closed_on_authority_policy_freshness_evidence(self):
        payload = work_item(origin_mode="automatic")
        cases = {
            "authority_unknown": ready_context(authority_valid=None),
            "policy_invalid": ready_context(policy_valid=False),
            "freshness_unknown": ready_context(freshness_valid=None),
            "evidence_invalid": ready_context(evidence_valid=False),
        }
        for expected_reason, context in cases.items():
            with self.subTest(reason=expected_reason):
                candidate = candidate_from_work_item(payload, context)
                state = classify_readiness(candidate)
                self.assertFalse(state.ready)
                self.assertIn(expected_reason, state.reasons)

    def test_budget_and_approval_gates_are_explicit(self):
        payload = work_item(
            origin_mode="directed",
            budget_ref="budget/2026",
            approval_ref="approval/42",
        )
        candidate = candidate_from_work_item(payload, ready_context())
        self.assertEqual(
            set(classify_readiness(candidate).reasons),
            {"budget_unknown", "approval_unknown"},
        )

        ready = candidate_from_work_item(
            payload,
            ready_context(budget_valid=True, approval_valid=True),
        )
        self.assertTrue(classify_readiness(ready).ready)

    def test_work_item_dependencies_claims_reservations_and_idempotency_block(self):
        payload = work_item(
            depends_on=["factory#270"],
            claims=["scripts/dispatcher_v2.py"],
        )
        baseline = candidate_from_work_item(payload, ready_context())
        scope = baseline.metadata["idempotency_scope"]

        candidate = candidate_from_work_item(
            payload,
            ready_context(
                completed_dependencies=frozenset(),
                active_claims=frozenset({"scripts/dispatcher_v2.py"}),
                incompatible_reservation=True,
                active_idempotency_scopes=frozenset({scope}),
            ),
        )
        self.assertEqual(
            set(classify_readiness(candidate).reasons),
            {
                "open_dependencies",
                "claim_overlap",
                "incompatible_reservation",
                "idempotency_active",
            },
        )

    def test_work_item_authority_class_preserves_dispatcher_hierarchy(self):
        candidates = [
            candidate_from_work_item(
                work_item(work_id="health", authority_level="health", priority_class="medium"),
                ready_context(),
            ),
            candidate_from_work_item(
                work_item(work_id="incident", authority_level="incident", priority_class="medium"),
                ready_context(),
            ),
            candidate_from_work_item(
                work_item(work_id="active", authority_level="active_fix", priority_class="medium"),
                ready_context(),
            ),
            candidate_from_work_item(
                work_item(work_id="decision", authority_level="owner_decision", priority_class="medium"),
                ready_context(),
            ),
            candidate_from_work_item(
                work_item(work_id="critical", authority_level="standard", priority_class="critical"),
                ready_context(),
            ),
        ]
        self.assertEqual(select_next(candidates).key, "health")
        self.assertEqual([authority_class(c) for c in candidates], [
            "health",
            "incident",
            "active_fix",
            "owner_decision",
            "critical",
        ])

    def test_non_code_work_item_can_be_ready_without_repository(self):
        payload = work_item(
            work_type="content",
            repository_ref=None,
            claims=[],
            requested_capabilities=["writing"],
            required_roles=["producto"],
        )
        candidate = candidate_from_work_item(payload, ready_context())
        self.assertTrue(classify_readiness(candidate).ready)
        self.assertIsNone(candidate.metadata["repository_ref"])


class AdaptiveDispatcherIntegrationTests(unittest.TestCase):
    def adaptive_snapshot(self, freshness="fresh"):
        """Snapshot mínimo para composición Presence -> Fencing -> Dispatcher."""
        return {
            "version": 1,
            "source": "controlbot-runtime",
            "observed_at": "2026-09-27T23:50:00Z",
            "sessions": [{
                "session_id": "s1",
                "agent_id": "a1",
                "project": "factory",
                "repo": "pl0n3r/Factory",
                "work_item": "Factory#283",
                "issue_ref": "#283",
                "pr_ref": None,
                "state": "working",
                "assignment": "integration",
                "claims": ["scripts/dispatcher_v2.py"],
                "capabilities": ["python"],
                "heartbeat_at": "2026-09-27T23:49:30Z",
                "freshness": freshness,
                "generation": 7,
                "attempt": 1,
                "safe_point": True,
                "preemptibility": "preemptible",
            }],
            "capacity": {
                "known_slots": 2,
                "eligible_free_slots": 1,
                "degraded_slots": 0,
                "freshness": "fresh",
            },
        }

    def fenced(self, snapshot=None, generation=7):
        """Construye una decisión de fencing válida o stale según generation."""
        snapshot = snapshot or self.adaptive_snapshot()
        return evaluate_fencing(
            snapshot,
            [{
                "event": {
                    "event_type": "capacity_changed",
                    "subject": "factory",
                    "state": "changed",
                    "evidence_ref": "issue:283",
                },
                "generation": generation,
                "attempt": 1,
            }],
            current_generation=7,
            current_attempt=1,
            cooldown_seconds=0,
            elapsed_since_replan=0,
            active_work_safe=False,
            active_work_ready=True,
            safe_point=True,
            preemptibility="preemptible",
        )

    def test_presence_unknown_or_stale_is_not_ready(self):
        """AC-01: presence incierta nunca se convierte en capacidad utilizable."""
        for freshness, expected in (("unknown", "adaptive_presence_unknown"), ("stale", "adaptive_presence_stale")):
            with self.subTest(freshness=freshness):
                snapshot = self.adaptive_snapshot(freshness)
                presence = classify_presence(snapshot)
                fencing = self.fenced(snapshot)
                adapted = adapt_candidates_for_adaptive(
                    [Candidate(key="candidate", priority="critical")],
                    presence=presence,
                    fencing=fencing,
                    replan_action="fail_closed",
                )
                readiness = classify_readiness(adapted[0])
                self.assertFalse(readiness.ready)
                self.assertIn(expected, readiness.reasons)

    def test_adaptive_replan_preserves_authority_hierarchy(self):
        """AC-02: Adaptive no cambia la jerarquía canónica de autoridad."""
        presence = classify_presence(self.adaptive_snapshot())
        fencing = self.fenced()
        candidates = [
            Candidate(key="critical", priority="critical"),
            Candidate(key="decision", owner_decision_resolved=True),
            Candidate(key="active", active_fix=True),
            Candidate(key="incident", incident=True),
            Candidate(key="health", health=True),
        ]
        adapted = adapt_candidates_for_adaptive(
            candidates,
            presence=presence,
            fencing=fencing,
            replan_action="replan",
        )
        self.assertEqual(select_next(adapted).key, "health")
        self.assertEqual(
            [authority_class(c) for c in adapted],
            ["critical", "owner_decision", "active_fix", "incident", "health"],
        )

    def test_stale_generation_is_excluded_before_selection(self):
        """AC-03: generation stale bloquea candidatos antes del selector."""
        snapshot = self.adaptive_snapshot()
        presence = classify_presence(snapshot)
        fencing = self.fenced(snapshot, generation=6)
        adapted = adapt_candidates_for_adaptive(
            [Candidate(key="stale", priority="critical")],
            presence=presence,
            fencing=fencing,
            replan_action="fail_closed",
        )
        readiness = classify_readiness(adapted[0])
        self.assertFalse(readiness.ready)
        self.assertTrue(
            any(
                reason.startswith("adaptive_fencing_invalid:stale_generation")
                for reason in readiness.reasons
            )
        )
        self.assertIsNone(select_next(adapted))

    def test_adaptive_parallelism_reuses_existing_dag_and_claim_rules(self):
        """AC-04: paralelismo sigue DAG y claims del dispatcher existente."""
        presence = classify_presence(self.adaptive_snapshot())
        fencing = self.fenced()
        candidates = [
            Candidate(key="a", claims=frozenset({"x"})),
            Candidate(key="b", claims=frozenset({"x"})),
            Candidate(key="c", claims=frozenset({"y"})),
            Candidate(key="blocked", dependencies_open=("dep",)),
        ]
        adapted = adapt_candidates_for_adaptive(
            candidates,
            presence=presence,
            fencing=fencing,
            replan_action="replan",
        )
        keys = {item.key for item in parallel_ready(adapted)}
        self.assertIn("c", keys)
        self.assertEqual(len(keys & {"a", "b"}), 1)
        self.assertNotIn("blocked", keys)

    def test_safe_active_work_continuity_survives_replan(self):
        """AC-05: continuidad existente sobrevive si sigue siendo canónica."""
        presence = classify_presence(self.adaptive_snapshot())
        fencing = self.fenced()
        active = Candidate(key="active", priority="high", continuity=10)
        rival = Candidate(key="rival", priority="high")
        adapted = adapt_candidates_for_adaptive(
            [rival, active],
            presence=presence,
            fencing=fencing,
            replan_action="keep",
            replan_reasons=("continuity_preserved",),
        )
        self.assertEqual(select_next(adapted).key, "active")

    def test_adaptive_metadata_is_attributable_without_runtime_persistence(self):
        """AC-06: salida expone fingerprints/generation como metadata."""
        presence = classify_presence(self.adaptive_snapshot())
        fencing = self.fenced()
        record = adaptive_dispatch_record(
            [Candidate(key="chosen", priority="high")],
            presence=presence,
            fencing=fencing,
            replan_action="replan",
            replan_reasons=("presence_or_capacity_changed",),
        )
        adaptive = record["adaptive"]
        self.assertEqual(len(adaptive["snapshot_fingerprint"]), 64)
        self.assertEqual(len(adaptive["event_fingerprint"]), 64)
        self.assertEqual(adaptive["generation"], 7)
        self.assertEqual(record["candidates"]["chosen"]["metadata"]["adaptive"], adaptive)

    def test_presence_replan_fencing_e2e_uses_single_dispatcher_ranking(self):
        """AC-07: E2E termina en el único ranking de Dispatcher V2."""
        snapshot = self.adaptive_snapshot()
        presence = classify_presence(snapshot)
        event_payload = {
            "event_type": "incident_changed",
            "subject": "factory",
            "state": "open",
            "evidence_ref": "issue:283",
        }
        replan = decide_replan(
            snapshot,
            [event_payload],
            active_work_safe=True,
            active_work_ready=True,
        )
        fencing = evaluate_fencing(
            snapshot,
            [{"event": event_payload, "generation": 7, "attempt": 1}],
            current_generation=7,
            current_attempt=1,
            cooldown_seconds=300,
            elapsed_since_replan=0,
            active_work_safe=True,
            active_work_ready=True,
            safe_point=True,
            preemptibility="preemptible",
        )
        record = adaptive_dispatch_record(
            [
                Candidate(key="critical", priority="critical"),
                Candidate(key="incident", incident=True),
                Candidate(key="health", health=True),
            ],
            presence=presence,
            fencing=fencing,
            replan_action=replan.action,
            replan_reasons=replan.reasons,
        )
        self.assertEqual(replan.action, "replan")
        self.assertEqual(fencing.action, "replan")
        self.assertEqual(record["selected"], "health")
        self.assertEqual(record["selected_class"], "health")


if __name__ == "__main__":
    unittest.main()
