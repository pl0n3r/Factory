# Memoria institucional de Factory

## Objetivo

El bootstrap no debe reconstruir incidentes ni decisiones leyendo conversaciones largas. `lecciones/` conserva únicamente fallos/retrabajos demostrados y genera un resumen acotado por proyecto. La telemetría de #5 permite medir si ese contexto reduce tokens reales de entrada.

## Flujo de mantenimiento

1. Al cerrar un incidente o un PR con retrabajo material, agregar una lección con fuente verificable.
2. Registrar solo causa confirmada y prevención ejecutable; nunca secretos, PII ni conjeturas.
3. Antes de trabajar en un proyecto, generar/leer su contexto acotado junto con las decisiones vigentes. Si una lección reciente no cabe en el límite, el generador sigue buscando una anterior más corta en vez de declarar memoria vacía.
4. Medir tareas de bootstrap con `task_type=agent-bootstrap`, `task_id=owner/repo#N` y comparar tokens before/after con un corte temporal explícito **por proyecto**; nunca mezclar repositorios.

## Integración de #8

El slice implementa `lecciones/`, validación, contexto por proyecto y medición de tokens. Factory ya incorpora en `main` el `decisiones.yml` raíz, la lectura de `decisiones.yml` + `lecciones/` desde el núcleo común y la ejecución de la suite `lecciones/` dentro de `Tests de scripts`. Por eso la memoria queda integrada sin duplicar fuentes de verdad.

La reducción de tokens o incidentes **no se presume**: mientras no existan muestras reales before/after suficientes, la evidencia correcta es `insufficient-data`.

## Seguridad del CLI

Las rutas son canónicas y no provienen de argumentos: lecciones desde `lecciones/registros`, telemetría desde `metricas/datos/tareas.jsonl`. La salida va a stdout para que el consumidor decida si la muestra, la redirige o la integra al bootstrap, sin que Python escriba rutas aportadas por el usuario.
