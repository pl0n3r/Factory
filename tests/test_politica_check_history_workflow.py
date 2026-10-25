"""Regresión de histórico autenticado de check-runs en Policy (Factory #1512).

La consulta REST debe preservar los intentos anteriores sin permitir que un
resultado antiguo (incluso fallido) sustituya el check más reciente de un gate.
No usa red, credenciales ni un repositorio consumidor.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.politica_kit import (
    PolicyError,
    _latest_checks_by_name,
    validate_other_gates_green,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/politica.yml").read_text(encoding="utf-8")
HEAD = "a" * 40


def _check(
    identifier: int,
    name: str,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    slug: str = "github-actions",
    app_id: int = 15368,
    head_sha: str = HEAD,
) -> str:
    return json.dumps(
        {
            "id": identifier,
            "name": name,
            "head_sha": head_sha,
            "app": {"slug": slug, "id": app_id},
            "status": status,
            "conclusion": conclusion,
        }
    )


def _check_history() -> list[str]:
    return [
        # Primer intento fallido: se conserva para la procedencia del retry.
        _check(101, "Factory policy / Validar decisiones y límite de revisión",
               conclusion="failure"),
        _check(102, "validate", conclusion="failure"),
        # El siguiente intento reemplaza el estado *vigente* del gate.
        _check(103, "validate"),
        _check(104, "SonarCloud Code Analysis",
               slug="sonarqubecloud", app_id=12526),
        _check(105, "CodeQL",
               slug="github-advanced-security", app_id=57789),
        _check(106, "tests"),
        _check(107, "validar-pr / Validar coordinación"),
        _check(108, "privacidad / Privacidad como código"),
        # Un retry de Policy puede estar aún en ejecución: no es un gate externo.
        _check(109, "Factory policy / Validar decisiones y límite de revisión",
               status="in_progress", conclusion=None),
    ]


class PoliticaCheckHistoryWorkflowTests(unittest.TestCase):
    def test_authenticated_query_preserves_all_attempts_across_pages(self) -> None:
        self.assertIn(
            'checks_url_base="repos/$REPOSITORY/commits/$PR_HEAD_SHA/'
            'check-runs?filter=all&per_page=100"',
            WORKFLOW,
        )
        # GitHub usa filter=latest por defecto y omite el check anterior.
        self.assertNotIn("check-runs?per_page=100", WORKFLOW)
        self.assertIn('"${checks_url_base}&page=$page"', WORKFLOW)
        self.assertIn("for page in 1 2 3 4 5; do", WORKFLOW)
        self.assertIn('X-GitHub-Api-Version: 2022-11-28', WORKFLOW)

    def test_history_is_not_pruned_and_current_gate_selection_is_monotonic(self) -> None:
        self.assertIn(
            "# El motor Policy recibe checks_file ORIGINAL sin ninguna poda.",
            WORKFLOW,
        )
        self.assertIn('--checks-file "$checks_file"', WORKFLOW)
        self.assertIn("jq -c '.check_runs[]' \"$checks_json\" >> \"$checks_file\"", WORKFLOW)
        checks = _check_history()
        selected = _latest_checks_by_name(checks, head_sha=HEAD)
        self.assertEqual(selected["validate"]["id"], 103)
        self.assertEqual(
            selected["Factory policy / Validar decisiones y límite de revisión"]["id"],
            109,
        )
        # El fallo histórico de CI no desplaza el success actual, mientras la
        # Policy histórica permanece disponible para validar procedencia.
        validate_other_gates_green(checks, head_sha=HEAD)
        # Un check *más reciente* fallido tampoco puede ser ignorado por
        # existir otro success en el historial del mismo gate.
        with self.assertRaisesRegex(PolicyError, "Check no verde"):
            validate_other_gates_green(
                [*checks, _check(110, "validate", conclusion="failure")],
                head_sha=HEAD,
            )
        # Histórico de otro HEAD o con emisor desconocido sigue fallando cerrado.
        for bad in (
            _check(111, "validate", head_sha="b" * 40),
            _check(111, "validate", slug="evil", app_id=999),
        ):
            with self.subTest(bad=bad), self.assertRaises(PolicyError):
                validate_other_gates_green([*checks, bad], head_sha=HEAD)

    def test_query_retains_bounded_stable_fail_closed_snapshot(self) -> None:
        # filter=all no elimina límites ni estabilización: más intentos
        # implican fallo cerrado si exceden presupuesto o hay carreras REST.
        for required in (
            "MAX_PUBLIC_CHECKS",
            "MAX_EVIDENCE_BYTES",
            "(( current_total <= MAX_PUBLIC_CHECKS ))",
            "(( observed_count <= expected_total ))",
            "(( observed_count == expected_total ))",
            "total_count cambió entre páginas de check-runs",
            "IDs de check-runs autenticados inválidos o duplicados",
            'cmp -s "$previous_snapshot" "$current_snapshot"',
            '[[ "$stable_snapshot" == true ]]',
            "Check-runs sin dos snapshots completos y estables",
            "recheck_pr_identity",
        ):
            with self.subTest(required=required):
                self.assertIn(required, WORKFLOW)
        self.assertLess(
            WORKFLOW.index('[[ "$stable_snapshot" == true ]]'),
            WORKFLOW.index("if gate_readiness; then"),
        )
        self.assertLess(
            WORKFLOW.index("if gate_readiness; then"),
            WORKFLOW.index('POLICY_OUTPUT='),
        )


if __name__ == "__main__":
    unittest.main()
