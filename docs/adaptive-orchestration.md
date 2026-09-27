# Adaptive Orchestration

## Presence Contract v1

Factory consume snapshots autoritativos de presencia y capacidad para decidir si
puede continuar, paralelizar o debe fallar cerrado. **ControlBot**, o el runtime
externo expresamente designado por el contrato, es la **fuente autoritativa** de
Sessions, heartbeats y capacidad. Factory consume snapshots; **no persiste
Sessions** ni mantiene una base de presencia paralela.

El contrato v1 es puro y determinista. Cada snapshot incluye versión, fuente,
instante observado, Sessions y capacidad agregada. Una Session solo cuenta como
activa cuando su freshness es `fresh`, tiene `heartbeat_at` explícito y está
en un estado activo permitido. Freshness `stale` o `unknown`, heartbeat
ausente o capacidad no fresca nunca se interpretan como healthy/free.

La evaluación produce señales compatibles, no un enum excluyente. Por ejemplo,
dos Sessions activas con un slot elegible libre producen `multi +
idle_capacity`. Sin slots elegibles conocidos se añade `saturated`; si hay
capacidad o Sessions degradadas se añade `degraded`. Ante evidencia
insuficiente o freshness desconocida, el resultado es `unknown`.

## Límites del slice

Presence Contract v1 no consulta ControlBot, no hace red, no persiste runtime,
no replanifica, no implementa cooldown/generation fencing y no modifica
Dispatcher V2. Los siguientes slices del épico #260 consumen este contrato en
ese orden para evitar una jerarquía de coordinación paralela.

## Replan Contract v1

Factory consume eventos tipados y el Presence Contract v1 para decidir de forma
pura entre `keep`, `replan` y `fail_closed`. Eventos equivalentes se
coalescen por fingerprint; health/incident válidos fuerzan replan inmediato,
mientras señales `unknown` o `stale` fallan cerrado. La continuidad del
trabajo activo se conserva cuando sigue seguro y ready.

## Fencing Contract v1

Cada evento que atraviesa el fence se envuelve con `generation` y `attempt`
del propietario vigente. El fence exige coincidencia exacta antes de consultar
el motor de replan: generaciones o intentos anteriores/futuros fallan cerrado y
no alteran el intento actual. Envelopes equivalentes se coalescen y producen un
fingerprint estable independiente del orden de entrada.

El cooldown se expresa como duración y tiempo transcurrido, sin reloj interno ni
estado persistido. Solo retiene replans no críticos; health/incident válidos
pueden bypassarlo, pero siguen sujetos a authority/readiness explícitos. Un
`replan` no equivale a preemption: `pause_allowed` solo es true cuando el
trabajo es `preemptible` y está en `safe_point`.

### Límites de fencing

Este slice no pausa ni migra trabajo, no ejecuta órdenes, no persiste
generation/cooldown, no llama a ControlBot y no reimplementa Dispatcher V2. El
siguiente E2E del épico #260 debe componer Presence → Replan → Fencing usando
estos contratos puros.
