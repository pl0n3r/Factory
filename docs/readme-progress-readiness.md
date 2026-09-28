# README Progress + Readiness v1

Este contrato extiende README Contract v1 con dos métricas ejecutivas distintas y explicables:

- **Progress**: cuánto del alcance objetivo se ha construido o verificado.
- **Readiness**: cuánto de lo necesario para el siguiente objetivo operativo/comercial está demostrado.

El motor vive en `readme/progress_readiness.py`. No consulta GitHub, producción, ControlBot ni redes. Recibe evidencia normalizada y produce un snapshot determinista descrito por `readme/progress_readiness.schema.json`.

## Target explícito

Todo cálculo pertenece a un target identificable:

- `id`;
- `label`;
- `scope`;
- `version`.

El fingerprint del target usa `id + scope + version`. Cambiar cualquiera de esos campos crea un baseline nuevo.

Un cambio de target se reporta como `REBASELINE`, con deltas nulos. No se presenta como mejora o deterioro comparable.

## Evidencia y estados

Cada dimensión contiene hitos ponderados. Cada hito declara por separado:

- `progress_state`;
- `readiness_state`;
- `weight`;
- `evidence_refs[]`.

Estados canónicos:

| Estado | Semántica |
| --- | --- |
| `SATISFIED` | evidencia actual demuestra el hito; aporta su peso |
| `UNSATISFIED` | evidencia demuestra que falta; aporta 0 |
| `UNKNOWN` | no existe evidencia suficiente; aporta 0 |
| `STALE` | existió evidencia pero no es actual; aporta 0 |
| `NOT_APPLICABLE` | explícitamente fuera de alcance; se excluye del denominador |

`NOT_APPLICABLE` requiere `evidence_refs`: no puede usarse como truco para eliminar trabajo del denominador sin justificación.

`UNKNOWN` puede no tener refs porque representa precisamente ausencia de evidencia. `STALE`, `SATISFIED`, `UNSATISFIED` y `NOT_APPLICABLE` requieren evidencia.

Si existe cualquier hito o blocker `UNKNOWN/STALE`, `evidence_freshness` queda `DEGRADED`. Nunca se convierte automáticamente en CURRENT o GREEN.

## Cálculo

Para una dimensión y una métrica:

```text
dimension_score =
  sum(weight de hitos SATISFIED)
  / sum(weight de hitos aplicables)
```

Los hitos `NOT_APPLICABLE` no entran en el denominador. UNKNOWN, STALE y UNSATISFIED sí son aplicables y valen cero.

El resultado global usa el peso de cada dimensión aplicable:

```text
metric =
  sum(dimension_weight × dimension_score)
  / sum(dimension_weight)
```

La aritmética interna usa fracciones exactas. El output expone:

- `basis_points`: entero 0..10000;
- `percent`: string decimal de dos posiciones, por ejemplo `"63.25"`;
- `contributions[]`: score, peso, evidence refs y unknown/stale por dimensión.

Esto evita depender de floats y deja el resultado reproducible byte a byte.

### No es conteo de Issues

El motor no recibe ni conoce “issues cerrados” o “issues totales”. Dos hitos pueden tener pesos 90/10 y producir 90% aunque solo uno de dos esté satisfecho. El peso representa impacto del objetivo, no cantidad de objetos administrativos.

Los pesos son parte del target/contrato de evidencia y deben cambiarse mediante una nueva definición de target cuando alteren materialmente el baseline.

## Progress y Readiness son independientes

Un mismo hito puede estar:

- construido pero todavía no listo para operar;
- listo en términos operativos aunque otra capacidad de producto siga incompleta;
- N/A para una métrica y aplicable para la otra.

Por eso cada milestone tiene dos estados distintos y el motor calcula dos agregados independientes.

## Blockers

Los blockers permanecen fuera del promedio.

Campos:

- `id`;
- `label`;
- `severity`;
- `state: OPEN|RESOLVED|UNKNOWN|STALE`;
- `evidence_refs[]`.

Un blocker `critical` que no esté `RESOLVED` aparece en `critical_blockers[]` y fuerza:

```text
readiness.status = BLOCKED
```

aunque `readiness.basis_points == 10000`.

Un blocker crítico UNKNOWN/STALE también bloquea fail-closed. Un promedio alto nunca convierte ausencia de evidencia crítica en autorización.

Estados de readiness:

- `READY`: 100% demostrado y cero blockers críticos no resueltos;
- `BUILDING`: medición disponible pero incompleta;
- `BLOCKED`: existe blocker crítico no resuelto/conocido;
- `UNKNOWN`: no existe base aplicable para medir.

## Tendencia y explicación

El snapshot puede compararse con uno anterior del mismo target.

### Mismo target

Resultado:

`TREND`

Incluye:

- delta de progress en basis points;
- delta de readiness en basis points;
- `causes[]` para milestones y blockers que cambiaron;
- evidence refs nuevas en cambios de milestones.

### Target distinto

Resultado:

`REBASELINE`

- `comparable: false`;
- deltas `null`;
- causa `target_change`;
- target anterior y nuevo explícitos.

Así un cambio del denominador nunca se vende como “+12 puntos” de progreso real.

## Determinismo

Antes de calcular:

- dimensiones se ordenan por `id`;
- hitos se ordenan por `id`;
- blockers se ordenan de forma estable;
- evidence refs se deduplican y ordenan;
- timestamps se normalizan a UTC;
- aritmética usa `Fraction`;
- JSON canónico usa keys ordenadas.

Mismo input semántico produce el mismo snapshot y el mismo `canonical_payload()`.

## Payload canónico

El snapshot contiene:

- target y `target_fingerprint`;
- `observed_at`;
- progress;
- readiness;
- evidence freshness;
- dimensiones con milestones normalizados;
- blockers y critical blockers;
- trend/rebaseline.

README y ControlBot deben consumir este mismo payload. Ningún consumidor debe recalcular porcentajes con otra fórmula.

## Boundaries

Este slice no:

- modifica el generador o validador del README;
- escribe porcentajes manuales;
- consulta GitHub, producción o proveedores;
- decide pesos automáticamente;
- crea rankings entre proyectos;
- mide productividad individual;
- autoriza deploy, dinero, legal o go-live.

La integración al bloque README, targets de los siete repos y E2E/consumer contract se entregan en los slices dependientes #295, #296 y #297.
