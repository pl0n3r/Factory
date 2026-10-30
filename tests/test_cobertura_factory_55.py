#!/usr/bin/env python3
"""Factory #1846: cobertura conductual de Risk Compiler y roles del kit.

Ejecuta módulos reales con entradas sintéticas, sin I/O externo. El SHA real
resuelto por @v1 requiere evidencia externa de GitHub (clasificación B).
No confunde una sugerencia de rollback con autorización administrativa.
"""
from __future__ import annotations

from copy import deepcopy
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib import request

from intelligence.project_dna import discover_project_dna
from intelligence.risk_compiler import (
    BASE_CONTROLS,
    MEDIUM_CONTROLS,
    HIGH_CONTROLS,
    RiskCompilerError,
    compile_risk,
    validate_risk_evidence,
)
from scripts.roles_kit import (
    ROLES_DIR,
    RoleError,
    classify,
    compile_team,
    labels_for,
    load_catalog,
    parse_checklist,
    validate_pr,
)


def _dna(*, sparse=False):
    if sparse:
        return discover_project_dna(
            paths=["package.json"],
            manifests={"package.json": {"dependencies": {"fastify": "^5"}}},
            capabilities=["api"],
        )
    return discover_project_dna(
        paths=[
            "package.json", ".github/workflows/ci.yml", "vercel.json",
            "database/schema.sql", ".sentryclirc",
        ],
        manifests={"package.json": {
            "dependencies": {"fastify": "^5", "@sentry/node": "^9"},
        }},
        capabilities=["api", "auth"],
    )


def _task(*, kind="docs", surfaces=None, **signals):
    complete = {
        "production": False,
        "destructive": False,
        "migration": False,
        "touches_auth": False,
        "external_integration": False,
    }
    complete.update(signals)
    return {
        "id": "fixture/factory-1846",
        "title": "Prueba sintética de riesgo",
        "change_type": kind,
        "surfaces": surfaces if surfaces is not None else ["docs"],
        "signals": complete,
    }


def _role_context(catalog, *, risk=False, language="es"):
    roles = ["ingenieria-software", "qa"]
    if risk:
        roles.append("seguridad")
    label_key = "label_en" if language == "en" else "label_es"
    lines = [
        "Rol(es): " + ", ".join(roles),
        "Rol primario: ingenieria-software",
    ]
    if risk:
        lines.append("Revisión cruzada: qa")
    for role in roles:
        profile = (ROLES_DIR / (role + ".md")).read_text(encoding="utf-8")
        for item in parse_checklist(profile):
            lines.append("- [x] " + item)
    return {
        "title": "Cambio aislado",
        "body": "\n".join(lines),
        "files": ["security/auth.py"] if risk else ["tests/example.py"],
        "labels": ["tipo: pruebas"] + [catalog[role][label_key] for role in roles],
    }


class CoberturaFactory55Tests(unittest.TestCase):
    """AC-01..04: comprobar comportamiento, nunca solo presencia documental."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def test_contrato_principal(self):
        # risk-compiler L12/13/16: dimensiones independientes; máximo,
        # nunca promedio. Señales operativas y Project DNA importan.
        dna = _dna()
        low = compile_risk(project_dna=dna, task=_task())
        medium = compile_risk(
            project_dna=dna, task=_task(kind="code", surfaces=["api"]),
        )
        high = compile_risk(
            project_dna=dna,
            task=_task(kind="security", surfaces=["auth"], touches_auth=True),
        )
        self.assertEqual([low["risk"], medium["risk"], high["risk"]],
                         ["low", "medium", "high"])
        self.assertEqual(low["dimensions"]["change"], "low")
        self.assertEqual(medium["dimensions"]["surface"], "medium")
        self.assertEqual(high["dimensions"]["signals"], "high")
        self.assertEqual(high["risk"], max(
            high["dimensions"].values(),
            key={"low": 0, "medium": 1, "high": 2}.__getitem__,
        ))
        self.assertEqual(high["dimensions"]["project_context"], "low")
        self.assertIn("task.signals.touches_auth", {
            item["source"] for item in high["trace"]
        })

        # risk-compiler L23..26: cada señal preserva procedencia, riesgo y
        # razón de forma estructurada, también en los controles.
        for row in high["trace"]:
            self.assertEqual(set(row), {"signal", "source", "risk", "reason"})
            self.assertTrue(all(isinstance(v, str) and v for v in row.values()))
        sources = {row["source"] for row in high["trace"]}
        for control in high["controls"]:
            self.assertTrue(control["sources"])
            self.assertTrue(set(control["sources"]).issubset(sources))
        self.assertTrue(high["blast_radius"])

        # risk-compiler L36..41: niveles acumulativos y controles adicionales.
        low_targets = {c["target"] for c in low["controls"]}
        med_targets = {c["target"] for c in medium["controls"]}
        high_targets = {c["target"] for c in high["controls"]}
        self.assertEqual(low_targets, set(BASE_CONTROLS))
        self.assertEqual(med_targets, low_targets | set(MEDIUM_CONTROLS))
        self.assertEqual(high_targets, med_targets | set(HIGH_CONTROLS))
        self.assertTrue(low_targets < med_targets < high_targets)

        # roles-profesionales L10/L11/L14/L14-U2: clasificación del archivo,
        # declaración de rol primario y checklist completo evaluado por motor.
        normal = _role_context(self.catalog)
        required, risks = classify(normal, self.catalog)
        self.assertEqual(set(required), {"ingenieria-software", "qa"})
        self.assertFalse(risks)
        actual = validate_pr(normal, self.catalog, ROLES_DIR, "es")
        self.assertEqual(set(actual["declared"]), set(required))
        self.assertFalse(actual["risks"])
        self.assertEqual(compile_team(normal, self.catalog)["primary"],
                         "ingenieria-software")

        # roles-profesionales L12: riesgo de seguridad requiere revisión
        # independiente por otro rol permitido, no solo declararla.
        secured = _role_context(self.catalog, risk=True)
        validated = validate_pr(secured, self.catalog, ROLES_DIR, "es")
        self.assertIn("security", validated["risks"])
        self.assertIn("seguridad", validated["required"])
        self.assertNotEqual(compile_team(secured, self.catalog)["primary"], "qa")

        # roles-profesionales L18/L19: el mismo catálogo cambia realmente
        # las etiquetas verificadas en proyectos ES y EN.
        english = _role_context(self.catalog, language="en")
        self.assertEqual(set(validate_pr(english, self.catalog, ROLES_DIR, "en")["declared"]),
                         {"ingenieria-software", "qa"})
        self.assertIn("rol: qa", labels_for(self.catalog, "es"))
        self.assertIn("role: qa", labels_for(self.catalog, "en"))

    def test_falla_cerrado(self):
        # risk-compiler L52: incertidumbre crítica o contexto ausente
        # nunca reduce riesgo ni controles de seguridad.
        for field in ("production", "destructive", "migration", "touches_auth"):
            with self.subTest(signal=field):
                unknown = compile_risk(
                    project_dna=_dna(),
                    task=_task(kind="code", surfaces=["api"], **{field: "unknown"}),
                )
                self.assertEqual(unknown["risk"], "high")
                self.assertFalse(unknown["context_complete"])
                self.assertIn("task.signals." + field,
                              unknown["unknown_critical_signals"])
                self.assertIn("security:scan", {
                    control["target"] for control in unknown["controls"]
                })
        sparse = compile_risk(
            project_dna=_dna(sparse=True),
            task=_task(kind="code", surfaces=["api"]),
        )
        self.assertEqual(sparse["risk"], "high")
        self.assertFalse(sparse["context_complete"])
        self.assertIn("project_dna.hosting", sparse["unknown_critical_signals"])

        # Entrada ambigua (señal ausente, campo extra) no genera contrato.
        broken = _task()
        del broken["signals"]["production"]
        with self.assertRaises(RiskCompilerError):
            compile_risk(project_dna=_dna(), task=broken)
        broken = _task()
        broken["signals"]["production"] = "maybe"
        with self.assertRaises(RiskCompilerError):
            compile_risk(project_dna=_dna(), task=broken)

        # roles-profesionales L10/11/12/14-U2: ausencia de rol, checklist,
        # etiqueta o revisión cruzada es error, no una aprobación ficticia.
        normal = _role_context(self.catalog)
        cases = [
            ("sin_roles", normal["body"].replace(
                "Rol(es): ingenieria-software, qa", "Roles no declarados")),
            ("sin_primario", normal["body"].replace(
                "Rol primario: ingenieria-software", "")),
            ("sin_checklist", normal["body"].replace("- [x] ", "- [ ] ", 1)),
        ]
        for name, body in cases:
            with self.subTest(name=name), self.assertRaises(RoleError):
                validate_pr({**normal, "body": body},
                            self.catalog, ROLES_DIR, "es")
        with self.assertRaises(RoleError):
            validate_pr({**normal, "labels": ["tipo: pruebas"]},
                        self.catalog, ROLES_DIR, "es")
        secured = _role_context(self.catalog, risk=True)
        for reviewer in ("", "ingenieria-software"):
            with self.subTest(reviewer=reviewer), self.assertRaises(RoleError):
                validate_pr({
                    **secured,
                    "body": secured["body"].replace("Revisión cruzada: qa",
                                                    "Revisión cruzada: " + reviewer),
                }, self.catalog, ROLES_DIR, "es")
        with self.assertRaises(RoleError):
            validate_pr(_role_context(self.catalog, language="en"),
                        self.catalog, ROLES_DIR, "es")

    def test_sin_datos_reales(self):
        # No hay cuentas reales, red, procesos o despliegues; únicamente
        # sintéticos y acceso de lectura al catálogo local del repositorio.
        def forbidden(*_args, **_kwargs):
            raise AssertionError("I/O externo no autorizado")
        with patch.object(socket, "create_connection", forbidden), \
             patch.object(request, "urlopen", forbidden), \
             patch.object(subprocess, "run", forbidden):
            data = _task(kind="security", surfaces=["auth"], touches_auth=True)
            result = compile_risk(project_dna=_dna(), task=data)
            self.assertEqual(result["risk"], "high")
            context = _role_context(self.catalog)
            self.assertIn("qa", validate_pr(
                context, self.catalog, ROLES_DIR, "es")["declared"])
        self.assertEqual(data["id"], "fixture/factory-1846")

    def test_gate_validar_presente(self):
        # La compuerta GitHub Validar se acredita externamente en CI exact-HEAD;
        # aquí se comprueba que su evidencia de riesgo no puede falsificarse.
        dna, task = _dna(), _task(kind="code", surfaces=["api"])
        genuine = compile_risk(project_dna=dna, task=task)
        self.assertEqual(
            validate_risk_evidence(project_dna=dna, task=task, result=genuine),
            genuine,
        )
        fake = deepcopy(genuine)
        fake["risk"] = "low"
        with self.assertRaises(RiskCompilerError):
            validate_risk_evidence(project_dna=dna, task=task, result=fake)
        for invalid in (None, {}, {"conclusion": "success"}):
            with self.subTest(invalid=invalid), self.assertRaises(RiskCompilerError):
                validate_risk_evidence(project_dna=dna, task=task, result=invalid)


if __name__ == "__main__":
    unittest.main()
