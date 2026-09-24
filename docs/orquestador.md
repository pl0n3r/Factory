# Orquestador único de la fábrica

Factory convierte un épico estructurado en un DAG de Issues ejecutables antes de que dos agentes empiecen a trabajar.

## Contrato del épico

El Issue épico declara un único marker factory-plan con version=1 y una lista tasks.
Cada tarea exige key, title, owner, paths y depends_on.

- key: identificador estable.
- title: una línea.
- owner: login GitHub responsable.
- paths: archivos exactos o prefijos de directorio terminados en /; no acepta glob, traversal ni rutas absolutas.
- depends_on: keys del mismo plan.

Los roles no se escriben a mano: se derivan del clasificador profesional de #2 usando título, tipo del épico y paths.

## /planificar

Un actor OWNER, MEMBER o COLLABORATOR comenta /planificar en el épico.

El workflow valida esquema, límites y DAG; rechaza ciclos; detecta claims de paths solapados; crea o actualiza Issues hijos idempotentes; asigna owner, roles y etiquetas; materializa dependencias como números de Issue; y publica un grafo + tabla de ejecución en un único comentario del bot.

Si dos tareas reclaman rutas solapadas, el plan solo es válido cuando una depende transitivamente de la otra. Una tarea ya activa no puede cambiar su marker y una tarea materializada no puede desaparecer del plan.

## Enforcement antes de /tomar

Cada Issue hijo lleva un marker factory-plan-task. El coordinador lo lee antes de crear o recuperar una reserva:

- el actor debe coincidir con el owner planificado;
- todas las dependencias deben estar cerradas;
- ninguna otra tarea planificada en estado reservado, revisión o recuperación puede reclamar un path solapado, incluso si pertenece a otro épico.

Los Issues históricos sin marker siguen usando el flujo normal. El validador de PR conserva su detección de colisiones exactas como segunda barrera.

## Garantía verificable

Una tarea planificada no entra a /tomar si una dependencia o claim de archivos la hace incompatible con trabajo activo. El objetivo es prevenir la colisión antes de escribir código, no descubrirla al final del PR.
