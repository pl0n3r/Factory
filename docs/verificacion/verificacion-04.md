# Factory #2020 — verificación lote 04/18 (70 filas)

**Fuente:** `docs/matriz-cobertura.md` · Épica #304 · 5-nov-2026.
**Reserva V3:** consultar siempre el [último recibo auténtico de Coordinación en Factory #2020](https://github.com/pl0n3r/Factory/issues/2020); los UUID históricos de esta hoja no acreditan autoridad vigente.
**Alcance:** solo `docs/verificacion/verificacion-04.md` y `tests/test_verificacion_factory_04.py`.

## Resultado verificable y límites

**70/70** cláusulas de Evolution Engine (1), Experience Guardrails (22),
preflight F2 (8), Factory Queue (20), Feedback Mesh (18) y Fitness Engine (1).
**0 promociones** de `NO_VERIFICABLE` a `CUBIERTO`: la consolidación #2035
requiere recibos suficientes para autorizar cualquier promoción.

`tests/test_verificacion_factory_04.py` valida identidades exactas, cláusulas
de matriz, anclas de las líneas originales y testigos conductuales reales.
Casos negativos rechazan filas suprimidas, duplicadas o nuevas, fuentes alteradas,
testigos ficticios y promoción de cobertura. Solo fixtures sintéticos/offline.

| Clase | Evidencia local | Brecha no acreditada |
| --- | --- | --- |
| EVOLUCION_LOCAL | Lifecycle y rollback append-only | promoción/activación real |
| EXPERIENCIA_LOCAL | Umbral, normalización y candidato | autoridad estable externa |
| F2_LOCAL | Preflight en seis checkouts locales | forks/callers externos, mover `Factory@v1` |
| COLA_LOCAL | WorkItem, scopes, feedback y E2E sintético | agentes reales |
| FEEDBACK_LOCAL | Refs, fitness y rechazo seguro | mejora causal en producción |
| FITNESS_LOCAL | Comparación y drift de direcciones | telemetría productiva |

## Trazabilidad de las 70 unidades

| Fila exacta | Testigo de código | Alcance | Ancla real normalizada | Resultado |
| --- | --- | --- | --- | --- |
| `docs/evolution-engine.md:L41-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_rollback_restores_prior_generation_without_erasing_history` | EVOLUCION_LOCAL | `rollback solo es valido al final del recorrido constitucional` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L4-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `nunca promueve una regla directamente a` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L5-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `stable y nunca modifica las lecciones historicas` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L11-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `what que ocurrio` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L12-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `why causa` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L13-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `prevention prevencion esperada` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L14-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `source issue pr con evidencia` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L15-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `ademas de id proyecto kind y timestamp` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L17-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_repeated_evidence_can_generate_guardrail_candidate` | EXPERIENCIA_LOCAL | `las lecciones se validan con el validador existente antes de agruparlas` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L24-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_equivalent_lessons_are_consolidated` | EXPERIENCIA_LOCAL | `causa normalizada` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L25-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_equivalent_lessons_are_consolidated` | EXPERIENCIA_LOCAL | `prevencion normalizada` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L27-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_equivalent_lessons_are_consolidated` | EXPERIENCIA_LOCAL | `la normalizacion solo elimina diferencias de mayusculas acentos puntuacion y` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L32-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_single_anecdote_does_not_become_policy` | EXPERIENCIA_LOCAL | `por defecto se requieren al menos 2 lecciones y 2 fuentes distintas` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L36-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_single_anecdote_does_not_become_policy` | EXPERIENCIA_LOCAL | `el compilador acepta hasta 32 lecciones por llamada y el umbral nunca puede bajar` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L43-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_candidate_keeps_origin_and_expected_prevention` | EXPERIENCIA_LOCAL | `fingerprint determinista del patron` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L44-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_candidate_keeps_origin_and_expected_prevention` | EXPERIENCIA_LOCAL | `ids y fuentes de todas las lecciones origen` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L45-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_candidate_keeps_origin_and_expected_prevention` | EXPERIENCIA_LOCAL | `prevencion esperada` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L46-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_candidate_keeps_origin_and_expected_prevention` | EXPERIENCIA_LOCAL | `ocurrencias` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L47-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_candidate_keeps_origin_and_expected_prevention` | EXPERIENCIA_LOCAL | `candidato constitucional bajo` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L49-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_candidate_keeps_origin_and_expected_prevention` | EXPERIENCIA_LOCAL | `rollback revert` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L50-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_candidate_keeps_origin_and_expected_prevention` | EXPERIENCIA_LOCAL | `fingerprint validado por constitution` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L53-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_single_anecdote_does_not_become_policy` | EXPERIENCIA_LOCAL | `promocion posterior debe recorrer evolution engine factory lab` | NO_VERIFICABLE |
| `docs/experience-guardrails.md:L54-U1` | `tests/test_experience_guardrails.py::ExperienceGuardrailTests::test_single_anecdote_does_not_become_policy` | EXPERIENCIA_LOCAL | `no puede convertir el candidato en autoridad estable` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L3-U1` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_multiple_consumers_and_yaml_extensions` | F2_LOCAL | `esta prueba solo lee los workflows de seis checkouts existentes en una raiz local condor grindflow brvtal controlbot autofactory y fact` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L11-U1` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_all_scanned_with_no_references_can_be_safe` | F2_LOCAL | `el codigo 0 safe significa solo que no se observaron callers de esos targets en los seis checkouts inspeccionados no que puedan borrarse inmedia` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L15-U1` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_missing_consumer_blocks_removal` | F2_LOCAL | `este inventario no representa otros forks callers externos branches ni repositorios a los que no se tenga acceso` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L15-U2` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_missing_consumer_blocks_removal` | F2_LOCAL | `para publicar un reemplazo o retirar un reusable hace falta otro contrato v3 con los consumidores migrados regresiones gates de release y prueba ` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L16-U1` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_pinned_and_v1_callers_are_reported` | F2_LOCAL | `preservar ci privacidad codeql sonar roles permisos minimos etiquetas exigidas factory v1 y revision coderabbit final` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L16-U2` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_pinned_and_v1_callers_are_reported` | F2_LOCAL | `ni el preflight ni su safe autorizan mover un tag o saltar una puerta humana` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L17-U1` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_cli_reports_safe_and_blocked_with_exit_codes` | F2_LOCAL | `un reporte blocked no debe resolverse suprimiendo la referencia en una rama ajena` | NO_VERIFICABLE |
| `docs/f2-caller-migration.md:L17-U2` | `tests/test_f2_caller_preflight.py::F2CallerPreflightTests::test_cli_reports_safe_and_blocked_with_exit_codes` | F2_LOCAL | `la migracion corresponde a los repos consumidores mediante sus propias reservas v3` | NO_VERIFICABLE |
| `docs/factory-queue.md:L3-U1` | `tests/test_factory_queue_e2e.py::FactoryQueueE2ETests::test_docs_describe_complete_factory_queue_v1_flow` | COLA_LOCAL | `este documento describe unicamente el contrato de origen introducido por factory 269 270` | NO_VERIFICABLE |
| `docs/factory-queue.md:L35-U1` | `tests/test_work_origin.py::WorkOriginTests::test_collections_are_bounded_deduplicated_and_secret_safe` | COLA_LOCAL | `el validador falla cerrado ante campos desconocidos listas fuera de limites identificadores invalidos referencias sobredimensionadas y valores co` | NO_VERIFICABLE |
| `docs/factory-queue.md:L39-U1` | `tests/test_work_origin.py::WorkOriginTests::test_canonical_payload_and_fingerprint_are_deterministic` | COLA_LOCAL | `canonical payload serializa el workitem validado de forma determinista` | NO_VERIFICABLE |
| `docs/factory-queue.md:L40-U1` | `tests/test_work_origin.py::WorkOriginTests::test_canonical_payload_and_fingerprint_are_deterministic` | COLA_LOCAL | `work fingerprint identifica el contenido completo del workitem` | NO_VERIFICABLE |
| `docs/factory-queue.md:L41-U1` | `tests/test_work_origin.py::WorkOriginTests::test_idempotency_scope_is_stable_and_isolated` | COLA_LOCAL | `idempotency scope combina group id venture id project id work type e idempotency key` | NO_VERIFICABLE |
| `docs/factory-queue.md:L55-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_is_attributable_to_work_item` | COLA_LOCAL | `factory queue v1 cierra el ciclo operativo con un feedback terminal que conserva provenance hacia el workitem canonico` | NO_VERIFICABLE |
| `docs/factory-queue.md:L63-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_is_attributable_to_work_item` | COLA_LOCAL | `work id identidad del workitem observado` | NO_VERIFICABLE |
| `docs/factory-queue.md:L64-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_is_attributable_to_work_item` | COLA_LOCAL | `work fingerprint fingerprint canonico recomputado desde el workitem` | NO_VERIFICABLE |
| `docs/factory-queue.md:L65-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_is_attributable_to_work_item` | COLA_LOCAL | `idempotency scope scope estable usado para deduplicacion cross origin` | NO_VERIFICABLE |
| `docs/factory-queue.md:L66-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_fails_closed_on_invalid_provenance_or_freshness` | COLA_LOCAL | `executor ref ejecutor concreto que produjo el outcome` | NO_VERIFICABLE |
| `docs/factory-queue.md:L67-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_fails_closed_on_invalid_provenance_or_freshness` | COLA_LOCAL | `producer ref productor original del workitem que debe coincidir` | NO_VERIFICABLE |
| `docs/factory-queue.md:L68-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_fails_closed_on_invalid_provenance_or_freshness` | COLA_LOCAL | `status estado terminal success failed rejected cancelled` | NO_VERIFICABLE |
| `docs/factory-queue.md:L69-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_fails_closed_on_invalid_provenance_or_freshness` | COLA_LOCAL | `evidence refs referencias de evidencia no vacias y sin duplicados` | NO_VERIFICABLE |
| `docs/factory-queue.md:L70-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_fails_closed_on_invalid_provenance_or_freshness` | COLA_LOCAL | `observed at timestamp con zona horaria y freshness valida` | NO_VERIFICABLE |
| `docs/factory-queue.md:L72-U1` | `tests/test_feedback_contract.py::FeedbackContractTests::test_execution_feedback_fails_closed_on_invalid_provenance_or_freshness` | COLA_LOCAL | `la validacion falla cerrada si provenance fingerprint scope productor evidencia estado o freshness no corresponden al workitem` | NO_VERIFICABLE |
| `docs/factory-queue.md:L76-U1` | `tests/test_factory_queue_e2e.py::FactoryQueueE2ETests::test_terminal_outcome_produces_attributable_feedback` | COLA_LOCAL | `el escenario e2e de 273 debe construir un workitem valido pasarlo por readiness dispatcher v2 simular una ejecucion terminal y producir feedback ` | NO_VERIFICABLE |
| `docs/factory-queue.md:L76-U2` | `tests/test_factory_queue_e2e.py::FactoryQueueE2ETests::test_terminal_outcome_produces_attributable_feedback` | COLA_LOCAL | `la evidencia e2e debe demostrar que el resultado conserva work fingerprint e idempotency scope que entradas stale inconsistentes fallan cerrado y` | NO_VERIFICABLE |
| `docs/factory-queue.md:L80-U1` | `tests/test_factory_queue_e2e.py::FactoryQueueE2ETests::test_multi_origin_equivalent_work_deduplicates_by_scope` | COLA_LOCAL | `factory queue v1 queda validada de extremo a extremo con el siguiente flujo canonico` | NO_VERIFICABLE |
| `docs/factory-queue.md:L84-U1` | `tests/test_factory_queue_e2e.py::FactoryQueueE2ETests::test_multi_origin_equivalent_work_deduplicates_by_scope` | COLA_LOCAL | `ambas comparten idempotency scope por lo que no se materializan como dos unidades ejecutables` | NO_VERIFICABLE |
| `docs/factory-queue.md:L88-U1` | `tests/test_factory_queue_e2e.py::FactoryQueueE2ETests::test_docs_describe_complete_factory_queue_v1_flow` | COLA_LOCAL | `unicamente demuestra la composicion coherente de los contratos entregados por 270 271 y 272` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L3-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_manifest_uses_real_typed_evidence_without_falsifying_state` | FEEDBACK_LOCAL | `este slice cierra la demostracion operativa de factory 161 no crear un motor nuevo es una restriccion explicita` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L9-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_manifest_uses_real_typed_evidence_without_falsifying_state` | FEEDBACK_LOCAL | `factory pr 253 merge 34409905f874b118b973ec316041467534fe2cd6 aporta una cohorte real de revision` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L10-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_manifest_uses_real_typed_evidence_without_falsifying_state` | FEEDBACK_LOCAL | `grindflow pr 181 aporta evidencia real de review en head 4a85df7dffb667a476afc3103c268e5f46f0e79a permanece open y nunca se presenta como merge` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L11-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_manifest_uses_real_typed_evidence_without_falsifying_state` | FEEDBACK_LOCAL | `factory 163 pr 256 merge 3d5752bd33cfae73380610e30c5f9de9740af11f materializa el experimento de eficiencia marginal` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L12-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_manifest_uses_real_typed_evidence_without_falsifying_state` | FEEDBACK_LOCAL | `factory pr 325 y 326 son ejecuciones posteriores reales` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L12-U2` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_manifest_uses_real_typed_evidence_without_falsifying_state` | FEEDBACK_LOCAL | `326 llega a main 3b99efa32ba4fe931f053f1023b34943fe63bf14 con ci exact main run 36503410235 en success` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L20-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_review_baseline_replays_factory_and_consumer_evidence` | FEEDBACK_LOCAL | `metricas datos review efficiency baseline jsonl reproduce evidencia de factory consumidor sin mezclar cohortes incompatibles` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L21-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_insufficient_evidence_rejects_change_and_keeps_stable_policy` | FEEDBACK_LOCAL | `163 formula la hipotesis de reducir rondas automaticas low risk de 3 a 2` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L22-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_candidate_preserves_constitution_evolution_fitness_and_rollback_lineage` | FEEDBACK_LOCAL | `constitution limita el candidato al namespace evolutivo y exige rollback reversible` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L23-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_candidate_preserves_constitution_evolution_fitness_and_rollback_lineage` | FEEDBACK_LOCAL | `factory lab ejecuta shadow sin escrituras externas` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L24-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_candidate_preserves_constitution_evolution_fitness_and_rollback_lineage` | FEEDBACK_LOCAL | `fitness conserva dimensiones protegidas y la incertidumbre explicita` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L25-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_insufficient_evidence_rejects_change_and_keeps_stable_policy` | FEEDBACK_LOCAL | `la muestra real disponible es insuficiente para cambiar politica` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L25-U2` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_insufficient_evidence_rejects_change_and_keeps_stable_policy` | FEEDBACK_LOCAL | `el resultado correcto es reject insufficient evidence` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L26-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_insufficient_evidence_rejects_change_and_keeps_stable_policy` | FEEDBACK_LOCAL | `review round limit 3 permanece estable` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L27-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_next_real_execution_keeps_stable_review_policy` | FEEDBACK_LOCAL | `pr 325 326 demuestran ejecuciones posteriores reales bajo la politica estable sin afirmar una mejora causal inexistente` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L31-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_feedback_loop_never_expands_authority` | FEEDBACK_LOCAL | `el candidato solo puede tocar evolution state no constitution ni permisos externos` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L33-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_e2e_is_deterministic_offline_and_fails_closed_on_inconsistent_refs` | FEEDBACK_LOCAL | `el escenario se reproduce offline y falla cerrado si un ref declara un estado imposible por ejemplo un pr open con merge sha o un pr merged sin m` | NO_VERIFICABLE |
| `docs/feedback-mesh-e2e.md:L39-U1` | `tests/test_feedback_mesh_e2e.py::FeedbackMeshE2ETests::test_docs_describe_complete_feedback_mesh_loop_without_parallel_engine` | FEEDBACK_LOCAL | `no satisface por si solo la demostracion final de 248 ac 09 que exige una mejora autosugerida probada y medida posteriormente` | NO_VERIFICABLE |
| `docs/fitness-engine.md:L20-U1` | `tests/test_fitness_engine.py::FitnessEngineTests::test_rejects_direction_drift_and_non_finite_values` | FITNESS_LOCAL | `imputa valores direction debe ser higher o lower y no puede cambiar` | NO_VERIFICABLE |

## Validación y reversión

- `python3 -m unittest -v tests.test_verificacion_factory_04`.
- `Tests de scripts` exact-HEAD, SonarCloud, CodeQL y CodeRabbit FINAL.
- Mantener `NO_VERIFICABLE` para las 70 filas; no tocar `docs/matriz-cobertura.md`.
- Ningún deploy, secreto, gasto, dato real, actualización de release o permiso.
- Reversión por revert del squash del PR.
