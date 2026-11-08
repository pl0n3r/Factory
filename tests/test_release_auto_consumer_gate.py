"""Four executable acceptance tests for Factory #2093."""
from __future__ import annotations

import copy
import json
import subprocess
import unittest
from unittest.mock import patch

from scripts.release_auto_consumer_gate import CONSUMERS, _get, collect_consumer_ci, evaluate_fixture

CANDIDATE = "a" * 40
MAIN_SHA = "b" * 40


def fixture():
    return {
        "candidate_sha": CANDIDATE,
        "consumers": [
            dict(repository=repo, candidate_sha=CANDIDATE, run_id=i + 1,
                 status="completed", conclusion="success", source="independent")
            for i, repo in enumerate(CONSUMERS)
        ],
        "watchdog": dict(candidate_sha=CANDIDATE, run_id=99,
                         status="completed", conclusion="success", source="independent"),
    }


def fake_get(visited):
    def read(route):
        visited.append(route)
        if route.endswith("/branches/main"):
            return {"name": "main", "protected": True, "commit": {"sha": MAIN_SHA}}
        if route.endswith("/check-runs?filter=latest&per_page=100"):
            return {"total_count": 1, "check_runs": [
                {"name": "Validar", "head_sha": MAIN_SHA, "status": "completed",
                 "conclusion": "success", "app": {"slug": "github-actions", "id": 15368}}
            ]}
        raise AssertionError(route)
    return read


class ReleaseAutoConsumerGateTests(unittest.TestCase):
    def blocked(self, result):
        self.assertEqual("BLOCKED", result["state"], result)
        self.assertFalse(result["authorizes_release"])
        self.assertFalse(result["evidence_authenticated"])
        self.assertEqual(0, result["mutations"])
        self.assertEqual(0, result["tag_writes"])
        self.assertEqual(0, result["release_writes"])

    def test_inventario_incompleto_o_sha_invalido_bloquea(self):
        for case in (None, [], {}, dict(fixture(), candidate_sha="bad"),
                     dict(fixture(), extra=True), dict(fixture(), consumers=[])):
            with self.subTest(case=str(case)[:50]):
                self.blocked(evaluate_fixture(case, synthetic=True))
        case = fixture()
        case["consumers"][0] = copy.deepcopy(case["consumers"][1])
        self.blocked(evaluate_fixture(case, synthetic=True))
        self.blocked(evaluate_fixture(fixture(), synthetic=False))

    def test_seis_consumidores_exigen_procedencia_y_compatibilidad_independiente(self):
        visited = []
        result = collect_consumer_ci(fake_get(visited))
        self.blocked(result)
        self.assertEqual("candidate_compatibility_and_watchdog_unknown", result["reason"])
        self.assertEqual(6, result["observed_consumers"])
        self.assertEqual(12, len(visited))
        self.assertEqual(set(CONSUMERS), {"/".join(x.split("/")[2:4]) for x in visited})
        for field, invalid in [("repository", "other/repo"), ("candidate_sha", "c" * 40),
                               ("run_id", 0), ("source", "caller_only"),
                               ("status", "queued"), ("conclusion", "failure")]:
            case = fixture()
            case["consumers"][0][field] = invalid
            with self.subTest(field=field):
                self.blocked(evaluate_fixture(case, synthetic=True))
        for failure in ("failure", "skipped", "queued"):
            def bad_get(route):
                item = fake_get([])(route)
                if "check-runs" in route:
                    item["check_runs"][0]["conclusion"] = failure
                return item
            self.blocked(collect_consumer_ci(bad_get))

    def test_watchdog_y_veto_exact_sha(self):
        for field, invalid in [("candidate_sha", "c" * 40), ("run_id", None),
                               ("source", "untrusted"), ("status", "in_progress"),
                               ("conclusion", "neutral")]:
            case = fixture()
            case["watchdog"][field] = invalid
            with self.subTest(field=field):
                self.blocked(evaluate_fixture(case, synthetic=True))
        passing = evaluate_fixture(fixture(), synthetic=True)
        self.assertEqual("REVIEW_ONLY", passing["state"])
        self.assertTrue(passing["synthetic"])
        self.assertFalse(passing["evidence_authenticated"])
        self.assertFalse(passing["authorizes_release"])
        self.assertEqual(0, passing["mutations"])

    def test_consultas_solo_get_sin_mutacion(self):
        route = "/repos/pl0n3r/Condor/branches/main"
        with patch("scripts.release_auto_consumer_gate.subprocess.run") as mock:
            mock.return_value = subprocess.CompletedProcess([], 0,
                stdout=json.dumps({"name": "main"}).encode(), stderr=b"")
            self.assertEqual({"name": "main"}, _get(route))
            args, kwargs = mock.call_args
            self.assertEqual(["gh", "api", "-X", "GET", route], args[0])
            self.assertTrue(kwargs["check"])
            for bad in ("/repos/pl0n3r/Condor/pulls",
                        "/repos/pl0n3r/Condor/git/refs/tags/v1",
                        "https://external.example/secrets",
                        "/repos/pl0n3r/Condor/branches/main?body=secrets"):
                with self.assertRaises(ValueError):
                    _get(bad)
            self.assertEqual(1, mock.call_count)
        with patch("scripts.release_auto_consumer_gate.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, ["gh"])):
            self.blocked(collect_consumer_ci())
        self.blocked(evaluate_fixture(fixture()))
