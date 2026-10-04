#!/usr/bin/env python3
import json
import unittest

from scripts.aceptacion_kit import parse_contract
from scripts.normalizar_issue import normalize_issue_body, plan_issue_normalization
from scripts.orquestador_kit import parse_task_marker
from scripts.dispatcher_v2 import Candidate, RepoFairnessContext, select_next_action, work_ladder


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


    def test_dispatcher_normalizes_before_first_take_and_skips_incomplete_same_cycle(self):
        complete_body = """## Problema
Legacy completo.

## Trabajo
Normalizar.

## Límites
Sin inventar.

## Criterios
- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_dispatcher_normalizes_before_first_take_and_skips_incomplete_same_cycle`.

### Rutas reclamadas
- `scripts/normalizar_issue.py`
"""
        complete = Candidate(
            key="factory-complete",
            priority="high",
            metadata={
                "repository_ref": "pl0n3r/Factory",
                "issue_body": complete_body,
                "normalizer_task_metadata": TASK_METADATA,
            },
        )
        action = select_next_action(
            [complete],
            fairness_context=RepoFairnessContext(),
        )
        self.assertEqual(action["action"], "normalize_then_take")
        self.assertEqual(action["selected"], "factory-complete")
        self.assertTrue(action["retry_once"])

        incomplete_body = complete_body.replace(
            "- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_dispatcher_normalizes_before_first_take_and_skips_incomplete_same_cycle`.",
            "- [ ] [AC-01] Sin target.",
        )
        incomplete = Candidate(
            key="factory-incomplete",
            priority="high",
            unlock_impact=10,
            metadata={
                "repository_ref": "pl0n3r/Factory",
                "issue_body": incomplete_body,
                "normalizer_task_metadata": TASK_METADATA,
            },
        )
        next_candidate = Candidate(
            key="condor-next",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        action = select_next_action(
            [incomplete, next_candidate],
            fairness_context=RepoFairnessContext(),
        )
        self.assertEqual(action["action"], "take")
        self.assertEqual(action["selected"], "condor-next")
        self.assertEqual(len(action["repairs"]), 1)
        self.assertEqual(
            action["repairs"][0]["plan"]["action"],
            "comment_and_skip",
        )
        self.assertFalse(action["declare_no_work"])


    def test_normalization_is_idempotent_and_preserves_single_task_marker(self):
        body = """## Problema
Legacy con marker de tarea existente.

## Trabajo
Normalizar sin duplicar markers.

## Límites
No inventar.

## Criterios
- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_normalization_is_idempotent_and_preserves_single_task_marker`.

### Rutas reclamadas
- `scripts/normalizar_issue.py`

<!-- factory-plan-task {"depends_on":[942],"epic":943,"order":1,"owner":"pl0n3r","paths":["scripts/normalizar_issue.py"],"roles":["ingenieria-software"],"task_key":"ISSUE_NORMALIZER_V1","version":1} -->
"""
        first = normalize_issue_body(body, task_metadata=TASK_METADATA)
        self.assertTrue(first.complete)
        self.assertEqual(first.body.count("<!-- factory-plan-task "), 1)

        second = normalize_issue_body(first.body, task_metadata=TASK_METADATA)
        self.assertTrue(second.complete)
        self.assertFalse(second.changed)
        self.assertEqual(second.body.count("<!-- factory-plan-task "), 1)

        plan = plan_issue_normalization(
            first.body,
            task_metadata=TASK_METADATA,
        )
        self.assertEqual(plan["action"], "take")
        self.assertFalse(plan["retry_once"])

    def test_work_ladder_exposes_normalization_before_take(self):
        body = """## Problema
Legacy listo para normalizar.

## Trabajo
Normalizar.

## Límites
Sin inventar.

## Criterios
- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_work_ladder_exposes_normalization_before_take`.

### Rutas reclamadas
- `scripts/normalizar_issue.py`
"""
        candidate = Candidate(
            key="factory-legacy",
            priority="high",
            metadata={
                "repository_ref": "pl0n3r/Factory",
                "issue_body": body,
                "normalizer_task_metadata": TASK_METADATA,
            },
        )
        action = work_ladder(
            [candidate],
            fairness_context=RepoFairnessContext(),
        )
        self.assertEqual(action["step"], "normalize_before_take")
        self.assertEqual(action["work"]["key"], "factory-legacy")
        self.assertEqual(
            action["normalization"]["action"],
            "edit_and_retry_once",
        )
        self.assertTrue(action["retry_once"])


if __name__ == "__main__":
    unittest.main()
