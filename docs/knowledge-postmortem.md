# Knowledge Operations — Postmortem v1

#320 estructura postmortems verificables sin crear un Knowledge Engine, store o scheduler.

## Contrato

Un postmortem enlaza un `knowledge_item` clase `postmortem` y declara incidente, tiempo, impacto, detección, recuperación, timeline, factores, acciones, root cause y evidencia.

- `root_cause.status=known` exige resumen causal, evidencia verificable y prevención explícita.
- `root_cause.status=unknown` exige `summary=null` y cero evidencia causal. Factory conserva el unknown; no inventa causa raíz.
- Texto libre es acotado y rechaza formas comunes de secretos/PII.
- La salida fija `authority: unchanged`, `execute_actions: false` y `emit_work_items: false`.

## Guardrail input

`guardrail_lesson_input()` devuelve una lección validada por `lecciones.memoria.validate_lesson` solo para una causa conocida/verificada. Ese artefacto puede alimentar después `experience_guardrails`; #320 no compila, promueve ni instala guardrails.

## Boundary

- #319: Knowledge Item Contract/Lifecycle.
- #320: postmortem verificable → lesson candidate.
- #321: selección scoped para Context Compiler.
- #322: E2E lifecycle/context/pruning/guardrails.

No existe scheduler/backlog paralelo, no se crean WorkItems ni se ejecutan fixes. README sigue siendo portada derivada; el conocimiento profundo vive fuera de README.
