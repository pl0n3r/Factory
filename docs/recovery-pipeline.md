# Recovery backup pipeline v1

#329 conecta Recovery Manifest (#327) y adapters (#328) sin ejecutar I/O.

Flujo canónico: **snapshot/dump → checksum → encrypt → upload object storage → verify → cold-copy opcional → evidence**. `build_backup_pipeline()` solo emite un plan `PLANNED`; cada paso mantiene `authority=unchanged` y `execute=false`.

Object storage siempre es `primary_offsite`. Google Drive solo existe como `cold_copy` cuando el manifest lo exige y nunca sustituye el destino primario. Las idempotency keys de adapters se derivan con SHA-256 para ser estables y acotadas.

`verify_backup_evidence()` solo devuelve `VERIFIED` si manifest, pipeline y evidencia coinciden y existen encryption observada, checksum exacto, primary verification, referencia de inmutabilidad/versionado, cold-copy cuando aplica, timestamps coherentes y evidence refs opacas. Conserva RPO como `freshness_target_seconds`; #331 decidirá freshness real contra el tiempo observado.

No hay dumps/cifrado/uploads reales, SDK/OAuth, filesystem externo, subprocess, retention execution, restore, scheduler, WorkItems ni producción. #330 define restore drill; #331 health/Readiness; #332 E2E.
