# Recovery Health v1

#331 deriva una sola señal de Recovery para Factory Queue (#269) y Readiness (#293). No crea scheduler, WorkItems, porcentajes ni una fórmula paralela.

Estados:
- `HEALTHY`: backup VERIFIED fresco y restore drill PASSED fresco.
- `DEGRADED`: evidencia vigente con breach conocido de RPO/RTO o retention drift.
- `UNKNOWN`: evidencia requerida ausente o stale. Nunca cuenta como sano.
- `BLOCKED`: evidencia inválida/incoherente, checksum/offsite/authority/target contractual inválido.

Freshness no inventa umbrales: backup usa el RPO del Recovery Manifest y restore drill usa `restore_drill.cadence_days`.

El payload incluye razones explicables y solo estas clases canónicas de #269: `backup_missing`, `backup_stale`, `offsite_missing`, `checksum_failed`, `restore_drill_failed`, `rpo_breached`, `rto_breached`, `retention_drift`. `recovery_work_item_classes()` únicamente clasifica; no crea ni despacha trabajo.

`project_recovery_readiness()` copia el mismo `recovery_health`; no recalcula. Para recovery crítico, `UNKNOWN` o `BLOCKED` fuerza `ready=false`. `DEGRADED` permanece visible pero no se transforma artificialmente en otro estado.

Todo es declarativo: `authority=unchanged`, `execute=false`. #332 consume esta salida en el escenario E2E.
