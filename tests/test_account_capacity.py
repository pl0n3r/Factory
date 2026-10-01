import copy
import unittest

from intelligence.account_capacity import (
    AccountCapacityError,
    estimate_account_capacity,
)


def fallback():
    return {
        "max_messages": 2,
        "window_seconds": 600,
        "min_interval_seconds": 300,
    }


def observation(
    *,
    accepted,
    observed_at,
    limited=False,
    window_seconds=600,
    reset_after_seconds=None,
    model=None,
    reasoning=None,
):
    return {
        "accepted": accepted,
        "limited": limited,
        "window_seconds": window_seconds,
        "reset_after_seconds": reset_after_seconds,
        "observed_at": observed_at,
        "model": model,
        "reasoning": reasoning,
    }


def request(observations, *, ttl_seconds=300):
    return {
        "version": 1,
        "ttl_seconds": ttl_seconds,
        "fallback_budget": fallback(),
        "observations": observations,
    }


class AccountCapacityTests(unittest.TestCase):
    def test_unknown_and_stale_use_exact_conservative_fallback(self):
        unknown = estimate_account_capacity(request([]), now=1000)
        self.assertEqual(unknown["status"], "UNKNOWN")
        self.assertEqual(unknown["confidence"], "none")
        self.assertEqual(unknown["budget"], fallback())
        self.assertIsNone(unknown["observed_safe_max"])

        stale = estimate_account_capacity(
            request([observation(accepted=7, observed_at=500)], ttl_seconds=100),
            now=1000,
        )
        self.assertEqual(stale["status"], "STALE")
        self.assertEqual(stale["budget"], fallback())
        self.assertEqual(stale["observed_at"], 500)
        self.assertEqual(stale["expires_at"], 600)
    def test_fresh_budget_never_exceeds_observed_safe_capacity(self):
        result = estimate_account_capacity(
            request(
                [
                    observation(accepted=10, observed_at=900),
                    observation(
                        accepted=6,
                        limited=True,
                        reset_after_seconds=900,
                        observed_at=920,
                    ),
                    observation(
                        accepted=4,
                        limited=True,
                        reset_after_seconds=1200,
                        observed_at=940,
                    ),
                ]
            ),
            now=1000,
        )

        self.assertEqual(result["status"], "FRESH")
        self.assertEqual(result["source"], "observed-limit")
        self.assertEqual(result["observed_safe_max"], 4)
        self.assertEqual(result["budget"]["max_messages"], 4)
        self.assertEqual(result["budget"]["window_seconds"], 1200)
        self.assertEqual(result["budget"]["min_interval_seconds"], 300)
        self.assertLessEqual(
            result["budget"]["max_messages"],
            min(6, 4),
        )
    def test_closed_versioned_schema_rejects_chat_content_and_unknown_fields(self):
        bad_request = request([])
        bad_request["transcript"] = "contenido que nunca debe entrar"
        with self.assertRaisesRegex(AccountCapacityError, "esquema cerrado"):
            estimate_account_capacity(bad_request, now=1000)

        bad_observation = observation(accepted=2, observed_at=900)
        bad_observation["chat_id"] = "conversation-123"
        with self.assertRaisesRegex(AccountCapacityError, "esquema cerrado"):
            estimate_account_capacity(request([bad_observation]), now=1000)

        wrong_version = request([])
        wrong_version["version"] = 2
        with self.assertRaisesRegex(AccountCapacityError, "version"):
            estimate_account_capacity(wrong_version, now=1000)

        valid = request(
            [observation(accepted=3, observed_at=900, model="gpt", reasoning="high")]
        )
        first = estimate_account_capacity(valid, now=1000)
        second = estimate_account_capacity(copy.deepcopy(valid), now=1000)
        self.assertEqual(first, second)
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")
    def test_changing_limit_uses_recent_conservative_evidence_deterministically(self):
        observations = [
            observation(
                accepted=8,
                limited=True,
                reset_after_seconds=600,
                observed_at=800,
            ),
            observation(
                accepted=4,
                limited=True,
                reset_after_seconds=900,
                observed_at=950,
            ),
            observation(accepted=5, observed_at=970),
        ]
        first = estimate_account_capacity(
            request(observations, ttl_seconds=300),
            now=1000,
        )
        second = estimate_account_capacity(
            request(list(reversed(observations)), ttl_seconds=300),
            now=1000,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["budget"]["max_messages"], 4)
        self.assertEqual(first["budget"]["window_seconds"], 900)
        self.assertEqual(first["confidence"], "low")
        self.assertEqual(first["limited_count"], 2)
    def test_success_only_evidence_never_extrapolates_above_observed_count(self):
        result = estimate_account_capacity(
            request(
                [
                    observation(accepted=3, observed_at=900),
                    observation(accepted=5, observed_at=950),
                ]
            ),
            now=1000,
        )
        self.assertEqual(result["source"], "observed-success")
        self.assertEqual(result["budget"]["max_messages"], 5)
        self.assertEqual(result["confidence"], "medium")

    def test_invalid_policy_or_future_observation_fails_closed(self):
        invalid = request([])
        invalid["fallback_budget"]["min_interval_seconds"] = 1
        with self.assertRaises(AccountCapacityError):
            estimate_account_capacity(invalid, now=1000)

        future = request([observation(accepted=1, observed_at=1001)])
        with self.assertRaisesRegex(AccountCapacityError, "futuro"):
            estimate_account_capacity(future, now=1000)

    def test_zero_safe_capacity_can_pause_without_division_by_zero(self):
        result = estimate_account_capacity(
            request(
                [
                    observation(
                        accepted=0,
                        limited=True,
                        reset_after_seconds=700,
                        observed_at=950,
                    )
                ]
            ),
            now=1000,
        )
        self.assertEqual(result["budget"]["max_messages"], 0)
        self.assertEqual(result["budget"]["min_interval_seconds"], 700)


if __name__ == "__main__":
    unittest.main()
