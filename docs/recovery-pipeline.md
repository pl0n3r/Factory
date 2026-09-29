# Recovery backup pipeline v1

#329 conecta Recovery Manifest (#327) con los adapters declarativos (#328). El módulo modela el ciclo mínimo:

```text
snapshot/dump
→ checksum
→ encrypt
→ upload object storage
→ verify remote object
→ cold-copy opcional
→ record evidence
```

Todo el resultado es **descriptivo**: cada paso conserva `authority=unchanged` y `execute=false`. Factory no abre sockets, no ejecuta subprocess, no lee/escribe backups reales y no cifra ni sube datos.

## Plan

`build_backup_pipeline()` exige una source `REQUIRED` del Recovery Manifest, refs opacas, SHA-256 e idempotency key. Object storage siempre es `primary_offsite`. Google Drive solo se añade como `cold_copy` si el manifest lo declara; nunca sustituye el destino técnico primario.

El pipeline permanece `PLANNED`; construirlo no demuestra que exista un backup.

## Evidence gate

`verify_backup_evidence()` solo emite `status=VERIFIED` si coinciden manifest, pipeline y evidencia y además:

- encryption está observada como realizada;
- checksum coincide con el plan;
- object storage primario fue verificado;
- existe una referencia opaca de versión/inmutabilidad;
- Drive fue verificado cuando el manifest lo requiere;
- timestamps tienen zona y `verified_at >= created_at`;
- existe al menos una evidence ref opaca.

La salida conserva timestamps, RPO como `freshness_target_seconds`, destinos y evidence refs para que #331 calcule estado/freshness. Este slice **no** calcula salud contra el reloj actual.

## Límites

No dumps, cifrado real, cloud SDK, OAuth, Google Drive API, filesystem externo, subprocess, retention execution, restore, scheduler, creación de WorkItems ni producción. #330 define restore drill; #331 health/Readiness; #332 E2E.
