#!/usr/bin/env python3
import json
import unittest

from scripts.aceptacion_kit import parse_contract
from scripts.normalizar_issue import normalize_issue_body, plan_issue_normalization
from scripts.orquestador_kit import parse_task_marker


TASK_METADATA = {
    "epic": 943,
    "task_key": "ISSUE_NORMALIZER_V1",
    "order": 1,
    "owner": "pl0n3r",
    "roles": ["ingenieria-software", "sre"],
    "depends_on": [942],
}


class NormalizarIssueTests(unittest.TestCase):
    def test_legacy_headings_are_mapped_to_five_canonical_sections_without_losing_content(self):
        body = """## Problema
Caso histórico equivalente a Factory#931: una puerta rearmada fue rechazada.

#### Qué pasó
El detalle del fallo debe conservar su subencabezado.

## Trabajo
Normalizar el contrato sin cambiar su semántica.

## Límites
No publicar releases ni ampliar permisos.

## Criterios
- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_legacy_headings_are_mapped_to_five_canonical_sections_without_losing_content`.
- [ ] [AC-02] Check `Tests de scripts`.

### Rutas reclamadas
- `scripts/normalizar_issue.py`
- `tests/test_normalizar_issue.py`

Nota final que debe sobrevivir.
"""
        result = normalize_issue_body(body, task_metadata=TASK_METADATA)

        self.assertTrue(result.complete)
        self.assertTrue(result.changed)
        for heading in (
            "### Contexto",
            "### Alcance",
            "### Fuera de alcance",
            "### Criterios de aceptación",
            "### Contrato ejecutable",
        ):
            self.assertEqual(result.body.count(heading), 1)
        self.assertIn("Caso histórico equivalente a Factory#931", result.body)
        self.assertIn("#### Qué pasó", result.body)
        self.assertIn("El detalle del fallo debe conservar su subencabezado.", result.body)
        self.assertIn("Nota final que debe sobrevivir.", result.body)
        self.assertIn("<!-- factory-acceptance ", result.body)
        self.assertIn("<!-- factory-plan-task ", result.body)
        self.assertIn('"paths":["scripts/normalizar_issue.py","tests/test_normalizar_issue.py"]', result.body)
        self.assertEqual(len(parse_contract(result.body)), 2)
        marker = parse_task_marker(result.body)
        self.assertIsNotNone(marker)
        self.assertEqual(
            marker["paths"],
            ["scripts/normalizar_issue.py", "tests/test_normalizar_issue.py"],
        )

    def test_markers_are_built_only_from_valid_targets_never_invented(self):
        valid = """## Problema
Caso equivalente a Factory#932.

## Trabajo
Conservar permisos mínimos.

## Límites
No ampliar authority.

## Criterios
- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_markers_are_built_only_from_valid_targets_never_invented`.
- [ ] [AC-02] Check `Tests de scripts`.

### Rutas reclamadas
- `scripts/normalizar_issue.py`
"""
        result = normalize_issue_body(valid, task_metadata=TASK_METADATA)
        self.assertTrue(result.complete)
        marker = result.body.split("<!-- factory-acceptance ", 1)[1].split(" -->", 1)[0]
        payload = json.loads(marker)
        self.assertEqual(
            payload["criteria"],
            [
                {
                    "id": "AC-01",
                    "kind": "test",
                    "target": "tests/test_normalizar_issue.py::NormalizarIssueTests::test_markers_are_built_only_from_valid_targets_never_invented",
                },
                {"id": "AC-02", "kind": "check", "target": "Tests de scripts"},
            ],
        )

        missing_target = valid.replace(
            "- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_markers_are_built_only_from_valid_targets_never_invented`.",
            "- [ ] [AC-01] Esto debería quedar cubierto por alguna prueba.",
        )
        incomplete = normalize_issue_body(missing_target, task_metadata=TASK_METADATA)
        self.assertFalse(incomplete.complete)
        self.assertNotIn('"id":"AC-01"', incomplete.body)
        self.assertIn("AC-01 sin target ejecutable explícito", incomplete.missing)

    def test_incomplete_issue_gets_single_precise_comment_not_silent_failure(self):
        body = """## Problema
Formato antiguo.

## Trabajo
Repararlo.

## Límites
No inventar.

## Criterios
- [ ] [AC-01] Falta la evidencia ejecutable.

### Rutas reclamadas
- `scripts/normalizar_issue.py`
"""
        first = plan_issue_normalization(
            body,
            task_metadata=TASK_METADATA,
            existing_comments=(),
        )
        self.assertEqual(first["action"], "comment_and_skip")
        self.assertTrue(first["continue_same_cycle"])
        self.assertTrue(first["should_comment"])
        self.assertIn("AC-01 sin target ejecutable explícito", first["comment"])
        self.assertIn("factory-format-repair", first["comment"])

        second = plan_issue_normalization(
            body,
            task_metadata=TASK_METADATA,
            existing_comments=(first["comment"],),
        )
        self.assertEqual(second["action"], "comment_and_skip")
        self.assertFalse(second["should_comment"])
        self.assertIsNone(second["comment"])
        self.assertTrue(second["continue_same_cycle"])


if __name__ == "__main__":
    unittest.main()
