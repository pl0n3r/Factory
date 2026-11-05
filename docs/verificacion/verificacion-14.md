# Factory #2030 — verificación lote 14/18

Corte: `main@7fbb24a0c59578db9070bda44d0a801eac60696a`, 5-nov-2026. Épico #304.
Reserva V3: `0ad9b964-f42a-4996-bf1d-92450e51db29`. PR de entrega: [#2056](https://github.com/pl0n3r/Factory/pull/2056); su estado de fusión se consulta en GitHub.

70/70 filas contrastadas, 0 SIN_COBERTURA originales y **0 promociones** de matriz.
Cada fila conserva NO_VERIFICABLE hasta la consolidación #2035; la evidencia local
no acredita producción, recuperación externa ni decisiones humanas. No se modifica
`docs/matriz-cobertura.md`. Este informe distingue prueba ejecutable y contrato documental.

## Corrección de interpretación y evidencia previa

- **Feedback:** el workflow `feedback-producto.yml` fue retirado por [PR #1304](https://github.com/pl0n3r/Factory/pull/1304), commit `2e20aef`; el motor `producto/feedback.py` y su CLI permanecen. **No hay consulta API ni publicación semanal acreditada**. Las menciones presentes en L30/L46/L47/L49 describen un contrato histórico; hoy solo se comprueban inputs locales, markers y archivos generados en un directorio temporal. La referencia al Job Summary no demuestra publicación vigente. Esta es la corrección del texto para las filas afectadas, sin reactivar triggers ni ampliar los claims.
- **Recuperación:** L41–L45 son instrucciones de respuesta humana. La presencia exacta del procedimiento y el rechazo de manifiestos inválidos se prueban; no hay prueba sintética capaz de demostrar rotación, expiración de un token real, restore externo o ejecución de CI/smoke/rollback. No se ejecutan esas operaciones.
- **Permisos:** `scripts/reusable_permission_compat.py` compara mapas. Prueba pura de precedencia/unanimidad; no descubre ni autentica los permisos reales de callers. L19 describe una obligación del adaptador, no una garantía del comparador aislado.
- **Rollback:** `scripts/release_auto_rollback_plan.py` exige historia correlacionada, produce `HUMAN_GATE_REQUIRED`, `authorizes_tag_move=false`, `mutations=0` y tres verificaciones posteriores. No lee un release semántico, no autentica GitHub, no mueve refs ni verifica recuperación/cierre reales. L10 y L56–L63 incluyen evidencia administrativa fuera del schema del plan.
- **Riesgo:** `intelligence/risk_compiler.py` sí conserva la dimensión `signals`; cambiar solo `production` de false a true la eleva de low a high con su fuente trazable.

Pruebas anteriores reutilizadas: `tests/test_cobertura_factory_52.py` ([PR #1930](https://github.com/pl0n3r/Factory/pull/1930)), `tests/test_cobertura_factory_54.py` ([PR #1917](https://github.com/pl0n3r/Factory/pull/1917)), `producto/test_feedback.py` y `tests/test_reusable_permission_compat.py`. Se ejecutan métodos concretos; se rechazan skips y fallos. Los tests nuevos añaden inventario, fronteras 99/100 muestras y 4/5 %, tabla completa de permisos y mutantes en memoria.

## Trazabilidad por fila

Todos los métodos abreviados pertenecen a `tests/test_verificacion_factory_14.py::VerificacionFactory14Tests`; el prefijo `test_` es literal. `test_inventario_y_anclas` verifica además la cláusula completa de cada ID en su línea fuente. Las filas documentales nunca equivalen a validación de operaciones externas.

| Fila exacta | Prueba exacta | Aserción y límite | Estado de matriz |
| --- | --- | --- | --- |
| `docs/resiliencia-fabrica.md:L41-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula íntegra presente; procedimiento humano, ejecución externa no acreditada | NO_VERIFICABLE |
| `docs/resiliencia-fabrica.md:L42-U1` | `test_manifiesto_sin_secretos_ni_prueba_externa` | Manifiesto válido no certifica hechos; mecanismo no-App, campos extra y evidencia vieja rechazados; expiración real no probada | NO_VERIFICABLE |
| `docs/resiliencia-fabrica.md:L42-U2` | `test_manifiesto_sin_secretos_ni_prueba_externa` | Manifiesto válido no certifica hechos; mecanismo no-App, campos extra y evidencia vieja rechazados; expiración real no probada | NO_VERIFICABLE |
| `docs/resiliencia-fabrica.md:L43-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula íntegra presente; procedimiento humano, ejecución externa no acreditada | NO_VERIFICABLE |
| `docs/resiliencia-fabrica.md:L44-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula íntegra presente; procedimiento humano, ejecución externa no acreditada | NO_VERIFICABLE |
| `docs/resiliencia-fabrica.md:L45-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula íntegra presente; procedimiento humano, ejecución externa no acreditada | NO_VERIFICABLE |
| `docs/resiliencia-fabrica.md:L62-U1` | `test_manifiesto_sin_secretos_ni_prueba_externa` | Manifiesto válido no certifica hechos; mecanismo no-App, campos extra y evidencia vieja rechazados; expiración real no probada | NO_VERIFICABLE |
| `docs/resiliencia-fabrica.md:L62-U2` | `test_manifiesto_sin_secretos_ni_prueba_externa` | Manifiesto válido no certifica hechos; mecanismo no-App, campos extra y evidencia vieja rechazados; expiración real no probada | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L9-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L10-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L11-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L12-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L13-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L14-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L15-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L16-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L18-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L18-U2` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L20-U1` | `test_feedback_esquema_cerrado` | Validador real acepta esquema exacto y rechaza identidad/tipo/campo extra inválidos; datos sintéticos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L30-U1` | `test_feedback_ventanas_markers_y_cli` | Marker ausente/discrepante rechazado; CORRECCIÓN: solo mapa local, workflow/API retirado por #1304 | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L34-U1` | `test_feedback_ventanas_markers_y_cli` | Solapes y varios p75 rechazados; score exacto solo ordena agregados sintéticos, no valor de negocio | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L34-U2` | `test_feedback_ventanas_markers_y_cli` | Solapes y varios p75 rechazados; score exacto solo ordena agregados sintéticos, no valor de negocio | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L34-U3` | `test_feedback_muestra_y_umbral_exactos` | 99 insuficiente/100 comparable; 4 % estable/5 % propuesta; fase ausente sin porcentaje ni propuesta | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L34-U4` | `test_feedback_ventanas_markers_y_cli` | Baseline cero: delta null/proposals vacías; fase ausente cubierta por test_feedback_muestra_y_umbral_exactos | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L36-U1` | `test_feedback_muestra_y_umbral_exactos` | 99 insuficiente/100 comparable; 4 % estable/5 % propuesta; fase ausente sin porcentaje ni propuesta | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L40-U1` | `test_feedback_ventanas_markers_y_cli` | Solapes y varios p75 rechazados; score exacto solo ordena agregados sintéticos, no valor de negocio | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L46-U1` | `test_feedback_ventanas_markers_y_cli` | CLI escribe JSON/Markdown y contenido esperado; CORRECCIÓN: sin publicación ni Job Summary acreditados | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L47-U1` | `test_feedback_ventanas_markers_y_cli` | CLI escribe JSON/Markdown y contenido esperado; CORRECCIÓN: sin publicación ni Job Summary acreditados | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L49-U1` | `test_feedback_ventanas_markers_y_cli` | Marker ausente/discrepante rechazado; CORRECCIÓN: solo mapa local, workflow/API retirado por #1304 | NO_VERIFICABLE |
| `docs/retroalimentacion-producto.md:L49-U2` | `test_feedback_ventanas_markers_y_cli` | Marker ausente/discrepante rechazado; CORRECCIÓN: solo mapa local, workflow/API retirado por #1304 | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L3-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L7-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L8-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L9-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L10-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L11-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L11-U2` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L17-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L19-U1` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-permission-compat.md:L19-U2` | `test_permisos_tabla_completa_y_unanimidad` | 9 pares de niveles, omisión none, mapas inválidos y un caller insuficiente bloquean; no autentica fuentes externas | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L9-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L10-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L11-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L12-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L13-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L19-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L19-U2` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L23-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L24-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L25-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L26-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L30-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L32-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L34-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L38-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L42-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L44-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L45-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L46-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L48-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L50-U1` | `test_rollback_plan_sin_autoridad` | Plan real exige historia por repo/workflow/SHA, no autoriza tags y requiere tres checks nuevos; no acredita rollback ejecutado | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L56-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L57-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L58-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L59-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L60-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L61-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L63-U1` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/reusable-release-rollback.md:L63-U2` | `test_runbooks_no_equivalen_a_ejecucion` | Cláusula administrativa íntegra; release, acta, cierre y seguimiento reales no acreditados por plan offline | NO_VERIFICABLE |
| `docs/risk-compiler.md:L12-U1` | `test_senal_operativa_eleva_dimension` | production false→true: signals low→high y trace incluye task.signals.production; no ejecuta controles | NO_VERIFICABLE |

## Validación y reversión

Comando: `python3 -m unittest tests.test_verificacion_factory_14 -v`.
Los mutantes sustituyen en memoria el umbral 5 % por 6 % y la unanimidad por aceptación
incondicional: las pruebas conductuales deben fallar con AssertionError, no por errores
de importación. El inventario rechaza eliminación, duplicado y promoción no autorizada.
`Tests de scripts`/`Validar` exact-HEAD se acreditan en el PR, nunca por este texto.
Riesgo bajo; revertir el squash restaura solo los dos archivos de esta hoja.
