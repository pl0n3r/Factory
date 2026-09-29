# Portfolio Signals v1

#247 añade una vista **descriptiva** de trade-offs entre WorkItems que ya son elegibles. La prioridad del dueño sigue siendo la autoridad normativa. Portfolio Signals no decide qué trabajo ejecutar.

## Fuentes reutilizadas

- **#6 Product Feedback:** impacto técnico/producto declarado u observado.
- **#7 Cost Control:** tiempo/tokens/CI observados o estimados con confidence.
- **#161 Feedback Mesh:** outcomes, bloqueos, evidencia y provenance.
- ControlBot puede presentar estas dimensiones, pero no convertirlas en una decisión automática.

No existe un motor Portfolio paralelo.

## Dimensiones

Cada WorkItem declara por separado:

- dependencias desbloqueadas (`unlocks`);
- urgencia;
- riesgo;
- costo;
- impacto técnico/producto;
- reversibilidad.

Cada dimensión contiene:

- `status=known|unknown`;
- valor estructurado;
- `confidence`;
- `source=observed|estimated|declared`;
- `provenance`.

Cuando falta evidencia, el valor queda `unknown`, con confidence 0. No se sustituye por cero, ROI estimado ni valor inventado.

## Comparación

`explain_tradeoffs()` solo acepta WorkItems:

1. ya marcados como elegibles;
2. con la **misma prioridad del dueño**.

La salida ordena por identidad para ser determinista y expone cada dimensión lado a lado. Es **sin ranking**, score, winner o recomendación automática.

La respuesta conserva:

- `owner_priority_authoritative=true`;
- `decision=null`;
- `authority=owner_unchanged`;
- lista explícita de incertidumbres.

## Boundary

Este slice no cambia Dispatcher V2, Constitution, autoridad, prioridad, pagos, producto ni go-live. Tampoco crea scheduler, store, dashboard o runtime nuevo.

ControlBot puede explicar: “A desbloquea más dependencias pero tiene mayor riesgo y costo estimado; B tiene menor impacto técnico y alta reversibilidad”. La decisión sigue siendo humana o de la política normativa existente.
