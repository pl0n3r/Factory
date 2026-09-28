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

El fingerprint del baseline usa `id + scope + version` del target más la estructura ponderada de dimensiones/hitos y su aplicabilidad por métrica. Cambiar target, pesos o qué queda `NOT_APPLICABLE` crea un baseline nuevo; cambiar únicamente SATISFIED/UNSATISFIED/UNKNOWN/STALE no lo hace.

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

Los pesos son parte del baseline. Si cambian, el fingerprint cambia y la comparación devuelve `REBASELINE` aunque el caller olvide subir la versión del target.

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


## Targets canónicos por proyecto

Los targets de adopción viven en `readme/projects/progress-readiness/`. Son inputs declarativos para el motor canónico de este documento: **no contienen porcentajes manuales** y no sustituyen las fuentes de verdad de cada producto.

| Proyecto | Target actual | Scope | Fuente de verdad / roadmap |
| --- | --- | --- | --- |
| Factory | Autonomous Factory Readiness | `pl0n3r/factory` | PLAN-AGENTES.md, #293 y roadmap del kit |
| Condor | Colombia V1 Readiness | `pl0n3r/Condor` | Roadmap #1 y evidencia operativa canónica |
| GrindFlow | Commercial V1 Readiness | `pl0n3r/GrindFlow` | Roadmap #2 y especificaciones/requirements |
| BRVTAL | Platform / Event Operations Readiness | `pl0n3r/brvtal` | Roadmap #533 y evidencia de plataforma/eventos |
| ControlBot | Business OS Readiness | `pl0n3r/ControlBot` | Business OS #121 y contratos del control plane |
| FactoryRunner | Execution Plane Readiness | `pl0n3r/FactoryRunner` | Roadmap #1 y contratos del execution plane |
| AutoFactory | Local Automation Readiness | `pl0n3r/AutoFactory` | Roadmap #1 y contratos locales/manuales |

Cada fixture declara dimensiones y pesos propios del objetivo. Un milestone que todavía no tiene evidencia empieza como `UNKNOWN`, por lo que aporta cero y degrada freshness; el archivo no fabrica progreso inicial. `NOT_APPLICABLE` solo se usa cuando una dimensión queda explícitamente fuera del target y siempre conserva una `evidence_ref` de política.

### Actualizar un target

1. Cambia evidencia/estado de milestones cuando el objetivo y denominador siguen siendo los mismos.
2. Cambia `target.version`, scope, pesos o aplicabilidad cuando cambia el baseline.
3. El segundo caso debe producir `REBASELINE`; nunca se conserva un porcentaje del scope anterior como si fuera tendencia comparable.
4. Los valores derivados se calculan con `calculate_progress_readiness()` y se serializan con `canonical_payload()`; README y ControlBot no implementan otra fórmula.
5. Las fuentes de verdad permanecen en roadmap, WorkItems, acceptance, CI, health, seguridad, legal, infraestructura y demás evidencia canónica. Los fixtures solo describen qué dimensiones pertenecen al objetivo.

El slice E2E #297 enlaza después evidencia → cálculo → README → contrato consumidor de ControlBot.


## E2E: evidence → cálculo → README → ControlBot

El slice E2E de #297 prueba el recorrido completo sin red ni dependencias externas:

1. toma un fixture canónico de `readme/projects/progress-readiness/`;
2. representa la evidencia cambiando únicamente estados/evidence refs del mismo target;
3. calcula con `calculate_progress_readiness()`;
4. valida/serializa con `canonical_payload()`;
5. entrega **ese mismo snapshot** a `generate_readme()`;
6. proyecta el mismo payload canónico al consumer contract compatible con ControlBot.

### Contrato consumidor de ControlBot

ControlBot es un consumidor, no una segunda calculadora. La vista contractual puede leer del payload canónico:

- `target`;
- `progress`;
- `readiness`;
- `evidence_freshness`;
- `critical_blockers`;
- `trend`.

No recibe una fórmula alternativa ni vuelve a sumar weights/milestones. Si necesita drill-down, debe conservar referencias al snapshot/evidencia canónica y ampliar el contrato de forma versionada, no recomputar el agregado.

Un blocker crítico continúa visible y mantiene `readiness.status = BLOCKED` aunque otros hitos estén satisfechos. `UNKNOWN` y `STALE` siguen fail-closed según el motor canónico.

### Tendencia frente a rebaseline

Una transición de milestone dentro del mismo baseline produce `TREND` y causas explicables. Cambiar target, scope, version, pesos o aplicabilidad produce `REBASELINE` con deltas nulos.

Por tanto el flujo E2E nunca presenta un cambio de denominador como mejora real.

### Boundary de este E2E

Este test no llama a GitHub, producción ni ControlBot, y no modifica ControlBot. Demuestra el **consumer contract** offline usando exactamente el mismo payload que README. La integración de UI/backend de ControlBot debe consumir este contrato sin ampliar autoridad ni introducir porcentajes manuales.
