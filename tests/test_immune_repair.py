import unittest

from evolution.constitution import validate_candidate
from evolution.immune import (
    RECOVERY_LIFECYCLE,
    ImmuneError,
    ImmuneIncident,
    compile_immunity_candidate,
)
from evolution.repair import RepairError, compile_repair_plan, validate_repair_plan


def repair_plan(*, destructive=False, authority=None):
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
    )


def immunity_candidate():
    return compile_immunity_candidate(
        failure_signature="stale generated rule",
        origins=[
            {
                "incident_id": "incident-001",
                "source": "pl0n3r/factory#130",
            },
            {
                "incident_id": "incident-002",
                "source": "pl0n3r/factory#131",
            },
        ],
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
        import hashlib
        import json
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

        approved = repair_plan(
            destructive=True,
            authority={
                "approved": True,
                "decision_ref": "owner-decision:factory#156:A",
            },
        )
        self.assertTrue(approved["authority"]["approved"])
        self.assertTrue(approved["authorized_execution_ready"])
        self.assertFalse(approved["automatic_execution_allowed"])
        self.assertEqual(approved["execution"], "not-performed")

    def test_repeated_failure_can_emit_immunity_candidate(self):
        candidate = immunity_candidate()
        self.assertEqual(len(candidate["origins"]), 2)
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


if __name__ == "__main__":
    unittest.main()
