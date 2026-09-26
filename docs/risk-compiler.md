# Risk Compiler v1

Risk Compiler transforma señales explícitas de la tarea y Project DNA en un
contrato de riesgo trazable. No ejecuta controles ni sustituye puertas humanas.

## Salida

El contrato conserva dimensiones independientes:

- cambio;
- superficie;
- señales operativas;
- contexto del proyecto.

El riesgo global es el máximo conservador de esas dimensiones: `low`,
`medium` o `high`. No se usa una media que pueda esconder una dimensión
peligrosa.

## Blast radius y trazabilidad

Cada señal conserva:

- `signal`: qué se observó;
- `source`: de dónde vino;
- `risk`: nivel aportado;
- `reason`: por qué afecta riesgo.

El blast radius se deriva de las señales medium/high. Cada control requerido
conserva las fuentes que justifican el contrato, permitiendo reconstruir
señal → riesgo → control.

## Controles monotónicos

Los controles son acumulativos:

- low: CI, revisión sin hallazgos y scope reclamado;
- medium: todo low + tests del cambio + rollback plan;
- high: todo medium + full suite + security scan + smoke exact-SHA +
  completar contexto antes de promoción.

Por construcción, aumentar riesgo nunca elimina controles.

## Fail-safe

Las señales críticas `production`, `destructive`, `migration` y
`touches_auth` aceptan `unknown` como incertidumbre explícita. Un unknown
crítico eleva el contrato a `high`, queda listado en
`unknown_critical_signals` y marca `context_complete=false`.

Project DNA también puede volver crítica una ausencia contextual: por ejemplo,
hosting desconocido para release/web/api o data desconocido para una superficie
de base de datos. La ausencia nunca reduce el estándar.

## Fuera de alcance

Risk Compiler no ejecuta tests, backups, scans, deploys ni puertas humanas.
Tampoco concede permisos o autoridad.
