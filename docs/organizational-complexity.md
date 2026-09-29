# Organizational Complexity Budget v1

Factory #245 mide burocracia por WorkItem sin crear un **Complexity Engine** ni un score mágico.

## Qué se mide

Cada observación conserva por separado:

- reglas/guardrails consultados;
- roles activos y revisores;
- checks/gates;
- handoffs;
- engines/compilers consultados;
- tokens de contexto;
- minutos de coordinación;
- minutos de espera;
- minutos de revisión;
- minutos de ejecución útil;
- las cinco dimensiones protegidas de Factory Constitution;
- evidencia y scope comparable.

El costo monetario/tokens/CI general sigue perteneciendo a #7. Este contrato usa sus budgets de tamaño y multiplicadores de `task_type` como fuente para escalar límites de overhead; no crea una segunda política de costos.

## Budget contextual

El budget depende de:

1. `task_size=small|medium|large` del modelo de #7;
2. multiplicador de `task_type` ya definido en `metricas/presupuestos.json`;
3. `risk=low|medium|high|critical`.

Riesgo mayor puede justificar más coordinación, checks, contexto o revisión. El límite no es universal.

No existe budget para reducir `security`, `privacy`, `traceability`, `reversibility` o `authority`. Esas dimensiones provienen de Factory Constitution y permanecen protegidas aunque el WorkItem exceda overhead.

## Vector, no score

`evaluate_workitem_complexity()` devuelve cada dimensión con:

- valor observado;
- budget contextual;
- estado `within|over`.

No suma estas dimensiones en una puntuación única. Un exceso crea únicamente un **simplification candidate** con dimensiones objetivo, provenance y `execute=false`. El candidato no desactiva controles ni modifica stable.

## Before / after

`compare_simplification()` reutiliza Fitness Engine. Solo compara observaciones de la misma cohorte (`comparison_scope + task_type + task_size + risk`).

Fitness recibe:

- Constitution: security/privacy/traceability/reversibility/authority, dirección `higher`;
- organizational_overhead_minutes, context_tokens y governance_items, dirección `lower`.

Una reducción de overhead con regresión protegida queda `blocked`. Una dimensión protegida unknown deja el resultado `inconclusive`. Solo `claim=improved`, sin regresiones ni faltantes, permite `can_claim_simplification=true`. Incluso entonces `execute=false`: adopción corresponde al lifecycle existente de #143/#161.

## Reporte / dashboard

`build_complexity_report()` distingue explícitamente:

- `useful_execution_minutes`;
- `organizational_overhead_minutes`;
- `total_minutes`;
- `overhead_ratio`;
- candidatos de simplificación;
- conteo de dimensiones excedidas.

Esto permite observar el costo operativo de la organización sin confundir trabajo productivo con coordinación.

## Boundary

Este slice no crea scheduler, store, workflow, ranking ni dashboard paralelo. No cambia `metricas/costos.py`, `metricas/presupuestos.json`, Fitness ni Constitution. No ejecuta simplificaciones y no rebaja gates de seguridad para cumplir un budget.

El siguiente consumidor de #248 es Growth/Pruning: puede usar candidatos con evidencia para proponer consolidación o retiro, preservando historia y autoridad.
