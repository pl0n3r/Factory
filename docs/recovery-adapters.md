# Recovery Adapters v1

#328 define adapters **declarativos** para destinos offsite. No realiza red, filesystem externo, subprocess, OAuth ni uploads reales.

## Providers

- `object_storage`: destino técnico primario/offsite. Siempre permanece primario.
- `google_drive`: cold-copy opcional y solo si el Recovery Manifest v1 declara `offsite.cold_copy=google_drive`.
- `icloud`: no soportado y no es dependencia del contrato.

## Descriptor

Cada intención recibe un Recovery Manifest v1 ya validable por #327 y un request cerrado:

- `provider`: `object_storage|google_drive`;
- `operation`: `upload|materialize|verify`;
- `object_ref`: referencia opaca, no path ni URL;
- `checksum_sha256`: SHA-256 hexadecimal lowercase;
- `idempotency_key`: referencia opaca y estable.

La salida añade proyecto, namespace derivado, role del destino, `authority=unchanged`, `execute=false` y un `descriptor_id` SHA-256 determinista. Repetir la misma intención produce el mismo descriptor.

## Seguridad

El módulo falla cerrado ante campos extra, providers/operaciones desconocidos, refs con path/URL, checksums inválidos y formas sensibles. No refleja valores secretos/PII en errores.

Los descriptors son **datos**, no comandos. No conceden permiso para tocar producción ni ejecutar restore/failover.

#329 consume estos descriptors para modelar el pipeline de backup/evidence. #330–#332 mantienen restore, health y E2E separados.
