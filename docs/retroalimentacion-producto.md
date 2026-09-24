# Retroalimentación de producto real

Factory define un contrato común para que Condor, GrindFlow y BRVTAL puedan reportar resultados de producto sin enviar datos personales. El objetivo es conectar uso, errores, conversión, Core Web Vitals y SEO con la priorización semanal.

## Contrato sin PII

Cada línea JSONL contiene exactamente:

- `project`: `owner/repo`;
- `epic`: `owner/repo#N`, del mismo proyecto;
- `metric`: identificador del catálogo `producto/metricas.json`;
- `surface`: slug de taxonomía de producto, por ejemplo `home` o `checkout`;
- `phase`: `baseline` o `post-deploy`;
- `period_start` / `period_end`: ISO-8601 con zona horaria;
- `value`: agregado numérico;
- `sample_size`: cantidad agregada usada para ponderar.

No se permiten campos adicionales. En particular el contrato no tiene nombre, email, teléfono, IP, user/session ID, query string, URL libre, payload de error ni texto de usuario. `surface` es un slug controlado por el producto y no debe contener identificadores dinámicos.

Las métricas iniciales cubren las cinco familias obligatorias: `usage`, `error`, `conversion`, `cwv` y `seo`.

## Épicos orientados a métricas

Antes de implementar un épico de producto, su Issue declara la métrica que intenta mover:

```html
<!-- factory-product-metric {"metric":"conversion_rate","surface":"checkout","target_improvement_pct":10} -->
```

El marker no contiene la dirección porque se deriva del catálogo. El reporte semanal **debe resolver el Issue real de cada épico observado**, parsear ese marker y rechazar telemetría cuya `metric` o `surface` no coincida. El resultado y cualquier propuesta conservan también `target_improvement_pct`; así el mismo Issue enlaza objetivo y resultado observable.

## Comparación y prioridad

Factory usa promedio ponderado por `sample_size` para métricas donde esa operación es válida. Las métricas con unidad `count` son totales de ventana y se normalizan como **tasa por día**: suma de counts / suma de días observados. Esto evita comparar falsamente una ventana de 14 días con una de 7 días como si fueran equivalentes. Las ventanas dentro de una fase no pueden solaparse y baseline debe terminar antes de post-deploy. Para Core Web Vitals p75 se exige **un único agregado por fase**: Factory no promedia percentiles ya calculados, porque eso no reconstruye el percentil de la población. Por defecto se requieren al menos 100 muestras por fase. Sin ambas fases, con muestra insuficiente o baseline igual a cero, no se calcula una regresión porcentual ni se propone un Issue.

Una variación adversa de al menos 5% entra a `proposals`. El `impact_score` es una heurística auditable:

`regression_pct × min(4, log10(post_deploy_samples + 1))`

Sirve únicamente para ordenar evidencia comparable. No pretende medir ingresos, severidad legal ni valor de negocio.

## Reporte semanal

`.github/workflows/feedback-producto.yml` ejecuta la suite en PR y, cada lunes o bajo demanda, procesa `producto/datos/*.jsonl`. Publica:

- `artifacts/reporte-producto.json`: resultados y propuestas máquina;
- `artifacts/reporte-producto.md`: tablero humano y Job Summary.

El workflow primero obtiene la lista validada de épicos presentes en la telemetría, consulta solo esos Issues vía API y construye un mapa efímero de bodies. El paso de análisis usa ese mapa sin recibir token de GitHub. Si un Issue falta, no tiene marker o declara otra métrica/surface, la corrida falla cerrado.

Con cero datos la corrida es válida y declara que no existen propuestas. Factory no crea Issues automáticamente hasta que los proyectos adopten el contrato y aporten telemetría observada suficiente; el reporte semanal propone candidatos reproducibles sin fabricar datos.
