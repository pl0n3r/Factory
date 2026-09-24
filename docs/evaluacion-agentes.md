# Evaluación continua de agentes, modelos y prompts

## Contrato de datos

Cada tarea cerrada aporta una línea JSONL al conjunto de métricas. El registro identifica la tarea, su tipo y la configuración usada (`agent`, `model`, `prompt_id`, `roles`) y mide resultado, commits, rondas de revisión, retrabajo, incidentes posteriores, tokens y tiempos cuando estén disponibles.

Campos obligatorios:

`task_id`, `task_type`, `agent`, `model`, `prompt_id`, `roles`, `success`, `merged_first_try`, `commits`, `review_rounds`, `rework_commits`, `incidents_after`, `completed_at`.

Campos opcionales: `tokens_input`, `tokens_output`, `ci_minutes`, `agent_minutes`.

El validador rechaza campos desconocidos, duplicados por `task_id`, números negativos, timestamps sin zona horaria y más de tres rondas de revisión. No imprime el payload rechazado.

## Ranking

La comparación se hace **dentro de cada tipo de tarea**. Una configuración solo entra al ranking al alcanzar la muestra mínima. El orden es determinista y prioriza, en este orden:

1. mayor tasa de éxito;
2. menos incidentes posteriores por tarea;
3. mayor tasa de integración a la primera;
4. menos commits de retrabajo;
5. menos rondas de revisión;
6. menos tokens cuando el dato existe.

Solo se publica una recomendación cuando existen al menos dos configuraciones comparables con muestra suficiente **y una diferencia medida**. Un empate exacto conserva orden determinista pero no fabrica ganador. Tokens solo desempatan cuando todas las tareas de las configuraciones empatadas tienen `tokens_input` y `tokens_output`; telemetría parcial queda como `tokens_avg: null` y no se interpreta como costo cero. Cada fila expone `sample_status: eligible|insufficient_data`.

## Operación mensual

`.github/workflows/metricas.yml` valida el motor y evalúa **el mes UTC anterior completo** en la corrida programada; una ejecución manual puede fijar `month=YYYY-MM`. Los límites son inclusivo al inicio y exclusivo al inicio del mes siguiente, normalizando `completed_at` a UTC. El periodo evaluado queda escrito en JSON y Markdown.

El CLI del workflow lee únicamente `metricas/datos/*.jsonl` y escribe únicamente en `artifacts/`; no acepta rutas arbitrarias. Rechaza symlinks, archivos/líneas excesivos y entradas no UTF-8 antes de agregarlas. El workflow publica `dashboard.md` en el Job Summary y conserva `dashboard.md` + `recomendaciones.json` como artifact. El contenido comparable no incluye timestamps de generación, por lo que la misma entrada y periodo producen la misma salida. Con cero datos del periodo la corrida sigue siendo válida pero **no recomienda** ninguna configuración. El histórico acumulado sigue disponible omitiendo `--month` al ejecutar la herramienta directamente; las rutas de entrada/salida siguen siendo las canónicas del repositorio.

Los proyectos que adopten el kit deben producir registros con este contrato de forma automática al cerrar una tarea; el dueño no carga datos manualmente. El ajuste de modelo/prompt se decide a partir del reporte mensual: esta automatización mide y recomienda, pero no cambia configuraciones de agentes por sí sola.
