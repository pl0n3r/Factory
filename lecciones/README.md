# Lecciones de la fábrica

Cada línea de `registros/*.jsonl` conserva una lección demostrada, no una hipótesis. El formato obliga a responder en forma compacta:

- **what**: qué pasó;
- **why**: por qué ocurrió;
- **prevention**: cómo evitar que se repita;
- **source**: Issue/PR que aporta evidencia.

La herramienta falla cerrado ante campos extra, duplicados, timestamps sin zona horaria, symlinks, archivos excesivos o textos demasiado largos; los lectores procesan línea a línea para mantener el uso de memoria acotado. El CLI no acepta rutas de lectura/escritura: usa exclusivamente `lecciones/registros` y `metricas/datos/tareas.jsonl`, y entrega su salida por stdout para evitar path injection.

## Contexto rápido por proyecto

```bash
PYTHONPATH=lecciones python3 lecciones/memoria.py summary \
  --project pl0n3r/factory > /tmp/factory-context.md
```

Por defecto entrega como máximo 5 lecciones y 3000 caracteres. No mezcla proyectos.

## Medir el costo de bootstrap

La reducción de tokens no se estima a partir de caracteres. Se mide con `tokens_input` reportados por la telemetría de #5 para tareas `agent-bootstrap`:

```bash
PYTHONPATH=lecciones python3 lecciones/memoria.py compare-tokens \
  --change-at 2026-10-01T00:00:00Z \
  --project pl0n3r/factory > /tmp/bootstrap-tokens.json
```

Se requieren al menos dos muestras reales antes y después **del mismo proyecto**; de lo contrario el resultado es `insufficient-data`. Para tareas `agent-bootstrap`, `task_id` debe usar `owner/repo#N`; una identidad ambigua falla cerrado. El JSON conserva `project`, `task_type` y el corte UTC normalizado para auditar la comparación.
