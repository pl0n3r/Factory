# Performance Engineering Loop v1

Factory conecta cuatro contratos seriales:

`Performance Contract (#310) → Detection/Triage (#311) → Remediation + before/after (#312) → Performance Health (#313)`.

## Estado canónico

`performance/status.py` publica exactamente `HEALTHY | DEGRADED | UNKNOWN | BLOCKED`.

- evidencia no CURRENT → `UNKNOWN`;
- `PERF_INCIDENT` current o remediación BLOCKED/ESCALATE → `BLOCKED`;
- `PERF_DEGRADATION` current → `DEGRADED`;
- `PERF_INFO` current → `HEALTHY`, salvo before/after no adoptado.

No hay promedio ni score oculto. Un estado crítico no puede diluirse con checks menores.

## Readiness

La proyección para Readiness #293 copia `status`, razones, freshness/evidence refs e identidad de la dimensión performance. No reimplementa ni recalcula clasificación. UNKNOWN/stale nunca se presenta como sano.

## E2E y autoridad

El E2E de tests demuestra regresión → triage → WorkItem candidato → decisión gobernada → medición after → ADOPT → HEALTHY. Los caminos stale, escalamiento y regresión final permanecen no saludables.

Todo el loop es puro y reversible: `authority: unchanged`, `execute_actions: false`. No consulta producción, no crea PRs ni WorkItems remotamente y **no crea scheduler ni backlog paralelo**; el trabajo ejecutable sigue entrando por Factory Queue #269.
