"""Regresiones del decisor puro para liberar reservas; no usa red ni GitHub real."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.lease_auto_release import (
    RECOVERY, RESERVED, REVIEW, Evidence, decide,
)

START = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
ID = "945515c7-78b2-4dc6-9803-06808fd0abb8"


def fixture(minute: int = 29, *, status: str = RESERVED,
            recovery_minute: int | None = None) -> Evidence:
    return Evidence(
        now=START + timedelta(minutes=minute),
        last_activity_at=START,
        recovery_since=(
            START + timedelta(minutes=recovery_minute)
            if recovery_minute is not None else None
        ),
        status=status, phase="construccion",
        issue_open=True, v3_active=True, lease_id=ID,
        owner="pl0n3r", branch_sha="a" * 40,
        branch_present=True, evidence_complete=True, trusted_phase=True,
        kill_switch_running=True, ci_running=False,
        changes_requested=False, owner_recovered=False,
        rate_remaining=20, rate_limit=100,
    )


class LeaseAutoReleaseTests(unittest.TestCase):
    def test_stale_grace_and_fail_closed_guards(self) -> None:
        # Exactitud del contrato: detección a los 30 min; liberación SOLO
        # tras 10 min desde la transición verificable a recuperación.
        expected = (
            (29, RESERVED, None, "wait", 11),
            (30, RESERVED, None, "mark_recovery", 10),
            (39, RECOVERY, 30, "wait", 1),
            (40, RECOVERY, 30, "release", 0),
            (49, RECOVERY, 40, "wait", 1),
            (50, RECOVERY, 40, "release", 0),
            (44, RECOVERY, 35, "wait", 1),
            (45, RECOVERY, 35, "release", 0),
        )
        for minute, state, recovered, action, remaining in expected:
            with self.subTest(minute=minute, state=state):
                result = decide(fixture(minute, status=state,
                                        recovery_minute=recovered))
                self.assertEqual(result.action, action)
                self.assertEqual(result.libera_en_min, remaining)

        for changed in (
            {"kill_switch_running": False},
            {"ci_running": True},
            {"changes_requested": True},
            {"phase": "live"},
            {"owner_recovered": True},
            {"issue_open": False},
            {"v3_active": False},
            {"branch_present": False},
            {"status": "estado: bloqueado"},
        ):
            with self.subTest(block=changed):
                self.assertNotEqual(
                    decide(replace(fixture(60, status=RECOVERY,
                                           recovery_minute=30), **changed)).action,
                    "release",
                )
        for changed in (
            {"evidence_complete": False},
            {"trusted_phase": False},
            {"rate_remaining": 19},
            {"rate_remaining": None},
            {"rate_remaining": True},
            {"lease_id": "invalid"},
            {"branch_sha": "not-a-sha"},
            {"last_activity_at": None},
            {"last_activity_at": START.replace(tzinfo=None)},
            {"last_activity_at": START + timedelta(hours=2)},
            {"recovery_since": None},
            {"recovery_since": START.replace(tzinfo=None)},
            {"recovery_since": START - timedelta(minutes=1)},
            {"recovery_since": START + timedelta(minutes=61)},
            {"ci_running": None},
            {"status": None},
        ):
            with self.subTest(unknown=changed):
                self.assertNotEqual(
                    decide(replace(fixture(60, status=RECOVERY,
                                           recovery_minute=30), **changed)).action,
                    "release",
                )

    def test_original_owner_return_or_competing_evidence_preserves_lease(self):
        case = fixture(50, status=RECOVERY, recovery_minute=30)
        self.assertEqual(
            decide(replace(case, last_activity_at=START + timedelta(minutes=39))).action,
            "unknown",
        )
        self.assertEqual(decide(replace(case, owner_recovered=True)).action, "wait")
        self.assertEqual(decide(replace(case, ci_running=True)).reason,
                         "protected_or_active_work")
        self.assertEqual(decide(replace(case, changes_requested=True)).action, "wait")

    def test_budget_exact_20_percent_and_unknown_are_distinct(self):
        e = fixture(50, status=RECOVERY, recovery_minute=30)
        self.assertEqual(decide(e).action, "release")
        self.assertEqual(decide(replace(e, rate_remaining=19)).action, "unknown")
        self.assertEqual(decide(replace(e, rate_limit=0)).action, "unknown")
        self.assertEqual(decide(replace(e, rate_remaining=101)).action, "unknown")

    def test_extreme_utc_clocks_fail_closed_without_overflow(self):
        # datetime.max + 30/40 minutos no debe matar el cron.
        far = datetime.max.replace(tzinfo=timezone.utc)
        reserved = replace(fixture(30), now=far, last_activity_at=far)
        self.assertEqual(decide(reserved).reason, "invalid_clock_range")
        recovering = replace(
            fixture(40, status=RECOVERY, recovery_minute=30),
            now=far, last_activity_at=far, recovery_since=far,
        )
        self.assertEqual(decide(recovering).reason, "invalid_clock_range")

    def test_scheduled_workflow_cannot_write_or_claim_release(self):
        workflow = (
            Path(__file__).resolve().parents[1] /
            ".github/workflows/liberar-reservas.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("cron: '*/10 * * * *'", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("if: steps.budget.outputs.allow == 'true'", workflow)
        self.assertIn("gh api /rate_limit", workflow)
        self.assertIn("AUDITORÍA SOLAMENTE", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("liberar-forzado", workflow)

    def test_no_io_or_external_authority_is_derived(self):
        e = fixture(45, status=REVIEW)
        self.assertEqual(decide(e).action, "mark_recovery")
        self.assertEqual(e.status, REVIEW)
        self.assertEqual(e.branch_sha, "a" * 40)
        self.assertNotEqual(decide(replace(e, phase="UNKNOWN")).action, "release")
        self.assertNotEqual(decide(replace(e, trusted_phase=False)).action, "release")

    def test_phase_and_status_must_be_actual_strings(self):
        """Hostile comparison operators cannot certify release eligibility."""
        class AlwaysEqual:
            def __ne__(self, other):
                return False

            def __eq__(self, other):
                return True

        class Explosive:
            def __ne__(self, other):
                raise RuntimeError("untrusted comparison")

            def __eq__(self, other):
                raise RuntimeError("untrusted comparison")

        eligible = fixture(50, status=RECOVERY, recovery_minute=30)
        self.assertEqual(decide(eligible).action, "release")
        for name in ("phase", "status"):
            for forged in (None, True, 1, 1.0, [], AlwaysEqual(), Explosive()):
                with self.subTest(field=name, forged=type(forged).__name__):
                    candidate = replace(eligible, **{name: forged})
                    result = decide(candidate)
                    self.assertEqual(result.action, "unknown")
                    self.assertEqual(result.reason, "invalid_evidence_types")

    def test_quota_preflight_runs_real_bash_without_false_green(self):
        """Exercise the actual workflow preflight with a fake GH API response."""
        import json
        import os
        import shutil
        import subprocess
        import tempfile
        import textwrap

        if shutil.which("jq") is None:
            self.skipTest("jq needed for the real GitHub Actions preflight")
        source = (
            Path(__file__).resolve().parents[1] /
            ".github/workflows/liberar-reservas.yml"
        ).read_text(encoding="utf-8")
        name = "      - name: Preflight autenticado de cuota API (no publica datos privados)\n"
        self.assertEqual(source.count(name), 1)
        section = source.split(name, 1)[1]
        script = textwrap.dedent(
            section.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
        )
        for remaining, limit, should_allow in (
            (20, 100, True), (19, 100, False),
            (19.5, 100, False), (20, 100.5, False),
            (True, 100, False), (20, 0, False),
            (1000000001, 1000000001, False),
        ):
            with self.subTest(remaining=remaining, limit=limit):
                with tempfile.TemporaryDirectory() as folder:
                    helper = Path(folder) / "gh"
                    helper.write_text(
                        "#!/bin/sh\nprintf '%s\\n' \"$QUOTA_JSON\"\n",
                        encoding="utf-8",
                    )
                    helper.chmod(0o755)
                    output = Path(folder) / "output.txt"
                    env = dict(os.environ)
                    env.update({
                        "PATH": folder + os.pathsep + env.get("PATH", ""),
                        "QUOTA_JSON": json.dumps({
                            "resources": {"core": {
                                "remaining": remaining, "limit": limit
                            }}
                        }),
                        "RUNNER_TEMP": folder,
                        "GITHUB_OUTPUT": str(output),
                        "GH_TOKEN": "unused",
                        "EXPECTED_REPOSITORY": "pl0n3r/Factory",
                        "OBSERVED_REPOSITORY": "pl0n3r/Factory",
                    })
                    proc = subprocess.run(
                        ["bash", "-c", script], env=env,
                        capture_output=True, text=True, timeout=12,
                    )
                    self.assertEqual(
                        proc.returncode == 0, should_allow,
                        msg=proc.stderr,
                    )
                    logged = output.read_text(encoding="utf-8") if output.exists() else ""
                    self.assertEqual("allow=true" in logged, should_allow)


if __name__ == "__main__":
    unittest.main()
