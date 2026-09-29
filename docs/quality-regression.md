# Quality Regression Intelligence

#346 añade una capa acotada para convertir regresiones verificadas en evidencia reutilizable. No ejecuta fixes ni tests reales: valida observaciones deterministas, clasifica la evidencia y delega patrones repetidos al **Experience Guardrail Compiler** existente.

## Observation v1

Cada observación declara proyecto, superficie, signature, fuente GitHub, timestamps y dos muestras cerradas:

- `before`: cantidad de corridas, fallos, referencia de evidencia y timestamp;
- `after`: la misma forma para demostrar el estado posterior;
- `regression_test_ref`: referencia del test de regresión cuando existe;
- causa raíz y prevención necesarias para derivar una lesson válida.

Campos desconocidos, referencias inválidas, timestamps futuros/incoherentes, conteos imposibles y formas sensibles fallan cerrado. Los errores no reflejan secretos.

## Reproducible, FLAKY y PASS

Un fallo se considera reproducido únicamente cuando existe más de una corrida y todas fallan. Cualquier muestra con `0 < failures < runs`, sea `before` o `after`, se clasifica **FLAKY** y nunca puede convertirse en PASS.

Un fix solo queda verificado cuando:

1. el fallo `before` es reproducible;
2. `after` termina con cero fallos;
3. existe `regression_test_ref`;
4. la evidencia temporal y las referencias son válidas.

Solo en ese caso se genera una lesson compatible con `lecciones.memoria`. Una observación no verificada conserva evidencia diagnóstica, pero no produce material de guardrail.

## Reutilización de guardrails

Dos o más lessons verificadas, con fuentes GitHub distintas y el mismo patrón causal/preventivo, se entregan a `compile_guardrail_candidates()` del **Experience Guardrail Compiler**. Este módulo solo expone el candidato retornado por ese contrato: **no promueve** candidatos a política estable.

No se crea un Immune/Guardrail Engine paralelo, no hay scheduler, backlog, Issues automáticos ni ejecución de remediaciones.

## Límites del slice

- Quality Health y proyección a **Readiness #293** pertenecen a #347.
- Clasificación/corrección operativa mediante **Queue #269** pertenece a #347 y contratos existentes.
- El E2E transversal pertenece a #348.
- Este módulo no modifica Performance ni Recovery.
- No existe autoridad para ejecutar fixes, promover políticas o declarar producción sana.
