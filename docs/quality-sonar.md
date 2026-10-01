# Evidencia Sonar v1

Este leaf de #487 normaliza snapshots de Sonar ya obtenidos por otro componente. No hace red, no ejecuta acciones en Sonar, no crea Issues y no modifica Quality Health.

La entrada es deliberadamente cerrada. Debe declarar:

- `project` dentro del catálogo explícito: `brvtal`, `condor`, `controlbot`, `factory`, `factoryrunner`, `grindflow`;
- `snapshot_at` con zona horaria y `evidence_refs` no sensibles;
- `quality_gate` con estado `OK|ERROR` y condiciones fallidas cuando aplique;
- `analysis` con `analyzed_at`, método `automatic|ci` y si existe cobertura publicable;
- `ce_task` y su `error_message` cuando el servidor marca `FAILED`;
- uso de líneas de organización, visibilidad y deuda histórica;
- ausencia conocida de una señal como `null`, no omitiendo la clave.

Una clave faltante, un campo extra, una referencia URL/secreta, datos temporales futuros o un payload ambiguo abortan con error. Un valor explícitamente ausente (`null`) se normaliza como **UNKNOWN**, nunca como PASS.

## Salida

`normalize_sonar_snapshot()` produce ocho señales ordenadas:

1. `quality_gate`;
2. `analysis_freshness`;
3. `ce_task`;
4. `organization_line_usage`;
5. `visibility`;
6. `analysis_method`;
7. `coverage`;
8. `historical_debt`.

Cada señal contiene `status=PASS|FAIL|UNKNOWN|STALE|NOT_APPLICABLE`, `observed_at`, `freshness`, `evidence_refs`, razón y detalles normalizados. `NOT_APPLICABLE` solo existe cuando el Quality Contract Sonar lo declara explícitamente con `state`, `reason` y `source_ref`; no es PASS, no es UNKNOWN y conserva su provenance. Si el snapshot o análisis supera su freshness contractual, las señales requeridas se vuelven **STALE**; una señal contractualmente `NOT_APPLICABLE` conserva ese estado.

`analysis_method=ci` exige evidencia de cobertura: `coverage_available=false` es FAIL. Cuando `analysis_method=automatic`, el runtime productivo declara `coverage` como `not_applicable`; la señal se conserva como `NOT_APPLICABLE`, nunca como PASS. Contratos legacy sin `sonar.applicability` conservan el comportamiento anterior (Automatic sin cobertura → UNKNOWN). De forma equivalente, `organization_line_usage` es `NOT_APPLICABLE` solo cuando el contrato declara visibilidad pública; para visibilidad privada sigue siendo requerida.

La deuda se agrupa por `type + severity`, conserva `oldest_age_days` por grupo y se compara contra los límites explícitos del Quality Contract; también falla si la antigüedad máxima global supera `max_debt_age_days`. Los `evidence_ref` item-level se validan pero no se propagan al agregado; la autoridad del lote queda en `snapshot.evidence_refs`, evitando que un snapshot válido falle solo por cantidad de hallazgos.

Los mensajes de CE task se compactan y sanea cualquier URL o forma de secreto antes de conservarlos. Las demás entradas sensibles fallan cerrado.

La salida declara `authority=read_only` y `execute_actions=false`. #491 puede consumirla; este módulo no recalcula Quality Health ni crea un pipeline paralelo.
