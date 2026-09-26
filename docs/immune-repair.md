# Immune + Repair Engine v1

Immune + Repair convierte incidentes en una secuencia verificable de recuperación
y aprendizaje sin ocultar el fallo original.

## Lifecycle cerrado

Cada incidente empieza en `detect` y solo puede avanzar un paso:

`detect → contain → diagnose → repair → verify → immunize`

No hay saltos. El historial es append-only y `snapshot()` conserva siempre
`visible=true` y `history_preserved=true`, incluso después de reparar o
revertir. Un rollback no borra el incidente.

## Repair Plan

Toda reparación declara obligatoriamente:

- diagnóstico;
- acciones propuestas;
- verificación posterior;
- rollback reversible (`revert` o `restore_baseline`).

Repair Engine nunca ejecuta el plan: `automatic_execution_allowed=false` y
`execution=not-performed`.

### Acciones destructivas

Una reparación destructiva conserva explícitamente
`authority.required=human`. Sin una decisión humana concreta queda
`authorized_execution_ready=false`.

Incluso con una referencia de decisión aprobada, el motor solo marca el plan
como listo para un executor autorizado; **nunca** habilita ejecución automática.

## Verificación

La etapa `verify` exige un resultado booleano. `immunize` solo es posible si
la verificación anterior fue exitosa. Si falla, el incidente permanece visible
en `verify` y no puede convertirse en inmunidad.

## Inmunización

Dos o más incidentes distintos, respaldados por dos fuentes distintas, pueden
producir un candidato de inmunidad. El candidato conserva:

- firma canónica del fallo;
- todos los incidentes/fuentes origen;
- prevención esperada;
- estado `candidate`;
- rollback `revert`;
- fingerprint validado por Factory Constitution.

Se escribe únicamente como candidato en
`evolution_state.heuristics.immunity_<hash>`; este motor no lo promueve a
stable.

## Fuera de alcance

- ejecutar reparaciones;
- acciones destructivas automáticas;
- ocultar o eliminar incidentes;
- promover guardrails directamente;
- ampliar autoridad.
