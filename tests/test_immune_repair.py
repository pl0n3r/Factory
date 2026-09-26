import hashlib
import json
import unittest

from evolution.constitution import validate_candidate
from evolution.immune import (
    RECOVERY_LIFECYCLE,
    ImmuneError,
    ImmuneIncident,
    compile_immunity_candidate,
)
from evolution.provenance import (
    AuthenticatedDecisionReader,
    AuthenticatedIncidentReader,
    ProvenanceError,
    TrustedDecisionSource,
    TrustedIncidentRegistry,
    _authenticated_decision_reader,
    _authenticated_incident_reader,
)
from evolution.repair import RepairError, compile_repair_plan, validate_repair_plan


def repair_plan(
    *,
    destructive=False,
    authority=None,
    decision_evidence=None,
    decision_source=None,
    actions=None,
):
    action_steps = (
        ["replace stale generated rule"] if actions is None else actions
    )
    return compile_repair_plan(
        diagnosis="Root cause isolated to a stale generated rule.",
        actions=action_steps,
        verification=["run regression suite", "compare health against baseline"],
        rollback={
            "strategy": "restore_baseline",
            "steps": ["restore previous rule snapshot"],
        },
        destructive=destructive,
        human_authority=authority,
        decision_evidence=decision_evidence,
        decision_source=decision_source,
    )


def decision_evidence(scope_fingerprint, *, issue_ref="pl0n3r/factory#900"):
    gate = {
        "category": "product-direction",
        "context": "A destructive repair requires explicit owner authorization.",
        "options": [
            {
                "id": "A",
                "label": "Authorize exact destructive repair",
                "effect": f"authorize-destructive-repair:{scope_fingerprint}",
                "pros": ["Allows the reviewed repair scope"],
                "cons": ["Destructive action remains externally executed"],
                "risk": "high",
                "cost": "",
                "reversible": True,
            },
            {
                "id": "B",
                "label": "Keep repair blocked",
                "effect": "keep-destructive-repair-blocked",
                "pros": ["Preserves current state"],
                "cons": ["Repair cannot proceed"],
                "risk": "low",
                "cost": "",
                "reversible": True,
            },
        ],
        "recommendation": "B",
        "safe_default": "B",
        "title_simple": "Authorize destructive repair?",
        "summary_simple": "The repair scope is explicit and remains non-executing.",
        "why_recommended": "Blocking is the safe default without owner approval.",
        "blocks": "Blocks destructive repair readiness.",
    }
    raw = {
        "version": 1,
        "issue_ref": issue_ref,
        "author_association": "OWNER",
        "gate": gate,
        "selected_option": "A",
        "status": "resolved",
    }
    raw["fingerprint"] = hashlib.sha256(
        json.dumps(
            raw,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return raw


def trusted_decision_source(plan):
    evidence = decision_evidence(plan["scope_fingerprint"])
    ref = "owner-decision:pl0n3r/factory#900:A"
    records = {ref: evidence}
    source = _authenticated_decision_reader(
        "controlbot:test-decisions",
        records.get,
    )
    return source, ref, evidence


def verified_incident(incident_id, *, signature="stale generated rule"):
    incident = ImmuneIncident(
        incident_id,
        signature=signature,
        reason="health regression detected",
        evidence=[f"detect:{incident_id}"],
    )
    incident.advance(
        "contain",
        reason="freeze candidate promotion",
        evidence=[f"contain:{incident_id}"],
    )
    incident.advance(
        "diagnose",
        reason="root cause identified",
        evidence=[f"diagnose:{incident_id}"],
    )
    incident.advance(
        "repair",
        reason="prepare reversible correction",
        evidence=[f"repair:{incident_id}"],
        repair_plan=repair_plan(),
    )
    incident.advance(
        "verify",
        reason="correction verified",
        evidence=[f"verify:{incident_id}"],
        verification_passed=True,
    )
    return incident


def trusted_incident_registry(*, signature="stale generated rule"):
    ids = ["incident-001", "incident-002"]
    records = {
        incident_id: verified_incident(
            incident_id,
            signature=signature,
        ).snapshot()
        for incident_id in ids
    }
    registry = _authenticated_incident_reader(
        "controlbot:test-incidents",
        records.get,
    )
    return registry, ids


def immunity_candidate():
    registry, ids = trusted_incident_registry()
    candidate = compile_immunity_candidate(
        failure_signature="stale generated rule",
        incident_ids=ids,
        incident_registry=registry,
        expected_prevention="Reject stale generated rules before promotion.",
    )
    return candidate, registry


class ImmuneRepairTests(unittest.TestCase):
    def test_incident_follows_closed_recovery_lifecycle(self):
        incident = ImmuneIncident(
            "incident-003",
            signature="stale generated rule",
            reason="health regression detected",
            evidence=["observer:run-1"],
        )
        observed = [incident.current.stage]
        with self.assertRaisesRegex(ImmuneError, "se esperaba contain"):
            incident.advance(
                "diagnose",
                reason="cannot skip containment",
                evidence=["observer:run-1"],
            )

        incident.advance(
            "contain",
            reason="freeze candidate promotion",
            evidence=["containment:1"],
        )
        observed.append(incident.current.stage)
        incident.advance(
            "diagnose",
            reason="root cause identified",
            evidence=["diagnosis:1"],
        )
        observed.append(incident.current.stage)
        incident.advance(
            "repair",
            reason="prepare reversible correction",
            evidence=["repair:1"],
            repair_plan=repair_plan(),
        )
        observed.append(incident.current.stage)
        incident.advance(
            "verify",
            reason="correction verified",
            evidence=["verify:1"],
            verification_passed=True,
        )
        observed.append(incident.current.stage)
        candidate, registry = immunity_candidate()
        incident.advance(
            "immunize",
            reason="candidate prevention compiled",
            evidence=["immunity:1"],
            immunity_candidate=candidate,
            incident_registry=registry,
        )
        observed.append(incident.current.stage)

        self.assertEqual(tuple(observed), RECOVERY_LIFECYCLE)
        snapshot = incident.snapshot()
        self.assertTrue(snapshot["visible"])
        self.assertTrue(snapshot["history_preserved"])
        self.assertEqual(len(snapshot["history"]), len(RECOVERY_LIFECYCLE))

    def test_repair_plan_requires_verification_and_rollback(self):
        plan = repair_plan()
        self.assertTrue(plan["verification"])
        self.assertTrue(plan["rollback"]["steps"])
        self.assertFalse(plan["automatic_execution_allowed"])
        self.assertEqual(plan["execution"], "not-performed")
        self.assertEqual(validate_repair_plan(plan), plan)

        with self.assertRaisesRegex(RepairError, "verification"):
            compile_repair_plan(
                diagnosis="root cause",
                actions=["safe correction"],
                verification=[],
                rollback={
                    "strategy": "revert",
                    "steps": ["undo correction"],
                },
            )
        with self.assertRaisesRegex(RepairError, "rollback"):
            compile_repair_plan(
                diagnosis="root cause",
                actions=["safe correction"],
                verification=["run tests"],
                rollback={"strategy": "revert", "steps": []},
            )

        tampered = dict(plan)
        tampered["rollback"] = "not-a-rollback"
        unsigned = dict(tampered)
        unsigned.pop("fingerprint")
        tampered["fingerprint"] = hashlib.sha256(
            json.dumps(
                unsigned,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(RepairError, "rollback"):
            validate_repair_plan(tampered)

    def test_destructive_repair_requires_human_authority(self):
        blocked = repair_plan(destructive=True)
        self.assertEqual(blocked["authority"]["required"], "human")
        self.assertFalse(blocked["authority"]["approved"])
        self.assertFalse(blocked["authorized_execution_ready"])
        self.assertFalse(blocked["automatic_execution_allowed"])

    def test_repeated_failure_can_emit_immunity_candidate(self):
        candidate, _registry = immunity_candidate()
        self.assertEqual(len(candidate["origins"]), 2)
        self.assertEqual(len(candidate["incidents"]), 2)
        self.assertEqual(
            candidate["expected_prevention"],
            "Reject stale generated rules before promotion.",
        )
        self.assertEqual(
            validate_candidate(candidate["candidate"]),
            candidate["candidate_fingerprint"],
        )
        self.assertEqual(
            candidate["candidate"]["changes"][0]["value"]["status"],
            "candidate",
        )

    def test_forged_human_authority_cannot_enable_destructive_repair(self):
        forged = repair_plan(
            destructive=True,
            authority={
                "approved": True,
                "decision_ref": "owner-decision:factory#156:A",
            },
        )
        self.assertFalse(forged["authority"]["approved"])
        self.assertFalse(forged["authorized_execution_ready"])
        self.assertIsNone(forged["authority_evidence"])
        self.assertFalse(forged["automatic_execution_allowed"])

    def test_canonical_human_decision_can_mark_destructive_plan_ready(self):
        blocked = repair_plan(destructive=True)
        source, ref, _evidence = trusted_decision_source(blocked)
        approved = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
        )
        self.assertTrue(approved["authority"]["approved"])
        self.assertTrue(approved["authorized_execution_ready"])
        self.assertFalse(approved["automatic_execution_allowed"])
        self.assertEqual(approved["execution"], "not-performed")
        self.assertEqual(
            validate_repair_plan(approved, decision_source=source),
            approved,
        )
        with self.assertRaisesRegex(RepairError, "autoridad"):
            validate_repair_plan(approved)

    def test_forged_incident_origins_cannot_emit_immunity_candidate(self):
        candidate, registry = immunity_candidate()
        forged = [dict(item) for item in candidate["origins"]]
        forged[0]["source"] = "pl0n3r/factory#fake"
        with self.assertRaisesRegex(ImmuneError, "registro confiable"):
            compile_immunity_candidate(
                failure_signature="stale generated rule",
                origins=forged,
                incident_ids=candidate["provenance"]["incident_ids"],
                incident_registry=registry,
                expected_prevention="Reject stale generated rules before promotion.",
            )

    def test_repeated_failure_is_recomputed_from_canonical_incidents(self):
        registry, ids = trusted_incident_registry()
        candidate = compile_immunity_candidate(
            failure_signature="stale generated rule",
            incident_ids=ids,
            incident_registry=registry,
            expected_prevention="Reject stale generated rules before promotion.",
        )
        self.assertEqual(
            [item["incident_id"] for item in candidate["incidents"]],
            ids,
        )
        self.assertTrue(
            all(
                item["history"][RECOVERY_LIFECYCLE.index("verify")][
                    "verification_passed"
                ]
                is True
                for item in candidate["incidents"]
            )
        )

        wrong_registry, wrong_ids = trusted_incident_registry(
            signature="other failure"
        )
        with self.assertRaisesRegex(ImmuneError, "failure_signature"):
            compile_immunity_candidate(
                failure_signature="stale generated rule",
                incident_ids=wrong_ids,
                incident_registry=wrong_registry,
                expected_prevention="Reject stale generated rules before promotion.",
            )

    def test_hardening_preserves_non_execution_and_history(self):
        blocked = repair_plan(destructive=True)
        source, ref, _evidence = trusted_decision_source(blocked)
        approved = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
        )
        self.assertFalse(approved["automatic_execution_allowed"])
        self.assertEqual(approved["execution"], "not-performed")
        self.assertEqual(
            validate_repair_plan(approved, decision_source=source),
            approved,
        )

        candidate, _registry = immunity_candidate()
        self.assertEqual(
            validate_candidate(candidate["candidate"]),
            candidate["candidate_fingerprint"],
        )
        self.assertTrue(
            all(item["history_preserved"] for item in candidate["incidents"])
        )
        self.assertTrue(all(item["visible"] for item in candidate["incidents"]))
        self.assertTrue(candidate["candidate"]["rollback"]["reversible"])

    def test_caller_constructed_decision_store_is_not_trusted(self):
        """AC-01: una store mutable local no puede autorizar reparación."""
        blocked = repair_plan(destructive=True)
        evidence = decision_evidence(blocked["scope_fingerprint"])
        ref = "owner-decision:pl0n3r/factory#900:A"
        store = TrustedDecisionSource("caller:forged")
        store.record_decision(ref, evidence)
        plan = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=store,
        )
        self.assertFalse(plan["authority"]["approved"])
        self.assertFalse(plan["authorized_execution_ready"])

    def test_caller_constructed_incident_registry_is_not_trusted(self):
        """AC-02: snapshots perfectos en registry local no producen Immunity."""
        store = TrustedIncidentRegistry("caller:forged")
        ids = ["incident-001", "incident-002"]
        for incident_id in ids:
            store.record_incident(
                incident_id,
                verified_incident(incident_id).snapshot(),
            )
        with self.assertRaisesRegex(ImmuneError, "autenticado"):
            compile_immunity_candidate(
                failure_signature="stale generated rule",
                incident_ids=ids,
                incident_registry=store,
                expected_prevention="Reject stale generated rules before promotion.",
            )

    def test_production_provenance_capability_is_read_only(self):
        """AC-03: readers productivos no exponen mutación."""
        source, _ref, _evidence = trusted_decision_source(
            repair_plan(destructive=True)
        )
        registry, _ids = trusted_incident_registry()
        self.assertIsInstance(source, AuthenticatedDecisionReader)
        self.assertIsInstance(registry, AuthenticatedIncidentReader)
        self.assertFalse(hasattr(source, "record_decision"))
        self.assertFalse(hasattr(registry, "record_incident"))
        with self.assertRaises(ProvenanceError):
            AuthenticatedDecisionReader(
                "caller:forged",
                lambda _key: None,
                _seal=object(),
            )

    def test_authenticated_decision_adapter_authorizes_exact_scope(self):
        """AC-04: reader sellado autoriza únicamente el scope exacto."""
        blocked = repair_plan(destructive=True)
        source, ref, _evidence = trusted_decision_source(blocked)
        approved = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
        )
        self.assertTrue(approved["authorized_execution_ready"])
        other = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
            actions=["different destructive action"],
        )
        self.assertFalse(other["authorized_execution_ready"])

    def test_authenticated_incident_adapter_proves_repetition_without_execution(self):
        """AC-05: registry autenticado prueba repetición sin ejecutar nada."""
        registry, ids = trusted_incident_registry()
        candidate = compile_immunity_candidate(
            failure_signature="stale generated rule",
            incident_ids=ids,
            incident_registry=registry,
            expected_prevention="Reject stale generated rules before promotion.",
        )
        self.assertEqual(candidate["provenance"]["incident_ids"], ids)
        self.assertTrue(candidate["candidate"]["rollback"]["reversible"])
        self.assertTrue(
            all(item["history_preserved"] for item in candidate["incidents"])
        )
        blocked = repair_plan(destructive=True)
        source, ref, _evidence = trusted_decision_source(blocked)
        approved = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
        )
        self.assertFalse(approved["automatic_execution_allowed"])
        self.assertEqual(approved["execution"], "not-performed")

    def test_self_signed_decision_evidence_is_not_authority(self):
        """AC-01: un dict autocertificado nunca reemplaza una fuente confiable."""
        blocked = repair_plan(destructive=True)
        evidence = decision_evidence(blocked["scope_fingerprint"])
        plan = repair_plan(
            destructive=True,
            authority={
                "approved": True,
                "decision_ref": "owner-decision:pl0n3r/factory#900:A",
            },
            decision_evidence=evidence,
        )
        self.assertFalse(plan["authority"]["approved"])
        self.assertFalse(plan["authorized_execution_ready"])
        self.assertIsNone(plan["authority_evidence"])

    def test_trusted_decision_source_can_authorize_exact_scope(self):
        """AC-02: el handle se resuelve en una fuente durable y fija el scope."""
        blocked = repair_plan(destructive=True)
        source, ref, _evidence = trusted_decision_source(blocked)
        plan = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
        )
        self.assertTrue(plan["authorized_execution_ready"])
        self.assertEqual(plan["authority"]["source_id"], source.source_id)
        self.assertEqual(
            validate_repair_plan(plan, decision_source=source),
            plan,
        )

        other = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
            actions=["different destructive action"],
        )
        self.assertFalse(other["authorized_execution_ready"])

    def test_self_signed_incident_snapshots_are_not_provenance(self):
        """AC-03: hashes correctos en snapshots del caller no prueban procedencia."""
        snapshots = [
            verified_incident("incident-001").snapshot(),
            verified_incident("incident-002").snapshot(),
        ]
        origins = [
            {
                "incident_id": item["incident_id"],
                "source": f"incident-snapshot:{item['fingerprint']}",
            }
            for item in snapshots
        ]
        with self.assertRaisesRegex(ImmuneError, "autocertificados"):
            compile_immunity_candidate(
                failure_signature="stale generated rule",
                origins=origins,
                incident_snapshots=snapshots,
                expected_prevention="Reject stale generated rules before promotion.",
            )

    def test_trusted_incident_registry_proves_repeated_failure(self):
        """AC-04: el candidato se deriva de handles resueltos en registro append-only."""
        registry, ids = trusted_incident_registry()
        candidate = compile_immunity_candidate(
            failure_signature="stale generated rule",
            incident_ids=ids,
            incident_registry=registry,
            expected_prevention="Reject stale generated rules before promotion.",
        )
        self.assertEqual(candidate["provenance"]["source_id"], registry.source_id)
        self.assertEqual(candidate["provenance"]["incident_ids"], ids)
        self.assertEqual(
            candidate["candidate"]["changes"][0]["value"]["occurrences"],
            2,
        )

    def test_trusted_provenance_preserves_non_execution_and_history(self):
        """AC-05: provenance fuerte no amplía ejecución y conserva rollback/historia."""
        blocked = repair_plan(destructive=True)
        source, ref, _evidence = trusted_decision_source(blocked)
        approved = repair_plan(
            destructive=True,
            authority={"approved": True, "decision_ref": ref},
            decision_source=source,
        )
        self.assertFalse(approved["automatic_execution_allowed"])
        self.assertEqual(approved["execution"], "not-performed")

        candidate, registry = immunity_candidate()
        self.assertEqual(
            validate_candidate(candidate["candidate"]),
            candidate["candidate_fingerprint"],
        )
        self.assertTrue(candidate["candidate"]["rollback"]["reversible"])
        self.assertTrue(
            all(item["history_preserved"] for item in candidate["incidents"])
        )

        incident = verified_incident("incident-final")
        incident.advance(
            "immunize",
            reason="trusted repeated failure compiled",
            evidence=["immunity:trusted-registry"],
            immunity_candidate=candidate,
            incident_registry=registry,
        )
        snapshot = incident.snapshot()
        self.assertTrue(snapshot["visible"])
        self.assertTrue(snapshot["history_preserved"])
        self.assertEqual(snapshot["stage"], "immunize")


if __name__ == "__main__":
    unittest.main()
