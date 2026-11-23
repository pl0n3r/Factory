# C1 · Prueba del ciclo Qwen autónomo de extremo a extremo

> **Corte:** 22-nov-2026 / 23:00 Colombia, fuentes autenticadas en GitHub. [Factory main@fd7217e6](https://github.com/pl0n3r/Factory/commit/fd7217e6acce6c6c43a772fec7127203ee497c94), [ControlBot main@b7ffd01d](https://github.com/pl0n3r/ControlBot/commit/b7ffd01d6a4e4100e54c0b2852596dcb12a55925), [FactoryRunner main@cb43318e](https://github.com/pl0n3r/FactoryRunner/commit/cb43318ebf8a3031638506182ece6dc2bdf3559a). Hoja [Factory #2129](https://github.com/pl0n3r/Factory/issues/2129) de [épica #2121](https://github.com/pl0n3r/Factory/issues/2121).

## Dictamen

**Ciclo C1 autónomo completo: NO DEMOSTRADO.** La primera arista no acreditada es **backlog elegible → disparador automático → orden ejecutable entregada a un agente Qwen**: el workflow observado de Factory prepara una propuesta *manual y offline*, no despacha trabajo a un worker. Hay además una ruptura reproducida en laboratorio: **Ollama emite una tool call → Qwen Code CLI ejecuta edit → unittest verde**, que no ocurrió con el modelo real. Ni éxito de CI ni PR fusionado por GPT/Claude suplen una traza autónoma.

Este archivo es una **auditoría supervisada** y su eventual PR no acredita una corrida Qwen. La reserva de esta hoja fue solicitada [manualmente con /tomar](https://github.com/pl0n3r/Factory/issues/2129#issuecomment-7091166945); [Coordinación produjo la V3 auténtica](https://github.com/pl0n3r/Factory/issues/2129#issuecomment-7091174446) en el [run 45109019934](https://github.com/pl0n3r/Factory/actions/runs/45109019934): UUID b109722f-bfa8-4b25-be98-dd18199475e1, ruta exclusiva docs/auditoria-autonomia/08-prueba-ciclo.md. Es prueba de **coordinación tras comando humano**, no de un worker Qwen. No habilita automáticamente [C2 #2130](https://github.com/pl0n3r/Factory/issues/2130).

**Semántica:** VERIFICADO significa prueba primaria de la característica exacta en el ámbito indicado; PARCIAL acredita solo un tramo/contrato; BLOQUEADO identifica una guarda de autoridad o fallo reproducido; NO IMPLEMENTADO se usa exclusivamente para ausencia en superficie delimitada e inspeccionada; NO DEMOSTRADO significa evidencia primaria ausente o incompleta, nunca funcionalidad inferida.

## Matriz de transiciones y evidencia por capacidad

| Transición de una misma tarea | Clasificación | Fuente primaria y límite |
| --- | --- | --- |
| 1. Issue elegible, dependencias y alcance | **VERIFICADO** (GitHub) | [#2129](https://github.com/pl0n3r/Factory/issues/2129) declara aceptación, ruta única y dependencia [#2128 completada](https://github.com/pl0n3r/Factory/issues/2128). Esto no implica ejecutor autónomo. |
| 2. Trigger periódico/evento → selección y orden Qwen | **NO IMPLEMENTADO** en workflow inspeccionado; global **NO DEMOSTRADO** | [orquestador.yml@fd7217e6](https://github.com/pl0n3r/Factory/blob/fd7217e6acce6c6c43a772fec7127203ee497c94/.github/workflows/orquestador.yml) solo admite /planificar humano y workflow_dispatch; offline_dispatch requiere activación manual. No tiene schedule/entrega Qwen. [A2](02-dispatcher.md) acota el inventario anterior de 36 workflows, no otros servicios externos. |
| 3. Inventario siete repos, selector V2 e idempotencia | **PARCIAL**, solo propuesta | [Factory #2146 / PR #2149 fusionado](https://github.com/pl0n3r/Factory/pull/2149), [squash 4015f17a](https://github.com/pl0n3r/Factory/commit/4015f17a24f5450ae1ce0dd1e91481f4e005e46a): PROPOSED/BLOCKED/REPLAY con policy_sha y negativos; execution=OFFLINE_ONLY, executed=false y sent_count=0. No acredita emisión remota. |
| 4. Orden ejecutable enviada desde Factory → ControlBot | **NO DEMOSTRADO** | [PR #2149](https://github.com/pl0n3r/Factory/pull/2149) explícitamente no envía. [A3](03-controlbot.md) detectó contratos, no recibo de orden autenticada que conecte ambos componentes. Falta order_id, policy_sha y recepción correlacionada. |
| 5. Poll → ACK → evento final → replay/restart durable | **PARCIAL** en laboratorio | [ControlBot #1516 / PR #1517](https://github.com/pl0n3r/ControlBot/pull/1517), [squash b7ffd01d](https://github.com/pl0n3r/ControlBot/commit/b7ffd01d6a4e4100e54c0b2852596dcb12a55925): tres procesos PHP y archivo sintético preservan IDs y rechazan replay; provenance=synthetic-offline, execution=false. No certifica endpoint o worker real. |
| 6. Obtener V3 válida por Qwen para esa orden | **VERIFICADO** solo manual/BOT, autónomo **NO DEMOSTRADO** | [Comando humano](https://github.com/pl0n3r/Factory/issues/2129#issuecomment-7091166945) y [recibo BOT V3](https://github.com/pl0n3r/Factory/issues/2129#issuecomment-7091174446), sin order_id Qwen ligado. La reserva actual solo permite este documento. |
| 7. Worker FactoryRunner real, identidad/heartbeat fresco | **BLOQUEADO** para live, operativo **NO DEMOSTRADO** | [FactoryRunner #465](https://github.com/pl0n3r/FactoryRunner/issues/465) mantiene NO-GO del dueño. [scripts/run-runner.ts@cb43318e](https://github.com/pl0n3r/FactoryRunner/blob/cb43318ebf8a3031638506182ece6dc2bdf3559a/scripts/run-runner.ts) exige transporte mock loopback y adapter unavailable que falla. [A4](04-runner.md) distingue tests y workers. |
| 8. Inferencia Ollama genera llamada estructurada | **VERIFICADO**, solo llamada aislada | [Ensayo #2067](https://github.com/pl0n3r/Factory/issues/2067#issuecomment-6937997561), [A5](05-qwen.md): qwen3:4b entregó tool_calls para multiply por APIs bajo presupuesto suficiente. Generación de JSON no equivale a herramienta ejecutada. |
| 9. Qwen Code real ejecuta edit y prueba verde | **BLOQUEADO** en laboratorio, C1 **NO DEMOSTRADO** | [#2067](https://github.com/pl0n3r/Factory/issues/2067#issuecomment-6937997561): CLI 0.26.9 y Ollama real finalizaron exit 55 sin editar ni pasar unittest. Con proveedor mock el CLI editó, pero sin test verde ni modelo real. No concatenar ambos ensayos como una prueba. |
| 10. Qwen aplica código, commit y PR sin operador | **NO DEMOSTRADO** | [Factory PR #2073](https://github.com/pl0n3r/Factory/pull/2073), [Condor PR #1871](https://github.com/pl0n3r/Condor/pull/1871) y [A5](05-qwen.md) documentan entregas supervisadas tras intentos CLI fallidos; no existe la cadena de autoría Qwen/orden/lease. |
| 11. Tests, CI exact-HEAD, Sonar/CodeQL, CodeRabbit FINAL | **VERIFICADO** para PR supervisados, C1 **NO DEMOSTRADO** | [PR #2149](https://github.com/pl0n3r/Factory/pull/2149) y [#1517](https://github.com/pl0n3r/ControlBot/pull/1517) prueban entregas parciales; sus checks no se atribuyen a un Qwen real. |
| 12. Squash de la misma tarea y separación de deploy | **VERIFICADO** para PR supervisados, C1 **NO DEMOSTRADO** | Squash [4015f17a](https://github.com/pl0n3r/Factory/commit/4015f17a24f5450ae1ce0dd1e91481f4e005e46a) y [b7ffd01d](https://github.com/pl0n3r/ControlBot/commit/b7ffd01d6a4e4100e54c0b2852596dcb12a55925); merge no demuestra Qwen ni producción. |
| 13. Terminal → siguiente issue despachado sin humano | **NO DEMOSTRADO** | [A1](01-cadena.md), [B1](07-causa-raiz.md), [épica #2121](https://github.com/pl0n3r/Factory/issues/2121). Falta orden siguiente correlacionada con la misma sesión autónoma y otro issue elegible. |
| 14. Cuatro agentes paralelos sin colisiones/merge serial | **BLOQUEADO** por C1 y **NO DEMOSTRADO** | [C2 #2130](https://github.com/pl0n3r/Factory/issues/2130), aún bloqueado. Un test de claims disjuntos no es evidencia de cuatro ejecutores reales. |

## Prueba falsable de desbloqueo C1

1. **Seleccionar y despachar:** snapshot auténtico y completo de siete repos con policy_sha exacto, prioridad/lease/claims y kill switch RUNNING. Un trigger permitido y no manual produce order_id único y orden firmada. Sin snapshot, dependencia, permisos o integridad: **cero órdenes**. La salida sent_count=0 de #2146 debe permanecer clasificada offline.
2. **Recibir y ejecutar:** ControlBot registra entrega, FactoryRunner auténtico devuelve poll/ACK/heartbeat/evento final del **mismo** order_id/runner_id/lease_id con tiempos y reanudación idempotente; replay, identidad incorrecta, heartbeat stale y token revocado son negativos obligatorios. No aceptar mock como ejecución real.
3. **Verificar Qwen:** modelo real con CLI ejecuta de verdad read_file→edit y unittest que era rojo antes del cambio queda verde; se observa diff del archivo sintético y recibo de tool call ejecutada, no JSON textual ni parche aplicado por el operador. Sin edit real: STOP/UNKNOWN aunque el modelo haya respondido.
4. **GitHub y continuidad:** el mismo agente autorizado produce branch/commit/PR con V3, CI/CodeQL/Sonar terminales sobre HEAD exacto, una sola revisión CodeRabbit FINAL y squash; después se observa la **siguiente selección** con IDs/timestamps y sin un nuevo comando humano.
5. **Falsos positivos a rechazar:** workflow success de observación, propuesta no enviada, ACK simulado, script con exit 0 que imprime JSON, PR de GPT/Claude supervisado, CI verde sin identidad Qwen, ausencia de logs compensada por etiquetas. En cualquiera, C1 no se declara VERIFICADO.

## Autoridades, límites y cambios que no se ejecutaron

| Puerta | Condición |
| --- | --- |
| #767 / V3 | Único marker RUNNING y reserva propia auténtica con claims exactos para cada ejecución; un snapshot mock RUNNING no sirve como autoridad. |
| FactoryRunner #465 | [NO-GO vigente](https://github.com/pl0n3r/FactoryRunner/issues/465) de trabajo/activación real, salvo autorización específica del dueño; el preflight offline no habilita runtime. |
| ControlBot #625 / D-059 | [Puerta Hostinger](https://github.com/pl0n3r/ControlBot/issues/625): para deploy/conexión real hacen falta consentimiento exacto, backup/restore válido y controles de privacidad. La prueba sintética #1516 no concede live. |
| D-061 / AutoFactory | [A6](06-autofactory.md), [A7](10-orq-local.md): bridge remoto y sesiones siguen sujetos a permiso específico, no se activan por un informe. |
| D-043, D-069, release | La producción exige recibo VALIDATED_IN_PRODUCTION con SHA y no se infiere desde CI. No publicar/mover Factory@v1 ni eludir protección de rama. |
| Datos, gasto, credenciales | No usar PII, datos de clientes, secretos, compras, host real o sesiones de terceros. Las pruebas sintéticas solo proporcionan evidencia acotada. |

## Criterios de #2129, autorrevisión SRE/QA y reversión

| Criterio | Evidencia verificable de esta hoja |
| --- | --- |
| **AC-01** | Este archivo clasifica 14 capacidades con fuentes y limites; la primera transición no acreditada está nombrada. **No se afirma** que el ciclo Qwen real funcionó. |
| **AC-02** | Sin cambios de runtime, workflows o otros repositorios: no se fabrican regresiones de código. La prueba futura debe fallar al retirar el envío, autenticación del ACK, edit efectivo o idempotencia; se detallan las autorizaciones requeridas. |
| **AC-03** | Tests de scripts, Validar, Sonar y CodeQL deben ser terminales success sobre el HEAD exacto del **PR documental**. Ese CI solo valida la entrega auditada, **no** el ciclo autónomo. Evidencia del PR se consigna en la conversación de entrega. |

**QA:** se contrastan positivos de scope (selector offline, ACK mock, V3 manual, Ollama tool_calls) con negativos deterministas (sin orden, worker no habilitado, CLI exit 55, sin PR atribuible a Qwen). **SRE:** no se atribuyen health, restore, rollback, RPO ni smoke real sin un servicio autorizado y recibo fresco; se especifica reconciliación exacta entre orden, worker, lease y estados terminales. UX/E2E de navegador no aplica a esta hoja exclusivamente documental.

**Riesgo:** bajo; solo documentación. Revertir el squash elimina el informe. No se alteran workers, hosts, datos reales, credenciales, permisos ni releases. El cierre administrativo de #2129 **no debe promover** el estado global de la épica #2121 ni desbloquear #2130 hasta existir evidencia E2E positiva independiente.
