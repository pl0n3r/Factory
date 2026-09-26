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
from evolution.repair import RepairError, compile_repair_plan, validate_repair_plan


def repair_plan(*, destructive=False, authority=None, decision_evidence=None):
    return compile_repair_plan(
        diagnosis="Root cause isolated to a stale generated rule.",
        actions=["replace stale generated rule"],
        verification=["run regression suite", "compare health against baseline"],
        rollback={
            "strategy": "restore_baseline",
            "steps": ["restore previous rule snapshot"],
        },
        destructive=destructive,
        human_authority=authority,
        decision_evidence=decision_evidence,
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


def canonical_incident_inputs():
    snapshots = [
        verified_incident("incident-001").snapshot(),
        verified_incident("incident-002").snapshot(),
    ]
    origins = sorted(
        [
            {
                "incident_id": item["incident_id"],
                "source": f"incident-snapshot:{item['fingerprint']}",
            }
            for item in snapshots
        ],
        key=lambda item: (item["source"], item["incident_id"]),
    )
    return snapshots, origins


def immunity_candidate():
    snapshots, origins = canonical_incident_inputs()
    return compile_immunity_candidate(
        failure_signature="stale generated rule",
        origins=origins,
        incident_snapshots=snapshots,
        expected_prevention="Reject stale generated rules before promotion.",
    )


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
        incident.advance(
            "immunize",
            reason="candidate prevention compiled",
            evidence=["immunity:1"],
            immunity_candidate=immunity_candidate(),
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
        candidate = immunity_candidate()
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
        evidence = decision_evidence(blocked["scope_fingerprint"])
        approved = repair_plan(
            destructive=True,
            authority={
                "approved": True,
                "decision_ref": "owner-decision:pl0n3r/factory#900:A",
            },
            decision_evidence=evidence,
        )
        self.assertTrue(approved["authority"]["approved"])
        self.assertTrue(approved["authorized_execution_ready"])
        self.assertFalse(approved["automatic_execution_allowed"])
        self.assertEqual(approved["execution"], "not-performed")
        self.assertEqual(validate_repair_plan(approved), approved)

    def test_forged_incident_origins_cannot_emit_immunity_candidate(self):
        snapshots, origins = canonical_incident_inputs()
        forged = [dict(item) for item in origins]
        forged[0]["source"] = "pl0n3r/factory#fake"
        with self.assertRaisesRegex(ImmuneError, "incidentes canónicos"):
            compile_immunity_candidate(
                failure_signature="stale generated rule",
                origins=forged,
                incident_snapshots=snapshots,
                expected_prevention="Reject stale generated rules before promotion.",
            )

    def test_repeated_failure_is_recomputed_from_canonical_incidents(self):
        snapshots, origins = canonical_incident_inputs()
        candidate = compile_immunity_candidate(
            failure_signature="stale generated rule",
            origins=origins,
            incident_snapshots=snapshots,
            expected_prevention="Reject stale generated rules before promotion.",
        )
        self.assertEqual(candidate["origins"], origins)
        self.assertEqual(
            [item["incident_id"] for item in candidate["incidents"]],
            ["incident-001", "incident-002"],
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

        wrong_signature = [
            verified_incident("incident-004", signature="other failure").snapshot(),
            verified_incident("incident-005", signature="other failure").snapshot(),
        ]
        with self.assertRaisesRegex(ImmuneError, "failure_signature"):
            compile_immunity_candidate(
                failure_signature="stale generated rule",
                origins=[
                    {
                        "incident_id": item["incident_id"],
                        "source": f"incident-snapshot:{item['fingerprint']}",
                    }
                    for item in wrong_signature
                ],
                incident_snapshots=wrong_signature,
                expected_prevention="Reject stale generated rules before promotion.",
            )

    def test_hardening_preserves_non_execution_and_history(self):
        blocked = repair_plan(destructive=True)
        evidence = decision_evidence(blocked["scope_fingerprint"])
        approved = repair_plan(
            destructive=True,
            authority={
                "approved": True,
                "decision_ref": "owner-decision:pl0n3r/factory#900:A",
            },
            decision_evidence=evidence,
        )
        self.assertFalse(approved["automatic_execution_allowed"])
        self.assertEqual(approved["execution"], "not-performed")
        self.assertEqual(validate_repair_plan(approved), approved)

        candidate = immunity_candidate()
        self.assertEqual(
            validate_candidate(candidate["candidate"]),
            candidate["candidate_fingerprint"],
        )
        self.assertTrue(
            all(item["history_preserved"] for item in candidate["incidents"])
        )
        self.assertTrue(all(item["visible"] for item in candidate["incidents"]))
        self.assertTrue(candidate["candidate"]["rollback"]["reversible"])


if __name__ == "__main__":
    unittest.main()
