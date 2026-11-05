# Factory #2019 — verificación lote 03/18 (70 filas)

**Corte:** 5-nov-2026; fuente `docs/matriz-cobertura.md`; épica #304;
reserva V3 `e3612e16-f2b0-4271-af50-0a806ad8e017`; fase `construccion`.
Claims exclusivos `docs/verificacion/verificacion-03.md` y
`tests/test_verificacion_factory_03.py`.

## Alcance y límites demostrables

Se contrastan 70/70 filas originales de cuatro fuentes: 20 de vistas
derivadas, 24 de DoD Compiler, 17 de evaluación de agentes y 9 de
Evolution Engine. Se ejecutan testigos conductuales existentes de
implementación, se cotejan las cláusulas con su línea histórica y se
rechazan mutaciones en inventario e informe.

**0 promociones**: todas las 70 filas conservan `NO_VERIFICABLE`.
Los tests ejercen regresiones locales y sintéticas, no prueban adopción
integral de consumidores, decisiones humanas, observación efectiva de
agentes reales, costo real, operación de fábrica ni publicación.
No se certifica la matriz como verde; la consolidación #2035 conserva
la exclusividad de `docs/matriz-cobertura.md`.

| Clase | Prueba local ejecutada | Brecha sin acreditar |
| --- | --- | --- |
| DERIVED_VIEWS_LOCAL | manifest, determinismo, drift y autorreferencia | sincronización efectiva en consumidores |
| DOD_LOCAL | criterios Done por tipo, invariantes y seguridad fail-closed | pruebas exactas de PRs cross-repo |
| AGENTS_EVALUATION_LOCAL | ranking con muestra suficiente, datos parciales y esquema | desempeño/telemetría de agentes reales |
| EVOLUTION_LOCAL | ciclo, transiciones, causalidad y rollback lógico | despliegues y evolución observada en producción |

## Trazabilidad de las 70 unidades

| Fila exacta | Testigo de código | Alcance | Ancla real normalizada | Resultado |
| --- | --- | --- | --- | --- |
| `docs/derived-views.md:L3-U2` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views` | DERIVED_VIEWS_LOCAL | `la vista solo materializa o verifica esa información` | NO_VERIFICABLE |
| `docs/derived-views.md:L9-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views` | DERIVED_VIEWS_LOCAL | `view id identificador estable` | NO_VERIFICABLE |
| `docs/derived-views.md:L10-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views` | DERIVED_VIEWS_LOCAL | `source fuente canónica y sus referencias` | NO_VERIFICABLE |
| `docs/derived-views.md:L11-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views` | DERIVED_VIEWS_LOCAL | `view superficie derivada` | NO_VERIFICABLE |
| `docs/derived-views.md:L12-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic` | DERIVED_VIEWS_LOCAL | `mode generated si existe un generador seguro o regression cuando la fu` | NO_VERIFICABLE |
| `docs/derived-views.md:L13-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic` | DERIVED_VIEWS_LOCAL | `generator función determinista obligatoria para generated` | NO_VERIFICABLE |
| `docs/derived-views.md:L14-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic` | DERIVED_VIEWS_LOCAL | `drift check test guard que impide publicar una vista divergente` | NO_VERIFICABLE |
| `docs/derived-views.md:L18-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic` | DERIVED_VIEWS_LOCAL | `un generador debe ser una función pura sin red reloj aleatoriedad ni e` | NO_VERIFICABLE |
| `docs/derived-views.md:L18-U2` | `tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic` | DERIVED_VIEWS_LOCAL | `la misma instantánea normalizada de la fuente debe producir exactament` | NO_VERIFICABLE |
| `docs/derived-views.md:L24-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed` | DERIVED_VIEWS_LOCAL | `el guard compara la salida esperada con la vista comprometida y falla ` | NO_VERIFICABLE |
| `docs/derived-views.md:L24-U2` | `tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed` | DERIVED_VIEWS_LOCAL | `no se debe arreglar la fuente para hacer pasar el check ni aceptar la ` | NO_VERIFICABLE |
| `docs/derived-views.md:L28-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed` | DERIVED_VIEWS_LOCAL | `la regresión debe comprobar claims concretos contra la fuente canónica` | NO_VERIFICABLE |
| `docs/derived-views.md:L28-U2` | `tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed` | DERIVED_VIEWS_LOCAL | `esto permite proteger una vista mientras se evita inventar una extracc` | NO_VERIFICABLE |
| `docs/derived-views.md:L34-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source` | DERIVED_VIEWS_LOCAL | `no debe convertir el readme en fuente de verdad` | NO_VERIFICABLE |
| `docs/derived-views.md:L38-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source` | DERIVED_VIEWS_LOCAL | `identifique la fuente canónica` | NO_VERIFICABLE |
| `docs/derived-views.md:L39-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source` | DERIVED_VIEWS_LOCAL | `registre la vista en el manifiesto` | NO_VERIFICABLE |
| `docs/derived-views.md:L40-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source` | DERIVED_VIEWS_LOCAL | `elija generated solo si puede demostrar determinismo y ausencia de efe` | NO_VERIFICABLE |
| `docs/derived-views.md:L40-U2` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source` | DERIVED_VIEWS_LOCAL | `de lo contrario use regression` | NO_VERIFICABLE |
| `docs/derived-views.md:L41-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source` | DERIVED_VIEWS_LOCAL | `añada un drift check determinista` | NO_VERIFICABLE |
| `docs/derived-views.md:L42-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source` | DERIVED_VIEWS_LOCAL | `documente el límite y la reversión` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L3-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts` | DOD_LOCAL | `definition of done compiler deriva el contrato de evidencia que debe e` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L5-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts` | DOD_LOCAL | `solo produce requisitos verificables por máquina a partir de la tarea ` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L6-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts` | DOD_LOCAL | `project dna validado` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L12-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts` | DOD_LOCAL | `change type code database ci docs security o` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L14-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts` | DOD_LOCAL | `surfaces superficies afectadas por ejemplo api web` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L16-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants` | DOD_LOCAL | `risk low medium high o unknown` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L18-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants` | DOD_LOCAL | `project dna aporta el fingerprint y el conocimiento verificable del so` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L24-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants` | DOD_LOCAL | `ci requerida` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L25-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants` | DOD_LOCAL | `cero hallazgos de revisión abiertos` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L26-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants` | DOD_LOCAL | `alcance limitado a rutas reclamadas` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L34-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable` | DOD_LOCAL | `código tests del scope análisis estático` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L35-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable` | DOD_LOCAL | `base de datos verify plan backup y compatibilidad de esquema` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L36-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable` | DOD_LOCAL | `ci validación de workflow ejecución representativa` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L37-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable` | DOD_LOCAL | `docs lint y links` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L38-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable` | DOD_LOCAL | `seguridad scan casos negativos` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L39-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable` | DOD_LOCAL | `riesgo medio alto plan de rollback` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L39-U2` | `tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable` | DOD_LOCAL | `riesgo alto añade smoke exact sha` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L48-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done` | DOD_LOCAL | `safe fallback y exige además de las invariantes` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L50-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done` | DOD_LOCAL | `suite completa` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L51-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done` | DOD_LOCAL | `análisis estático` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L52-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done` | DOD_LOCAL | `security scan` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L53-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done` | DOD_LOCAL | `rollback plan` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L54-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done` | DOD_LOCAL | `completar contexto antes de promoción` | NO_VERIFICABLE |
| `docs/dod-compiler.md:L56-U1` | `tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done` | DOD_LOCAL | `así ignorancia nunca equivale a menos evidencia` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L7-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_ranking_is_separate_by_task_type_and_deterministic` | AGENTS_EVALUATION_LOCAL | `campos obligatorios` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L13-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_ranking_is_separate_by_task_type_and_deterministic` | AGENTS_EVALUATION_LOCAL | `el validador rechaza campos desconocidos duplicados por task id número` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L17-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation` | AGENTS_EVALUATION_LOCAL | `una configuración solo entra al ranking al alcanzar la muestra mínima` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L19-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation` | AGENTS_EVALUATION_LOCAL | `mayor tasa de éxito` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L20-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation` | AGENTS_EVALUATION_LOCAL | `menos incidentes posteriores por tarea` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L21-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation` | AGENTS_EVALUATION_LOCAL | `mayor tasa de integración a la primera` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L22-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation` | AGENTS_EVALUATION_LOCAL | `menos commits de retrabajo` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L23-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation` | AGENTS_EVALUATION_LOCAL | `menos rondas de revisión` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L24-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation` | AGENTS_EVALUATION_LOCAL | `menos tokens cuando el dato existe` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L26-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `solo se publica una recomendación cuando existen al menos dos configur` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L26-U2` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `tokens solo desempatan cuando todas las tareas de las configuraciones ` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L26-U3` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `telemetría parcial queda como tokens avg null y no se interpreta como ` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L30-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `github workflows metricas yml valida el motor y evalúa el mes utc ante` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L32-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `el cli del workflow lee únicamente metricas datos jsonl y escribe únic` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L32-U2` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `no acepta rutas arbitrarias` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L32-U3` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `con cero datos del periodo la corrida sigue siendo válida pero no reco` | NO_VERIFICABLE |
| `docs/evaluacion-agentes.md:L34-U1` | `metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost` | AGENTS_EVALUATION_LOCAL | `los proyectos que adopten el kit deben producir registros con este con` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L10-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_candidate_follows_closed_lifecycle` | EVOLUTION_LOCAL | `observe remember learn propose shadow experiment validate promote or r` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L12-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_candidate_follows_closed_lifecycle` | EVOLUTION_LOCAL | `solo se admite la transición a la etapa inmediatamente siguiente` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L20-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed` | EVOLUTION_LOCAL | `generation` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L22-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed` | EVOLUTION_LOCAL | `parent generation` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L25-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed` | EVOLUTION_LOCAL | `la huella del candidato validado por constitution v1` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L26-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed` | EVOLUTION_LOCAL | `decision cuando la etapa es promote or reject` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L27-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed` | EVOLUTION_LOCAL | `restores generation cuando la etapa es rollback` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L29-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_lineage_preserves_parent_reason_and_evidence` | EVOLUTION_LOCAL | `el candidato se valida antes de crear la primera generación` | NO_VERIFICABLE |
| `docs/evolution-engine.md:L35-U1` | `tests/test_evolution_engine.py::EvolutionEngineTests::test_lineage_preserves_parent_reason_and_evidence` | EVOLUTION_LOCAL | `promote or reject exige una decisión explícita adopt o reject` | NO_VERIFICABLE |

## Validación y reversión

`python3 -m unittest -v tests.test_verificacion_factory_03`,
`Tests de scripts`, `Criterios de aceptación` y `Validar` exact-HEAD.
No se tocan esquemas, permisos, matriz central, datos reales, releases,
proveedores, secretos, producción ni go-live. Reversión por squash revert.
