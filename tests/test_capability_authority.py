import hashlib
import json
import os
import unittest
from unittest.mock import patch

from evolution.capability_authority import (
    CapabilityAuthorityError,
    CapabilityAuthorityRegistry,
)
from evolution.provenance import (
    TrustedDecisionSource,
    authenticated_decision_reader_from_environment,
)


def stable_hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def decision(
    *,
    operation="grant",
    capability="deploy-observer",
    actions=("observe", "propose"),
    scopes=("project:brvtal",),
    targets=("production",),
    authority_class="operational",
    actor_ref="decision:owner#1",
    reason="explicit reviewed authority",
    grant_id="",
):
    raw = {
        "version": 1,
        "operation": operation,
        "capability": capability,
        "actions": list(actions),
        "scopes": list(scopes),
        "targets": list(targets),
        "authority_class": authority_class,
        "actor_ref": actor_ref,
        "reason": reason,
        "status": "resolved",
        "grant_id": grant_id,
    }
    raw["fingerprint"] = stable_hash(raw)
    return raw


def authenticated_source(records):
    env = {
        "FACTORY_DECISION_SOURCE_ID": "controlbot:test-decisions",
        "FACTORY_DECISION_SOURCE_URL": "https://controlbot.example/decisions",
        "FACTORY_PROVENANCE_TOKEN": "test-token",
    }
    with patch.dict(os.environ, env, clear=False), patch(
        "evolution.provenance._fetch_json", return_value=records
    ):
        return authenticated_decision_reader_from_environment()


def grant_decision(**kwargs):
    raw = decision(**kwargs)
    normalized = {
        "capability": raw["capability"],
        "actions": tuple(sorted(raw["actions"])),
        "scopes": tuple(sorted(raw["scopes"])),
        "targets": tuple(sorted(raw["targets"])),
        "authority_class": raw["authority_class"],
        "human_gate": raw["authority_class"] != "operational",
        "reason": raw["reason"],
    }
    ref = "owner-decision:factory#246:grant"
    raw["grant_id"] = stable_hash(
        {
            **normalized,
            "decision_ref": ref,
            "source_id": "controlbot:test-decisions",
            "actor_ref": raw["actor_ref"],
        }
    )
    unsigned = dict(raw)
    unsigned.pop("fingerprint")
    raw["fingerprint"] = stable_hash(unsigned)
    return ref, raw


class CapabilityAuthorityTests(unittest.TestCase):
    def test_capability_matrix_declares_actions_and_scope(self):
        ref, raw = grant_decision(actions=("observe", "execute"))
        registry = CapabilityAuthorityRegistry()
        registry.grant(ref, decision_source=authenticated_source({ref: raw}))

        matrix = registry.matrix("deploy-observer")
        self.assertEqual(
            set(matrix["actions"]),
            {"observe", "propose", "experiment", "execute", "promote_adopt"},
        )
        self.assertTrue(matrix["actions"]["observe"]["allowed"])
        self.assertTrue(matrix["actions"]["execute"]["allowed"])
        self.assertEqual(
            matrix["actions"]["execute"]["scopes"], ["project:brvtal"]
        )
        self.assertEqual(
            matrix["actions"]["execute"]["targets"], ["production"]
        )
        self.assertFalse(matrix["actions"]["experiment"]["allowed"])
        self.assertTrue(
            registry.authorize(
                "deploy-observer", "execute", "project:brvtal", "production"
            )
        )
        self.assertFalse(
            registry.authorize(
                "deploy-observer", "execute", "project:condor", "production"
            )
        )

    def test_performance_cannot_create_new_authority(self):
        ref, raw = grant_decision(actions=("observe", "propose"))
        registry = CapabilityAuthorityRegistry()
        registry.grant(ref, decision_source=authenticated_source({ref: raw}))
        baseline = registry.autonomy_scope("deploy-observer", "observe")
        promoted = registry.autonomy_scope("deploy-observer", "autonomous")

        self.assertEqual(baseline["fingerprint"], promoted["fingerprint"])
        self.assertFalse(
            promoted["authority"]["actions"]["execute"]["allowed"]
        )
        self.assertFalse(
            registry.authorize(
                "deploy-observer", "execute", "project:brvtal", "production"
            )
        )

    def test_autonomy_changes_only_within_existing_scope(self):
        ref, raw = grant_decision(
            actions=("observe", "propose", "execute")
        )
        registry = CapabilityAuthorityRegistry()
        registry.grant(ref, decision_source=authenticated_source({ref: raw}))

        for level in (
            "observe", "propose", "shadow", "supervised", "autonomous"
        ):
            snapshot = registry.autonomy_scope("deploy-observer", level)
            self.assertEqual(
                snapshot["authority"]["actions"]["execute"]["scopes"],
                ["project:brvtal"],
            )
            self.assertEqual(
                snapshot["authority"]["actions"]["execute"]["targets"],
                ["production"],
            )
            self.assertFalse(
                registry.authorize(
                    "deploy-observer",
                    "execute",
                    "project:condor",
                    "production",
                )
            )
        with self.assertRaises(CapabilityAuthorityError):
            registry.autonomy_scope("deploy-observer", "superuser")

    def test_reserved_authorities_remain_human_gated(self):
        for authority_class in (
            "money",
            "legal",
            "personal_data",
            "irreversible_delete",
            "authority_expansion",
        ):
            with self.subTest(authority_class=authority_class):
                ref, raw = grant_decision(
                    authority_class=authority_class,
                    actions=("observe", "propose"),
                )
                registry = CapabilityAuthorityRegistry()
                registry.grant(
                    ref, decision_source=authenticated_source({ref: raw})
                )
                matrix = registry.matrix("deploy-observer")
                self.assertTrue(
                    matrix["actions"]["observe"]["human_gate"]
                )
                self.assertFalse(
                    registry.authorize(
                        "deploy-observer",
                        "observe",
                        "project:brvtal",
                        "production",
                    )
                )

                ref2, unsafe = grant_decision(
                    authority_class=authority_class,
                    actions=("execute",),
                )
                with self.assertRaisesRegex(
                    CapabilityAuthorityError, "human-gated"
                ):
                    CapabilityAuthorityRegistry().grant(
                        ref2,
                        decision_source=authenticated_source({ref2: unsafe}),
                    )

    def test_grants_and_revocations_require_trusted_provenance(self):
        ref, raw = grant_decision()
        fixture = TrustedDecisionSource("caller-built")
        fixture.record_decision(ref, raw)
        registry = CapabilityAuthorityRegistry()
        with self.assertRaisesRegex(
            CapabilityAuthorityError, "autenticada"
        ):
            registry.grant(ref, decision_source=fixture)

        source = authenticated_source({ref: raw})
        grant = registry.grant(ref, decision_source=source)
        revoke_ref = "owner-decision:factory#246:revoke"
        revoke = decision(
            operation="revoke",
            actions=grant.actions,
            scopes=grant.scopes,
            targets=grant.targets,
            authority_class=grant.authority_class,
            reason="authority explicitly revoked",
            grant_id=grant.grant_id,
        )
        revoke_source = authenticated_source({revoke_ref: revoke})
        revoked = registry.revoke(
            grant.grant_id,
            revoke_ref,
            decision_source=revoke_source,
        )

        self.assertFalse(revoked.active)
        self.assertFalse(
            registry.authorize(
                "deploy-observer", "observe", "project:brvtal", "production"
            )
        )
        self.assertEqual(
            [event.event for event in registry.history],
            ["grant", "revoke"],
        )
        self.assertEqual(
            registry.history[0].source_id,
            "controlbot:test-decisions",
        )
        self.assertEqual(
            registry.history[1].actor_ref,
            "decision:owner#1",
        )

    def test_contract_is_deterministic_and_rejects_extra_fields(self):
        ref, raw = grant_decision()
        registry = CapabilityAuthorityRegistry()
        registry.grant(ref, decision_source=authenticated_source({ref: raw}))
        first = registry.matrix("deploy-observer")
        second = registry.matrix("deploy-observer")
        self.assertEqual(first, second)

        extra = dict(raw)
        extra["performance_score"] = 1.0
        with self.assertRaisesRegex(CapabilityAuthorityError, "campos"):
            CapabilityAuthorityRegistry().grant(
                ref,
                decision_source=authenticated_source({ref: extra}),
            )

        forged = dict(raw)
        forged["actions"] = ["observe", "execute"]
        with self.assertRaisesRegex(
            CapabilityAuthorityError, "fingerprint"
        ):
            CapabilityAuthorityRegistry().grant(
                ref,
                decision_source=authenticated_source({ref: forged}),
            )


if __name__ == "__main__":
    unittest.main()
