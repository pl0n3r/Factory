# Guardas runtime del modo desatendido seguro — Tramo 4B

Estado: **runtime puro, sin efectos externos**.

4B implementa la envolvente definida por
[`unattended-safe-mode.md`](unattended-safe-mode.md). No ejecuta trabajo, no
muta GitHub, no hace polling, no compra/provisiona recursos y no amplía
autoridad.

## Frontera con `adaptive_fencing`

`scripts/unattended_guards.py` recibe una `FencingDecision` ya calculada:

- `fail_closed` siempre produce `BLOCKED`;
- `PAUSE` solo existe si fencing ya trae `pause_allowed=true`;
- si una guarda necesita pausa sin safe-point/preemptibility válido, produce
  `BLOCKED`;
- la salida conserva `authority=unchanged`.

Es una capa de seguridad, no un segundo dispatcher/coordinador.

## Configuración y evidencia

`ALLOW` exige configuración cerrada y explícita de:

- `global_pause`;
- al menos un breaker `open|closed` con evidencia `condition/fresh/consistent`;
- techos no negativos de `usage`, `cost` y `parallelism`;
- mediciones correspondientes;
- riesgo y evidencia de segunda pasada;
- flags sensibles y requisito/evidencia de backup.

Campos ausentes/extra, números no finitos, `UNKNOWN`, stale o contradicción
fallan cerrado. Nunca se infieren presupuesto, cuota, paralelismo ni freshness.

## Decisiones

- `ALLOW`: todas las guardas explícitas están satisfechas.
- `PAUSE`: pausa global, breaker abierto o techo superado, solo cuando fencing
  permite pausa segura.
- `BLOCKED`: falta configuración/evidencia/autoridad o la pausa necesaria no
  está permitida.

La salida incluye `reasons` cerradas y `evidence_fingerprint` SHA-256 sobre el
estado normalizado; no copia payloads libres, secretos, credenciales ni PII.

## Riesgo y autoridad sensible

`risk=high` requiere `second_pass=true`; `risk=UNKNOWN` bloquea. `go_live`,
`spend`, `irreversible` y `real_data` siguen fuera de autoridad. Cuando un cambio
de producción exige backup, solo continúa con `backup_verified=true`.

Satisfacer 4B nunca salta D-055/D-059/D-063/D-066/D-067 ni otra puerta humana.

## Boundary con 4C

4C podrá consumir `GuardDecision` para watchdog/freshness y resumen diario, pero
no podrá cambiar `BLOCKED→ALLOW`, ampliar `pause_allowed`, reinterpretar
autoridad, inventar thresholds ni añadir I/O a este módulo.

Orden serial: `4A contrato → 4B guardas → 4C watchdog/resumen → 4D simulacro E2E`.
