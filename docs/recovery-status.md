# Recovery Health v1

#331 deriva una sola señal de Recovery para Factory Queue (#269) y Readiness (#293). No crea scheduler, WorkItems, porcentajes ni una fórmula paralela.

Estados:
- `HEALTHY`: backup VERIFIED fresco y restore drill PASSED fresco.
- `DEGRADED`: evidencia vigente con breach conocido de RPO/RTO o retention drift.
- `UNKNOWN`: evidencia requerida ausente o stale. Nunca cuenta como sano.
- `BLOCKED`: evidencia inválida/incoherente, checksum/offsite/authority/target contractual inválido.

Freshness no inventa umbrales: backup usa el RPO del Recovery Manifest y restore drill usa `restore_drill.cadence_days`.

**Orden causal obligatorio del drill.** Aunque una observación esté fresca, `drill_observed_at` debe ser mayor o igual a `verified_backup.created_at` (instante UTC validado del backup cuya referencia/huella el drill afirma haber recuperado), y nunca posterior a `observed_at`. Un drill anterior a la creación del backup devuelve `BLOCKED` con razón `DRILL_BEFORE_BACKUP` y clase `restore_drill_failed`; para Recovery crítico, Readiness conserva `ready=false`. La comprobación es determinista y declarativa: no verifica por sí sola que se ejecutó un restore, que el proveedor remoto contiene datos auténticos ni que existe evidencia operativa de RPO/RTO. Esos recibos siguen pendientes en Factory #305 y requieren autorización real de live (D-066/Factory #683).

El payload incluye razones explicables y solo estas clases canónicas de #269: `backup_missing`, `backup_stale`, `offsite_missing`, `checksum_failed`, `restore_drill_failed`, `rpo_breached`, `rto_breached`, `retention_drift`. `recovery_work_item_classes()` únicamente clasifica; no crea ni despacha trabajo.

`project_recovery_readiness()` copia el mismo `recovery_health`; no recalcula. Para recovery crítico, `UNKNOWN` o `BLOCKED` fuerza `ready=false`. `DEGRADED` permanece visible pero no se transforma artificialmente en otro estado.

Todo es declarativo: `authority=unchanged`, `execute=false`. #332 consume esta salida en el escenario E2E.

**Unicode inválido en recibos.** Si la serialización de evidencia de backup o drill contiene un surrogate Unicode sin parear, el control de tamaño UTF-8 lo trata como entrada inválida y devuelve `BLOCKED` (`BACKUP_SENSITIVE`/`DRILL_SENSITIVE`) en lugar de propagar una excepción. Un fixture válido mantiene la evaluación `HEALTHY` solo declarativa; no acredita backup real ni restore y conserva las prohibiciones D-066/Factory #683.
