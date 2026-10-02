# Fuente canónica STATE/Presence para modo desatendido

Este contrato convierte **evidencia GitHub ya leída por el caller** en STATE utilizable y en una PresenceSnapshot deliberadamente conservadora. El módulo no hace red, polling ni mutaciones.

## Marker STATE

Mientras exista trabajo activo con reserva canónica, los handoffs/checkpoints materiales publican en el Issue de trabajo:

`<!-- factory-state {"version":1,"state":{...STATE v4A...}} -->`

El objeto `state` usa exactamente el contrato de `scripts/unattended_watchdog.validate_state()`: identidad, repo, branch/SHA/reserva, riesgo, severidad, evidencia, estado anterior, próxima acción, blockers y `updated_at`.

Con una reserva activa, esta fuente exige binding de `work_identity`, `repository`, `reservation_id` y `branch`; si el caller aporta el SHA real de la rama, un SHA distinto bloquea. El `updated_at` del STATE no puede ser posterior al timestamp GitHub del comentario que lo contiene.

## Provenance

- La lease autoritativa es el **último** marker **v3** `condor-reserva` publicado por `github-actions[bot]`; versiones históricas o shapes parciales fallan cerrado.
- La lease v3 usa shape cerrado, hashes SHA-256 válidos y listas de paths/dependencias sin duplicados.
- El STATE aceptado debe ser publicado por el `owner` de esa lease.
- Campos desconocidos, secretos, PII, UUID/SHA/repo incoherentes o timestamps futuros fallan cerrado.
- STATE no sustituye GitHub, HEALTH, checks, smoke, decisiones humanas ni el kill switch.

## Presence: no inventar señales

Una reserva y un STATE **no prueban un heartbeat ni la capacidad total de agentes**. Por eso este adapter no convierte `Issue.updated_at`, `PR.updated_at` ni `STATE.updated_at` en heartbeat.

Hasta que exista una señal explícita de heartbeat/capacidad, PresenceSnapshot sale con:

- `sessions=[]`;
- capacidad `known_slots=0`, `eligible_free_slots=0`, `degraded_slots=0`;
- `capacity.freshness=unknown`.

4C clasificará esa Presence como UNKNOWN/fail-closed. Esto es intencional: #769 puede alertar la ausencia de evidencia en lugar de fabricar GREEN.

## Freshness

La edad del marker de reserva usa el timestamp del comentario confiable. La freshness de STATE usa su propio `updated_at` y un threshold explícito suministrado por el caller. No hay defaults ocultos.

El módulo devuelve `READY` cuando STATE está correctamente ligado a una lease activa, aunque Presence siga UNKNOWN por falta de heartbeat; devuelve `UNKNOWN` cuando falta evidencia esperada o la lease está stale; y `BLOCKED` ante evidencia inválida/incoherente.

## Consumidores

- #769 lee GitHub, entrega snapshots a este parser y luego llama 4B/4C.
- #768 consume STATE/resumen una vez exista su runtime.
- Ningún consumidor puede reinterpretar UNKNOWN como ALLOW ni ampliar `authority=unchanged`.
