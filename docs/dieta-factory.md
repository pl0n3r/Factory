# Dieta Factory: inventario exacto y plan reversible

> **Hoja 0 de [Factory #1296](https://github.com/pl0n3r/Factory/issues/1296), ejecución [#1297](https://github.com/pl0n3r/Factory/issues/1297).** Inventario observado en `main@b0713650194e9a0c464d625bc6136eecad776377` el 2026-10-12. No es una orden de borrar archivos ni una autorización de publicar o desplegar.

## Evidencia y alcance

El árbol Git exacto contiene **38 archivos `.github/workflows/*.yml`** y ningún `.yaml` adicional; la estimación de 40 de la épica es orientativa y no debe sustituir este conteo. Hay 67 scripts Python bajo `scripts/` y 234 pruebas Python bajo `tests/` según el mismo árbol. Los nombres de tests de la tabla son **impactos a revisar**, no una instrucción de eliminarlos; incluyen pruebas indirectas. «Ninguno directo» indica que el workflow no llama de forma literal a un script local, no que carezca de dependencias. Ningún cambio de runtime/CI forma parte de esta hoja.

**Regla de seguridad:** conservar CI de tests/lint/build, CodeQL, Sonar, CodeRabbit (integración externa, sin workflow propio), privacidad, releases/deploy/observación y puertas de gasto, datos reales, borrado, freeze, credenciales y go-live. «Simplificar» jamás significa saltar una puerta dura. La futura política de severidades pertenece a #1295 y requiere su propia reserva, regresiones y gates. **Excepciones justificadas frente a la poda tentativa de #1296:** `costos.yml` conserva la evidencia de presupuesto del PR (`presupuesto-pr`) y `unattended-watchdog.yml` conserva vigilancia de actividad + resumen diario. Ninguno se sustituye por una frase genérica sobre gasto ni por el kill switch de Factory#767.

**Nota de actualización (#1068/#1300, 2026-10-12):** la línea base `main@b0713650194e9a0c464d625bc6136eecad776377` tenía 186 líneas en `.github/workflows/politica-comentario.yml`; la fila activa registra 332 tras el refuerzo de seguridad. El recuento histórico se conserva aquí como procedencia, sin añadir ni eliminar workflows. La separación permanente entre métricas históricas y pruebas de inventario corresponde a #1302.

## Inventario de workflows

| Workflow | Disparador(es) | Líneas | Scripts/dependencias directas | Tests afectados por revisar | Decisión | Fase |
| --- | --- | ---: | --- | --- | --- | ---: |
| `.github/workflows/aceptacion.yml` | workflow_call | 154 | scripts/aceptacion_kit.py | tests/test_aceptacion_kit.py, tests/test_aceptacion_workflow_contract.py | **simplificar** | 3 |
| `.github/workflows/auditoria-privacidad.yml` | workflow_call | 198 | scripts/auditar_privacidad.py | tests/test_auditar_privacidad.py | **quedarse** | 0 |
| `.github/workflows/automerge-construccion.yml` | pull_request | 321 | scripts/automerge_construccion.py (indirecto) | tests/test_automerge_construccion.py, tests/test_automerge_workflow.py | **simplificar** | 3 |
| `.github/workflows/bootstrap-coordination.yml` | issue_comment, workflow_dispatch | 144 | scripts/bootstrap_coordination.py | tests/test_bootstrap_coordination_workflow.py | **quedarse** | 0 |
| `.github/workflows/ci.yml` | workflow_call | 249 | ninguno directo | tests/test_runtime_workflow_contract.py | **quedarse** | 0 |
| `.github/workflows/codeql-evidence.yml` | pull_request, push | 60 | scripts/codeql_sarif_summary.py | tests/test_codeql_evidence_workflow.py, tests/test_codeql_sarif_summary.py | **quedarse** | 0 |
| `.github/workflows/coordinacion-trabajo.yml` | schedule, workflow_dispatch, pull_request, issues, issue_comment | 342 | scripts/coordinar_trabajo.py | tests/test_coordinar_trabajo.py, tests/test_coordinar_trabajo_unblock_validation.py | **simplificar** | 4 |
| `.github/workflows/coordinacion.yml` | workflow_call | 236 | scripts/coordinar_trabajo.py | tests/test_coordinacion_reusable_contract.py | **quedarse** | 0 |
| `.github/workflows/costos.yml` | pull_request, workflow_dispatch, schedule | 167 | metricas/costos.py | metricas/test_costos.py | **quedarse** | 0 |
| `.github/workflows/deploy.yml` | workflow_call | 86 | scripts/deploy_kit.py | tests/test_runtime_workflow_contract.py | **quedarse** | 0 |
| `.github/workflows/etiquetas-pr.yml` | workflow_call | 107 | scripts/labels_kit.py | tests/test_etiquetas_workflow_contract.py | **eliminar** | 2 |
| `.github/workflows/etiquetas.yml` | workflow_call | 230 | scripts/labels_kit.py, scripts/pr_label_governance.py | tests/test_etiquetas_workflow_contract.py, tests/test_labels_kit.py | **eliminar** | 2 |
| `.github/workflows/factory-ci.yml` | pull_request, push | 382 | scripts/politica_kit.py, scripts/release_window.py, scripts/coordinar_trabajo.py, scripts/aceptacion_kit.py | tests/test_quality_gates.py | **quedarse** | 0 |
| `.github/workflows/liberar-reservas.yml` | schedule, workflow_dispatch, pull_request | 84 | scripts/lease_auto_release.py | tests/test_lease_auto_release.py | **quedarse** | 0 |
| `.github/workflows/observar.yml` | workflow_call | 176 | scripts/observe_kit.py | tests/test_observar_workflow_contract.py | **quedarse** | 0 |
| `.github/workflows/orquestador.yml` | issue_comment, workflow_dispatch | 57 | scripts/orquestar_fabrica.py | tests/test_orquestador_workflow_contract.py | **quedarse** | 0 |
| `.github/workflows/politica-comentario.yml` | workflow_call | 332 | scripts/politica_kit.py | tests/test_politica_workflow_contract.py | **simplificar** | 3 |
| `.github/workflows/politica.yml` | workflow_call | 417 | scripts/politica_kit.py | tests/test_politica_kit.py, tests/test_politica_workflow_contract.py | **simplificar** | 3 |
| `.github/workflows/preview.yml` | workflow_call | 114 | scripts/preview_kit.py | tests/test_preview_workflow_contract.py | **quedarse** | 0 |
| `.github/workflows/privacidad.yml` | workflow_call | 48 | scripts/privacidad_gate.py | tests/test_privacidad_gate.py | **quedarse** | 0 |
| `.github/workflows/provision-project.yml` | workflow_dispatch | 65 | scripts/provision_project.py | tests/test_provision_project.py (verificar nombre al implementar) | **quedarse** | 0 |
| `.github/workflows/readme.yml` | workflow_call | 102 | ninguno directo (Python inline) | tests/test_readme_contract.py, tests/test_readme_contract_v2.py | **eliminar** | 2 |
| `.github/workflows/release-bootstrap.yml` | workflow_dispatch | 368 | scripts/verificar_ruleset_v1.py | tests/test_release_bootstrap_workflow.py | **simplificar** | 3 |
| `.github/workflows/release-window.yml` | workflow_dispatch, workflow_run | 296 | scripts/release_window.py | tests/test_release_window.py, tests/test_release_window_on_demand.py | **simplificar** | 3 |
| `.github/workflows/release.yml` | workflow_call | 231 | ninguno directo | tests/test_release_workflow_contract.py | **quedarse** | 0 |
| `.github/workflows/reusable-release-watchdog.yml` | push, schedule, workflow_dispatch | 269 | ninguno directo (shell/API) | tests/test_reusable_release_watchdog.py | **simplificar** | 3 |
| `.github/workflows/reusable-selftest.yml` | pull_request | 23 | scripts/ci_retry.py | tests/test_reusable_release_preflight.py | **quedarse** | 0 |
| `.github/workflows/roles.yml` | workflow_call | 207 | scripts/roles_kit.py | tests/test_roles_kit.py, tests/test_roles_workflow_contract.py | **eliminar** | 2 |
| `.github/workflows/seguridad.yml` | pull_request, push, issues, issue_comment, workflow_dispatch | 297 | ninguno directo (CodeQL/seguridad) | tests/test_template_security_workflow_contract.py | **quedarse** | 0 |
| `.github/workflows/sonar.yml` | pull_request, push, workflow_dispatch | 201 | scripts/generate_coverage.py | tests/test_sonar_ci_analysis_workflow.py | **quedarse** | 0 |
| `.github/workflows/unattended-watchdog.yml` | push, schedule, workflow_dispatch | 63 | scripts/unattended_watchdog_runtime.py, scripts/unattended_daily_summary.py | tests/test_unattended_watchdog_runtime.py, tests/test_unattended_daily_summary.py, tests/test_unattended_kill_switch.py | **quedarse** | 0 |

## Ledger F1A de bajas autorizadas

**Baseline histórica inmutable:** 38 workflows en `main@173519bde16498a796afd6a5af96b517d7e3a091` (después de #1297). **36 workflows tras F1A** al retirar esos dos triggers; **35 workflows activos tras F1B** al apagar el cron mensual accesorio de métricas. La tabla anterior enumera los workflows actuales: la línea base histórica y los blobs previos quedan registrados en este ledger, no se reemplazan por recuentos futuros.

**Preflight de consumidores:** se leyeron 88 workflows de consumidores en Condor (17), GrindFlow (25), brvtal (18), ControlBot (14), AutoFactory (6) y FactoryRunner (8), bajo sus SHA de `main` anotados en Factory #1301; ningún workflow hace `uses` de los dos YAML retirados. No están declarados como required checks ni puertas duras en el preflight F1A; la publicación de nuevos consumers requiere revisar de nuevo estos contratos.

| Baja | Workflow retirado | Blob SHA previo | Fase | Reversión | Regresión de dominio preservada |
| --- | --- | --- | --- | --- | --- |
| 1 | `.github/workflows/evolution-lab.yml` | `645cd08c9d9f79e23e945f798d14b225eaf0e95d` | F1A / fase 1 | squash-revert PR F1A | `tests/test_factory_lab_contract.py` |
| 2 | `.github/workflows/feedback-producto.yml` | `fe107d7f3a39a30d4fecefd0ca1c9ece68f5e490` | F1A / fase 1 | squash-revert PR F1A | `tests/test_feedback_contract.py` |

**Compensaciones conservadas en CI común:** compilación offline de todos los `lab/*.py`, suites shadow/experimentos, `producto/feedback.py` y `producto/test_feedback.py`, además de validación JSON de `producto/metricas.json`. El informe semanal automatizado de Feedback se suspende; el motor/reporte manual siguen presentes. No se tocan seguridad, presupuesto, privacidad, coordinación V3, release ni despliegue.

**Reversión:** squash-revert PR F1A restaura estos dos YAML, las dos filas originales del inventario, el contrato histórico de tests y la sección original de fase 1; sin movimiento de `Factory@v1` ni autorización live.
## Ledger F1B de baja del cron de métricas

**Baseline F1A:** 36 workflows en `main@2e20aef7fd8b019c677acec37e18d711341662cc`. Después de retirar **solo** `metricas.yml`, quedan **35 workflows activos**. El inventario histórico de 38 y las dos bajas F1A permanecen en su ledger independiente.

| Baja | Workflow retirado | Blob SHA previo | Transición | Reversión |
| --- | --- | --- | --- | --- |
| F1B | `.github/workflows/metricas.yml` | `f76a0bac2f9fc7b3669fbc58b968f1136c05d527` | 36 → 35 | squash-revert PR F1B |

**Efecto intencional:** se suspende el ranking mensual automático y sus artifacts `evaluacion-agentes-<run_id>` (`artifacts/recomendaciones.json`, `artifacts/dashboard.md`, retención anterior de 90 días); no se inventa otro cron. El motor offline `metricas/evaluar_agentes.py` y las pruebas `metricas/test_evaluar_agentes.py`, `metricas/test_producto_diario.py` continúan en el CI común. `costos.yml/presupuesto-pr` y los watchdogs, guardas de seguridad, privacidad, release y Coordinación permanecen.

**Preflight:** el YAML retirado era `pull_request`, `workflow_dispatch`, `schedule`, y no `workflow_call`. El check requerido observable de `main` es `Validar`; el CI común ejecuta las suites de métricas. Revalidar callers externos si se añaden referencias nuevas a ese trigger local. **Reversión:** squash-revert solo del PR F1B restaura cron, YAML, fila y pruebas anteriores sin deshacer F1A. No mover `Factory@v1`, publicar, gastar, desplegar ni activar live.

## Ledger F1C de baja de Sonar Watch

**Baseline F1B:** 35 workflows activos en `main@d9d9681720b258ad871c14260a254d389fbb96d2`. Tras retirar **solo** `.github/workflows/sonar-watch.yml` quedan **34 workflows activos**. Persisten la baseline histórica 38, F1A 36 y F1B 35; las cuatro bajas acumuladas son distintas y verificables.

| Baja | Workflow retirado | Blob SHA previo | Transición | Reversión |
| --- | --- | --- | --- | --- |
| F1C | `.github/workflows/sonar-watch.yml` | `8dd0f9cfed97be7a804c8248a89b17b817639a7a` | 35 → 34 | squash-revert PR F1C |

**Preflight de consumidores:** se inspeccionaron por contenido 122 YAML distintos del disparador candidato: 34 de Factory y 88 de Condor (17), GrindFlow (25), brvtal (18), ControlBot (14), AutoFactory (6) y FactoryRunner (8). No existen referencias literales a `sonar-watch.yml`, `Sonar Watch` o `sonar-watch.py` en esos workflows. La ficha `GET /repos/pl0n3r/Factory/branches/main` confirma `protected=true` y check requerido `Validar`; Sonar Watch no es ese check. No se elimina un reusable `workflow_call`: su entrada era solo `schedule` cada seis horas y `workflow_dispatch`.

**Pérdida funcional deliberada:** cesan tanto la sincronización automática Sonar → GitHub Issues cada seis horas como la invocación manual desde GitHub Actions. En particular, las alertas Sonar ya abiertas #1052/#1053 **dejan de actualizarse por este cron**. Los checks Sonar CI-based y CodeQL **no reemplazan** esta vigilancia. El motor offline `scripts/sonar-watch.py`, `quality/sonar-watch-config.json`, `tests/test_sonar_watch.py` y sus escenarios de API/fail-closed siguen preservados, sin un trigger nuevo de escritura.

**Seguridad:** sin cambios en `factory-ci.yml`, `sonar.yml`, `codeql-evidence.yml`, `costos.yml`, `unattended-watchdog.yml`, coordinación V3, release/bootstrap/freeze, deploy, kill switch ni `Factory@v1`. **Reversión:** squash-revert solo del PR F1C restaura workflow, cron/manual, fila del inventario y las tres pruebas de integración YAML anteriores sin revertir F1A/F1B. No se publica ni despliega.

## Plan por fases (F1A, F1B y F1C aplicadas; siguientes hojas independientes)

### Fase 1: apagar telemetría y aprendizaje, sin suprimir controles

**Rutas exactas:** ninguna de fase 1 permanece activa tras F1E; el motor de captura queda offline. **Dependencias a revisar antes del PR:** `scripts/cabina.py`, `scripts/captura_leccion.py`, `scripts/sonar-watch.py`, `metricas/evaluar_agentes.py`, `producto/feedback.py`, `metricas/test_evaluar_agentes.py`, `metricas/test_producto_diario.py`, `producto/test_feedback.py`, `tests/test_cabina_workflow_contract.py`, `tests/test_captura_leccion_workflow.py`, `tests/test_factory_lab_contract.py`, `tests/test_feedback_contract.py`, `tests/test_metricas_integer_bounds.py` y `tests/test_sonar_watch.py`.

**Orden:** eliminar primero consumidores directos por workflow, ejecutar pruebas y decidir con evidencia si los scripts/test restantes tienen otro consumidor. **No borrar** `scripts/unattended_kill_switch.py`, `scripts/unattended_guards.py` ni la comprobación obligatoria de #767. **Conservar explícitamente:**
- `.github/workflows/costos.yml`: el job `presupuesto-pr` evalúa `metricas/costos.py pr` contra la **base confiable** y publica artifacts de presupuesto; `tendencia-ci` sí es telemetría programada y solo podría simplificarse mediante otra hoja con reserva, pruebas y evidencia de preservación de `presupuesto-pr`.
- `.github/workflows/unattended-watchdog.yml`: el job `watchdog` comprueba actividad y degrada la salud operativa cuando corresponde; `daily-summary` envía reporte al dueño. El interruptor #767 únicamente pausa nuevas mutaciones; no reemplaza estas funciones ni `reusable-release-watchdog.yml`.

Hasta demostrar replacements con contratos equivalentes, ambos workflows quedan **quedarse / fase 0**. **Reversión:** revertir únicamente el PR de fase 1; recuperar los workflows programados y sus tests si se cambian. Ninguna publicación/live.

### Fase 2: quitar validadores de forma

**Rutas exactas:** `.github/workflows/etiquetas.yml`, `.github/workflows/etiquetas-pr.yml`, `.github/workflows/readme.yml`, `.github/workflows/roles.yml`. **Dependencias a revisar:** `scripts/labels_kit.py`, `scripts/pr_label_governance.py`, `scripts/sync_label_colors.py`, `scripts/roles_kit.py`, `tests/test_etiquetas_workflow_contract.py`, `tests/test_labels_kit.py`, `tests/test_sync_label_colors.py`, `tests/test_readme_contract.py`, `tests/test_readme_contract_v2.py`, `tests/test_roles_kit.py`, `tests/test_roles_workflow_contract.py`. Mantener etiquetas/roles y procedencia que sean **requisitos de autoridad de Coordinación**, hasta que la fase 4 los reemplace con pruebas equivalentes. Antes de retirar `roles.yml`, buscar en **los siete repositorios consumidores** sus referencias `uses: .../roles.yml@v1` y sus required checks (p. ej., `Validar evidencia de roles`), documentar el reemplazo en el PR y validar que ningún branch protection check quede ausente. La lista local de tests por sí sola no es prueba de compatibilidad.

**Reversión:** revertir el PR de fase 2 y reactivar los mismos reusable workflows; verificar los repos consumidores antes de volver a exigirlos.

### Fase 3: reducir política y release sin soltar puertas duras

**Rutas exactas:** `.github/workflows/aceptacion.yml`, `.github/workflows/automerge-construccion.yml`, `.github/workflows/politica.yml`, `.github/workflows/politica-comentario.yml`, `.github/workflows/release-window.yml`, `.github/workflows/release-bootstrap.yml`, `.github/workflows/reusable-release-watchdog.yml`, `scripts/politica_kit.py`, `scripts/release_window.py`, `scripts/release_bootstrap.py`, `scripts/automerge_construccion.py`, `scripts/aceptacion_kit.py`, `tests/test_politica_kit.py`, `tests/test_politica_workflow_contract.py`, `tests/test_release_window.py`, `tests/test_release_bootstrap_workflow.py`, `tests/test_automerge_construccion.py`, `tests/test_aceptacion_kit.py`. **No tocar** `.github/workflows/release.yml`, `.github/workflows/deploy.yml`, `.github/workflows/observar.yml`, `.github/workflows/seguridad.yml`, `.github/workflows/sonar.yml`, `.github/workflows/codeql-evidence.yml` ni CodeRabbit. Antes de simplificar, reconciliar #1295 y las decisiones humanas existentes.

**Reversión:** squash-revert solo de fase 3; restaurar el comportamiento previo de política y release, con pruebas de freeze, aceptación y go-live exact-SHA.

### Fase 4: reducir coordinación y el PLAN al final

**Rutas exactas:** `.github/workflows/coordinacion-trabajo.yml`, `scripts/coordinar_trabajo.py`, `tests/test_coordinar_trabajo.py`, `tests/test_coordinar_trabajo_unblock_validation.py`, `PLAN-AGENTES.md`, `agentes/NUCLEO.md`. Conservar `.github/workflows/coordinacion.yml` hasta tener reemplazo compatible y pruebas de reservas V3, claims disjuntos, rotación de UUID, carrera y recuperación segura. Los scripts `scripts/dispatcher_v2.py` y `scripts/dispatch_inventory.py` **no aparecen como llamadas directas de los 38 workflows actuales**; `PLAN-AGENTES.md`, `AGENTES.md`, `agentes/NUCLEO.md`, `README.md`, `docs/orquestador.md` y `scripts/orquestar_fabrica.py` tampoco contienen el nombre literal `dispatcher_v2`. Esto **no demuestra ausencia de consumidores externos**, así que no eliminarlos sin búsqueda de referencias en todos los consumidores y prueba negativa.

**Reversión:** squash-revert solo de fase 4 y restaurar protocolo, coordinación y prevención de colisiones. Toda fase conserva CI y la autoridad de #767; `main` protegido, no merges directos. Cada fase se propone como PR independiente con tests de sus consumidores antes de fusionarla.

## Revisión de cobertura y trade-offs

- **Fase 1 primero:** menor impacto en ruta de código y gasto; riesgo: consumidores de resúmenes silenciosamente rotos. Mitigar con búsqueda literal y tests de rutas antes de borrar.
- **Fase 2 después:** reduce fricción de forma, pero las etiquetas aún se usan como estado de coordinación; mantener intactas las exigencias de seguridad hasta fase 4.
- **Fase 3:** máxima mejora potencial del tiempo de entrega; riesgo alto de falsa autorización. No modificar privilegios, secretos, freezes ni puertas duras.
- **Fase 4 al final:** cambiar primero Coordinación crearía colisiones/duplicados; exigir preflight de lease y simulaciones de carreras.
- **Alternativa descartada:** borrar los 38 workflows o quitar tests de contrato sin reemplazo, porque no preserva compatibilidad ni una reversión verificable.

## Validación de este inventario

`python3 -m unittest tests.test_factory_diet_inventory -v` verifica cobertura del árbol, disparadores, scripts/test a revisar, preservación de puertas duras y orden/reversibilidad de las fases. Este inventario **no es evidencia de ejecución de ese comando** hasta obtener un run que lo confirme en el HEAD exacto.

## Ledger F1D de baja de Cabina

**Baseline post-F1C/runbook:** 34 workflows en `main@4544f63ef3aebddfcddda5f2e88ebe9870035f3f`. F1D retira solamente Cabina programada y deja 33 workflows; historial 38 → 36 → 35 → 34 → 33 workflows. Sin automatización horaria, `workflow_dispatch`, push-trigger de Cabina ni artefacto Pages automático. `scripts/cabina.py` y QA de Sentry permanecen offline. La decisión #35 es no publicar Pages **todavía** sin nueva autorización del dueño; ninguna exposición nueva.

| Baja | Workflow | Blob previo | Secuencia | Reversión |
| --- | --- | --- | --- | --- |
| F1D | `.github/workflows/cabina.yml` | `8fbbd85b5697a43d196223292961c77976d45f96` | 34 → 33 | squash-revert PR F1D |

Reversión: squash-revert solo del PR F1D, sin tocar F1A/F1B/F1C ni modificar publicación, secretos o producción. La pérdida de generación privada automática es deliberada; el motor sigue disponible offline.

## Ledger F2A de baja de Sync Label Colors

**Baseline F1D:** 33 workflows en `main@26c585070d1b8524f5b4562092f610c5c327de82`. F2A retira exclusivamente el disparador `sync-label-colors.yml`, quedando **32 workflows**; historial 38 → 36 → 35 → 34 → 33 → 32 workflows. Se pierde la invocación remota por comentario en #874 (`/sync-label-colors dry-run|apply`). No se modifican colores ni etiquetas reales, y se conserva `scripts/sync_label_colors.py` con su QA offline. Sin reemplazo remoto y sin ejecutar `--apply`.

| Baja | Workflow | Blob previo | Secuencia | Reversión |
| --- | --- | --- | --- | --- |
| F2A | `.github/workflows/sync-label-colors.yml` | `7005e0cddab8fe5dfc7635a05f3001cd61497d5f` | 33 → 32 | squash-revert PR F2A |

**Reversión:** squash-revert solo del PR F2A, independiente de las fases F1A/B/C/D. Mantener gates de seguridad, CI y autoridad.

## Ledger F1E de baja de Captura de lecciones

**Baseline tras F2A:** 32 workflows en `main@ae88faecaf228b376d8fd26d23ca1c012edd8873`. F1E retira exclusivamente el trigger `.github/workflows/captura-leccion.yml`: **31 workflows activos**, secuencia histórica **38 → 36 → 35 → 34 → 33 → 32 → 31**. El blob previo autenticado es `df7cdd904b9370600a897f174d28322e5a99d84e`. Los eventos `issues.closed` y `pull_request.closed` ya no generan candidatos automáticos; se conserva `scripts/captura_leccion.py` offline, sin reemplazo remoto. Las pruebas de identidad fail-closed y deduplicación sobreviven mediante una copia histórica del gate en `tests/test_captura_leccion_workflow.py`.

| Baja | Workflow retirado | Blob SHA previo | Transición | Reversión |
| --- | --- | --- | --- | --- |
| F1E | `.github/workflows/captura-leccion.yml` | `df7cdd904b9370600a897f174d28322e5a99d84e` | 32 → 31 | squash-revert PR F1E |

**Preflight:** árboles Git completos de los siete repos, sin callers literales en otros workflows; esa lectura no garantiza ausencia de automatizaciones externas. El check requerido de Factory es `Validar`, no Captura. Sin cambios de permisos, secretos, datos, etiquetas reales, release, despliegue ni go-live. **Reversión:** squash-revert solo del PR F1E restaura el disparador, tabla y QA originales sin afectar F1A/F1B/F1C/F1D/F2A.
