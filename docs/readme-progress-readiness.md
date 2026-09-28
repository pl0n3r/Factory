# Progress + Readiness v1

Este contrato complementa README Contract v1. Factory calcula dos métricas distintas para un **target explícito** y publica un único payload canónico que después pueden renderizar README y consumir ControlBot.

## Semántica

`progress` responde cuánto del alcance objetivo está construido o verificado. `readiness` responde qué tan preparado está ese mismo alcance para su siguiente objetivo operativo/comercial. No se deriva de `issues cerrados / issues totales`.

El input declara `target`, dimensiones aplicables, hitos ponderados y blockers. Cada hito tiene señales independientes de progress/readiness, peso, freshness y referencias de evidencia. Los estados positivos `DEMONSTRATED`/`PARTIAL` solo cuentan con evidencia `CURRENT`; `STALE` y `UNKNOWN` conservan trazabilidad pero aportan cero.

Las dimensiones `NOT_APPLICABLE` permanecen visibles y salen del denominador. Una dimensión aplicable siempre conserva su peso aunque su evidencia sea unknown/stale: por eso la ausencia de prueba no mejora el porcentaje.

## Cálculo y blockers

Primero se normaliza cada dimensión por el peso de sus hitos; después se ponderan dimensiones. Esto evita que muchos checks pequeños dominen una capacidad crítica. El resultado es determinista y ordena dimensiones, hitos, blockers y evidence refs por identidad estable.

Un blocker `CRITICAL + OPEN` no borra el porcentaje calculado: lo conserva para diagnóstico, pero fuerza `readiness.status=BLOCKED`. Así un promedio alto nunca se presenta como listo.

`evidence_freshness` es `UNKNOWN` si alguna evidencia aplicable tiene freshness desconocida, `STALE` si al menos una es stale y ninguna unknown, y `CURRENT` solo cuando todo el baseline aplicable está current.

## Baseline y tendencia

`baseline_fingerprint` incluye target (`id`, `version`, `scope`) y la estructura ponderada de dimensiones/hitos. `compare_snapshots()` solo emite `DELTA` cuando ese fingerprint coincide. Si cambia target, scope, pesos o denominador, devuelve `REBASELINE` con deltas nulos: un cambio de baseline nunca se disfraza de mejora.

Para un baseline estable, la comparación conserva cambios de porcentaje por dimensión y apertura/cierre de blockers críticos como causas explicables.

## Frontera de responsabilidad

Este módulo no consulta GitHub, producción, AEGIS, LEX ni ControlBot. Recibe evidencia ya normalizada y no concede autoridad. #295 integra el payload con el bloque generado del README; #296 fija targets de los siete repos; #297 demuestra WorkItems/evidence → cálculo → README → consumer contract. ControlBot debe consumir este payload, no implementar una fórmula competidora.
