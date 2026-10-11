"""Regresiones sin red para Factory #1135 y el incidente raíz #1132."""

from __future__ import annotations

import copy
import json
import unittest

from scripts.release_api_budget import (
    ReleaseBudgetError, classify_transport_failure, estimate_api_budget,
)


def issue(n: int, gate: bool = False) -> dict:
    return {
        "id": 100000 + n, "node_id": f"I_fake_{n}", "number": n,
        "state": "closed", "title": f"Puerta {n}",
        "body": "factory-human-gate factory-release" if gate else "factory-human-gate",
        "created_at": "2026-10-09T20:00:00Z",
        "updated_at": "2026-10-10T20:00:00Z",
        "labels": [{"name": "ejemplo"}],
    }


def search_pages(*, rows: int = 120, gates: int = 98) -> list[dict]:
    items = [issue(i + 1, i < gates) for i in range(rows)]
    return [
        {"incomplete_results": False, "total_count": rows,
         "items": items[start:start + 100]}
        for start in range(0, max(1, rows), 100)
    ]


class ReleaseApiBudgetTests(unittest.TestCase):
    def test_120_results_and_98_gates_require_at_least_104_calls(self):
        pages = search_pages()
        report = estimate_api_budget(pages, copy.deepcopy(pages))
        self.assertEqual(report.search_rows, 120)
        self.assertEqual(report.release_gates, 98)
        self.assertEqual(report.search_calls, 4)
        self.assertEqual(report.comments_calls_min, 98)
        self.assertEqual(report.metadata_calls, 2)
        self.assertEqual(report.total_calls_min, 104)
        self.assertFalse(report.comments_fully_paginated)
        self.assertEqual(estimate_api_budget(search_pages(rows=0, gates=0),
                                              search_pages(rows=0, gates=0)).total_calls_min, 4)

    def test_incomplete_ambiguous_or_drifting_search_fails_closed(self):
        good = search_pages()
        bad_cases = []
        missing = copy.deepcopy(good[:1]); bad_cases.append(missing)
        partial = copy.deepcopy(good); partial[1]["incomplete_results"] = True; bad_cases.append(partial)
        altered = copy.deepcopy(good); altered[1]["total_count"] = 121; bad_cases.append(altered)
        duplicated = copy.deepcopy(good); duplicated[1]["items"][0]["number"] = 1; bad_cases.append(duplicated)
        duplicated_id = copy.deepcopy(good)
        duplicated_id[1]["items"][0]["id"] = duplicated_id[0]["items"][0]["id"]
        bad_cases.append(duplicated_id)
        missing_id = copy.deepcopy(good); del missing_id[1]["items"][0]["id"]; bad_cases.append(missing_id)
        bool_id = copy.deepcopy(good); bool_id[1]["items"][0]["id"] = True; bad_cases.append(bool_id)
        duplicate_node = copy.deepcopy(good)
        duplicate_node[1]["items"][0]["node_id"] = duplicate_node[0]["items"][0]["node_id"]
        bad_cases.append(duplicate_node)
        missing_node = copy.deepcopy(good); del missing_node[1]["items"][0]["node_id"]
        bad_cases.append(missing_node)
        bad_created = copy.deepcopy(good); bad_created[1]["items"][0]["created_at"] = "mañana"
        bad_cases.append(bad_created)
        no_labels = copy.deepcopy(good); del no_labels[1]["items"][0]["labels"]
        bad_cases.append(no_labels)
        bool_count = copy.deepcopy(good); bool_count[0]["total_count"] = True; bad_cases.append(bool_count)
        wrong_body = copy.deepcopy(good); del wrong_body[1]["items"][0]["body"]; bad_cases.append(wrong_body)
        oversized = search_pages(rows=201, gates=0); bad_cases.append(oversized)
        for bad in bad_cases:
            with self.subTest(bad=str(bad)[:70]), self.assertRaises(ReleaseBudgetError):
                estimate_api_budget(bad, good)
        for change in ("body", "updated_at", "title", "id", "node_id",
                       "created_at", "labels", "state_reason"):
            drift = copy.deepcopy(good)
            if change == "id":
                drift[1]["items"][0][change] += 1000000
            elif change == "labels":
                drift[1]["items"][0][change].append({"name": "nueva"})
            elif change == "state_reason":
                drift[1]["items"][0][change] = "completed"
            elif change == "created_at":
                drift[1]["items"][0][change] = "2026-10-08T20:00:00Z"
            else:
                drift[1]["items"][0][change] += " cambiado"
            with self.subTest(change=change), self.assertRaises(ReleaseBudgetError):
                estimate_api_budget(good, drift)

    def test_workflow_projected_search_is_not_complete_api_evidence(self):
        """El adaptador de #1132 debe alimentar páginas REST crudas, no JSON reducido."""
        raw = search_pages()
        projection = [
            {key: item[key] for key in ("number", "state", "title", "body", "updated_at")}
            for page in raw for item in page["items"]
        ]
        # El workflow #1118 entrega una lista plana sin paginación.
        with self.assertRaises(ReleaseBudgetError):
            estimate_api_budget(projection, copy.deepcopy(projection))
        # Envolver artificialmente el JSON reducido no restaura identidades REST.
        wrapped = [
            {"total_count": 120, "incomplete_results": False,
             "items": projection[start:start + 100]}
            for start in (0, 100)
        ]
        with self.assertRaises(ReleaseBudgetError):
            estimate_api_budget(wrapped, copy.deepcopy(wrapped))
        with self.assertRaises(ReleaseBudgetError):
            estimate_api_budget(raw[:1], copy.deepcopy(raw[:1]))
        self.assertEqual(estimate_api_budget(raw, copy.deepcopy(raw)).total_calls_min, 104)

    def test_rate_limit_retries_bounded_and_always_fail_closed(self):
        primary = classify_transport_failure(403, remaining=0, reset_after_seconds=25)
        self.assertEqual(primary.kind, "limite_primario")
        self.assertEqual(primary.suggested_retry_seconds, 25)
        # If both GitHub wait hints exist, the longest delay wins.
        mixed = (
            (403, {"remaining": 0, "retry_after_seconds": 120, "reset_after_seconds": 5}, "limite_primario", None),
            (403, {"remaining": 0, "retry_after_seconds": 5, "reset_after_seconds": 25}, "limite_primario", 25),
            (429, {"retry_after_seconds": 5, "reset_after_seconds": 120}, "limite_secundario", None),
            (429, {"retry_after_seconds": 5, "reset_after_seconds": 25}, "limite_secundario", 25),
            (403, {"remaining": 3, "retry_after_seconds": 5, "reset_after_seconds": 25}, "limite_secundario", 25),
            (403, {"remaining": 0, "retry_after_seconds": 5}, "limite_primario", None),
            (429, {"reset_after_seconds": 5}, "limite_secundario", None),
        )
        for status, options, expected_kind, expected_delay in mixed:
            with self.subTest(status=status, options=options):
                outcome = classify_transport_failure(status, **options)
                self.assertEqual(outcome.kind, expected_kind)
                self.assertEqual(outcome.suggested_retry_seconds, expected_delay)
                self.assertTrue(outcome.must_fail_closed)
                self.assertFalse(outcome.execution_authorized)
        failures = (
            classify_transport_failure(403),
            classify_transport_failure(403, remaining=25),
            classify_transport_failure(429, retry_after_seconds=31),
            classify_transport_failure(429, retry_after_seconds=5, attempts_used=2),
            classify_transport_failure(401, retry_after_seconds=5),
            classify_transport_failure(500, retry_after_seconds=5),
        )
        for failure in (primary, *failures):
            self.assertTrue(failure.must_fail_closed)
            self.assertFalse(failure.execution_authorized)
        self.assertTrue(all(f.suggested_retry_seconds is None for f in failures))
        for option in ({"remaining": False}, {"retry_after_seconds": "15"},
                       {"reset_after_seconds": -1},
                       {"reset_after_seconds": 10**9},
                       {"max_attempts": True}, {"attempts_used": 4}):
            with self.subTest(option=option), self.assertRaises(ReleaseBudgetError):
                classify_transport_failure(403, **option)
        # Una respuesta 200 no es un fallo: ni siquiera puede diagnosticarse como tal.
        with self.assertRaisesRegex(ReleaseBudgetError, "transporte_parametros_invalidos"):
            classify_transport_failure(200, retry_after_seconds=5)

    def test_report_excludes_comment_bodies_and_tokens(self):
        pages = search_pages()
        secret = "ghp_SUPER_SECRET_TOKEN_NOT_A_REAL_CREDENTIAL"
        pages[0]["items"][0]["body"] += secret
        report = estimate_api_budget(pages, copy.deepcopy(pages))
        public = json.dumps(report.public_report(), sort_keys=True)
        self.assertEqual(set(report.public_report()), {
            "search_rows", "release_gates", "search_calls", "comments_calls_min",
            "metadata_calls", "total_calls_min", "comments_fully_paginated",
        })
        self.assertNotIn(secret, public)
        self.assertNotIn("factory-release", public)
        self.assertNotIn("ghp_", repr(report))
        with self.assertRaises(ReleaseBudgetError) as caught:
            altered = copy.deepcopy(pages)
            altered[0]["items"][0]["body"] += "another private string"
            estimate_api_budget(pages, altered)
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn("private string", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
