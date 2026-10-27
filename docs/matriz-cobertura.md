# Matriz de cobertura de requisitos de Factory

> Corte 27-oct-2026 · SHA auditado: `main@8088e66c2366f2483d5229fc6fda8718f1ab46a0` · [#1550](https://github.com/pl0n3r/Factory/issues/1550) · V3 `999577a6-9986-4495-8049-bb120d0583e1`.

## Método y semántica

La extracción usa **unidades identificables de comportamiento, contrato o límite**, no encabezados: listas operativas y cláusulas con predicados normativos. Los IDs `ruta:LNN-UM` señalan línea y unidad separada por punto o punto y coma bajo el SHA inmutable. La tabla de fuentes enumera 103 archivos Markdown vigentes de `docs/` más `AGENTES.md`, sin inventar filas «documento presente». Los títulos, índices y snippets en bloques de código no son requisitos. Este extractor no reemplaza una revisión humana completa de cláusulas complejas o de contexto.

## Contraste de comportamientos #1561

Las cláusulas de `docs/inventario-tecnico-datos-productos.md`, `docs/arquitectura-tecnica.md` y `docs/admin-staff-api.md` se agrupan por contratos `Bnn` verificables en [contraste de datos y arquitectura](contraste-matriz-datos_arq.md), sin perder el inventario histórico de cláusulas del snapshot #1550. Los conteos de **Inventario de fuentes** permanecen anclados al censo original; las **Filas de cobertura** reflejan ahora 11 comportamientos de estas tres fuentes y las filas históricas intactas de las restantes 101 fuentes. `NO_VERIFICABLE` no implica ausencia ni permite inventar backlog. `CUBIERTO` solo acredita la porción exacta del template o script citado y un PR fusionado.

`CUBIERTO` requiere código + prueba + PR MERGED pertinente; `EN_CURSO` exige issue con `factory-plan-task` ejecutable y claims o PR abierto, **no** un épico/roadmap; `SIN_COBERTURA` obliga a hoja nueva real en el registro y evidencia de ausencia; `DESCARTADO` requiere decisión del OWNER; `NO_VERIFICABLE` significa insuficiencia de prueba, sin inferir que falte funcionalidad. El enlace al epic es referencia documental, no ejecutabilidad. Nadie ha autorizado backup B2/live, go-live, seguridad jurídica ni eliminar puertas de release.

## Contraste de comportamientos #1562

Las 305 cláusulas fragmentarias del censo histórico de `docs/auditoria-pre-v1.md`, `docs/release-bootstrap.md`, `docs/readme-progress-readiness.md`, `docs/readme-contract.md` se reemplazan en las filas operativas por 17 comportamientos con IDs `Bnn`, contrastados en [pre-v1, release y README](contraste-matriz-prev1_release.md). El inventario #1550 y sus conteos por fuente siguen históricos, no se reescriben. Cinco comportamientos de biblioteca/validadores README tienen código + prueba + PR MERGED verificados; ninguno implica release actual, protección administrativa de `v1`, validación de consumidores ni go-live. Ante evidencia incompleta se conserva `NO_VERIFICABLE`, sin crear hojas ficticias.

## Contraste de comportamientos #1565

Se sustituyen 201 fragmentos de cinco fuentes unattended por **20 comportamientos** en [contraste unattended](contraste-matriz-unattended.md): 15 CUBIERTO y 5 NO_VERIFICABLE. F1G retiró cron/job diario; el motor offline no implica entrega activa. El inventario original #1550 y las otras fuentes permanecen intactos.

## Contraste de comportamientos #1564

241 cláusulas de Living (84), Runner (63), dieta (59), Lab (35) agregadas como 23 contratos. Véase [contraste Living Runner](contraste-matriz-living_runner.md). El censo original permanece anclado, los demás contrastes están intactos, y no se autoriza go-live.

## Inventario de fuentes

| Fuente | Unidades |
| --- | ---: |
| `docs/aceptacion-ejecutable.md` | 25 |
| `docs/adaptive-orchestration.md` | 10 |
| `docs/admin-staff-api.md` | 51 |
| `docs/ai-gateway.md` | 8 |
| `docs/arquitectura-tecnica.md` | 87 |
| `docs/auditoria-pre-v1.md` | 96 |
| `docs/automerge-construccion.md` | 39 |
| `docs/autonomy-engine.md` | 12 |
| `docs/capability-authority.md` | 9 |
| `docs/context-compiler.md` | 12 |
| `docs/conversacion-agentes.md` | 28 |
| `docs/coordinacion-pr-validation.md` | 22 |
| `docs/costos-presupuestos.md` | 11 |
| `docs/cumplimiento-datos-licencias.md` | 13 |
| `docs/derived-views.md` | 21 |
| `docs/dieta-factory.md` | 59 |
| `docs/dod-compiler.md` | 24 |
| `docs/evaluacion-agentes.md` | 17 |
| `docs/evolution-engine.md` | 10 |
| `docs/experience-guardrails.md` | 22 |
| `docs/f2-caller-migration.md` | 8 |
| `docs/factory-lab.md` | 35 |
| `docs/factory-living-software.md` | 84 |
| `docs/factory-queue.md` | 20 |
| `docs/factoryrunner-execution-plane.md` | 63 |
| `docs/feedback-mesh-e2e.md` | 18 |
| `docs/fitness-engine.md` | 15 |
| `docs/growth-pruning.md` | 21 |
| `docs/immune-repair.md` | 34 |
| `docs/inventario-tecnico-datos-productos.md` | 183 |
| `docs/issue-contract-preflight.md` | 8 |
| `docs/knowledge-lifecycle.md` | 27 |
| `docs/knowledge-operations-e2e.md` | 9 |
| `docs/knowledge-operations.md` | 22 |
| `docs/knowledge-postmortem.md` | 12 |
| `docs/knowledge-selection.md` | 3 |
| `docs/label-color-sync.md` | 22 |
| `docs/lease-phase-a-artifact-qa.md` | 8 |
| `docs/liberacion-automatica-de-reservas.md` | 86 |
| `docs/living-software-operational-e2e.md` | 22 |
| `docs/memoria-institucional.md` | 11 |
| `docs/no-work-dedup.md` | 33 |
| `docs/observador-reservas-consumidor.md` | 22 |
| `docs/organizational-complexity.md` | 29 |
| `docs/orquestador.md` | 65 |
| `docs/performance-brvtal.md` | 12 |
| `docs/performance-ci-professional-report.md` | 6 |
| `docs/performance-ci-suite-benchmark.md` | 7 |
| `docs/performance-classification.md` | 6 |
| `docs/performance-classifier.md` | 6 |
| `docs/performance-contract.md` | 16 |
| `docs/performance-detection.md` | 7 |
| `docs/performance-engineering.md` | 6 |
| `docs/performance-github-actions-ci.md` | 7 |
| `docs/performance-grindflow.md` | 15 |
| `docs/performance-remediation.md` | 17 |
| `docs/performance-team-compiler-bridge.md` | 1 |
| `docs/politica-revisor-externo.md` | 53 |
| `docs/portfolio-signals.md` | 21 |
| `docs/pr-label-governance.md` | 18 |
| `docs/preview-preproduccion.md` | 12 |
| `docs/principios-construccion.md` | 31 |
| `docs/project-dna.md` | 13 |
| `docs/provisioning.md` | 16 |
| `docs/puertas-humanas-lenguaje-simple.md` | 15 |
| `docs/puertas-humanas.md` | 57 |
| `docs/quality-contract.md` | 8 |
| `docs/quality-engineering.md` | 7 |
| `docs/quality-gates.md` | 4 |
| `docs/quality-health.md` | 32 |
| `docs/quality-project-dna.md` | 10 |
| `docs/quality-regression.md` | 21 |
| `docs/quality-sonar-watch.md` | 23 |
| `docs/quality-sonar.md` | 21 |
| `docs/readme-contract.md` | 47 |
| `docs/readme-progress-readiness.md` | 79 |
| `docs/reconciliacion-issues-20261024.md` | 8 |
| `docs/recovery-adapters.md` | 11 |
| `docs/recovery-contract.md` | 3 |
| `docs/recovery-drill.md` | 1 |
| `docs/recovery-e2e.md` | 5 |
| `docs/recovery-pipeline.md` | 4 |
| `docs/recovery-status.md` | 12 |
| `docs/release-bootstrap.md` | 83 |
| `docs/release-runbook.md` | 22 |
| `docs/resiliencia-fabrica.md` | 29 |
| `docs/retroalimentacion-producto.md` | 22 |
| `docs/reusable-permission-compat.md` | 10 |
| `docs/reusable-release-rollback.md` | 29 |
| `docs/risk-compiler.md` | 12 |
| `docs/roles-profesionales.md` | 19 |
| `docs/sonar-superseded-ce.md` | 9 |
| `docs/tanda1-handoff.md` | 10 |
| `docs/unattended-daily-summary.md` | 38 |
| `docs/unattended-handoff-consumer-pack.md` | 24 |
| `docs/unattended-kill-switch.md` | 20 |
| `docs/unattended-runtime-guards.md` | 44 |
| `docs/unattended-safe-mode-drill.md` | 28 |
| `docs/unattended-safe-mode.md` | 53 |
| `docs/unattended-state-source.md` | 18 |
| `docs/unattended-watchdog-runtime.md` | 32 |
| `docs/unattended-watchdog.md` | 34 |
| `docs/lista-salida-produccion.md` | 16 |
| `AGENTES.md` | 51 |

## Filas de cobertura

| ID de requisito | Requisito verificable | Estado | Evidencia / condición no acreditada | Hoja |
| --- | --- | --- | --- | --- |
| `docs/aceptacion-ejecutable.md:L5-U1` | **gates genéricos**, como lint, tests globales, coordinación, CodeQL y Sonar; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L6-U1` | **criterios específicos del Issue**, definidos como `AC-NN` y verificados por el job `Criterios de aceptación`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L8-U1` | Un PR no está “hecho” si solo pasa la primera capa. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L12-U1` | El Issue debe contener exactamente una sección no vacía para: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L14-U1` | `### Contexto`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L15-U1` | `### Alcance`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L16-U1` | `### Fuera de alcance`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L17-U1` | `### Criterios de aceptación`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L18-U1` | `### Contrato ejecutable`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L22-U1` | `- [ ] [AC-01] descripción verificable` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L37-U1` | Los IDs del marker deben coincidir exactamente con los IDs humanos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L41-U1` | Solo acepta un target con forma: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L45-U1` | La ruta debe vivir en un directorio de tests permitido (`tests/`, `metricas/`, `seguridad/`, `lecciones/` o `producto/`), ser relativa y segura. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L49-U1` | Exige un check run del mismo SHA con nombre exacto y conserva la selección del ID más reciente por nombre. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L49-U2` | nunca cuenta como éxito. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L49-U3` | Un check `completed` solo satisface el criterio con `conclusion=success` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L51-U1` | `Validar` y `Criterios de aceptación` no pueden referenciarse como evidencia para evitar ciclos/autovalidación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L57-U1` | `Lint + Tests + Coordinación → Criterios de aceptación → Validar` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L59-U1` | La espera solo vuelve a leer check-runs: **no vuelve a ejecutar** workflows, jobs ni tests del consumidor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L59-U2` | Un fallo terminal distinto de evidencia pendiente aborta de inmediato y el timeout falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L61-U1` | Los criterios `kind=test` no se ejecutan durante ese preflight. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L67-U1` | `.github/ISSUE_TEMPLATE/trabajo.yml` exige las cinco secciones y `config.yml` deshabilita blank issues. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L71-U1` | Los PR históricos abiertos deberán migrar su Issue al contrato cuando vuelvan a sincronizarse con `main`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L71-U2` | No se fabrican criterios retrospectivos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/aceptacion-ejecutable.md:L71-U3` | al retomar cada Issue se documenta el comportamiento que realmente debe probarse. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L6-U1` | puede continuar, paralelizar o debe fallar cerrado. **ControlBot**, o el runtime | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L12-U1` | Una Session solo cuenta como | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L15-U1` | ausente o capacidad no fresca nunca se interpretan como healthy/free. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L33-U1` | pura entre `keep`, `replan` y `fail_closed`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L41-U1` | El fence exige coincidencia exacta antes de consultar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L47-U1` | Solo retiene replans no críticos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L49-U1` | `replan` no equivale a preemption: `pause_allowed` solo es true cuando el | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L56-U1` | siguiente E2E del épico #260 debe componer Presence → Replan → Fencing usando | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L63-U1` | Presence y Fencing únicamente aportan razones de readiness y metadata atribuible | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/adaptive-orchestration.md:L67-U1` | Una Presence unknown o stale, o un Fencing fail_closed, excluye candidatos antes | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/admin-staff-api.md:B01` | El template de administración remota incluye solo staff/admin y prohíbe exportación masiva y borrado físico. | CUBIERTO | `template/ops/admin-staff-api.json`; `tests/test_admin_staff_contract.py`; [#186](https://github.com/pl0n3r/Factory/pull/186) · `64f1901e456ac5bedae4be6f4c8ef575eccc190f` | — |
| `docs/admin-staff-api.md:B02` | El template exige HMAC-SHA256 por producto, TLS y rutas ausentes 404 sin clave/allowlist. | CUBIERTO | `template/ops/admin-staff-api.json`; `tests/test_admin_staff_contract.py`; [#186](https://github.com/pl0n3r/Factory/pull/186) · `64f1901e456ac5bedae4be6f4c8ef575eccc190f` | — |
| `docs/admin-staff-api.md:B03` | Mutaciones de staff requieren idempotencia separada del nonce/replay y protección de owner/root. | CUBIERTO | `template/ops/admin-staff-api.json`; `tests/test_admin_staff_contract.py`; [#186](https://github.com/pl0n3r/Factory/pull/186) · `64f1901e456ac5bedae4be6f4c8ef575eccc190f` | — |
| `docs/admin-staff-api.md:B04` | Los adapters de producto deben hacer cumplir en ejecución la prohibición de acceso a clientes y autoridades protegidas. | NO_VERIFICABLE | Requiere pruebas negativas cross-repo en SHA exactos; la existencia del schema portable no las sustituye. | — |
| `docs/ai-gateway.md:L3-U1` | provider/model nunca forman parte de la prioridad del WorkItem. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/ai-gateway.md:L9-U1` | Si ningún adapter cumple todo, falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/ai-gateway.md:L11-U1` | Fallback solo ocurre ante `unavailable` o `rate_limited`, queda registrado en `route_trace` y está limitado por `max_attempts`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/ai-gateway.md:L11-U2` | Un fallback nunca puede saltarse budget, quality, security, data policy o authority. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/ai-gateway.md:L13-U1` | Cada éxito registra provider/model/executor, venture/project, costo, evidence refs y un payload compatible con `producto.feedback.validate_execution_feedba | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/ai-gateway.md:L15-U1` | Un adapter `codex` exige `governed=true` y workspace igual a `repository_ref`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/ai-gateway.md:L15-U2` | Así Codex/CLI sigue siendo un adapter gobernado de Factory/FactoryRunner, nunca un canal paralelo `ControlBot → shell/model`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/ai-gateway.md:L17-U1` | credenciales deberán entrar únicamente por el execution plane autorizado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/arquitectura-tecnica.md:B01` | La coordinación de una tarea V3 parcial no cierra indebidamente su roadmap padre. | CUBIERTO | `scripts/coordinar_trabajo.py`; `tests/test_coordinar_trabajo.py`; [#1414](https://github.com/pl0n3r/Factory/pull/1414) · `67994aafbb5d2ce0e802dcb65a3dd1b1d46bd425` | — |
| `docs/arquitectura-tecnica.md:B02` | Reusable workflows deben rechazar eventos privilegiados antes del checkout y mantener mínimos permisos. | NO_VERIFICABLE | Hay prueba parcial, pero no se acreditó el set completo de reusables y un PR común pertinente. | — |
| `docs/arquitectura-tecnica.md:B03` | Releases y deploys deben respetar rollback, gates y autorización de tag `v1`. | NO_VERIFICABLE | No se confirma cadena end-to-end de publicación/rollback; no mover `@v1`. | — |
| `docs/arquitectura-tecnica.md:B04` | Separar ControlBot, FactoryRunner y productos en planos con autoridad limitada y sin credenciales compartidas. | NO_VERIFICABLE | Una descripción de arquitectura no demuestra las autorizaciones vigentes de los consumidores. | — |
| `docs/automerge-construccion.md:L5-U1` | Factory #1295 reduce las señales de calidad que bloquearían un merge durante `construccion` sin autorizar cambios a `main`, al workflow real de CI ni al ca | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L9-U1` | Fuente: evidencia de GitHub API autenticada y completa, con repositorio, número de PR, HEAD, base y main exactos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L9-U2` | se vuelve a leer antes del informe. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L9-U3` | Rechazar identidades duplicadas, paginación incompleta, deriva de SHA y registros malformados. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L10-U1` | Gates en `construccion`: el check de CI `validate`/`Validar` debe estar terminal `success`, con HEAD exacto | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L10-U2` | la evidencia de seguridad y las puertas duras siguen obligatorias. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L10-U3` | Aceptación, coordinación, claims V3 de *informe* (no la autoridad de reserva), rondas CodeRabbit/Policy, `CHANGES_REQUESTED` no grave e hilos no graves pas | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L10-U4` | No se exige `APPROVED` independiente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L10-U5` | Los hallazgos graves —bugs o vulnerabilidades `high`/`critical` en código nuevo de SonarCloud, CodeQL o CodeRabbit— bloquean | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L10-U6` | hallazgos menores se documentan como deuda. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L11-U1` | Estado global: leer Factory#767 al comenzar y al terminar la captura, con un único marker válido `RUNNING` y owner autorizado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L11-U2` | `PAUSED` o `UNKNOWN` invalida el resultado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L11-U3` | Kill switch `RUNNING` no salta límites 4B. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L12-U1` | Seguridad: el `freeze` activo, el kill switch distinto de RUNNING, permisos, reservas V3 de escritura inválidas, branch protection, gasto, datos reales, de | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L12-U2` | Las rutas sensibles siguen en revisión protectora del diagnóstico | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L12-U3` | cuota insuficiente, fuente de calidad incompleta o desfasada, snapshot parcial o datos vencidos implican `eligible=false` o `UNKNOWN`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L12-U4` | Ningún aviso bajo de Sonar permite neutralizar un finding grave. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L13-U1` | Los datos de entrada no se consideran confiables por venir de un evento de PR. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L13-U2` | El observador no ejecuta código del HEAD del PR ni acepta snapshots suministrados por el autor como autoridad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L17-U1` | Ejecutar solo con evento de PR **no privilegiado**, permisos de lectura mínimos, timeout y concurrencia acotados | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L17-U2` | nada de `pull_request_target`, `workflow_run`, `issue_comment` o `repository_dispatch` para ejecutar código del PR. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L18-U1` | Recopilar evidencia completa sin registrar cuerpos de comentarios, tokens, cabeceras de autorización, secretos, correos, contenido de Issues ni datos reale | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L18-U2` | Fallar cerrado ante 403/429, incertidumbre o presupuestos desconocidos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L18-U3` | no reintentar en bucle. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L19-U1` | Alimentar al evaluador solo si se demuestra identidad exact-SHA y frescura. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L19-U2` | Un resultado `eligible_diagnostic_only` **jamás** llama a `merge`, `enablePullRequestAutoMerge`, `update-branch` ni escribe en Issues/PRs/checks. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L20-U1` | Emitir reporte JSON acotado con `repository`, `pr_number`, `head_sha`, `eligible` y `reason` de vocabulario fijo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L20-U2` | Ante entrada no verificable, usar `eligible=false`, `reason=incomplete_evidence` sin volcar el payload de la excepción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L21-U1` | Volver a validar kill switch e identidades antes de mostrar un diagnóstico positivo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L21-U2` | Si alguna lectura falla, emitir únicamente resultado denegado y salir sin side effects. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L25-U1` | Los cinco tests `AutoMergeWorkflowTests::test_*` del Issue #1143 deben reproducir casos positivos y negativos **sin red**, incluidos doble evento, SHA camb | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L25-U2` | La evidencia de CI debe ser terminal sobre el HEAD exacto del PR y registrar los roles QA/seguridad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L31-U1` | **Diagnóstico no es enforcement.** Los workflows existentes `.github/workflows/factory-ci.yml` y `.github/workflows/politica.yml`, la protección de rama qu | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L31-U2` | Si el actual `Validar` agregado depende de aceptación/coordinación, un fallo sigue bloqueando la fusión real hasta que un cambio autorizado y probado recon | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L33-U1` | La evidencia de severidad debe ser completa, autenticada, exact-HEAD y cubrir SonarCloud, CodeQL y CodeRabbit. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L33-U2` | Si falta, está rate-limited, incompleta o tiene tipos inválidos, el diagnóstico falla cerrado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L33-U3` | no se puede traducir silencio en «cero hallazgos». | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L35-U1` | **Deuda pre-live obligatoria:** antes de cualquier decisión de go-live, revisar y limpiar la deuda pendiente de Sonar y CodeRabbit y volver a ejecutar todo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/automerge-construccion.md:L35-U2` | Se conserva siempre la decisión humana de despliegue/release, el freeze exact-SHA, dinero, datos reales y borrado irreversible. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L8-U1` | Una capacidad solo puede recorrer, de a un nivel: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L17-U1` | Una promoción exige: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L19-U1` | Fitness completo, sin dimensiones faltantes ni regresiones protegidas; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L20-U1` | claim `equal` o `improved`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L21-U1` | Risk con contexto crítico completo; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L22-U1` | evidencia no vacía. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L24-U1` | El nivel `autonomous` no se concede con riesgo `high`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L28-U1` | Los fallos nunca se esconden: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L30-U1` | `minor`: baja un nivel; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L31-U1` | `major`: baja dos niveles; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L32-U1` | `critical`: revoca hasta `observe`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/autonomy-engine.md:L34-U1` | la historia previa no se modifica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L5-U1` | nunca crea acciones, scopes, targets ni clases de autoridad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L16-U1` | disparar menos autonomía o revocación, nunca más permisos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L18-U1` | Cuando una acción recibe varios grants, `scopes` y `targets` agregados son solo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L19-U1` | La autoridad verificable vive en `bindings`, que | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L21-U1` | el resumen como un producto cartesiano. `authorize()` evalúa siempre el grant | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L22-U1` | exacto y falla cerrado ante combinaciones no concedidas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L26-U1` | Los grants y revocaciones se aceptan únicamente desde | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L39-U1` | `CapabilityAuthorityRegistry.autonomy_scope()` acepta únicamente los niveles | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/capability-authority.md:L42-U1` | nunca agregan permisos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L4-U1` | Project DNA ya validado, la tarea actual y decisiones/lecciones previamente | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L11-U1` | `project_dna` validado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L12-U1` | una `task` cerrada con id, título, objetivo y tags; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L13-U1` | `context` relevante con categoría, fuente, texto y tags; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L14-U1` | límites explícitos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L15-U1` | fingerprint SHA-256 determinista. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L17-U1` | Solo entran piezas cuyo conjunto de tags intersecta los tags de la tarea. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L23-U1` | El compilador falla cerrado ante claves sensibles como tokens, passwords, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L32-U1` | máximo 12 piezas de contexto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L33-U1` | máximo 1200 caracteres por texto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L34-U1` | máximo 12000 caracteres para el paquete serializado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/context-compiler.md:L35-U1` | sin I/O, sin mutación del proyecto y sin decisión de riesgo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L7-U1` | Solo en transiciones significativas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L11-U1` | `Encontré que el fallo viene del wiring de test, no del transporte productivo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L11-U2` | Ahora valido el contenedor en APP_ENV=test.` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L12-U1` | `Backend y Validar ya están verdes | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L12-U2` | solo falta Playwright. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L12-U3` | Mientras corre, reviso el flujo nuevo para detectar fallos lógicos.` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L13-U1` | `El enfoque A falló por X. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L13-U2` | Cambio al enfoque B porque evita Y.` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L15-U1` | Prohibidas: `Sigo revisando.`, `Déjame pensar.`, `Estoy trabajando en eso.` y repetir `voy a revisar...` sin hallazgo nuevo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L39-U1` | Debe conservar: objetivo, repo/Issue/PR, branch y SHA, decisiones tomadas, hallazgos confirmados, intentos fallidos que no deben repetirse, checks pendient | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L43-U1` | No reexplicar lo ya presente en Issue/PR/`lecciones/`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L44-U1` | Buscar primero | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L44-U2` | abrir solo fragmentos relevantes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L45-U1` | Agrupar lecturas independientes en paralelo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L46-U1` | Sin polling: una lectura terminal de CI y más solo ante fallo o transición real. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L47-U1` | Resultado primero, detalle después | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L47-U2` | hitos en 3–7 líneas salvo petición. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L48-U1` | No duplicar en el chat lo registrado en GitHub. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L57-U1` | Lo de la segunda fila no se resuelve solo con instrucciones: si la integración es nuestra, se evalúa allí. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L65-U1` | **No es un fallo:** no reenviar el mensaje, no abrir otro chat y no cancelar mientras el aviso esté visible | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L65-U2` | una sola espera, luego continuar. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L66-U1` | **Reducir disparadores:** pedir una sola tarea acotada por turno | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L66-U2` | no pegar secretos, tokens ni volcados grandes de logs/salida (resumir y citar solo el fragmento relevante) | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L66-U3` | no encadenar ejecuciones de código innecesarias | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L66-U4` | describir la finalidad defensiva/operativa de cualquier comando de seguridad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L67-U1` | **Si se repite en el mismo chat:** escribir una nota `STATE`, continuar en un chat nuevo de la misma cuenta desde ella y anotar el hallazgo en el Issue. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L69-U1` | Requiere Issue propio. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/conversacion-agentes.md:L73-U1` | `tests/test_conversacion_agentes.py` comprueba que trae todos los campos y que un agente puede reanudar solo con ella (objetivo, SHA, fallos a no repetir y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L5-U1` | La coordinación valida cada PR mientras está abierto: rama canónica, relación con | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L8-U1` | `Closes #N`, GitHub puede cerrar el Issue antes de que una revalidación tardía | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L9-U1` | volver a exigir entonces que el Issue siga abierto produce un falso rojo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L14-U1` | El evento de merge es terminal para el gate `validar-pr`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L16-U1` | El caller canónico conserva `pull_request: closed`, porque `pr-event` todavía | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L17-U1` | debe reconciliar la reserva y el estado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L18-U1` | El caller usa `validar-pr-evento` como precondición: ese job solo completa | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L19-U1` | cuando `github.event.pull_request.merged != true`. `validar-pr` conserva | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L21-U1` | llega a invocar `operation: validate`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L22-U1` | El reusable aplica la misma defensa: una llamada `validate` originada por un | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L24-U1` | Un cierre **sin merge** tiene `merged == false` y no recibe esta excepción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L27-U1` | Mantener la forma legacy de `validar-pr` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L29-U1` | `closed` por sí solo nunca se convierte en autoridad para saltarse validaciones. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L33-U1` | La neutralidad post-merge no cambia `validate_pull()`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L34-U1` | siga abierto, el coordinador conserva el comportamiento fail-closed existente: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L35-U1` | el Issue debe estar abierto, la branch debe ser `trabajo/issue-N`, la reserva y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L36-U1` | su identidad deben ser válidas, la relación de cierre debe corresponder y no | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L40-U1` | `Issue #N debe estar abierto durante el PR`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L47-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L48-U1` | `tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L49-U1` | `tests/test_coordinar_trabajo.py::CoordinacionTests::test_open_pr_with_closed_issue_still_fails_closed`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/coordinacion-pr-validation.md:L52-U1` | La reversión es un revert de estos cambios declarativos y no requiere migración | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L5-U1` | El agente que abre un PR declara únicamente métricas numéricas y clasificación, nunca el contenido del prompt ni secretos: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L13-U1` | Mientras tokens, minutos de CI, minutos de agente o rondas solo estén autodeclarados, el resultado no puede presentarse como completamente verificado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L15-U1` | `ok`: reservado para una evaluación completamente observada y por debajo de 80 % | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L15-U2` | con la telemetría actual no se emite a partir de datos autodeclarados; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L16-U1` | `warning`: al menos una dimensión está entre 80 % y 100 %; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L17-U1` | `soft-block`: falta medición o alguna dimensión supera 100 %. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L19-U1` | Un marker malformado falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L19-U2` | Un PR dentro de límites pero con dimensiones solo declaradas permanece en `warning` con señales `unverified:*` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L19-U3` | así no se confunde una estimación con costo observado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L27-U1` | Un `run_id` duplicado falla cerrado para evitar doble conteo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/costos-presupuestos.md:L29-U1` | F1F no acredita ningún informe mensual nuevo ni ahorro cuantificado de API/CI. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L7-U1` | El script `seguridad/cumplimiento.py` comprueba que un producto tenga un inventario documental *referenciado* y que las dependencias de sus archivos de blo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L15-U1` | `evidence` exige siete referencias no sensibles a evidencias revisadas: `privacy_policy`, `terms`, `processing_register`, `rights_channel`, `retention_sche | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L15-U2` | El validador rechaza campos adicionales y revisiones con más de 365 días conforme a la **política interna de refresco**, no a un plazo legal general. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L17-U1` | **Importante:** `exception_for_legal_review` solo deja constancia de que una excepción fue planteada: no autoriza tratar datos por sí sola. `consent_docume | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L17-U2` | El responsable debe contrastar evidencias y hechos del producto antes de activar producción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L21-U1` | El CLI no acepta rutas arbitrarias. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L21-U2` | La evidencia de privacidad entra por `stdin`, por lo que su ubicación privada nunca se pasa como argumento. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L36-U1` | Las pruebas propias son `PYTHONPATH=seguridad python3 -m unittest discover -s seguridad -p 'test_cumplimiento.py'`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L37-U1` | `seguridad.yml` ya ejecuta `unittest discover -s seguridad -p 'test_*.py'` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L37-U2` | al integrar este slice, las regresiones de cumplimiento quedan dentro de `Validar puertas del candidato` sin modificar el workflow. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L38-U1` | Cada proyecto debe aportar al menos una evidencia documentada y verificada por tratamiento y los archivos lock reales de su stack. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L38-U2` | Un fixture de tests **no** es prueba de cumplimiento de ningún producto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/cumplimiento-datos-licencias.md:L39-U1` | Cierre de #12 requiere CI y evidencia de la revisión material, no únicamente la estructura o la salida del script. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L3-U1` | Una vista derivada **nunca es una fuente de verdad**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L3-U2` | la vista solo materializa o verifica esa información. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L9-U1` | `view_id`: identificador estable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L10-U1` | `source`: fuente canónica y sus referencias. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L11-U1` | `view`: superficie derivada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L12-U1` | `mode`: `generated` si existe un generador seguro, o `regression` cuando la fuente todavía no puede consumirse de forma segura. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L13-U1` | `generator`: función determinista obligatoria para `generated`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L14-U1` | `drift_check`: test/guard que impide publicar una vista divergente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L18-U1` | Un generador debe ser una función pura: sin red, reloj, aleatoriedad ni estado mutable externo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L18-U2` | La misma instantánea normalizada de la fuente debe producir exactamente los mismos bytes, incluido orden, columnas y saltos de línea. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L24-U1` | El guard compara la salida esperada con la vista comprometida y falla cerrado ante cualquier diferencia. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L24-U2` | No se debe “arreglar” la fuente para hacer pasar el check ni aceptar la vista como nueva fuente canónica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L28-U1` | La regresión debe comprobar claims concretos contra la fuente canónica y señalar qué dato cambiaría si la fuente cambia. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L28-U2` | Esto permite proteger una vista mientras se evita inventar una extracción estructurada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L34-U1` | no debe convertir el README en fuente de verdad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L38-U1` | Identifique la fuente canónica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L39-U1` | Registre la vista en el manifiesto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L40-U1` | Elija `generated` solo si puede demostrar determinismo y ausencia de efectos externos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L40-U2` | de lo contrario use `regression`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L41-U1` | Añada un drift check determinista. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/derived-views.md:L42-U1` | Documente el límite y la reversión. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L3-U1` | Definition-of-Done Compiler deriva el contrato de evidencia que debe existir | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L5-U1` | solo produce requisitos verificables por máquina a partir de la tarea y de un | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L6-U1` | Project DNA validado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L12-U1` | `change_type`: `code`, `database`, `ci`, `docs`, `security` o | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L14-U1` | `surfaces`: superficies afectadas, por ejemplo `api`, `web`, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L16-U1` | `risk`: `low`, `medium`, `high` o `unknown`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L18-U1` | Project DNA aporta el fingerprint y el conocimiento verificable del software. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L24-U1` | CI requerida; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L25-U1` | cero hallazgos de revisión abiertos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L26-U1` | alcance limitado a rutas reclamadas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L34-U1` | código: tests del scope + análisis estático; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L35-U1` | base de datos: verify-plan, backup y compatibilidad de esquema; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L36-U1` | CI: validación de workflow + ejecución representativa; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L37-U1` | docs: lint y links; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L38-U1` | seguridad: scan + casos negativos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L39-U1` | riesgo medio/alto: plan de rollback | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L39-U2` | riesgo alto añade smoke exact-SHA. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L48-U1` | `safe-fallback` y exige, además de las invariantes: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L50-U1` | suite completa; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L51-U1` | análisis estático; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L52-U1` | security scan; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L53-U1` | rollback plan; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L54-U1` | completar contexto antes de promoción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/dod-compiler.md:L56-U1` | Así, ignorancia nunca equivale a menos evidencia. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L7-U1` | Campos obligatorios: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L13-U1` | El validador rechaza campos desconocidos, duplicados por `task_id`, números negativos, timestamps sin zona horaria y más de tres rondas de revisión. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L17-U1` | Una configuración solo entra al ranking al alcanzar la muestra mínima. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L19-U1` | mayor tasa de éxito; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L20-U1` | menos incidentes posteriores por tarea; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L21-U1` | mayor tasa de integración a la primera; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L22-U1` | menos commits de retrabajo; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L23-U1` | menos rondas de revisión; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L24-U1` | menos tokens cuando el dato existe. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L26-U1` | Solo se publica una recomendación cuando existen al menos dos configuraciones comparables con muestra suficiente **y una diferencia medida**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L26-U2` | Tokens solo desempatan cuando todas las tareas de las configuraciones empatadas tienen `tokens_input` y `tokens_output` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L26-U3` | telemetría parcial queda como `tokens_avg: null` y no se interpreta como costo cero. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L30-U1` | `.github/workflows/metricas.yml` valida el motor y evalúa **el mes UTC anterior completo** en la corrida programada | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L32-U1` | El CLI del workflow lee únicamente `metricas/datos/*.jsonl` y escribe únicamente en `artifacts/` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L32-U2` | no acepta rutas arbitrarias. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L32-U3` | Con cero datos del periodo la corrida sigue siendo válida pero **no recomienda** ninguna configuración. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evaluacion-agentes.md:L34-U1` | Los proyectos que adopten el kit deben producir registros con este contrato de forma automática al cerrar una tarea | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L10-U1` | `observe → remember → learn → propose → shadow → experiment → validate → promote_or_reject → measure → prune → rollback` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L12-U1` | Solo se admite la transición a la etapa inmediatamente siguiente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L20-U1` | `generation`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L22-U1` | `parent_generation`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L25-U1` | la huella del candidato validado por Constitution v1; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L26-U1` | `decision` cuando la etapa es `promote_or_reject`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L27-U1` | `restores_generation` cuando la etapa es `rollback`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L29-U1` | El candidato se valida antes de crear la primera generación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L35-U1` | `promote_or_reject` exige una decisión explícita `adopt` o `reject`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/evolution-engine.md:L41-U1` | Rollback solo es válido al final del recorrido constitucional. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L4-U1` | Nunca promueve una regla directamente a | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L5-U1` | stable y nunca modifica las lecciones históricas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L11-U1` | `what`: qué ocurrió; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L12-U1` | `why`: causa; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L13-U1` | `prevention`: prevención esperada; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L14-U1` | `source`: Issue/PR con evidencia; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L15-U1` | además de id, proyecto, kind y timestamp. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L17-U1` | Las lecciones se validan con el validador existente antes de agruparlas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L24-U1` | causa normalizada; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L25-U1` | prevención normalizada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L27-U1` | La normalización solo elimina diferencias de mayúsculas, acentos, puntuación y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L32-U1` | Por defecto se requieren al menos **2 lecciones** y **2 fuentes distintas**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L36-U1` | El compilador acepta hasta 32 lecciones por llamada y el umbral nunca puede bajar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L43-U1` | fingerprint determinista del patrón; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L44-U1` | ids y fuentes de todas las lecciones origen; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L45-U1` | prevención esperada; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L46-U1` | ocurrencias; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L47-U1` | candidato constitucional bajo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L49-U1` | rollback `revert`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L50-U1` | fingerprint validado por Constitution. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L53-U1` | promoción posterior debe recorrer Evolution Engine / Factory Lab | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/experience-guardrails.md:L54-U1` | no puede convertir el candidato en autoridad estable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L3-U1` | Esta prueba **solo lee** los workflows de seis checkouts existentes en una raíz local: `Condor`, `GrindFlow`, `brvtal`, `ControlBot`, `AutoFactory` y `Fact | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L11-U1` | El código `0` (`SAFE`) significa **solo** que no se observaron callers de esos targets en los seis checkouts inspeccionados, no que puedan borrarse inmedia | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L15-U1` | Este inventario no representa otros forks, callers externos, branches ni repositorios a los que no se tenga acceso. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L15-U2` | Para publicar un reemplazo o retirar un reusable hace falta otro contrato V3 con los consumidores migrados, regresiones, gates de release y prueba de no ru | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L16-U1` | Preservar CI, privacidad, CodeQL, Sonar, roles, permisos mínimos, etiquetas exigidas, `Factory@v1` y revisión CodeRabbit final. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L16-U2` | Ni el preflight ni su `SAFE` autorizan mover un tag o saltar una puerta humana. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L17-U1` | Un reporte `BLOCKED` no debe resolverse suprimiendo la referencia en una rama ajena | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/f2-caller-migration.md:L17-U2` | la migración corresponde a los repos consumidores mediante sus propias reservas V3. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L3-U1` | Este documento describe únicamente el contrato de origen introducido por Factory #269/#270. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L35-U1` | El validador falla cerrado ante campos desconocidos, listas fuera de límites, identificadores inválidos, referencias sobredimensionadas y valores con forma | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L39-U1` | `canonical_payload()` serializa el WorkItem validado de forma determinista. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L40-U1` | `work_fingerprint()` identifica el contenido completo del WorkItem. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L41-U1` | `idempotency_scope()` combina `group_id`, `venture_id`, `project_id`, `work_type` e `idempotency_key`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L55-U1` | Factory Queue v1 cierra el ciclo operativo con un feedback terminal que conserva provenance hacia el WorkItem canónico. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L63-U1` | `work_id`: identidad del WorkItem observado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L64-U1` | `work_fingerprint`: fingerprint canónico recomputado desde el WorkItem; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L65-U1` | `idempotency_scope`: scope estable usado para deduplicación cross-origin; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L66-U1` | `executor_ref`: ejecutor concreto que produjo el outcome; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L67-U1` | `producer_ref`: productor original del WorkItem, que debe coincidir; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L68-U1` | `status`: estado terminal `success\\|failed\\|rejected\\|cancelled`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L69-U1` | `evidence_refs[]`: referencias de evidencia no vacías y sin duplicados; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L70-U1` | `observed_at`: timestamp con zona horaria y freshness válida. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L72-U1` | La validación falla cerrada si provenance, fingerprint, scope, productor, evidencia, estado o freshness no corresponden al WorkItem. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L76-U1` | El escenario E2E de #273 debe construir un WorkItem válido, pasarlo por readiness/Dispatcher V2, simular una ejecución terminal y producir feedback mediant | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L76-U2` | La evidencia E2E debe demostrar que el resultado conserva `work_fingerprint` e `idempotency_scope`, que entradas stale/inconsistentes fallan cerrado y que  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L80-U1` | Factory Queue v1 queda validada de extremo a extremo con el siguiente flujo canónico: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L84-U1` | Ambas comparten `idempotency_scope`, por lo que no se materializan como dos unidades ejecutables. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/factory-queue.md:L88-U1` | únicamente demuestra la composición coherente de los contratos entregados por #270, #271 y #272. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L3-U1` | Este slice cierra la demostración operativa de Factory #161: **no crear un motor nuevo** es una restricción explícita. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L9-U1` | Factory PR #253, merge `34409905f874b118b973ec316041467534fe2cd6`, aporta una cohorte real de revisión. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L10-U1` | GrindFlow PR #181 aporta evidencia real de review en HEAD `4a85df7dffb667a476afc3103c268e5f46f0e79a`. **Permanece open** y nunca se presenta como merge. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L11-U1` | Factory #163 / PR #256, merge `3d5752bd33cfae73380610e30c5f9de9740af11f`, materializa el experimento de eficiencia marginal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L12-U1` | Factory PR #325 y #326 son ejecuciones posteriores reales | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L12-U2` | #326 llega a `main@3b99efa32ba4fe931f053f1023b34943fe63bf14` con CI exact-main run `36503410235` en success. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L20-U1` | `metricas/datos/review-efficiency-baseline.jsonl` reproduce evidencia de Factory + consumidor sin mezclar cohortes incompatibles. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L21-U1` | #163 formula la hipótesis de reducir rondas automáticas low-risk de 3 a 2. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L22-U1` | Constitution limita el candidato al namespace evolutivo y exige rollback reversible. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L23-U1` | Factory Lab ejecuta shadow sin escrituras externas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L24-U1` | Fitness conserva dimensiones protegidas y la incertidumbre explícita. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L25-U1` | La muestra real disponible es insuficiente para cambiar política. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L25-U2` | El resultado correcto es `reject / insufficient_evidence`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L26-U1` | `review_round_limit=3` permanece estable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L27-U1` | PR #325/#326 demuestran ejecuciones posteriores reales bajo la política estable, sin afirmar una mejora causal inexistente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L31-U1` | El candidato solo puede tocar `evolution_state.*`, no Constitution ni permisos externos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L33-U1` | El escenario se reproduce offline y falla cerrado si un ref declara un estado imposible, por ejemplo un PR `open` con `merge_sha` o un PR `merged` sin merg | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/feedback-mesh-e2e.md:L39-U1` | No satisface por sí solo la demostración final de #248 AC-09, que exige una mejora autosugerida, probada y medida posteriormente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L20-U1` | imputa valores. `direction` debe ser `higher` o `lower` y no puede cambiar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L30-U1` | Fitness informa el bloqueo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L37-U1` | `improved`: mejora según su dirección; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L38-U1` | `equal`: no cambia; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L39-U1` | `regressed`: empeora; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L40-U1` | `unknown`: falta baseline o candidate. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L50-U1` | cualquier regresión protegida → `blocked`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L51-U1` | cualquier dato faltante → `inconclusive`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L52-U1` | regresiones no protegidas mezcladas con mejoras → `mixed`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L53-U1` | una o más mejoras sin regresiones/faltantes → `improved`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L54-U1` | todo igual → `equal`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L56-U1` | `can_claim_improvement=true` solo para `improved`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L62-U1` | por vector, se rechazan números no finitos y el resultado incluye un fingerprint | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L69-U1` | Solo compara evidencia entregada explícitamente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/fitness-engine.md:L75-U1` | `reversibility` y `authority` son siempre protegidas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L10-U1` | Solo normaliza | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L20-U1` | capacidad requerida; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L21-U1` | valor esperado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L22-U1` | fingerprint del gap; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L23-U1` | evidencia origen; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L24-U1` | rollback reversible. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L30-U1` | `evaluate_pruning()` exige evidencia medible: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L33-U1` | edad >= 90 días; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L34-U1` | valor <= 0.25; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L35-U1` | al menos 2 referencias de evidencia. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L37-U1` | Solo si las cuatro condiciones se cumplen se marca `eligible=true`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L43-U1` | parent fingerprint; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L44-U1` | fingerprint de la evaluación; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L46-U1` | `history_preserved=true`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L48-U1` | La ejecución real debe atravesar Evolution Engine y Factory Lab. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L52-U1` | Nunca pueden podarse las dimensiones constitucionales: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L60-U1` | Pruning falla cerrado antes de evaluar uso/edad/valor para cualquiera de ellas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L64-U1` | borrar historia; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L65-U1` | retirar Constitution o controles protegidos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L66-U1` | mutar stable; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/growth-pruning.md:L67-U1` | promover candidatos automáticamente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L3-U1` | Immune + Repair convierte incidentes en una secuencia verificable de recuperación | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L8-U1` | Cada incidente empieza en `detect` y solo puede avanzar un paso: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L12-U1` | El historial es append-only y `snapshot()` conserva siempre | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L18-U1` | Toda reparación declara obligatoriamente: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L20-U1` | diagnóstico; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L21-U1` | acciones propuestas; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L22-U1` | verificación posterior; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L23-U1` | rollback reversible (`revert` o `restore_baseline`). | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L25-U1` | Repair Engine nunca ejecuta el plan: `automatic_execution_allowed=false` y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L34-U1` | La autoridad no se acepta desde un dict del caller, aunque incluya | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L36-U1` | solo aporta un **handle** `decision_ref` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L38-U1` | conserva el fingerprint como integridad del registro resuelto, nunca como prueba | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L39-U1` | Revalidar un plan destructivo aprobado exige consultar otra vez | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L42-U1` | Incluso con una referencia de decisión aprobada, el motor solo marca el plan | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L43-U1` | **nunca** habilita ejecución automática. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L47-U1` | La etapa `verify` exige un resultado booleano. `immunize` solo es posible si | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L48-U1` | la verificación anterior fue exitosa. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L49-U1` | en `verify` y no puede convertirse en inmunidad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L53-U1` | Dos o más incidentes distintos pueden producir un candidato de inmunidad solo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L57-U1` | su `source_id` y los handles que se vuelven a resolver al validar el candidato. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L61-U1` | firma canónica del fallo; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L62-U1` | todos los incidentes/fuentes origen; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L63-U1` | prevención esperada; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L64-U1` | estado `candidate`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L65-U1` | rollback `revert`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L66-U1` | fingerprint validado por Factory Constitution. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L68-U1` | Se escribe únicamente como candidato en | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L74-U1` | ejecutar reparaciones; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L75-U1` | acciones destructivas automáticas; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L76-U1` | ocultar o eliminar incidentes; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L77-U1` | promover guardrails directamente; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L78-U1` | ampliar autoridad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L84-U1` | Sus registros son append-only: un handle existente no se puede reemplazar. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/immune-repair.md:L86-U1` | GitHub/ControlBot u otro almacén durable vive fuera de estos motores y debe | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/inventario-tecnico-datos-productos.md:B01` | Inventario anclado a SHA por producto; cambios de fuente invalidan cualquier inferencia de estado actual. | NO_VERIFICABLE | Histórico/read-only: ninguna prueba de los tres HEAD actuales se atribuye a Factory. | — |
| `docs/inventario-tecnico-datos-productos.md:B02` | Clasificar proveedores observados y no convertir un gateway nulo o tags externos en proveedor/contrato activo. | NO_VERIFICABLE | Los adaptadores de terceros y los contratos operativos no se certifican desde este corte. | — |
| `docs/inventario-tecnico-datos-productos.md:B03` | Distinguir TTL técnicos observables (invitation/dedupe/CAPTCHA) de calendarios generales de retención no probados. | NO_VERIFICABLE | No existe recibo de pruebas cross-repo exact-SHA para políticas generales de borrado. | — |
| `docs/issue-contract-preflight.md:L3-U1` | Antes de publicar `/tomar`, un agente puede validar localmente que el body del Issue cumple **los dos contratos que Coordinación fijará en la reserva**: ac | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/issue-contract-preflight.md:L19-U1` | valida primero las secciones y criterios con `aceptacion_kit.parse_contract`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/issue-contract-preflight.md:L20-U1` | fija el fingerprint con `contract_fingerprint`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/issue-contract-preflight.md:L21-U1` | valida el marker con `orquestador_kit.parse_task_marker`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/issue-contract-preflight.md:L22-U1` | fija su identidad con `task_marker_fingerprint`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/issue-contract-preflight.md:L24-U1` | Un marker ausente o inválido bloquea el preflight. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/issue-contract-preflight.md:L28-U1` | Este comando **no reserva trabajo** y no autoriza ningún cambio. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/issue-contract-preflight.md:L28-U2` | Solo valida texto local reutilizando los parsers canónicos de Factory. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L9-U1` | **candidate**: evidencia suficiente para proponer, todavía no habilita autonomía. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L10-U1` | **active**: regla revalidada dentro de su ventana de revisión. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L11-U1` | **needs_review**: la validación envejeció | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L11-U2` | la regla deja de aumentar autonomía hasta revalidarse. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L12-U1` | **deprecated**: conocimiento sustituido o retirado de uso activo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L13-U1` | **archived**: historial conservado para auditoría | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L13-U2` | nunca implica borrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L19-U1` | provenance verificable y scope `project/domain`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L20-U1` | `created_at`, `last_validated_at` y `last_useful_at`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L21-U1` | `content_fingerprint` SHA-256; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L22-U1` | confidence y evidence class; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L23-U1` | política explícita `review_after_days / expires_after_days`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L24-U1` | history append-only de transiciones. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L26-U1` | Mientras esté vencida, sea `candidate`, `deprecated` o `archived`, **no puede aumentar autonomía**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L30-U1` | Revalidar exige al menos una **identidad de evidencia nueva**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L30-U2` | La identidad puede ser la fuente histórica simple o una fuente versionada como `source@sha256:<digest>`, `source@rev:<revision>` o `source@event:<verificat | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L30-U3` | Repetir la misma fuente base es válido solo cuando cambia esa identidad verificable | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L30-U4` | reenviar exactamente la misma identidad se rechaza y no refresca timestamps, estado ni autonomía. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L30-U5` | La revalidación actualiza provenance/fecha/confidence/evidence class y añade una transición trazable a `active`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L30-U6` | Revalidar no revive conocimiento ya `deprecated` o `archived` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L30-U7` | ese caso requiere una nueva propuesta. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L36-U1` | duplicado por `content_fingerprint`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L37-U1` | sin uso reciente; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L38-U1` | envejecido o pendiente de revisión. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L40-U1` | El resultado es siempre una **propuesta** `review-consolidation` o `review-retirement`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L40-U2` | Nunca contiene una operación delete y siempre declara `history_preserved=true`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-lifecycle.md:L42-U1` | Solo reduce autonomía cuando la evidencia envejece y conserva trazabilidad cuando una regla se revalida o retira. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L7-U1` | Postmortem (#320) con causa conocida y evidencia → lesson canónica → Experience Guardrails puede producir únicamente un candidate. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L9-U1` | propose_pruning_candidates() solo genera propuestas revisables con delete=false e history_preserved=true. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L13-U1` | No promoción automática de guardrails. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L14-U1` | No delete físico durante pruning. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L15-U1` | No store, red, scheduler, polling, vector DB ni embeddings. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L16-U1` | No WorkItems ni cambios de authority en este slice. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L17-U1` | Context Compiler recibe únicamente category/source/text/tags. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L18-U1` | Provenance permanece en bindings/artefactos canónicos, no se inventa. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations-e2e.md:L20-U1` | README permanece como portada operativa derivada: el detalle de root cause, lifecycle, guardrails y pruning vive en estos artefactos/docs, no en README.\n\ | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L9-U1` | **Knowledge Lifecycle** (`evolution/knowledge_lifecycle.py`) conserva provenance, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L11-U1` | **Context Compiler** seleccionará en #321 el mínimo conocimiento relevante para | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L13-U1` | **Experience Guardrails / pruning** continúan siendo responsables de candidatos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L20-U1` | `item_id` e `item_class`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L21-U1` | `title`, `summary` y `tags` acotados; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L22-U1` | `owner_ref`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L23-U1` | `authority_class`, usando el catálogo canónico Capability × Authority; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L24-U1` | `sensitivity`: `normal \\| personal_data \\| sensitive_data`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L25-U1` | `related_refs`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L26-U1` | relaciones `supersedes` / `superseded_by`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L27-U1` | `lifecycle`, validado íntegramente por Knowledge Lifecycle v1. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L35-U1` | `item_id` debe coincidir con `lifecycle.knowledge_id` y `item_class` con | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L42-U1` | `effective_state()` del Knowledge Lifecycle y solo considera `current=true` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L45-U1` | Así, un item `candidate`, `needs_review`, `deprecated` o `archived` nunca se | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L56-U1` | El contrato no permite incluir | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L58-U1` | decidirá qué items son elegibles para Context Compiler y debe fallar cerrado ante | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L63-U1` | sin I/O ni store; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L64-U1` | sin búsqueda vectorial; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L65-U1` | sin scheduler; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L67-U1` | sin mutar Knowledge Lifecycle; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L68-U1` | sin ampliar autonomy/authority; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-operations.md:L69-U1` | sin convertir README en almacén documental. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L9-U1` | `root_cause.status=known` exige resumen causal, evidencia verificable y prevención explícita. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L10-U1` | `root_cause.status=unknown` exige `summary=null` y cero evidencia causal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L10-U2` | Factory conserva el unknown | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L10-U3` | no inventa causa raíz. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L11-U1` | Texto libre es acotado y rechaza formas comunes de secretos/PII. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L12-U1` | La salida fija `authority: unchanged`, `execute_actions: false` y `emit_work_items: false`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L16-U1` | `guardrail_lesson_input()` devuelve una lección validada por `lecciones.memoria.validate_lesson` solo para una causa conocida/verificada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L20-U1` | #319: Knowledge Item Contract/Lifecycle. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L21-U1` | #320: postmortem verificable → lesson candidate. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L22-U1` | #321: selección scoped para Context Compiler. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L23-U1` | #322: E2E lifecycle/context/pruning/guardrails. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-postmortem.md:L25-U1` | No existe scheduler/backlog paralelo, no se crean WorkItems ni se ejecutan fixes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-selection.md:L5-U1` | Cada item se valida con knowledge.contract y su freshness proviene exclusivamente de knowledge_item_status(). | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-selection.md:L7-U1` | solo proyecta items current. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/knowledge-selection.md:L7-U2` | Con require_current=true, si no queda selección compatible/current falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L7-U1` | Fuente canónica: `labels/es.json` para Factory, Condor, GrindFlow, ControlBot, AutoFactory y FactoryRunner | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L7-U2` | `labels/en.json` para BRVTAL. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L8-U1` | Los catálogos deben mantener el mismo color por `key`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L9-U1` | El reconciliador solo genera operaciones `update_color` para labels existentes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L10-U1` | No crea, borra, renombra ni reasigna labels, y no cambia descripciones. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L11-U1` | BRVTAL conserva sus nombres en inglés. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L17-U1` | `estado: bloqueado` / `status: blocked`: trabajo que sí está detenido por una dependencia, fallo o condición real pendiente; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L18-U1` | `estado: planificado` / `status: planned`: plan, épica o roadmap no ejecutable por diseño. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L18-U2` | No está atascado, no entra al despacho y no debe contarse como bloqueo operativo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L20-U1` | La exclusividad de la dimensión `state_` se conserva: un Issue no puede ser simultáneamente `planificado` y `bloqueado`, `disponible`, `reservado`, `en rev | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L22-U1` | La clasificación a `planificado` debe ser conservadora. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L22-U2` | Nunca se usa para esconder una hoja ejecutable ni una dependencia abierta real. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L22-U3` | La migración de Issues existentes se prepara primero como `--dry-run`, es idempotente y solo puede aplicarse después de publicar el kit compatible en `v1`  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L24-U1` | ControlBot adopta el nuevo estado en una hoja separada (`ControlBot#752`) para que el Orquestador lo muestre aparte de los bloqueos reales. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L24-U2` | Esa adopción permanece bloqueada hasta completar el orden kit → publicación autorizada → sincronización de labels. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L28-U1` | Estos comandos de comentario se conservan aquí solo como referencia histórica, no como instrucciones operativas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L30-U1` | El motor `scripts/sync_label_colors.py` permanece disponible para pruebas offline y para generar un plan de lectura `python3 scripts/sync_label_colors.py - | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L30-U2` | Las pruebas de paridad y reconciliación siguen cubriendo el contrato de actualizar únicamente colores de labels existentes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L32-U1` | **No ejecutar `--apply` ni usar `FACTORY_PROVISION_TOKEN` sin una autorización explícita independiente.** El motor conserva controles de fail-closed, pero  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L36-U1` | Para revertir una aplicación, se usan esos valores anteriores como evidencia y se restauran únicamente los colores afectados | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L36-U2` | no se requiere rename/create/delete ni cambios de asignaciones. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/label-color-sync.md:L38-U1` | Ante catálogo inválido, repo fuera de allowlist, snapshot ambiguo, falta de token en apply, respuesta ilegible de GitHub o deriva residual, el reconciliado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L3-U1` | Este helper solo inspecciona localmente un ZIP lease-audit-evidence de GitHub Actions y un JSON de metadatos **obtenido por GitHub autenticado** (endpoint  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L3-U2` | Se exige schedule, completed/success y coincidencia exacta de identidad | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L3-U3` | no se realizan consultas de red, cambios de permisos, almacenamiento de datos, ni llamadas de escritura a GitHub. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L3-U4` | La operación solo calcula SHA-256 de los bytes originales lease-audit-evidence.json, valida el esquema Fase A y rechaza entradas peligrosas/ambiguas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L9-U1` | QA verifica independientemente la respuesta REST, artefacto ID, integridad, SHA/run, repositorio y evento, la cadena exacta y cualquier actividad del titul | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L11-U1` | El evaluador existente evaluate_phase_a_candidate es independiente y debe recibir recibos autenticados y la **QA individual** de cada release hipotético. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L13-U1` | Se exigen **24 horas**, **100 ciclos** terminales válidos por repositorio, cero falsos positivos y todas las revisiones individuales correctas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/lease-phase-a-artifact-qa.md:L15-U1` | **No autoriza Fase B**, cambiar el flag en los workflows, liberar reservas, crear comentarios, fusionar, desplegar, publicar Factory@v1, gastar dinero o pr | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L14-U1` | `collect_activity(..., allow_ci_veto_only=True)` permite emitir evidencia | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L15-U1` | `ci_veto_only=true` únicamente cuando los checks o runs de la rama están | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L16-U1` | Solo se usa desde | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L26-U1` | o carrera devuelve `UNKNOWN`, nunca una falsa prueba negativa. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L27-U1` | **Un veto tipado nunca demuestra la ausencia de pushes y no acredita una | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L36-U1` | SHAs y `pushed_at` válidos, inventario revalidado en dos lecturas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L40-U1` | de actividad no ofrece cobertura íntegra garantizada para inferir | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L44-U1` | no se simulan `mark_recovery` ni `release`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L47-U1` | reserva V3 también son evidencia positiva para `wait`: se valida autor | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L49-U1` | Nunca se usa | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L55-U1` | falta, es inválido o apunta al futuro, invalida el snapshot como `UNKNOWN`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L56-U1` | Por la precisión de un segundo de `pushed_at`, cualquier valor del último minuto también invalida la observación como `UNKNOWN`, incluso si ambas lecturas  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L60-U1` | ninguna fuente de inactividad ni autoridad para release. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L65-U1` | Cuando hay `UNKNOWN`, persiste únicamente un registro mínimo sin | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L66-U1` | El filtro exige exactamente **un objeto JSON | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L69-U1` | no se envía a comentarios. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L70-U1` | La ventana ampliada permite revisar evidencia de más ejecuciones programadas, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L71-U1` | pero no garantiza obtener 100 ciclos terminales válidos ni reemplaza la | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L74-U1` | El manifiesto sólo puede marcar `candidate_terminal` cuando existe al menos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L75-U1` | una observación válida, ninguna `UNKNOWN` y la cantidad, estados e IDs únicos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L78-U1` | IDs duplicados invalidan la generación del manifiesto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L79-U1` | estados acredita por sí solo los 100 ciclos ni sustituye el QA externo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L80-U1` | El manifiesto declara siempre `terminal_certified=false`: ni `success` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L92-U1` | `scripts/lease_auto_release_run.py::evaluate_phase_a_candidate`: requiere | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L94-U1` | `schedule` terminales `success`, artefactos acreditados por una verificación | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L99-U1` | `mark_recovery` requiere motivo `inactive_30_minutes`, fuente identificada y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L100-U1` | un `release` requiere motivo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L107-U1` | un switch pausado o un `activity_window` sin fuente no pueden sumar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L111-U1` | no convierte una declaración QA en firma auténtica y nunca permite release**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L112-U1` | Todos los recibos y evidencias deben verificarse manualmente por QA contra | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L116-U1` | Antes de considerar la Fase B se exigen **24 horas** reales y **100 ciclos** | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L120-U1` | Cualquier falso positivo o resultado sin procedencia autenticada bloquea la | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L122-U1` | mover `@v1` y activar liberaciones requieren puertas independientes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L133-U1` | **No se autoriza activar un cron mutante** hasta integrar un colector auténtico | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L136-U1` | solo lectura cada 10 minutos: en `pull_request` ejecuta contratos **offline** | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L137-U1` | en `schedule/workflow_dispatch` de `main` requiere | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L146-U1` | únicamente de lectura**, y `tests/test_lease_github_port.py` con fakes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L149-U1` | Valida el objeto mediante el parser canónico (incluido el rechazo de claves | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L151-U1` | Una observación positiva emite solo `RECENT_ACTIVITY` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L155-U1` | **Implementado en modo GET-only:** `recovery_note()` verifica procedencia | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L171-U1` | Ninguna prueba parcial satisface AC-03 o autoriza activar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L180-U1` | Reserva en \`reservado\` o \`en revisión\`: después de **30 minutos** | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L181-U1` | Candidatura `mark_recovery` hipotética, sin liberación automática | CUBIERTO | `scripts/lease_auto_release_integration.py` + `tests/test_lease_hypothetical_action_preview.py`; [PR #1515](https://github.com/pl0n3r/Factory/pull/1515) MERGED `1072b8b26582` | [#1514](https://github.com/pl0n3r/Factory/issues/1514) |
| `docs/liberacion-automatica-de-reservas.md:L182-U1` | Estado \`requiere recuperación\`: tras **10 minutos completos desde | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L183-U1` | la marca autenticada** y al menos 40 minutos de inactividad, propone | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L185-U1` | Con cron de 10 minutos, la liberación suele ocurrir a los **40–50 | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L187-U1` | Por tanto **no se promete liberación efectiva a los 30 minutos**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L192-U1` | El inspector de solo lectura expone este límite únicamente tras una | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L201-U1` | `RECENT_ACTIVITY`/ `UNKNOWN` y `libera_en_min` si es verificable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L212-U1` | Identidad canónica del Issue, reserva V3 actual, UUID, titular, claim, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L215-U1` | Último commit real de la rama y comentarios atribuibles al titular, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L219-U1` | Estado cerrado de protección: \`live\`, \`CHANGES_REQUESTED\` vigente, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L222-U1` | Kill switch global Factory #767 canónico y RUNNING, fase de construcción | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L224-U1` | Lock distribuido común con coordinación, doble lectura **bajo lock** de | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L226-U1` | La lectura previa nunca equivale a un compare-and-swap de GitHub. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L227-U1` | Persistencia auditada de la liberación: marker V3 \`active:false\` con | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L234-U1` | y reserva V3 \`active:false\`, \`reserve_work\` devuelve el error que exige | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L238-U1` | exigiría una tarea y reserva separadas sobre \`scripts/coordinar_trabajo.py\`, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L242-U1` | \`/adoptar-contrato-huerfana\` **solo tras desactivación inequívoca** de | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L254-U1` | En `.github/workflows/coordinacion-trabajo.yml` los comandos /tomar, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L260-U1` | una cola no destructiva y verificar la procedencia del workflow antes de | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L262-U1` | Las lecturas condicionales `If-None-Match` de GitHub REST son para GET. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L267-U1` | GitHub GraphQL **`updateRefs`** sí ofrece un `RefUpdate.beforeOid` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L280-U1` | **Escritor común**: Coordinación y liberador deben acordar el mismo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L282-U1` | `scripts/coordinar_trabajo.py` para respetar ese protocolo **requiere un | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L284-U1` | Ninguna versión parcial de este PR puede suplantarlo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L285-U1` | **Adquisición demostrable**: recibir el contexto autenticado de ejecución | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L289-U1` | nunca se asume posesión del lock por un | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L291-U1` | **Lectura con atribución**: demostrar ausencia de actividad del *agente | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L296-U1` | **Precondición bajo exclusión**: #767 CLOSED/RUNNING en su URL absoluta, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L300-U1` | reviews/CI/push del titular revalidados. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L301-U1` | **Commit y reconciliación**: tras acreditar el fence y el estado exacto, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L306-U1` | `partial/UNKNOWN`: reanudar solo con el mismo ID y nuevo fence validado, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L308-U1` | **Pruebas contractuales**: dos ejecutores concurrentes con el mismo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L309-U1` | `beforeOid` (solo uno vence), cambio externo de UUID/HEAD/claim bajo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L313-U1` | AC-03 debe ejercer la ruta REAL y verificar la ausencia de doble | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L314-U1` | escritura, no simplemente crear el método con el nombre exigido. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L317-U1` | atómico, exista una fuente verificable de inactividad del titular y un dry-run | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L320-U1` | PR DRAFT, y ninguna aceptación/merge/go-live por inferencia. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L321-U1` | es de seguridad de la funcionalidad, no un fallo que deba ignorar `Validar`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L325-U1` | AC-01: decisor y negativos 29/30/39/40/49/50 min, quota 19/20%, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L327-U1` | AC-02: compatibilidad del test existente de coordinación, que evita | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L329-U1` | Preparación ya comprobada: cron de 10 minutos, modo PR offline, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L331-U1` | Ninguna parte escribe en GitHub. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L332-U1` | Bloqueos pendientes: prueba autoritativa de ausencia de push/comentarios/ | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/liberacion-automatica-de-reservas.md:L338-U1` | No habilitar release, auto-merge, movimiento de \`v1\`, deploy ni live | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L9-U1` | run `36507015627`: failure porque el contrato de aceptación no tenía todavía la estructura canónica; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L10-U1` | run `36507097760`: workflow success, pero sin reserva efectiva porque faltaba `estado: disponible`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L11-U1` | run `36507219161`: failure porque el trabajo no planificado no podía coexistir con #330; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L12-U1` | tras agrupar las tres precondiciones como readiness bundle, run `36507269422`: success y reserva V3 concedida. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L14-U1` | La hipótesis autosugerida es simple: **validar acceptance contract + available state + factory-plan-task antes de emitir `/tomar`**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L22-U1` | invariantes protegidos: security, privacy, traceability, reversibility y authority; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L23-U1` | segundos de coordinación; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L24-U1` | cantidad de intentos necesarios para obtener una reserva. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L26-U1` | Shadow no permite mutación ni escrituras externas y conserva rollback `restore_baseline`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L28-U1` | No se modifica automáticamente `coordinar_trabajo.py` ni se declara todavía una regla universal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L42-U1` | before: 7 s + 20 s + 8 s = **35 s** de coordinación improductiva; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L43-U1` | after: **27 s** para la reserva exitosa; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L44-U1` | ejecución útil común: **29 s** de CI; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L45-U1` | protected metrics: iguales antes/después. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L55-U1` | La candidata puede generalizarse más adelante solo si acumula evidencia suficiente | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L59-U1` | sin crear un Engine, scheduler, store o ranking; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L60-U1` | sin nueva authority; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L61-U1` | sin tocar dinero, legal, datos personales, borrado irreversible ni permisos externos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L62-U1` | sin tocar #330; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L63-U1` | sin reescribir el coordinador; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L64-U1` | sin afirmar causalidad fuera del escenario #247. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/living-software-operational-e2e.md:L66-U1` | Con #161 ya demostrando Feedback Mesh y #142/#242–#247 integrados, esta evidencia completa la demostración operacional exigida por #248: Factory observa su | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L5-U1` | El bootstrap no debe reconstruir incidentes ni decisiones leyendo conversaciones largas. `lecciones/` conserva únicamente fallos/retrabajos demostrados y g | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L5-U2` | La telemetría de #5 permite medir si ese contexto reduce tokens reales de entrada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L9-U1` | Al cerrar un incidente o un PR con retrabajo material, agregar una lección con fuente verificable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L10-U1` | Registrar solo causa confirmada y prevención ejecutable | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L10-U2` | nunca secretos, PII ni conjeturas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L11-U1` | Antes de trabajar en un proyecto, generar/leer su contexto acotado junto con las decisiones vigentes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L11-U2` | Si una lección reciente no cabe en el límite, el generador sigue buscando una anterior más corta en vez de declarar memoria vacía. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L12-U1` | Medir tareas de bootstrap con `task_type=agent-bootstrap`, `task_id=owner/repo#N` y comparar tokens before/after con un corte temporal explícito **por proy | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L12-U2` | nunca mezclar repositorios. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L16-U1` | El slice implementa `lecciones/`, validación, contexto por proyecto y medición de tokens. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/memoria-institucional.md:L18-U1` | La reducción de tokens o incidentes **no se presume**: mientras no existan muestras reales before/after suficientes, la evidencia correcta es `insufficient | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L5-U1` | Issue: `pl0n3r/Factory#904`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L6-U1` | La decisión es pura y vive en `scripts/no_work_dedup.py`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L7-U1` | El caller sigue siendo responsable de leer inventario vivo, recheck final y GitHub. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L8-U1` | Este contrato no altera ranking, readiness, kill switch, D-068 ni puertas humanas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L14-U1` | estado del kill switch; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L15-U1` | hojas `available` / `estado: disponible`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L16-U1` | hojas de recovery; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L17-U1` | reservas vivas; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L19-U1` | número, estado y HEAD de PRs abiertos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L20-U1` | los siete repos canónicos: Factory, Condor, GrindFlow, brvtal, ControlBot, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L36-U1` | debe usar el namespace explícito `observation_metadata: {updated_at: ...}`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L37-U1` | Solo admite `observed_at`, `fetched_at`, `captured_at` y `updated_at` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L39-U1` | Se rechazan cadenas arbitrarias, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L42-U1` | reserva o bloqueo y nunca se descarta por heurística. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L46-U1` | pero ambigua o con claves no permitidas falla cerrado con | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L47-U1` | `NoWorkInventoryError`: nunca se omiten campos desconocidos de una supuesta | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L57-U1` | La huella sigue dependiendo solo del inventario autorizado y nunca del timestamp. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L74-U1` | Después de la creación inicial, la política nunca requiere crear otro comentario | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L79-U1` | Una decisión calculada no autoriza por sí sola el overwrite. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L80-U1` | de `create` o `update`, el caller debe releer el estado canónico y ejecutar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L81-U1` | `revalidate_no_work_application(decision, current)`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L83-U1` | La precondición es fail-closed: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L85-U1` | `apply`: el comentario/fingerprint esperado siguen vigentes y la observación | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L87-U1` | `omit`: la decisión original ya era un no-op; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L88-U1` | `recompute`: cambió `comment_id`, cambió el fingerprint esperado, apareció o | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L92-U1` | Ante `recompute`, el caller no debe escribir con la decisión vieja: debe volver a | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L93-U1` | leer inventario vivo, recalcular la decisión y repetir la revalidación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L107-U1` | Este es el baseline verificable usado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L108-U1` | no se extrapola desde la palabra “decenas”. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L112-U1` | primera observación sin comentario canónico: máximo **1 creación total**; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L113-U1` | después de existir el comentario: máximo **0 comentarios nuevos/h** por | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L115-U1` | con huella idéntica, como máximo **2 updates in-place/h** (intervalo 30 min); | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/no-work-dedup.md:L116-U1` | un cambio real de inventario puede actualizar inmediatamente el mismo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L7-U1` | `FACTORY_LEASE_AUTO_RELEASE_ENABLED`, no libera reservas, no cierra PRs ni | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L10-U1` | `candidate_terminal` son **evidencia candidata**, nunca permiso para Fase B. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L13-U1` | `.github/workflows/liberar-reservas.yml` continúa observando **solo Factory**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L24-U1` | son diferentes para evitar que el caller bloquee al reusable que invoca; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L27-U1` | falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L31-U1` | Validar `Validar`, suite de seguridad, CodeQL/Sonar y revisión FINAL en el | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L33-U1` | Publicar una versión Factory semántica y promover el **canal protegido `@v1`** | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L34-U1` | solo bajo la puerta de release vigente del owner | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L36-U1` | En **cada** uno de Condor, GrindFlow, brvtal, ControlBot, AutoFactory y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L39-U1` | archivo instalado debe conservar `permissions` read-only y apuntar a | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L41-U1` | nunca push directo ni token | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L43-U1` | Verificar un run `schedule` auténtico de ese repositorio y recuperar su | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L49-U1` | Acumular únicamente **al menos 100 ciclos terminales válidos durante | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L50-U1` | al menos 24 horas reales por repositorio**, con cero falsos positivos y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L53-U1` | `evaluate_phase_a_candidate` solo calcula candidatos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L61-U1` | `preview_integrated_activity` mantiene `UNKNOWN` cuando no puede demostrar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L63-U1` | de Issues no amplía autoridad ni sustituye la validación del marker V3 en el | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L68-U1` | protocolo de bloqueo/CAS compartido real con Coordinación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L71-U1` | Un artefacto candidato no se puede transformar por sí solo en | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L77-U1` | Revertir el caller local por PR deja de generar recibos sin tocar ninguna V3. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L78-U1` | Revertir el reusable de Factory requiere una release protegida posterior. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/observador-reservas-consumidor.md:L80-U1` | titulares y solo contienen números de Issue y códigos de diagnóstico. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L9-U1` | reglas/guardrails consultados; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L10-U1` | roles activos y revisores; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L11-U1` | checks/gates; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L13-U1` | engines/compilers consultados; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L14-U1` | tokens de contexto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L15-U1` | minutos de coordinación; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L16-U1` | minutos de espera; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L17-U1` | minutos de revisión; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L18-U1` | minutos de ejecución útil; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L19-U1` | las cinco dimensiones protegidas de Factory Constitution; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L20-U1` | evidencia y scope comparable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L28-U1` | `task_size=small\\|medium\\|large` del modelo de #7; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L29-U1` | multiplicador de `task_type` ya definido en `metricas/presupuestos.json`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L30-U1` | `risk=low\\|medium\\|high\\|critical`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L40-U1` | valor observado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L41-U1` | budget contextual; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L42-U1` | estado `within\\|over`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L44-U1` | Un exceso crea únicamente un **simplification candidate** con dimensiones objetivo, provenance y `execute=false`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L48-U1` | Solo compara observaciones de la misma cohorte (`comparison_scope + task_type + task_size + risk`). | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L52-U1` | Constitution: security/privacy/traceability/reversibility/authority, dirección `higher`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L53-U1` | organizational_overhead_minutes, context_tokens y governance_items, dirección `lower`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L55-U1` | Solo `claim=improved`, sin regresiones ni faltantes, permite `can_claim_simplification=true`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L61-U1` | `useful_execution_minutes`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L62-U1` | `organizational_overhead_minutes`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L63-U1` | `total_minutes`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L64-U1` | `overhead_ratio`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L65-U1` | candidatos de simplificación; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L66-U1` | conteo de dimensiones excedidas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/organizational-complexity.md:L68-U1` | Esto permite observar el costo operativo de la organización sin confundir trabajo productivo con coordinación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L8-U1` | Cada tarea exige key, title, owner, paths y depends_on. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L10-U1` | key: identificador estable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L11-U1` | title: una línea. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L12-U1` | owner: login GitHub responsable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L13-U1` | paths: archivos exactos o prefijos de directorio terminados en / | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L13-U2` | no acepta glob, traversal ni rutas absolutas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L14-U1` | depends_on: keys del mismo plan. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L16-U1` | Los roles no se escriben a mano: se derivan del clasificador profesional de #2 usando título, tipo del épico y paths. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L22-U1` | El workflow valida esquema, límites y DAG | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L24-U1` | Si dos tareas reclaman rutas solapadas, el plan solo es válido cuando una depende transitivamente de la otra. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L24-U2` | Una tarea ya activa no puede cambiar su marker y una tarea materializada no puede desaparecer del plan. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L29-U1` | con contexto del repositorio y vuelve a validar colisiones. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L35-U1` | La expansión es estable, idempotente y no se aplica a otros repositorios. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L36-U1` | `config/version.php` no se deriva de `datos.yml`: debe aparecer explícitamente | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L38-U1` | con claims menores, el resync falla cerrado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L38-U2` | la ampliación requiere el flujo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L45-U1` | el actor debe coincidir con el owner planificado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L46-U1` | todas las dependencias deben estar cerradas; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L47-U1` | ninguna otra tarea planificada en estado reservado, revisión o recuperación puede reclamar un path solapado, incluso si pertenece a otro épico. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L49-U1` | El validador de PR conserva su detección de colisiones exactas como segunda barrera. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L57-U1` | Cuando un repositorio `pl0n3r/*` existente no puede usar `/tomar` porque todavía no contiene el caller de coordinación, Factory no crea una excepción manua | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L59-U1` | El workflow reutiliza únicamente `FACTORY_PROVISION_TOKEN`, valida owner, Issue abierto y SHA exacto, y genera una rama `factory/bootstrap-coordination-<is | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L59-U2` | El request externo sigue cerrado: no acepta patches, comandos, rutas ni contenido arbitrario. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L61-U1` | El primer adapter es `pl0n3r/GrindFlow`: exige paridad entre `config/version.php`, `package.json` y las dos versiones raíz de `package-lock.json`, calcula  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L63-U1` | Solo consume el JSON preparado, verifica identidad, SHA del patch, tamaño, ausencia de traversal/symlinks y una allowlist cerrada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L65-U1` | Nunca copia `coordinar_trabajo.py`: el caller consume `pl0n3r/factory/.github/workflows/coordinacion.yml@v1` con perfil `es`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L67-U1` | Si cambian la intención, `main`, el owner, el Issue o aparece un path/symlink fuera de la allowlist, el bootstrap falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L67-U2` | El merge del PR no sustituye la evidencia del consumidor: después del merge, `/tomar` debe funcionar en el Issue objetivo antes de considerar restaurada la | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L72-U1` | Esa es la opción por defecto y permite que GitHub | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L75-U1` | Una excepción cerrada existe **solo para incidentes** que necesitan evidencia | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L83-U1` | El coordinador acepta el marker únicamente cuando `issue` coincide con el Issue | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L86-U1` | un Issue que no sea incidente, una reserva inválida o mezclar el marker con una | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L98-U1` | requiere SHA completos estables, un conjunto de archivos completo, paths canónicos y UUID identificable de la otra lease. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L100-U1` | La puerta de **validación de PR** consulta `GitHub.pull_files_exact_head`, que exige `changed_files` (0–3000), lee todas las páginas de 100 archivos de la  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L100-U2` | Cambios concurrentes o datos incompletos son **errores**, nunca permiso para ignorar una colisión. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L102-U1` | Una reserva V1/V2 sin `task_paths`, un PR sin diff verificable o un directorio declarado por el candidato **siguen bloqueados**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L102-U2` | el draft por sí solo no invalida la lectura. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L102-U3` | La comprobación previa vuelve a comparar tanto el fingerprint de aceptación como el marker de tarea. **Exclusividad vigente:** incluso con diff disjunto, ` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L102-U4` | Es necesario enforcement de claims durante la lease o merge-train verificable antes de habilitar una excepción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L104-U1` | **Validación provisional en cada push de PR interno:** el job `claims-pr / Validar claims V3 del PR` corre en eventos `opened`, `synchronize`, `reopened` y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L104-U2` | El job no hace checkout ni ejecuta código del PR: usa exclusivamente el runner y la API de GitHub para leer claims y evidencia, con credenciales de solo le | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L104-U3` | Para proteger merges, publicarla desde una base confiable, exigir ese check desde las reglas de rama/repositorio y conservar revisión independiente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L104-U4` | Hasta entonces, AC-01 de directorios solapados permanece **FAIL-CLOSED**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L106-U1` | **Archivos compartidos obligatorios:** `config/version.php`, `README.md`, `package-lock.json` y archivos fuente iguales siguen siendo colisiones reales, in | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L106-U2` | Una excepción por merge-train, bump serializado o rebase de hunks requiere una implementación específica con evidencia atómica en cada integración | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L106-U3` | no se habilita automáticamente mediante la función pura. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L108-U1` | El `Validar` agregado exact-HEAD y la revisión independiente siguen siendo obligatorios para fusionar esta capacidad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L112-U1` | **Exclusividad V3 obligatoria (Factory #1234):** incluso con `CONDOR_PARALLEL_FILE_GRANTS=1`, un diff exact-SHA de un PR no concede independencia para clai | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L112-U2` | Si una lease A reclama `src/` y solo ha cambiado `src/a.py`, A todavía puede modificar `src/b.py` en un push futuro | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L112-U3` | por tanto no se concede a B una segunda lease sobre `src/b.py`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L114-U1` | El cálculo de archivos cambiados se conserva **únicamente como diagnóstico**, sin autoridad para omitir la colisión de claims ni siquiera mediante opt-in. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L114-U2` | El interruptor permanece fail-closed: valor ausente, `0`, `1`, `false` o cualquier valor desconocido no habilita grants que solapen claims, hasta implement | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L114-U3` | Ningún check verde aislado reemplaza la reserva V3, la revisión de seguridad y CI exact-HEAD. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L121-U1` | El lifecycle parcial exige V3 auténtica, claims y fingerprints coincidentes | CUBIERTO | `scripts/coordinar_trabajo.py` + `tests/test_coordinar_trabajo.py`; [PR #1414](https://github.com/pl0n3r/Factory/pull/1414) MERGED `67994aafbb5d` | [#1413](https://github.com/pl0n3r/Factory/issues/1413) |
| `docs/orquestador.md:L122-U1` | coordinador verifica la **reserva V3** vigente emitida por el bot: rama | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L135-U1` | No se utiliza `Closes #129` ni `Fixes`/`Resolves` junto a esta relación: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L137-U1` | mantiene su palabra de cierre obligatoria | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L138-U1` | `post_merge_validation` permanece **solo para incidentes**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L140-U1` | Durante `pull_request.closed` de una hoja parcial validada, el cierre | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L143-U1` | eliminan la rama únicamente mediante CAS del HEAD validado y mantienen el | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L148-U1` | contrato, permiso, HEAD, rama, o hay un marker duplicado/forjado, falla cerrado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L149-U1` | antes de borrar una referencia o invalidar el estado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L150-U1` | no se omite el coordinador. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L153-U1` | humanas, D-061 o validación real de Safari/ControlBot. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/orquestador.md:L154-U1` | main` **no actualiza Factory@v1**: publicar o mover `@v1` exige el bootstrap, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L3-U1` | Este documento materializa la policy específica de BRVTAL que desbloquea la frontera baseline/budget de Factory #304. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L17-U1` | mobile: FCP 380 ms, LCP 1624 ms, CLS 0; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L18-U1` | desktop: FCP 456 ms, LCP 1772 ms, CLS 0.005. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L20-U1` | El artifact real `production-performance-36853443439` (id `11160130127`) registra el attempt 2 con timestamps verificables: las observaciones mobile usan ` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L20-U2` | Como Performance Contract v1 necesita un único `observed_at` por baseline/evidence derivada, el contrato usa el timestamp verificable del envelope, `2026-1 | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L20-U3` | esta página conserva los runs/attempts y timestamps por superficie que permiten reproducir la derivación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L26-U1` | FCP `<= 1800 ms`, alineado con la referencia pública de web.dev para una puntuación FCP “good”: https://web.dev/articles/fcp | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L27-U1` | LCP `<= 2500 ms`, alineado con la referencia pública de web.dev para LCP “good”: https://web.dev/articles/lcp | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L28-U1` | CLS `<= 0.1`, alineado con la referencia pública de web.dev para CLS “good”: https://web.dev/articles/cls | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L30-U1` | Aquí se reutilizan **solo los valores numéricos como budgets de laboratorio explícitos** para este consumidor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L34-U1` | Esto permite clasificar la evidencia reciente sin fingir una distribución estadística. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-brvtal.md:L36-U1` | el detector real debe devolver `PERF_REVIEW` + `UNKNOWN` para ellas, nunca inferir un límite. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-professional-report.md:L6-U1` | El caller debe autenticar por su cuenta el GET de GitHub | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-professional-report.md:L14-U1` | El contrato `performance/contracts/factoryrunner.json` permite únicamente | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-professional-report.md:L15-U1` | no autoriza `create_work_item` ni | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-professional-report.md:L20-U1` | el cuello, no asignación ni diagnóstico causal verificado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-professional-report.md:L23-U1` | solamente campos canónicos saneados, nunca payload arbitrario, credenciales | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-professional-report.md:L28-U1` | Esta hoja solo avanza | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-suite-benchmark.md:L5-U1` | El adaptador `performance/github_actions_ci.py` clasifica la ejecución completa. `performance/ci_suite_benchmark.py` solo mide el resumen de `unittest` den | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-suite-benchmark.md:L7-U1` | El caller autorizado lee GitHub Actions por GET autenticado para un run y job **exactos**, verifica `event=push`, `branch=main`, repositorio y SHA, obtiene | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-suite-benchmark.md:L7-U2` | Esta función **no autentica el origen**: validaciones de forma no sustituyen el transporte ni un sello de fuente, y cualquier valor posterior permanece inf | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-suite-benchmark.md:L7-U3` | El parser solo extrae `Ran N tests in X.XXXs` seguido de un `OK` inequívoco, aplica límites de 256 KB y 4000 líneas y no copia contenido del log al resulta | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-suite-benchmark.md:L16-U1` | La diferencia visible de 48,492 s en el tiempo Python **no se adopta**: las suites contienen distinto número de tests, cambiaron el SHA y las condiciones d | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-suite-benchmark.md:L22-U1` | Las cuatro pruebas verifican extracción limitada, escenarios negativos, no comparabilidad de dos runs auténticos y delta sintético solo informativo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-ci-suite-benchmark.md:L22-U2` | Después se requieren nuevas mediciones reales antes/después, decisión `ADOPT/REVERT` y estado Readiness | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classification.md:L3-U1` | El adaptador valida el envelope y delega cada observación a `performance.detector.detect_performance()` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classification.md:L5-U1` | El productor debe enviar `version=1`, `classification_authority=factory-performance-v1`, `classification=null`, identidad de proyecto, SHA/release, `eviden | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classification.md:L5-U2` | Cada observación debe coincidir con el proyecto, SHA/release y `evidence_ref` del envelope. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classification.md:L7-U1` | Lee contrato y envelope desde archivos locales, exige un `--evaluated-at` explícito y escribe JSON a stdout o a `--output`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classification.md:L9-U1` | El adaptador nunca inventa un budget ni acepta clasificación precalculada por el productor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classification.md:L11-U1` | Factory #304 todavía requiere una regresión material real antes de que el loop pueda crear un WorkItem, despachar remediación profesional, registrar eviden | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classifier.md:L5-U1` | Factory Performance v1 conserva sus ocho campos de envelope obligatorios. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classifier.md:L14-U1` | El campo **opcional** se verifica con lista cerrada de dos nombres, diseño | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classifier.md:L16-U1` | Se rechazan campos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classifier.md:L21-U1` | y **nunca** cambia baselines, budgets, severidad, freshness, autoridad de | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classifier.md:L31-U1` | del productor, no autorización de remediación ni cierre del épico #304. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-classifier.md:L33-U1` | Validación offline: \`python3 -m unittest tests.test_performance_classifier\` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L7-U1` | Cada métrica exige: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L9-U1` | `baseline`: valor, unidad y `observed_at`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L10-U1` | `budget`: operador `lte\\|gte`, valor y la misma unidad del baseline; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L11-U1` | `window`: `duration_seconds` y `min_samples`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L12-U1` | `freshness.max_age_seconds`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L13-U1` | `evidence`: `source`, referencia opaca y timestamp; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L14-U1` | `allowed_actions`: solo `observe`, `diagnose`, `benchmark`, `create_work_item`, `measure_before_after`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L15-U1` | `escalation_conditions`: catálogo cerrado de costo, arquitectura, consistencia, semántica de negocio, migración destructiva, datos sensibles o presupuesto  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L17-U1` | El validador falla cerrado ante campos desconocidos, números no finitos, unidades incompatibles, timestamps sin zona, freshness inválido o texto con forma  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L17-U2` | Los errores describen el campo/clase y nunca reflejan el valor sensible. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L23-U1` | Este slice solo valida que exista un límite de freshness y evidencia fechada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L23-U2` | No decide si una observación está sana: #311 compara evidencia contra baseline/budget y debe tratar stale/ausente como `UNKNOWN`/degradado, nunca como sano | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L27-U1` | #310: contrato, schema y validación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L28-U1` | #311: detección de regresiones y triage. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L29-U1` | #312: remediación gobernada + before/after. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-contract.md:L30-U1` | #313: estado consumible por Readiness y escenario E2E. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-detection.md:L9-U1` | La evidencia queda fail-closed: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-detection.md:L10-U1` | identidad desconocida → `PERF_REVIEW / UNKNOWN`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-detection.md:L11-U1` | stale, ventana corta o muestra insuficiente → `PERF_REVIEW`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-detection.md:L12-U1` | budget cumplido con evidencia current → `PERF_INFO`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-detection.md:L13-U1` | breach current → `PERF_DEGRADATION`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-detection.md:L14-U1` | `PERF_INCIDENT` exige además severidad `critical` e impacto operacional explícito. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-detection.md:L16-U1` | Cruzar un número aislado nunca basta para declarar incidente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-engineering.md:L11-U1` | evidencia no CURRENT → `UNKNOWN`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-engineering.md:L12-U1` | `PERF_INCIDENT` current o remediación BLOCKED/ESCALATE → `BLOCKED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-engineering.md:L13-U1` | `PERF_DEGRADATION` current → `DEGRADED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-engineering.md:L14-U1` | `PERF_INFO` current → `HEALTHY`, salvo before/after no adoptado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-engineering.md:L16-U1` | Un estado crítico no puede diluirse con checks menores. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-engineering.md:L20-U1` | UNKNOWN/stale nunca se presenta como sano. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-github-actions-ci.md:L9-U1` | El caller debe obtener el JSON desde GitHub autenticado y vincularlo al run exacto que consultó: el adaptador **no verifica firmas, credenciales ni transpo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-github-actions-ci.md:L9-U2` | Rechaza otra identidad de repositorio, workflow distinto de \`CI\`, eventos que no sean \`push\`, ramas distintas a \`main\`, runs incompletos, en curso u  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-github-actions-ci.md:L9-U3` | Otras propiedades no se vuelven a publicar para no filtrar nombres de usuarios, secrets ni rutas de jobs. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-github-actions-ci.md:L11-U1` | Con una sola muestra solo se clasifica la métrica contractual cuyo mínimo es uno. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-github-actions-ci.md:L11-U2` | No se estima P95 desde esa muestra, no se diagnostica el testcase ni se atribuye el cuello sin perfilado: \`bottleneck=unknown\`, \`operational_impact=fals | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-github-actions-ci.md:L13-U1` | una entrada inválida genera error explícito, nunca \`HEALTHY\`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-github-actions-ci.md:L15-U1` | El contrato de FactoryRunner solo concede \`observe\`, \`diagnose\`, \`benchmark\`: no autoriza crear WorkItems, alterar tests de FactoryRunner, tocar su p | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L7-U1` | Proyecto `grindflow` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L7-U2` | `main@3c137b21654d30bc5ce123853e58934d973ce4b5`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L8-U1` | GrindFlow Production Smoke #38010129128, job `production-smoke #114087986892`, `completed/success`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L9-U1` | GitHub Actions Jobs REST: `started_at=2026-10-10T00:41:39Z` y `completed_at=2026-10-10T00:42:17Z`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L9-U2` | Duración observada **38 s** | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L9-U3` | mide el **job completo**, no TTFB ni latencia de una ruta específica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L10-U1` | Ventana de la muestra: **38 s**, igual al intervalo iniciado→completado del job | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L10-U2` | una única observación, no una tendencia ni 38 s de latencia web. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L11-U1` | Budget inicial de seguimiento: **≤120 s** por job completado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L11-U2` | Es un umbral técnico provisional, **no un SLA comercial ni un RTO**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L11-U3` | Una ejecución aislada no acredita percentiles ni tendencias. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L22-U1` | El schema cerrado `performance/contract.schema.json` y `validate_performance_contract()` exigen `baseline.value` numérico | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L22-U2` | no permiten `UNKNOWN` como valor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L22-U3` | agregar rutas web requiere evidencia adicional real y una posterior actualización del contrato. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-grindflow.md:L26-U1` | nunca asumir ausencia de degradación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L3-U1` | Reutiliza el Work Origin Contract de Factory Queue #269 y devuelve un WorkItem v1 validado como artefacto puro. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L9-U1` | La decisión es fail-closed: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L11-U1` | `PERF_INFO` → `NO_ACTION`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L12-U1` | evidencia no `CURRENT` → `BLOCKED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L13-U1` | costo/arquitectura/consistencia/semántica/destructivo/datos/capacity o falta de authority → `ESCALATE`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L14-U1` | sin reversibilidad o tests → `BLOCKED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L15-U1` | solo un cambio seguro, reversible, testeado y dentro de authority → `AUTO_REPAIR`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L17-U1` | `AUTO_REPAIR` significa **elegible para la cola Factory**, no ejecución dentro de este módulo. `execute_actions` siempre es false y `authority` permanece u | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L21-U1` | La comparación exige la misma identidad `project + surface + metric`, el mismo budget/unidad y evidencia `CURRENT`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L23-U1` | `ADOPT` requiere **una secuencia before → after distinguible** además de mejora de valor y clasificación: `after.observed.observed_at` debe ser estrictamen | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L23-U2` | los `evidence_ref` deben ser diferentes y el cambio debe tener al menos un SHA o identificador de release **válido, presente en ambas muestras y distinto** | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L25-U1` | **Forma y límites de las muestras:** antes de usar un Mapping de detección, esta capa vuelve a exigir que `observed.sample_count` y `observed.window_second | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L25-U2` | budget y muestra deben compartir unidad del catálogo canónico. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L25-U3` | Muestra inválida bloquea ADOPT mediante `PerformanceRemediationError` | CUBIERTO | `performance/remediation.py` + `tests/test_performance_remediation.py`; [PR #1548](https://github.com/pl0n3r/Factory/pull/1548) MERGED `9c12107bd64e` | [#1547](https://github.com/pl0n3r/Factory/issues/1547) |
| `docs/performance-remediation.md:L25-U4` | esa validación corresponde al detector y al productor autorizado.\n\nSolo una mejora medida con esa procedencia mínima, estados `CURRENT` y clasificación n | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L25-U5` | El caller conserva responsabilidad de verificar la autenticidad de cada muestra y el cambio realmente aplicado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-remediation.md:L29-U1` | solo valida/deriva artefactos. #313 consume el resultado para Readiness/E2E. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/performance-team-compiler-bridge.md:L3-U1` | El adaptador performance.team_compiler_bridge.compile_performance_team consume una deteccion validada de Performance Contract v1 con **evaluated_at UTC obl | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L3-U1` | Este fallback existe únicamente para evitar que una limitación de capacidad del reviewer detenga indefinidamente trabajo ya validado durante la fase `const | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L7-U1` | La policy solo acepta el fallback cuando se cumplen **todas** estas condiciones: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L9-U1` | La fase canónica leída desde `datos.yml` de la **BASE exacta** del PR es `construccion`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L10-U1` | Existe evidencia de rate limit del reviewer requerido asociada al **HEAD exacto**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L11-U1` | Sobre ese mismo HEAD existe un fallo de `Factory policy / Validar decisiones y límite de revisión`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L12-U1` | Existe un reintento posterior verificable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L13-U1` | Los demás gates obligatorios observados sobre ese HEAD están terminales y verdes: CI, pruebas/aceptación, Sonar, CodeQL, Coordinación y Privacidad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L14-U1` | No existe ningún thread abierto/no resuelto del reviewer requerido ni un `CHANGES_REQUESTED` sobre el HEAD exacto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L16-U1` | Un único rate limit sin reintento verificable nunca basta. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L22-U1` | comentario `Review rate limited` posterior al commit HEAD; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L23-U1` | Policy falla sobre ese HEAD; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L24-U1` | un segundo comentario rate-limited del reviewer aparece después del fallo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L26-U1` | Para ese caso, la policy exige una cadena más explícita: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L28-U1` | Policy falla sobre el HEAD exacto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L29-U1` | el `OWNER` del repositorio publica exactamente `@coderabbitai review` después de ese fallo; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L30-U1` | el comentario del reviewer requerido se actualiza después de ese trigger y contiene una señal terminal de capacidad (`Review rate limited` o `Review limit  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L31-U1` | el body actualizado contiene el SHA completo del HEAD exacto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L32-U1` | `updated_at` es posterior al trigger y no puede ser anterior a `created_at`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L34-U1` | Sin el trigger OWNER posterior al fallo de Policy, el fallback permanece bloqueado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L40-U1` | Ese texto, por sí solo, **no constituye revisión ni permite fallback**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L44-U1` | una sexta página solo puede estar vacía. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L45-U1` | Ningún contenido del PR candidato determina esa | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L48-U1` | La alternativa requiere **toda** esta correlación adicional: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L50-U1` | La timeline está completa, contiene un último evento `committed` cuyo SHA | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L54-U1` | Existe un primer comentario de **`coderabbitai[bot]` real**, con | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L57-U1` | Más tarde, un comentario **`OWNER`** con el cuerpo literal | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L60-U1` | Una **segunda respuesta distinta** del bot, posterior a ese comando y | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L64-U1` | No hay `committed`, `head_ref_force_pushed` ni `synchronize` que | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L71-U1` | intactos. `live` nunca admite esta excepción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L71-U2` | No se modifica `Factory@v1` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L76-U1` | No permite cambiar el HEAD para provocar otra ronda. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L77-U1` | No permite ignorar findings abiertos ni un `CHANGES_REQUESTED` del reviewer sobre el HEAD exacto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L78-U1` | No permite pasar con CI, pruebas, Sonar, CodeQL, Coordinación o Privacidad en rojo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L79-U1` | No permite activar el fallback cuando la fase es `live`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L80-U1` | No cambia el límite de rondas de reviewers ni elimina la obligación de revisión externa antes de live. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L81-U1` | No permite convertir cualquier edición de comentario en evidencia: el retry OWNER, el orden temporal y el HEAD exacto siguen siendo obligatorios. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L83-U1` | Si la fase no puede leerse de forma canónica desde la BASE, el fallback queda deshabilitado y la policy conserva el comportamiento estricto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L89-U1` | el SHA exacto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L90-U1` | la hora del reintento rate-limited o de la actualización terminal del comentario canónico; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L91-U1` | el enlace al comentario del reviewer; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L92-U1` | una advertencia explícita de que la revisión externa sigue siendo obligatoria para `live`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L98-U1` | Así un PR no puede habilitar su propio fallback cambiando `datos.yml`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L100-U1` | La lectura está paginada y acotada a un máximo de **5 páginas / 500 check-runs**: `total_count` debe ser entero, permanecer idéntico en todas las páginas,  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L100-U2` | El propio check de policy y el agregado circular `Validar` no se usan para decidir si los demás controles están verdes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L102-U1` | La lectura de reviews, comentarios, BASE exacta y reviewThreads continúa usando únicamente permisos read-only. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L104-U1` | Cualquier ambigüedad —fase ausente, demasiados check-runs/threads para evaluar de forma acotada, evidencia malformada, HEAD distinto, trigger no OWNER, sec | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L117-U1` | El bridge acepta únicamente: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L119-U1` | `v1`, para conservar el canal estable histórico; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L120-U1` | un SHA lowercase exacto de 40 caracteres hexadecimales. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L124-U1` | El input solo selecciona el `ref` del checkout interno en `.factory` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L124-U2` | únicamente permite validar un repair inmutable mientras la decisión de promoción del canal estable permanece separada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L129-U1` | El retry SHA-less exige timeline REST completa, único comando OWNER, ausencia de comandos competidores, respuesta bot inmutable y fallo Policy exact-HEAD p | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/politica-revisor-externo.md:L129-U2` | Una revisión `COMMENTED` que solo indica rate-limit no es revisión sustantiva | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L7-U1` | **#6 Product Feedback:** impacto técnico/producto declarado u observado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L8-U1` | **#7 Cost Control:** tiempo/tokens/CI observados o estimados con confidence. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L9-U1` | **#161 Feedback Mesh:** outcomes, bloqueos, evidencia y provenance. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L10-U1` | ControlBot puede presentar estas dimensiones, pero no convertirlas en una decisión automática. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L18-U1` | dependencias desbloqueadas (`unlocks`); | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L22-U1` | impacto técnico/producto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L23-U1` | reversibilidad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L27-U1` | `status=known\\|unknown`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L28-U1` | valor estructurado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L29-U1` | `confidence`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L30-U1` | `source=observed\\|estimated\\|declared`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L31-U1` | `provenance`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L33-U1` | No se sustituye por cero, ROI estimado ni valor inventado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L37-U1` | `explain_tradeoffs()` solo acepta WorkItems: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L39-U1` | ya marcados como elegibles; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L40-U1` | con la **misma prioridad del dueño**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L46-U1` | `owner_priority_authoritative=true`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L47-U1` | `decision=null`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L48-U1` | `authority=owner_unchanged`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L49-U1` | lista explícita de incertidumbres. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/portfolio-signals.md:L55-U1` | ControlBot puede explicar: “A desbloquea más dependencias pero tiene mayor riesgo y costo estimado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L3-U1` | **solo el dueño** administra rulesets/protección de ramas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L7-U1` | ausencia de un ruleset visible no se interpreta como ausencia de protección. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L19-U1` | Caso que motivó el guard: FactoryRunner PR #82 se fusionó en `2fd240f570c41e21f8089bcc0862c363695c11bb` con `validar-pr / Labels = failure` y sin éxito pos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L23-U1` | El payload canónico crea un ruleset dedicado que **solo añade** `Etiquetas` como required status check sobre la rama por defecto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L32-U1` | `name = factory-required-labels`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L33-U1` | `target = branch`, `enforcement = active`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L34-U1` | `ref_name.include = ["~DEFAULT_BRANCH"]`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L35-U1` | check `Etiquetas` del GitHub Actions App (`integration_id=15368`); | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L36-U1` | `strict_required_status_checks_policy = false` y ningún bypass actor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L38-U1` | Aplicación administrativa, **solo por el dueño** y después de revisar el payload: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L50-U1` | nunca se reemplaza a ciegas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L54-U1` | Aplicar etiquetas a un PR usa el endpoint de Issues y no requiere `pull-requests: write`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L54-U2` | Como los siete repos de la fábrica son públicos, el sweep consulta `check-runs` por REST público sin token, valida el SHA antes de construir la URL y manti | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L56-U1` | un PR sin estado recibe `estado: en revisión`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L57-U1` | si contiene una única referencia `Closes/Fixes/Resolves #N`, tipo y prioridad faltantes se heredan del Issue servidor-side; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L58-U1` | etiquetas ambiguas o incompletas fallan cerrado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L59-U1` | no se escriben contenidos, checks, Actions ni secretos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/pr-label-governance.md:L63-U1` | Si el último check terminal no es `success`, el workflow publica **un solo comentario** en el PR con marker `factory-pr-label-governance-alert` y evidencia | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L9-U1` | `ops/factory/build` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L10-U1` | `ops/factory/backup` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L11-U1` | `ops/factory/migrate` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L12-U1` | `ops/factory/deploy` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L13-U1` | `ops/factory/rollback` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L15-U1` | La diferencia es el contexto: durante preview Factory crea un directorio temporal y expone únicamente las variables `FACTORY_PREVIEW=1`, `FACTORY_SYNTHETIC | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L17-U1` | Los adapters del proyecto deben ramificar explícitamente por `FACTORY_PREVIEW=1` y operar solo dentro de `FACTORY_PREVIEW_ROOT`. **Nunca deben tocar recurs | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L29-U1` | `ops/factory/preview-health`: confirma versión, SHA y schema cuando aplica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L30-U1` | `ops/factory/preview-smoke`: valida las superficies críticas del artifact preview. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L31-U1` | `ops/factory/preview-e2e`: ejecuta el recorrido sintético mínimo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L37-U1` | Un gate final `Validar` depende de ambos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/preview-preproduccion.md:L37-U2` | en `push` el preview queda skipped, mientras que en `pull_request` debe terminar success. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L3-U1` | no habilita por sí solo acciones, coordinación, merges ni releases. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L7-U1` | serializar solo por dependencia real de datos, colisión real de archivos o gate de autoridad vigente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L7-U2` | Maximizar paralelismo **demostrable**, nunca inferido de que dos tareas son conceptualmente distintas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L11-U1` | Una cola con cero hojas disponible en los siete repositorios exige inventario completo y escalera no ociosa | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L11-U2` | no da permiso de convertir bloqueos en trabajo listo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L11-U3` | Diferenciar disponible, reservado, en revisión, bloqueado y planificado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L11-U4` | todo bloqueo lleva causa y condición verificable de salida. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L11-U5` | El catálogo oficial incluye además `estado: requiere recuperación` / `status: recovery required` como **sexto estado** disjunto: una lease inactiva requier | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L11-U6` | Mientras #1098/#1100 solo admitan cinco estados, un snapshot con recovery falla cerrado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L15-U1` | Un módulo puro build-ahead con fakes deterministas permite preparación offline cuando un gate operativo impide activación | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L19-U1` | Una lease activa sobre un directorio no se ignora por prometer editar archivos distintos: el árbitro necesita pruebas completas de diff exact-SHA y depende | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L19-U2` | Si el diff está ausente, truncado, stale, ambiguo o cambió el SHA, falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L19-U3` | Ni siquiera hunks distintos del mismo archivo permiten paralelismo automático. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L23-U1` | planificado ≠ bloqueado y available ≠ ready si faltan tandas, dependencias, reserva o autoridad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L23-U2` | UNKNOWN nunca equivale a GREEN. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L23-U3` | Verificar evidencia terminal exact-HEAD | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L23-U4` | para puertas D-043 exigir VALIDATED_IN_PRODUCTION, SHA e identidad, sin pendientes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L27-U1` | construccion permite preparar trabajo reversible y offline dentro de D-068 | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L27-U2` | D-063 exige atestación válida para excepciones informativas | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L27-U3` | Factory@v1 mantiene su puerta vigente exact-SHA mientras no se integre otro contrato: Factory #1080 es propuesta, **no** autorización autoejecutable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L31-U1` | AC-NN debe señalar unittest existente/implementable o check real, nunca un nombre ficticio. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L35-U1` | Verificar rate_limit y conservar capacidad para reparaciones | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L35-U2` | Autenticación compartida no garantiza 5.000 solicitudes disponibles en el instante. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L39-U1` | Nunca fabricar APPROVED, HEALTH, actividad, throughput o readiness. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L43-U1` | Reportar por repositorio y global conteos separados de disponible, reservado, en revisión, bloqueado y planificado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L43-U2` | identificar causa y fuente de cada bloqueo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L43-U3` | El `estado: requiere recuperación` / `status: recovery required` es un **sexto estado** canónico que **no es disponible**, blocked ni planned | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L43-U4` | Contarlo por separado solo tras integrar el contrato de Factory #1102 en #1098/#1100 | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L43-U5` | antes, rechazar snapshots que no puedan representar recovery, sin fabricar GREEN o `queue_empty`. **Utilización = agentes activos verificados / capacidad d | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L43-U6` | Sin evidencia autenticada de agentes activos, capacidad, heartbeat y frescura, marcar UNKNOWN / no calculable, nunca 0 % o 100 %. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/principios-construccion.md:L47-U1` | Esta documentación no cambia Coordinación, no autoriza merges, releases, tags, ejecución GitHub, live, gasto ni producción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L9-U1` | El descubridor recibe señales explícitas y no secretas: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L11-U1` | rutas relativas del repositorio; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L12-U1` | presencia de manifests conocidos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L13-U1` | estructura declarada de esos manifests; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L14-U1` | capacidades declaradas por un caller confiable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L26-U1` | `frameworks`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L30-U1` | `integrations`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L31-U1` | `capabilities`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L33-U1` | `extensions`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L34-U1` | `fingerprint`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L37-U1` | No se sustituye por una conjetura. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L48-U1` | Las capacidades futuras deben añadirse | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/project-dna.md:L50-U1` | Un cambio incompatible de los campos base requiere una nueva versión | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L5-U1` | El destino permitido es `pl0n3r/<repo>` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L5-U2` | tanto un repo nuevo como uno adoptado deben ser **privados**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L6-U1` | La autoridad externa es exclusivamente `FACTORY_PROVISION_TOKEN` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L6-U2` | el `GITHUB_TOKEN` del workflow conserva `contents: read`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L7-U1` | La credencial debe pertenecer a `pl0n3r` y limitarse a las capacidades necesarias para crear un repositorio privado y empujar su commit inicial. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L7-U2` | Factory valida la identidad autenticada antes de la primera escritura. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L8-U1` | Si la credencial falta, el workflow falla antes del checkout y antes de cualquier escritura remota. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L8-U2` | Su valor nunca se pega en Issues, chats, URLs remotas ni logs. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L9-U1` | El runtime se descarga desde el SHA exacto que disparó el workflow | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L9-U2` | la gobernanza se descarga por separado desde `Factory@v1`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L9-U3` | El SHA exacto resuelto de esa gobernanza queda registrado en `.factory/provisioning.json`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L10-U1` | El bootstrap construye localmente `template/ + .factory/provisioning.json`, crea un único root commit en `main` y lo empuja mediante un `GIT_ASKPASS` efíme | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L10-U2` | No usa Git Database REST para inicializar un repositorio vacío. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L11-U1` | La descripción de recuperación liga un digest SHA-256 de la intención completa, incluida la idempotency key completa y el SHA exacto de gobernanza. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L12-U1` | Un retry con el mismo marker converge sin nuevas escrituras. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/provisioning.md:L12-U2` | Un repo preexistente público, no vacío, con identidad distinta o con marker distinto falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L3-U1` | Las decisiones nuevas deben entenderse sin conocer GitHub, programación ni | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L4-U1` | El mensaje breve debe explicar **qué se decide y qué cambia**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L8-U1` | **Pregunta**: una frase corta en `title_simple`, preferiblemente una pregunta. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L9-U1` | **Resumen**: dos o tres frases cortas en `summary_simple`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L9-U2` | No más de 25 palabras por oración. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L10-U1` | **Opciones**: `label` es un título corto | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L10-U2` | `effect` y `explain_simple` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L12-U1` | **Impacto**: indicar claramente si afecta datos de personas, dinero, redes, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L14-U1` | **Recomendación**: usar `why_recommended` para explicar una opción en una frase. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L15-U1` | **Detalles técnicos separados**: referencias a issues, versiones, hashes, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L19-U1` | Evitar palabras como `exact-main`, `fail-closed`, `exact-HEAD`, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L28-U1` | Todavía no se conectarán cuentas ni personas reales. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L30-U1` | **A: Preparar prueba.** Solo se crea una prueba con datos inventados. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L35-U1` | **Recomendación:** Preparar la prueba permite revisar el resultado sin riesgos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas-lenguaje-simple.md:L47-U1` | validación histórica: no se alteran sus opciones, autoridad, identificadores | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L3-U1` | La fábrica solo interrumpe al dueño por categorías cerradas: dirección de producto, marca, dinero, legal, datos reales de clientes, publicar 1.0.0, manteni | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L18-U1` | `title_simple`: pregunta breve, una línea; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L19-U1` | `summary_simple`: resumen de hasta 3 líneas; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L20-U1` | `why_recommended`: una frase; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L21-U1` | `blocks`: qué trabajo queda bloqueado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L23-U1` | `effect`: qué pasa si se elige; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L24-U1` | `pros[]` y `cons[]`: entre 1 y 5 elementos, texto corto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L25-U1` | `risk`: `low`, `medium` o `high`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L26-U1` | `cost`: texto corto o vacío; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L27-U1` | `reversible`: booleano; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L28-U1` | `explain_simple`: qué significa elegir esa opción, explicado como a alguien de 12 años, hasta 3 líneas y 400 caracteres. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L30-U1` | `explain_simple`: la pregunta explicada sin jerga, hasta 4 líneas y 600 caracteres. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L40-U1` | Por opción, `effect` y `cost` son cadenas, `reversible` es booleano JSON (`true`/`false`), `risk` acepta únicamente `low`, `medium` o `high`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L40-U2` | Solo `pros` y `cons` admiten listas de 1 a 5 cadenas cortas. `blocks` nunca es una lista ni `risk` admite una explicación libre. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L48-U1` | Si el parser clasifica una puerta confiable como `invalid-gate`, el workflow publica una explicación **idempotente** con el campo y la regla incumplida, si | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L48-U2` | La corrección posterior del marker válido restaura `estado: disponible` cuando el bloqueo fue gestionado por este flujo | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L52-U1` | La compatibilidad existe para no romper Issues históricos. **Toda puerta nueva escrita por un agente debe incluir `explain_simple` en la raíz y en cada opc | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L56-U1` | El contexto y las opciones son acotados. `recommendation` y `safe_default` deben referir opciones existentes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L60-U1` | Solo Issues creados por actores con asociación `OWNER`, `MEMBER` o `COLLABORATOR` pueden activar la cola. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L60-U2` | Un Issue externo, aunque contenga un marker sintácticamente válido, nunca etiqueta, asigna ni menciona al dueño. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L66-U1` | La cola trata una puerta como una decisión activa identificable, no solo como un número de Issue. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L68-U1` | Las demás se cierran como `duplicate`, se retiran de `decisión: dueño` y reciben un marker idempotente que referencia la canónica | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L68-U2` | este paso **nunca** materializa una opción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L70-U1` | Si una puerta equivalente no canónica ya contiene un journal de decisión, o aparecen evidencias incompatibles entre equivalentes, la reconciliación falla c | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L74-U1` | Una puerta válida se resuelve de forma máquina únicamente con un comentario exacto de un actor con asociación `OWNER`. `MEMBER\\|COLLABORATOR` pueden segui | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L78-U1` | La opción debe existir realmente en el marker `factory-human-gate`, el Issue debe seguir abierto y conservar `decisión: dueño`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L80-U1` | Aceptar `/decidir X` **solo materializa la elección**: publica una evidencia idempotente y controlada, retira `decisión: dueño`, sustituye únicamente la et | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L80-U2` | Los flujos dependientes deben reconciliarse por su propio contrato. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L82-U1` | La evidencia `factory-human-decision` usa journal **v2** y contiene únicamente la opción elegida y `gate_sha256`: un SHA-256 de la representación normaliza | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L82-U2` | El comando queda además ligado al snapshot `event.issue.body`: su fingerprint debe coincidir con el primer GET vivo y con cada revalidación posterior. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L82-U3` | Si la puerta se edita después del comentario, ese comentario antiguo no autoriza la puerta nueva | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L82-U4` | Un retry solo puede reanudar la misma opción cuando ese fingerprint sigue coincidiendo con la puerta vigente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L82-U5` | Si cambia cualquier parte semántica del gate —aunque conserve la misma letra de opción—, o aparece evidencia legacy/incompatible, el flujo falla cerrado y  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L84-U1` | no se infieren retroactivamente como comandos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L88-U1` | Los repositorios consumidores deben incluir `template/.github/workflows/seguridad.yml` (o un caller funcionalmente equivalente) para que las puertas humana | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L90-U1` | procesa `issues: opened\\|edited\\|reopened` para clasificar y enrutar `factory-human-gate`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L91-U1` | procesa únicamente comentarios exactos `/decidir A` .. `/decidir D` de un actor `OWNER`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L92-U1` | hace checkout **solo** de `pl0n3r/factory@v1` en `.factory`, nunca del código del consumidor; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L93-U1` | ejecuta `.factory/seguridad/puertas_humanas.py`, `sincronizar_puerta.py` y `decision_respuesta.py` con permisos mínimos `contents: read` + `issues: write`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L94-U1` | conserva el journal v2, deduplicación de puertas, fingerprint exacto del gate y fail-closed implementados por Factory. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L96-U1` | Tener únicamente `decisión: dueño` o un workflow de Coordinación **no** materializa `/decidir X`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L96-U2` | Los repositorios existentes deben adoptar el caller en un PR propio | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L96-U3` | comentarios humanos anteriores a la adopción no se reproducen ni se convierten retroactivamente en journal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L96-U4` | Tras adoptar el workflow, el dueño debe emitir un comentario nuevo sobre la puerta vigente si todavía desea la misma opción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L100-U1` | Si no hay respuesta, el agente puede seguir únicamente con la opción declarada como `safe_default` cuando esa opción sea realmente segura y reversible | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L100-U2` | acciones que por política requieren autorización explícita continúan bloqueadas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L104-U1` | El clasificador no acepta rutas de archivos por CLI. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L104-U2` | Python limita el tamaño del evento y del cuerpo del Issue, valida esquema cerrado y solo emite `status` + `category`, nunca contexto, resúmenes, opciones,  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L108-U1` | En eventos `opened\\|edited\\|reopened`, el workflow procesa la cola únicamente mientras el Issue siga **abierto** y verifica primero la asociación del aut | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L108-U2` | Un Issue cerrado/completado no puede reingresar a `decisión: dueño` por una edición posterior. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L108-U3` | Un error estructural del marker no puede degradarse silenciosamente a trabajo autónomo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L112-U1` | El reusable workflow `.github/workflows/auditoria-privacidad.yml` puede crear una puerta de categoría `legal` únicamente cuando el mapa `datos.yml` introdu | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L112-U2` | La puerta es **informativa (D-063)** solo cuando `phase=construccion` y `datos.yml` atestigua explícitamente `d063_attestation.nothing_live=true` y `d063_a | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L112-U3` | Si la atestación falta, contiene `false`/`null`, es inválida o el proyecto está `live`, la puerta permanece bloqueante y requiere revisión jurídica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L114-U1` | La auditoría nunca copia valores observados del código a Issues: publica únicamente identificadores controlados de señales/proveedores y rutas del reposito | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L114-U2` | El Issue técnico de auditoría es idempotente y se cierra automáticamente cuando deja de haber drift. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/puertas-humanas.md:L114-U3` | Una puerta legal, en cambio, **no se cierra automáticamente**: requiere la decisión humana correspondiente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L7-U1` | Performance (#304) y Recovery (#305) son dimensiones externas: el contrato guarda `required` + `source_ref` y nunca copia budgets, estado o lógica de esos  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L15-U1` | `expected_visibility`: `public\\|private`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L16-U1` | `analysis_method`: `automatic\\|ci`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L17-U1` | `max_analysis_age_seconds`: freshness máxima del análisis; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L18-U1` | `max_organization_line_usage_percent`: porcentaje máximo de uso de líneas de la organización antes de degradar la señal; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L19-U1` | `max_open_vulnerabilities`, `max_open_bugs` y `max_open_hotspots`: deuda abierta máxima permitida; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L20-U1` | `max_debt_age_days`: antigüedad máxima permitida para deuda abierta. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-contract.md:L22-U1` | Si `sonar` está ausente, el significado es **“Sonar monitoring no configurado”**: aguas abajo no se aplican thresholds Sonar y esa ausencia nunca debe rein | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-engineering.md:L19-U1` | Los gates exigidos por DoD se presentan como evidencia current y una regresión ya verificada no degrada el resultado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-engineering.md:L31-U1` | evidencia stale o UNKNOWN → Quality Health `UNKNOWN` → no ready; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-engineering.md:L32-U1` | regresión FLAKY → nunca `PASS` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-engineering.md:L32-U2` | permanece degradación explícita; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-engineering.md:L33-U1` | un blocker crítico nunca se diluye con gates menores verdes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-engineering.md:L41-U1` | Quality solo consume sus proyecciones. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-engineering.md:L43-U1` | El rollout a Condor, GrindFlow, BRVTAL, ControlBot, AutoFactory y FactoryRunner requiere evidencia propia por proyecto y no forma parte de #348. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-gates.md:L7-U1` | Risk y DoD consumen Quality Contract solo si valida con #343, versión/fingerprint coinciden con `Project DNA.extensions.quality_contract` y cada superficie | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-gates.md:L7-U2` | Falta, mismatch o superficie desconocida falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-gates.md:L11-U1` | La criticidad Quality solo puede elevar riesgo: `low→low`, `medium→medium`, `high\\|critical→high`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-gates.md:L11-U2` | Nunca reduce señales, blast radius ni controles. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L7-U1` | La matriz esperada `surface × required_gate` se deriva **únicamente** de Quality Contract v1. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L11-U1` | `status=PASS\\|FAIL\\|UNKNOWN\\|STALE`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L12-U1` | timestamp observado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L13-U1` | referencia de evidencia. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L15-U1` | Evidencia ausente, stale o unknown nunca equivale a PASS. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L19-U1` | VERIFIED no degrada por sí sola; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L20-U1` | FLAKY y OBSERVED nunca habilitan PASS; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L21-U1` | REPRODUCED no resuelta bloquea una superficie crítica y degrada una no crítica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L31-U1` | PASS no degrada por sí solo; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L32-U1` | UNKNOWN y STALE proyectan Quality Health a UNKNOWN y nunca habilitan PASS; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L33-U1` | NOT_APPLICABLE se conserva visible con razón/provenance, es neutral para el agregado, no crea clase correctiva y nunca se reetiqueta como PASS; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L34-U1` | un FAIL con evidencia CURRENT afecta la salud, pero conserva freshness global CURRENT; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L35-U1` | snapshot STALE exige señales requeridas STALE | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L35-U2` | una señal contractualmente NOT_APPLICABLE conserva N/A. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L35-U3` | PASS/FAIL solo son válidos con freshness CURRENT y cualquier combinación incoherente falla cerrado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L36-U1` | FAIL de Quality Gate o CE task es bloqueante; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L37-U1` | FAIL de line usage, configuración/cobertura o deuda degrada y emite una clase correctiva cerrada; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L38-U1` | razones y `evidence_refs` del normalizador se preservan con validación fail-closed; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L39-U1` | ausencia de evidencia Sonar cuando el contrato la exige produce UNKNOWN; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L40-U1` | contratos legacy sin bloque `sonar` conservan exactamente el comportamiento anterior. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L44-U1` | no se vuelven a ejecutar detectores; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L45-U1` | no se copian budgets; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L46-U1` | no se recalculan RPO/RTO; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L47-U1` | ausencia de una dimensión requerida produce UNKNOWN. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L53-U1` | fallo o regresión reproducida en superficie crítica → BLOCKED; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L54-U1` | evidencia ausente/stale/unknown, incluida Sonar requerida, → UNKNOWN; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L55-U1` | fallo conocido no crítico o dimensión externa degraded → DEGRADED; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L56-U1` | solo evidencia current sin degradaciones → PASS. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L62-U1` | PASS y DEGRADED pueden continuar; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L63-U1` | UNKNOWN y BLOCKED nunca son ready; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L64-U1` | `recalculated=false`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-health.md:L79-U1` | por eso `derive_quality_health()` exige `project_ref` explícito y valida cada regresión contra ese valor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L9-U1` | La extensión contiene únicamente: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L12-U1` | `source_ref`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L13-U1` | `fingerprint` SHA-256 del Quality Contract canónico validado por #343. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L17-U1` | El Quality Contract completo **no se copia** dentro de Project DNA. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L18-U1` | Project DNA **no infiere** quality gates desde stack, rutas, frameworks o capabilities. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L19-U1` | Si no se aporta explícitamente un Quality Contract, `discover_project_dna()` conserva `extensions={}`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L20-U1` | `attach_quality_contract()` valida primero Project DNA y Quality Contract, luego recalcula el fingerprint de Project DNA. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L21-U1` | `validate_project_dna()` valida el shape cerrado de `extensions.quality_contract` cuando existe. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L22-U1` | El namespace general `extensions` permanece abierto para futuras capacidades. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-project-dna.md:L24-U1` | Project DNA solo declara qué contrato gobierna el proyecto | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L9-U1` | `before`: cantidad de corridas, fallos, referencia de evidencia y timestamp; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L10-U1` | `after`: la misma forma para demostrar el estado posterior; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L11-U1` | `regression_test_ref`: referencia del test de regresión cuando existe; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L12-U1` | causa raíz y prevención necesarias para derivar una lesson válida. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L18-U1` | Un fallo se considera reproducido únicamente cuando existe más de una corrida y todas fallan. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L18-U2` | Cualquier muestra con `0 < failures < runs`, sea `before` o `after`, se clasifica **FLAKY** y nunca puede convertirse en PASS. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L20-U1` | Un fix solo queda verificado cuando: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L22-U1` | el fallo `before` es reproducible; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L23-U1` | `after` termina con cero fallos; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L24-U1` | existe `regression_test_ref`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L25-U1` | la evidencia temporal y las referencias son válidas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L27-U1` | Solo en ese caso se genera una lesson compatible con `lecciones.memoria`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L27-U2` | Una observación no verificada conserva evidencia diagnóstica, pero no produce material de guardrail. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L31-U1` | Dos o más lessons verificadas, con fuentes GitHub distintas y el mismo patrón causal/preventivo, se entregan a `compile_guardrail_candidates()` del **Exper | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L31-U2` | Este módulo solo expone el candidato retornado por ese contrato: **no promueve** candidatos a política estable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L33-U1` | No se crea un Immune/Guardrail Engine paralelo, no hay scheduler, backlog, Issues automáticos ni ejecución de remediaciones. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L37-U1` | Quality Health y proyección a **Readiness #293** pertenecen a #347. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L38-U1` | Clasificación/corrección operativa mediante **Queue #269** pertenece a #347 y contratos existentes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L39-U1` | El E2E transversal pertenece a #348. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L40-U1` | Este módulo no modifica Performance ni Recovery. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-regression.md:L41-U1` | No existe autoridad para ejecutar fixes, promover políticas o declarar producción sana. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L3-U1` | **Estado post-F1C (#1308 / PR #1309): Sonar Watch no se ejecuta automáticamente.** Se eliminó el cron cada seis horas y `workflow_dispatch` al retirar `.gi | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L3-U2` | Los Issues `[AUTO] Sonar` (#1052/#1053) **no se refrescan automáticamente**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L3-U3` | El motor offline `scripts/sonar-watch.py` y la proyección `quality.sonar` permanecen disponibles solo para ejecuciones expresamente autorizadas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L22-U1` | no requieren reinterpretar observación runtime como política. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L24-U1` | Migrar `analysis_method` de un proyecto requiere nueva decisión del dueño. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L30-U1` | Si alguno exige `private` y no existe `SONAR_TOKEN`, aborta sin tocar la red. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L32-U1` | Payload ausente o ambiguo falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L32-U2` | no se convierte en política implícita. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L42-U1` | El parser exige exactamente un setting `sonar.autoscan.enabled` con valor textual `true` o `false`, normalizado a `automatic` o `ci`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L42-U2` | Ausencia, duplicidad, key inesperada o cualquier otro valor falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L46-U1` | esto **no autoriza ejecutarlo** ni sincronizar Issues reales. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L48-U1` | Los checks **Sonar CI-based** (`sonar.yml`) y **CodeQL** siguen como validadores CI de PR y **no sustituyen** la sincronización periódica Sonar→GitHub Issu | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L52-U1` | un `PASS` solo lo cierra con freshness `CURRENT`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L52-U2` | Una señal `NOT_APPLICABLE` no abre Issue: si existe uno abierto del mismo marker, Sonar Watch añade una sola explicación con razón/source_ref y lo cierra | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L54-U1` | Todo Issue abierto que administra el watcher se crea o reconcilia con `tipo: calidad`, `prioridad: media` y `estado: bloqueado`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L54-U2` | Las alertas son observaciones, **no hojas ejecutables**: el cuerpo explica que solo un `PASS/CURRENT` o un `NOT_APPLICABLE` canónico puede desbloquearlas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L54-U3` | En cierre verificado, el estado de GitHub pasa a `closed` y la etiqueta a `estado: completado` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L54-U4` | el contenido histórico no se reescribe como PASS. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L54-U5` | Se preservan etiquetas fuera de las familias tipo/prioridad/estado y se rechazan clasificaciones gobernadas contradictorias antes de mutar. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L56-U1` | El cuerpo conserva estado, razón, freshness, referencias opacas y un origen validado `https://sonarcloud.io/project/overview?id=<sonar_key>`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L60-U1` | ControlBot y Factory usan CI: cobertura ausente sigue siendo un FAIL real y sus Issues no se cierran como N/A. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L60-U2` | Cambiar método o visibilidad exige actualizar el contrato | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar-watch.md:L64-U1` | Si falta configuración, el contrato es ambiguo, una respuesta no respeta su shape o la proyección difiere de la evidencia normalizada, falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L5-U1` | Debe declarar: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L7-U1` | `project` dentro del catálogo explícito: `brvtal`, `condor`, `controlbot`, `factory`, `factoryrunner`, `grindflow`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L8-U1` | `snapshot_at` con zona horaria y `evidence_refs` no sensibles; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L9-U1` | `quality_gate` con estado `OK\\|ERROR` y condiciones fallidas cuando aplique; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L10-U1` | `analysis` con `analyzed_at`, método `automatic\\|ci` y si existe cobertura publicable; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L11-U1` | `ce_task` y su `error_message` cuando el servidor marca `FAILED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L12-U1` | uso de líneas de organización, visibilidad y deuda histórica; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L13-U1` | ausencia conocida de una señal como `null`, no omitiendo la clave. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L15-U1` | Un valor explícitamente ausente (`null`) se normaliza como **UNKNOWN**, nunca como PASS. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L21-U1` | `quality_gate`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L22-U1` | `analysis_freshness`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L24-U1` | `organization_line_usage`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L25-U1` | `visibility`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L26-U1` | `analysis_method`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L28-U1` | `historical_debt`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L30-U1` | Cada señal contiene `status=PASS\\|FAIL\\|UNKNOWN\\|STALE\\|NOT_APPLICABLE`, `observed_at`, `freshness`, `evidence_refs`, razón y detalles normalizados. `N | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L32-U1` | `analysis_method=ci` exige evidencia de cobertura: `coverage_available=false` es FAIL. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L32-U2` | la señal se conserva como `NOT_APPLICABLE`, nunca como PASS. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L32-U3` | De forma equivalente, `organization_line_usage` es `NOT_APPLICABLE` solo cuando el contrato declara visibilidad pública | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L34-U1` | Los `evidence_ref` item-level se validan pero no se propagan al agregado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/quality-sonar.md:L34-U2` | la autoridad del lote queda en `snapshot.evidence_refs`, evitando que un snapshot válido falle solo por cantidad de hallazgos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L5-U1` | El contrato de un Issue no se declara cumplido por un PR parcial ni por un test offline. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L20-U1` | **8 Issues abiertos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L20-U2` | 0 cierres automáticos** justificables por aceptación integral. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L20-U3` | La existencia de commits parciales no permite cerrar épicas ni cancelar reservas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L21-U1` | No se fusiona Factory@v1, no se activa ninguna liberación de leases, no se cambian gates ni producción. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L21-U2` | Esta hoja solo reclama su documento y su test. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L22-U1` | Antes de un corte posterior hay que releer Issues, HEAD de main, PRs, CI, reservas y evidencia productiva. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reconciliacion-issues-20261024.md:L22-U2` | Este documento no prueba el estado futuro. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L7-U1` | `object_storage`: destino técnico primario/offsite. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L7-U2` | Siempre permanece primario. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L8-U1` | `google_drive`: cold-copy opcional y solo si el Recovery Manifest v1 declara `offsite.cold_copy=google_drive`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L9-U1` | `icloud`: no soportado y no es dependencia del contrato. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L13-U1` | Cada intención recibe un Recovery Manifest v1 ya validable por #327 y un request cerrado: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L15-U1` | `provider`: `object_storage\\|google_drive`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L16-U1` | `operation`: `upload\\|materialize\\|verify`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L17-U1` | `object_ref`: referencia opaca, no path ni URL; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L18-U1` | `checksum_sha256`: SHA-256 hexadecimal lowercase; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L19-U1` | `idempotency_key`: referencia opaca y estable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-adapters.md:L25-U1` | El módulo falla cerrado ante campos extra, providers/operaciones desconocidos, refs con path/URL, checksums inválidos y formas sensibles. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-contract.md:L7-U1` | al menos una debe aplicar. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-contract.md:L9-U1` | Encryption es obligatoria y el manifiesto solo declara key_material=EXTERNAL_ONLY: nunca contiene llaves, tokens ni credenciales. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-contract.md:L9-U2` | El validador falla cerrado ante campos desconocidos, tipos/coherencia inválidos o formas sensibles. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-drill.md:L5-U1` | `evaluate_restore_drill()` exige checksum consistente y health/smoke/integrity exitosos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-e2e.md:L18-U1` | El escenario sano usa únicamente referencias opacas y evidencia simulada/determinista. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-e2e.md:L18-U2` | consume solo el artefacto verificado/offsite. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-e2e.md:L21-U1` | backup fresco + drill PASSED → `HEALTHY` → Readiness reutiliza `HEALTHY` sin recalcular; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-e2e.md:L22-U1` | drill vigente con RPO/RTO excedidos → `DEGRADED` con `rpo_breached` y `rto_breached` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-e2e.md:L22-U2` | un recovery point stale también permanece explícito como `backup_stale`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-pipeline.md:L5-U1` | Flujo canónico: **snapshot/dump → checksum → encrypt → upload object storage → verify → cold-copy opcional → evidence**. `build_backup_pipeline()` solo emi | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-pipeline.md:L7-U1` | Object storage siempre es `primary_offsite`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-pipeline.md:L7-U2` | Google Drive solo existe como `cold_copy` cuando el manifest lo exige y nunca sustituye el destino primario. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-pipeline.md:L9-U1` | `verify_backup_evidence()` solo devuelve `VERIFIED` si manifest, pipeline y evidencia coinciden y existen encryption observada, checksum exacto, primary ve | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L6-U1` | `HEALTHY`: backup VERIFIED fresco y restore drill PASSED fresco. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L7-U1` | `DEGRADED`: evidencia vigente con breach conocido de RPO/RTO o retention drift. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L8-U1` | `UNKNOWN`: evidencia requerida ausente o stale. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L8-U2` | Nunca cuenta como sano. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L9-U1` | `BLOCKED`: evidencia inválida/incoherente, checksum/offsite/authority/target contractual inválido. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L13-U1` | Restore anterior al backup no produce estado HEALTHY | CUBIERTO | `recovery/status.py` + `tests/test_recovery_status.py`; [PR #1528](https://github.com/pl0n3r/Factory/pull/1528) MERGED `465bc1e711ea` | [#1526](https://github.com/pl0n3r/Factory/issues/1526) |
| `docs/recovery-status.md:L13-U2` | La comprobación es determinista y declarativa: no verifica por sí sola que se ejecutó un restore, que el proveedor remoto contiene datos auténticos ni que  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L13-U3` | Esos recibos siguen pendientes en Factory #305 y requieren autorización real de live (D-066/Factory #683). | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L15-U1` | El payload incluye razones explicables y solo estas clases canónicas de #269: `backup_missing`, `backup_stale`, `offsite_missing`, `checksum_failed`, `rest | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L17-U1` | Para recovery crítico, `UNKNOWN` o `BLOCKED` fuerza `ready=false`. `DEGRADED` permanece visible pero no se transforma artificialmente en otro estado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L21-U1` | Un fixture válido mantiene la evaluación `HEALTHY` solo declarativa | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/recovery-status.md:L21-U2` | no acredita backup real ni restore y conserva las prohibiciones D-066/Factory #683. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L5-U1` | El kill switch Factory #767 y las condiciones de protección no se sustituyen por este documento. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L9-U1` | Si la generación modifica otras copias, incluirlas también en los claims legítimos, nunca ampliarlos silenciosamente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L18-U1` | Verificar la prueba concreta del nuevo número y todas las fuentes | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L18-U2` | Fusionar el PR del candidato solo tras `Validar` y seguridad exact-HEAD sobre el SHA definitivo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L24-U1` | Comando equivalente, **solo OWNER**: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L31-U1` | Revalida para el HEAD exacto: **CI factory** `factory-ci.yml`, **Sonar CI-based** `sonar.yml`, **Evidencia CodeQL** `codeql-evidence.yml`, watchdog de reus | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L31-U2` | Ausencia o carrera de resultados termina con `revalidation_required`: completar los gates terminales `success` sobre el mismo SHA y volver a solicitar la v | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L33-U1` | La puerta `factory-release` caduca y su ventana puede congelar `main`: el check `Ventana de release Factory` puede bloquear PRs hasta que la puerta se deci | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L43-U1` | Un mensaje libre o `sigue` nunca constituye decisión. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L43-U2` | El número de Issue se obtiene del enlace real de la puerta, no se inventa. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L45-U1` | Si `main` se movió desde que se abrió la ventana, especialmente por cambios a la maquinaria de release, hay deriva y la puerta debe revalidarse o reabrirse | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L57-U1` | El workflow actual también admite `expected_sha=<SHA_de_40_hex>`, siempre que concuerde con `main`, `github.sha` y la aprobación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L57-U2` | El mensaje `require_exact_main_success: command not found` fue un fallo **histórico** de bootstrap corregido en #1436: nunca afirmarlo como limitación perm | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L59-U1` | Mientras el canal `refs/tags/v1` siga en el commit estable anterior, el check `channel-ready` falla cerrado o bloquea el self-test. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L61-U1` | La aprobación anterior no autoriza un commit diferente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L65-U1` | Solo el OWNER autorizado puede mover el tag mayor protegido `v1` al SHA exacto aprobado, conforme al ruleset y los permisos vigentes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L81-U1` | La validación terminal exige `channel-ready` y self-test `Validar` del `@v1` publicado sobre el SHA exacto, además de controles de compatibilidad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L96-U1` | Para cualquier acción futura, verificar versión actual en `config/version.json` y Releases, nunca reutilizar la decisión A previa. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L100-U1` | Workflow de ventana y evaluador. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L101-U1` | Bootstrap, reusable release y guía de release. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L102-U1` | CI factory, Sonar y CodeQL. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/release-runbook.md:L103-U1` | Puertas humanas, reglas de agentes y reparación #1436. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L3-U1` | **no demuestra por sí solo que una credencial, backup o restore real exista o haya funcionado**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L7-U1` | Factory valida capacidades y mecanismos, no una cantidad artificial de identidades: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L9-U1` | **CI:** `github-token:ephemeral`, emitido por GitHub Actions para cada corrida y limitado con `permissions` mínimos por job. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L10-U1` | **Observador:** `github-token:ephemeral` con alcance mínimo para el propio repositorio | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L10-U2` | los health checks del producto usan endpoints públicos cuando aplica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L11-U1` | **Deploy:** `hostinger:git` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L11-U2` | el despliegue no usa una credencial GitHub persistente de Factory. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L12-U1` | **Escritura cross-repo:** requiere una **GitHub App dedicada**, instalada solo en los repos necesarios y con permisos mínimos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L12-U2` | El `GITHUB_TOKEN` de un workflow no se eleva ni se sustituye por PAT personal para sortear esta frontera. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L14-U1` | No se admiten PATs personales, tokens de larga duración ni aliases libres dentro del manifiesto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L16-U1` | Los workflows continúan sujetos al auditor preventivo: acciones fijadas a SHA, `pull_request_target` prohibido, sin `write-all` y sin permisos globales de  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L20-U1` | El gate actual acepta únicamente `version: 2` con campos raíz exactos: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L24-U1` | `execution_mechanisms` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L25-U1` | `cross_repo_write` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L28-U1` | Los mecanismos permitidos son exactamente los descritos arriba y `cross_repo_write.required_mechanism` debe ser `github-app`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L30-U1` | Los checks `repo_backup`, `secrets_escrow`, `token_rotation` y `restore_drill` conservan `verified_at` UTC y `evidence_ref` no sensible. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L30-U2` | La evidencia debe tener como máximo 90 días y no puede estar fechada en el futuro. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L34-U1` | El formato v1 histórico con `identities` queda disponible únicamente mediante el validador legacy explícito para **diagnóstico y migración**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L34-U2` | No es una configuración operativa vigente y `validate_manifest()` / `--manifest-stdin` lo rechazan con instrucción de migrar a v2. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L36-U1` | Mantener el parser legacy evita perder capacidad de inspeccionar evidencia histórica, pero no permite que una configuración nueva pase el gate con la polít | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L40-U1` | **Contener:** revocar el mecanismo o integración afectada y suspender el job/deploy con ese alcance. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L41-U1` | **Delimitar:** identificar permisos efectivos, repos alcanzables y ventana de exposición sin copiar secretos a Issues o logs. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L42-U1` | **Rotar:** renovar credenciales donde existan y revocar las anteriores | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L42-U2` | los tokens efímeros expiran y no se almacenan como evidencia. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L43-U1` | **Recuperar:** verificar integridad y antigüedad de la copia externa, restaurar en un entorno aislado y comparar refs, tags y artefactos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L44-U1` | **Verificar:** ejecutar CI, smoke y prueba de rollback antes de retomar despliegues. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L45-U1` | **Aprender:** registrar causa, controles preventivos y resultado en `lecciones/` sin PII ni credenciales. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L62-U1` | La validación estructural no prueba hechos externos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/resiliencia-fabrica.md:L62-U2` | Si en el futuro aparece una escritura cross-repo, esa capacidad debe introducir una GitHub App dedicada y evidencia verificable antes de habilitarse. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L9-U1` | `project`: `owner/repo`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L10-U1` | `epic`: `owner/repo#N`, del mismo proyecto; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L11-U1` | `metric`: identificador del catálogo `producto/metricas.json`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L12-U1` | `surface`: slug de taxonomía de producto, por ejemplo `home` o `checkout`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L13-U1` | `phase`: `baseline` o `post-deploy`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L14-U1` | `period_start` / `period_end`: ISO-8601 con zona horaria; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L15-U1` | `value`: agregado numérico; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L16-U1` | `sample_size`: cantidad agregada usada para ponderar. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L18-U1` | No se permiten campos adicionales. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L18-U2` | En particular el contrato no tiene nombre, email, teléfono, IP, user/session ID, query string, URL libre, payload de error ni texto de usuario. `surface` e | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L20-U1` | Las métricas iniciales cubren las cinco familias obligatorias: `usage`, `error`, `conversion`, `cwv` y `seo`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L30-U1` | El reporte semanal **debe resolver el Issue real de cada épico observado**, parsear ese marker y rechazar telemetría cuya `metric` o `surface` no coincida. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L34-U1` | Las ventanas dentro de una fase no pueden solaparse y baseline debe terminar antes de post-deploy. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L34-U2` | Para Core Web Vitals p75 se exige **un único agregado por fase**: Factory no promedia percentiles ya calculados, porque eso no reconstruye el percentil de  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L34-U3` | Por defecto se requieren al menos 100 muestras por fase. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L34-U4` | Sin ambas fases, con muestra insuficiente o baseline igual a cero, no se calcula una regresión porcentual ni se propone un Issue. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L36-U1` | Una variación adversa de al menos 5% entra a `proposals`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L40-U1` | Sirve únicamente para ordenar evidencia comparable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L46-U1` | `artifacts/reporte-producto.json`: resultados y propuestas máquina; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L47-U1` | `artifacts/reporte-producto.md`: tablero humano y Job Summary. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L49-U1` | El workflow primero obtiene la lista validada de épicos presentes en la telemetría, consulta solo esos Issues vía API y construye un mapa efímero de bodies | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/retroalimentacion-producto.md:L49-U2` | Si un Issue falta, no tiene marker o declara otra métrica/surface, la corrida falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L3-U1` | `reusable_permission_compat.py` define un contrato **puro y fail-closed** para comparar el permission envelope máximo que requiere un workflow reusable con | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L7-U1` | niveles: `none < read < write`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L8-U1` | scopes omitidos por el caller equivalen a `none`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L9-U1` | scopes o niveles desconocidos invalidan el contrato; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L10-U1` | un reusable es compatible solo si, para cada scope requerido, el caller concede un nivel igual o mayor; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L11-U1` | un conjunto de consumidores es compatible solo si **todos** sus callers lo son. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L11-U2` | No existe mayoría, promedio ni excepción implícita. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L17-U1` | Su único trabajo es validar mapas ya extraídos por un adaptador confiable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L19-U1` | La integración posterior con la puerta de release debe obtener los envelopes de callers reales o fixtures con provenance y alimentar este contrato | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-permission-compat.md:L19-U2` | cualquier evidencia ausente o inválida debe conservar el bloqueo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L9-U1` | SHA exacto de Factory que está resolviendo `@v1`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L10-U1` | tag/release semántica asociada al incidente; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L11-U1` | repositorios y workflows consumidores afectados; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L12-U1` | run IDs cuyo resultado sea `startup_failure`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L13-U1` | SHA/tag estable previo conocido que sí materializaba jobs en consumidores. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L19-U1` | El objetivo debe ser un SHA/tag Factory previamente conocido como estable para los consumidores afectados. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L19-U2` | No se elige por inferencia ni por “último release verde” si no existe evidencia de consumidor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L23-U1` | `affected_factory_sha=<SHA afectado>`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L24-U1` | `stable_factory_sha=<SHA estable objetivo>`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L25-U1` | consumidores que justifican el rollback; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L26-U1` | evidencia que demuestra que el SHA estable había materializado jobs. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L30-U1` | Detectar o recomendar rollback **no autoriza** a un agente, workflow o sesión automática a mover `refs/tags/v1`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L32-U1` | El OWNER debe ejecutar conscientemente la actualización del tag mayor al SHA estable exacto mediante su canal administrativo autorizado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L34-U1` | La acción administrativa debe equivaler exactamente a mover: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L38-U1` | No se autoriza mover tags semánticos, publicar una release nueva, cambiar otra referencia ni usar un SHA distinto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L42-U1` | Después de restablecer `v1`, genera un evento nuevo en al menos un consumidor afectado y exige evidencia nueva de que: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L44-U1` | el workflow reutilizable vuelve a **materializar jobs**; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L45-U1` | el run deja de terminar en `startup_failure`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L46-U1` | el workflow usa el `Factory@v1` que resuelve al SHA estable objetivo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L48-U1` | Solo pueden reintentarse o regenerarse después de restablecer el canal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L50-U1` | Si no existe evidencia nueva de consumidor, el incidente permanece abierto/fail-closed. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L56-U1` | SHA afectado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L57-U1` | SHA estable restaurado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L58-U1` | repos/workflows afectados; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L59-U1` | run IDs antes y después; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L60-U1` | evidencia de al menos un consumidor recuperado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L61-U1` | decisión humana/administrativa que movió `v1`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L63-U1` | Después del rollback, la corrección de fondo debe viajar por un PR separado y una nueva puerta de release. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/reusable-release-rollback.md:L63-U2` | Nunca uses el rollback como bypass de compatibilidad reusable↔caller. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L12-U1` | señales operativas; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L13-U1` | contexto del proyecto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L16-U1` | No se usa una media que pueda esconder una dimensión | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L23-U1` | `signal`: qué se observó; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L24-U1` | `source`: de dónde vino; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L25-U1` | `risk`: nivel aportado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L26-U1` | `reason`: por qué afecta riesgo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L36-U1` | low: CI, revisión sin hallazgos y scope reclamado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L37-U1` | medium: todo low + tests del cambio + rollback plan; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L38-U1` | high: todo medium + full suite + security scan + smoke exact-SHA + | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L41-U1` | Por construcción, aumentar riesgo nunca elimina controles. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/risk-compiler.md:L52-U1` | La ausencia nunca reduce el estándar. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L3-U1` | no se mantiene una segunda copia manual de roles en `labels/*.json`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L9-U1` | `Rol(es): slug1, slug2` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L10-U1` | `Rol primario: slug1` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L11-U1` | todos los items de checklist de cada rol como `- [x] …` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L12-U1` | si el cambio toca esquema, seguridad, deploy/workflows o UX pública: `Revisión cruzada: <slug>`, distinto del rol primario y permitido para ese riesgo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L14-U1` | El motor deriva roles obligatorios de archivos tocados y tipo/contexto del Issue. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L14-U2` | el rol primario debe estar declarado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L18-U1` | Proyectos en español: `rol: <slug>`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L19-U1` | BRVTAL/inglés: `role: <name>`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L21-U1` | `mode=sync` crea/actualiza las etiquetas desde el catálogo canónico. `mode=suggest` asigna las etiquetas a la entidad del evento. `mode=validate` comprueba | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L25-U1` | El workflow siempre ejecuta el kit publicado `@v1` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L25-U2` | el caller no elige una ref. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L26-U1` | `validate` es read-only y solo acepta el PR actual. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L27-U1` | `sync` escribe únicamente desde `push\\|workflow_dispatch` de la rama principal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L28-U1` | `suggest` solo puede modificar la entidad del evento `issues\\|pull_request`, o una entidad explícita bajo `workflow_dispatch` en la rama principal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L29-U1` | El contexto entra al validador por stdin con tamaño acotado | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L29-U2` | el CLI no acepta rutas de catálogo, perfiles ni contexto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L30-U1` | La clasificación es determinista y explicable | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/roles-profesionales.md:L30-U2` | ningún texto remoto se ejecuta como código o shell. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L3-U1` | Hay una excepción cerrada para un caso que Sonar declara explícitamente como obsoleto: un reporte de un commit viejo no puede procesarse porque ya se proce | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L7-U1` | La excepción solo aplica si el mensaje completo coincide con la forma canónica observada por Sonar: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L9-U1` | identifica el commit del reporte rechazado con un SHA hexadecimal de 40 caracteres; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L10-U1` | afirma que un reporte más nuevo ya fue procesado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L11-U1` | afirma que procesar reportes antiguos no está soportado; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L12-U1` | identifica el último commit procesado con otro SHA hexadecimal de 40 caracteres; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L13-U1` | no contiene texto extra fuera de esa forma. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L15-U1` | Esto permite que `sonar-watch.py` cierre el Issue automático anterior únicamente cuando la señal está fresca y el resto de observables vigentes también se  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/sonar-superseded-ce.md:L21-U1` | Tampoco reintenta análisis, escribe en Sonar, modifica el repositorio observado ni cierra manualmente Issues sin una nueva evaluación fresca. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L9-U1` | La clasificación de puertas, asignación y recepción móvil real quedaron verificadas. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L9-U2` | Las decisiones humanas siguen siendo explícitas y nunca se infieren de un workflow verde. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L13-U1` | la escritura cross-repo requiere una **GitHub App dedicada**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L25-U1` | #1–#14: cerrados conforme al contrato vigente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L26-U1` | #54: privacidad como código cerrada tras revalidación de los tres productos y evidencia real del auditor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L27-U1` | #83: raíz de confianza del canal `v1` resuelta. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L28-U1` | `v1.0.0`: GitHub Release publicada y self-test consumidor en verde. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L29-U1` | TANDA 1 global: completada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L33-U1` | El cierre de TANDA 1 anterior permanece histórico y no se reescribe. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/tanda1-handoff.md:L35-U1` | Un cambio en `main` no modifica por sí solo el canal publicado `@v1`: debe pasar el proceso de mantenimiento descrito en **release-bootstrap.md**. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-daily-summary.md:B01` | El motor de resumen estructura decisiones, bloqueos, avances, alertas, acciones y cuotas sin inventar datos. | CUBIERTO | Código `scripts/unattended_daily_summary.py`; prueba `tests/test_unattended_daily_summary.py`; PR MERGED [#789](https://github.com/pl0n3r/Factory/pull/789) `6c69a6cfd594ce5ba7617e2b0c22257045b2e477` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-daily-summary.md:B02` | La publicación diaria manual autorizada usa marker idempotente y relee kill switch. | CUBIERTO | Código `scripts/unattended_daily_summary.py`; prueba `tests/test_unattended_daily_summary.py`; PR MERGED [#789](https://github.com/pl0n3r/Factory/pull/789) `6c69a6cfd594ce5ba7617e2b0c22257045b2e477` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-daily-summary.md:B03` | La tarjeta pública Condor D-043 verifica versión y SHA sin credenciales de Factory. | CUBIERTO | Código `scripts/unattended_daily_summary.py`; prueba `tests/test_unattended_daily_summary.py`; PR MERGED [#789](https://github.com/pl0n3r/Factory/pull/789) `6c69a6cfd594ce5ba7617e2b0c22257045b2e477` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-daily-summary.md:B04` | La entrega automática a las 08:00 Bogotá depende de un cron y job vigentes. | NO_VERIFICABLE | Evidencia insuficiente: F1G retiró daily-summary y cron 0 13: el motor offline no equivale a entrega programada. · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-handoff-consumer-pack.md:L5-U1` | Este pack permite que ControlBot y FactoryRunner **interpreten** el handoff v1 ya | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L9-U1` | `config/unattended-handoff-v1.schema.json`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L10-U1` | `tests/fixtures/unattended_handoff_v1/allow.json`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L11-U1` | `tests/fixtures/unattended_handoff_v1/pause.json`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L12-U1` | `tests/fixtures/unattended_handoff_v1/blocked.json`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L13-U1` | `tests/fixtures/unattended_handoff_v1/unknown.json`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L19-U1` | Solo proyecta el estado que ya viene | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L29-U1` | `UNKNOWN` **no** amplía el enum de `action` y nunca se convierte en `ALLOW`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L30-U1` | no se deriva una transición nueva. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L33-U1` | No deben usar esos | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L43-U1` | Ambos consumidores deben validar primero el documento contra el schema v1. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L49-U1` | El handoff conserva siempre: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L51-U1` | `authority=unchanged`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L52-U1` | `permissions.reserve=false`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L53-U1` | `permissions.merge=false`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L54-U1` | `permissions.deploy=false`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L55-U1` | `permissions.spend=false`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L56-U1` | `permissions.live=false`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L58-U1` | Por tanto, incluso un documento `ALLOW` **no autoriza** reserva, merge, deploy, | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L63-U1` | Leer un documento local. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L64-U1` | Validarlo contra `config/unattended-handoff-v1.schema.json`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L65-U1` | Mostrar/proyectar `ALLOW\\|PAUSE\\|BLOCKED\\|UNKNOWN` usando únicamente | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L67-U1` | Conservar provenance/reasons/incidents/interrupt state sin reinterpretarlos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-handoff-consumer-pack.md:L68-U1` | Mantener todos los permisos operativos denegados. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L11-U1` | El Issue debe contener exactamente un marker: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L15-U1` | El Issue canónico **#767 debe estar cerrado** (`state: "closed"`) antes de admitir `RUNNING`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L19-U1` | `RUNNING`: no añade pausa | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L19-U2` | el resto de guardas 4B sigue aplicando. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L20-U1` | `PAUSED`: `global_pause=true` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L20-U2` | no se inicia trabajo ni se muta GitHub. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L21-U1` | `UNKNOWN`: estado derivado localmente ante lectura fallida, fuente inesperada o marker inválido. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L21-U2` | Siempre pausa fail-closed. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L25-U1` | Solo el dueño puede ordenar el cambio operativo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L27-U1` | Después del cambio, cualquier ciclo nuevo debe leer la URL exacta antes de comentar, reservar, crear branch/PR o escribir código. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L31-U1` | Solo el dueño puede ordenar la reanudación. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L33-U1` | `RUNNING` solo quita esta pausa global | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L37-U1` | Si la URL no puede leerse, apunta a otro Issue/repositorio/autor, el marker falta o aparece más de una vez, o el JSON/version/owner/state no es válido: | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L39-U1` | deriva `UNKNOWN`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L40-U1` | trata `global_pause=true`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L41-U1` | realiza cero mutaciones; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L42-U1` | informa una única línea al dueño con la razón auditable. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L46-U1` | nunca se toma el primer `RUNNING` como permiso. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L48-U1` | La regla “solo el dueño cambia el marker” sigue siendo una frontera de gobernanza y no debe presentarse como provenance técnica del último editor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-kill-switch.md:L52-U1` | Por eso cada ciclo debe comprobarlo **antes de la primera mutación** y volver a comprobarlo al iniciar el siguiente ciclo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-runtime-guards.md:B01` | 4B respeta fencing fail_closed y replan y no inventa autoridad para pausar. | CUBIERTO | Código `scripts/unattended_guards.py`; prueba `tests/test_unattended_guards.py`; PR MERGED [#747](https://github.com/pl0n3r/Factory/pull/747) `073b46e8e0a0bd81b081f0b6a678e2681a088d68` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-runtime-guards.md:B02` | Breakers derivan su apertura de threshold, scope, subject y evidencia fresh explícitos. | CUBIERTO | Código `scripts/unattended_guards.py`; prueba `tests/test_unattended_guards.py`; PR MERGED [#747](https://github.com/pl0n3r/Factory/pull/747) `073b46e8e0a0bd81b081f0b6a678e2681a088d68` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-runtime-guards.md:B03` | Techos de uso, coste y paralelismo requieren presupuestos declarados y medidas válidas. | CUBIERTO | Código `scripts/unattended_guards.py`; prueba `tests/test_unattended_guards.py`; PR MERGED [#747](https://github.com/pl0n3r/Factory/pull/747) `073b46e8e0a0bd81b081f0b6a678e2681a088d68` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-runtime-guards.md:B04` | Segunda pasada de riesgo alto y backup verificado nunca amplían autoridad sensible. | CUBIERTO | Código `scripts/unattended_guards.py`; prueba `tests/test_unattended_guards.py`; PR MERGED [#747](https://github.com/pl0n3r/Factory/pull/747) `073b46e8e0a0bd81b081f0b6a678e2681a088d68` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-safe-mode-drill.md:L5-U1` | Este tramo valida la composición de los contratos ya integrados de 4B | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L16-U1` | No se utilizan credenciales, secretos, datos reales, proveedores, producción | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L23-U1` | 4B produce `ALLOW`, `pause_allowed=false`, `authority=unchanged`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L24-U1` | 4C conserva `ALLOW`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L25-U1` | no aparecen incidencias ni interrupción al dueño. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L30-U1` | Con fencing que ya permite pausa, 4B produce `PAUSE` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L31-U1` | Si la pausa no está autorizada por fencing, 4B falla cerrado en | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L34-U1` | Ningún escenario crea trabajo autónomo nuevo ni amplía autoridad. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L40-U1` | Presence `unknown`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L41-U1` | STATE stale; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L42-U1` | trabajo ready sin siguiente despacho; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L43-U1` | reserva activa stale. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L46-U1` | falla cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L52-U1` | inyecta como incidencia S1 sintética y se observa únicamente a través de 4B/4C. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L62-U1` | backup requerido no verificado → 4B `BLOCKED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L63-U1` | irreversible/destructivo → 4B `BLOCKED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L64-U1` | riesgo/autoridad UNKNOWN → 4B `BLOCKED`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L65-U1` | 4C conserva `BLOCKED` y solo refleja una next action sintética de | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L74-U1` | UNKNOWN conserva fail-closed. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L80-U1` | verificado permanecen `BLOCKED`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L80-U2` | El simulacro no puede convertir estas puertas | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L85-U1` | 4D se considera técnicamente aprobado únicamente cuando los siete criterios de | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L92-U1` | publicación de Factory@v1; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L93-U1` | gasto o aprovisionamiento; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L94-U1` | uso de credenciales o datos reales; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L95-U1` | deploy, backup o rollback real. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L97-U1` | Cualquier fallo del simulacro debe corregirse en 4B o 4C si corresponde | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode-drill.md:L98-U1` | no puede debilitar esos contratos para pasar. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-safe-mode.md:B01` | Autoridad sensible, riesgo alto, backup y segunda pasada nunca habilitan gasto, live ni datos reales sin permiso. | CUBIERTO | Código `scripts/unattended_guards.py`; prueba `tests/test_unattended_guards.py`; PR MERGED [#747](https://github.com/pl0n3r/Factory/pull/747) `073b46e8e0a0bd81b081f0b6a678e2681a088d68` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-safe-mode.md:B02` | Handoff STATE usa identidad, freshness y severidad; UNKNOWN y stale no son progreso sano. | CUBIERTO | Código `scripts/unattended_watchdog.py`; prueba `tests/test_unattended_watchdog.py`; PR MERGED [#754](https://github.com/pl0n3r/Factory/pull/754) `e1509bfe9d133d0dda58ecb3f898201d5ccdc53e` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-safe-mode.md:B03` | SLO de cada producto requiere objetivos configurados y evidencia de medición vigente. | NO_VERIFICABLE | Evidencia insuficiente: Sin mediciones autenticadas de consumidores ni objetivos aprobados, no se acredita su SLO real. · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-safe-mode.md:B04` | Rollback operativo y simulacro integrado necesitan autoridad previa y evidencia E2E de reversibilidad. | NO_VERIFICABLE | Evidencia insuficiente: No hay demostración operativa exact-SHA de rollback productivo ni backup restaurable para los consumidores. · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-state-source.md:L11-U1` | El objeto `state` usa exactamente el contrato de `scripts/unattended_watchdog.validate_state()`: identidad, repo, branch/SHA/reserva, riesgo, severidad, ev | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L13-U1` | Con una reserva activa, esta fuente exige binding de `work_identity`, `repository`, `reservation_id` y `branch` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L13-U2` | si el caller aporta el SHA real de la rama, un SHA distinto bloquea. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L13-U3` | El `updated_at` del STATE no puede ser posterior al timestamp GitHub del comentario que lo contiene. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L17-U1` | La lease autoritativa es el **último** marker `condor-reserva` publicado por `github-actions[bot]`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L18-U1` | Se aceptan exactamente tres formas cerradas del protocolo real: **v3 activa completa** y **v3 inactiva completa** con hashes SHA-256 y listas de paths/depe | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L18-U2` | V1 activa, extras, hashes/paths/dependencias inválidos, versiones desconocidas o shapes parciales fallan cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L19-U1` | El STATE aceptado debe ser publicado por el `owner` de esa lease. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L20-U1` | Campos desconocidos, secretos, PII, UUID/SHA/repo incoherentes o timestamps futuros fallan cerrado. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L21-U1` | STATE no sustituye GitHub, HEALTH, checks, smoke, decisiones humanas ni el kill switch. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L29-U1` | `sessions=[]`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L30-U1` | capacidad `known_slots=0`, `eligible_free_slots=0`, `degraded_slots=0`; | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L31-U1` | `capacity.freshness=unknown`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L33-U1` | 4C clasificará esa Presence como UNKNOWN/fail-closed. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L41-U1` | La freshness se expresa en `reasons` (`state_stale`) y el consumidor la deriva otra vez con `validate_state()`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L45-U1` | #769 lee GitHub, entrega snapshots a este parser y luego llama 4B/4C. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L46-U1` | #768 consume STATE/resumen una vez exista su runtime. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-state-source.md:L47-U1` | Ningún consumidor puede reinterpretar UNKNOWN como ALLOW ni ampliar `authority=unchanged`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `docs/unattended-watchdog-runtime.md:B01` | Runtime usa configuración fija y stdin acotado, sin rutas CLI ni cambios de política 4C. | CUBIERTO | Código `scripts/unattended_watchdog_runtime.py`; prueba `tests/test_unattended_watchdog_runtime.py`; PR MERGED [#786](https://github.com/pl0n3r/Factory/pull/786) `2964992a8833e10627e353132c24358ecce99de9` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-watchdog-runtime.md:B02` | Alertas propias exigen provenance/marker/fingerprint; stale no permite resolver ni escribir con #767 pausado. | CUBIERTO | Código `scripts/unattended_watchdog_runtime.py`; prueba `tests/test_unattended_watchdog_runtime.py`; PR MERGED [#786](https://github.com/pl0n3r/Factory/pull/786) `2964992a8833e10627e353132c24358ecce99de9` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-watchdog-runtime.md:B03` | La continuidad operativa real de la cadencia de quince minutos requiere runs y HEALTH observados. | NO_VERIFICABLE | Evidencia insuficiente: El workflow describe cadencia, pero este contraste no acredita runs continuos, disponibilidad ni HEARTBEAT real. · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-watchdog-runtime.md:B04` | Reactivar resumen diario suspendido por F1G exige autorización humana separada. | NO_VERIFICABLE | Evidencia insuficiente: No reponer automáticamente el cron; watchdog periódico no reemplaza la entrega diaria retirada. · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-watchdog.md:B01` | 4C exige umbrales explícitos para ready sin despacho, reservas sin progreso y STATE stale. | CUBIERTO | Código `scripts/unattended_watchdog.py`; prueba `tests/test_unattended_watchdog.py`; PR MERGED [#754](https://github.com/pl0n3r/Factory/pull/754) `e1509bfe9d133d0dda58ecb3f898201d5ccdc53e` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-watchdog.md:B02` | Identidad de reserva, STATE y Presence deben corresponder con freshness y timestamps válidos. | CUBIERTO | Código `scripts/unattended_watchdog.py`; prueba `tests/test_unattended_watchdog.py`; PR MERGED [#754](https://github.com/pl0n3r/Factory/pull/754) `e1509bfe9d133d0dda58ecb3f898201d5ccdc53e` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-watchdog.md:B03` | 4C consume GuardDecision sin elevar BLOCKED, PAUSE o ALLOW ni crear nueva pausa. | CUBIERTO | Código `scripts/unattended_watchdog.py`; prueba `tests/test_unattended_watchdog.py`; PR MERGED [#754](https://github.com/pl0n3r/Factory/pull/754) `e1509bfe9d133d0dda58ecb3f898201d5ccdc53e` · [contraste](contraste-matriz-unattended.md) | — |
| `docs/unattended-watchdog.md:B04` | Las incidencias poseen fingerprints idempotentes y solo S1/S2 nuevas interrumpen al dueño. | CUBIERTO | Código `scripts/unattended_watchdog.py`; prueba `tests/test_unattended_watchdog.py`; PR MERGED [#754](https://github.com/pl0n3r/Factory/pull/754) `e1509bfe9d133d0dda58ecb3f898201d5ccdc53e` · [contraste](contraste-matriz-unattended.md) | — |
| `AGENTES.md:L13-U1` | Comenta `/tomar` en el Issue y espera la reserva del bot (UUID). | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L14-U1` | Trabaja solo en la rama `trabajo/issue-N`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L15-U1` | Abre el PR con la plantilla, `Closes #N` y la reserva declarada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L16-U1` | El check agregado **`Validar`** debe pasar | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L16-U2` | `main` está protegido y solo acepta PRs. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L17-U1` | Libera con `/liberar <UUID>` si abandonas el trabajo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L33-U1` | **Reusable workflows** configurables por `inputs` (stack `symfony\|laravel\|php\|node`, dominio, fuente de versión, idioma de etiquetas, fase `construccion | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L33-U2` | nada específico de un proyecto dentro del kit. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L34-U1` | Acciones de terceros **fijadas a SHA** | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L34-U2` | `permissions` mínimos por job | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L34-U3` | `timeout-minutes` explícito | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L34-U4` | `concurrency` y filtros `if:` a nivel de job para no cargar GitHub. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L35-U1` | Scripts en Python 3 de biblioteca estándar, con tests `unittest` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L35-U2` | nada de secretos en logs. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L36-U1` | **Versionado:** tags `vN.M.P` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L36-U2` | los proyectos consumen `@vN`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L36-U3` | Un cambio incompatible sube la versión mayor. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L37-U1` | Todo cambio se prueba primero aquí antes de publicarse a los proyectos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L47-U1` | Cada tarea planificada tiene owner, roles derivados, orden, dependencias y paths reclamados. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L48-U1` | /tomar falla si hay dependencias abiertas o claims solapados con otra tarea activa. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L49-U1` | Si dos tareas necesitan tocar la misma ruta, el DAG debe serializarlas mediante depends_on. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L50-U1` | No edites owner/paths/dependencias de una tarea ya reservada o en revisión | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L50-U2` | replantea el épico antes de iniciar trabajo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L56-U1` | Antes de `/tomar`, el Issue debe contener Contexto, Alcance, Fuera de alcance, criterios humanos `AC-NN` y un marker `factory-acceptance` consistente. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L58-U1` | Cada `AC-NN` apunta a un test `unittest` exacto o a un check GitHub exacto. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L59-U1` | No se permiten comandos shell provenientes del Issue. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L60-U1` | `Criterios de aceptación` debe pasar en el PR | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L60-U2` | `Validar` depende de ese job. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L61-U1` | Gates genéricos verdes son necesarios, pero no suficientes para declarar el trabajo hecho. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L62-U1` | Si cambia el comportamiento esperado, actualiza primero el Issue y su evidencia ejecutable antes de modificar código. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L70-U1` | Declara en el PR los roles asumidos y completa el checklist de cada perfil. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L71-U1` | Si el clasificador exige un rol adicional por los archivos modificados, inclúyelo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L72-U1` | Cambios de esquema, seguridad, deploy o UX pública requieren **revisión cruzada** por un rol distinto al implementador. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L73-U1` | Los perfiles de rol complementan este contrato | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L73-U2` | no sustituyen `PLAN-AGENTES.md`, `decisiones.yml` ni las lecciones vigentes. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L79-U1` | Prioriza GitHub/API y usa Remote Desktop Commander solo para trabajo que realmente requiera el Mac del dueño. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L80-U1` | Agrupa varios pasos locales en una sola llamada o script | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L80-U2` | cuando leas archivos, combina lecturas relacionadas en vez de una llamada por archivo. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L81-U1` | No sondees procesos ni releas archivos/directorios sin cambios. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L81-U2` | Ejecuta con espera acotada y lee el resultado una sola vez. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L82-U1` | Limita la salida con filtros como `grep`, `head` o `--jq` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L82-U2` | evita volcados completos cuando basta evidencia acotada. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L83-U1` | Si una tarea previsiblemente requiere más de ~20 llamadas remotas, avisa antes y propone una ejecución más corta. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L84-U1` | No hagas revisiones periódicas ni revalidaciones globales no solicitadas mediante este canal. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L85-U1` | No está autorizado comprar plan Pro, recargar saldo ni asumir gasto para ampliar límites de Remote Desktop Commander. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L88-U1` | Los reusables que hacen checkout o ejecutan código del repositorio consumidor deben fallar cerrado antes del checkout cuando el caller proviene de un event | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L88-U2` | Además, esos reusables declaran `cache-mode: read`: pueden restaurar cachés, pero el código del consumidor no puede guardar ni sobrescribir caché de GitHub | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L88-U3` | El CI base admite `pull_request`, `push` y `merge_group` para su contrato/preflight, pero los jobs que ejecutan PHP/Node del consumidor solo corren en `pul | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L88-U4` | Preview y aceptación solo admiten `pull_request`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L88-U5` | No se permite ejecutar código del consumidor desde `pull_request_target`, `workflow_run`, `issue_comment`, `check_run`, `issues`, `schedule` ni `repository | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `AGENTES.md:L88-U6` | Los workflows operativos que necesiten otros eventos deben validar explícitamente evento y rama principal antes del primer checkout. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `9c12107b` | — |
| `ISSUE-304:AC-01` | Los proyectos pueden declarar Performance Contracts específicos. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-02` | Factory detecta regresiones comparando contra baseline verificable. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-03` | Team Compiler asigna roles adecuados según el cuello. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-04` | Ninguna optimización se adopta sin before/after. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-05` | Cache/Redis/CDN/etc. se aplican solo con hipótesis y evidencia. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-06` | Stale/UNKNOWN nunca se presenta como rendimiento sano. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-07` | Un hallazgo material crea WorkItem en Factory #269. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-08` | Fixes seguros/reversibles pueden autocorregirse dentro de authority. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-09` | Cambios de costo/arquitectura/consistencia escalan correctamente. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-10` | Readiness #293 consume el estado sin recalcular con otro algoritmo. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-11` | Existe al menos un E2E: regresión → diagnóstico profesional → fix → before/after → producción/baseline. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-304:AC-12` | No existe un scheduler/backlog de performance paralelo a Factory. | NO_VERIFICABLE | Épico #304 no es hoja ejecutable ni evidencia operativa | [Fuente #304](https://github.com/pl0n3r/Factory/issues/304) |
| `ISSUE-305:AC-01` | Recovery Manifest v1 tiene schema cerrado y validación determinista. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-02` | El contrato expresa 3-2-1-1-0, RPO/RTO, retención y NOT_APPLICABLE explícito sin umbrales inventados. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-03` | Campos desconocidos, valores sensibles, destinos incoherentes y evidencia incompleta fallan cerrado sin eco de secretos. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-04` | Adapters object-storage y Google Drive cold-copy son idempotentes, checksum-aware y usan únicamente referencias opacas; iCloud no es dependencia. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-05` | El pipeline mínimo modela snapshot/dump → checksum → encrypt → upload → verify → cold-copy → evidence sin ejecutar I/O externo. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-06` | Un backup requerido no puede declararse verificable sin cifrado, checksum, offsite/inmutabilidad y evidence según su manifest. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-07` | Restore drill valida manifest/checksum/decrypt/restore/health/smoke/integrity y mide RTO en target descartable. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-08` | Restore/failover nunca amplía authority: cutover productivo o acción destructiva permanece fail-closed. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-09` | Recovery Health deriva HEALTHY\\|DEGRADED\\|UNKNOWN\\|BLOCKED con razones/freshness explícitas. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-10` | Drift/fallo se clasifica en las clases canónicas de WorkItem de #269 sin crear scheduler/backlog paralelo. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-11` | Readiness consume el mismo Recovery Health; UNKNOWN/BLOCKED crítico no puede presentarse como ready. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-305:AC-12` | E2E produce backup verificable, materializa offsite, restaura sin fuente original, valida health/smoke/integrity y reporta RPO/RTO sin secretos. | NO_VERIFICABLE | Épico #305 no es hoja ejecutable ni evidencia operativa | [Fuente #305](https://github.com/pl0n3r/Factory/issues/305) |
| `ISSUE-1080:AC-01` | Check `En construccion, main con versión nueva y gates verdes publica release y mueve v1 sin intervención humana` | NO_VERIFICABLE | Épico #1080 no es hoja ejecutable ni evidencia operativa | [Fuente #1080](https://github.com/pl0n3r/Factory/issues/1080) |
| `ISSUE-1080:AC-02` | Check `En fase live o con cambios en maquinaria de release exige la puerta humana existente` | NO_VERIFICABLE | Épico #1080 no es hoja ejecutable ni evidencia operativa | [Fuente #1080](https://github.com/pl0n3r/Factory/issues/1080) |
| `ISSUE-1080:AC-03` | Check `Kill switch unattended detiene el release automático` | NO_VERIFICABLE | Épico #1080 no es hoja ejecutable ni evidencia operativa | [Fuente #1080](https://github.com/pl0n3r/Factory/issues/1080) |
| `ISSUE-1080:AC-04` | Check `Rollback de v1 al SHA anterior documentado y probado en dry-run` | NO_VERIFICABLE | Épico #1080 no es hoja ejecutable ni evidencia operativa | [Fuente #1080](https://github.com/pl0n3r/Factory/issues/1080) |
| `ISSUE-1082:AC-01` | Check `docs/principios-construccion.md y lecciones/ recogen las 8 reglas con su evidencia` | NO_VERIFICABLE | Épico #1082 no es hoja ejecutable ni evidencia operativa | [Fuente #1082](https://github.com/pl0n3r/Factory/issues/1082) |
| `ISSUE-1082:AC-02` | Check `template/AGENTES.md se propaga a los 6 consumidores por el sync existente` | NO_VERIFICABLE | Épico #1082 no es hoja ejecutable ni evidencia operativa | [Fuente #1082](https://github.com/pl0n3r/Factory/issues/1082) |
| `ISSUE-1082:AC-03` | Check `salud-cola crea el incidente de cola vacía con causas por bloqueo y respeta rate_limit` | NO_VERIFICABLE | Épico #1082 no es hoja ejecutable ni evidencia operativa | [Fuente #1082](https://github.com/pl0n3r/Factory/issues/1082) |
| `ISSUE-1082:AC-04` | Check `El normalizador rechaza claims de directorio completo y sugiere partición` | NO_VERIFICABLE | Épico #1082 no es hoja ejecutable ni evidencia operativa | [Fuente #1082](https://github.com/pl0n3r/Factory/issues/1082) |
| `ISSUE-1382:AC-01` | El censo de actividad reciente es autenticado, acotado y no ejecuta mutaciones. Test: `tests/test_lease_auto_release_run.py::LeaseAutoReleaseRunTests::test | NO_VERIFICABLE | Épico #1382 no es hoja ejecutable ni evidencia operativa | [Fuente #1382](https://github.com/pl0n3r/Factory/issues/1382) |
| `ISSUE-1382:AC-02` | La orquestación respeta el kill switch, la cuota API y la exclusión del lock compartido. Test: `tests/test_lease_auto_release_workflow.py::LeaseAutoRelease | NO_VERIFICABLE | Épico #1382 no es hoja ejecutable ni evidencia operativa | [Fuente #1382](https://github.com/pl0n3r/Factory/issues/1382) |
| `ISSUE-1382:AC-03` | La integración falla cerrado cuando falta evidencia completa y autenticada. Test: `tests/test_lease_auto_release_integration.py::LeaseAutoReleaseIntegratio | NO_VERIFICABLE | Épico #1382 no es hoja ejecutable ni evidencia operativa | [Fuente #1382](https://github.com/pl0n3r/Factory/issues/1382) |
| `ISSUE-1382:AC-04` | La Fase A informa decisiones y motivos de los Issues **del repositorio que ejecuta el workflow**, con fuente y antigüedad de actividad y cero mutaciones; n | NO_VERIFICABLE | Épico #1382 no es hoja ejecutable ni evidencia operativa | [Fuente #1382](https://github.com/pl0n3r/Factory/issues/1382) |
| `ISSUE-1382:AC-05` | Cuota baja devuelve `deferred_low_quota` con workflow verde; la Fase B exige ≥24 h y ≥100 ciclos terminales y válidos **por repositorio**, cero falsos posi | NO_VERIFICABLE | Épico #1382 no es hoja ejecutable ni evidencia operativa | [Fuente #1382](https://github.com/pl0n3r/Factory/issues/1382) |
| `ISSUE-1382:AC-06` | La activación autorizada se limita a 3 liberaciones por ciclo, conserva ramas y PRs, registra evidencia auditada y permite revertir el feature flag. Test:  | NO_VERIFICABLE | Épico #1382 no es hoja ejecutable ni evidencia operativa | [Fuente #1382](https://github.com/pl0n3r/Factory/issues/1382) |
| `ISSUE-1382:AC-07` | El README de coordinación indica el estado verificable de Fase A/Fase B sin confundir observación con autoridad de release. Test: `tests/test_lease_auto_re | NO_VERIFICABLE | Épico #1382 no es hoja ejecutable ni evidencia operativa | [Fuente #1382](https://github.com/pl0n3r/Factory/issues/1382) |

| `docs/lista-salida-produccion.md:L7-U1` | Una fila por requisito verificable, no por encabezado. `LISTO` se reserva a **implementación documental o de código + prueba citada** presente en el árbol  | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L7-U2` | nunca basta épico/roadmap. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L8-U1` | `SIN_COBERTURA` identifica ausencia de implementación completa y contiene **hoja canónica creada** y su Issue. `DEL_DUEÑO` expresa autoridad externa, cuent | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L9-U1` | Fuentes: `decisiones.yml` (D-054–D-070), `docs/resiliencia-fabrica.md`, `docs/release-runbook.md`, `docs/release-bootstrap.md`, `docs/reusable-release-roll | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L9-U2` | El observador real de cada consumidor sigue siendo la autoridad para su despliegue. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L79-U1` | No se crearon hojas de soporte o backup ficticias: las puertas reales ya corresponden a #305/#304/#1082 y al OWNER. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L83-U1` | **3-2-1-1-0 auténtico / RPO/RTO:** falta offsite/cuenta aprobada por D-066 y restore real comprobable (#305) | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L83-U2` | el contrato offline no los acredita. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L84-U1` | **Autoridad de publicación:** OWNER debe abrir ventana protegida, aprobar SHA/versión y mover conscientemente Factory@v1 conforme a `docs/release-runbook.m | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L84-U2` | un PR verde no publica. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L85-U1` | **Operación real:** falta acreditar recepción efectiva de alertas, guardia/SLA, cargas de agentes, smoke pospublicación y restauración con evidencia extern | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L86-U1` | **Gobierno y legal:** cada consumidor debe acreditar HTTPS, accesibilidad, privacidad, manejo de datos, backups y autorización go-live según sus contratos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L87-U1` | **Continuidad técnica:** hoja #1553 cubre el procedimiento fail-closed ante GitHub o ChatGPT no disponibles | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L87-U2` | hasta integrarse, las filas de ese alcance permanecen `SIN_COBERTURA`. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L88-U1` | **Costo / accesos:** no provisionar B2, contratar proveedores ni rotar credenciales reales sin autorización del OWNER y recibos. | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |
| `docs/lista-salida-produccion.md:L90-U1` | La lista no constituye una declaración de `VALIDATED_IN_PRODUCTION` | NO_VERIFICABLE | No se confirmó test + PR fusionado pertinentes en `8088e66c` | — |

| `docs/auditoria-pre-v1.md:B01` | La auditoría de v1.0.0 se limita al SHA histórico auditado y no certifica el estado actual de Factory. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/auditoria-pre-v1.md:B02` | Los hallazgos altos del caller de bootstrap y trust-root de v1 exigen verificación de mitigación y puerta humana antes de publicar. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/auditoria-pre-v1.md:B03` | Las dependencias externas ejecutadas en CI deben acreditar integridad criptográfica y no solo fijación por versión. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/auditoria-pre-v1.md:B04` | Los eventos de coordinación y el costo de Actions deben medirse antes de recortar disparadores de seguridad. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/release-bootstrap.md:B01` | El release protegido debe ejecutar kit desde el trust root v1 y no aceptar ref dinámica privilegiada. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/release-bootstrap.md:B02` | La publicación requiere ventana factory-release y decisión OWNER A v2 ligada a fingerprint, versión y SHA, sin heredar aprobaciones stale. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/release-bootstrap.md:B03` | La primera pasada publica release semántica sin mover v1 y la segunda exige coincidencia del canal movido por el OWNER. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/release-bootstrap.md:B04` | Un cambio de maquinaria de release frente al baseline invalida una puerta previa incluso al usar expected_sha=latest. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/release-bootstrap.md:B05` | Freeze, TTL, reglas de excepción y provenance de puertas bot impiden publicar si faltan pruebas de identidad y compatibilidad. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-progress-readiness.md:B01` | El motor calcula scores ponderados con aritmética determinista por target, normaliza evidencia y produce payload canónico. | CUBIERTO | `readme/progress_readiness.py`, `tests/test_readme_progress.py`, [PR #298](https://github.com/pl0n3r/Factory/pull/298) · `73e63d68af7ced46ee1444a4cf4c7fe9b32d131a` | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-progress-readiness.md:B02` | Un blocker crítico no resuelto fuerza readiness BLOCKED aunque el score alcance 100%. | CUBIERTO | `readme/progress_readiness.py`, `tests/test_readme_progress.py`, [PR #298](https://github.com/pl0n3r/Factory/pull/298) · `73e63d68af7ced46ee1444a4cf4c7fe9b32d131a` | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-progress-readiness.md:B03` | El E2E reutiliza el mismo snapshot para generador README y consumer contract de ControlBot sin recalcular porcentajes. | CUBIERTO | `readme/progress_readiness.py`, `tests/test_readme_progress_e2e.py`, [PR #301](https://github.com/pl0n3r/Factory/pull/301) · `3e47a229c2a1c0495b871177b3884b02a818441c` | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-progress-readiness.md:B04` | Los targets de siete proyectos requieren evidencia fresca real; UNKNOWN/STALE no equivalen a GREEN. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-contract.md:B01` | El README v2 usa enlaces y señales vivas, omitiendo tablas de estado UNKNOWN y progreso calculado dentro de la portada. | CUBIERTO | `readme/validate_readme.py`, `tests/test_readme_contract_v2.py`, [PR #1025](https://github.com/pl0n3r/Factory/pull/1025) · `2dc5a8d0b2a6670ff5b87c96844c05ffcb0ebf53` | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-contract.md:B02` | La migración acepta marcadores v1 legacy hasta que el consumidor actualice a v2 sin romper compatibilidad. | CUBIERTO | `readme/validate_readme.py`, `tests/test_readme_contract_v2.py`, [PR #1025](https://github.com/pl0n3r/Factory/pull/1025) · `2dc5a8d0b2a6670ff5b87c96844c05ffcb0ebf53` | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-contract.md:B03` | La insignia de health solo aparece si el producto expone una fuente pública real y segura. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |
| `docs/readme-contract.md:B04` | Ningún proceso de refresco automático debe mover main solo para actualizar métricas del README. | NO_VERIFICABLE | Contrastado por comportamiento; falta verificación exact-SHA del alcance mencionado | [#1562](https://github.com/pl0n3r/Factory/issues/1562) |

| `docs/factory-living-software.md:B01` | Constitution v1 separa autoridad estable del estado evolutivo. | CUBIERTO | `evolution/constitution.py`, `tests/test_living_constitution.py`, [PR #199](https://github.com/pl0n3r/Factory/pull/199) · `445f41ca3858ba1726d6013d996763a68f5c05a4` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-living-software.md:B02` | El candidato no puede debilitar las cinco invariantes protegidas. | CUBIERTO | `evolution/constitution.py`, `tests/test_living_constitution.py`, [PR #199](https://github.com/pl0n3r/Factory/pull/199) · `445f41ca3858ba1726d6013d996763a68f5c05a4` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-living-software.md:B03` | Los cambios permitidos exigen namespaces evolution_state, evidencia y rollback reversible. | CUBIERTO | `evolution/constitution.py`, `tests/test_living_constitution.py`, [PR #199](https://github.com/pl0n3r/Factory/pull/199) · `445f41ca3858ba1726d6013d996763a68f5c05a4` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-living-software.md:B04` | La validación genera huella determinista y rechaza candidatos JSON inválidos. | CUBIERTO | `evolution/constitution.py`, `tests/test_living_constitution.py`, [PR #199](https://github.com/pl0n3r/Factory/pull/199) · `445f41ca3858ba1726d6013d996763a68f5c05a4` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-living-software.md:B05` | El DAG Living ejecuta el lifecycle completo desde observe hasta rollback. | NO_VERIFICABLE | Contrastado: No se acreditó ejecución integral de once fases con los motores integrados. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-living-software.md:B06` | Las promociones y reglas aprendidas respetan puertas humanas en operaciones reales. | NO_VERIFICABLE | Contrastado: La prohibición estructural no prueba el flujo productivo de autorización. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factoryrunner-execution-plane.md:B01` | Factory gobierna, ControlBot decide y FactoryRunner ejecuta sin ampliar autoridad. | NO_VERIFICABLE | Contrastado: Test de arquitectura documental, no ejecución del runtime externo. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factoryrunner-execution-plane.md:B02` | El execution plane funciona en hosting compartido sin root, Docker ni procesos ilimitados. | NO_VERIFICABLE | Contrastado: No hay smoke actual del runtime desplegado en Shared Hosting. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factoryrunner-execution-plane.md:B03` | Las órdenes son secret-free y los adapters resuelven aliases con permisos mínimos. | NO_VERIFICABLE | Contrastado: No se acreditó filtrado completo en todos los adapters reales. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factoryrunner-execution-plane.md:B04` | Orden y evento mantienen idempotencia y fencing por attempt_id y generation. | NO_VERIFICABLE | Contrastado: No se validaron side effects remotos con fencing real end-to-end. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factoryrunner-execution-plane.md:B05` | ControlBot preserva estado durable y rechaza eventos stale o doble ownership. | NO_VERIFICABLE | Contrastado: Un contrato textual no verifica transacciones reales de MariaDB. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factoryrunner-execution-plane.md:B06` | El fallback macOS solo se usa con evidencia de inviabilidad y protocolo idéntico. | NO_VERIFICABLE | Contrastado: El handoff físico no ha sido ensayado en este contraste. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/dieta-factory.md:B01` | El inventario de workflows mantiene baselines históricas separadas del estado vivo. | NO_VERIFICABLE | Contrastado: No se reprodujo aquí todo snapshot histórico de todas las fases. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/dieta-factory.md:B02` | La poda F1A preserva calidad, presupuesto y watchdog sin saltar gates. | CUBIERTO | `.github/workflows/factory-ci.yml`, `tests/test_dieta_fase1a.py`, [PR #1304](https://github.com/pl0n3r/Factory/pull/1304) · `2e20aef7fd8b019c677acec37e18d711341662cc` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/dieta-factory.md:B03` | La retirada del trigger Lab conserva las suites offline del laboratorio. | CUBIERTO | `.github/workflows/factory-ci.yml`, `tests/test_factory_lab_contract.py`, [PR #1304](https://github.com/pl0n3r/Factory/pull/1304) · `2e20aef7fd8b019c677acec37e18d711341662cc` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/dieta-factory.md:B04` | Cada siguiente poda dispone de preflight vigente en todos los consumidores. | NO_VERIFICABLE | Contrastado: El ledger anterior no acredita un preflight exact-main actual. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/dieta-factory.md:B05` | Una reversión acumulada de fases restaura todas las puertas sin pérdida de estado. | NO_VERIFICABLE | Contrastado: Existe plan de reversión por etapa, no simulacro integrado. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-lab.md:B01` | El laboratorio opera shadow y prohíbe escrituras externas. | CUBIERTO | `lab/factory_lab.py`, `tests/test_factory_lab_contract.py`, [PR #210](https://github.com/pl0n3r/Factory/pull/210) · `be8c5776e716d5115f2e9040e73ab1ecfd464851` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-lab.md:B02` | La comparación de candidato frente a stable usa SHAs distintos y evidencia Fitness. | CUBIERTO | `lab/factory_lab.py`, `tests/test_factory_lab_contract.py`, [PR #210](https://github.com/pl0n3r/Factory/pull/210) · `be8c5776e716d5115f2e9040e73ab1ecfd464851` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-lab.md:B03` | La evidencia causal exige muestras por impacto y rechaza observaciones insuficientes. | CUBIERTO | `lab/experiment_evidence.py`, `tests/test_experiment_evidence.py`, [PR #291](https://github.com/pl0n3r/Factory/pull/291) · `3e6b1640a780b94fd21ab99d4f17be18f3ca1d44` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-lab.md:B04` | La promoción revalida provenance y preserva execution=not-performed. | CUBIERTO | `lab/factory_lab.py`, `tests/test_factory_lab_contract.py`, [PR #219](https://github.com/pl0n3r/Factory/pull/219) · `5f22c659288bd2013213a234f61eae285d7f8ed3` | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-lab.md:B05` | El workflow evolution-lab.yml permanece habilitado para ejecutar shadow. | NO_APLICA | Contrastado: El trigger fue retirado expresamente por F1A, PR #1304; las pruebas viven en CI. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |
| `docs/factory-lab.md:B06` | El laboratorio autoriza por sí solo despliegue productivo tras mejorar Fitness. | NO_VERIFICABLE | Contrastado: La promoción no publica ni cruza puerta humana sin autorización. | [#1564](https://github.com/pl0n3r/Factory/issues/1564) |

## Producción y mejoras pendientes

Los épicos #304, #305, #1080, #1082, #1296 y #1382 tienen autoridad y criterios propios, pero ninguno constituye por sí solo una hoja ejecutable. Los AC de esos épicos se inventarían como fuente en `NO_VERIFICABLE` cuando no hay evidencia suficiente para acreditarlos. Se han comprobado cuatro capacidades offline específicas con PR MERGED y pruebas, sin atribuirles aceptación productiva ni cierre del épico.

Antes de afirmar `SIN_COBERTURA`, verificar ausencia en árbol exact-main y PRs fusionados, definir una hoja dentro del MVP y comprobar el presupuesto de creación Factory #1289. Un fallo de observación, una dependencia humana o un epic abierto no fabrican una brecha. No generar cien Issues por desconocimiento.

## Registro de hojas SIN_COBERTURA

| Issue nuevo canónico | Requisitos asociados | Autoridad/alcance |
| --- | --- | --- |
| Ninguna brecha positivamente demostrada en este corte | 0 | No se crean hojas artificiales |

## Resumen verificable

| Estado | Filas |
| --- | ---: |
| CUBIERTO | 38 |
| EN_CURSO | 0 |
| SIN_COBERTURA | 0 |
| DESCARTADO | 0 |
| NO_APLICA | 1 |
| NO_VERIFICABLE | 1680 |
| TOTAL | 1719 |

**Porcentaje CUBIERTO:** 2.21% (38/1719).

**Hojas nuevas creadas:** 0. **Fuentes Markdown:** 103+AGENTES.md. **Criterios de los seis épicos:** 39.

> La proporción mide acreditación positiva por cláusula en este corte, no progreso real del producto. Los requisitos no observados no son backlog autorizado y no deben expresarse como GREEN.
