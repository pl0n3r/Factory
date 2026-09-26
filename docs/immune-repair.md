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

La autoridad no se acepta desde un dict del caller, aunque incluya
`author_association=OWNER`, estado resuelto y un SHA-256 correcto. El caller
solo aporta un **handle** `decision_ref`; un `TrustedDecisionSource`
inyectado por el runtime resuelve el registro durable y autenticado. El plan
conserva el fingerprint como integridad del registro resuelto, nunca como prueba
de procedencia. Revalidar un plan destructivo aprobado exige consultar otra vez
la misma fuente confiable y el mismo scope exacto.

Incluso con una referencia de decisión aprobada, el motor solo marca el plan
como listo para un executor autorizado; **nunca** habilita ejecución automática.

## Verificación

La etapa `verify` exige un resultado booleano. `immunize` solo es posible si
la verificación anterior fue exitosa. Si falla, el incidente permanece visible
en `verify` y no puede convertirse en inmunidad.

## Inmunización

Dos o más incidentes distintos pueden producir un candidato de inmunidad solo
cuando sus IDs se resuelven desde un `TrustedIncidentRegistry` append-only
inyectado por el runtime. Snapshots y hashes aportados directamente por el
caller no constituyen provenance. El registry entrega los snapshots canónicos,
su `source_id` y los handles que se vuelven a resolver al validar el candidato.

El candidato conserva:

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

## Trust boundary de provenance

`TrustedDecisionSource` y `TrustedIncidentRegistry` son capacidades del
runtime, no payloads serializados elegidos por quien solicita la reparación.
Sus registros son append-only: un handle existente no se puede reemplazar.
Esta capa modela la procedencia confiable; la integración concreta con
GitHub/ControlBot u otro almacén durable vive fuera de estos motores y debe
autenticar identidad, permisos y origen antes de registrar evidencia.
