#!/usr/bin/env python3
"""Regresiones de la entrega diaria del resumen unattended al dueño."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from scripts.unattended_daily_summary import (
    DailySummaryError,
    Fact,
    immediate_incidents,
    parse_daily_marker,
    publish_once,
    render_summary,
)
from scripts.unattended_watchdog import DailySummary, WatchdogDecision

ROOT = Path(__file__).resolve().parents[1]


def decision(
    *,
    freshness: str = "fresh",
    incidents: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    gates: tuple[str, ...] = (),
    integrated: tuple[str, ...] = (),
    active: tuple[str, ...] = ("Factory#768",),
    next_actions: tuple[str, ...] = ("continuar",),
) -> WatchdogDecision:
    return WatchdogDecision(
        action="BLOCKED" if incidents or blockers else "ALLOW",
        authority="unchanged",
        incidents=(),
        new_alert_fingerprints=(),
        interrupt_owner=any(
            item.startswith("S1:") or item.startswith("S2:")
            for item in incidents
        ),
        daily_summary=DailySummary(
            active_fronts=active,
            state_freshness=freshness,
            incidents=incidents,
            blockers=blockers,
            human_gates=gates,
            integrated=integrated,
            reverted=(),
            next_actions=next_actions,
        ),
        evidence_fingerprint="a" * 64,
    )


def runtime_input(updated_at: str = "2026-10-02T12:30:00Z") -> dict[str, object]:
    return {
        "guard": {},
        "evidence": {
            "state": {"updated_at": updated_at},
            "presence": {"source": "factory-state-github"},
        },
    }


class FakeClient:
    def __init__(self, comments=None):
        self.comments = list(comments or [])
        self.writes = []

    def list_issue_comments(self, issue_number):
        self.issue_number = issue_number
        return list(self.comments)

    def _request(self, method, path, payload=None):
        self.writes.append((method, path, payload))
        return {"ok": True}


class UnattendedDailySummaryTests(unittest.TestCase):
    def test_workflow_delivers_once_per_local_day_at_0800_bogota(self):
        workflow = (
            ROOT / ".github" / "workflows" / "unattended-watchdog.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("cron: '*/15 * * * *'", workflow)
        self.assertIn("cron: '0 13 * * *'", workflow)
        self.assertIn("github.event.schedule == '0 13 * * *'", workflow)
        self.assertIn("python3 -m scripts.unattended_daily_summary", workflow)
        self.assertIn("issues: write", workflow)
        self.assertNotIn("secrets.", workflow)

        body = (
            '<!-- factory-unattended-daily-summary '
            '{"local_date":"2026-10-02","version":1} -->\n'
            "## Resumen diario Factory"
        )
        client = FakeClient()
        self.assertTrue(
            publish_once(client, local_date="2026-10-02", body=body)
        )
        self.assertEqual(len(client.writes), 1)
        client.comments.append(
            {
                "user": {"login": "github-actions[bot]"},
                "body": body,
            }
        )
        self.assertFalse(
            publish_once(client, local_date="2026-10-02", body=body)
        )
        self.assertEqual(len(client.writes), 1)

        with self.assertRaises(DailySummaryError):
            parse_daily_marker(
                {
                    "user": {"login": "github-actions[bot]"},
                    "body": (
                        '<!-- factory-unattended-daily-summary '
                        '{"local_date":"2026-10-02","version":1} -->'
                        '<!-- factory-unattended-daily-summary broken -->'
                    ),
                }
            )

    def test_summary_reports_source_age_and_unknown_or_stale_without_invention(self):
        now = datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)
        stale = render_summary(
            decision(freshness="stale", blockers=("state_stale",)),
            runtime_input(),
            {"decisions": (), "blockers": (), "advances": ()},
            now,
        )
        self.assertIn(
            "STATE/Presence — source=factory-state-github · age=30m · stale",
            stale,
        )
        self.assertIn(
            "CI: UNKNOWN — source=Factory#584:not-observed · age=UNKNOWN · unknown",
            stale,
        )
        self.assertIn("UNKNOWN/STALE", stale)

        missing = render_summary(
            decision(freshness="unknown", active=(), next_actions=()),
            {},
            {"decisions": (), "blockers": (), "advances": ()},
            now,
        )
        self.assertIn(
            "STATE/Presence — source=4C:UNKNOWN · age=UNKNOWN · unknown",
            missing,
        )
        self.assertIn(
            "UNKNOWN: no hay avance demostrable en la evidencia disponible.",
            missing,
        )

    def test_pending_decisions_and_blockers_are_rendered_first(self):
        now = datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)
        context = {
            "decisions": (
                Fact("#900 decisión", "GitHub Issues", 5, "fresh"),
            ),
            "blockers": (
                Fact("#901 bloqueo", "GitHub Issues", 8, "fresh"),
            ),
            "advances": (
                Fact("#899 completado", "GitHub Issues", 10, "fresh"),
            ),
        }
        rendered = render_summary(
            decision(),
            runtime_input(),
            context,
            now,
        )
        self.assertLess(
            rendered.index("### Decisiones pendientes"),
            rendered.index("### Bloqueos"),
        )
        self.assertLess(
            rendered.index("### Bloqueos"),
            rendered.index("### Avances"),
        )
        self.assertIn("#900 decisión — source=GitHub Issues · age=5m · fresh", rendered)
        self.assertIn("#901 bloqueo — source=GitHub Issues · age=8m · fresh", rendered)

    def test_only_s1_s2_are_immediate_interrupts(self):
        incidents = (
            "S3:degraded",
            "S2:service_down",
            "UNKNOWN:missing",
            "S1:data_loss",
        )
        self.assertEqual(
            immediate_incidents(incidents),
            ("S1:data_loss", "S2:service_down"),
        )
        now = datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)
        rendered = render_summary(
            decision(incidents=incidents),
            runtime_input(),
            {"decisions": (), "blockers": (), "advances": ()},
            now,
        )
        immediate_section = rendered.split(
            "Alerta inmediata aparte:\n", 1
        )[1].split("### Próximas acciones", 1)[0]
        self.assertIn("S1:data_loss", immediate_section)
        self.assertIn("S2:service_down", immediate_section)
        self.assertNotIn("S3:degraded", immediate_section)
        self.assertNotIn("UNKNOWN:missing", immediate_section)

    def test_normal_s1_and_missing_data_matrix(self):
        now = datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)
        context = {"decisions": (), "blockers": (), "advances": ()}

        normal = render_summary(
            decision(),
            runtime_input(),
            context,
            now,
        )
        self.assertIn(
            "Alerta inmediata aparte:\n- Ninguna. Solo S1/S2 interrumpen",
            normal,
        )

        s1 = render_summary(
            decision(incidents=("S1:critical",), blockers=("critical",)),
            runtime_input(),
            context,
            now,
        )
        self.assertIn("Alerta inmediata aparte:\n- S1:critical", s1)

        missing = render_summary(
            decision(
                freshness="unknown",
                incidents=("UNKNOWN:invalid_evidence",),
                blockers=("invalid_evidence",),
                active=(),
                next_actions=(),
            ),
            {},
            context,
            now,
        )
        self.assertIn("UNKNOWN:invalid_evidence", missing)
        self.assertIn("source=4C:UNKNOWN · age=UNKNOWN · unknown", missing)
        self.assertIn("### Cuotas", missing)


if __name__ == "__main__":
    unittest.main()
