# Diagnóstico conservador de suite CI FactoryRunner — Factory #1501

## Objetivo y límite operativo

El contrato `performance/contracts/factoryrunner.json` sigue fijando el presupuesto real de `ci.workflow/workflow_elapsed` en **≤120 s** y `allowed_actions=[observe, diagnose, benchmark]`. El adaptador `performance/github_actions_ci.py` clasifica la ejecución completa. `performance/ci_suite_benchmark.py` solo mide el resumen de `unittest` dentro del log autenticado de un job; **no** reprograma workflows, toca el consumidor, crea WorkItems, concede acciones, cambia límites ni afirma que se ejecutó una reparación.

El caller autorizado lee GitHub Actions por GET autenticado para un run y job **exactos**, verifica `event=push`, `branch=main`, repositorio y SHA, obtiene el log íntegro y pasa su texto al parser. Esta función **no autentica el origen**: validaciones de forma no sustituyen el transporte ni un sello de fuente, y cualquier valor posterior permanece informativo. El parser solo extrae `Ran N tests in X.XXXs` seguido de un `OK` inequívoco, aplica límites de 256 KB y 4000 líneas y no copia contenido del log al resultado ni al mensaje de error.

## Evidencia observada

| Corrida CI push/main | SHA | Tests Python | Duración suite | Duración workflow |
| --- | --- | ---: | ---: | ---: |
| [#40029930158](https://github.com/pl0n3r/FactoryRunner/actions/runs/40029930158) | `789a312d7520e9813835f99d8c4e5de5ee22cb2a` | 615 | 152,868 s | 182 s |
| [#40119747013](https://github.com/pl0n3r/FactoryRunner/actions/runs/40119747013) | `33277d549a82e9cba5371982d1d80e43e06bd0d5` | 616 | 104,376 s | 130 s |

La diferencia visible de 48,492 s en el tiempo Python **no se adopta**: las suites contienen distinto número de tests, cambiaron el SHA y las condiciones de runner no son equivalentes. El comparador devuelve `NO_COMPARABLE` y `duration_delta_ms=null`. Aun con el mismo recuento de tests el resultado sería `COMPARABLE_DIAGNOSTIC`, no evidencia causal: `sample_pairs=1`, `causality=unproven`, `adopt=false`, `authority=unchanged`, sin WorkItem ni ejecución.

## Pruebas y siguiente tramo

`python3 -m unittest tests.test_performance_ci_suite_benchmark -v`

Las cuatro pruebas verifican extracción limitada, escenarios negativos, no comparabilidad de dos runs auténticos y delta sintético solo informativo. Una investigación de causa raíz necesita perfil individual de test/subprocess, muestras de runner y un fix en **FactoryRunner** con hoja, aceptación, V3, CI exact-HEAD y permiso de ese repositorio. Después se requieren nuevas mediciones reales antes/después, decisión `ADOPT/REVERT` y estado Readiness; **Factory #304 AC-11 permanece pendiente** hasta ese E2E. No alterar presupuesto, baseline, rollout ni producción para volver verde un indicador.

### Rollback

Revert del squash de #1501; no hay migración, datos, cron ni efectos externos.
