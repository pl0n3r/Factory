# GrindFlow — Performance Contract v1 (evidencia acotada)

**Estado:** build-ahead; **NO** acredita latencia web, rendimiento de usuarios, ni producción GREEN.

## Baseline verificable

- Proyecto `grindflow`; `main@3c137b21654d30bc5ce123853e58934d973ce4b5`.
- [GrindFlow Production Smoke #38010129128](https://github.com/pl0n3r/GrindFlow/actions/runs/38010129128), job `production-smoke #114087986892`, `completed/success`.
- GitHub Actions Jobs REST: `started_at=2026-10-10T00:41:39Z` y `completed_at=2026-10-10T00:42:17Z`. Duración observada **38 s**; mide el **job completo**, no TTFB ni latencia de una ruta específica.
- Ventana de la muestra: **38 s**, igual al intervalo iniciado→completado del job; una única observación, no una tendencia ni 38 s de latencia web.
- Budget inicial de seguimiento: **≤120 s** por job completado. Es un umbral técnico provisional, **no un SLA comercial ni un RTO**. Una ejecución aislada no acredita percentiles ni tendencias.

## Superficies pendientes de medición

| Superficie | Estado de baseline | Razón |
| --- | --- | --- |
| Landing pública | UNKNOWN | No hay medición GET verificable de TTFB/tamaño/requests para esta ruta |
| Login | UNKNOWN | No hay medición GET verificable de TTFB/tamaño/requests; no hacer autenticación |
| Composer | UNKNOWN | Superficie autenticada; sin evidencia autorizada y reproducible |
| Library | UNKNOWN | Superficie autenticada; sin evidencia autorizada y reproducible |

El schema cerrado `performance/contract.schema.json` y `validate_performance_contract()` exigen `baseline.value` numérico; no permiten `UNKNOWN` como valor. Por eso estas cuatro superficies **no** se incorporan con números inventados, ni con cero como sustituto. La única métrica serializada es el job CI efectivamente medido; agregar rutas web requiere evidencia adicional real y una posterior actualización del contrato.

## Autoridad y reversión

Acciones permitidas: observar, diagnosticar, medir y preparar benchmarks; sin cambios de infraestructura, secretos, clientes, deploy, gasto o go-live. Ante ausencia de medición, resultado **UNKNOWN**; nunca asumir ausencia de degradación. Reversión: retirar este contrato y su test, sin efectos externos.

Fuente de alcance: [Factory #1085](https://github.com/pl0n3r/Factory/issues/1085), [Factory #304](https://github.com/pl0n3r/Factory/issues/304).
