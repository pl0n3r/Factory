#!/usr/bin/env python3
"""Factory #1800: pruebas conductuales offline de coordinación, costos y cumplimiento.

Ejerce implementaciones reales con entradas sintéticas. No consulta la matriz
ni convierte un resultado local en certificación jurídica o evidencia live.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from metricas.costos import CostError, ci_trend, evaluate_pr
from scripts.coordinar_trabajo import (
    CoordinationError, STATUS_COMPLETED, close_pr_reservation,
    closing_issues, issue_from_branch, validate_pull,
)
from seguridad.cumplimiento import (
    ComplianceError, REQUIRED_EVIDENCE, main as compliance_main,
    validate_privacy,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
BUDGETS = {
    "schema_version": 1,
    "global_limits": {"commits": 10, "review_rounds": 3},
    "sizes": {
        "small": {"tokens": 100, "ci_minutes": 10, "agent_minutes": 20},
        "medium": {"tokens": 200, "ci_minutes": 20, "agent_minutes": 40},
        "large": {"tokens": 400, "ci_minutes": 40, "agent_minutes": 80},
    },
    "task_type_multipliers": {"default": 1.0, "infraestructura": 1.0},
}
OFFLINE = frozenset({
    "docs/coordinacion-pr-validation.md:L5-U1",
    "docs/coordinacion-pr-validation.md:L8-U1",
    "docs/coordinacion-pr-validation.md:L9-U1",
    "docs/costos-presupuestos.md:L5-U1",
    "docs/costos-presupuestos.md:L13-U1",
    "docs/costos-presupuestos.md:L15-U1",
    "docs/costos-presupuestos.md:L15-U2",
    "docs/costos-presupuestos.md:L16-U1",
    "docs/costos-presupuestos.md:L17-U1",
    "docs/costos-presupuestos.md:L19-U1",
    "docs/costos-presupuestos.md:L19-U2",
    "docs/costos-presupuestos.md:L19-U3",
    "docs/costos-presupuestos.md:L27-U1",
    "docs/cumplimiento-datos-licencias.md:L15-U1",
    "docs/cumplimiento-datos-licencias.md:L15-U2",
    "docs/cumplimiento-datos-licencias.md:L17-U1",
    "docs/cumplimiento-datos-licencias.md:L21-U1",
})
WORLD = {"docs/cumplimiento-datos-licencias.md:L17-U2":
         "La revisión material del producto y la habilitación de producción son externas"}
POLICY = {
    "docs/coordinacion-pr-validation.md:L52-U1":
        "La reversión declarativa no tiene una función de aplicación independiente",
    "docs/costos-presupuestos.md:L29-U1":
        "Nota histórica F1F; un informe mensual real no se acredita offline",
}


def marker(*, tokens: int = 30, ci_minutes: int = 3,
           agent_minutes: int = 6, review_rounds: int = 1) -> dict:
    return {
        "task_type": "infraestructura", "size": "small", "tokens": tokens,
        "ci_minutes": ci_minutes, "agent_minutes": agent_minutes,
        "review_rounds": review_rounds,
    }


def event(cost: dict | None = None, *, commits: int = 2) -> dict:
    body = "Closes #1800"
    if cost is not None:
        body += "\n<!-- factory-cost " + json.dumps(cost) + " -->"
    return {
        "repository": {"full_name": "pl0n3r/Factory"},
        "pull_request": {"number": 19, "body": body, "commits": commits},
    }


def privacy() -> dict:
    return {
        "version": 1, "project": "pl0n3r/GrindFlow",
        "scope": "operations", "purpose": "support",
        "data_categories": ["account_identifier"],
        "consent_or_exception": "exception_for_legal_review",
        "evidence": {name: "fixture:" + name for name in REQUIRED_EVIDENCE},
        "reviewed_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


class _CoordAPI:
    """Interfaz mínima sintética; nunca crea un cliente GitHub autenticado."""
    def __init__(self) -> None:
        self.issue_state = "open"
        self.pull_data = {
            "base": {"ref": "main"}, "head": {"ref": "trabajo/issue-17"},
            "body": "Closes #17", "merged": False,
        }
        self.deleted: list[str] = []
        self.statuses: list[tuple[int, str]] = []

    def pull(self, number: int) -> dict:
        if number != 19:
            raise AssertionError("PR ajeno al fixture")
        return self.pull_data

    def issue(self, number: int) -> dict:
        if number != 17:
            raise AssertionError("Issue ajeno al fixture")
        return {"number": number, "state": self.issue_state, "labels": []}

    def pull_files(self, number: int) -> set[str]:
        if number != 19:
            raise AssertionError("PR ajeno al fixture")
        return {"tests/synthetic.py"}

    def open_pulls(self) -> list[dict]:
        return []

    def delete_branch(self, branch: str) -> None:
        self.deleted.append(branch)

    def set_status(self, issue: int, value: str) -> None:
        self.statuses.append((issue, value))


class CoberturaFactory09Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: ejecutar contratos reales en los 17 subcasos offline."""
        self.assertEqual((17, 1, 2),
                         (len(OFFLINE), len(WORLD), len(POLICY)))
        self.assertEqual(len(OFFLINE | WORLD.keys() | POLICY.keys()), 20)
        self.assertFalse(OFFLINE & (WORLD.keys() | POLICY.keys()))

        # Coordinación L5: rama, relación de cierre, destino y colisiones.
        api = _CoordAPI()
        self.assertEqual(issue_from_branch("trabajo/issue-17"), 17)
        self.assertEqual(closing_issues("Closes #17"), {17})
        with redirect_stdout(StringIO()) as stdout:
            validate_pull(api, 19, False)
        self.assertIn("Coordinación válida", stdout.getvalue())

        # Coordinación L8/L9: el merge legítimo cierra el Issue antes del
        # evento tardío y su limpieza terminal no exige volver a abrirlo.
        api.issue_state = "closed"
        api.pull_data["merged"] = True
        close_pr_reservation(api, 17, "trabajo/issue-17", api.pull_data, None)
        self.assertEqual(api.deleted, ["trabajo/issue-17"])
        self.assertEqual(api.statuses, [(17, STATUS_COMPLETED)])

        # Costos L5, L13, L15-U1/U2: solo métricas numéricas declaradas;
        # commits observados; no inventar un resultado verificado 'ok'.
        result = evaluate_pr(event(marker()), BUDGETS)
        self.assertEqual(result["issue"], "pl0n3r/Factory#1800")
        self.assertEqual(result["usage"]["commits"], 2)
        self.assertEqual(result["usage_sources"]["commits"], "observed")
        self.assertEqual(result["usage_sources"]["tokens"], "declared")
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "warning")
        self.assertNotEqual(result["status"], "ok")

        # L16: 80-100 % activa warning aun sin dimensión excedida.
        near = evaluate_pr(event(marker(tokens=85)), BUDGETS)
        self.assertEqual(near["status"], "warning")
        self.assertIn("near:tokens", near["reasons"])

        # L17: falta observación o un consumo > 100 % no autoriza progreso.
        missing = evaluate_pr(event(), BUDGETS)
        self.assertEqual(missing["status"], "soft-block")
        self.assertEqual(missing["reasons"], ["missing-cost-marker"])
        over = evaluate_pr(event(marker(tokens=101)), BUDGETS)
        self.assertEqual(over["status"], "soft-block")
        self.assertIn("over:tokens", over["reasons"])

        # L19-U2/U3: trazabilidad de dimensiones no verificadas, nunca 'ok'.
        self.assertIn("unverified:tokens", result["reasons"])
        self.assertIn("unverified:ci_minutes", result["reasons"])
        self.assertIn("unverified:agent_minutes", result["reasons"])
        self.assertIn("unverified:review_rounds", result["reasons"])

        # L27: el motor agrupa ejecuciones reales en una única unidad PR,
        # sin fingir que estas muestras sintéticas son telemetría real.
        history = [
            {"pr_number": i, "run_id": i, "ci_minutes": 5,
             "conclusion": "success", "created_at": f"2026-10-{i:02d}T00:00:00Z"}
            for i in range(1, 5)
        ]
        trend = ci_trend(history)
        self.assertEqual(trend["metric"], "ci_minutes_per_pr")
        self.assertEqual(trend["samples"], 4)
        self.assertEqual(trend["run_samples"], 4)
        self.assertEqual(trend["status"], "measured")

        # Cumplimiento L15-U1/U2: referencias controladas y fecha vigente.
        record = privacy()
        self.assertEqual(set(record["evidence"]), REQUIRED_EVIDENCE)
        self.assertEqual(validate_privacy(record, now=NOW), "pl0n3r/GrindFlow")

        # Cumplimiento L17-U1: la excepción es anotación, nunca permiso.
        with patch.object(sys, "argv", ["cumplimiento.py", "--stdlib-only"]), \
             patch.object(sys, "stdin", StringIO(json.dumps(record))), \
             redirect_stdout(StringIO()) as captured:
            self.assertEqual(compliance_main(), 0)
        result = json.loads(captured.getvalue())
        self.assertEqual(result["evidence_status"], "documented_not_legally_approved")
        self.assertEqual(result["license_status"], "identifiers_present_review_required")
        self.assertEqual(result["packages_observed"], 0)
        self.assertNotIn("compliant", result)
        self.assertNotIn("release_authorized", result)

    def test_falla_cerrado(self) -> None:
        """AC-02: permisos, entradas, duplicados y evidencia inválida."""
        # Coordinación: la excepción post-merge NO se permite para un PR abierto.
        api = _CoordAPI()
        api.issue_state = "closed"
        with self.assertRaisesRegex(CoordinationError, "debe estar abierto"):
            validate_pull(api, 19, False)
        api.issue_state = "open"
        api.pull_data["base"]["ref"] = "develop"
        with self.assertRaisesRegex(CoordinationError, "main"):
            validate_pull(api, 19, False)
        api.pull_data["base"]["ref"] = "main"
        api.pull_data["head"]["ref"] = "feature/incorrect"
        with self.assertRaisesRegex(CoordinationError, "canónico"):
            validate_pull(api, 19, False)
        api.pull_data["head"]["ref"] = "trabajo/issue-17"
        api.pull_data["body"] = "No relación de cierre"
        with self.assertRaisesRegex(CoordinationError, "Closes #17"):
            validate_pull(api, 19, False)

        # Costos L19-U1: un marker JSON inválido y valores no numéricos vetan.
        malformed = event()
        malformed["pull_request"]["body"] += "\n<!-- factory-cost {broken} -->"
        with self.assertRaises(CostError):
            evaluate_pr(malformed, BUDGETS)
        with self.assertRaisesRegex(CostError, "tokens"):
            evaluate_pr(event(marker(tokens=-2)), BUDGETS)
        with self.assertRaisesRegex(CostError, "tokens"):
            evaluate_pr(event(marker(tokens=True)), BUDGETS)
        with self.assertRaisesRegex(CostError, "run_id duplicado"):
            ci_trend([
                {"pr_number": 1, "run_id": 8, "ci_minutes": 1,
                 "conclusion": "success", "created_at": "2026-10-01T00:00:00Z"},
                {"pr_number": 2, "run_id": 8, "ci_minutes": 1,
                 "conclusion": "failure", "created_at": "2026-10-02T00:00:00Z"},
            ])

        # Cumplimiento: siete evidencias, esquema cerrado, 365 días de
        # política interna y negación sin filtrar información del llamador.
        record = privacy()
        cases = []
        missing = deepcopy(record)
        del missing["evidence"]["legal_review"]
        cases.append(missing)
        extra = deepcopy(record)
        extra["contact_email"] = "synthetic@example.invalid"
        cases.append(extra)
        old = deepcopy(record)
        old["reviewed_at"] = (NOW - timedelta(days=366)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cases.append(old)
        future = deepcopy(record)
        future["reviewed_at"] = (NOW + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cases.append(future)
        inconsistent = deepcopy(record)
        inconsistent["consent_or_exception"] = "no_personal_data"
        cases.append(inconsistent)
        for case in cases:
            with self.subTest(violation=tuple(sorted(case))):
                with self.assertRaises(ComplianceError) as caught:
                    validate_privacy(case, now=NOW)
                self.assertNotIn("synthetic@example.invalid", str(caught.exception))

        # L21: argparse del CLI no admite paths arbitrarios ni secretos.
        with patch.object(sys, "argv",
                          ["cumplimiento.py", "--privacy", "/tmp/private.json",
                           "--stdlib-only"]), \
             patch.object(sys, "stdin", StringIO("{}")):
            with self.assertRaises(SystemExit) as caught:
                compliance_main()
        self.assertEqual(caught.exception.code, 2)

    def test_sin_datos_reales(self) -> None:
        """AC-03: evidencia enteramente sintética; sin red ni credenciales."""
        record = privacy()
        before = deepcopy(record)
        validate_privacy(record, now=NOW)
        self.assertEqual(record, before)
        payload = json.dumps(record, sort_keys=True)
        for forbidden in ("password", "token", "cookie", "private_key",
                          "access_key", "customer_name", "customer_email"):
            self.assertNotIn(forbidden, payload.lower())
        self.assertEqual(len(OFFLINE | WORLD.keys() | POLICY.keys()), 20)
        self.assertTrue(all(reason for reason in (*WORLD.values(), *POLICY.values())))
        self.assertTrue((ROOT / "scripts/coordinar_trabajo.py").is_file())
        self.assertTrue((ROOT / "metricas/costos.py").is_file())
        self.assertTrue((ROOT / "seguridad/cumplimiento.py").is_file())

    def test_gate_validar_presente(self) -> None:
        """AC-04: contrato del gate en código; CI acredita HEAD exacto."""
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("\n  validar:\n", workflow)
        gate = workflow.split("\n  validar:\n", 1)[1]
        self.assertIn("name: Validar", gate)
        self.assertIn("if: always()", gate)
        self.assertIn("needs:", gate)


if __name__ == "__main__":
    unittest.main()
