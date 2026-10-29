"""#1810: offline behavioral coverage for real pruning and provenance boundaries.

The historical cross-repository inventory and the requirement to run a real
Evolution Engine/Factory Lab process are *not* certified by these fixtures.
No matrix state, network requests, credentials, personal data or production.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest
from unittest.mock import patch

from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from evolution.growth import canonical_capability
from evolution.immune import ImmuneError, ImmuneIncident, compile_immunity_candidate
from evolution.provenance import (
    TrustedDecisionSource,
    TrustedIncidentRegistry,
    authenticated_decision_reader_from_environment,
    authenticated_incident_reader_from_environment,
)
from evolution.pruning import (
    PruningError,
    compile_pruning_candidate,
    evaluate_pruning,
)
from evolution.repair import RepairError, compile_repair_plan, validate_repair_plan


PARENT = "a" * 64
EVIDENCE = ["synthetic:unit-1810-a", "synthetic:unit-1810-b"]


def evaluate(**overrides):
    """Invoke the shipping evaluator with controlled, non-production inputs."""
    params = dict(capability="legacy synthetic formatter", usage_count=1,
                  age_days=90, value_score=0.25, evidence=EVIDENCE,
                  parent_fingerprint=PARENT)
    params.update(overrides)
    return evaluate_pruning(**params)


def compile_prune(**overrides):
    """Compile an actual reversible proposal from its recomputed source data."""
    params = dict(capability="legacy synthetic formatter", usage_count=1,
                  age_days=90, value_score=0.25, evidence=EVIDENCE,
                  parent_fingerprint=PARENT)
    params.update(overrides)
    return compile_pruning_candidate(evaluate(**params), **params)


def repair(**overrides):
    params = dict(
        diagnosis="Synthetic incident: stale rule",
        actions=["Prepare synthetic correction"],
        verification=["Check synthetic regression"],
        rollback={"strategy": "revert", "steps": ["Restore prior candidate"]},
        destructive=True,
    )
    params.update(overrides)
    return compile_repair_plan(**params)


def approved_decision(scope_fingerprint):
    """Generate a structurally valid but entirely synthetic gate record."""
    gate = {
        "category": "product-direction",
        "context": "Authorize exactly one hypothetical destructive repair.",
        "options": [{
            "id": "A", "label": "Authorize synthetic scope",
            "effect": f"authorize-destructive-repair:{scope_fingerprint}",
            "pros": ["Permits a hypothetical reviewed step"],
            "cons": ["Real executor remains separate"],
            "risk": "high", "cost": "", "reversible": True,
        }, {
            "id": "B", "label": "Keep synthetic scope blocked",
            "effect": "keep-destructive-repair-blocked",
            "pros": ["Preserves all state"],
            "cons": ["No execution"],
            "risk": "low", "cost": "", "reversible": True,
        }],
        "recommendation": "B", "safe_default": "B",
        "title_simple": "Authorize a synthetic repair?",
        "summary_simple": "No real operation will execute.",
        "why_recommended": "Fail closed without owner authority.",
        "blocks": "Prevents destructive repair readiness.",
    }
    item = {"version": 1, "issue_ref": "pl0n3r/factory#1810",
            "author_association": "OWNER", "gate": gate,
            "selected_option": "A", "status": "resolved"}
    item["fingerprint"] = hashlib.sha256(json.dumps(
        item, ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return item


def trusted_decision(plan):
    ref = "owner-decision:pl0n3r/factory#1810:A"
    env = {"FACTORY_DECISION_SOURCE_ID": "synthetic:decision-source",
           "FACTORY_DECISION_SOURCE_URL": "https://example.invalid/decisions",
           "FACTORY_PROVENANCE_TOKEN": "synthetic-token-not-a-secret"}
    with patch.dict(os.environ, env), patch(
        "evolution.provenance._fetch_json",
        return_value={ref: approved_decision(plan["scope_fingerprint"])},
    ):
        return authenticated_decision_reader_from_environment(), ref


def verified_incident(incident_id):
    """Exercise every real lifecycle stage through verified, append-only history."""
    item = ImmuneIncident(incident_id, signature="Synthetic repeated failure",
                          reason="Synthetic health regression",
                          evidence=["synthetic:detect"])
    for stage in ("contain", "diagnose"):
        item.advance(stage, reason=f"Synthetic {stage}", evidence=[f"synthetic:{stage}"])
    item.advance("repair", reason="Synthetic reversible repair",
                 evidence=["synthetic:repair"], repair_plan=repair(destructive=False))
    item.advance("verify", reason="Synthetic verification passed",
                 evidence=["synthetic:verified"], verification_passed=True)
    return item.snapshot()


def trusted_incidents():
    ids = ["synthetic-incident-001", "synthetic-incident-002"]
    env = {"FACTORY_INCIDENT_SOURCE_ID": "synthetic:incident-registry",
           "FACTORY_INCIDENT_SOURCE_URL": "https://example.invalid/incidents",
           "FACTORY_PROVENANCE_TOKEN": "synthetic-token-not-a-secret"}
    with patch.dict(os.environ, env), patch(
        "evolution.provenance._fetch_json",
        return_value={id_: verified_incident(id_) for id_ in ids},
    ):
        return authenticated_incident_reader_from_environment(), ids


class CoberturaFactory19Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: actual evaluator, compiler, provenance and safe candidate behavior."""
        # growth-pruning L30/L33/L34/L35/L37: *all four* thresholds.
        accepted = evaluate()
        self.assertTrue(accepted["eligible"])
        self.assertEqual({"usage_low": True, "old_enough": True,
                          "value_low": True}, accepted["criteria"])
        for change in ({"usage_count": 2}, {"age_days": 89},
                       {"value_score": 0.251}, {"evidence": EVIDENCE[:1]},
                       {"evidence": [EVIDENCE[0], EVIDENCE[0]]}):
            with self.subTest(threshold=change):
                self.assertFalse(evaluate(**change)["eligible"])
        self.assertTrue(evaluate(age_days=91, value_score=0.24)["eligible"])

        # L43/L44/L46: lineage and fingerprints of real immutable candidate.
        compiled = compile_prune()
        self.assertIsNotNone(compiled)
        candidate = compiled["candidate"]
        value = candidate["changes"][0]["value"]
        self.assertEqual(PARENT, compiled["lineage"]["parent_fingerprint"])
        self.assertEqual(accepted["fingerprint"],
                         compiled["lineage"]["evaluation_fingerprint"])
        self.assertIs(compiled["lineage"]["history_preserved"], True)
        self.assertEqual(EVIDENCE, compiled["lineage"]["evidence"])
        self.assertEqual(validate_candidate(candidate),
                         compiled["candidate_fingerprint"])

        # L52/L60: constitutional and explicitly protected capabilities.
        for protected in (*sorted(PROTECTED_INVARIANTS), "constitution",
                          "human gates", "rollback", "audit trail"):
            with self.subTest(protected=protected):
                with self.assertRaisesRegex(PruningError, "protegida"):
                    evaluate(capability=protected, usage_count="not a number",
                             age_days=None, evidence=None)

        # L64/L65/L66/L67: real compiler adds only reversible heuristic candidate;
        # it cannot erase history, change stable authority or auto-promote.
        self.assertEqual(1, len(candidate["changes"]))
        self.assertEqual("add", candidate["changes"][0]["operation"])
        self.assertTrue(candidate["changes"][0]["path"].startswith(
            "evolution_state.heuristics.prune_"))
        self.assertEqual("prune-candidate", value["status"])
        self.assertTrue(value["lineage"]["history_preserved"])
        self.assertEqual({"reversible": True, "strategy": "restore_baseline"},
                         candidate["rollback"])
        self.assertEqual(candidate, compile_prune()["candidate"])

        # immune-repair B03: a real authenticated reader is required to prove
        # provenance; a caller-provided dict is not authority.
        blocked = repair()
        self.assertFalse(blocked["authorized_execution_ready"])
        source, ref = trusted_decision(blocked)
        ready = repair(human_authority={"approved": True, "decision_ref": ref},
                       decision_source=source)
        self.assertTrue(ready["authorized_execution_ready"])
        self.assertEqual("synthetic:decision-source", ready["authority"]["source_id"])
        self.assertEqual(ready, validate_repair_plan(ready, decision_source=source))
        self.assertIs(ready["automatic_execution_allowed"], False)
        self.assertEqual("not-performed", ready["execution"])

        # immune-repair B04: verified incidents fetched by read-only source,
        # not caller-provided snapshots, produce only a non-stable candidate.
        registry, ids = trusted_incidents()
        immune = compile_immunity_candidate(
            failure_signature="Synthetic repeated failure", incident_ids=ids,
            incident_registry=registry,
            expected_prevention="Reject synthetic repeated failures.",
        )
        self.assertEqual(len(ids), len(immune["incidents"]))
        self.assertEqual(len(ids), len(immune["origins"]))
        self.assertEqual("synthetic:incident-registry", immune["provenance"]["source_id"])
        self.assertEqual("candidate", immune["candidate"]["changes"][0]["value"]["status"])
        self.assertEqual(validate_candidate(immune["candidate"]),
                         immune["candidate_fingerprint"])

    def test_falla_cerrado(self):
        """AC-02: reject protected/ambiguous input and forged provenance."""
        for field, bad in (("usage_count", True), ("age_days", -1),
                           ("value_score", float("nan")),
                           ("value_score", "0.24"), ("evidence", []),
                           ("parent_fingerprint", "bad"), ("protected", 1)):
            with self.subTest(field=field, bad=bad):
                with self.assertRaises(PruningError):
                    evaluate(**{field: bad})
        with self.assertRaises(PruningError):
            evaluate(capability="constitutional", protected=True)
        with self.assertRaises(PruningError):
            evaluate(capability="security", usage_count=None)
        with self.assertRaises(PruningError):
            compile_pruning_candidate(
                {"eligible": True}, capability="security", usage_count=0,
                age_days=120, value_score=0, evidence=EVIDENCE,
            )
        forged = copy.deepcopy(evaluate())
        forged["metrics"]["value_score"] = 0.0
        with self.assertRaisesRegex(PruningError, "evidencia fuente"):
            compile_pruning_candidate(
                forged, capability="legacy synthetic formatter", usage_count=1,
                age_days=90, value_score=0.25, evidence=EVIDENCE,
                parent_fingerprint=PARENT,
            )
        self.assertIsNone(compile_prune(age_days=89))

        blocked = repair()
        ref = "owner-decision:pl0n3r/factory#1810:A"
        fake = {"approved": True, "decision_ref": ref}
        self.assertFalse(repair(human_authority=fake,
                                decision_evidence=approved_decision(
                                    blocked["scope_fingerprint"]))
                         ["authorized_execution_ready"])
        mutable = TrustedDecisionSource("synthetic:mutable-not-trusted")
        mutable.record_decision(ref, approved_decision(blocked["scope_fingerprint"]))
        self.assertFalse(repair(human_authority=fake,
                                decision_source=mutable)["authorized_execution_ready"])
        source, ref = trusted_decision(blocked)
        ready = repair(human_authority=fake, decision_source=source)
        with self.assertRaisesRegex(RepairError, "autoridad"):
            validate_repair_plan(ready)

        registry, ids = trusted_incidents()
        with self.assertRaises(ImmuneError):
            compile_immunity_candidate(
                failure_signature="Synthetic repeated failure",
                incident_ids=ids,
                incident_registry=TrustedIncidentRegistry("synthetic:mutable"),
                expected_prevention="Reject synthetic repeated failures.",
            )
        with self.assertRaises(ImmuneError):
            compile_immunity_candidate(
                failure_signature="Synthetic repeated failure",
                incident_ids=[ids[0], ids[0]], incident_registry=registry,
                expected_prevention="Reject synthetic repeated failures.",
            )
        with self.assertRaises(ImmuneError):
            compile_immunity_candidate(
                failure_signature="Synthetic repeated failure",
                incident_ids=ids, incident_registry=registry,
                incident_snapshots={ids[0]: verified_incident(ids[0])},
                expected_prevention="Reject synthetic repeated failures.",
            )

    def test_sin_datos_reales(self):
        """AC-03: executable checks run against fake inputs, no network I/O."""
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            result = evaluate(capability="synthetic transient module")
            self.assertTrue(result["eligible"])
            self.assertIsNotNone(compile_prune(capability="synthetic transient module"))
            source, ref = trusted_decision(repair())
            self.assertIsNotNone(source.resolve_decision(ref))
            registry, ids = trusted_incidents()
            self.assertEqual(ids, sorted(ids))
            self.assertIsNotNone(registry.resolve_incident(ids[0]))
        self.assertEqual("legacy-synthetic-formatter",
                         canonical_capability("Legacy Synthetic Formatter"))


if __name__ == "__main__":
    unittest.main()
