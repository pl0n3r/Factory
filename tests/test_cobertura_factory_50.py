"""Factory #1841: evidencia de comportamiento real, 100 % sintética y offline.

No inspecciona la matriz ni reclama evidencia de publicación/hosting real.
"""
from __future__ import annotations

import copy
import json
import socket
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts import release_bootstrap as bootstrap
from scripts import release_window as release
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch
from seguridad import resiliencia


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 40
NEW_SHA = "b" * 40
VERSION = "1.0.44"


def synthetic_switch(state: str = "RUNNING") -> dict[str, object]:
    marker = json.dumps({"version": 1, "state": state, "owner": "pl0n3r"})
    return {
        "number": 767,
        "url": "https://api.github.com/repos/pl0n3r/Factory/issues/767",
        "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
        "state": "closed",
        "user": {"login": "pl0n3r"},
        "body": f"<!-- factory-unattended-kill-switch {marker} -->",
    }


def synthetic_manifest() -> dict[str, object]:
    return {
        "version": 2,
        "project": "pl0n3r/Factory",
        "execution_mechanisms": {
            "ci": "github-token:ephemeral",
            "observer": "github-token:ephemeral",
            "deploy": "hostinger:git",
        },
        "cross_repo_write": {"required_mechanism": "github-app"},
        "checks": {
            item: {"verified_at": "2026-10-29T11:00:00Z", "evidence_ref": "fixture/synthetic-check-42"}
            for item in ("repo_backup", "secrets_escrow", "token_rotation", "restore_drill")
        },
    }


class CoberturaFactory50Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        # release-runbook L5-U1: la autorización de continuar exige kill switch real.
        switch = evaluate_unattended_kill_switch(synthetic_switch())
        self.assertEqual((switch.state, switch.global_pause), ("RUNNING", False))

        # release-runbook L45-U1, L61-U1: ventana, target SHA y decisión no heredada.
        gate = release._render_gate(VERSION, SHA, NOW, source_issue=901)
        parsed, version, target = release._gate_from_body(gate["body"])
        self.assertEqual((version, target), (VERSION, SHA))
        self.assertEqual(parsed["category"], "factory-release")
        self.assertEqual(parsed["safe_default"], "B")
        window = release._window_from_body(gate["body"], SHA)
        self.assertIsNotNone(window)
        self.assertEqual(window["sha"], SHA)
        self.assertGreater(window["expires_at"], window["opened_at"])
        decision = release._decision_a([], release._gate_fingerprint(parsed))
        self.assertFalse(decision)

        # release-runbook L57-U1: SHA exacto y cuatro gates de bootstrap.
        checks = {name: "success" for name in bootstrap.REQUIRED_EXACT_MAIN_CHECKS}
        self.assertEqual(bootstrap._sha(SHA, "expected_sha"), SHA)
        self.assertIsNone(bootstrap._validate_latest_release_context(
            body=gate["body"], expected=SHA, current_version=VERSION,
            changed_files=[], exact_main_checks=checks,
        ))
        self.assertTrue(bootstrap._is_release_machinery_path("scripts/release_bootstrap.py"))

        # resiliencia-fabrica L11-U1, L12-U1, L12-U2, L14-U1 y L20-U1:
        # validar el esquema operativo v2 real, no solo citar el documento.
        self.assertIsNone(resiliencia.validate_manifest(synthetic_manifest(), now=NOW))

        # resiliencia-fabrica L16-U1: invocar el auditor real con YAML benigno.
        self.assertIsNone(resiliencia.audit_workflow(
            "name: Prueba sintetica\non:\n  push:\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"
        ))

    def test_falla_cerrado(self) -> None:
        # RUNNING no se deduce de evidencia incompleta o manipulada.
        for mutation in (
            lambda x: x.update({"state": "open"}),
            lambda x: x.update({"user": {"login": "otro"}}),
            lambda x: x.update({"body": x["body"] + x["body"]}),
        ):
            with self.subTest(mutation=mutation.__code__.co_firstlineno):
                candidate = synthetic_switch()
                mutation(candidate)
                self.assertTrue(evaluate_unattended_kill_switch(candidate).global_pause)
        self.assertTrue(evaluate_unattended_kill_switch(synthetic_switch("PAUSED")).global_pause)

        gate = release._render_gate(VERSION, SHA, NOW, source_issue=901)
        with self.assertRaises(release.ReleaseWindowError):
            release._window_from_body(gate["body"], NEW_SHA)
        with self.assertRaises(bootstrap.ReleaseBootstrapError):
            bootstrap._sha("no-es-sha", "expected_sha")
        checks = {name: "success" for name in bootstrap.REQUIRED_EXACT_MAIN_CHECKS}
        with self.assertRaises(bootstrap.ReleaseBootstrapError):
            bootstrap._validate_latest_release_context(
                body=gate["body"], expected=NEW_SHA, current_version=VERSION,
                changed_files=["scripts/release_bootstrap.py"], exact_main_checks=checks,
            )
        checks["codeql"] = "pending"
        with self.assertRaises(bootstrap.ReleaseBootstrapError):
            bootstrap._validate_latest_release_context(
                body=gate["body"], expected=SHA, current_version=VERSION,
                changed_files=[], exact_main_checks=checks,
            )
        # Un repair no crítico no cruza el freeze (release-runbook L61-U1).
        marker = '<!-- factory-release-freeze-exception {"version":1,"reason":"critical-repair","issue":901} -->'
        self.assertFalse(release._critical_exception(
            {"body": marker}, {"number": 901, "state": "open", "labels": [{"name": "prioridad: media"}]},
        ))

        baseline = synthetic_manifest()
        mutations = [
            {"version": 1},
            {"unexpected": True},
            {"execution_mechanisms": {**baseline["execution_mechanisms"], "ci": "github-token:persistent"}},
            {"execution_mechanisms": {**baseline["execution_mechanisms"], "observer": "github-token:persistent"}},
            {"execution_mechanisms": {**baseline["execution_mechanisms"], "deploy": "personal-pat"}},
            {"cross_repo_write": {"required_mechanism": "personal-pat"}},
            {"cross_repo_write": {"required_mechanism": "github-token"}},
            {"checks": {}},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                row = copy.deepcopy(baseline)
                row.update(mutation)
                with self.assertRaises(resiliencia.ValidationError):
                    resiliencia.validate_manifest(row, now=NOW)

        for unsafe in (
            "on: pull_request_target\n",
            "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n",
            "permissions: write-all\n",
        ):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(resiliencia.ValidationError):
                    resiliencia.audit_workflow(unsafe)

    def test_sin_datos_reales(self) -> None:
        # La evidencia tiene identidades, fechas y SHA sintéticos: nada externo.
        with patch.object(socket, "socket", side_effect=AssertionError("red prohibida")):
            decision = evaluate_unattended_kill_switch(synthetic_switch("PAUSED"))
            self.assertTrue(decision.global_pause)
            self.assertIsNone(resiliencia.validate_manifest(synthetic_manifest(), now=NOW))
            gate = release._render_gate(VERSION, SHA, NOW, source_issue=901)
            self.assertEqual(release._gate_from_body(gate["body"])[2], SHA)
        self.assertEqual(len(SHA), 40)
        self.assertNotIn("token", synthetic_manifest()["project"].lower())


if __name__ == "__main__":
    unittest.main()
