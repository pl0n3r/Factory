import copy
import inspect
import unittest

import intelligence.account_capacity_policy as policy_module
from intelligence.account_capacity import estimate_account_capacity
from intelligence.account_capacity_policy import (
    AccountCapacityPolicyError,
    project_account_capacity_policy,
)


def fallback():
    return {
        "max_messages": 2,
        "window_seconds": 600,
        "min_interval_seconds": 300,
    }


def observation(*, accepted, observed_at, limited=False, reset_after_seconds=None):
    return {
        "accepted": accepted,
        "limited": limited,
        "window_seconds": 600,
        "reset_after_seconds": reset_after_seconds,
        "observed_at": observed_at,
        "model": None,
        "reasoning": None,
    }


def request(observations, *, ttl_seconds=300):
    return {
        "version": 1,
        "ttl_seconds": ttl_seconds,
        "fallback_budget": fallback(),
        "observations": observations,
    }


def fresh_capacity(*, accepted=4, observed_at=950, now=1000):
    return estimate_account_capacity(
        request(
            [
                observation(
                    accepted=accepted,
                    observed_at=observed_at,
                    limited=True,
                    reset_after_seconds=900,
                )
            ],
            ttl_seconds=300,
        ),
        now=now,
    )


def resign_capacity(capacity):
    payload = {
        key: value
        for key, value in capacity.items()
        if key != "fingerprint"
    }
    capacity["fingerprint"] = policy_module._stable_hash(payload)
    return capacity


class AccountCapacityPolicyTests(unittest.TestCase):
    def test_fresh_capacity_projects_exact_versioned_budget_in_milliseconds(self):
        capacity = fresh_capacity()
        projected = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=1000,
        )

        self.assertEqual(
            set(projected),
            {
                "version",
                "accountAlias",
                "status",
                "budget",
                "observedAt",
                "expiresAt",
                "source",
                "capacityFingerprint",
                "fingerprint",
            },
        )
        self.assertEqual(projected["version"], 1)
        self.assertEqual(projected["accountAlias"], "primary")
        self.assertEqual(projected["status"], "FRESH")
        self.assertEqual(
            projected["budget"],
            {
                "limit": 4,
                "windowMs": 900000,
                "minIntervalMs": 225000,
            },
        )
        self.assertEqual(projected["observedAt"], 950000)
        self.assertEqual(projected["expiresAt"], 1250000)
        self.assertEqual(projected["capacityFingerprint"], capacity["fingerprint"])
        self.assertLessEqual(projected["budget"]["limit"], capacity["observed_safe_max"])

    def test_rejects_tampered_capacity_with_stale_fingerprint(self):
        capacity = fresh_capacity()
        tampered = copy.deepcopy(capacity)
        tampered["budget"]["max_messages"] = 3
        tampered["budget"]["min_interval_seconds"] = 300
        tampered["observed_safe_max"] = 3

        with self.assertRaisesRegex(
            AccountCapacityPolicyError,
            "fingerprint no corresponde",
        ):
            project_account_capacity_policy(
                tampered,
                account_alias="primary",
                now=1000,
            )

        projected = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=1000,
        )
        self.assertEqual(projected["capacityFingerprint"], capacity["fingerprint"])

    def test_unknown_stale_and_expired_capacity_never_publish_authoritative_budget(self):
        unknown = estimate_account_capacity(request([]), now=1000)
        projected_unknown = project_account_capacity_policy(
            unknown,
            account_alias="primary",
            now=1000,
        )
        self.assertEqual(projected_unknown["status"], "UNKNOWN")
        self.assertIsNone(projected_unknown["budget"])
        self.assertIsNone(projected_unknown["observedAt"])
        self.assertIsNone(projected_unknown["expiresAt"])

        stale = estimate_account_capacity(
            request([observation(accepted=5, observed_at=500)], ttl_seconds=100),
            now=1000,
        )
        projected_stale = project_account_capacity_policy(
            stale,
            account_alias="primary",
            now=1000,
        )
        self.assertEqual(projected_stale["status"], "STALE")
        self.assertIsNone(projected_stale["budget"])
        self.assertEqual(projected_stale["observedAt"], 500000)
        self.assertEqual(projected_stale["expiresAt"], 600000)

        capacity = fresh_capacity()
        projected_expired = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=1300,
        )
        self.assertEqual(projected_expired["status"], "STALE")
        self.assertIsNone(projected_expired["budget"])
        self.assertEqual(projected_expired["expiresAt"], 1250000)

    def test_closed_contract_rejects_identifying_alias_unknown_fields_and_incoherent_time(self):
        capacity = fresh_capacity()
        with self.assertRaisesRegex(AccountCapacityPolicyError, "alias local opaco"):
            project_account_capacity_policy(
                capacity,
                account_alias="user@example.com",
                now=1000,
            )

        unknown_field = copy.deepcopy(capacity)
        unknown_field["transcript"] = "never accepted"
        with self.assertRaisesRegex(AccountCapacityPolicyError, "esquema cerrado"):
            project_account_capacity_policy(
                unknown_field,
                account_alias="primary",
                now=1000,
            )

        wrong_version = copy.deepcopy(capacity)
        wrong_version["version"] = 2
        with self.assertRaisesRegex(AccountCapacityPolicyError, "version"):
            project_account_capacity_policy(
                wrong_version,
                account_alias="primary",
                now=1000,
            )

        future = copy.deepcopy(capacity)
        future["observed_at"] = 1001
        future["expires_at"] = 1301
        resign_capacity(future)
        with self.assertRaisesRegex(AccountCapacityPolicyError, "futuro"):
            project_account_capacity_policy(
                future,
                account_alias="primary",
                now=1000,
            )

        incoherent = copy.deepcopy(capacity)
        incoherent["expires_at"] = incoherent["observed_at"]
        resign_capacity(incoherent)
        with self.assertRaisesRegex(AccountCapacityPolicyError, "expires_at"):
            project_account_capacity_policy(
                incoherent,
                account_alias="primary",
                now=1000,
            )

    def test_projection_fingerprint_is_deterministic_and_evidence_bound(self):
        capacity = fresh_capacity()
        first = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=1000,
        )
        second = project_account_capacity_policy(
            copy.deepcopy(capacity),
            account_alias="primary",
            now=1000,
        )
        changed = project_account_capacity_policy(
            fresh_capacity(accepted=3),
            account_alias="primary",
            now=1000,
        )

        self.assertEqual(first, second)
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(first["capacityFingerprint"], changed["capacityFingerprint"])
        self.assertNotEqual(first["fingerprint"], changed["fingerprint"])

    def test_policy_projection_is_pure_secret_free_and_has_no_provider_limits(self):
        source = inspect.getsource(policy_module)
        for forbidden in (
            "requests.",
            "urllib.",
            "socket.",
            "subprocess.",
            "http://",
            "https://",
            "chat_id",
            "transcript",
            "authorization",
        ):
            self.assertNotIn(forbidden, source.lower())

        numeric_constants = {
            name: value
            for name, value in vars(policy_module).items()
            if name.isupper() and type(value) is int
        }
        self.assertEqual(
            numeric_constants,
            {"POLICY_VERSION": 1, "CAPACITY_VERSION": 1},
        )

    def test_budget_limit_must_be_javascript_safe_integer(self):
        maximum = (1 << 53) - 1
        capacity = fresh_capacity()
        capacity["budget"]["max_messages"] = maximum
        capacity["observed_safe_max"] = maximum
        resign_capacity(capacity)

        projected = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=1000,
        )
        self.assertEqual(projected["budget"]["limit"], maximum)

        unsafe = copy.deepcopy(capacity)
        unsafe["budget"]["max_messages"] = maximum + 1
        unsafe["observed_safe_max"] = maximum + 1
        resign_capacity(unsafe)
        with self.assertRaisesRegex(AccountCapacityPolicyError, "entero seguro JavaScript"):
            project_account_capacity_policy(
                unsafe,
                account_alias="primary",
                now=1000,
            )

    def test_millisecond_projection_respects_js_safe_integer_boundary(self):
        maximum_seconds = ((1 << 53) - 1) // 1000
        capacity = fresh_capacity(accepted=1)
        capacity["budget"]["window_seconds"] = maximum_seconds
        capacity["budget"]["min_interval_seconds"] = maximum_seconds
        resign_capacity(capacity)

        projected = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=1000,
        )
        self.assertEqual(projected["budget"]["windowMs"], maximum_seconds * 1000)
        self.assertEqual(
            projected["budget"]["minIntervalMs"],
            maximum_seconds * 1000,
        )

        for field in ("window_seconds", "min_interval_seconds"):
            unsafe = fresh_capacity(accepted=1)
            if field == "window_seconds":
                unsafe["budget"]["window_seconds"] = maximum_seconds + 1
                unsafe["budget"]["min_interval_seconds"] = maximum_seconds + 1
            else:
                unsafe["budget"]["window_seconds"] = 1
                unsafe["budget"]["min_interval_seconds"] = maximum_seconds + 1
            resign_capacity(unsafe)
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    AccountCapacityPolicyError,
                    "entero seguro JavaScript",
                ):
                    project_account_capacity_policy(
                        unsafe,
                        account_alias="primary",
                        now=1000,
                    )

    def test_evidence_timestamps_must_project_to_javascript_safe_milliseconds(self):
        maximum_seconds = ((1 << 53) - 1) // 1000
        capacity = fresh_capacity(accepted=1)
        capacity["observed_at"] = maximum_seconds - 1
        capacity["expires_at"] = maximum_seconds
        resign_capacity(capacity)

        projected = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=maximum_seconds,
        )
        self.assertEqual(projected["status"], "STALE")
        self.assertIsNone(projected["budget"])
        self.assertEqual(projected["observedAt"], (maximum_seconds - 1) * 1000)
        self.assertEqual(projected["expiresAt"], maximum_seconds * 1000)

        unsafe_observed = fresh_capacity(accepted=1)
        unsafe_observed["observed_at"] = maximum_seconds + 1
        unsafe_observed["expires_at"] = maximum_seconds + 2
        resign_capacity(unsafe_observed)
        with self.assertRaisesRegex(AccountCapacityPolicyError, "observed_at.*entero seguro"):
            project_account_capacity_policy(
                unsafe_observed,
                account_alias="primary",
                now=maximum_seconds + 2,
            )

        unsafe_expires = fresh_capacity(accepted=1)
        unsafe_expires["observed_at"] = maximum_seconds
        unsafe_expires["expires_at"] = maximum_seconds + 1
        resign_capacity(unsafe_expires)
        with self.assertRaisesRegex(AccountCapacityPolicyError, "expires_at.*entero seguro"):
            project_account_capacity_policy(
                unsafe_expires,
                account_alias="primary",
                now=maximum_seconds + 1,
            )

    def test_valid_fresh_unknown_and_stale_semantics_remain_compatible(self):
        fresh = project_account_capacity_policy(
            fresh_capacity(),
            account_alias="primary",
            now=1000,
        )
        repeated = project_account_capacity_policy(
            fresh_capacity(),
            account_alias="primary",
            now=1000,
        )
        unknown = project_account_capacity_policy(
            estimate_account_capacity(request([]), now=1000),
            account_alias="primary",
            now=1000,
        )
        stale = project_account_capacity_policy(
            estimate_account_capacity(
                request([observation(accepted=5, observed_at=500)], ttl_seconds=100),
                now=1000,
            ),
            account_alias="primary",
            now=1000,
        )
        expired = project_account_capacity_policy(
            fresh_capacity(),
            account_alias="primary",
            now=1300,
        )

        self.assertEqual(
            set(fresh),
            {
                "version",
                "accountAlias",
                "status",
                "budget",
                "observedAt",
                "expiresAt",
                "source",
                "capacityFingerprint",
                "fingerprint",
            },
        )
        self.assertEqual(fresh["fingerprint"], repeated["fingerprint"])
        self.assertEqual(fresh["status"], "FRESH")
        self.assertIsNotNone(fresh["budget"])
        self.assertEqual(unknown["status"], "UNKNOWN")
        self.assertIsNone(unknown["budget"])
        self.assertEqual(stale["status"], "STALE")
        self.assertIsNone(stale["budget"])
        self.assertEqual(expired["status"], "STALE")
        self.assertIsNone(expired["budget"])

    def test_zero_safe_capacity_remains_an_authoritative_pause(self):
        capacity = estimate_account_capacity(
            request(
                [
                    observation(
                        accepted=0,
                        observed_at=950,
                        limited=True,
                        reset_after_seconds=700,
                    )
                ]
            ),
            now=1000,
        )
        projected = project_account_capacity_policy(
            capacity,
            account_alias="primary",
            now=1000,
        )
        self.assertEqual(projected["status"], "FRESH")
        self.assertEqual(projected["budget"]["limit"], 0)
        self.assertEqual(projected["budget"]["minIntervalMs"], 700000)


if __name__ == "__main__":
    unittest.main()
