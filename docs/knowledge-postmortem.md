# Knowledge Operations — Postmortem v1

#320 estructura postmortems verificables sin crear un Knowledge Engine, un store ni un scheduler.

## Contrato

El postmortem contiene un `knowledge_item` clase `postmortem` ya validado por Knowledge Item Contract v1 y agrega:

- referencia del incidente y `occurred_at`;
- impacto, detección y recuperación;
- timeline acotado con evidencia;
- factores contribuyentes y acciones;
- `root_cause.status = known|unknown`;
- prevención candidata y referencias de evidencia.

La causa **known** exige resumen causal, evidencia verificable y prevención explícita. La causa **unknown** exige `summary=null` y cero evidencia causal: Factory no rellena huecos con inferencias.

## Guardrail input

`guardrail_lesson_input()` produce una lección canónica compatible con `lecciones.memoria.validate_lesson` únicamente cuando la causa es conocida y verificable. Ese artefacto puede alimentar posteriormente `experience_guardrails`; esta capa no compila, promueve ni instala guardrails.

Un postmortem con causa unknown devuelve `None` como lesson input. Conservar el unknown es preferible a inventar root cause.

## Seguridad y autoridad

Texto libre se limita y rechaza formas comunes de secretos/PII. Las referencias son opacas y acotadas. La salida fija:

- `authority: unchanged`;
- `execute_actions: false`;
- `emit_work_items: false`.

El contrato no ejecuta fixes, no crea WorkItems y no modifica autonomía.

## Boundary

- #319: Knowledge Item Contract/Lifecycle.
- #320: postmortem verificable → lesson candidate.
- #321: selección scoped para Context Compiler.
- #322: E2E lifecycle/context/pruning/guardrails.

No existe scheduler/backlog paralelo; README sigue siendo portada derivada y el conocimiento profundo vive en documentación/artefactos canónicos.
