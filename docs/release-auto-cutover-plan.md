# Plan de transición exact-SHA, no ejecutable (#1080 / #2095)

Este contrato puro correlaciona el candidato de `release_auto_candidate_preflight.py`, la evidencia de consumidores de `release_auto_consumer_gate.py` y el SHA publicado anteriormente. Es **un esquema de orden de controles**, no un ejecutor de release ni una aprobación de seguridad.

- Estado predeterminado `HOLD`: identidad, checks, origen, fase, consumidor, watchdog o recibos incompletos/sintéticos/ambiguos; sin pasos transferibles.
- `PLAN_ONLY`: únicamente un ejemplo estructural de cinco etapas cuando el caller *afirma* que existen recibos auténticos independientes. No autentica esas afirmaciones y jamás marca `authorizes_release=true`.
- La implementación real actual de `release_auto_consumer_gate.py` todavía devuelve `BLOCKED` por compatibilidad candidata y watchdog desconocidos; no puede alimentar el camino real hacia `PLAN_ONLY` hasta que existan verificadores externos autorizados.
- El voto de dirección de producto `#2075/A` autoriza desarrollar, **no** cambia las puertas de `factory-release`. La publicación real, el tag protegido `Factory@v1`, la ventana y el bootstrap siguen bajo la autoridad del OWNER según `docs/release-bootstrap.md`.
- En fase `live`, si cambia la maquinaria de release o si falta evidencia exact-SHA, el plan rechaza el avance sin intentar una escritura. La última etapa conserva explícitamente el SHA estable anterior para verificar un rollback externo.

Prueba aislada: `python3 -m unittest -v tests.test_release_auto_cutover_plan`. Los tres archivos son reversibles por `git revert` del squash. No hacen I/O ni crean workflows, permisos, tokens, releases, tags, descriptores de comandos o automatizaciones.
