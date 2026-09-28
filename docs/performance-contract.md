# Performance Contract v1

Factory define aquí **qué medir y contra qué evidencia comparar**, no umbrales globales. Cada proyecto declara sus superficies y métricas con baseline y budget propios.

## Contrato

Un documento v1 contiene `project` y una o más `surfaces`. Cada métrica exige:

- `baseline`: valor, unidad y `observed_at`;
- `budget`: operador `lte|gte`, valor y la misma unidad del baseline;
- `window`: `duration_seconds` y `min_samples`;
- `freshness.max_age_seconds`;
- `evidence`: `source`, referencia opaca y timestamp;
- `allowed_actions`: solo `observe`, `diagnose`, `benchmark`, `create_work_item`, `measure_before_after`;
- `escalation_conditions`: catálogo cerrado de costo, arquitectura, consistencia, semántica de negocio, migración destructiva, datos sensibles o presupuesto de capacidad.

El validador falla cerrado ante campos desconocidos, números no finitos, unidades incompatibles, timestamps sin zona, freshness inválido o texto con forma de secreto. Los errores describen el campo/clase y nunca reflejan el valor sensible.

Los arrays y superficies se normalizan de forma determinista. `allowed_actions` describe pasos de workflow; **no concede autoridad** para escribir en producción, cambiar políticas, gastar dinero ni ejecutar acciones destructivas. La autoridad sigue viniendo de `PLAN-AGENTES.md`, `decisiones.yml` y las puertas humanas vigentes.

## Freshness y estado

Este slice solo valida que exista un límite de freshness y evidencia fechada. No decide si una observación está sana: #311 compara evidencia contra baseline/budget y debe tratar stale/ausente como `UNKNOWN`/degradado, nunca como sano.

## Boundary del DAG

- #310: contrato, schema y validación.
- #311: detección de regresiones y triage.
- #312: remediación gobernada + before/after.
- #313: estado consumible por Readiness y escenario E2E.

No hay scheduler, APM, consultas de producción, Team Compiler, WorkItems automáticos, caches/CDN/Redis ni auto-repair en este slice.
