"""Contrato offline de conteos diarios de producto (#1157)."""
import unittest

from metricas.evaluar_agentes import summarize_product_day

AS_OF = "2026-10-11T10:00:00Z"


def pr(number, merged_at, sha="a" * 40):
    return {"number": number, "merged": True, "merged_at": merged_at,
            "merge_commit_sha": sha}


def snapshot(repo, events=None):
    return {
        "repo": repo,
        "repository_sha": "d" * 40,
        "observed_at": "2026-10-11T09:30:00Z",
        "source": "github-api", "authenticated": True, "complete": True,
        "run_id": 100, "run_status": "completed", "run_conclusion": "success",
        "pages": 2, "verified_pages": 2,
        "events": [] if events is None else events,
    }


class ProductoDiarioTests(unittest.TestCase):
    def test_daily_metric_counts_from_real_observation_fixtures(self):
        # Fixtures que representan observaciones externas autenticadas, sin usar API.
        repo = "pl0n3r/Factory"
        first = snapshot(repo, [
            pr(12, "2026-10-11T09:00:00Z"),
            pr(12, "2026-10-11T04:00:00-05:00"),
            pr(13, "2026-10-10T09:30:00Z", "b" * 40),
            pr(14, "2026-10-10T09:29:59Z", "c" * 40),
        ])
        other = snapshot("pl0n3r/GrindFlow")
        a = summarize_product_day([first, other], as_of=AS_OF,
                                  repos=[repo, "pl0n3r/GrindFlow"])
        b = summarize_product_day([other, {**first, "events": list(reversed(first["events"]))}],
                                  as_of="2026-10-11T05:00:00-05:00",
                                  repos=["pl0n3r/GrindFlow", repo])
        self.assertEqual(a, b)
        self.assertEqual(a["status"], "MEASURED")
        self.assertFalse(a["publication_allowed"])
        self.assertEqual(a["repositories"][repo]["merged_prs"], 2)
        self.assertEqual(a["repositories"][repo]["repository_sha"], "d" * 40)
        self.assertEqual(a["repositories"][repo]["run_id"], 100)
        self.assertEqual(a["repositories"][repo]["observations"], 3)
        self.assertEqual(a["repositories"]["pl0n3r/GrindFlow"]["merged_prs"], 0)
        self.assertEqual(a["repositories"][repo]["window_start"], "2026-10-10T09:30:00Z")

    def test_provenance_fields_reject_hostile_non_string_equality(self):
        class BypassEquality:
            def __ne__(self, other):
                return False

        class RaiseOnCompare:
            def __ne__(self, other):
                raise RuntimeError("equality must not execute on untrusted provenance")

        repo = "pl0n3r/Factory"
        good = snapshot(repo, [pr(77, "2026-10-11T09:00:00Z")])
        self.assertEqual(
            summarize_product_day([good], as_of=AS_OF, repos=[repo])["status"],
            "MEASURED",
        )
        for field in ("source", "run_status", "run_conclusion"):
            for bad in (BypassEquality(), RaiseOnCompare(), [], {}, 1, False, None):
                with self.subTest(field=field, bad=type(bad).__name__):
                    observed = summarize_product_day(
                        [{**good, field: bad}], as_of=AS_OF, repos=[repo],
                    )
                    self.assertEqual(observed["status"], "UNKNOWN")
                    self.assertEqual(
                        observed["reason"], "untrusted_stale_or_partial_snapshot",
                    )
                    self.assertFalse(observed["publication_allowed"])
                    self.assertNotIn("repositories", observed)

    def test_missing_run_stale_or_partial_metrics_are_unknown_not_zero(self):
        repo = "pl0n3r/Factory"
        original = snapshot(repo, [pr(77, "2026-10-11T09:00:00Z")])
        invalid = [
            None,
            {**original, "authenticated": False},
            {**original, "authenticated": 1},
            {**original, "complete": False},
            {key: val for key, val in original.items() if key != "repository_sha"},
            {**original, "repository_sha": "not-a-sha"},
            {**original, "repository_sha": None},
            {**original, "repository_sha": True},
            {**original, "pages": 2, "verified_pages": 1},
            {**original, "run_id": None},
            {**original, "run_id": True},
            {**original, "run_status": "in_progress"},
            {**original, "run_conclusion": "failure"},
            {**original, "source": "unknown"},
            {**original, "observed_at": "2026-10-11T08:00:00Z"},
            {**original, "observed_at": "2026-10-11T10:01:00Z"},
            {**original, "events": [{**original["events"][0], "merge_commit_sha": "SECRET"}]},
            {**original, "events": [pr(77, "2026-10-11T09:00:00Z"), pr(77, "2026-10-11T09:01:00Z")]},
            {**original, "events": [pr(77, "2026-10-11T10:00:00Z")]},
        ]
        for row in invalid:
            with self.subTest(row=row):
                result = summarize_product_day([row], as_of=AS_OF, repos=[repo])
                self.assertEqual(result["status"], "UNKNOWN")
                self.assertNotIn("repositories", result)
                self.assertFalse(result["publication_allowed"])
                self.assertNotIn("SECRET", str(result))
        missing = summarize_product_day([], as_of=AS_OF, repos=[repo])
        self.assertEqual(missing["status"], "UNKNOWN")
        self.assertNotIn("repositories", missing)
        minimum = snapshot(repo, [])
        minimum["observed_at"] = "0001-01-01T00:00:00Z"
        boundary = summarize_product_day([minimum],
                                         as_of="0001-01-01T00:00:00Z", repos=[repo])
        self.assertEqual(boundary["status"], "UNKNOWN")
        self.assertNotIn("repositories", boundary)
        overflow_zone = summarize_product_day([minimum],
                                              as_of="0001-01-01T00:00:00+23:00", repos=[repo])
        self.assertEqual(overflow_zone["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
