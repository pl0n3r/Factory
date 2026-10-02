# Guardas runtime del modo desatendido seguro — Tramo 4B

Estado: **runtime puro, sin efectos externos**.

Este documento implementa el segundo slice serial definido por
[`unattended-safe-mode.md`](unattended-safe-mode.md). La capa 4B no ejecuta
trabajo, no muta GitHub, no hace polling, no compra/provisiona recursos y no
amplía autoridad. Solo decide si una transición desatendida puede continuar,
debe pausar o debe quedar bloqueada.

## Frontera con `adaptive_fencing`

`scripts/unattended_guards.py` recibe una `FencingDecision` ya calculada por
`scripts/adaptive_fencing.py`.

Reglas invariantes:

- `adaptive_fencing.action == fail_closed` siempre produce `BLOCKED`;
- una guarda puede producir `PAUSE` solo cuando `adaptive_fencing.pause_allowed`
  ya es `true`;
- si la guarda necesita pausar pero fencing no autoriza pausa, produce
  `BLOCKED`, nunca inventa un safe-point;
- la salida conserva `authority = unchanged`;
- generation/attempt y fingerprints de fencing entran únicamente en el
  fingerprint determinista de evidencia, no se reinterpretan.

La capa 4B es una envolvente de seguridad, no un segundo dispatcher ni un
segundo coordinador.

## Configuración cerrada

Para llegar a `ALLOW` deben existir explícitamente:

1. `global_pause`: booleano;
2. al menos un circuit breaker configurado con estado `open` o `closed`;
3. techos numéricos no negativos para `usage`, `cost` y `parallelism`;
4. evidencia actual y consistente de cada breaker;
5. mediciones explícitas de uso, costo y paralelismo;
6. clasificación de riesgo y estado de segunda pasada;
7. flags cerrados para acciones sensibles y requisito/evidencia de backup.

Campos ausentes, extra, no finitos, negativos, `UNKNOWN`, stale o
contradictorios fallan cerrado. El módulo no inventa presupuesto, cuota,
paralelismo, freshness ni estado de breaker.

## Decisiones

La salida solo puede ser:

- `ALLOW`: todas las guardas explícitas están satisfechas;
- `PAUSE`: una condición configurada exige pausa y `adaptive_fencing` ya permite
  esa pausa en un safe-point/preemptibility válido;
- `BLOCKED`: falta autoridad, configuración o evidencia, fencing falló cerrado,
  la pausa necesaria no está permitida o una acción sensible conserva puerta.

Toda salida contiene:

- `authority = unchanged`;
- `pause_allowed` sin ampliar el valor de fencing;
- `reasons` de vocabulario cerrado, sin copiar payloads libres;
- `evidence_fingerprint` SHA-256 reproducible sobre el estado normalizado.

## Pausa global

Cuando `global_pause=true`, la capa no permite iniciar nueva transición
autónoma. Si fencing ya autoriza una pausa segura, devuelve `PAUSE`. En caso
contrario devuelve `BLOCKED` para no forzar una interrupción en un punto no
seguro.

Una configuración ausente o no booleana no se interpreta como `false`.

## Circuit breakers

Cada breaker tiene un identificador acotado y un estado configurado `open` o
`closed`. La evidencia correspondiente debe declarar:

- `condition`: condición observada;
- `fresh`: evidencia actual;
- `consistent`: ausencia de contradicción conocida.

Un breaker `closed` con condición observada activa es contradictorio y bloquea.
Un breaker `open` solo puede producir `PAUSE` cuando la condición está observada,
fresh y consistente. `UNKNOWN`, stale o inconsistente nunca produce `ALLOW`.

## Techos de uso, costo y paralelismo

Los tres techos deben estar declarados. La ausencia de cualquiera bloquea la
decisión en vez de inferir un valor por defecto.

Si una medición supera su techo, la guarda solicita pausa. `PAUSE` solo se emite
si fencing ya la autoriza; de lo contrario el resultado es `BLOCKED`.

Estos techos son límites de ejecución ya configurados, no autorización para
comprar, recargar, renovar ni aumentar planes.

## Riesgo y autoridad sensible

- `risk=high` exige evidencia `second_pass=true` antes de `ALLOW`;
- `risk=UNKNOWN` bloquea;
- `go_live`, `spend`, `irreversible` y `real_data` permanecen fuera de la
  autoridad de 4B y producen `BLOCKED`;
- un cambio de producción cuyo contrato exige backup solo puede continuar con
  `backup_verified=true`.

Esto conserva D-055/D-059/D-063/D-066/D-067 y las puertas humanas vigentes. El
hecho de satisfacer guardas no autoriza por sí mismo una acción que otro contrato
prohíbe.

## Sanitización y determinismo

El módulo no usa red, filesystem, subprocesses ni APIs externas. Las entradas se
normalizan a estructuras cerradas y la salida nunca refleja tokens, secretos,
PII o payloads libres. Entradas con campos inesperados fallan cerrado con una
razón genérica y un fingerprint que no incorpora el payload inválido.

## Boundary con Tramo 4C

4C podrá consumir `GuardDecision` para watchdog/freshness y resumen diario, pero
no debe:

- volver a evaluar o reinterpretar autoridad;
- cambiar `BLOCKED` a `ALLOW`;
- ampliar `pause_allowed`;
- inventar thresholds ausentes;
- ejecutar polling o side effects desde este módulo.

El orden sigue siendo serial:

`4A contrato → 4B guardas runtime → 4C watchdog/resumen → 4D simulacro E2E`.
