# Continuidad offline ante caídas de GitHub y ChatGPT

**Factory #1553 · Parent #1082 · estado documental.** Este runbook no ejecuta failover automático, restore ni cambio de proveedor: define un freno seguro para un agente sin fuentes autenticadas. La credencial, backup y restore reales se rigen por [resiliencia-fabrica.md](resiliencia-fabrica.md), #1035 y #305. Ninguna fila certifica una caída o recuperación real.

## Autoridad y estados

- **UNKNOWN:** pérdida, caducidad, contradicción o lectura parcial de una fuente necesaria. Acción obligatoria: **SUSPENDER**, sin mutaciones. No reutilizar snapshots de PR, Checks, reservas o Factory#767.
- **PAUSED:** Factory#767 responde PAUSED, ilegible o con marker inválido/duplicado. Acción: **SUSPENDER**. No inferir que el kill switch sigue RUNNING. Únicamente el dueño puede modificarlo mediante decisión expresa.
- **RECUPERACION_EN_VALIDACION:** vuelve una conexión o sesión, pero aún faltan controles o consentimiento. Acción: **SUSPENDER**; HTTP 200 y un workflow marcado success no bastan.
- **READY_VERIFICADO:** solo tras un nuevo ciclo completo: identidad GitHub autenticada, Factory#767 RUNNING único, reserva V3 propia, main/HEAD exactos, claims y dependencias, CI y gates terminales, branch protection y freeze verificados. No autoriza live ni go-live.
- La pérdida de una sesión ChatGPT afecta al agente afectado, no crea una pausa global por sí misma. Otros agentes legítimos necesitan su propio preflight; nunca heredan reservas de una sesión caída.

## Matriz de escenarios y fuentes observables

| ID | Escenario y disparador observable | Fuente y comprobación para distinguir el fallo | Estado | Acción |
| --- | --- | --- | --- | --- |
| GH-API | GitHub API devuelve 401/403/429, 5xx, timeout o datos truncados | Contrastar cuota, autorización y transporte mediante respuesta autenticada; sin API no se comprueban Factory#767 ni leases V3 | UNKNOWN | SUSPENDER |
| GH-ACTIONS | GitHub Actions tiene run pendiente, cancelado, ausente o con SHA distinto | Consultar jobs/checks y evidencia terminal de Validar, aceptación, CodeQL y SonarCloud en HEAD exacto, nunca color antiguo | UNKNOWN | SUSPENDER |
| GH-IDENTIDAD | GitHub App revocada, permisos faltantes, 2FA/MFA de identidad pendiente | Custodio verifica identidad, instalación y scopes actuales sin emitir un PAT personal ni cuenta alternativa | UNKNOWN | SUSPENDER |
| CG-SESION | ChatGPT pierde sesión, conector, contexto o responde parcialmente | Sesión ChatGPT afectada no tiene autoridad vigente; otro ejecutor requiere preflight autenticado propio | UNKNOWN | SUSPENDER |
| CG-CUENTA | ChatGPT bloquea la cuenta, recuperación pendiente o acceso no demostrable | Custodio de la cuenta verifica recuperación legítima; ChatGPT no acredita una lease de GitHub | UNKNOWN | SUSPENDER |
| MIXTO | GitHub API/Actions y cuenta/sesión ChatGPT son simultáneamente inaccesibles | No hay comprobación actual de coordinación, RUNNING, main, PR ni checks; bitácoras son únicamente históricas | UNKNOWN | SUSPENDER |

Una API GitHub disponible no demuestra GitHub Actions sano; Actions success sin API/autenticación no demuestra permisos o lease; volver a ChatGPT no acredita identidad de GitHub. No usar un status público, pantalla cacheada o reloj para convertir UNKNOWN en READY_VERIFICADO.

## Contención: operaciones suspendidas

En UNKNOWN, PAUSED o RECUPERACION_EN_VALIDACION están prohibidos **/tomar, /liberar, /transferir, /renovar-contrato**, commits, push, modificación de Issues/PR/tags, merge, rerun de jobs, releases, mover Factory@v1, deploy y go-live. **Ninguna escritura** está permitida aunque la acción parezca reversible. La lease histórica es **no prorrogada**, no se puede recuperar por copiar su UUID. Ante una llamada fallida, **no autoriza un segundo intento de escritura** sin nuevo preflight verificable. No atribuir éxito a CI o VALIDATED_IN_PRODUCTION sin evidencia terminal específica.

## Canal manual offline estrictamente sin escritura

Registrar en bitácora local: fecha y hora aproximada marcada **no verificable**, ID público del Issue/PR, último main/HEAD SHA identificado como histórico, clase del error, incertidumbre, comandos suspendidos y próximos requisitos de comprobación. La información es local y saneada: **sin escritura** sobre GitHub ni otras APIs, sin enviar instrucciones operativas por correo, DM o cuentas suplantadas. Si hay pérdida de identidad del destinatario no se envía nada. Páginas públicas de GitHub/OpenAI son solo contexto, nunca sustituyen la URL exacta de Factory#767, lease o check.

Prohibido copiar secretos, cookies, PAT, tokens, claves privadas, passwords, 2FA/MFA, contenido de ChatGPT, conversaciones de clientes, direcciones personales, PII, datos reales, logs privados o backups reales. Se pueden anotar identificadores públicos y la conclusión **histórica** de un check, nunca presentarla como actual.

## Reentrada autenticada: secuencia obligatoria

1. **Identidad autorizada**: restaurar la lectura autenticada de GitHub API e identificar el actor. ChatGPT recuperado no hereda permisos, y cuentas/2FA/MFA requieren custodio legítimo.
2. **Factory#767**: consultar la URL exacta y validar número, repo, autor pl0n3r y único marker v1 RUNNING; si falla se continúa **SUSPENDER**.
3. **main y HEAD exactos**: releer SHA actual de main, rama trabajo/issue-N y PR existente; validar ausencia de conflicto, protección efectiva y reconciliación.
4. **reserva V3**: verificar UUID, owner, actividad, fingerprint, claims disjuntos, dependencias, revocación y vigencia actuales. Una lease perdida no puede recuperarse desde texto guardado; solo pedir /tomar de nuevo cuando las reglas lo permitan.
5. **gates del SHA exacto**: verificar Validar, aceptación, SonarCloud, CodeQL, CodeRabbit/Policy, D-069/D-070, freeze #921 y gates de seguridad y producción pertinentes; nunca confundir checks pendientes con terminales.
6. **bitácora offline**: comparar toda evidencia histórica con nueva fuente autenticada; SHA distinto, permiso ausente o check parcial mantienen RECUPERACION_EN_VALIDACION y **SUSPENDER**.
7. **Decidir reentrada**: únicamente si cada comprobación es auténtica, actual y satisfactoria pasar a READY_VERIFICADO para trabajo reversible dentro del Issue. Deploy, compra, datos reales, publicación y go-live conservan sus puertas humanas independientes.

Nunca se salta directamente de UNKNOWN/PAUSED a escritura por timeout, mensaje de ChatGPT, token nuevo, copia del UUID, status web o cache.

## Pruebas de mesa sintéticas, sin red

| Fixture | Datos sintéticos | Resultado esperado |
| --- | --- | --- |
| MESA-01 | API=429, Actions success histórico y Factory#767 ilegible | UNKNOWN; SUSPENDER |
| MESA-02 | API=200, Actions pending y SHA de check distinto | UNKNOWN; SUSPENDER |
| MESA-03 | ChatGPT sin sesión, GitHub disponible para un tercero | UNKNOWN para el agente perdido; SUSPENDER |
| MESA-04 | API restaurada, RUNNING, reserva V3 revocada | RECUPERACION_EN_VALIDACION; SUSPENDER |
| MESA-05 | ChatGPT restaurado, RUNNING, CodeQL incompleto o main nuevo | RECUPERACION_EN_VALIDACION; SUSPENDER |
| MESA-06 | Actor autenticado, RUNNING, reserva propia, main/HEAD reconciliados, checks exact-SHA terminales y sin freeze | READY_VERIFICADO solo para labor autorizada; nunca go-live automático |

Las pruebas documentales corren offline: python3 -m unittest -v tests.test_continuidad_caida_proveedores. No usan cuentas, tokens ni red.

## Límites de autoridad, costos y reversión

**RTO: UNKNOWN. RPO: UNKNOWN.** No hay medición real de RTO/RPO, SLA acreditado ni un restore de producción con fixtures. Backups externos, 3-2-1-1-0, proveedores, cuenta ChatGPT, secretos/2FA, credenciales e identidades reales exigen custodio y gates separados. Prohibidos gastos, compras, failover automático, cuentas alternas inventadas, acceso a datos reales, PII, secreto alguno, modificación de CI/PLAN, borrado irreversible, DNS, deploy, mover Factory@v1 o go-live.

Fuera de alcance: medir tiempos reales, provisionar infraestructura, activar producción, certificar proveedor recuperado o declarar GREEN/live. La reversión del squash borra solo este runbook y los tests: **sin efectos sobre runtime**.
