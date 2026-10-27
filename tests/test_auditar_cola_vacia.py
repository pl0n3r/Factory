#!/usr/bin/env python3
"""Contrato F1082 del auditor de cola: únicamente snapshots inventados."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch
from io import StringIO
from pathlib import Path

from scripts import auditar_cola_vacia as auditor


def issue(number, kind="leaf", status="planificado",
          parent=None, blocker=None):
    return {
        "number": number,
        "kind": kind,
        "status": status,
        "parent": parent,
        "blocker": blocker,
    }


def fixture(*issues):
    return {"version": 1, "source": "fixture",
            "complete": True, "issues": list(issues)}


class F1082AuditarColaTests(unittest.TestCase):
    def test_contrato_principal(self):
        snapshot = fixture(
            issue(10, "roadmap", "planificado"),
            issue(20, "container", "planificado", 10),
            issue(30, "leaf", "bloqueado", 20, "dependency"),
            issue(40, "roadmap", "planificado"),
            issue(50, "container", "planificado", 40),
            issue(60, "leaf", "planificado"),
        )
        result = auditor.audit(snapshot)
        self.assertEqual(result["state"], "COLA_VACIA_CON_PENDIENTES")
        self.assertTrue(result["action_required"])
        self.assertEqual(result["available_count"], 0)
        self.assertEqual(result["pending_count"], 6)
        findings = {(x["issue"], x["reason"], x["action"])
                    for x in result["findings"]}
        self.assertIn((40, "ROADMAP_SIN_HOJAS", "DESCOMPONER_HOJAS"), findings)
        self.assertIn((50, "CONTENEDOR_SIN_HOJAS", "MATERIALIZAR_HOJAS"), findings)
        self.assertIn((30, "HOJA_BLOQUEADA", "RESOLVER_DEPENDENCIA"), findings)
        self.assertIn((60, "HOJA_PLANIFICADA", "VALIDAR_ELEGIBILIDAD"), findings)
        self.assertNotIn((10, "ROADMAP_SIN_HOJAS", "DESCOMPONER_HOJAS"), findings)
        reordered = fixture(*reversed(snapshot["issues"]))
        self.assertEqual(result, auditor.audit(reordered))
        with_available = fixture(*snapshot["issues"],
                                 issue(70, "leaf", "disponible"))
        self.assertEqual(auditor.audit(with_available)["state"],
                         "COLA_DISPONIBLE")
        finished = fixture(issue(1, "leaf", "completado"))
        self.assertEqual(auditor.audit(finished)["state"],
                         "SIN_TRABAJO_PENDIENTE")

    def test_falla_cerrado(self):
        good = fixture(issue(1, "roadmap"), issue(2, parent=1))
        bad = [
            None, [], {}, {"version": 1, "issues": []},
            {**good, "complete": False}, {**good, "source": "github"},
            {**good, "issues": [issue(1), issue(1)]},
            {**good, "issues": [issue(True)]},
            {**good, "issues": [issue(2, parent=99)]},
            {**good, "issues": [issue(1, parent=2), issue(2, parent=1)]},
            {**good, "issues": [issue(1, status="maybe")]},
            {**good, "issues": [issue(1, status="bloqueado")]},
            {**good, "issues": [issue(1, status="completado", blocker="claims")]},
            {**good, "issues": [issue(1, "leaf"), issue(2, parent=1)]},
            {**good, "issues": [issue(1, kind="mystery")]},
            {**good, "issues": [dict(issue(1), email="x@example.test")]},
        ]
        for candidate in bad:
            with self.subTest(candidate=repr(candidate)[:100]):
                result = auditor.audit(candidate)
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertFalse(result["action_required"])
                self.assertIsNone(result["available_count"])
                self.assertEqual(result["findings"], [])
        for raw in (
            '{"version":1,"version":1,"source":"fixture","complete":true,"issues":[]}',
            '{"version": NaN,"source":"fixture","complete":true,"issues":[]}',
            '{"version":1,"source":"fixture","complete":true,"issues":[}',
            "x" * (auditor.MAX_BYTES + 1),
        ):
            with self.subTest(raw=raw[:20]):
                self.assertEqual(auditor.parse_fixture(raw)["state"], "UNKNOWN")

    def test_sin_datos_reales(self):
        script = (Path(__file__).resolve().parents[1]
                  / "scripts/auditar_cola_vacia.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "urllib", "socket", "subprocess",
                          "os.environ", "Authorization", "GITHUB_TOKEN",
                          "api.github.com", "open(", "write_text(", "input("):
            self.assertNotIn(forbidden, script)
        synthetic = fixture(issue(100, "leaf", "bloqueado",
                                  blocker="human_gate"))
        output = json.dumps(auditor.audit(synthetic))
        self.assertIn("VERIFICAR_PUERTA_HUMANA", output)
        self.assertNotIn("email", output)
        self.assertNotIn("tenant", output)
        leaked = copy.deepcopy(synthetic)
        leaked["issues"][0]["name"] = "persona privada"
        result = auditor.audit(leaked)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertNotIn("persona privada", json.dumps(result))

    def test_estados_unknown_explicitos(self):
        pending = fixture(issue(1, "roadmap", "planificado"))
        self.assertEqual(auditor.audit(pending)["state"],
                         "COLA_VACIA_CON_PENDIENTES")
        for reason, action in (
            ("dependency", "RESOLVER_DEPENDENCIA"),
            ("claims", "RESOLVER_COLISION_CLAIMS"),
            ("human_gate", "VERIFICAR_PUERTA_HUMANA"),
            ("technical", "REPARAR_BLOQUEO_TECNICO"),
        ):
            with self.subTest(reason=reason):
                report = auditor.audit(fixture(issue(1, status="bloqueado",
                                                    blocker=reason)))
                self.assertEqual(report["findings"][0]["action"], action)
        ambiguous = fixture(issue(1, status="bloqueado", blocker="unknown"))
        self.assertEqual(auditor.audit(ambiguous)["state"], "UNKNOWN")
        self.assertEqual(auditor.parse_fixture("not-json")["state"], "UNKNOWN")
        with (
            patch("sys.stdin", StringIO("not-json")),
            patch("sys.stdout", new_callable=StringIO) as capture,
        ):
            self.assertEqual(auditor.main(), 2)
        self.assertEqual(json.loads(capture.getvalue())["state"], "UNKNOWN")
        with (
            patch("sys.stdin", StringIO(json.dumps(pending))),
            patch("sys.stdout", new_callable=StringIO) as capture,
        ):
            self.assertEqual(auditor.main(), 0)
        self.assertEqual(json.loads(capture.getvalue())["state"],
                         "COLA_VACIA_CON_PENDIENTES")


if __name__ == "__main__":
    unittest.main()
