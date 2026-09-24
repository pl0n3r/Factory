# Presupuestos de tareas y costo de CI

## Presupuesto por PR

El agente que abre un PR declara únicamente métricas numéricas y clasificación, nunca el contenido del prompt ni secretos:

```html
<!-- factory-cost {"task_type":"infraestructura","size":"medium","tokens":80000,"ci_minutes":40,"agent_minutes":120,"review_rounds":1} -->
```

`metricas/presupuestos.json` define presupuestos por tamaño y multiplicadores por tipo de tarea. Los topes globales de la fábrica son inmutables en este control: **10 commits** y **3 rondas de revisión**.

El evaluador deriva el número real de commits del evento de GitHub y la relación `Closes #N` del cuerpo del PR. Cada dimensión publica además su fuente: `observed` o `declared`. Mientras tokens, minutos de CI, minutos de agente o rondas solo estén autodeclarados, el resultado no puede presentarse como completamente verificado. Estados:

- `ok`: reservado para una evaluación completamente observada y por debajo de 80 %; con la telemetría actual no se emite a partir de datos autodeclarados;
- `warning`: al menos una dimensión está entre 80 % y 100 %;
- `soft-block`: falta medición o alguna dimensión supera 100 %.

El soft-block no fusiona ni gasta nada por sí mismo: aparece como warning y Job Summary para que el agente reduzca alcance, divida el cambio o documente el escalamiento técnico. Un marker malformado falla cerrado. Un PR dentro de límites pero con dimensiones solo declaradas permanece en `warning` con señales `unverified:*`; así no se confunde una estimación con costo observado.

Durante la **instalación inicial** del propio control, el job hace checkout de la base confiable del PR. Si esa base todavía no contiene `metricas/costos.py`, publica `bootstrap-not-enforced` y evidencia explícita en lugar de intentar ejecutar un archivo inexistente o informar un falso `ok`. Desde el primer merge que incorpora el control, todos los PR posteriores se evalúan usando el código confiable de su base.

## Tendencia de CI

La ejecución mensual de `.github/workflows/costos.yml` consulta las últimas corridas **completadas** de `ci.yml` disparadas por Pull Request, incluidas las exitosas, fallidas y canceladas. Suma la duración de todos los jobs por corrida y luego agrupa **todas las corridas del mismo PR**: la unidad de comparación es `ci_minutes_per_pr`, no una corrida aislada.

El reporte conserva `before_avg`, `after_avg`, `delta_pct`, `direction`, número de PRs (`samples`), número de corridas (`run_samples`) y conclusiones incluidas. Un `run_id` duplicado falla cerrado para evitar doble conteo. Con menos de cuatro PRs devuelve `insufficient-data`; no inventa una mejora ni oculta el costo de reintentos fallidos.

Los presupuestos iniciales son guardrails, no objetivos de gasto. #5 compara calidad/resultado; #7 controla consumo. La revisión mensual puede ajustar presupuestos o configuración cuando los datos lo justifiquen, sin intervención manual del dueño para recolectar métricas.
