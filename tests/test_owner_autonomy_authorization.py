#!/usr/bin/env python3
"""Contrato ejecutable de la autorización permanente acotada Factory#796."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from scripts.dispatcher_v2 import (
    Candidate,
    DirectionLeaf,
    DirectionProposal,
    OwnerAutonomyContext,
    direction_gate_trigger,
    materialize_direction_leaves,
    runway_floor_status,
)
from scripts.unattended_daily_summary import (
    parse_daily_marker,
    parse_night_marker,
    publish_night_report_once,
    publish_once,
)

ROOT = Path(__file__).resolve().parents[1]


class MemoryClient:
    def __init__(self):
        self.comments = []
        self.writes = []

    def list_issue_comments(self, issue_number):
        return list(self.comments)

    def _request(self, method, path, payload=None):
        self.writes.append((method, path, payload))
        return {"ok": True}


class OwnerAutonomyAuthorizationTests(unittest.TestCase):
    def proposal(self):
        return DirectionProposal(
            repository_ref="pl0n3r/Condor",
            objective="Materializar un tramo local y reversible con contrato ejecutable.",
            leaves=(
                DirectionLeaf(
                    key="SAFE_NEXT",
                    title="Leaf local provider-neutral",
                    acceptance_targets=(
                        "tests/test_safe_next.py::SafeNextTests::test_local_contract",
                    ),
                ),
            ),
        )

    def safe_context(self):
        return OwnerAutonomyContext(
            kill_switch_running=True,
            production_green=True,
            risk="medium",
            second_role_reviewed=True,
            go_live=False,
            spend_or_purchase=False,
            paid_provider=False,
            backblaze_real=False,
            real_customer_data=False,
            secrets_or_credentials=False,
            destructive_or_irreversible=False,
            backup_required_without_verified=False,
            grindflow_scope_choice=False,
            legal_or_privacy_gate=False,
            acceptance_executable=True,
        )

    def test_owner_delegation_is_recorded_with_exact_boundaries(self):
        decisions = json.loads((ROOT / "decisiones.yml").read_text(encoding="utf-8"))
        d068 = next(item for item in decisions["decisions"] if item["id"] == "D-068")
        self.assertEqual(d068["status"], "active")
        for boundary in (
            "go-live",
            "gasto",
            "Backblaze",
            "datos reales",
            "secretos",
            "SQL destructivo",
            "GrindFlow",
            "legal/privacidad",
        ):
            self.assertIn(boundary, d068["text"])

        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertIn("D-068 / Factory#796", plan)
        self.assertIn("Materialización bajo autorización permanente del dueño (#796)", plan)
        self.assertIn("proposal_sha256", plan)

    def test_safe_direction_auto_materializes_with_owner_provenance_without_human_click(self):
        proposal = self.proposal()
        context = self.safe_context()
        trigger = direction_gate_trigger(
            proposal,
            [],
            owner_autonomy_context=context,
        )
        self.assertEqual(trigger["action"], "materialize_authorized")
        self.assertTrue(trigger["materialize_leaves"])
        self.assertIn("#796", trigger["audit_comment"])
        self.assertNotIn("factory-human-gate", trigger.get("marker", ""))

        materialized = materialize_direction_leaves(
            proposal,
            owner_autonomy_context=context,
        )
        self.assertEqual(len(materialized), 1)
        self.assertEqual(materialized[0]["state"], "available")
        self.assertEqual(materialized[0]["authorization"]["source_issue"], 796)
        self.assertIn(
            "Materialización bajo autorización permanente del dueño (#796)",
            materialized[0]["body"],
        )
        self.assertIn(trigger["proposal_sha256"], materialized[0]["body"])

        reused = direction_gate_trigger(
            proposal,
            [],
            existing_gate_keys=(trigger["gate_key"],),
            known_proposal_sha256s=(trigger["proposal_sha256"],),
            owner_autonomy_context=context,
        )
        self.assertEqual(reused["action"], "materialize_authorized")
        self.assertTrue(reused["materialize_leaves"])
        self.assertTrue(reused["reuses_existing_gate"])
        self.assertEqual(reused["proposal_sha256"], trigger["proposal_sha256"])

        mismatched = direction_gate_trigger(
            proposal,
            [],
            existing_gate_keys=(trigger["gate_key"],),
            owner_autonomy_context=context,
        )
        self.assertEqual(mismatched["action"], "blocked")
        self.assertFalse(mismatched["materialize_leaves"])
        self.assertEqual(
            mismatched["reason"],
            "direction_gate_open_without_matching_proposal",
        )

    def test_runway_floor_is_three_or_requires_explicit_reason(self):
        self.assertTrue(runway_floor_status(3)["compliant"])
        self.assertFalse(runway_floor_status(2)["compliant"])
        below = runway_floor_status(
            1,
            explicit_reason="dependencia canónica aún abierta",
        )
        self.assertTrue(below["compliant"])
        self.assertEqual(below["target"], 3)

        two_ready = [
            Candidate(
                key=f"condor-ready-{index}",
                priority="high",
                metadata={"repository_ref": "pl0n3r/Condor"},
            )
            for index in range(2)
        ]
        refill = direction_gate_trigger(
            self.proposal(),
            two_ready,
            owner_autonomy_context=self.safe_context(),
        )
        self.assertEqual(refill["action"], "materialize_authorized")
        self.assertEqual(refill["eligible_leaf_count"], 2)
        self.assertEqual(refill["eligible_leaf_threshold"], 2)

        three_ready = [
            *two_ready,
            Candidate(
                key="condor-ready-2",
                priority="high",
                metadata={"repository_ref": "pl0n3r/Condor"},
            ),
        ]
        sufficient = direction_gate_trigger(
            self.proposal(),
            three_ready,
            owner_autonomy_context=self.safe_context(),
        )
        self.assertEqual(sufficient["action"], "noop")
        self.assertEqual(sufficient["reason"], "sufficient_eligible_work")
        self.assertEqual(sufficient["eligible_leaf_count"], 3)
        self.assertEqual(sufficient["eligible_leaf_threshold"], 2)

        legacy = direction_gate_trigger(self.proposal(), two_ready)
        self.assertEqual(legacy["action"], "noop")
        self.assertEqual(legacy["reason"], "sufficient_eligible_work")
        self.assertEqual(legacy["eligible_leaf_threshold"], 1)

    def test_runway_topics_remain_bounded_and_executable(self):
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        for repo in (
            "Condor",
            "GrindFlow",
            "BRVTAL",
            "ControlBot",
            "AutoFactory",
            "FactoryRunner",
            "Factory",
        ):
            self.assertIn(repo, plan)
        self.assertIn("criterios de aceptación ejecutables", plan)
        self.assertIn("Runway D-068", plan)
        self.assertIn("3 hojas elegibles", plan)
        self.assertIn("Factory#796 §4", plan)
        self.assertIn("iniciativas explícitas", plan)
        self.assertIn("pendiente de materialización product-direction", plan)
        self.assertIn("no cuenta para el piso de 3", plan)

    def test_human_only_boundaries_never_auto_authorize(self):
        proposal = self.proposal()
        base = self.safe_context()
        for field in (
            "go_live",
            "spend_or_purchase",
            "paid_provider",
            "backblaze_real",
            "real_customer_data",
            "secrets_or_credentials",
            "destructive_or_irreversible",
            "backup_required_without_verified",
            "grindflow_scope_choice",
            "legal_or_privacy_gate",
        ):
            with self.subTest(field=field):
                trigger = direction_gate_trigger(
                    proposal,
                    [],
                    owner_autonomy_context=replace(base, **{field: True}),
                )
                self.assertEqual(trigger["action"], "open_gate")
                self.assertFalse(trigger["materialize_leaves"])
                self.assertEqual(trigger["gate"]["safe_default"], "B")
                self.assertIn(field, trigger["authorization"]["human_reasons"])

        no_acceptance = direction_gate_trigger(
            proposal,
            [],
            owner_autonomy_context=replace(base, acceptance_executable=False),
        )
        self.assertEqual(no_acceptance["action"], "open_gate")
        self.assertIn(
            "acceptance_not_executable",
            no_acceptance["authorization"]["human_reasons"],
        )

    def test_paused_or_non_green_production_fails_closed(self):
        proposal = self.proposal()
        base = self.safe_context()
        for context, reason in (
            (replace(base, kill_switch_running=False), "kill_switch_not_running"),
            (replace(base, kill_switch_running=None), "kill_switch_not_running"),
            (replace(base, production_green=False), "production_not_green"),
            (replace(base, production_green=None), "production_not_green"),
            (
                replace(base, risk="high", second_role_reviewed=False),
                "second_role_review_required",
            ),
        ):
            with self.subTest(reason=reason):
                trigger = direction_gate_trigger(
                    proposal,
                    [],
                    owner_autonomy_context=context,
                )
                self.assertEqual(trigger["action"], "blocked")
                self.assertFalse(trigger["materialize_leaves"])
                self.assertEqual(trigger["reason"], reason)

    def test_night_report_and_daily_summary_are_deduplicated(self):
        client = MemoryClient()
        date = "2026-10-02"
        daily = (
            '<!-- factory-unattended-daily-summary '
            '{"local_date":"2026-10-02","version":1} -->\n'
            "## Resumen diario Factory"
        )
        night = (
            '<!-- factory-unattended-night-report '
            '{"local_date":"2026-10-02","version":1} -->\n'
            "## Informe de la noche Factory"
        )
        self.assertTrue(publish_night_report_once(client, local_date=date, body=night))
        self.assertTrue(publish_once(client, local_date=date, body=daily))
        client.comments.extend(
            {
                "user": {"login": "github-actions[bot]"},
                "body": write[2]["body"],
            }
            for write in client.writes
        )
        self.assertFalse(publish_night_report_once(client, local_date=date, body=night))
        self.assertFalse(publish_once(client, local_date=date, body=daily))
        self.assertEqual(len(client.writes), 2)
        self.assertEqual(parse_night_marker(client.comments[0]), date)
        self.assertEqual(parse_daily_marker(client.comments[1]), date)


if __name__ == "__main__":
    unittest.main()
