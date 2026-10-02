#!/usr/bin/env python3
import inspect
import unittest
from unittest.mock import patch

from scripts.dispatcher_v2 import (
    BlockedWork,
    Candidate,
    DirectionGateInstance,
    DirectionLeaf,
    DirectionProposal,
    WorkItemReadinessContext,
    adaptive_dispatch_record,
    adapt_candidates_for_adaptive,
    authority_class,
    candidate_from_work_item,
    classify_readiness,
    direction_gate_trigger,
    idle_time_metric,
    dispatch_record,
    materialize_direction_leaves,
    reconcile_direction_gate_instances,
    parallel_ready,
    select_next,
    work_ladder,
)

from scripts.adaptive_fencing import FencingContext, FencingDecision, evaluate_fencing
from scripts.adaptive_replan import decide_replan
from scripts.presence_contract import classify_presence
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import DailySummary, WatchdogDecision, WatchdogIncident


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


def unattended_guard_decision(
    action="ALLOW",
    *,
    authority="unchanged",
):
    return GuardDecision(
        action=action,
        authority=authority,
        pause_allowed=action == "PAUSE",
        reasons=("synthetic-guard",),
        evidence_fingerprint="c" * 64,
    )


def unattended_watchdog_decision(
    action="ALLOW",
    *,
    authority="unchanged",
):
    return WatchdogDecision(
        action=action,
        authority=authority,
        incidents=(),
        new_alert_fingerprints=(),
        interrupt_owner=False,
        daily_summary=DailySummary(
            active_fronts=(),
            state_freshness="fresh",
            incidents=(),
            blockers=(),
            human_gates=(),
            integrated=(),
            reverted=(),
            next_actions=(),
        ),
        evidence_fingerprint="d" * 64,
    )


class DispatcherV2Tests(unittest.TestCase):
    def test_work_ladder_never_returns_none_when_all_repos_have_no_ready(self):
        candidates = [
            Candidate(
                key=f"{repo}#blocked",
                blocked=True,
                metadata={"repository_ref": repo},
            )
            for repo in (
                "pl0n3r/Factory",
                "pl0n3r/Condor",
                "pl0n3r/GrindFlow",
                "pl0n3r/brvtal",
                "pl0n3r/ControlBot",
                "pl0n3r/AutoFactory",
                "pl0n3r/FactoryRunner",
            )
        ]

        result = work_ladder(candidates)
        record = dispatch_record(candidates)

        self.assertIsNotNone(result)
        self.assertEqual(result["step"], "declare_idle_reason")
        self.assertEqual(result["work"]["kind"], "status")
        self.assertTrue(result["reason"])
        self.assertTrue(result["needs"])
        self.assertIsNone(record["selected"])
        self.assertIsNotNone(record["next_action"])
        self.assertEqual(record["next_action"]["step"], "declare_idle_reason")

    def test_stale_block_sweeper_unblocks_satisfied_condition_once(self):
        block = BlockedWork(
            key="pl0n3r/Condor#425",
            unlock_condition="V0.1.107 está VALIDATED_IN_PRODUCTION",
            condition_satisfied=True,
            evidence_refs=("run:36922566823", "sha:4ad0f7b"),
        )

        first = work_ladder([], blocked_work=[block])
        second = work_ladder(
            [],
            blocked_work=[block],
            reconciled_block_keys=("pl0n3r/Condor#425",),
        )

        self.assertEqual(first["step"], "reconcile_stale_blocks")
        self.assertEqual(first["actions"][0]["action"], "unblock")
        self.assertIn("run:36922566823", first["actions"][0]["evidence_refs"])
        self.assertIn("Evidencia:", first["actions"][0]["comment"])
        self.assertEqual(second["step"], "declare_idle_reason")

    def test_work_ladder_never_preempts_higher_priority_work(self):
        normal = Candidate(
            key="normal-product",
            priority="medium",
            metadata={"work_ladder_lane": "normal"},
        )
        quality = Candidate(
            key="quality-critical",
            priority="critical",
            metadata={"work_ladder_lane": "quality"},
        )
        filler = Candidate(
            key="filler-critical",
            priority="critical",
            metadata={"work_ladder_lane": "filler"},
        )

        result = work_ladder([filler, quality, normal])

        self.assertEqual(result["step"], "normal")
        self.assertEqual(result["work"]["key"], "normal-product")

    def test_work_ladder_respects_filler_parallel_limit(self):
        filler = Candidate(
            key="filler",
            priority="medium",
            metadata={
                "work_ladder_lane": "filler",
                "filler_curated": True,
                "filler_reversible": True,
                "filler_no_spend": True,
            },
        )

        available = work_ladder(
            [filler],
            active_filler_count=0,
            max_filler_parallel=1,
        )
        capped = work_ladder(
            [filler],
            active_filler_count=1,
            max_filler_parallel=1,
        )

        self.assertEqual(available["step"], "filler")
        self.assertEqual(capped["step"], "declare_idle_reason")

    def test_work_ladder_caps_parallel_fillers_and_rejects_expensive_work(self):
        safe = Candidate(
            key="safe-filler",
            priority="medium",
            effort=2,
            risk=1,
            metadata={
                "work_ladder_lane": "filler",
                "filler_curated": True,
                "filler_reversible": True,
                "filler_no_spend": True,
            },
        )
        uncurated = Candidate(
            key="uncurated",
            metadata={"work_ladder_lane": "filler"},
        )
        expensive = Candidate(
            key="expensive",
            effort=3,
            risk=1,
            metadata={
                "work_ladder_lane": "filler",
                "filler_curated": True,
                "filler_reversible": True,
                "filler_no_spend": True,
            },
        )
        risky = Candidate(
            key="risky",
            effort=1,
            risk=2,
            metadata={
                "work_ladder_lane": "filler",
                "filler_curated": True,
                "filler_reversible": True,
                "filler_no_spend": True,
            },
        )
        paid = Candidate(
            key="paid",
            metadata={
                "work_ladder_lane": "filler",
                "filler_curated": True,
                "filler_reversible": True,
                "filler_no_spend": False,
            },
        )

        self.assertEqual(
            work_ladder([safe], active_filler_count=1)["step"],
            "filler",
        )
        self.assertEqual(
            work_ladder([safe], active_filler_count=2)["step"],
            "declare_idle_reason",
        )
        for candidate in (uncurated, expensive, risky, paid):
            with self.subTest(candidate=candidate.key):
                self.assertEqual(
                    work_ladder([candidate])["step"],
                    "declare_idle_reason",
                )
        with self.assertRaisesRegex(ValueError, "capped at 2"):
            work_ladder([safe], max_filler_parallel=3)

    def test_work_ladder_declares_reason_when_no_safe_work_exists(self):
        result = work_ladder(
            [],
            no_safe_work_reason=(
                "Todos los candidatos requieren una puerta humana o evidencia nueva."
            ),
        )

        self.assertEqual(result["step"], "declare_idle_reason")
        self.assertEqual(
            result["reason"],
            "Todos los candidatos requieren una puerta humana o evidencia nueva.",
        )
        self.assertEqual(result["work"]["key"], "dispatcher:no-safe-work")

    def test_idle_time_metric_alerts_over_threshold(self):
        healthy = idle_time_metric(
            agent_id="agent-1",
            repository_ref="pl0n3r/Factory",
            finished_at="2026-10-01T20:00:00Z",
            next_dispatch_at="2026-10-01T20:10:00Z",
            threshold_minutes=15,
        )
        degraded = idle_time_metric(
            agent_id="agent-1",
            repository_ref="pl0n3r/Factory",
            finished_at="2026-10-01T20:00:00Z",
            next_dispatch_at="2026-10-01T20:16:00Z",
            threshold_minutes=15,
        )

        self.assertFalse(healthy["alert"])
        self.assertEqual(healthy["quality_health"], "HEALTHY")
        self.assertTrue(degraded["alert"])
        self.assertEqual(degraded["quality_health"], "DEGRADED")
        self.assertEqual(degraded["idle_seconds"], 960)

    def test_product_direction_trigger_covers_all_repos_when_everything_is_blocked(self):
        repositories = (
            "pl0n3r/Factory",
            "pl0n3r/Condor",
            "pl0n3r/GrindFlow",
            "pl0n3r/brvtal",
            "pl0n3r/ControlBot",
            "pl0n3r/AutoFactory",
            "pl0n3r/FactoryRunner",
        )
        for repo in repositories:
            with self.subTest(repo=repo):
                proposal = DirectionProposal(
                    repository_ref=repo,
                    objective="Mantener una cola útil y reversible.",
                    leaves=(
                        DirectionLeaf(
                            key=f"{repo.rsplit('/', 1)[-1].lower()}-next",
                            title="Siguiente trabajo seguro",
                            acceptance_targets=(
                                "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                            ),
                        ),
                    ),
                )
                blocked = Candidate(
                    key=f"{repo}#blocked",
                    blocked=True,
                    metadata={"repository_ref": repo},
                )

                result = work_ladder(
                    [blocked],
                    direction_proposals=(proposal,),
                )

                self.assertEqual(result["step"], "product_direction")
                self.assertEqual(
                    result["work"]["key"],
                    f"product-direction:{repo}",
                )

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

    def test_future_product_tranche_is_not_ready_while_previous_tranche_is_open(self):
        candidate = Candidate(
            key="product-t3",
            priority="high",
            tranche_subject=True,
            tranche=3,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        state = classify_readiness(candidate, active_tranche=2)
        self.assertFalse(state.ready)
        self.assertIn("future_tranche_blocked", state.reasons)
        self.assertIsNone(select_next([candidate], active_tranche=2))

    def test_preemptive_authority_classes_bypass_normal_tranche_gate(self):
        candidates = [
            Candidate(key="health", health=True, tranche_subject=True, tranche=3),
            Candidate(key="incident", incident=True, tranche_subject=True, tranche=3),
            Candidate(key="auto-incident", auto_class="AUTO_INCIDENT", tranche_subject=True, tranche=3),
            Candidate(key="active", active_fix=True, tranche_subject=True, tranche=3),
            Candidate(
                key="decision",
                owner_decision_resolved=True,
                tranche_subject=True,
                tranche=3,
            ),
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate.key):
                state = classify_readiness(candidate, active_tranche=2)
                self.assertTrue(state.ready)
                self.assertNotIn("future_tranche_blocked", state.reasons)

    def test_factory_maintenance_exception_remains_ready_during_open_tranche(self):
        factory = Candidate(
            key="factory-hardening",
            priority="high",
            tranche_subject=True,
            tranche=3,
            tranche_exception=True,
            metadata={"repository_ref": "pl0n3r/Factory"},
        )
        product = Candidate(
            key="product-hardening",
            priority="high",
            tranche_subject=True,
            tranche=3,
            tranche_exception=True,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        self.assertTrue(classify_readiness(factory, active_tranche=2).ready)
        self.assertFalse(classify_readiness(product, active_tranche=2).ready)

    def test_condor_375_regression_is_excluded_with_structured_reason(self):
        candidate = Candidate(
            key="pl0n3r/Condor#375",
            priority="high",
            tranche_subject=True,
            tranche=3,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        record = dispatch_record([candidate], active_tranche=2)
        self.assertIsNone(record["selected"])
        self.assertEqual(
            record["excluded"]["pl0n3r/Condor#375"],
            ["future_tranche_blocked"],
        )
        self.assertEqual(record["active_tranche"], 2)
        self.assertEqual(
            parallel_ready([candidate], active_tranche=2),
            [],
        )

    def test_tranche_subject_product_fails_closed_without_tranche_evidence(self):
        missing_candidate_tranche = Candidate(
            key="missing-candidate",
            tranche_subject=True,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        missing_global_tranche = Candidate(
            key="missing-global",
            tranche_subject=True,
            tranche=3,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        legacy = Candidate(key="legacy", priority="high")

        self.assertIn(
            "tranche_evidence_missing",
            classify_readiness(
                missing_candidate_tranche,
                active_tranche=2,
            ).reasons,
        )
        self.assertIn(
            "tranche_evidence_missing",
            classify_readiness(missing_global_tranche).reasons,
        )
        self.assertTrue(classify_readiness(legacy).ready)
        self.assertEqual(select_next([legacy]).key, "legacy")

    def test_work_item_adapter_carries_explicit_tranche_evidence(self):
        candidate = candidate_from_work_item(
            work_item(
                work_id="pl0n3r/Condor#375",
                repository_ref="pl0n3r/Condor",
            ),
            ready_context(
                tranche_subject=True,
                tranche=3,
            ),
        )

        record = dispatch_record([candidate], active_tranche=2)

        self.assertIsNone(record["selected"])
        self.assertEqual(
            record["excluded"]["pl0n3r/Condor#375"],
            ["future_tranche_blocked"],
        )
        self.assertTrue(
            record["candidates"]["pl0n3r/Condor#375"]["tranche_subject"],
        )
        self.assertEqual(
            record["candidates"]["pl0n3r/Condor#375"]["tranche"],
            3,
        )

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
            FencingContext(
                current_generation=7,
                current_attempt=1,
                cooldown_seconds=0,
                elapsed_since_replan=0,
                active_work_safe=False,
                active_work_ready=True,
                safe_point=True,
                preemptibility="preemptible",
            ),
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

    def test_reasonless_fail_closed_still_blocks_readiness(self):
        """Regresión: fail_closed sin reasons nunca puede quedar ready."""
        presence = classify_presence(self.adaptive_snapshot())
        fencing = FencingDecision(
            action="fail_closed",
            pause_allowed=False,
            generation=7,
            attempt=1,
            snapshot_fingerprint="a" * 64,
            event_fingerprint="b" * 64,
            coalesced_events=0,
            reasons=(),
        )
        adapted = adapt_candidates_for_adaptive(
            [Candidate(key="blocked", priority="critical")],
            presence=presence,
            fencing=fencing,
            replan_action="fail_closed",
        )
        readiness = classify_readiness(adapted[0])
        self.assertFalse(readiness.ready)
        self.assertIn("adaptive_fencing_invalid", readiness.reasons)

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

    def test_unattended_dispatch_requires_canonical_guard_and_watchdog_decisions(self):
        presence = classify_presence(self.adaptive_snapshot())
        record = adaptive_dispatch_record(
            [Candidate(key="candidate", priority="critical")],
            presence=presence,
            fencing=self.fenced(),
            replan_action="keep",
            unattended_mode=True,
        )

        self.assertIsNone(record["selected"])
        self.assertEqual(record["next_action"]["step"], "unattended_gate")
        self.assertEqual(record["next_action"]["action"], "BLOCKED")
        self.assertEqual(record["unattended"]["authority"], "unchanged")
        self.assertIn(
            "unattended_guard_decision_invalid",
            record["unattended"]["reasons"],
        )

    def test_unattended_pause_or_blocked_decision_suppresses_new_dispatch(self):
        presence = classify_presence(self.adaptive_snapshot())

        for action in ("PAUSE", "BLOCKED"):
            with self.subTest(action=action):
                record = adaptive_dispatch_record(
                    [Candidate(key="candidate", priority="critical")],
                    presence=presence,
                    fencing=self.fenced(),
                    replan_action="keep",
                    unattended_mode=True,
                    unattended_guard=unattended_guard_decision(action),
                    unattended_watchdog=unattended_watchdog_decision(action),
                )

                self.assertIsNone(record["selected"])
                self.assertEqual(record["next_action"]["step"], "unattended_gate")
                self.assertEqual(record["next_action"]["action"], action)
                self.assertEqual(record["next_action"]["authority"], "unchanged")
                self.assertTrue(record["next_action"]["reasons"])
                self.assertIn(
                    f"unattended_watchdog_{action.lower()}",
                    record["next_action"]["reasons"],
                )
                self.assertIn(
                    "guard:synthetic-guard",
                    record["next_action"]["reasons"],
                )

        hardened = adaptive_dispatch_record(
            [Candidate(key="candidate", priority="critical")],
            presence=presence,
            fencing=self.fenced(),
            replan_action="keep",
            unattended_mode=True,
            unattended_guard=unattended_guard_decision("PAUSE"),
            unattended_watchdog=unattended_watchdog_decision("BLOCKED"),
        )
        self.assertEqual(hardened["next_action"]["action"], "BLOCKED")
        self.assertIn("guard:synthetic-guard", hardened["next_action"]["reasons"])

        reported_incident = WatchdogIncident(
            code="reported:ops incident 42",
            severity="S3",
            fingerprint="e" * 64,
            repeated=False,
            reasons=("source:synthetic", "freshness:fresh"),
        )
        reported_watchdog = WatchdogDecision(
            action="BLOCKED",
            authority="unchanged",
            incidents=(reported_incident,),
            new_alert_fingerprints=("e" * 64,),
            interrupt_owner=False,
            daily_summary=DailySummary(
                active_fronts=(),
                state_freshness="fresh",
                incidents=("S3:reported:ops incident 42",),
                blockers=("reported:ops incident 42",),
                human_gates=(),
                integrated=(),
                reverted=(),
                next_actions=(),
            ),
            evidence_fingerprint="f" * 64,
        )
        compatible_code = adaptive_dispatch_record(
            [Candidate(key="candidate", priority="critical")],
            presence=presence,
            fencing=self.fenced(),
            replan_action="keep",
            unattended_mode=True,
            unattended_guard=unattended_guard_decision("ALLOW"),
            unattended_watchdog=reported_watchdog,
        )
        self.assertEqual(compatible_code["next_action"]["action"], "BLOCKED")
        self.assertIn(
            "watchdog:reported:ops incident 42",
            compatible_code["next_action"]["reasons"],
        )

    def test_unattended_inconsistent_or_expanded_authority_fails_closed(self):
        presence = classify_presence(self.adaptive_snapshot())

        cases = (
            (
                unattended_guard_decision("ALLOW", authority="expanded"),
                unattended_watchdog_decision("ALLOW"),
                "unattended_guard_authority_invalid",
            ),
            (
                unattended_guard_decision("PAUSE"),
                unattended_watchdog_decision("ALLOW"),
                "unattended_decisions_incoherent",
            ),
            (
                GuardDecision(
                    action="ALLOW",
                    authority="unchanged",
                    pause_allowed=False,
                    reasons=(),
                    evidence_fingerprint="bad",
                ),
                unattended_watchdog_decision("ALLOW"),
                "unattended_guard_evidence_invalid",
            ),
            (
                unattended_guard_decision("ALLOW"),
                WatchdogDecision(
                    action="ALLOW",
                    authority="unchanged",
                    incidents=(),
                    new_alert_fingerprints=(),
                    interrupt_owner=False,
                    daily_summary=DailySummary(
                        active_fronts=(),
                        state_freshness="fresh",
                        incidents=(),
                        blockers=(),
                        human_gates=(),
                        integrated=(),
                        reverted=(),
                        next_actions=(),
                    ),
                    evidence_fingerprint="bad",
                ),
                "unattended_watchdog_contract_incoherent",
            ),
            (
                unattended_guard_decision("ALLOW"),
                WatchdogDecision(
                    action="ALLOW",
                    authority="unchanged",
                    incidents=(
                        WatchdogIncident(
                            code="reported:synthetic-s1",
                            severity="S1",
                            fingerprint="1" * 64,
                            repeated=False,
                            reasons=("source:synthetic", "freshness:fresh"),
                        ),
                    ),
                    new_alert_fingerprints=("1" * 64,),
                    interrupt_owner=True,
                    daily_summary=DailySummary(
                        active_fronts=(),
                        state_freshness="fresh",
                        incidents=("S1:reported:synthetic-s1",),
                        blockers=("reported:synthetic-s1",),
                        human_gates=(),
                        integrated=(),
                        reverted=(),
                        next_actions=(),
                    ),
                    evidence_fingerprint="2" * 64,
                ),
                "unattended_watchdog_contract_incoherent",
            ),
        )

        for guard, watchdog, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                record = adaptive_dispatch_record(
                    [Candidate(key="candidate", priority="critical")],
                    presence=presence,
                    fencing=self.fenced(),
                    replan_action="keep",
                    unattended_mode=True,
                    unattended_guard=guard,
                    unattended_watchdog=watchdog,
                )

                self.assertIsNone(record["selected"])
                self.assertEqual(record["next_action"]["action"], "BLOCKED")
                self.assertIn(expected_reason, record["unattended"]["reasons"])

    def test_unattended_allow_preserves_adaptive_dispatch_selection(self):
        presence = classify_presence(self.adaptive_snapshot())
        candidates = [
            Candidate(key="high", priority="high"),
            Candidate(key="critical", priority="critical"),
        ]
        legacy = adaptive_dispatch_record(
            candidates,
            presence=presence,
            fencing=self.fenced(),
            replan_action="replan",
            replan_reasons=("capacity_changed",),
        )
        unattended = adaptive_dispatch_record(
            candidates,
            presence=presence,
            fencing=self.fenced(),
            replan_action="replan",
            replan_reasons=("capacity_changed",),
            unattended_mode=True,
            unattended_guard=unattended_guard_decision("ALLOW"),
            unattended_watchdog=unattended_watchdog_decision("ALLOW"),
        )

        self.assertEqual(unattended["unattended"]["action"], "ALLOW")
        comparable = dict(unattended)
        comparable.pop("unattended")
        self.assertEqual(comparable, legacy)

    def test_unattended_mode_off_preserves_legacy_adaptive_dispatch(self):
        presence = classify_presence(self.adaptive_snapshot())
        candidates = [Candidate(key="candidate", priority="critical")]

        legacy = adaptive_dispatch_record(
            candidates,
            presence=presence,
            fencing=self.fenced(),
            replan_action="keep",
        )
        explicit_off = adaptive_dispatch_record(
            candidates,
            presence=presence,
            fencing=self.fenced(),
            replan_action="keep",
            unattended_mode=False,
            unattended_guard=object(),
            unattended_watchdog=object(),
        )

        self.assertEqual(explicit_off, legacy)
        self.assertNotIn("unattended", explicit_off)

    def test_unattended_dispatch_integration_is_pure_and_reuses_canonical_decisions(self):
        import scripts.dispatcher_v2 as dispatcher_module

        source = (
            inspect.getsource(dispatcher_module._unattended_dispatch_gate)
            + inspect.getsource(dispatcher_module._suppressed_adaptive_dispatch_record)
            + inspect.getsource(adaptive_dispatch_record)
        )

        self.assertIn("GuardDecision", source)
        self.assertIn("WatchdogDecision", source)
        self.assertNotIn("evaluate_unattended_guards", source)
        self.assertNotIn("evaluate_unattended_watchdog", source)
        for forbidden in (
            "requests.",
            "subprocess.",
            "socket.",
            "urllib.",
            "httpx.",
            "github.",
        ):
            self.assertNotIn(forbidden, source)

        presence = classify_presence(self.adaptive_snapshot())
        with patch(
            "scripts.dispatcher_v2.work_ladder",
            side_effect=AssertionError("blocked unattended path must not invoke work_ladder"),
        ):
            blocked = adaptive_dispatch_record(
                [Candidate(key="candidate", priority="critical")],
                presence=presence,
                fencing=self.fenced(),
                replan_action="keep",
                unattended_mode=True,
                unattended_guard=unattended_guard_decision("BLOCKED"),
                unattended_watchdog=unattended_watchdog_decision("BLOCKED"),
            )
        self.assertEqual(blocked["next_action"]["step"], "unattended_gate")
        self.assertFalse(blocked["next_action"]["mutates"])

    def direction_proposal(self):
        return DirectionProposal(
            repository_ref="pl0n3r/Condor",
            objective=(
                "Abrir el siguiente tramo funcional sin saltar la decisión del dueño."
            ),
            leaves=(
                DirectionLeaf(
                    key="condor-next-1",
                    title="Primer leaf del nuevo tramo",
                    acceptance_targets=(
                        "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                    ),
                ),
                DirectionLeaf(
                    key="condor-next-2",
                    title="Segundo leaf dependiente",
                    acceptance_targets=("check:validate",),
                    depends_on=("condor-next-1",),
                ),
            ),
        )

    def test_empty_product_queue_creates_single_direction_gate(self):
        trigger = direction_gate_trigger(self.direction_proposal(), [])
        self.assertEqual(trigger["action"], "open_gate")
        self.assertFalse(trigger["materialize_leaves"])
        self.assertEqual(trigger["gate"]["category"], "product-direction")
        self.assertEqual(trigger["gate"]["safe_default"], "B")
        self.assertEqual(len(trigger["proposal"]["leaves"]), 2)
        self.assertIn("factory-human-gate", trigger["marker"])

    def test_direction_gate_requires_approval_before_materializing_leaves(self):
        proposal = self.direction_proposal()
        opened = direction_gate_trigger(proposal, [])
        self.assertEqual(materialize_direction_leaves(proposal, decision_evidence=None), ())
        declined = {
            "gate_sha256": opened["gate_sha256"], "option": "B", "version": 2
        }
        self.assertEqual(materialize_direction_leaves(proposal, decision_evidence=declined), ())
        approved = {**declined, "option": "A"}
        materialized = materialize_direction_leaves(proposal, decision_evidence=approved)
        self.assertEqual(
            [leaf["key"] for leaf in materialized],
            ["condor-next-1", "condor-next-2"],
        )
        self.assertEqual(
            [leaf["state"] for leaf in materialized],
            ["available", "blocked"],
        )
        self.assertEqual(materialized[1]["depends_on"], ["condor-next-1"])
        stale = {**approved, "gate_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "does not match"):
            materialize_direction_leaves(proposal, decision_evidence=stale)

    def test_materialized_direction_leaf_contains_reservable_contract(self):
        proposal = self.direction_proposal()
        opened = direction_gate_trigger(proposal, [])
        approved = {
            "gate_sha256": opened["gate_sha256"],
            "option": "A",
            "version": 2,
        }

        materialized = materialize_direction_leaves(
            proposal,
            decision_evidence=approved,
        )

        self.assertEqual(len(materialized), 2)
        body = materialized[0]["body"]
        for heading in (
            "### Contexto",
            "### Alcance",
            "### Fuera de alcance",
            "### Criterios de aceptación",
            "### Contrato ejecutable",
        ):
            self.assertEqual(body.count(heading), 1)
        self.assertIn("[AC-01]", body)
        self.assertIn("factory-acceptance", body)

        from scripts.aceptacion_kit import parse_contract

        criteria = parse_contract(body)
        self.assertEqual(
            [(item.id, item.kind, item.target) for item in criteria],
            [
                (
                    "AC-01",
                    "test",
                    "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                )
            ],
        )
        second_criteria = parse_contract(materialized[1]["body"])
        self.assertEqual(
            [(item.id, item.kind, item.target) for item in second_criteria],
            [("AC-01", "check", "validate")],
        )

    def test_direction_leaf_materialization_prevalidates_before_available(self):
        proposal = self.direction_proposal()
        opened = direction_gate_trigger(proposal, [])
        approved = {
            "gate_sha256": opened["gate_sha256"],
            "option": "A",
            "version": 2,
        }

        with patch(
            "scripts.dispatcher_v2.parse_contract",
            side_effect=ValueError("invalid generated contract"),
        ) as preflight:
            with self.assertRaisesRegex(ValueError, "invalid generated contract"):
                materialize_direction_leaves(
                    proposal,
                    decision_evidence=approved,
                )

        preflight.assert_called_once()
        self.assertEqual(
            materialize_direction_leaves(
                proposal,
                decision_evidence={**approved, "option": "B"},
            ),
            (),
        )

    def test_auto_fed_lane_remains_dispatchable_without_owner_gate(self):
        auto = Candidate(
            key="quality-auto",
            title="[AUTO] Quality regression",
            priority="high",
            auto_class="AUTO_SECURITY",
            auto_evidence_reviewed=True,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        trigger = direction_gate_trigger(self.direction_proposal(), [auto])
        self.assertEqual(trigger["action"], "open_gate")
        self.assertFalse(trigger["materialize_leaves"])
        self.assertEqual(trigger["eligible_leaf_count"], 1)
        self.assertEqual(select_next([auto]).key, "quality-auto")

    def test_direction_proposal_rejects_forbidden_acceptance_checks(self):
        for target in ("check:Validar", "check:Criterios de aceptación"):
            with self.subTest(target=target), self.assertRaisesRegex(
                ValueError,
                "factory-acceptance",
            ):
                direction_gate_trigger(
                    DirectionProposal(
                        repository_ref="pl0n3r/Condor",
                        objective="Propuesta inválida por check genérico.",
                        leaves=(
                            DirectionLeaf(
                                key="invalid-check",
                                title="Leaf con check prohibido",
                                acceptance_targets=(target,),
                            ),
                        ),
                    ),
                    [],
                )

    def test_direction_proposal_rejects_noncanonical_test_targets(self):
        with self.assertRaisesRegex(ValueError, "factory-acceptance"):
            direction_gate_trigger(
                DirectionProposal(
                    repository_ref="pl0n3r/Condor",
                    objective="Propuesta inválida por target de test.",
                    leaves=(
                        DirectionLeaf(
                            key="invalid-test",
                            title="Leaf con test no canónico",
                            acceptance_targets=(
                                "tests/test_next_slice.py::NextSliceTests::not_a_test",
                            ),
                        ),
                    ),
                ),
                [],
            )

    def test_direction_proposal_accepts_canonical_targets(self):
        trigger = direction_gate_trigger(
            DirectionProposal(
                repository_ref="pl0n3r/Condor",
                objective="Propuesta con evidencia ejecutable canónica.",
                leaves=(
                    DirectionLeaf(
                        key="canonical-test",
                        title="Leaf con test exacto",
                        acceptance_targets=(
                            "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                        ),
                    ),
                    DirectionLeaf(
                        key="canonical-check",
                        title="Leaf con check específico",
                        acceptance_targets=("check:validate",),
                        depends_on=("canonical-test",),
                    ),
                ),
            ),
            [],
        )
        self.assertEqual(trigger["action"], "open_gate")

    def test_direction_gate_concurrent_creators_converge_to_oldest_valid_issue(self):
        instances = (
            DirectionGateInstance(
                issue_number=408,
                repository_ref="pl0n3r/Condor",
                created_at="2026-10-01T16:31:28Z",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
            DirectionGateInstance(
                issue_number=406,
                repository_ref="pl0n3r/Condor",
                created_at="2026-10-01T16:29:08Z",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
            DirectionGateInstance(
                issue_number=407,
                repository_ref="pl0n3r/Condor",
                created_at="2026-10-01T16:30:33Z",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
        )
        result = reconcile_direction_gate_instances(instances, "pl0n3r/Condor")
        self.assertEqual(result["winner_issue_number"], 406)
        self.assertEqual(result["duplicate_issue_numbers"], (407, 408))

    def test_direction_gate_reconciliation_ignores_closed_invalid_and_other_product(self):
        instances = (
            DirectionGateInstance(
                issue_number=405,
                repository_ref="pl0n3r/Condor",
                created_at="2026-10-01T16:28:00Z",
                state="closed",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
            DirectionGateInstance(
                issue_number=404,
                repository_ref="pl0n3r/Condor",
                created_at="not-a-date",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
            DirectionGateInstance(
                issue_number=220,
                repository_ref="pl0n3r/GrindFlow",
                created_at="2026-10-01T16:20:00Z",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/GrindFlow",
            ),
            DirectionGateInstance(
                issue_number=406,
                repository_ref="pl0n3r/Condor",
                created_at="2026-10-01T16:29:08Z",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
        )
        result = reconcile_direction_gate_instances(instances, "pl0n3r/Condor")
        self.assertEqual(result["winner_issue_number"], 406)
        self.assertEqual(result["duplicate_issue_numbers"], ())

    def test_direction_gate_reconciliation_is_idempotent(self):
        instances = (
            DirectionGateInstance(
                issue_number=407,
                repository_ref="pl0n3r/Condor",
                created_at="2026-10-01T16:30:33Z",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
            DirectionGateInstance(
                issue_number=406,
                repository_ref="pl0n3r/Condor",
                created_at="2026-10-01T16:29:08Z",
                state="open",
                category="product-direction",
                gate_key="product-direction:pl0n3r/Condor",
            ),
        )
        first = reconcile_direction_gate_instances(instances, "pl0n3r/Condor")
        second = reconcile_direction_gate_instances(instances, "pl0n3r/Condor")
        self.assertEqual(first, second)
        self.assertEqual(first["winner_issue_number"], 406)
        self.assertEqual(first["duplicate_issue_numbers"], (407,))

    def test_direction_gate_trigger_is_idempotent_for_empty_open_and_ready_states(self):
        proposal = self.direction_proposal()
        opened = direction_gate_trigger(proposal, [])
        duplicate = direction_gate_trigger(
            proposal,
            [],
            existing_gate_keys=(opened["gate_key"],),
        )
        ready = [
            Candidate(
                key="condor-ready-1",
                priority="high",
                metadata={"repository_ref": "pl0n3r/Condor"},
            ),
            Candidate(
                key="condor-ready-2",
                priority="high",
                metadata={"repository_ref": "pl0n3r/Condor"},
            ),
        ]
        has_work = direction_gate_trigger(proposal, ready)
        self.assertEqual(duplicate["reason"], "direction_gate_already_open")
        self.assertEqual(has_work["reason"], "sufficient_eligible_work")

    def test_direction_gate_threshold_keeps_single_open_gate_per_product(self):
        for repo in ("pl0n3r/Condor", "pl0n3r/GrindFlow", "pl0n3r/brvtal"):
            with self.subTest(repo=repo):
                proposal = DirectionProposal(
                    repository_ref=repo,
                    objective="Preparar el siguiente tramo antes de vaciar la cola.",
                    leaves=(
                        DirectionLeaf(
                            key=f"{repo.rsplit('/', 1)[-1].lower()}-next",
                            title="Siguiente leaf funcional",
                            acceptance_targets=(
                                "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                            ),
                        ),
                    ),
                )
                candidate = Candidate(
                    key=f"{repo}#current",
                    priority="high",
                    metadata={"repository_ref": repo},
                )
                first = direction_gate_trigger(proposal, [candidate])
                second = direction_gate_trigger(
                    proposal,
                    [candidate],
                    existing_gate_keys=(first["gate_key"],),
                )
                self.assertEqual(first["action"], "open_gate")
                self.assertEqual(second["action"], "noop")
                self.assertEqual(second["reason"], "direction_gate_already_open")

    def test_direction_gate_threshold_preserves_executable_proposal_contract(self):
        proposal = self.direction_proposal()
        candidate = Candidate(
            key="condor-current",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        trigger = direction_gate_trigger(proposal, [candidate])
        self.assertEqual(trigger["action"], "open_gate")
        self.assertFalse(trigger["materialize_leaves"])
        self.assertEqual(trigger["gate"]["category"], "product-direction")
        self.assertEqual(trigger["gate"]["safe_default"], "B")
        self.assertEqual(
            [option["id"] for option in trigger["gate"]["options"]],
            ["A", "B"],
        )
        self.assertEqual(
            trigger["proposal"]["leaves"][1]["depends_on"],
            ["condor-next-1"],
        )
        self.assertEqual(
            materialize_direction_leaves(proposal, decision_evidence=None),
            (),
        )

    def test_direction_gate_threshold_rejects_reproposal_of_active_segment(self):
        proposal = self.direction_proposal()
        candidate = Candidate(
            key="condor-current",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        first = direction_gate_trigger(proposal, [candidate])
        repeated = direction_gate_trigger(
            proposal,
            [candidate],
            known_proposal_sha256s=(first["proposal_sha256"],),
        )
        self.assertEqual(repeated["action"], "noop")
        self.assertEqual(repeated["reason"], "direction_proposal_already_known")
        self.assertEqual(repeated["proposal_sha256"], first["proposal_sha256"])

    def test_direction_gate_threshold_opens_when_eligible_leaves_are_few(self):
        candidate = Candidate(
            key="condor-current",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        trigger = direction_gate_trigger(self.direction_proposal(), [candidate])
        self.assertEqual(trigger["action"], "open_gate")
        self.assertEqual(trigger["eligible_leaf_count"], 1)
        self.assertEqual(trigger["eligible_leaf_threshold"], 1)
        self.assertFalse(trigger["materialize_leaves"])

    def test_direction_gate_threshold_covers_sufficient_few_and_open_gate_states(self):
        proposal = self.direction_proposal()
        candidates = [
            Candidate(
                key="condor-current-1",
                priority="high",
                metadata={"repository_ref": "pl0n3r/Condor"},
            ),
            Candidate(
                key="condor-current-2",
                priority="high",
                metadata={"repository_ref": "pl0n3r/Condor"},
            ),
        ]
        sufficient = direction_gate_trigger(proposal, candidates)
        few = direction_gate_trigger(proposal, candidates[:1])
        already_open = direction_gate_trigger(
            proposal,
            candidates[:1],
            existing_gate_keys=(few["gate_key"],),
        )
        self.assertEqual(sufficient["action"], "noop")
        self.assertEqual(sufficient["reason"], "sufficient_eligible_work")
        self.assertEqual(sufficient["eligible_leaf_count"], 2)
        self.assertEqual(few["action"], "open_gate")
        self.assertEqual(already_open["action"], "noop")
        self.assertEqual(already_open["reason"], "direction_gate_already_open")

    def test_product_direction_early_trigger_covers_controlbot_autofactory_and_factoryrunner(self):
        for repo in (
            "pl0n3r/ControlBot",
            "pl0n3r/AutoFactory",
            "pl0n3r/FactoryRunner",
        ):
            with self.subTest(repo=repo):
                proposal = DirectionProposal(
                    repository_ref=repo,
                    objective="Preparar el siguiente tramo sin ampliar autoridad.",
                    leaves=(
                        DirectionLeaf(
                            key=f"{repo.rsplit('/', 1)[-1].lower()}-next",
                            title="Siguiente leaf funcional",
                            acceptance_targets=(
                                "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                            ),
                        ),
                    ),
                )
                candidate = Candidate(
                    key=f"{repo}#current",
                    priority="high",
                    metadata={"repository_ref": repo},
                )

                trigger = direction_gate_trigger(proposal, [candidate])

                self.assertEqual(trigger["action"], "open_gate")
                self.assertEqual(trigger["eligible_leaf_count"], 1)
                self.assertEqual(trigger["eligible_leaf_threshold"], 1)
                self.assertFalse(trigger["materialize_leaves"])

    def test_product_direction_factoryrunner_without_open_issues_can_open_single_gate(self):
        proposal = DirectionProposal(
            repository_ref="pl0n3r/FactoryRunner",
            objective="Preparar el siguiente tramo del execution plane.",
            leaves=(
                DirectionLeaf(
                    key="factoryrunner-next",
                    title="Siguiente leaf de FactoryRunner",
                    acceptance_targets=(
                        "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                    ),
                ),
            ),
        )

        first = direction_gate_trigger(proposal, [])
        second = direction_gate_trigger(
            proposal,
            [],
            existing_gate_keys=(first["gate_key"],),
        )

        self.assertEqual(first["action"], "open_gate")
        self.assertEqual(first["eligible_leaf_count"], 0)
        self.assertEqual(second["action"], "noop")
        self.assertEqual(second["reason"], "direction_gate_already_open")

    def test_product_direction_additional_projects_keep_live_spend_and_provider_blocks(self):
        blocked = (
            ("pl0n3r/ControlBot", "Provisionar Backblaze para recuperación real."),
            ("pl0n3r/AutoFactory", "Cambiar plan de la cuenta para ampliar capacidad."),
            ("pl0n3r/FactoryRunner", "Comprar un proveedor de pago para el go-live."),
        )
        for repo, objective in blocked:
            with self.subTest(repo=repo):
                proposal = DirectionProposal(
                    repository_ref=repo,
                    objective=objective,
                    leaves=(
                        DirectionLeaf(
                            key=f"{repo.rsplit('/', 1)[-1].lower()}-blocked-next",
                            title="Leaf fuera de la autoridad operativa vigente",
                            acceptance_targets=(
                                "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                            ),
                        ),
                    ),
                )

                with self.assertRaisesRegex(
                    ValueError, "cannot cross human-only authority blocks"
                ):
                    direction_gate_trigger(proposal, [])

        safe = DirectionProposal(
            repository_ref="pl0n3r/FactoryRunner",
            objective="Mejorar la trazabilidad local del execution plane.",
            leaves=(
                DirectionLeaf(
                    key="factoryrunner-safe-next",
                    title="Trazabilidad reversible del runner",
                    acceptance_targets=(
                        "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                    ),
                ),
            ),
        )
        opened = direction_gate_trigger(safe, [])
        self.assertEqual(opened["gate"]["safe_default"], "B")
        self.assertFalse(opened["materialize_leaves"])

    def test_adaptive_dispatch_propagates_tranche_gate(self):
        presence = classify_presence(self.adaptive_snapshot())
        fencing = self.fenced()
        candidate = Candidate(
            key="adaptive-product-t3",
            priority="high",
            tranche_subject=True,
            tranche=3,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        record = adaptive_dispatch_record(
            [candidate],
            presence=presence,
            fencing=fencing,
            replan_action="replan",
            active_tranche=2,
        )
        self.assertIsNone(record["selected"])
        self.assertEqual(
            record["excluded"]["adaptive-product-t3"],
            ["future_tranche_blocked"],
        )

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
            FencingContext(
                current_generation=7,
                current_attempt=1,
                cooldown_seconds=300,
                elapsed_since_replan=0,
                active_work_safe=True,
                active_work_ready=True,
                safe_point=True,
                preemptibility="preemptible",
            ),
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