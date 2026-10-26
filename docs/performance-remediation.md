# Performance Remediation v1

Este slice convierte un hallazgo de #311 en una **decisión gobernada**, no en ejecución directa. Reutiliza el Work Origin Contract de Factory Queue #269 y devuelve un WorkItem v1 validado como artefacto puro.

## Plan

Un proposal v1 declara una acción de workflow permitida por Performance Contract, identificadores/referencias opacas de cambio, hipótesis y rollback, flags de reversibilidad/tests/authority/product semantics, condiciones de escalamiento activadas y un WorkItem v1.

La decisión es fail-closed:

- `PERF_INFO` → `NO_ACTION`;
- evidencia no `CURRENT` → `BLOCKED`;
- costo/arquitectura/consistencia/semántica/destructivo/datos/capacity o falta de authority → `ESCALATE`;
- sin reversibilidad o tests → `BLOCKED`;
- solo un cambio seguro, reversible, testeado y dentro de authority → `AUTO_REPAIR`.

`AUTO_REPAIR` significa **elegible para la cola Factory**, no ejecución dentro de este módulo. `execute_actions` siempre es false y `authority` permanece unchanged.

## Before / After

La comparación exige la misma identidad `project + surface + metric`, el mismo budget/unidad y evidencia `CURRENT`. La dirección de mejora depende del operador: menor para `lte`, mayor para `gte`.

`ADOPT` requiere **una secuencia before → after distinguible** además de mejora de valor y clasificación: `after.observed.observed_at` debe ser estrictamente posterior al `before`, con timestamps UTC exactos; los `evidence_ref` deben ser diferentes y el cambio debe tener al menos un SHA o identificador de release **válido, presente en ambas muestras y distinto**. La comparación con la misma marca de tiempo, la misma referencia o el mismo par SHA/release devuelve `REVERT_OR_REPLAN` con `after_not_later`, `reused_evidence_ref` o `unchanged_build_identity`. Los timestamps o identidades malformados fallan cerrado con `PerformanceRemediationError`.

Solo una mejora medida con esa procedencia mínima, estados `CURRENT` y clasificación no empeorada puede producir `ADOPT` **como decisión pura**. Evidencia stale/unknown, ausencia de mejora o clasificación peor produce `REVERT_OR_REPLAN`. Los fixtures sintéticos con timestamps y SHA distintos prueban el algoritmo, **no** acreditan que existiera un PR, intervención causal, benchmark productivo o adopción operativa de Factory #304 AC-11. El caller conserva responsabilidad de verificar la autenticidad de cada muestra y el cambio realmente aplicado.

## Boundary

Este módulo no crea WorkItems remotamente, PRs, cambios de infraestructura ni schedulers; solo valida/deriva artefactos. #313 consume el resultado para Readiness/E2E. La cola única sigue siendo Factory #269 y cualquier autoridad humana continúa gobernada por PLAN-AGENTES/Constitution.
