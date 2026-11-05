# Factory #2028 — verificación lote 12/18 (70 filas)

**Corte:** 5-nov-2026 · matriz canónica: `docs/matriz-cobertura.md` · épico #304 · reserva V3 `bc80faff-8bc8-480c-8a9b-3a7d7ad0f8fe`.

## Resultado verificable y límites

**PR de esta hoja: [#2048](https://github.com/pl0n3r/Factory/pull/2048)** — todos los testigos de la tabla se verifican en este PR; no supone promoción a cobertura productiva.

70/70 unidades trazadas: Quality Regression (10), Sonar Watch offline (23), evidencia Sonar (21), reconciliación histórica (8) y Recovery adapters (8). **0 promociones** a CUBIERTO; las 70 siguen NO_VERIFICABLE, sin SIN_COBERTURA en este lote.

Los testigos citados ejecutan contratos locales reales con fixtures sintéticos: rechazos fail-closed, ausencia de autoridad automática, normalización y estados. No acreditan observación Sonar externa, ejecución real en CI de consumidores, refresco de alertas antiguas, validación productiva, backup externo ni la vigencia actual de la fotografía histórica del 24-oct-2026. La consolidación #2035 debe conservar esta distinción.

| Área | Evidencia acotada | Brecha que no se promueve |
| --- | --- | --- |
| REGRESION_LOCAL | clasificación VERIFIED/FLAKY, lessons y candidato sin promoción | ejecución de corrección o política productiva |
| SONAR_WATCH_OFFLINE | parser, contratos, labels, deduplicación y runner sin cron | lectura viva de Sonar e Issues reales |
| SONAR_NORMALIZACION | esquemas, estados UNKNOWN/FAIL, cobertura N/A legítima | calidad observada real y gates de otros repos |
| RECONCILIACION_HISTORICA | snapshot fechado y sus ocho decisiones documentales | estado actual de los Issues y releases |
| RECOVERY_SIN_IO | proveedores, manifiesto y request cerrado, hashes e idempotencia | almacenamiento, restauración o backups efectivamente observados |

## Trazabilidad de las 70 unidades

| Fila exacta | Testigo conductual existente | Alcance | Ancla normalizada | Resultado |
| --- | --- | --- | --- | --- |
| `docs/quality-regression.md:L27-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler` | REGRESION_LOCAL | `solo en ese caso se genera una lesson compatible con lecciones` | NO_VERIFICABLE |
| `docs/quality-regression.md:L27-U2` | `tests/test_quality_regression.py::QualityRegressionTests::test_unverified_fix_or_missing_regression_test_never_emits_guardrail_material` | REGRESION_LOCAL | `una observación no verificada conserva evidencia diagnóstica p` | NO_VERIFICABLE |
| `docs/quality-regression.md:L31-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler` | REGRESION_LOCAL | `dos o más lessons verificadas con fuentes github distintas y e` | NO_VERIFICABLE |
| `docs/quality-regression.md:L31-U2` | `tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler` | REGRESION_LOCAL | `este módulo solo expone el candidato retornado por ese contrat` | NO_VERIFICABLE |
| `docs/quality-regression.md:L33-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue` | REGRESION_LOCAL | `no se crea un immune guardrail engine paralelo no hay schedule` | NO_VERIFICABLE |
| `docs/quality-regression.md:L37-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue` | REGRESION_LOCAL | `quality health y proyección a readiness 293 pertenecen a 347` | NO_VERIFICABLE |
| `docs/quality-regression.md:L38-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue` | REGRESION_LOCAL | `clasificación corrección operativa mediante queue 269 pertenec` | NO_VERIFICABLE |
| `docs/quality-regression.md:L39-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue` | REGRESION_LOCAL | `el e2e transversal pertenece a 348` | NO_VERIFICABLE |
| `docs/quality-regression.md:L40-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue` | REGRESION_LOCAL | `este módulo no modifica performance ni recovery` | NO_VERIFICABLE |
| `docs/quality-regression.md:L41-U1` | `tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue` | REGRESION_LOCAL | `no existe autoridad para ejecutar fixes promover políticas o d` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L3-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_sonar_watch_no_longer_has_scheduled_or_manual_triggers` | SONAR_WATCH_OFFLINE | `estado post f1c 1308 pr 1309 sonar watch no se ejecuta automát` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L3-U2` | `tests/test_sonar_watch.py::SonarWatchTests::test_retired_workflow_and_offline_engine_are_preserved` | SONAR_WATCH_OFFLINE | `los issues auto sonar 1052 1053 no se refrescan automáticament` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L3-U3` | `tests/test_sonar_watch.py::SonarWatchTests::test_offline_runtime_loads_versioned_config_without_workflow` | SONAR_WATCH_OFFLINE | `el motor offline scripts sonar watch py y la proyección qualit` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L22-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_versioned_runtime_config_covers_exact_factory_catalog` | SONAR_WATCH_OFFLINE | `no requieren reinterpretar observación runtime como política` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L24-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_versioned_runtime_config_covers_exact_factory_catalog` | SONAR_WATCH_OFFLINE | `migrar analysis method de un proyecto requiere nueva decisión` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L30-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_public_projects_need_no_token_and_private_projects_fail_closed_without_one` | SONAR_WATCH_OFFLINE | `si alguno exige private y no existe sonar token aborta sin toc` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L32-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_public_projects_need_no_token_and_private_projects_fail_closed_without_one` | SONAR_WATCH_OFFLINE | `payload ausente o ambiguo falla cerrado` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L32-U2` | `tests/test_sonar_watch.py::SonarWatchTests::test_analysis_method_uses_read_only_settings_get_only` | SONAR_WATCH_OFFLINE | `no se convierte en política implícita` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L42-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_autoscan_setting_maps_strictly_to_analysis_method` | SONAR_WATCH_OFFLINE | `el parser exige exactamente un setting sonar autoscan enabled` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L42-U2` | `tests/test_sonar_watch.py::SonarWatchTests::test_autoscan_setting_maps_strictly_to_analysis_method` | SONAR_WATCH_OFFLINE | `ausencia duplicidad key inesperada o cualquier otro valor fall` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L46-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_offline_runtime_loads_versioned_config_without_workflow` | SONAR_WATCH_OFFLINE | `esto no autoriza ejecutarlo ni sincronizar issues reales` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L48-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_sonar_watch_no_longer_has_scheduled_or_manual_triggers` | SONAR_WATCH_OFFLINE | `los checks sonar ci based sonar yml y codeql siguen como valid` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L52-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_current_pass_closes_only_matching_auto_issue` | SONAR_WATCH_OFFLINE | `un pass solo lo cierra con freshness current` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L52-U2` | `tests/test_sonar_watch.py::SonarWatchTests::test_not_applicable_closes_auto_issue_once_and_preserves_required_failures` | SONAR_WATCH_OFFLINE | `una señal not applicable no abre issue si existe uno abierto d` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L54-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_auto_alert_creation_has_canonical_labels_and_block_reason` | SONAR_WATCH_OFFLINE | `todo issue abierto que administra el watcher se crea o reconci` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L54-U2` | `tests/test_sonar_watch.py::SonarWatchTests::test_terminal_signals_do_not_fake_readiness_or_pass` | SONAR_WATCH_OFFLINE | `las alertas son observaciones no hojas ejecutables el cuerpo e` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L54-U3` | `tests/test_sonar_watch.py::SonarWatchTests::test_current_pass_closes_only_matching_auto_issue` | SONAR_WATCH_OFFLINE | `en cierre verificado el estado de github pasa a closed y la et` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L54-U4` | `tests/test_sonar_watch.py::SonarWatchTests::test_not_applicable_closes_auto_issue_once_and_preserves_required_failures` | SONAR_WATCH_OFFLINE | `el contenido histórico no se reescribe como pass` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L54-U5` | `tests/test_sonar_watch.py::SonarWatchTests::test_reconcile_unlabeled_auto_alert_without_duplicates` | SONAR_WATCH_OFFLINE | `se preservan etiquetas fuera de las familias tipo prioridad es` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L56-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_issue_body_contains_concrete_quality_gate_and_ce_failure_evidence` | SONAR_WATCH_OFFLINE | `el cuerpo conserva estado razón freshness referencias opacas y` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L60-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_ci_missing_coverage_remains_actionable` | SONAR_WATCH_OFFLINE | `controlbot y factory usan ci cobertura ausente sigue siendo un` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L60-U2` | `tests/test_sonar_watch.py::SonarWatchTests::test_versioned_runtime_config_covers_exact_factory_catalog` | SONAR_WATCH_OFFLINE | `cambiar método o visibilidad exige actualizar el contrato` | NO_VERIFICABLE |
| `docs/quality-sonar-watch.md:L64-U1` | `tests/test_sonar_watch.py::SonarWatchTests::test_runtime_auth_and_settings_scenarios_are_fail_closed_without_sonar_writes` | SONAR_WATCH_OFFLINE | `si falta configuración el contrato es ambiguo una respuesta no` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L5-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed` | SONAR_NORMALIZACION | `debe declarar` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L7-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_factory_project_catalog_is_explicit_and_bounded` | SONAR_NORMALIZACION | `project dentro del catálogo explícito brvtal condor controlbot` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L8-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed` | SONAR_NORMALIZACION | `snapshot at con zona horaria y evidence refs no sensibles` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L9-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_quality_gate_and_failed_condition_are_normalized` | SONAR_NORMALIZACION | `quality gate con estado ok error y condiciones fallidas cuando` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L10-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed` | SONAR_NORMALIZACION | `analysis con analyzed at método automatic ci y si existe cober` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L11-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_failed_ce_task_preserves_sanitized_server_error` | SONAR_NORMALIZACION | `ce task y su error message cuando el servidor marca failed` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L12-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds` | SONAR_NORMALIZACION | `uso de líneas de organización visibilidad y deuda histórica` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L13-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed` | SONAR_NORMALIZACION | `ausencia conocida de una señal como null no omitiendo la clave` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L15-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed` | SONAR_NORMALIZACION | `un valor explícitamente ausente null se normaliza como unknown` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L21-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_quality_gate_and_failed_condition_are_normalized` | SONAR_NORMALIZACION | `quality gate` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L22-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed` | SONAR_NORMALIZACION | `analysis freshness` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L24-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed` | SONAR_NORMALIZACION | `organization line usage` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L25-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed` | SONAR_NORMALIZACION | `visibility` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L26-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed` | SONAR_NORMALIZACION | `analysis method` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L28-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds` | SONAR_NORMALIZACION | `historical debt` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L30-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_quality_gate_and_failed_condition_are_normalized` | SONAR_NORMALIZACION | `cada señal contiene status pass fail unknown stale not applica` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L32-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed` | SONAR_NORMALIZACION | `analysis method ci exige evidencia de cobertura coverage avail` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L32-U2` | `tests/test_quality_sonar.py::SonarEvidenceTests::test_automatic_missing_coverage_is_not_applicable` | SONAR_NORMALIZACION | `la señal se conserva como not applicable nunca como pass` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L32-U3` | `tests/test_quality_sonar.py::SonarEvidenceTests::test_organization_line_usage_applicability_follows_visibility_policy` | SONAR_NORMALIZACION | `de forma equivalente organization line usage es not applicable` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L34-U1` | `tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds` | SONAR_NORMALIZACION | `los evidence ref item level se validan pero no se propagan al` | NO_VERIFICABLE |
| `docs/quality-sonar.md:L34-U2` | `tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds` | SONAR_NORMALIZACION | `la autoridad del lote queda en snapshot evidence refs evitando` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L5-U1` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `el contrato de un issue no se declara cumplido por un pr parci` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L20-U1` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `8 issues abiertos` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L20-U2` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `0 cierres automáticos justificables por aceptación integral` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L20-U3` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `la existencia de commits parciales no permite cerrar épicas ni` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L21-U1` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `no se fusiona factory v1 no se activa ninguna liberación de le` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L21-U2` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `esta hoja solo reclama su documento y su test` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L22-U1` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `antes de un corte posterior hay que releer issues head de main` | NO_VERIFICABLE |
| `docs/reconciliacion-issues-20261024.md:L22-U2` | `tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance` | RECONCILIACION_HISTORICA | `este documento no prueba el estado futuro` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L7-U1` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_and_google_drive_cold_copy_are_opaque_idempotent_and_checksum_aware` | RECOVERY_SIN_IO | `object storage destino técnico primario offsite` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L7-U2` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_remains_primary_and_icloud_is_not_supported` | RECOVERY_SIN_IO | `siempre permanece primario` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L8-U1` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_and_google_drive_cold_copy_are_opaque_idempotent_and_checksum_aware` | RECOVERY_SIN_IO | `google drive cold copy opcional y solo si el recovery manifest` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L9-U1` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_remains_primary_and_icloud_is_not_supported` | RECOVERY_SIN_IO | `icloud no soportado y no es dependencia del contrato` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L13-U1` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_adapter_contract_is_declarative_external_io_free_and_non_authorizing` | RECOVERY_SIN_IO | `cada intención recibe un recovery manifest v1 ya validable por` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L15-U1` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_invalid_sensitive_or_unsafe_adapter_input_fails_closed_without_echo` | RECOVERY_SIN_IO | `provider object storage google drive` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L16-U1` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_adapter_contract_is_declarative_external_io_free_and_non_authorizing` | RECOVERY_SIN_IO | `operation upload materialize verify` | NO_VERIFICABLE |
| `docs/recovery-adapters.md:L17-U1` | `tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_invalid_sensitive_or_unsafe_adapter_input_fails_closed_without_echo` | RECOVERY_SIN_IO | `object ref referencia opaca no path ni url` | NO_VERIFICABLE |

## Validación y reversión

El test nuevo `tests/test_verificacion_factory_12.py` verifica los 70 IDs contra la matriz y cada línea original, ejecuta testigos existentes y rechaza mutaciones (filas ausentes, duplicadas, añadidas, anclas incorrectas y promocionadas). No consulta la red ni escribe artefactos externos.

Validación reproducible: `python3 -m unittest discover -s tests -p test_verificacion_factory_12.py -v`; gate de CI: Tests de scripts y Validar terminales sobre HEAD exacto.

Solo se reclaman esta hoja y su test. Revertir el squash elimina ambos; no se modifica la matriz ni se publica Factory@v1.
