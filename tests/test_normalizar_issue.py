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

    def test_accepts_every_canonical_test_target_root(self):
        for root in ("tests", "metricas", "seguridad", "lecciones", "producto"):
            target = (
                f"{root}/test_contract.py::ContractTests::"
                "test_canonical_target_is_preserved"
            )
            body = f"""## Problema
Formato legacy con target canónico fuera de tests/.

## Trabajo
Normalizar sin rechazar roots válidos.

## Límites
No inventar targets.

## Criterios
- [ ] [AC-01] `{target}`.

### Rutas reclamadas
- `scripts/normalizar_issue.py`
"""
            result = normalize_issue_body(body, task_metadata=TASK_METADATA)
            self.assertTrue(result.complete, (root, result.missing))
            criteria = parse_contract(result.body)
            self.assertEqual(criteria[0].target, target)

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


    def test_real_931_and_932_current_bodies_are_noop(self):
        # Snapshots reales recuperables por la API de GitHub. Ambos ya fueron
        # reconciliados a forma canónica; el normalizador no debe reordenar
        # sus secciones auxiliares ni reescribir contenido técnico.
        real_bodies = ((931, "### Contexto\n\n#### Qué pasó (2026-10-03, 15:16 UTC)\n\nLa release 1.0.23 (puerta **#930**, decisión A del dueño registrada a las 15:14 UTC, `main@8f51b17ebd1a91a35145a072ddc1ed01957b06cf`) se frenó en el preflight. Run: https://github.com/pl0n3r/Factory/actions/runs/37132603675\n\n- `Compatibilidad de consumidores`: success.\n- `Validar gates de release v1.x` → paso `Verificar SHA, Issues, puerta y v1`: failure con `ERROR: Puerta creada por actor no confiable.` (`scripts/release_bootstrap.py`, línea ~257: `gate.get(\"author_association\") not in TRUSTED_ASSOCIATIONS`, con `TRUSTED_ASSOCIATIONS = {\"OWNER\",\"MEMBER\",\"COLLABORATOR\"}`).\n- `Publicar release semántico`, `Verificar canal v1` y self-test: skipped. No se creó `v1.0.23` ni Release; `v1` sigue en 1.0.22 (`5d1a2113`). Sin exposición a consumidores.\n\n#### Causa\n\nLa puerta #930 fue creada por `app/github-actions` (12:58 UTC) mediante el mecanismo de rearmado automático introducido para Factory#921 (`factory-release-rearm` desde #927, `factory-release-window`). Las puertas anteriores (#901, #918, #927) las crea `pl0n3r` (`OWNER`) y pasaban. Un Issue creado por el bot no tiene asociación `OWNER/MEMBER/COLLABORATOR`, así que el preflight lo rechaza. Es una incompatibilidad entre dos piezas nuevas: el rearmado automático y la validación de confianza del bootstrap.\n\n### Alcance\n\n1. Decidir la corrección sin debilitar la validación: (a) que el bootstrap acepte puertas del bot solo si llevan el marcador canónico de rearmado y `source_issue` apuntando a una puerta creada por el OWNER, con SHA coincidente y ventana vigente (verificable, no por nombre de actor); o (b) que el rearmado cree la puerta con una identidad de confianza ya aceptada. Documentar por qué es seguro.\n2. Pruebas de regresión con tres casos: puerta de OWNER (pasa), puerta rearmada del bot con `source_issue` válido (pasa), puerta de bot sin marcador/origen válido o con SHA distinto (falla cerrado).\n3. Revisar el resto del flujo de rearmado y de ventana (`factory-release-window` expiró a las 13:58 UTC sin decisión) para detectar otros desajustes parecidos antes de la siguiente release.\n4. Como el arreglo cambia `main`, la 1.0.23 necesitará una puerta nueva sobre el SHA exacto resultante, sin heredar la decisión de #930; abrirla de forma que el preflight la acepte y avisar al dueño en lenguaje sencillo.\n\n### Fuera de alcance\n\n- Publicar o mover `v1`, crear tags o Releases sin puerta del dueño con `expected_sha` exacto.\n- Aceptar puertas por el nombre del actor o relajar la confianza para puertas arbitrarias del bot.\n- Gasto, datos reales, go-live.\n\n### Criterios de aceptación\n\n- [ ] [AC-01] `tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::test_owner_created_gate_remains_trusted`.\n- [ ] [AC-02] `tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::test_rearmed_bot_gate_with_owner_source_issue_is_trusted`.\n- [ ] [AC-03] `tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::test_bot_gate_without_valid_rearm_origin_fails_closed`.\n- [ ] [AC-04] Check `Tests de scripts` verde sobre HEAD exacto.\n\n### Contrato ejecutable\n\n<!-- factory-acceptance {\"version\":1,\"criteria\":[{\"id\":\"AC-01\",\"kind\":\"test\",\"target\":\"tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::test_owner_created_gate_remains_trusted\"},{\"id\":\"AC-02\",\"kind\":\"test\",\"target\":\"tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::test_rearmed_bot_gate_with_owner_source_issue_is_trusted\"},{\"id\":\"AC-03\",\"kind\":\"test\",\"target\":\"tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::test_bot_gate_without_valid_rearm_origin_fails_closed\"},{\"id\":\"AC-04\",\"kind\":\"check\",\"target\":\"Tests de scripts\"}]} -->\n\n### Rutas reclamadas\n\n- `scripts/release_bootstrap.py`\n- `tests/test_release_bootstrap_runtime.py`\n- `docs/release-bootstrap.md`\n- `.github/workflows/release-bootstrap.yml`\n\n<!-- factory-plan-task {\"version\":1,\"epic\":931,\"task_key\":\"RELEASE_GATE_REARM_TRUST_V1\",\"order\":1,\"owner\":\"pl0n3r\",\"roles\":[\"seguridad\",\"sre\",\"ingenieria-software\",\"infraestructura\"],\"depends_on\":[],\"paths\":[\"scripts/release_bootstrap.py\",\"tests/test_release_bootstrap_runtime.py\",\"docs/release-bootstrap.md\",\".github/workflows/release-bootstrap.yml\"]} -->\n\n### Riesgo y reversión\n\nRiesgo medio: toca la validación de confianza de la puerta de release. Reversible por revert; no mueve `v1`, no crea tags ni publica.\n"), (932, "### Contexto\n\n#### Evidencia exacta\n\nFactoryRunner `main@80879785ba5353aebe68292829ca91164fc52b8a` tiene CI de push verde, pero el sweep programado de Etiquetas `37115028536` falló en el job `111180067287`, paso `Detectar merges con Etiquetas no verde`.\n\nEl reusable efectivo fue `pl0n3r/Factory/.github/workflows/etiquetas.yml@v1` en `5d1a211345c72f6a8743454ad68db7d20b62f19c`. El token del job tenía `contents: read`, `issues: write`, `pull-requests: read`. Al intentar persistir la alerta sobre una PR ya fusionada mediante `POST /repos/{repo}/issues/{pr}/comments`, GitHub respondió:\n\n`Resource not accessible by integration (HTTP 403)`.\n\n### Causa\n\n`.github/workflows/etiquetas.yml` conserva correctamente `pull-requests: read` por compatibilidad con consumidores. Subirlo a `pull-requests: write` repetiría la clase de incidente Factory#860: un reusable no puede exigir un envelope superior al de callers aún read-only y puede producir `startup_failure`.\n\nEl bug está en el destino de persistencia de la alerta: el sweep usa una PR fusionada como destino de escritura aunque el contrato deliberadamente no concede PR write.\n\n### Objetivo\n\nMantener el envelope compatible y enrutar la alerta durable/idempotente al **Issue fuente** que la PR cierra mediante el contrato `Closes #N`. Si una PR histórica no contiene referencia cerrante canónica, el sweep debe degradar a warning/summary no mutante y continuar; nunca debe fallar todo el sweep ni ampliar permisos.\n\n### Alcance\n\n- en `.github/workflows/etiquetas.yml`, para cada PR fusionada:\n  - resolver el Issue fuente con el parser canónico `labels_kit.py closing-reference`;\n  - leer comentarios del Issue fuente cuando exista;\n  - alimentar esos comentarios a `pr_label_governance.py alert-plan`;\n  - persistir una alerta nueva en `issues/{linked_issue}/comments`, no sobre la PR;\n  - si no existe closing reference válida, emitir warning visible y continuar sin POST;\n- conservar `contents: read`, `issues: write`, `pull-requests: read`;\n- no cambiar rulesets, required checks ni semántica del detector;\n- añadir regresión estática del destino y del fallback no fatal.\n\n### Criterios de aceptación\n\n- [ ] [AC-01] `tests/test_etiquetas_workflow_contract.py::EtiquetasWorkflowContractTests::test_sweep_routes_merge_alerts_to_linked_issue_without_pr_write`.\n- [ ] [AC-02] `tests/test_etiquetas_workflow_contract.py::EtiquetasWorkflowContractTests::test_metadata_permissions_remain_least_privilege`.\n- [ ] [AC-03] Check `Tests de scripts` verde sobre HEAD exacto.\n\n### Contrato ejecutable\n\n<!-- factory-acceptance {\"version\":1,\"criteria\":[{\"id\":\"AC-01\",\"kind\":\"test\",\"target\":\"tests/test_etiquetas_workflow_contract.py::EtiquetasWorkflowContractTests::test_sweep_routes_merge_alerts_to_linked_issue_without_pr_write\"},{\"id\":\"AC-02\",\"kind\":\"test\",\"target\":\"tests/test_etiquetas_workflow_contract.py::EtiquetasWorkflowContractTests::test_metadata_permissions_remain_least_privilege\"},{\"id\":\"AC-03\",\"kind\":\"check\",\"target\":\"Tests de scripts\"}]} -->\n\n### Rutas reclamadas\n\n- `.github/workflows/etiquetas.yml`\n- `tests/test_etiquetas_workflow_contract.py`\n\n<!-- factory-plan-task {\"version\":1,\"epic\":860,\"task_key\":\"LABEL_SWEEP_PR_ALERT_TARGET\",\"order\":1,\"owner\":\"pl0n3r\",\"roles\":[\"infraestructura\",\"ingenieria-software\",\"qa\",\"seguridad\"],\"depends_on\":[860],\"paths\":[\".github/workflows/etiquetas.yml\",\"tests/test_etiquetas_workflow_contract.py\"]} -->\n\n### Fuera de alcance\n\n- conceder `pull-requests: write`;\n- cambiar el detector de labels o rulesets;\n- reintentar workflows históricos;\n- mover `Factory@v1`, publicar release o tocar la puerta 1.0.23;\n- escribir en consumidores.\n\n### Riesgo y reversión\n\nRiesgo bajo/medio: cambia únicamente el destino de una alerta de gobernanza posterior al merge. El fallback sin closing reference es fail-safe y no bloquea el sweep. Reversible por revert."))
        for issue_number, body in real_bodies:
            result = normalize_issue_body(body, task_metadata=TASK_METADATA)
            self.assertTrue(result.complete, (issue_number, result.missing))
            self.assertFalse(result.changed, issue_number)
            self.assertEqual(result.body, body, issue_number)
            self.assertGreaterEqual(len(parse_contract(result.body)), 1)
            self.assertIsNotNone(parse_task_marker(result.body))

    def test_malformed_existing_markers_fail_closed_before_take(self):
        bad_acceptance = """### Contexto
Legacy.

### Alcance
Normalizar.

### Fuera de alcance
No inventar.

### Criterios de aceptación
- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_malformed_existing_markers_fail_closed_before_take`.

### Contrato ejecutable
<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"test"}]} -->

### Rutas reclamadas
- `scripts/normalizar_issue.py`
"""
        result = normalize_issue_body(
            bad_acceptance,
            task_metadata=TASK_METADATA,
        )
        self.assertFalse(result.complete)
        self.assertTrue(
            any(
                item.startswith("Contrato ejecutable inválido:")
                for item in result.missing
            )
        )

        bad_task = """### Contexto
Legacy.

### Alcance
Normalizar.

### Fuera de alcance
No inventar.

### Criterios de aceptación
- [ ] [AC-01] `tests/test_normalizar_issue.py::NormalizarIssueTests::test_malformed_existing_markers_fail_closed_before_take`.

### Contrato ejecutable
<!-- factory-acceptance {"criteria":[{"id":"AC-01","kind":"test","target":"tests/test_normalizar_issue.py::NormalizarIssueTests::test_malformed_existing_markers_fail_closed_before_take"}],"version":1} -->

<!-- factory-plan-task {"depends_on":[942],"epic":943,"order":1,"owner":"pl0n3r","paths":["scripts/normalizar_issue.py"],"task_key":"ISSUE_NORMALIZER_V1","version":1} -->
"""
        result = normalize_issue_body(
            bad_task,
            task_metadata=TASK_METADATA,
        )
        self.assertFalse(result.complete)
        self.assertTrue(
            any(
                item.startswith("factory-plan-task inválido:")
                for item in result.missing
            )
        )


if __name__ == "__main__":
    unittest.main()
