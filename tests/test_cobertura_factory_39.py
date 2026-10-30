#!/usr/bin/env python3
"""Factory #1830: funciones reales con fixtures enteramente sintéticos."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from intelligence.factory_status import COMMITTED_TANDA2_EVIDENCE, derive_factory_status
from intelligence.project_dna import (
    ProjectDnaError, discover_project_dna, validate_project_dna,
)
from scripts.issue_contract_preflight import (
    IssueContractPreflightError, evaluate_issue_body,
)
from scripts.orquestador_kit import (
    PlannedTask, build_task_marker, parallel_compatibility_evidence,
    reservation_blockers,
)

ROOT = Path(__file__).resolve().parents[1]


def planned_issue(number, path, *, state="estado: disponible",
                  actor="pl0n3r", depends_on=()):
    task = PlannedTask(
        key=f"TASK_{number}", title=f"Test {number}", owner=actor,
        paths=(path,), depends_on=(),
    )
    return {
        "number": number, "state": "open", "state_reason": None,
        "labels": [{"name": state}],
        "body": build_task_marker(
            epic=1082, task=task, order=number, roles=["qa"],
            dependency_issues=list(depends_on),
        ),
    }


def synthetic_body():
    acceptance = {
        "version": 1, "criteria": [{
            "id": "AC-01", "kind": "test", "target":
            "tests/test_cobertura_factory_39.py::"
            "CoberturaFactory39Tests::test_contrato_principal",
        }],
    }
    task = {
        "version": 1, "epic": 1082, "task_key": "CONTRATO_TEST",
        "order": 1, "owner": "pl0n3r", "roles": ["qa"],
        "depends_on": [], "paths": ["tests/synthetic_contract.py"],
    }
    return (
        "### Contexto\nCaso sintético.\n\n"
        "### Alcance\nContrato offline.\n\n"
        "### Fuera de alcance\nNo hay tráfico real.\n\n"
        "### Criterios de aceptación\n- [ ] [AC-01] Ejecutar prueba local.\n\n"
        "### Contrato ejecutable\n<!-- factory-acceptance "
        + json.dumps(acceptance, separators=(",", ":")) + " -->\n\n"
        "### Rutas reclamadas\n- tests/synthetic_contract.py\n"
        "<!-- factory-plan-task "
        + json.dumps(task, separators=(",", ":")) + " -->\n"
    )


def synthetic_dna(*, reverse=False):
    paths = [
        "package.json", "composer.json", "pyproject.toml",
        ".github/workflows/ci.yml", "prisma/schema.prisma", ".sentryclirc",
    ]
    if reverse:
        paths = list(reversed(paths)) + ["package.json"]
    return discover_project_dna(
        paths=paths,
        manifests={
            "package.json": {"dependencies": {"react": "^19", "stripe": "^18"}},
            "composer.json": {"require": {"symfony/framework-bundle": "^7"}},
            "pyproject.toml": {"project": {"dependencies": ["django>=5"]}},
        },
        capabilities=["web", "api"],
    )


class CoberturaFactory39Tests(unittest.TestCase):
    """AC-01..04: jamás consultar GitHub ni leer la matriz de cobertura."""

    def test_contrato_principal(self):
        # principios:L31-U1 — aceptación verdadera del código existente.
        contract = evaluate_issue_body(synthetic_body())
        self.assertTrue(contract["valid"])
        self.assertEqual(contract["paths"], ["tests/synthetic_contract.py"])
        self.assertEqual(contract["criteria"][0]["target"], (
            "tests/test_cobertura_factory_39.py::"
            "CoberturaFactory39Tests::test_contrato_principal"
        ))
        self.assertRegex(contract["acceptance_sha256"], r"^[0-9a-f]{64}$")

        # principios:L7-U1/U2 — claims disjuntos, comprobación ejecutable.
        active = planned_issue(10, "src/payment.py", state="estado: reservado")
        other = planned_issue(11, "docs/report.md")
        self.assertEqual(
            reservation_blockers(other, [active, other], "pl0n3r", {}), []
        )
        evidence = parallel_compatibility_evidence(other, [active, other])
        self.assertEqual(len(evidence), 1)
        self.assertIn("claims disjuntos", evidence[0])

        # principios:L43-U3 — recovery NO libera un claim ya reservado.
        recovering = planned_issue(
            12, "src/payment.py", state="estado: requiere recuperación",
        )
        candidate = planned_issue(13, "src/payment.py")
        self.assertTrue(any(
            "colisión" in reason for reason in reservation_blockers(
                candidate, [recovering, candidate], "pl0n3r", {},
            )
        ))

        # principios:L39-U1 — evidencia incompleta jamás produce GO.
        missing = derive_factory_status(COMMITTED_TANDA2_EVIDENCE[:-1])
        self.assertEqual(missing["tanda2"], "UNKNOWN")
        self.assertEqual(missing["tanda3"], "BLOQUEADA")
        self.assertFalse(missing["tanda3_active"])
        self.assertTrue(missing["reasons"])

        # project-dna:L11/12/13/14/26/30/31 — detección REAL.
        dna = synthetic_dna()
        self.assertEqual(dna["stack"], ["node", "php", "python"])
        self.assertEqual(dna["frameworks"], ["django", "react", "symfony"])
        self.assertEqual(dna["data"], ["prisma"])
        self.assertEqual(dna["ci"], ["github-actions"])
        self.assertEqual(dna["integrations"], ["sentry", "stripe"])
        self.assertEqual(dna["capabilities"], ["api", "web"])
        self.assertEqual(dna["signals"]["manifests"],
                         ["composer.json", "package.json", "pyproject.toml"])
        self.assertEqual(validate_project_dna(dna), dna)

    def test_falla_cerrado(self):
        # Entradas de aceptación falsas, permisos y claims incompatibles.
        for invalid in (
            synthetic_body().replace("### Contexto", "### Context"),
            synthetic_body().replace('"task_key":"CONTRATO_TEST"',
                                     '"task_key":"invalid"'),
            synthetic_body().replace("tests/synthetic_contract.py",
                                     "../private/secrets.txt"),
        ):
            with self.subTest(kind="preflight"):
                with self.assertRaises(IssueContractPreflightError):
                    evaluate_issue_body(invalid)

        active = planned_issue(10, "src/a.py", state="estado: reservado")
        same = planned_issue(11, "src/a.py")
        self.assertTrue(any(
            "colisión" in x for x in reservation_blockers(
                same, [active, same], "pl0n3r", {},
            )
        ))
        foreign = planned_issue(12, "docs/x.md", actor="other-owner")
        self.assertTrue(any(
            "no para" in x for x in reservation_blockers(
                foreign, [foreign], "pl0n3r", {},
            )
        ))
        dependency = planned_issue(13, "docs/y.md", depends_on=(9,))
        self.assertTrue(any(
            "dependencias no completadas" in x for x in reservation_blockers(
                dependency, [dependency], "pl0n3r",
                {9: {"state": "open", "state_reason": None}},
            )
        ))

        for paths in (["/secrets"], ["a/../passwd"], "not-a-list"):
            with self.subTest(paths=paths), self.assertRaises(ProjectDnaError):
                discover_project_dna(paths=paths)
        with self.assertRaises(ProjectDnaError):
            discover_project_dna(paths=["package.json"], manifests={
                "package.json": ["malformed"],
            })
        with self.assertRaises(ProjectDnaError):
            discover_project_dna(paths=["package.json"], capabilities=["", "api"])
        altered = copy.deepcopy(synthetic_dna())
        altered["integrations"] = ["stripe"]
        with self.assertRaisesRegex(ProjectDnaError, "fingerprint"):
            validate_project_dna(altered)

    def test_sin_datos_reales(self):
        # Fingerprint no cambia por orden/deduplicación y no infiere servicios.
        self.assertEqual(synthetic_dna(), synthetic_dna(reverse=True))
        empty = discover_project_dna(paths=[
            "README.md", "docs/stripe-integration.md",
            "src/sentry_integration.php",
        ])
        for field in ("stack", "frameworks", "data", "ci", "hosting",
                      "integrations", "capabilities"):
            self.assertEqual(empty[field], "unknown", field)
        self.assertNotIn("credentials", synthetic_dna())
        self.assertNotIn("health", synthetic_dna())
        body = synthetic_body()
        baseline = evaluate_issue_body(body)
        with_unrelated_whitespace = evaluate_issue_body(body + "\n")
        self.assertEqual(baseline, with_unrelated_whitespace)

    def test_gate_validar_presente(self):
        # No suplanta el check terminal exact-HEAD que publica GitHub.
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("    name: Validar\n", ci)
        self.assertIn("name: Validar contrato", ci)


if __name__ == "__main__":
    unittest.main()
