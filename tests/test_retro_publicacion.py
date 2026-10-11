"""Aceptación #1160: ejecutar el gate REAL extraído del workflow (sin red)."""
from __future__ import annotations

import copy
import json
import re
import textwrap
import unittest
from pathlib import Path

from scripts.retro_diaria import EVENT_KINDS

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "retro-diaria.yml"
NOW = "2026-10-11T09:00:00Z"
SHA = "a" * 40
UUID = "8d34eac1-a9ac-4582-96ac-72842b506c0d"


def gate():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    begin, end = "# RETRO_GATE_BEGIN", "# RETRO_GATE_END"
    if workflow.count(begin) != 1 or workflow.count(end) != 1:
        raise AssertionError("Falta delimitación única del gate ejecutable")
    snippet = workflow.split(begin, 1)[1].split(end, 1)[0]
    namespace = {"__name__": "retro_offline_contract"}
    exec(compile(textwrap.dedent(snippet), str(WORKFLOW), "exec"), namespace)
    return namespace["publication_candidate"]


def good():
    return {
        "event_name": "schedule",
        "repository": "pl0n3r/Factory",
        "ref": "refs/heads/main",
        "run_sha": SHA,
        "phase": "construccion",
        "kill_switch": "RUNNING",
        "quota": {"limit": 5000, "remaining": 1200},
        "lease": {"verified": True, "active": True, "owner": "pl0n3r",
                  "reservation_id": UUID},
        "sources": [
            {"id": "factory-issues-prs", "repo": "pl0n3r/Factory",
             "sha": SHA, "head_sha": SHA,
             "authenticated": True, "complete": True,
             "status": "completed", "conclusion": "success",
             "event_kinds": sorted(EVENT_KINDS)}
        ],
        "events": [
            {"id": "pr-42", "source_id": "factory-issues-prs",
             "repo": "pl0n3r/Factory", "kind": "pr_merged",
             "occurred_at": "2026-10-11T08:00:00Z"}
        ],
        "now": NOW,
    }


class RetroPublicationTests(unittest.TestCase):
    def test_exact_sha_authenticated_completed_sources_only(self):
        evaluate = gate()
        valid = good()
        result = evaluate(valid)
        self.assertEqual(result["status"], "CANDIDATE")
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(result["counts_by_repo"]["pl0n3r/Factory"]["pr_merged"], 1)
        self.assertEqual(result["window_end"], NOW)
        self.assertNotIn("events", result)
        self.assertNotIn("reservation_id", result)
        for change in (
            {"authenticated": False},
            {"complete": False},
            {"status": "in_progress"},
            {"conclusion": "failure"},
            {"conclusion": "skipped"},
            {"head_sha": "b" * 40},
            {"sha": "bad"},
            {"event_kinds": ["pr_merged"]},
        ):
            with self.subTest(change=change):
                bad = copy.deepcopy(valid)
                bad["sources"][0].update(change)
                self.assertEqual(evaluate(bad),
                                 {"status": "UNKNOWN", "publication_allowed": False})
        # Un ID de evento duplicado con contenido contradictorio no publica.
        bad = copy.deepcopy(valid)
        bad["events"].append({**bad["events"][0], "kind": "incident_closed"})
        self.assertEqual(evaluate(bad)["status"], "UNKNOWN")
        # Fuente de SHA igual, pero evento con reloj futuro es igualmente UNKNOWN.
        bad = copy.deepcopy(valid)
        bad["events"][0]["occurred_at"] = "2026-10-12T09:00:00Z"
        self.assertEqual(evaluate(bad)["status"], "UNKNOWN")

    def test_budget_missing_lease_duplicate_and_privileged_event_fail_closed(self):
        evaluate = gate()
        base = good()
        scenarios = (
            ("quota absent", lambda x: x.update(quota=None)),
            ("quota low", lambda x: x["quota"].update(remaining=999)),
            ("quota bool", lambda x: x["quota"].update(remaining=True)),
            ("lease missing", lambda x: x.update(lease=None)),
            ("lease forged", lambda x: x["lease"].update(verified=1)),
            ("lease inactive", lambda x: x["lease"].update(active=False)),
            ("duplicate source", lambda x: x["sources"].append(dict(x["sources"][0]))),
            ("alias source", lambda x: x["sources"].append({
                **x["sources"][0], "id": "alias", "repo": "PL0N3R/factory"})),
            ("workflow_run", lambda x: x.update(event_name="workflow_run")),
            ("issue_comment", lambda x: x.update(event_name="issue_comment")),
            ("wrong repo", lambda x: x.update(repository="pl0n3r/Condor")),
            ("wrong ref", lambda x: x.update(ref="refs/heads/development")),
            ("wrong phase", lambda x: x.update(phase="live")),
            ("paused", lambda x: x.update(kill_switch="PAUSED")),
            ("unknown", lambda x: x.update(kill_switch="UNKNOWN")),
            ("head absent", lambda x: x.update(run_sha="bad")),
        )
        for title, mutation in scenarios:
            with self.subTest(title=title):
                bad = copy.deepcopy(base)
                mutation(bad)
                self.assertEqual(evaluate(bad),
                                 {"status": "UNKNOWN", "publication_allowed": False})

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(workflow, r"(?m)^  schedule:\s*$")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: read", workflow)
        self.assertIn("pull-requests: read", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s+(?:contents|issues|pull-requests): write")
        self.assertIn("gh api repos/pl0n3r/Factory/issues/767", workflow)
        self.assertIn("sha == os.environ['EVENT_SHA']", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertLess(workflow.index("Preflight canónico"), workflow.index("uses: actions/checkout"))
        self.assertIn("No collector/Port authenticated is wired yet", workflow)


if __name__ == "__main__":
    unittest.main()
