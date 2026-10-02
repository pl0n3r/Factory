# Watchdog y resumen diario del modo desatendido — Tramo 4C

Estado: **runtime puro, determinista y sin efectos externos**.

4C consume los contratos ya integrados de 4A/4B. No crea scheduler, no hace
polling, no persiste estado y no muta GitHub. Su salida es evidencia para el
dispatcher y para el simulacro 4D.

## Entradas canónicas

`scripts/unattended_watchdog.py` exige configuración explícita, sin defaults:

- minutos máximos para trabajo ready sin siguiente despacho;
- minutos máximos de una reserva sin avance;
- freshness máxima de `STATE`.

La evidencia es cerrada e incluye: reloj observado explícito, PresenceSnapshot,
trabajo ready, siguiente despacho, reserva, `STATE`, incidentes observados,
fingerprints ya alertados y las listas del resumen diario. Campos desconocidos,
secretos, credenciales o PII fallan cerrado.

## Presence y actividad

4C reutiliza `scripts.presence_contract.classify_presence()`. No mantiene una
segunda definición de presencia.

- presencia `unknown`, sesión stale, heartbeat ausente o capacidad no fresca
  producen evidencia insuficiente y nunca cuentan como progreso sano;
- degradación conocida se reporta como S3;
- trabajo ready sin siguiente despacho solo abre incidencia cuando existe un
  umbral explícito y la edad observada lo alcanza.

## Reserva y STATE

La reserva usa identidad de trabajo, timestamp y freshness. Una reserva activa
que no coincide con `STATE.work_identity` falla cerrado. Stale/unknown o edad
por encima del umbral nunca se presenta como progreso.

`STATE` conserva exactamente los campos de 4A: identidad, repo, branch/SHA,
reserva, riesgo/severidad, evidencia, last state, next action, blockers y
timestamp. El watchdog valida timestamps, SHA, repo, listas y contenido
secret-free. Un timestamp futuro, campo desconocido o material sensible produce
`BLOCKED`.

## Decisión y autoridad

La decisión 4B se recibe como `GuardDecision` y no se recalcula:

- `BLOCKED` permanece `BLOCKED`;
- `PAUSE` permanece `PAUSE`;
- `ALLOW` solo permanece `ALLOW` con evidencia 4C suficiente y sin
  incidencias activas;
- UNKNOWN en 4C falla cerrado;
- 4C acepta solo el shape canónico de 4B: `ALLOW|BLOCKED` llevan
  `pause_allowed=false` y `PAUSE` lleva `pause_allowed=true`; una combinación
  incoherente falla cerrado;
- como un `ALLOW` canónico no concede autoridad de pausa, una incidencia 4C
  bajo `ALLOW` produce `BLOCKED`; un `PAUSE` ya emitido por 4B permanece
  `PAUSE`;
- 4C nunca convierte una decisión canónica en más autoridad.

La autoridad de salida siempre es `unchanged`.

## Idempotencia y alertas

Cada incidencia obtiene un SHA-256 sobre evidencia material estable: identidad,
freshness, threshold y timestamps que representen un cambio real de estado. Los
relojes de muestreo que avanzan normalmente (`now` y
`PresenceSnapshot.observed_at`) no forman parte de la identidad de la
incidencia. Una lista explícita de `already_alerted_fingerprints` marca
incidencias repetidas y evita emitir de nuevo el mismo fingerprint. Un cambio
material de reason/freshness/estado produce fingerprint nuevo.

Solo una incidencia S1/S2 nueva activa `interrupt_owner=true`. S3 se registra
sin interrupción; UNKNOWN conserva fail-closed sin inventar severidad.

## Resumen diario

`DailySummary` ordena determinísticamente:

- frentes activos;
- freshness de STATE;
- incidentes S1/S2/S3/UNKNOWN;
- blockers;
- gates humanos;
- cambios integrados;
- cambios revertidos;
- próximas acciones.

No incluye payloads libres ni datos sensibles.

## Frontera con 4D

4C solo produce evidencia/decisiones. 4D debe reutilizar este módulo y las
guardas 4B para su simulacro; no puede copiar lógica ni cambiar contratos para
hacer pasar el E2E.
