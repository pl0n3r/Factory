# Lista de salida a producción de Factory — corte verificable

> Corte de código: `Factory/main@9c12107bd64ef4bbc45b3baf4f961a6ce6f14664` (27-oct-2026), protegido. **Factory es un kit de automatización/reusable workflows, no un SaaS con web ni base propia.** Esta lista no ejecuta go-live, deploy, gastos, backups ni tratamientos reales.

## Método y criterios

- Una fila por requisito verificable, no por encabezado. `LISTO` se reserva a **implementación documental o de código + prueba citada** presente en el árbol exact-main, exclusivamente para la capacidad técnica descrita: no implica producción. `EN_CURSO` exige hoja ejecutable con contrato y rutas reclamadas o PR abierto; nunca basta épico/roadmap.
- `SIN_COBERTURA` identifica ausencia de implementación completa y contiene **hoja canónica creada** y su Issue. `DEL_DUEÑO` expresa autoridad externa, cuenta, gasto o decisión y no es tarea que el agente pueda ejecutar. `NO_APLICA` explica por qué el runtime del kit carece de esa superficie.
- Fuentes: `decisiones.yml` (D-054–D-070), `docs/resiliencia-fabrica.md`, `docs/release-runbook.md`, `docs/release-bootstrap.md`, `docs/reusable-release-rollback.md`, `docs/costos-presupuestos.md`, `docs/preview-preproduccion.md`, Issues #1082, #305, #304, #10, #12, #1080 y árbol de main. El observador real de cada consumidor sigue siendo la autoridad para su despliegue.

## Requisitos

| Área | ID / requisito | Estado | Evidencia y condición | Issue |
| --- | --- | --- | --- | --- |
| Respaldos y restauración | FSP-01 — Copia real 3-2-1-1-0 con offsite inmutable | `DEL_DUEÑO` | D-066/#305 no autorizan B2 real antes de la decisión live; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #305 |
| Respaldos y restauración | FSP-02 — Restauración aislada y hashes desde backup externo reciente | `DEL_DUEÑO` | #305 exige recibos reales; suite de fixtures no sustituye restore operativo; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #305 |
| Respaldos y restauración | FSP-03 — Contrato offline de recovery con manifest y validación | `LISTO` | Código recovery/contract.py y regresión tests/test_recovery_contract.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #305 |
| Respaldos y restauración | FSP-04 — Medición real de RPO/RTO y prueba de restauración cronometrada | `DEL_DUEÑO` | #305 no tiene mediciones productivas nuevas; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #305 |
| Respaldos y restauración | FSP-05 — Custodia offsite, retención y Object Lock con proveedor | `DEL_DUEÑO` | La cuenta B2 y el gasto permanecen bloqueados por D-066; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #305 |
| Monitoreo y alertas | FSP-06 — Observar la cola y fallar cerrado ante UNKNOWN | `LISTO` | Código scripts/salud_cola_observar.py y regresión tests/test_salud_cola_observar.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1082 |
| Monitoreo y alertas | FSP-07 — Contrato de alerta opt-in y antiflood sin escritura automática | `LISTO` | Código scripts/salud_cola_alertar.py y regresión tests/test_salud_cola_alertar.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1082 |
| Monitoreo y alertas | FSP-08 — Evidenciar alerta publicada y entregada a un destinatario | `DEL_DUEÑO` | #1082 AC-03 no tiene recibo de publicación real idempotente; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1082 |
| Monitoreo y alertas | FSP-09 — Definir guardia y escalamiento ante incidente de alta gravedad | `DEL_DUEÑO` | No existe confirmación de la persona operadora o turno de respuesta; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1082 |
| Dominios, DNS y TLS | FSP-10 — DNS y certificado de host web propio de Factory | `NO_APLICA` | NO_APLICA al runtime del kit Factory: el repo distribuye tooling y workflows, no una aplicación HTTP pública; la obligación en cada consumidor permanece. | — |
| Dominios, DNS y TLS | FSP-11 — Validar DNS/TLS de los productos consumidores | `DEL_DUEÑO` | Condor, GrindFlow, BRVTAL y ControlBot gestionan sus dominios; deben emitir observación por producto; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1082 |
| Dominios, DNS y TLS | FSP-12 — Gates de publicación del canal GitHub Factory@v1 | `LISTO` | Código scripts/release_bootstrap.py y regresión tests/test_release_bootstrap.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1080 |
| Secretos y accesos | FSP-13 — Auditoría de workflows y permisos mínimos | `LISTO` | Código seguridad/resiliencia.py y regresión seguridad/test_resiliencia.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #10 |
| Secretos y accesos | FSP-14 — Preview que no entrega secrets al código de PR | `LISTO` | Código scripts/preview_kit.py y regresión tests/test_preview_kit.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #10 |
| Secretos y accesos | FSP-15 — Cuenta de recuperación, custodia GitHub App y MFA/2FA | `DEL_DUEÑO` | docs/resiliencia-fabrica.md es runbook, no inventario de accesos efectivos; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #10 |
| Secretos y accesos | FSP-16 — Rotación y revocación de credenciales comprometidas | `DEL_DUEÑO` | Sin acceso real no existe recibo de rotación actual; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #10 |
| Costos y límites | FSP-17 — Límites de presupuesto de PR sin simular costo observado | `LISTO` | Código metricas/costos.py y regresión metricas/test_costos.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1082 |
| Costos y límites | FSP-18 — Límite de gasto operativo para CI, Hostinger y almacenamiento | `DEL_DUEÑO` | Ningún agente compra planes o provisiona B2 antes de decisión; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #305 |
| Costos y límites | FSP-19 — Presupuesto y veto por cuota API en release | `LISTO` | Código scripts/release_api_budget.py y regresión tests/test_release_api_budget.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1080 |
| Costos y límites | FSP-20 — Comparación real de costo y rendimiento con carga de agentes | `DEL_DUEÑO` | #304 solo permite evidencia sintética y no tiene BEFORE/AFTER real; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #304 |
| Privacidad y legal de lanzamiento | FSP-21 — Contrato documental de privacidad y licencias sin aprobación ficticia | `LISTO` | Código seguridad/cumplimiento.py y regresión seguridad/test_cumplimiento.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #12 |
| Privacidad y legal de lanzamiento | FSP-22 — Aprobación jurídica por tratamientos reales de cada producto | `DEL_DUEÑO` | D-063 permite preparación offline, no certifica legislación y terceros; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #12 |
| Privacidad y legal de lanzamiento | FSP-23 — Consentimiento y decisión de salida live | `DEL_DUEÑO` | Go-live y tratamiento de PII requieren puerta expresa, no un merge; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1082 |
| Privacidad y legal de lanzamiento | FSP-24 — Almacenar clientes reales en repositorio Factory | `NO_APLICA` | NO_APLICA al runtime del kit Factory: D-062 prohíbe PII, tokens y secretos en repos públicos; la obligación en cada consumidor permanece. | — |
| Soporte y operación diaria | FSP-25 — Manual de release con validación estructural | `LISTO` | Código docs/release-runbook.md y regresión tests/test_release_runbook_doc.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1080 |
| Soporte y operación diaria | FSP-26 — Responsable de guardia, soporte y SLA de atención | `DEL_DUEÑO` | No existe persona, horario y canal de respuesta acreditados; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1082 |
| Soporte y operación diaria | FSP-27 — Runbook de publicación con pruebas del flujo | `LISTO` | Código docs/release-bootstrap.md y regresión tests/test_release_bootstrap_workflow.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1080 |
| Soporte y operación diaria | FSP-28 — Simulacro humano de atención desde alerta hasta cierre | `DEL_DUEÑO` | Las pruebas unitarias no prueban respuesta real y escalamiento; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1082 |
| Migración de datos | FSP-29 — Migración de base de datos interna del runtime Factory | `NO_APLICA` | NO_APLICA al runtime del kit Factory: Factory no tiene base transaccional propia; la obligación en cada consumidor permanece. | — |
| Migración de datos | FSP-30 — Preview sintético del pipeline antes del merge | `LISTO` | Código scripts/preview_kit.py y regresión tests/test_preview_kit.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1082 |
| Migración de datos | FSP-31 — Backup, dry-run y reversión de migraciones de consumidores | `DEL_DUEÑO` | D-054/D-059 requieren backup antes de migraciones reales; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #305 |
| Migración de datos | FSP-32 — Mover datos reales entre proveedores cloud desde Factory | `NO_APLICA` | NO_APLICA al runtime del kit Factory: sin lanzamiento ni decisión sobre migración, el kit no mueve bases de clientes; la obligación en cada consumidor permanece. | — |
| Reversión y apagado de emergencia | FSP-33 — Interruptor global falla cerrado cuando no hay RUNNING | `LISTO` | Código scripts/unattended_kill_switch.py y regresión tests/test_unattended_kill_switch.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #767 |
| Reversión y apagado de emergencia | FSP-34 — Plan de rollback de reusable con test de regresión | `LISTO` | Código docs/reusable-release-rollback.md y regresión tests/test_reusable_release_rollback.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1080 |
| Reversión y apagado de emergencia | FSP-35 — Ejercitar reversión productiva de refs/tags/v1 | `DEL_DUEÑO` | Mover Factory@v1 exige operador administrativo y puerta humana, no solo CI; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1080 |
| Reversión y apagado de emergencia | FSP-36 — Contención documentada sin borrado de evidencia | `LISTO` | Código seguridad/resiliencia.py y regresión seguridad/test_resiliencia.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #10 |
| Seguridad y pruebas | FSP-37 — Política y control de revisión sobre PR | `LISTO` | Código tests/test_politica_workflow_contract.py y regresión .github/workflows/politica.yml existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1082 |
| Seguridad y pruebas | FSP-38 — Seguridad/privacidad con test que falla cerrado | `LISTO` | Código seguridad/cumplimiento.py y regresión seguridad/test_cumplimiento.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #12 |
| Seguridad y pruebas | FSP-39 — Dictamen final de todos los gates sobre SHA publicado | `DEL_DUEÑO` | El OWNER debe autorizar ventana release con Sonar y CodeQL terminales del candidato; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1080 |
| Seguridad y pruebas | FSP-40 — Watchdog de consumidores contra fallos de reusable | `LISTO` | Código scripts/reusable_release_watchdog.py y regresión tests/test_reusable_release_watchdog.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1080 |
| Accesibilidad y rendimiento | FSP-41 — WCAG de interfaz pública propia de Factory | `NO_APLICA` | NO_APLICA al runtime del kit Factory: Factory no sirve UI de consumidor final; la obligación en cada consumidor permanece. | — |
| Accesibilidad y rendimiento | FSP-42 — Benchmark sintético de CI/performance | `LISTO` | Código performance/ci_suite_benchmark.py y regresión tests/test_performance_ci_suite_benchmark.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #304 |
| Accesibilidad y rendimiento | FSP-43 — Prueba de carga concurrente de agentes con umbrales reales | `DEL_DUEÑO` | #304 no acredita carga de agentes reales ni métricas BEFORE/AFTER; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #304 |
| Accesibilidad y rendimiento | FSP-44 — Accesibilidad y tiempos bajo carga de los paneles consumidores | `DEL_DUEÑO` | Factory CI no observa accesibilidad de pantallas reales en otros repos; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1082 |
| Smoke de producción | FSP-45 — Smoke de pipeline con datos sintéticos en preview | `LISTO` | Código scripts/preview_kit.py y regresión tests/test_preview_kit.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1082 |
| Smoke de producción | FSP-46 — Observación de health con contrato fail-closed | `LISTO` | Código scripts/runtime_health.py y regresión tests/test_runtime_health.py existen en main@9c12107bd6; evidencia offline limitada, sin certificar efecto real. | #1082 |
| Smoke de producción | FSP-47 — Smoke real de seis consumidores tras cambio Factory@v1 | `DEL_DUEÑO` | Deben observarse SHA y versión reales tras publicación autorizada; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #1080 |
| Smoke de producción | FSP-48 — HTTP smoke del sitio web de Factory | `NO_APLICA` | NO_APLICA al runtime del kit Factory: el kit es una biblioteca/reusable, no tiene home/login ni dominio público propio; la obligación en cada consumidor permanece. | — |
| Continuidad de proveedores | FSP-49 — Distinguir indisponibilidad GitHub API, Actions y cuenta ChatGPT | `SIN_COBERTURA` | Hoja canónica #1553 creada con factory-plan-task y aceptación para este hueco; no hay implementación ni prueba fusionada; ver docs/resiliencia-fabrica.md. | #1553 |
| Continuidad de proveedores | FSP-50 — Detener mutaciones cuando la fuente de coordinación queda UNKNOWN | `SIN_COBERTURA` | Hoja canónica #1553 creada con factory-plan-task y aceptación para este hueco; no hay implementación ni prueba fusionada; ver docs/resiliencia-fabrica.md. | #1553 |
| Continuidad de proveedores | FSP-51 — Reanudar con nuevo origen autenticado, main/HEAD y reserva verificados | `SIN_COBERTURA` | Hoja canónica #1553 creada con factory-plan-task y aceptación para este hueco; no hay implementación ni prueba fusionada; ver docs/resiliencia-fabrica.md. | #1553 |
| Continuidad de proveedores | FSP-52 — Backups independientes de GitHub y acceso a identidades alternativas | `DEL_DUEÑO` | D-066 y #10 requieren proveedor, custodia y verificación externa; exige actuación y recibo auténtico del OWNER. No se declara ejecución o go-live. | #305 |

## Resumen final

| Estado | Filas |
| --- | ---: |
| LISTO | 21 |
| EN_CURSO | 0 |
| SIN_COBERTURA | 3 |
| DEL_DUEÑO | 22 |
| NO_APLICA | 6 |
| **TOTAL** | **52** |

**Hojas canónicas nuevas creadas por esta auditoría: 1.** [#1553](https://github.com/pl0n3r/Factory/issues/1553), continuidad offline de GitHub/ChatGPT; filas FSP-49, FSP-50, FSP-51. No se crearon hojas de soporte o backup ficticias: las puertas reales ya corresponden a #305/#304/#1082 y al OWNER.

## Qué impide go-live hoy

- **3-2-1-1-0 auténtico / RPO/RTO:** falta offsite/cuenta aprobada por D-066 y restore real comprobable (#305); el contrato offline no los acredita.
- **Autoridad de publicación:** OWNER debe abrir ventana protegida, aprobar SHA/versión y mover conscientemente Factory@v1 conforme a `docs/release-runbook.md`; un PR verde no publica.
- **Operación real:** falta acreditar recepción efectiva de alertas, guardia/SLA, cargas de agentes, smoke pospublicación y restauración con evidencia externa.
- **Gobierno y legal:** cada consumidor debe acreditar HTTPS, accesibilidad, privacidad, manejo de datos, backups y autorización go-live según sus contratos.
- **Continuidad técnica:** hoja #1553 cubre el procedimiento fail-closed ante GitHub o ChatGPT no disponibles; hasta integrarse, las filas de ese alcance permanecen `SIN_COBERTURA`.
- **Costo / accesos:** no provisionar B2, contratar proveedores ni rotar credenciales reales sin autorización del OWNER y recibos.

**Resultado:** 52 requisitos evaluados en 13 áreas, 21 capacidades técnicas listas en código/contrato y 22 puertas expresamente externas. La lista no constituye una declaración de `VALIDATED_IN_PRODUCTION`; revisar evidencias antes del lanzamiento y tras cualquier cambio de `main`.
