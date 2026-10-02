# Simulacro E2E controlado del modo desatendido seguro — Tramo 4D

Estado: **simulacro sintético, sin producción, sin I/O externo y sin concesión de go-live**.

Este tramo valida la composición de los contratos ya integrados de 4B
(`scripts/unattended_guards.py`) y 4C (`scripts/unattended_watchdog.py`).
El E2E no copia su lógica, no crea una política runtime nueva y no cambia
autoridad.

## Evidencia base

El escenario usa exclusivamente fixtures sintéticos y reloj explícito. La
identidad de trabajo es `Factory#746`; las referencias a repo, reserva,
PresenceSnapshot, guardas, métricas, STATE e incidentes son datos de prueba.

No se utilizan credenciales, secretos, datos reales, proveedores, producción
ni endpoints externos.

## Baseline sano

Presence y STATE frescos, guardas dentro de techos y sin autoridad sensible:

- 4B produce `ALLOW`, `pause_allowed=false`, `authority=unchanged`;
- 4C conserva `ALLOW`;
- no aparecen incidencias ni interrupción al dueño.

## Pausa, breaker y techos

El simulacro ejercita pausa global, breaker en N fallos consecutivos y techo de
costo excedido. Con fencing que ya permite pausa, 4B produce `PAUSE`; 4C la
conserva. Si la pausa no está autorizada por fencing, 4B falla cerrado en
`BLOCKED`.

Ningún escenario crea trabajo autónomo nuevo ni amplía autoridad.

## Freshness, idle y reserva sin progreso

Se combinan de forma sintética:

- Presence `unknown`;
- STATE stale;
- trabajo ready sin siguiente despacho;
- reserva activa stale.

4C registra las incidencias correspondientes, mantiene el STATE como stale y
falla cerrado. Repetir exactamente la misma evidencia con sus fingerprints ya
alertados no genera fingerprints nuevos.

## Smoke rojo sostenido

El E2E **no implementa** una decisión runtime de rollback/stop. El smoke rojo se
inyecta como incidencia S1 sintética y se observa únicamente a través de 4B/4C.

Para el camino reversible ya autorizado, la autorización previa se representa
como evidencia sintética en STATE/next actions (`rollback-authorized`,
`exact-sha`, `backup-verified`) mientras 4B ya está en `PAUSE` canónico.
4C conserva `PAUSE`, `authority=unchanged`, interrumpe por S1 y expone esa
next action como evidencia; no ejecuta nada ni infiere autoridad adicional.

Los caminos inseguros permanecen cerrados:

- backup requerido no verificado → 4B `BLOCKED`;
- irreversible/destructivo → 4B `BLOCKED`;
- riesgo/autoridad UNKNOWN → 4B `BLOCKED`;
- 4C conserva `BLOCKED` y solo refleja una next action sintética de
  stop/escalation.

Así, el test demuestra rollback/stop **seguro como evidencia de una acción ya
autorizada**, no como capacidad nueva creada por el simulacro.

## Severidad

Incidentes S1/S2 frescos activan `interrupt_owner=true`. S3 no interrumpe.
UNKNOWN conserva fail-closed. Una severidad S1/S2 heredada de un STATE stale se
degrada a UNKNOWN y no interrumpe.

## Fronteras humanas y sensibles

Go-live, gasto, irreversible, datos reales y producción con backup requerido no
verificado permanecen `BLOCKED`. El simulacro no puede convertir estas puertas
en autorización.

## Criterio de salida

4D se considera técnicamente aprobado únicamente cuando los siete criterios de
#746 y `Tests de scripts` pasan sobre el HEAD exacto del PR, junto con los
gates normales de Factory.

Esto **no** autoriza:

- go-live;
- publicación de Factory@v1;
- gasto o aprovisionamiento;
- uso de credenciales o datos reales;
- deploy, backup o rollback real.

Cualquier fallo del simulacro debe corregirse en 4B o 4C si corresponde; el E2E
no puede debilitar esos contratos para pasar.
