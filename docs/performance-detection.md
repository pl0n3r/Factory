# Performance Detection + Triage v1

Este slice consume Performance Contract v1 y una observación explícita. No consulta APM, RUM, bases de datos ni producción: compara evidencia ya recolectada.

## Observación

La identidad es `project + surface + metric`. La observación incluye valor/unidad, `observed_at`, ventana, muestra, severidad, impacto operacional, bottleneck explícito, referencia de evidencia y SHA/release opcionales.

La evidencia queda fail-closed:
- identidad desconocida → `PERF_REVIEW / UNKNOWN`;
- stale, ventana corta o muestra insuficiente → `PERF_REVIEW`;
- budget cumplido con evidencia current → `PERF_INFO`;
- breach current → `PERF_DEGRADATION`;
- `PERF_INCIDENT` exige además severidad `critical` e impacto operacional explícito.

Cruzar un número aislado nunca basta para declarar incidente.

## Triage

`performance/triage.py` traduce un bottleneck de catálogo cerrado a `role_hints`. Son recomendaciones para Team Compiler: no ejecutan acciones, no crean WorkItems y mantienen `authority: unchanged`.

## Boundary

#312 implementará remediación gobernada y before/after. #313 publicará el estado consumible por Readiness y el E2E. Este slice no cambia baseline, no autocorrige y **no crea scheduler ni backlog paralelo**; el trabajo material seguirá entrando por Factory Queue #269.
