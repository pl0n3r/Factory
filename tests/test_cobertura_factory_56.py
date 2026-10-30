"""Factory #1847: contratos reales de roles y Sonar CE con evidencias sintéticas.

Solo invoca parsers, clasificadores, validadores y reconciliación pura con un
adaptador de Issues de memoria. No ejecuta workflows, GitHub, shell ni Sonar.
No inspecciona docs/matriz-cobertura*.md ni declara recepción de datos reales.
"""
from __future__ import annotations

from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request as urllib_request

from scripts import roles_kit as rk
from test_sonar_superseded_ce import (
    FakeIssues, NOW, OLD_SHA, NEW_SHA, SUPERSEDED, ce_signal,
    contract, snapshot, sonar_watch,
)

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "agentes" / "roles"


def role_context(*, body=""):
    return {
        "title": "Regresión sintética de un parser",
        "body": body,
        "files": ["tests/ejemplo_prueba.py"],
        "labels": ["rol: ingenieria-software", "rol: qa", "tipo: pruebas"],
    }


def role_body():
    names = ("ingenieria-software", "qa")
    checked = []
    for slug in names:
        profile = (ROLES / f"{slug}.md").read_text(encoding="utf-8")
        checked.extend(f"- [x] {line}" for line in rk.parse_checklist(profile))
    return (
        "Rol(es): ingenieria-software, qa\n"
        "Rol primario: ingenieria-software\n"
        + "\n".join(checked)
    )


def sonar_case(message):
    data = snapshot()
    data["ce_task"] = {"status": "FAILED", "error_message": message}
    return data


def reconcile(data, issues, *, observed_at=NOW):
    return sonar_watch.sync_project(
        contract=contract(),
        snapshot=data,
        observed_at=observed_at,
        project_ref="pl0n3r/Condor",
        origin_ref="sonar:condor",
        origin_url="https://sonarcloud.io/project/overview?id=pl0n3r_Condor",
        issues=issues,
    )


class CoberturaFactory56Tests(unittest.TestCase):
    def test_contrato_principal(self):
        # roles-profesionales L3: etiquetas ES/EN derivadas del catálogo real.
        catalog = rk.load_catalog()
        self.assertGreaterEqual(len(catalog), 16)
        for slug in ("ingenieria-software", "qa"):
            self.assertIn(catalog[slug]["label_es"], rk.labels_for(catalog, "es"))
            self.assertIn(catalog[slug]["label_en"], rk.labels_for(catalog, "en"))

        # L9: forma de declaración consumida por el parser real.
        body = role_body()
        self.assertEqual(
            rk.declared_roles(body), ["ingenieria-software", "qa"]
        )
        self.assertEqual(
            rk.single_role(body, "Rol primario"), "ingenieria-software"
        )

        # L29-U1: contexto de evento por JSON acotado, no evaluado como código.
        candidate = role_context(body=body)
        parsed = rk.parse_context(json.dumps(candidate))
        self.assertEqual(parsed["files"], ["tests/ejemplo_prueba.py"])

        # L30-U1: clasificación determinista y validación explicable.
        required, risks = rk.classify(parsed, catalog)
        self.assertEqual(required, ["ingenieria-software", "qa"])
        self.assertEqual(risks, set())
        self.assertEqual(rk.classify(parsed, catalog), (required, risks))
        result = rk.validate_pr(parsed, catalog, ROLES, "es")
        self.assertEqual(result["declared"], required)
        self.assertEqual(result["risks"], [])

        # sonar-superseded-ce L3/L7/L10/L11/L12/L13:
        # mensaje CE canónico con dos SHA exactos reconoce obsolescencia.
        signal = ce_signal(sonar_case(SUPERSEDED))
        self.assertEqual(signal["status"], "PASS")
        self.assertEqual(signal["reason"], "ce_task_superseded_by_newer_report")
        self.assertEqual(signal["freshness"]["state"], "CURRENT")
        self.assertIn(OLD_SHA, signal["details"]["error_message"])
        self.assertIn(NEW_SHA, signal["details"]["error_message"])
        self.assertIn("a newer report has already been processed",
                      signal["details"]["error_message"])
        self.assertIn("processing older reports is not supported",
                      signal["details"]["error_message"])

        # L15: el watcher real cierra la incidencia AUTO anterior
        # únicamente si el observable CE está vigente y es PASS.
        issues = FakeIssues()
        operations = reconcile(sonar_case(SUPERSEDED), issues)
        self.assertEqual(issues.rows[0]["state"], "closed")
        self.assertIn({"action": "closed", "signal": "ce_task"}, operations)
        self.assertFalse(any(call[0] == "create" for call in issues.calls))

    def test_falla_cerrado(self):
        catalog = rk.load_catalog()
        good = role_context(body=role_body())

        # roles L29-U1: rechazar tamaños excesivos y formas ambiguas.
        with self.assertRaises(rk.RoleError):
            rk.parse_context("x" * (rk.MAX_CONTEXT + 1))
        with self.assertRaises(rk.RoleError):
            rk.parse_context('{"body":[],"labels":[],"files":[],"title":""}')

        # L29-U2: el CLI NO permite inyectar paths de catálogo/contexto.
        with patch("sys.argv", ["roles_kit.py", "suggest", "--catalog", "/tmp/otro.json"]):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as err:
                    rk.main()
        self.assertEqual(err.exception.code, 2)

        # L30-U2: texto remoto nunca se evalúa; requiere roles y etiquetas.
        missing_label = deepcopy(good)
        missing_label["labels"].remove("rol: qa")
        with self.assertRaisesRegex(rk.RoleError, "etiquetas"):
            rk.validate_pr(missing_label, catalog, ROLES, "es")
        missing_checklist = role_context(
            body="Rol(es): ingenieria-software, qa\n"
                 "Rol primario: ingenieria-software"
        )
        with self.assertRaisesRegex(rk.RoleError, "Checklist"):
            rk.validate_pr(missing_checklist, catalog, ROLES, "es")
        hostile = role_context(body="__import__('os').system('echo pwned')")
        self.assertEqual(rk.declared_roles(hostile["body"]), [])
        with self.assertRaisesRegex(rk.RoleError, "Rol.es."):
            rk.validate_pr(hostile, catalog, ROLES, "es")

        # Sonar L7 y L10-U1..L13-U1: mutaciones individuales no son
        # reporte superseded. Incluir SHA ausente, frase falsa, datos extra.
        invalid_messages = (
            SUPERSEDED.replace("a newer report has already been processed",
                               "a newer report might have been processed"),
            SUPERSEDED.replace("processing older reports is not supported",
                               "processing older reports is supported"),
            SUPERSEDED.replace(OLD_SHA, "not-a-sha"),
            SUPERSEDED.replace(NEW_SHA, "bad-hash"),
            SUPERSEDED + " extra trace",
            "error prefix " + SUPERSEDED,
            "Compute Engine task failed for an unrelated reason.",
        )
        for message in invalid_messages:
            with self.subTest(message=message[:55]):
                signal = ce_signal(sonar_case(message))
                self.assertEqual(signal["status"], "FAIL")
                self.assertEqual(signal["reason"], "ce_task_failed")

        # L15: fallo distinto no habilita cierre automático.
        issues = FakeIssues()
        reconcile(sonar_case(invalid_messages[-1]), issues)
        self.assertEqual(issues.rows[0]["state"], "open")

        # L15: incluso un superseded canónico, si está stale, no cierra.
        stale = FakeIssues()
        reconcile(sonar_case(SUPERSEDED), stale,
                  observed_at="2026-10-09T00:10:00Z")
        self.assertEqual(stale.rows[0]["state"], "open")

    def test_sin_datos_reales(self):
        # L21: los contratos son declarativos; las llamadas prueban que
        # no necesitan red, servidor Sonar ni API GitHub.
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("red no permitida")):
            with patch.object(urllib_request, "urlopen",
                              side_effect=AssertionError("Sonar no permitido")):
                catalog = rk.load_catalog()
                ctx = role_context(body=role_body())
                self.assertEqual(
                    rk.validate_pr(ctx, catalog, ROLES, "es")["risks"], []
                )
                raw = sonar_case(SUPERSEDED)
                self.assertEqual(ce_signal(raw)["status"], "PASS")
                issues = FakeIssues()
                reconcile(raw, issues)
                self.assertEqual(issues.rows[0]["state"], "closed")
                self.assertEqual(
                    {call[0] for call in issues.calls},
                    {"update", "comment_once"},
                )
        # No hay escritura remota ni secretos y el error genérico sigue FAIL.
        raw = sonar_case("CE failure, no approved superseding report")
        self.assertEqual(ce_signal(raw)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
