# Auditoría A2: dispatcher de Factory, funcionamiento real

> Corte verificable: 2026-11-12, `Factory/main@3239737cd040b222786f9d9003cbc92bbfb96231`. Issue [#2123](https://github.com/pl0n3r/Factory/issues/2123), épica [#2121](https://github.com/pl0n3r/Factory/issues/2121). Rol: infraestructura + SRE. Esta auditoría NO acredita autonomía de Factory, ControlBot, FactoryRunner ni Qwen.

## Dictamen resumido

**Resultado: PARCIAL en selección determinista y mecanismos de coordinación; NO DEMOSTRADO para despacho autónomo de un agente real y continuidad entre tareas.** Hay Python de selección, pruebas y workflows periódicos de observación/mantenimiento, pero no se halló una conexión verificable entre un disparador periódico, inventario de candidatos de los siete repositorios, el selector, `/tomar`, un ejecutor real y el siguiente trabajo. Los verdes de GitHub Actions son verdes de **sus propios jobs**, no prueba de esa cadena.

Se inspeccionaron individualmente las **36 definiciones** de `.github/workflows/*.yml` del mismo SHA. **Ninguna invoca directamente** `scripts/dispatcher_v2.py`, `select_next(`, `dispatch_record(` ni `parallel_ready(`. No se interpreta esta búsqueda negativa como prueba de inexistencia de ejecutores externos, sino como ausencia de cableado directo en los workflows de Factory examinados. `scripts/dispatcher_v2.py` define funciones y no ofrece un `__main__`/CLI que despache candidatos por sí mismo.

## Fuentes y método

- [Selector exact-SHA](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/scripts/dispatcher_v2.py): `AUTHORITY_ORDER` y repos canónicos (inicio), `classify_readiness` (L658), `select_next` (L799), `select_next_action` (L924), `parallel_ready` (L1799), `dispatch_record` (L1830) y `adaptive_dispatch_record` (final).
- [Pruebas sintéticas](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/tests/test_dispatcher_v2.py): comprueban funciones de selección con candidatos construidos en memoria; no son un recibo de ejecución de agentes ni cuatro workers reales.
- [Orquestador de fábrica](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/.github/workflows/orquestador.yml): únicamente `issue_comment` con `/planificar` y `workflow_dispatch` de un épico; materializa DAG/Issues, no despacha tareas autónomamente.
- [Coordinación V3](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/.github/workflows/coordinacion-trabajo.yml): cron `17 * * * *` y eventos GitHub; el job programado barre inactivas y bloqueos, no ejecuta el selector V2.
- [Salud de cola](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/.github/workflows/salud-cola.yml): cron `0 * * * *`, observador **GET-only** y publicación solo por `workflow_dispatch` con `publicar=true`. [Su script observador](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/scripts/salud_cola_observar.py) se declara local y sin autoridad de despacho; [el publicador](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/scripts/salud_cola_publicar.py) emite `SKIPPED`, no escribe GitHub.
- [Unattended Watchdog](https://github.com/pl0n3r/Factory/blob/3239737cd040b222786f9d9003cbc92bbfb96231/.github/workflows/unattended-watchdog.yml): cron `*/15 * * * *`; ejecuta `scripts.unattended_watchdog_runtime` para observar/gestionar alertas fail-closed de Factory, **no** arrancar trabajadores ni aceptar hojas.
- El alcance de búsqueda es el HEAD indicado y las definiciones de workflows de **Factory**, no todos los procesos externos de ControlBot, FactoryRunner o un equipo local. La ejecución autónoma de esos sistemas se audita por separado en #2124, #2125 y #2126.

## Evidencia primaria de ejecuciones (no tests simulados)

| Fecha UTC / ejecución | HEAD y evento | Resultado observado | Lectura correcta |
| --- | --- | --- | --- |
| [12-nov 12:40, watchdog #43220036613](https://github.com/pl0n3r/Factory/actions/runs/43220036613/job/131188919997) | `3239737cd040b222786f9d9003cbc92bbfb96231`, `schedule`, job `success` | JSON terminal: `action=BLOCKED`, `authority=unchanged`, `create=[]`, `close=[]`, `reopen=[]` | El watchdog se ejecutó, sin despachar ni crear trabajo. `BLOCKED` es el resultado **de este watchdog**, no un veto global inferido. |
| [12-nov 08:59, cola #43187545382](https://github.com/pl0n3r/Factory/actions/runs/43187545382/job/131078410762) | `3239737cd040b222786f9d9003cbc92bbfb96231`, `schedule`, job `success` | JSON terminal `status=SKIPPED`, `reason=local_observation_not_global_proof`, `action=none`, `writes=0` | Ejecución periódica de observación real; **no** dispatch ni prueba global de inventario. |
| [12-nov 09:45, coordinación #43194279056](https://github.com/pl0n3r/Factory/actions/runs/43194279056/job/131101094976) | `3239737cd040b222786f9d9003cbc92bbfb96231`, `schedule`, job `success` | `Reservas recuperables marcadas: 0` | Barrido real de reservas; no auto-selección de un issue ni activación de ejecutores. |
| [12-nov 13:01, orquestador #43223346102](https://github.com/pl0n3r/Factory/actions/runs/43223346102/job/131200182436) | `3239737cd040b222786f9d9003cbc92bbfb96231`, `issue_comment` | Job `planificar` `skipped` | Un comentario ajeno a `/planificar` no dispara planificación; este run no sirve como test de despacho. |
| [12-nov, #2123: comando manual](https://github.com/pl0n3r/Factory/issues/2123#issuecomment-6824531661) → [recibo BOT V3](https://github.com/pl0n3r/Factory/issues/2123#issuecomment-6824582659) | `issue_comment` del OWNER y coordinador real | Reserva auténtica `29dce0f4-f906-4629-87df-4240b0961987`, rama `trabajo/issue-2123` y claims exclusivos | **VERIFICADO:** el coordinador responde al `/tomar` manual; **NO** demuestra selección autónoma de #2123. |

Para la periodicidad, se constataron al menos dos watchdogs `schedule/success`: [#43153281021](https://github.com/pl0n3r/Factory/actions/runs/43153281021) (04:12 UTC) y [#43220036613](https://github.com/pl0n3r/Factory/actions/runs/43220036613) (12:40 UTC). Este intervalo observado es mayor que el cron nominal de 15 minutos. **La causa y la integridad de las corridas intermedias quedan NO DEMOSTRADAS**; no atribuirla a fallos del dispatcher sin investigación de programación/colas de Actions.

## Matriz de capacidades

| Capacidad solicitada | Clasificación | Evidencia y límite |
| --- | --- | --- |
| Código de selector determinista | **PARCIAL** | `select_next`, `classify_readiness`, `work_ladder`, `dispatch_record` y pruebas están en repositorio. Falta demostrar invocación en runtime productivo, con snapshot de candidatos autenticado. |
| Schedule que despierta al despachador V2 | **NO IMPLEMENTADO** *en los 36 workflows Factory revisados* | Existen crons para watchdog, barrido y observador; ninguno llama directamente al selector. No hay un runner V2 invocable por `schedule` en estos workflows. |
| Detección periódica de issues elegibles **en siete repositorios** | **NO DEMOSTRADO** | Constantes y reglas canónicas en código; `salud_cola_observar.py` inventaría **solo Factory** y su publicador declara `local_observation_not_global_proof`. Sin snapshot/fingerprint completo de los siete repos en un run de despacho. |
| Prioridad HEALTH > INCIDENT > ACTIVE FIX > OWNER > crítica > alta > media | **PARCIAL** | `AUTHORITY_ORDER`, desempates, tranche y guardas existen. No hay run que pruebe el ranking frente a issues actuales y que luego tome el ganador. |
| Dependencias, exclusión de claims y recuperación V3 | **VERIFICADO**, únicamente para la coordinación manual observada | El comando `/tomar` del OWNER en #2123 produjo recibo de bot V3, rama/claims. No prueba que un proceso desatendido invoque `/tomar`. |
| Conexión Factory → ControlBot/FactoryRunner con ejecutor real | **NO DEMOSTRADO** | Ningún run aportado de esta cadena lleva `agent_id`, job remoto, work item, resultado de agente y PR/merge correlacionados. Verificar con fuentes independientes de #2124/#2125, sin inferir por clases o mocks. |
| Cuatro frentes simultáneos reales con fencing | **NO DEMOSTRADO**; límite cuatro **NO IMPLEMENTADO** en `parallel_ready` | La función toma candidatos disjuntos y los añade hasta agotar los elegibles; no tiene parámetro/techo `max_active=4`. Eso no demuestra cuatro workers ni exclusividad interproceso. |
| Continuación automática merge → siguiente candidata sin intervención | **NO DEMOSTRADO** | No existe en esta muestra una cadena firmada `finished_at → next_dispatch_at` seguida de nueva lease, ejecutor y PR. `dispatch_signature` e `idle_time_metric` solo calculan registros a partir de parámetros. |
| Watchdog programado | **VERIFICADO** como observador; resultado de corrida **BLOQUEADO** | Run #43220036613 devuelve `BLOCKED` sin mutaciones. No equivale a selector/executor funcionando. |
| Salud de cola programada | **VERIFICADO** como observador; publicación/salida **BLOQUEADO** por contrato de esa muestra | Run #43187545382 devuelve `SKIPPED`, `writes=0`. Falta evidencia agregada de siete fuentes para la ruta de aviso; el job automático nunca reserva trabajo. |
| Orquestación `/planificar` | **PARCIAL** | Workflow definido bajo evento humano/manual y validaciones; run inspeccionado fue `skipped`. No acredita selección y ejecución periódica ni plan real materializado en ese run. |

**No confundir cuatro capas:** (1) mensajes y `/tomar` manuales de GPT/Claude: trabajo asistido por humanos, como esta hoja; (2) watchdog, coordinación y cola: automatización de **supervisión**; (3) ejecutar tareas con aprobación humana: ejecución supervisada, **NO DEMOSTRADA** aquí; (4) operador que despierta, asigna, ejecuta, fusiona y despacha otra hoja sin intervención: **NO DEMOSTRADO**.

## Causa técnica observable, medidas y autoridad

1. **Cableado de entrada:** no se encontró en el conjunto cerrado de 36 workflows Factory una llamada directa al selector V2 ni un job que persista un `dispatch_record` de candidatos reales. Corregir requiere una hoja de integración **nueva con claims exclusivos** de workflow/script/tests afectados, pruebas de schedule→inventario→selección y negativa ante #767/guardas, **no** editar desde esta reserva documental.
2. **Fuente global:** el observador horario se declara `GET-only`, `Factory-only`, y su publicador retorna `SKIPPED` ante observación local. Reutilizar el proveedor autenticado de inventario/fencing aprobado, verificar siete repos + paginación + cuota, y diseñar recibo exacto por selección; no fabricar trabajo ni ampliar permisos sin contrato.
3. **Entrega de trabajo:** falta recibo verificable de Factory → control plane → execution plane con `agent_id`, lease V3, SHA, fencing y entrega del PR. La propiedad de ese código debe aclararse contra auditorías #2124/#2125 y probar el caso real #2129 **antes** de cuatro frentes #2130.
4. **Paralelismo:** `parallel_ready` calcula conjunto disjunto, no presupuesto de cuatro slots. Una hoja de corrección debe agregar límite parametrizado y test que falla al permitir cinco elegibles, junto con exclusividad real interprocesos y recuperación por fallo; requiere claim de `scripts/dispatcher_v2.py` y test correspondiente.
5. **Frecuencia y cola:** revisar los eventos `schedule` y las ejecuciones ausentes entre 04:12 y 12:40 UTC, latencias/cancelaciones y capacidad del runner con timeline oficial, antes de atribuir causalidad al dispatcher. No cambiar timers para ocultar fallos.
6. **Continuidad:** medir dos dispatches consecutivos con `issue_id`, `agent_id`, `reservation_id`, `head_sha`, PR/merge SHA, `finished_at`, `next_dispatch_at` y prueba de que no hubo instrucción humana intermedia. Sin estos recibos, estado `NO DEMOSTRADO`.

### Correcciones de código en esta entrega

**Ninguna.** El contrato V3 de #2123 autoriza **exclusivamente** `docs/auditoria-autonomia/02-dispatcher.md`. Modificar `scripts/dispatcher_v2.py`, tests o workflows en el mismo PR violaría claims y coordinación. Las fallas técnicas anteriores se entregan como causas observables y propuestas **pendientes de hoja ejecutable/claims/V3**; no se marca una corrección como probada sin test RED→GREEN. El épico #2121 y la consolidación #2128 son el lugar de coordinación; no crear una segunda orquestación ni declarar reparada la autonomía por este informe.

### AC y reversión

- **AC-01:** informe presente, matriz de capacidades con categoría exacta y enlaces a fuente/run/log, incertidumbre explícita.
- **AC-02:** no hay modificaciones de código fuera del claim ni reparaciones falsamente atribuidas; cualquier cambio futuro requiere prueba que falle al revertirlo y autorización de rutas del repositorio correspondiente.
- **AC-03:** cierre de este PR **solo con CodeQL y `Validar` success sobre su HEAD exacto**, controles V3 y política de revisión FINAL después del CI verde.

Reversión: revertir el squash del PR #2123 elimina este informe sin alterar scripts, usuarios, producción ni estado de infraestructura. No hay acceso remoto, compras, credenciales, datos reales ni cambios de release incluidos.
