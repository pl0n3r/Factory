"""Fase A: release/recovery son hipótesis revisables, no autoridad."""
import copy
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from scripts.lease_auto_release import Decision
from scripts.lease_auto_release_integration import preview_integrated_activity
from scripts.lease_activity_collector import collect_activity
from test_lease_activity_collector import API, NOW, marker
from test_lease_auto_release_integration import canonical_review_pr_body
from test_lease_release_executor import snapshot


class StrictReadOnlyPort:
    def __init__(self, item):
        self.item = item
        self.reads = 0

    def read(self, issue):
        if issue != 21:
            raise AssertionError("incorrect issue")
        self.reads += 1
        return self.item

    def __getattr__(self, name):
        raise AssertionError("forbidden write: " + name)


class LeaseHypotheticalPreviewTests(unittest.TestCase):
    def _context(self, age, status="estado: reservado", recovery_minutes=None):
        api = API()
        api.pulls[0]["state"] = "open"
        api.pulls[0]["base"] = {"ref": "main"}
        api.pulls[0]["body"] = canonical_review_pr_body()
        api.checks[0]["status"] = "completed"
        report = collect_activity(api, 21, now=NOW)
        self.assertTrue(report["evidence_complete"])
        lease = json.loads(marker().split("<!-- condor-reserva ", 1)[1]
                           .split(" -->", 1)[0])
        item = replace(
            snapshot(recovery=False),
            issue=21, branch="trabajo/issue-21",
            reservation_id=lease["reservation_id"],
            marker={**snapshot(recovery=False).marker,
                    "reservation_id": lease["reservation_id"],
                    "branch": "trabajo/issue-21"},
            status=status, now=NOW,
            last_activity_at=NOW - timedelta(minutes=age),
            recovery_since=(NOW - timedelta(minutes=recovery_minutes)
                            if recovery_minutes is not None else None),
            rate_remaining=40, ci_running=False,
        )
        observed = dict(report)
        observed["status"] = status
        observed["last_activity_at"] = (
            NOW - timedelta(minutes=age)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return api, StrictReadOnlyPort(item), observed

    def test_authenticated_hypothetical_actions_are_non_authoritative(self):
        cases = [
            (35, "estado: reservado", None,
             "mark_recovery", "inactive_30_minutes"),
            (45, "estado: requiere recuperación", 12,
             "release", "inactive_after_recovery_grace"),
        ]
        for age, status, recovery_minutes, action, reason in cases:
            with self.subTest(action=action):
                api, port, report = self._context(
                    age, status, recovery_minutes)
                with patch("scripts.lease_auto_release_integration.collect_activity",
                           return_value=report):
                    observed = preview_integrated_activity(
                        api, port, 21, now=NOW)
                self.assertEqual(
                    (observed.state, observed.action, observed.reason),
                    ("read_only", action, reason),
                )
                self.assertEqual(observed.activity_age_minutes, age)
                self.assertEqual(observed.activity_source, "workflow_push")
                self.assertIs(observed.release_authorized, False)
                self.assertIs(observed.lock_verified, False)
                self.assertIs(observed.cas_verified, False)
                self.assertEqual(port.reads, 1)

    def test_forged_or_early_release_stays_unknown(self):
        for age, reason, expected in (
            (20, "inactive_after_recovery_grace", "inactivity_not_proven"),
            (45, "invented_reason", "inactivity_not_proven"),
            (45, "inactive_after_recovery_grace", "inactivity_not_proven"),
        ):
            with self.subTest(age=age, reason=reason):
                api, port, report = self._context(age)
                # Un plugin/decisor falsificado nunca convierte un estado
                # reservado sin gracia auténtica en release permitido.
                forged = Decision("release", reason)
                if age == 45 and reason == "inactive_after_recovery_grace":
                    report["ci_veto_only"] = True
                    report["ci_running"] = True
                with (patch("scripts.lease_auto_release_integration.collect_activity",
                            return_value=report),
                      patch("scripts.lease_auto_release_integration.decision_from_snapshot",
                            return_value=forged)):
                    result = preview_integrated_activity(
                        api, port, 21, now=NOW)
                self.assertEqual(result.state, "UNKNOWN")
                self.assertIn(result.reason, (
                    expected, "collector_unknown", "inconsistent_authenticated_sources"))
                self.assertFalse(result.release_authorized)

    def test_consumer_validator_accepts_only_safe_candidate_schema(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows"
                    / "observador-reservas-consumidor.yml").read_text()
        anchor = '            python3 - "$issue_number" "$RUNNER_TEMP/lease-local-raw.json" \\'
        self.assertEqual(workflow.count(anchor), 1)
        script = textwrap.dedent(workflow.split(anchor, 1)[1]
                                 .split("<<'PY'\n", 1)[1]
                                 .split("\n            PY", 1)[0])
        self.assertIn('raw.get("action") not in (', script)
        for action in ("wait", "mark_recovery", "release"):
            self.assertIn('"' + action + '"', script)
        self.assertIn("terminal_certified", workflow)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)

        original = {
            "issue": 21, "state": "read_only",
            "action": "release",
            "reason": "inactive_after_recovery_grace",
            "activity_age_minutes": 45,
            "activity_source": "workflow_push",
            "release_authorized": False, "lock_verified": False,
            "cas_verified": False, "mutations": 0,
        }
        def run_validator(value):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "record.json"
                p.write_text(json.dumps(value), encoding="utf-8")
                completed = subprocess.run(
                    [sys.executable, "-c", script, "21", str(p)],
                    capture_output=True, text=True, timeout=10, check=True)
            return json.loads(completed.stdout.strip())
        for action, reason, age in (
            ("wait", "activity_window", 20),
            ("mark_recovery", "inactive_30_minutes", 35),
            ("release", "inactive_after_recovery_grace", 45),
        ):
            with self.subTest(accepted=action):
                candidate = {**original, "action": action, "reason": reason,
                             "activity_age_minutes": age}
                record = run_validator(candidate)
                self.assertEqual((record["state"], record["action"]),
                                 ("read_only", action))
                self.assertFalse(record["release_authorized"])
                self.assertFalse(record["lock_verified"])
                self.assertFalse(record["cas_verified"])
                self.assertEqual(record["mutations"], 0)
        for edits in (
            {"activity_age_minutes": 29},
            {"activity_age_minutes": True},
            {"activity_age_minutes": None},
            {"reason": "forged_release"},
            {"activity_source": None},
            {"release_authorized": True},
            {"lock_verified": True},
            {"cas_verified": True},
            {"mutations": 1},
            {"state": "authorized"},
            {"action": "unknown"},
        ):
            with self.subTest(rejected=edits):
                record = run_validator({**original, **edits})
                self.assertEqual((record["state"], record["action"]),
                                 ("UNKNOWN", "unknown"))
                self.assertFalse(record["release_authorized"])
                self.assertFalse(record["lock_verified"])
                self.assertFalse(record["cas_verified"])
                self.assertEqual(record["mutations"], 0)


if __name__ == "__main__":
    unittest.main()
