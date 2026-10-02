import copy
import unittest

from quality.dispatch_audit import DispatchAuditError, dispatch_audit_snapshot
from scripts.dispatcher_v2 import (
    CANONICAL_DISPATCH_REPOS,
    dispatch_signature,
    no_work_proof,
)


def watchdog_evidence(*, repository_ref="pl0n3r/Factory", reasons=None):
    fingerprint = "b" * 64
    return {
        "version": 1,
        "repository_ref": repository_ref,
        "state": "UNKNOWN",
        "severity": "UNKNOWN",
        "reasons": ["proven_idle"] if reasons is None else reasons,
        "provenance": [
            "run:unattended-watchdog:37031848944",
            fingerprint,
        ],
        "evidence_fingerprint": fingerprint,
        "freshness": {
            "state": "CURRENT",
            "age_seconds": 120,
            "max_age_seconds": 900,
        },
        "source": "unattended_watchdog_v1",
        "authority": "unchanged",
        "execute_actions": False,
    }


def no_work_evidence():
    inventory = {repo: () for repo in CANONICAL_DISPATCH_REPOS}
    return no_work_proof(
        initial_inventory=inventory,
        reasons={repo: "no_dispatchable_work" for repo in CANONICAL_DISPATCH_REPOS},
        final_inventory=copy.deepcopy(inventory),
    )


class QualityDispatchAuditTests(unittest.TestCase):
    def test_snapshot_binds_stable_agent_watchdog_and_no_work_provenance(self):
        signature = dispatch_signature(
            agent_id="dispatcher-a1",
            repository_ref="pl0n3r/Factory",
        )
        watchdog = watchdog_evidence()
        no_work = no_work_evidence()

        snapshot = dispatch_audit_snapshot(
            dispatch_signature=signature,
            watchdog_evidence=watchdog,
            no_work_evidence=no_work,
        )

        self.assertEqual(snapshot["version"], 1)
        self.assertEqual(snapshot["agent_id"], "dispatcher-a1")
        self.assertEqual(snapshot["signature"], "Despacho (dispatcher-a1)")
        self.assertEqual(snapshot["repository_ref"], "pl0n3r/Factory")
        self.assertEqual(
            snapshot["watchdog"]["evidence_fingerprint"],
            watchdog["evidence_fingerprint"],
        )
        self.assertEqual(
            snapshot["provenance"]["watchdog"],
            watchdog["provenance"],
        )
        self.assertEqual(
            snapshot["provenance"]["no_work"]["initial_fingerprint"],
            no_work["initial_fingerprint"],
        )
        self.assertEqual(
            snapshot["provenance"]["no_work"]["final_fingerprint"],
            no_work["final_fingerprint"],
        )
        self.assertEqual(snapshot["freshness"]["watchdog"], watchdog["freshness"])
        self.assertTrue(snapshot["freshness"]["no_work_recheck_stable"])
        self.assertEqual(snapshot["authority"], "unchanged")
        self.assertFalse(snapshot["execute_actions"])
        self.assertFalse(snapshot["recalculated"])

    def test_snapshot_is_read_only_and_fails_closed_on_mismatched_or_stale_evidence(self):
        signature = dispatch_signature(
            agent_id="dispatcher-a1",
            repository_ref="pl0n3r/Factory",
        )
        watchdog = watchdog_evidence()
        no_work = no_work_evidence()
        original_signature = copy.deepcopy(signature)
        original_watchdog = copy.deepcopy(watchdog)
        original_no_work = copy.deepcopy(no_work)

        dispatch_audit_snapshot(
            dispatch_signature=signature,
            watchdog_evidence=watchdog,
            no_work_evidence=no_work,
        )
        self.assertEqual(signature, original_signature)
        self.assertEqual(watchdog, original_watchdog)
        self.assertEqual(no_work, original_no_work)

        stale = copy.deepcopy(watchdog)
        stale["freshness"] = {
            "state": "STALE",
            "age_seconds": 901,
            "max_age_seconds": 900,
        }

        mismatch = copy.deepcopy(watchdog)
        mismatch["repository_ref"] = "pl0n3r/Condor"

        ambiguous = copy.deepcopy(watchdog)
        ambiguous["provenance"] = [
            watchdog["evidence_fingerprint"],
            watchdog["evidence_fingerprint"],
        ]

        incomplete = copy.deepcopy(no_work)
        incomplete["reasons"].pop("pl0n3r/AutoFactory")

        changed = copy.deepcopy(no_work)
        changed["final_fingerprint"] = "c" * 64

        active_unknown = copy.deepcopy(watchdog)
        active_unknown["reasons"] = ["capacity:unknown"]

        invalid_cases = (
            (signature, stale, no_work),
            (signature, mismatch, no_work),
            (signature, ambiguous, no_work),
            (signature, watchdog, incomplete),
            (signature, watchdog, changed),
            (signature, active_unknown, no_work),
        )
        for dispatch_value, watchdog_value, no_work_value in invalid_cases:
            with self.subTest(
                watchdog=watchdog_value.get("reasons"),
                no_work_valid=no_work_value.get("valid"),
            ):
                with self.assertRaises(DispatchAuditError):
                    dispatch_audit_snapshot(
                        dispatch_signature=dispatch_value,
                        watchdog_evidence=watchdog_value,
                        no_work_evidence=no_work_value,
                    )

        sensitive = copy.deepcopy(watchdog)
        sensitive["reasons"] = ["token=supersecretvalue"]
        with self.assertRaises(DispatchAuditError) as caught:
            dispatch_audit_snapshot(
                dispatch_signature=signature,
                watchdog_evidence=sensitive,
                no_work_evidence=no_work,
            )
        self.assertNotIn("supersecretvalue", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
