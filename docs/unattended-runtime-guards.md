# Guardas runtime del modo desatendido seguro — Tramo 4B

Estado: **runtime puro, sin efectos externos**.

4B implementa la envolvente definida por
[`unattended-safe-mode.md`](unattended-safe-mode.md). No ejecuta trabajo, no
muta GitHub, no hace polling, no compra/provisiona recursos y no amplía
autoridad.

## Frontera con `adaptive_fencing`

`scripts/unattended_guards.py` recibe una `FencingDecision` ya calculada:

- `fail_closed` siempre produce `BLOCKED`;
- `replan` nunca se degrada a `ALLOW`: produce `PAUSE` si fencing permite la pausa y `BLOCKED` en caso contrario;
- `PAUSE` solo existe si fencing ya trae `pause_allowed=true`;
- si una guarda necesita pausa sin safe-point/preemptibility válido, produce
  `BLOCKED`;
- la salida conserva `authority=unchanged`.

Es una capa de seguridad, no un segundo dispatcher/coordinador.

## Configuración y evidencia

`ALLOW` exige configuración cerrada y explícita de:

- `global_pause`;
- al menos un breaker con `scope=agent|repo`, `subject` explícito y `threshold=N` positivo: `agent` usa identidad sin `/`; `repo` usa exactamente `owner/repo`, con componentes acotados;
- evidencia por breaker con `consecutive_failures`, `fresh` y `consistent`;
- techos no negativos de `usage`, `cost` y `parallelism`;
- mediciones correspondientes;
- riesgo y evidencia de segunda pasada;
- flags sensibles y requisito/evidencia de backup.

El estado del breaker **no lo decide el caller**: el core deriva `closed` cuando
`consecutive_failures < threshold` y `open` cuando es `>= threshold`.
Threshold ausente/cero/no entero, scope o subject inválidos, tipos no esperados,
evidencia ausente/no entera, `UNKNOWN`, stale o contradicción fallan cerrado.
Nunca se infiere N, presupuesto, cuota, paralelismo ni freshness.

## Decisiones

- `ALLOW`: todas las guardas explícitas están satisfechas.
- `PAUSE`: pausa global, breaker derivado abierto, techo superado o `replan`
  pendiente, solo cuando fencing ya permite pausa segura; un `replan` nunca se
  degrada a `ALLOW`.
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


## Aplicación en Dispatcher V2

`adaptive_dispatch_record(..., unattended_mode=True)` consume las decisiones ya
calculadas de 4B y 4C; **no** vuelve a evaluar thresholds, riesgo, freshness,
breakers, presupuestos ni severidades.

Exige:

- un `GuardDecision` canónico de 4B;
- un `WatchdogDecision` canónico de 4C;
- `authority=unchanged` en ambos;
- acciones cerradas `ALLOW|PAUSE|BLOCKED`;
- evidencia/fingerprints con forma canónica y razones secret-free.

Las combinaciones válidas son las que 4C puede emitir sin ser más permisivo que
4B:

- `ALLOW → ALLOW`: conserva exactamente el pipeline adaptativo y el ranking;
- `ALLOW → BLOCKED`: 4C endurece por evidencia UNKNOWN/stale/inválida;
- `PAUSE → PAUSE`: conserva la pausa autorizada por 4B;
- `PAUSE → BLOCKED`: 4C endurece una pausa a bloqueo;
- `BLOCKED → BLOCKED`: conserva el bloqueo.

`ALLOW → PAUSE` no es canónico: un `GuardDecision(ALLOW)` trae
`pause_allowed=false`, por lo que 4C no puede fabricar autoridad de pausa.
Cualquier combinación más permisiva, evidencia inválida, decisión ausente o
autoridad distinta de `unchanged` falla cerrado.

La frontera canónica de aplicación es `work_ladder()`. Cuando
`unattended_mode=true`, la escalera consume las decisiones 4B/4C **antes** de
normal, reconciliación quality, filler o product-direction.

Cuando el resultado efectivo es `PAUSE` o `BLOCKED`:

- `work_ladder()` retorna inmediatamente
  `next_action.step=unattended_gate`;
- la salida es status-only, `mutates=false` y `authority=unchanged`;
- `dispatch_record()` no invoca `select_next()` y conserva
  `selected=null`;
- no se ejecuta reconciliación stale, no se selecciona quality/filler y no se
  abre una puerta product-direction;
- las razones conservan causas canónicas secret-free como
  `guard:<reason>` y `watchdog:<incident-code>`;
- no se crea WorkItem ni una jerarquía paralela de supresión.

`dispatch_record()` propaga el modo y las decisiones a `work_ladder()`.
`adaptive_dispatch_record()` adapta Presence/Fencing y delega después en
`dispatch_record()`; ya no mantiene una segunda ruta de supresión. Con
`ALLOW → ALLOW` el pipeline/ranking previo se conserva.

`unattended_mode=false` mantiene compatibilidad legacy y no exige decisiones
4B/4C.

Esta frontera sigue siendo pura: no agenda, no muta GitHub, no reserva, no hace
polling y no concede autoridad para deploy, rollback, gasto o go-live. 4B/4C
deciden; Dispatcher V2 solo aplica esa decisión antes de iniciar trabajo nuevo.

