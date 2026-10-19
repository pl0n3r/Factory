# Performance classifier: metadata de release del productor

## Compatibilidad real · 19-oct-2026

Factory Performance v1 conserva sus ocho campos de envelope obligatorios. El
artefacto auténtico BRVTAL [Production Performance #39295316500](https://github.com/pl0n3r/brvtal/actions/runs/39295316500),
SHA \`46a801d54d3562cb4ac754e8bb84d69875caf4df\`,
release \`0.1.144\`, observación \`2026-10-19T17:35:28Z\`, agrega:

\`\`\`json
{"release_contract":{"design":"concept05","minimum_release":"0.1.137"}}
\`\`\`

El campo **opcional** se verifica con lista cerrada de dos nombres, diseño
identificador corto y versiones semánticas numéricas acotadas. Exige que
\`identity.release\` no preceda el mínimo declarado. Se rechazan campos
desconocidos, getters/datos no estructurados, tipos no esperados y valores
sobrelongitud sin registrar el valor secreto.

La metadata no forma parte del resultado de \`classify_performance_envelope\`
y **nunca** cambia baselines, budgets, severidad, freshness, autoridad de
clasificación, \`execute_actions=false\` ni \`create_work_item=false\`.
El detector sigue siendo \`performance.detector.detect_performance\`; los
envelopes históricos sin \`release_contract\` siguen funcionando.

## Evidencia y límites

En esta captura, FCP/LCP/CLS móvil 332/332/0 y desktop 396/396/0.03
están bajo budgets 1800/2500/0.1. El resultado esperado es 6 PERF_INFO
CURRENT y 4 PERF_REVIEW UNKNOWN sin incidente. El artefacto es evidencia
del productor, no autorización de remediación ni cierre del épico #304.

Validación offline: \`python3 -m unittest tests.test_performance_classifier\`
y \`python3 scripts/performance-classify.py --contract ... --envelope ...
--evaluated-at ...\`, con archivos confinados al checkout vía safe_io.

Revert de este patch deja de admitir el campo productivo, pero no cambia
el comportamiento legado. No mover Factory@v1, publicar, usar datos reales
ni activar entrega a consumidores como parte de este cambio.
