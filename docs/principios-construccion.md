# Principios de construcción de la fábrica

**Alcance:** siete repositorios canónicos de Factory. **Autoridad:** [PLAN-AGENTES.md](../PLAN-AGENTES.md) y contratos de cada consumidor. Documento de diseño para fase construcción; no habilita por sí solo acciones, coordinación, merges ni releases. Fuente: [Factory #1082](https://github.com/pl0n3r/Factory/issues/1082).

## Regla 0 — diseñar primero para ejecución en paralelo

Diseñar todo trabajo para ejecutarse en paralelo; serializar solo por dependencia real de datos, colisión real de archivos o gate de autoridad vigente. Dividir épicos en hojas con aceptación ejecutable, claims concretos y dependencias dirigidas. Maximizar paralelismo **demostrable**, nunca inferido de que dos tareas son conceptualmente distintas. Coordinación arbitra las reservas y la lease ajena conserva exclusividad. Fuente: [Factory #1081](https://github.com/pl0n3r/Factory/issues/1081).

## Principio 1 — cola saludable sin inventar disponibilidad

Una cola con cero hojas disponible en los siete repositorios exige inventario completo y escalera no ociosa; no da permiso de convertir bloqueos en trabajo listo. Diferenciar disponible, reservado, en revisión, bloqueado y planificado; todo bloqueo lleva causa y condición verificable de salida. La ausencia de candidatos se informa sin fabricar readiness. Fuentes: [Factory #1082](https://github.com/pl0n3r/Factory/issues/1082) y [ControlBot #760](https://github.com/pl0n3r/ControlBot/issues/760).

## Principio 2 — hojas pequeñas y reversibles

Descomponer tramos amplios en hojas con ruta crítica explícita, riesgo acotado, pruebas AC-NN y claims disjuntos. Un módulo puro build-ahead con fakes deterministas permite preparación offline cuando un gate operativo impide activación; el fake no demuestra permisos, proveedor real, HEALTH ni despliegue. Fuentes: [Factory #1082](https://github.com/pl0n3r/Factory/issues/1082) y [ControlBot #761](https://github.com/pl0n3r/ControlBot/issues/761).

## Principio 3 — claims verificados por archivo

Preferir claims estrechos por archivo. Una lease activa sobre un directorio no se ignora por prometer editar archivos distintos: el árbitro necesita pruebas completas de diff exact-SHA y dependencias. Si el diff está ausente, truncado, stale, ambiguo o cambió el SHA, falla cerrado. README.md, config/version.php, package.json, package-lock.json y otros lockfiles compartidos son colisiones reales; no** se excluyen del arbitraje por comodidad sin un merge-train probado y autoridad explícita. Ni siquiera hunks distintos del mismo archivo permiten paralelismo automático. Fuente: [Factory #1081](https://github.com/pl0n3r/Factory/issues/1081).

## Principio 4 — estados, CI y observación

planificado ≠ bloqueado y available ≠ ready si faltan tandas, dependencias, reserva o autoridad. UNKNOWN nunca equivale a GREEN. Un PR, workflow success o su updated_at no acreditan agente activo ni producción válida. Verificar evidencia terminal exact-HEAD; para puertas D-043 exigir VALIDATED_IN_PRODUCTION, SHA e identidad, sin pendientes. Fuentes: [Factory #1075](https://github.com/pl0n3r/Factory/issues/1075) y [ControlBot #760](https://github.com/pl0n3r/ControlBot/issues/760).

## Principio 5 — autonomía acotada por D-068

construccion permite preparar trabajo reversible y offline dentro de D-068; **No elimina aprobación humana** para go-live, gasto/compras, credenciales/secretos, datos reales de clientes, destrucción irreversible, proveedor/terms ni puertas legal/privacidad todavía vinculantes. D-063 exige atestación válida para excepciones informativas; D-059 obliga backup previo donde aplica. Factory@v1 mantiene su puerta vigente exact-SHA mientras no se integre otro contrato: [Factory #1080](https://github.com/pl0n3r/Factory/issues/1080) es propuesta, **no** autorización autoejecutable. Incidentes de seguridad continúan bajo reglas estrictas: [Factory #1072](https://github.com/pl0n3r/Factory/issues/1072).

## Principio 6 — contrato antes de /tomar

Todo Issue ejecutable nuevo lleva ### Contexto, ### Alcance, ### Fuera de alcance, ### Criterios de aceptación, ### Contrato ejecutable y factory-plan-task completo con owner, roles, dependencies/depends_on y paths. AC-NN debe señalar unittest existente/implementable o check real, nunca un nombre ficticio. Plan primero; luego /tomar, UUID confiable y rama canónica. Fuente: [Factory #1082](https://github.com/pl0n3r/Factory/issues/1082).

## Principio 7 — presupuesto API compartido

Acotar lecturas, reusar inventario fresco y no hacer polling de CI. Verificar rate_limit y conservar capacidad para reparaciones; bajo el umbral configurado (referencia #1082: 20 %) posponer lecturas globales prescindibles, sin inventar datos faltantes. Autenticación compartida no garantiza 5.000 solicitudes disponibles en el instante. Fuente: [Factory #1082](https://github.com/pl0n3r/Factory/issues/1082).

## Principio 8 — preflight exact-main, no brechas supuestas

Antes de reabrir, reparar, cerrar o reservar por supuesta brecha, comprobar main exacto, AC, paths, PRs fusionados y carreras de cambio. Si el contrato ya está satisfecho, reconciliar sin work duplicado; si falta, mostrar delta real. Nunca fabricar APPROVED, HEALTH, actividad, throughput o readiness. Fuente: [Factory #1082](https://github.com/pl0n3r/Factory/issues/1082).

## Salud de cola y utilización — contrato, no monitor implementado

Reportar por repositorio y global conteos separados de disponible, reservado, en revisión, bloqueado y planificado; identificar causa y fuente de cada bloqueo. **Utilización = agentes activos verificados / capacidad de agentes disponible verificada**. Sin evidencia autenticada de agentes activos, capacidad, heartbeat y frescura, marcar UNKNOWN / no calculable, nunca 0 % o 100 %. Una regla heurística como ≈4 chats por cuenta Plus no es un denominador medido. Un PR, una reserva o updated_at no acreditan que un agente esté activo. El workflow salud-cola está fuera de esta hoja.

## Límite de esta entrega

Esta documentación no cambia Coordinación, no autoriza merges, releases, tags, ejecución GitHub, live, gasto ni producción. Todo conflicto se resuelve a favor de [PLAN-AGENTES.md](../PLAN-AGENTES.md) y de restricciones técnicas más estrictas.
