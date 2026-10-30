#!/usr/bin/env python3
"""Factory #1853: proyección STATE/Presence y límite de autoridad watchdog.

Las pruebas llaman al adaptador y runtime reales con fixtures sintéticas.
No abren GitHub, no publican resúmenes, no inspeccionan matrices de cobertura.
"""
from __future__ import annotations

from copy import deepcopy
import http.client
import json
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib import request

from scripts.unattended_state_source import project_state_presence
from scripts.unattended_watchdog_runtime import (
    collect_github_input,
    evaluate_runtime,
)

NOW = "2026-10-02T04:10:00Z"
RID = "11111111-2222-4333-8444-555555555555"
HEAD = "a" * 40
REPOSITORY = "pl0n3r/Factory"
NUMBER = 775
CONFIG = {
    "ready_without_dispatch_minutes": 10,
    "reservation_stale_minutes": 15,
    "state_stale_minutes": 20,
}


def comment(user, body, at="2026-10-02T04:09:00Z"):
    return {
        "user": {"login": user},
        "body": body,
        "created_at": at,
        "updated_at": at,
    }


def reservation(**overrides):
    item = {
        "version": 3,
        "owner": "fixture-owner",
        "reservation_id": RID,
        "branch": "trabajo/issue-775",
        "active": True,
        "reason": "tomar",
        "acceptance_sha256": "b" * 64,
        "task_marker_sha256": "c" * 64,
        "task_paths": ["tests/test_fixture.py"],
        "task_depends_on": [],
    }
    item.update(overrides)
    return comment(
        "github-actions[bot]",
        "<!-- condor-reserva " + json.dumps(item, sort_keys=True) + " -->",
    )


def state(**overrides):
    item = {
        "work_identity": f"{REPOSITORY}#{NUMBER}",
        "repository": REPOSITORY,
        "branch": "trabajo/issue-775",
        "head_sha": HEAD,
        "reservation_id": RID,
        "risk": "medium",
        "severity": "S3",
        "evidence": ["fixture:synthetic"],
        "last_state": "implementing",
        "next_action": "run offline acceptance",
        "blockers": [],
        "updated_at": "2026-10-02T04:08:30Z",
    }
    item.update(overrides)
    return comment(
        "fixture-owner",
        "<!-- factory-state " + json.dumps(
            {"version": 1, "state": item}, sort_keys=True,
        ) + " -->",
    )


class FixtureGitHubClient:
    """Solo el contrato de lecturas requerido por collect_github_input."""

    repository = REPOSITORY

    def __init__(self, comments=None, *, head=HEAD, labels=None, number=NUMBER):
        self.messages = [reservation(), state()] if comments is None else comments
        self.head = head
        self.labels = ["estado: reservado"] if labels is None else labels
        self.number = number
        self.calls = []

    def list_open_work_items(self):
        self.calls.append("list_open_work_items")
        return [{
            "number": self.number,
            "labels": [{"name": label} for label in self.labels],
        }]

    def list_issue_comments(self, issue_number):
        self.calls.append(("list_issue_comments", issue_number))
        return deepcopy(self.messages)

    def get_branch_head(self, issue_number):
        self.calls.append(("get_branch_head", issue_number))
        return self.head


class CoberturaFactory62Tests(unittest.TestCase):
    def project(self, messages, **changes):
        options = {
            "repository": REPOSITORY,
            "issue_number": NUMBER,
            "comments": messages,
            "now": NOW,
            "state_stale_minutes": 20,
            "reservation_stale_minutes": 15,
            "branch_head_sha": HEAD,
        }
        options.update(changes)
        return project_state_presence(**options)

    def assert_guarded(self, result):
        self.assertEqual(result["guard"]["action"], "BLOCKED")
        self.assertEqual(result["guard"]["authority"], "unchanged")

    def test_contrato_principal(self):
        # L45-U1: la ruta real #769 proyecta comentarios GitHub ya
        # suministrados, verifica HEAD y entrega STATE a la frontera 4B/4C.
        client = FixtureGitHubClient()
        source_messages = deepcopy(client.messages)
        packet = collect_github_input(client, CONFIG, NOW)
        self.assert_guarded(packet)
        self.assertEqual(
            client.calls,
            [
                "list_open_work_items",
                ("list_issue_comments", NUMBER),
                ("get_branch_head", NUMBER),
            ],
        )
        self.assertEqual(client.messages, source_messages)
        evidence = packet["evidence"]
        self.assertIsInstance(evidence, dict)
        self.assertEqual(evidence["state"]["work_identity"], f"{REPOSITORY}#{NUMBER}")
        self.assertEqual(evidence["state"]["head_sha"], HEAD)
        self.assertEqual(evidence["active_fronts"], [f"{REPOSITORY}#{NUMBER}"])
        self.assertEqual(evidence["presence"]["sessions"], [])
        self.assertEqual(evidence["presence"]["capacity"], {
            "known_slots": 0,
            "eligible_free_slots": 0,
            "degraded_slots": 0,
            "freshness": "unknown",
        })

        # L47-U1: incluso un STATE READY no concede ALLOW. El guard
        # 4B falta, por lo que el runtime 4C real debe quedarse BLOCKED.
        projected = self.project(client.messages)
        self.assertEqual(projected.status, "READY")
        self.assertEqual(projected.authority, "unchanged")
        self.assertIn("presence_heartbeat_unavailable", projected.reasons)
        self.assertIn("presence_capacity_unknown", projected.reasons)
        decision, plan = evaluate_runtime(
            CONFIG, packet["guard"], packet["evidence"], {},
        )
        self.assertEqual(decision.action, "BLOCKED")
        self.assertEqual(decision.authority, "unchanged")
        self.assertEqual(plan.action, "BLOCKED")
        self.assertEqual(plan.authority, "unchanged")
        self.assertEqual(plan.close, ())

    def test_falla_cerrado(self):
        # L45/L47: sin marker, sin lease, con SHA ajeno, timestamps
        # falsos o reserva liberada no se fabrica un frente ejecutable.
        missing_state = self.project([reservation()])
        self.assertEqual(missing_state.status, "UNKNOWN")
        self.assertEqual(missing_state.authority, "unchanged")
        self.assertIsNone(missing_state.state)

        released = self.project([
            reservation(), state(),
            reservation(active=False, reason="pr-merged"),
        ])
        self.assertEqual(released.status, "UNKNOWN")
        self.assertEqual(released.authority, "unchanged")
        self.assertIsNone(released.state)

        failures = (
            ([reservation(), state(head_sha="d" * 40)], HEAD),
            ([reservation(), state(repository="fixture/other")], HEAD),
            ([reservation(), state(reservation_id="2" * 8 + "-2222-4333-8444-555555555555")], HEAD),
            ([reservation(active=True, version=1), state()], HEAD),
            ([reservation(), state(updated_at="2026-10-02T04:12:00Z")], HEAD),
        )
        for comments, head in failures:
            with self.subTest(comments=comments):
                result = self.project(comments, branch_head_sha=head)
                self.assertNotEqual(result.status, "READY")
                self.assertEqual(result.authority, "unchanged")

        # El runtime no usa READY sin timestamp para inferir ALLOW.
        for client in (
            FixtureGitHubClient(comments=[reservation()]),
            FixtureGitHubClient(head="d" * 40),
            FixtureGitHubClient(labels=["estado: disponible"]),
            FixtureGitHubClient(number=True),
        ):
            with self.subTest(client=client.labels, number=client.number):
                packet = collect_github_input(client, CONFIG, NOW)
                self.assert_guarded(packet)
                self.assertIsNone(packet["evidence"])

        # No extrapolar heartbeat ni autoridad desde updated_at.
        stale = self.project([
            reservation(),
            state(updated_at="2026-10-02T03:30:00Z"),
        ])
        self.assertEqual(stale.authority, "unchanged")
        self.assertIn("state_stale", stale.reasons)
        self.assertEqual(stale.presence["sessions"], [])
        self.assertEqual(stale.presence["capacity"]["freshness"], "unknown")

    def test_sin_datos_reales(self):
        # Bloquea salidas de red, shell y mutaciones incluso en la rama
        # feliz. El cliente es memoria local y los IDs son sintéticos.
        def forbidden(*_args, **_kwargs):
            raise AssertionError("I/O externo prohibido en cobertura offline")

        with patch.object(socket, "create_connection", forbidden), \
             patch.object(request, "urlopen", forbidden), \
             patch.object(http.client, "HTTPSConnection", forbidden), \
             patch.object(subprocess, "run", forbidden):
            client = FixtureGitHubClient()
            packet = collect_github_input(client, CONFIG, NOW)
            self.assertIsNotNone(packet["evidence"])
            self.assert_guarded(packet)
            decision, plan = evaluate_runtime(
                CONFIG, packet["guard"], packet["evidence"], {},
            )
            self.assertEqual(decision.authority, "unchanged")
            self.assertEqual(plan.close, ())
            self.assertEqual(self.project([reservation()]).status, "UNKNOWN")

    def test_gate_validar_presente(self):
        # AC-04: GitHub Validar success se comprueba SOLO en GitHub
        # para el HEAD definitivo. Esta regresión garantiza que el
        # fallback del core no atribuye ALLOW a entrada faltante.
        blocked, plan = evaluate_runtime(CONFIG, None, None, {})
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertEqual(blocked.authority, "unchanged")
        self.assertEqual(plan.authority, "unchanged")
        self.assertEqual(plan.close, ())


if __name__ == "__main__":
    unittest.main()
