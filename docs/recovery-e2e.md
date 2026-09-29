# Recovery E2E v1

#332 cierra el core local de Recovery componiendo, sin runtime nuevo, los contratos #327–#331:

```text
Recovery Manifest
→ backup plan
→ object storage primary + Google Drive cold-copy
→ backup VERIFIED
→ descartar source original
→ restore drill disposable
→ health + smoke + integrity
→ RPO/RTO
→ Recovery Health
→ Readiness projection
```

El escenario sano usa únicamente referencias opacas y evidencia simulada/determinista. Después de obtener el backup `VERIFIED`, el restore no recibe el source original ni los refs de snapshot/encrypted source; consume solo el artefacto verificado/offsite.

El E2E demuestra dos estados:
- backup fresco + drill PASSED → `HEALTHY` → Readiness reutiliza `HEALTHY` sin recalcular;
- drill vigente con RPO/RTO excedidos → `DEGRADED` con `rpo_breached` y `rto_breached`; un recovery point stale también permanece explícito como `backup_stale`.

Los negativos prueban que secretos/PII, target productivo y authority ampliada fallan cerrado. Todos los artefactos del flujo mantienen `authority=unchanged` y `execute=false`.

Este E2E no usa DB/media reales, red, SDK cloud, OAuth, subprocess, ControlBot, FactoryRunner ni producción. La adopción por Condor, GrindFlow, BRVTAL, ControlBot, Factory, FactoryRunner y AutoFactory sigue siendo evidencia separada del épico #305.
