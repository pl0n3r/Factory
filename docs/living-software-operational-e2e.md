# Living Software operacional — cierre E2E de #248

#341 materializa la Fase 5 de #248 sin crear un Engine nuevo. El escenario nace de una fricción operacional real observada mientras se despachaba #247 y usa únicamente evidencia fijada en `feedback/data/living-software-operational-e2e.json`.

## Observación autosugerida

El dueño pidió operacionalizar Living Software, pero no pidió la mejora concreta `reservation-readiness-preflight`. La candidata surge de cuatro ejecuciones reales de coordinación sobre #247:

1. run `36507015627`: failure porque el contrato de aceptación no tenía todavía la estructura canónica;
2. run `36507097760`: workflow success, pero sin reserva efectiva porque faltaba `estado: disponible`;
3. run `36507219161`: failure porque el trabajo no planificado no podía coexistir con #330;
4. tras agrupar las tres precondiciones como readiness bundle, run `36507269422`: success y reserva V3 concedida.

La hipótesis autosugerida es simple: **validar acceptance contract + available state + factory-plan-task antes de emitir `/tomar`**.

## Factory Lab + Fitness

La candidata se expresa dentro de `evolution_state.heuristics.*`, pasa Constitution y se evalúa en Factory Lab, modo shadow.

Fitness compara por separado:

- invariantes protegidos: security, privacy, traceability, reversibility y authority;
- segundos de coordinación;
- cantidad de intentos necesarios para obtener una reserva.

No existe score agregado. Los invariantes permanecen iguales y las dimensiones operativas mejoran. Shadow no permite mutación ni escrituras externas y conserva rollback `restore_baseline`.

La adopción demostrada es **acotada al escenario**: el bundle se usó para obtener la reserva válida de #247. No se modifica automáticamente `coordinar_trabajo.py` ni se declara todavía una regla universal.

## Resultado posterior real

Después del bundle:

`reserva #247 → PR #339 → CI verde → squash merge → main@7e9062203f3faae85a6dfc6fc9cb446d4faaf71e → CI/CodeQL exact-main verdes`

La ejecución útil de CI de PR #339 duró 29 s, según run `36507555400`.

## Complejidad organizacional #245

La comparación before/after usa el contrato existente de #245 y una única cohorte: el mismo procedimiento de readiness de #247.

- before: 7 s + 20 s + 8 s = **35 s** de coordinación improductiva;
- after: **27 s** para la reserva exitosa;
- ejecución útil común: **29 s** de CI;
- protected metrics: iguales antes/después.

Resultado esperado de `compare_simplification()`: Fitness `improved`, sin protected regressions, sin missing dimensions y con `authority=unchanged`.

Esto demuestra **reducción/no-regresión de complejidad organizacional** sin inventar ROI, costo monetario o score mágico.

## Ciclo final demostrado

`ejecución real → evidencia → observación → hipótesis autosugerida → candidato → Factory Lab → Fitness → adopción acotada → siguiente ejecución → medición before/after`

La evidencia posterior es PR #339 y su exact-main verde. La candidata puede generalizarse más adelante solo si acumula evidencia suficiente; este slice no convierte una observación local en política global.

## Boundary

- sin crear un Engine, scheduler, store o ranking;
- sin nueva authority;
- sin tocar dinero, legal, datos personales, borrado irreversible ni permisos externos;
- sin tocar #330;
- sin reescribir el coordinador;
- sin afirmar causalidad fuera del escenario #247.

Con #161 ya demostrando Feedback Mesh y #142/#242–#247 integrados, esta evidencia completa la demostración operacional exigida por #248: Factory observa su propia operación, propone una mejora no solicitada, la prueba bajo Constitution/Lab/Fitness, la usa dentro de authority existente y mide el resultado posterior.
