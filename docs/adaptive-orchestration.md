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
