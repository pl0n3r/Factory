#!/usr/bin/env python3
"""Regresiones de la entrega diaria del resumen unattended al dueño."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from scripts.unattended_daily_summary import (
    DailySummaryError,
    Fact,
    collect_issue_context,
    immediate_incidents,
    main as daily_main,
    parse_daily_marker,
    parse_night_marker,
    publish_night_report_once,
    publish_once,
    render_night_report,
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


        night = render_night_report(
            decision(integrated=("PR #1 fusionado",)),
            {"decisions": (), "blockers": (), "advances": ()},
            datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc),
        )
        self.assertIn("Informe de la noche Factory", night)
        self.assertTrue(
            publish_night_report_once(
                client,
                local_date="2026-10-02",
                body=night,
            )
        )
        client.comments.append(
            {
                "user": {"login": "github-actions[bot]"},
                "body": night,
            }
        )
        self.assertFalse(
            publish_night_report_once(
                client,
                local_date="2026-10-02",
                body=night,
            )
        )
        self.assertEqual(parse_night_marker(client.comments[-1]), "2026-10-02")

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


    def test_live_issue_context_and_entrypoint_are_fail_closed_and_publish_once(self):
        now = datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)

        class ContextClient:
            def _request(self, method, path, payload=None):
                self.last = (method, path, payload)
                if "state=open" in path:
                    return [
                        {
                            "number": 900,
                            "title": "decidir canal",
                            "updated_at": "2026-10-02T12:55:00Z",
                            "labels": [{"name": "decisión: dueño"}],
                            "body": (
                                '<!-- factory-human-gate '
                                '{"recommendation":"A","safe_default":"B"} -->'
                            ),
                        },
                        {
                            "number": 901,
                            "title": "dependencia externa",
                            "updated_at": None,
                            "labels": [{"name": "estado: bloqueado"}],
                            "body": "",
                        },
                    ]
                if "state=closed" in path:
                    return [
                        {
                            "number": 899,
                            "title": "trabajo integrado",
                            "updated_at": "2026-10-02T12:50:00Z",
                            "closed_at": "2026-10-02T12:50:00Z",
                            "labels": [{"name": "estado: completado"}],
                            "body": "",
                        }
                    ]
                raise AssertionError(path)

        context = collect_issue_context(ContextClient(), now)
        self.assertIn("recomendación=A · seguro=B", context["decisions"][0].text)
        self.assertEqual(context["decisions"][0].age_minutes, 5)
        self.assertTrue(context["blockers"][0].text.startswith("causa: #901"))
        self.assertEqual(context["blockers"][0].freshness, "unknown")
        self.assertEqual(context["advances"][0].text, "#899 trabajo integrado")

        class MainClient:
            def __init__(self, token, repository):
                self.token = token
                self.repository = repository
                self.comments = []
                self.writes = []

            def list_owned_alerts(self):
                return {}

            def list_issue_comments(self, issue_number):
                return list(self.comments)

            def get_issue(self, issue_number):
                return {"number": issue_number}

            def _request(self, method, path, payload=None):
                self.writes.append((method, path, payload))
                return {"ok": True}

        clients = []

        def client_factory(token, repository):
            client = MainClient(token, repository)
            clients.append(client)
            return client

        patches = (
            patch(
                "scripts.unattended_daily_summary.GitHubIssueClient",
                side_effect=client_factory,
            ),
            patch(
                "scripts.unattended_daily_summary.load_config",
                return_value={
                    "ready_without_dispatch_minutes": 10,
                    "reservation_stale_minutes": 15,
                    "state_stale_minutes": 20,
                },
            ),
            patch(
                "scripts.unattended_daily_summary.collect_github_input",
                return_value=runtime_input(),
            ),
            patch(
                "scripts.unattended_daily_summary.evaluate_runtime",
                return_value=(decision(), SimpleNamespace()),
            ),
            patch(
                "scripts.unattended_daily_summary.collect_issue_context",
                return_value={"decisions": (), "blockers": (), "advances": ()},
            ),
            patch(
                "scripts.unattended_daily_summary.evaluate_unattended_kill_switch",
                return_value=SimpleNamespace(global_pause=False, reason="running"),
            ),
        )
        with patch.dict(
            os.environ,
            {"GH_TOKEN": "token", "GITHUB_REPOSITORY": "pl0n3r/Factory"},
            clear=False,
        ), patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            self.assertEqual(daily_main(), 0)
        self.assertEqual(len(clients[-1].writes), 2)
        self.assertTrue(
            all("/issues/768/comments" in write[1] for write in clients[-1].writes)
        )
        bodies = [write[2]["body"] for write in clients[-1].writes]
        self.assertTrue(any("factory-unattended-night-report" in body for body in bodies))
        self.assertTrue(any("factory-unattended-daily-summary" in body for body in bodies))

        paused = MainClient("token", "pl0n3r/Factory")
        with patch.dict(
            os.environ,
            {"GH_TOKEN": "token", "GITHUB_REPOSITORY": "pl0n3r/Factory"},
            clear=False,
        ), patch(
            "scripts.unattended_daily_summary.GitHubIssueClient",
            return_value=paused,
        ), patch(
            "scripts.unattended_daily_summary.load_config",
            return_value={},
        ), patch(
            "scripts.unattended_daily_summary.collect_github_input",
            return_value=runtime_input(),
        ), patch(
            "scripts.unattended_daily_summary.evaluate_runtime",
            return_value=(decision(), SimpleNamespace()),
        ), patch(
            "scripts.unattended_daily_summary.collect_issue_context",
            return_value={"decisions": (), "blockers": (), "advances": ()},
        ), patch(
            "scripts.unattended_daily_summary.evaluate_unattended_kill_switch",
            return_value=SimpleNamespace(global_pause=True, reason="paused"),
        ):
            self.assertEqual(daily_main(), 1)
        self.assertEqual(paused.writes, [])



if __name__ == "__main__":
    unittest.main()
