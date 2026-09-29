# Feedback Mesh E2E — evidencia real y rechazo seguro

Este slice cierra la demostración operativa de Factory #161: **no crear un motor nuevo** es una restricción explícita. Reutiliza Factory Queue/feedback (#269–#273), Review Efficiency (#163), Constitution/Evolution/Fitness/Factory Lab (#143/#149/#153), causalidad (#244), lifecycle (#243) y authority (#246).

## Escenario real

La cadena de evidencia queda anclada a artefactos existentes:

- Factory PR #253, merge `34409905f874b118b973ec316041467534fe2cd6`, aporta una cohorte real de revisión.
- GrindFlow PR #181 aporta evidencia real de review en HEAD `4a85df7dffb667a476afc3103c268e5f46f0e79a`. **Permanece open** y nunca se presenta como merge.
- Factory #163 / PR #256, merge `3d5752bd33cfae73380610e30c5f9de9740af11f`, materializa el experimento de eficiencia marginal.
- Factory PR #325 y #326 son ejecuciones posteriores reales; #326 llega a `main@3b99efa32ba4fe931f053f1023b34943fe63bf14` con CI exact-main run `36503410235` en success.

El manifiesto canónico está en `feedback/data/feedback-mesh-e2e.json`. No almacena comentarios de reviewers, PII, secretos ni payload libre.

## Loop demostrado

`ejecución real → evidencia → observación → hipótesis → candidato → Factory Lab → Fitness → rechazo → siguiente ejecución`

1. `metricas/datos/review-efficiency-baseline.jsonl` reproduce evidencia de Factory + consumidor sin mezclar cohortes incompatibles.
2. #163 formula la hipótesis de reducir rondas automáticas low-risk de 3 a 2.
3. Constitution limita el candidato al namespace evolutivo y exige rollback reversible.
4. Factory Lab ejecuta shadow sin escrituras externas.
5. Fitness conserva dimensiones protegidas y la incertidumbre explícita.
6. La muestra real disponible es insuficiente para cambiar política. El resultado correcto es `reject / insufficient_evidence`.
7. `review_round_limit=3` permanece estable.
8. PR #325/#326 demuestran ejecuciones posteriores reales bajo la política estable, sin afirmar una mejora causal inexistente.

## Authority y seguridad

El loop no concede permisos. `money`, `legal`, `personal_data` e `irreversible_delete` permanecen fuera de la authority ganable. El candidato solo puede tocar `evolution_state.*`, no Constitution ni permisos externos.

No hay scheduler, store, red, ranking paralelo, producción ni mutación de ControlBot/AutoFactory. El escenario se reproduce offline y falla cerrado si un ref declara un estado imposible, por ejemplo un PR `open` con `merge_sha` o un PR `merged` sin merge SHA.

## Resultado

#161 obtiene una demostración E2E real y trazable sin inventar causalidad: Factory observa evidencia, formula un candidato, lo evalúa y **rechaza** el cambio por evidencia insuficiente. El rechazo es aprendizaje válido y mantiene stable intacto.

Esto satisface la Fase 1 de #248 para Feedback Mesh. No satisface por sí solo la demostración final de #248 AC-09, que exige una mejora autosugerida, probada y medida posteriormente.
