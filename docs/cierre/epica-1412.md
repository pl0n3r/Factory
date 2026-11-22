# Cierre documentado de Factory #1412 — evidencia sin aceptación inventada

**Corte:** 2026-11-22 · **Hoja de cierre:** [#2183](https://github.com/pl0n3r/Factory/issues/2183) · **Épica:** [#1412](https://github.com/pl0n3r/Factory/issues/1412) · **Estado:** cierre técnico del fix acreditado; cierre de la épica **NO-GO** mientras AC-04 esté pendiente.

## Alcance entregado, sin duplicación

- [Hoja #1413](https://github.com/pl0n3r/Factory/issues/1413): **CLOSED / estado: completado**.
- [PR #1414](https://github.com/pl0n3r/Factory/pull/1414): **MERGED** el 2026-10-19 23:36:17 UTC; HEAD final `5abe3eaefb4b466ae9052909ada327331abf71e6`; squash `67994aafbb5d2ce0e802dcb65a3dd1b1d46bd425`.
- [Comparación squash→main](https://github.com/pl0n3r/Factory/compare/67994aafbb5d2ce0e802dcb65a3dd1b1d46bd425...main): el squash es ancestro de `main` (consulta autenticada: `behind_by=0`). El PR modificó exclusivamente `scripts/coordinar_trabajo.py`, `tests/test_coordinar_trabajo.py` y `docs/orquestador.md`.
- Al realizar esta conciliación, `Factory/main@dd4debfccfae7f9954d3931e44946c4bd8d99970` está protegido; `Factory@v1` apunta al mismo SHA y `config/version.json@v1` declara `1.0.58`. Esta constatación de distribución **no** autoriza volver a publicar, mover `v1` o ejecutar acciones productivas.

## Matriz de aceptación #1412

| Criterio del padre | Evidencia comprobable | Resultado |
| --- | --- | --- |
| **AC-01** Roadmap parcial V3 válido conserva padre abierto | `CoordinacionTests.test_planned_partial_roadmap_merged_keeps_issue_open_and_uncompleted` en [tests/test_coordinar_trabajo.py](https://github.com/pl0n3r/Factory/blob/main/tests/test_coordinar_trabajo.py); [PR #1414 fusionado](https://github.com/pl0n3r/Factory/pull/1414); [Criterios de aceptación en SHA exacto](https://github.com/pl0n3r/Factory/actions/runs/39340446003/job/118360667323) `completed/success` | **CUBIERTO** (implementación/pruebas) |
| **AC-02** PR normal, no-merge y replay conservan semántica | `test_planned_partial_roadmap_normal_and_unmerged_behaviors` y `test_planned_partial_roadmap_replay_repairs_interrupted_cleanup` en la misma suite; [Tests de scripts](https://github.com/pl0n3r/Factory/actions/runs/39340446003/job/118360357590) `completed/success` sobre `5abe3eae...` | **CUBIERTO** |
| **AC-03** Falsificación, identidad y carreras fallan cerrado | `test_planned_partial_roadmap_forged_and_stale_authority_fail_closed`, `test_planned_partial_roadmap_delete_requires_cas_exact_sha` y regresiones de replay en la misma suite; [Validar coordinación](https://github.com/pl0n3r/Factory/actions/runs/39340446003/job/118360437465) `completed/success` | **CUBIERTO** |
| **AC-04** Tests/Validar/CodeQL/Sonar **y CodeRabbit FINAL exact-SHA antes de squash**; release @v1 con puerta propia | [Validar](https://github.com/pl0n3r/Factory/actions/runs/39340446003/job/118360730932), [Tests de scripts](https://github.com/pl0n3r/Factory/actions/runs/39340446003/job/118360357590), [CodeQL](https://github.com/pl0n3r/Factory/runs/118357648535) y [SonarCloud](https://sonarcloud.io/dashboard?id=pl0n3r_factory&pullRequest=1414) `completed/success` sobre HEAD final; revisión sustantiva de CodeRabbit **solo** en SHA anterior `14d0ce797926d6ffd5046ba627d1557da0e505d3` y [respuesta posterior](https://github.com/pl0n3r/Factory/pull/1414#issuecomment-6279560486) **“Review skipped: incremental reviews are disabled”** para el SHA final | **NO VERIFICABLE / PENDIENTE** — no existió revisión FINAL demostrada en el SHA definitivo antes de merge |

Los jobs de CI enumerados proceden de los **check-runs históricos del HEAD exacto** `5abe3eaefb4b466ae9052909ada327331abf71e6` y no de una ejecución local de esta hoja documental. Que el status de CodeRabbit sea `success` no certifica que haya revisado ese HEAD. El motivo `skipped` **no es** rate-limit auténtico y no satisface la excepción D-070. Una auditoría posterior tampoco puede retroceder la fecha de un control previo al squash.

## Trabajo faltante materializado

[Hoja #2185](https://github.com/pl0n3r/Factory/issues/2185) — auditoría independiente de AC-04 **bloqueada** a una **autorización explícita, específica y autenticada del OWNER** en #1412 para sustituir formalmente la obligación histórica por una auditoría posterior. Ninguna orden genérica de fusionar #2183 constituye esa autorización.

Con autorización, la hoja exige identidad del revisor, fecha, SHAs histórico y squash, comparación del delta de los **tres** archivos originales, identidad de blobs actualmente distribuidos, hallazgos clasificados por gravedad, mitigaciones y aceptación expresa del OWNER. Sin ella, mantener `AC-04 [ ]` y #1412 `OPEN / estado: bloqueado`, sin pedir otra revisión CodeRabbit al PR cerrado.

## Resultado y límites

Este documento **cumple el propósito de #2183** de mapear evidencias y materializar la brecha sin cambiar el significado de la aceptación original; el cierre de #1412 **no** está autorizado todavía. La hoja no altera workflows, releases, claims V3 ajenos, secretos, producción ni datos reales. Reversión del documento: revertir su PR documental; no modifica la entrega técnica ya fusionada.
