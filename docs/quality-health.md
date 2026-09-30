# Quality Health v1

#347 proyecta una sola lectura operacional de Quality para Readiness y Factory Queue. No ejecuta gates, no repara, no crea WorkItems y no recalcula Performance ni Recovery.

## Fuente de verdad

La matriz esperada `surface × required_gate` se deriva **únicamente** de Quality Contract v1. No existen defaults ocultos.

Cada gate aporta:

- `status=PASS|FAIL|UNKNOWN|STALE`;
- timestamp observado;
- referencia de evidencia.

La freshness se evalúa contra `evidence_freshness_seconds` del contrato. Evidencia ausente, stale o unknown nunca equivale a PASS.

Regression Intelligence #346 se consume ya clasificada:

- VERIFIED no degrada por sí sola;
- FLAKY y OBSERVED nunca habilitan PASS;
- REPRODUCED no resuelta bloquea una superficie crítica y degrada una no crítica.

## Performance y Recovery

Performance #304 y Recovery #305 son dimensiones externas. Quality consume sus estados canónicos y conserva razones/evidencia con `recalculated=false`.

## Sonar

Cuando Quality Contract declara `sonar`, Quality Health consume exclusivamente la evidencia normalizada por #490. No vuelve a interpretar payloads API ni recalcula Quality Gate, CE task, freshness, visibilidad, método, cobertura o deuda.

- PASS no degrada por sí solo;
- UNKNOWN y STALE proyectan Quality Health a UNKNOWN y nunca habilitan PASS;
- FAIL de Quality Gate o CE task es bloqueante;
- FAIL de line usage, configuración/cobertura o deuda degrada y emite una clase correctiva cerrada;
- razones y `evidence_refs` del normalizador se preservan con validación fail-closed;
- ausencia de evidencia Sonar cuando el contrato la exige produce UNKNOWN;
- contratos legacy sin bloque `sonar` conservan exactamente el comportamiento anterior.

La proyección vive en `external_dimensions.sonar` con `source=sonar_evidence_v1` y `recalculated=false`.

- no se vuelven a ejecutar detectores;
- no se copian budgets;
- no se recalculan RPO/RTO;
- ausencia de una dimensión requerida produce UNKNOWN.

## Precedencia

`BLOCKED > UNKNOWN > DEGRADED > PASS`.

- fallo o regresión reproducida en superficie crítica → BLOCKED;
- evidencia ausente/stale/unknown, incluida Sonar requerida, → UNKNOWN;
- fallo conocido no crítico o dimensión externa degraded → DEGRADED;
- solo evidencia current sin degradaciones → PASS.

## Readiness

`readiness_projection()` reutiliza exactamente Quality Health. No vuelve a clasificar evidencia.

- PASS y DEGRADED pueden continuar;
- UNKNOWN y BLOCKED nunca son ready;
- `recalculated=false`.

## Factory Queue

`work_item_classes` son clases correctivas descriptivas. Se materializan, si corresponde, usando **WorkItem v1 + Dispatcher V2** existentes. Este módulo no crea una cola, scheduler, Issue o PR.

Authority permanece `unchanged` y `execute_actions=false`.

## Boundary

No hay Quality Engine, ranking, score, scheduler, backlog ni pipeline paralelo. Readiness #293, Factory Queue #269, Performance #304, Recovery #305 y Sonar Evidence #490 siguen siendo contratos externos.


## Identidad y flags canónicos

Quality Contract usa un identificador lógico de proyecto y Regression Intelligence usa `owner/repo`; por eso `derive_quality_health()` exige `project_ref` explícito y valida cada regresión contra ese valor.

Los flags contractuales son literalmente `authority = unchanged`, `execute_actions = false` y `parallel_queue = false`. La integración opera sin scheduler y sin recalcular Performance o Recovery.
