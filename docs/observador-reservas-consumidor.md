# Observador local de reservas V3 para consumidores — Fase A (#1442)

## Estado y autoridad

Esta hoja separa la **observación GET-only** de la activación mutable de
Factory [#1382](https://github.com/pl0n3r/Factory/issues/1382). No altera
`FACTORY_LEASE_AUTO_RELEASE_ENABLED`, no libera reservas, no cierra PRs ni
borra ramas. El marcador de los artefactos conserva `terminal_certified:false`,
`release_authorized:false`, `mutations:0`. Un workflow verde y un
`candidate_terminal` son **evidencia candidata**, nunca permiso para Fase B.

El antiguo observador
`.github/workflows/liberar-reservas.yml` continúa observando **solo Factory**.
El nuevo reusable
`.github/workflows/observador-reservas-consumidor.yml` expone `workflow_call`
y comprueba `github.repository` contra el conjunto literal autorizado. El
caller `template/.github/workflows/observador-reservas-consumidor.yml`
programa el trabajo **en el repositorio que lo adopte**; no dispone de token
transversal. El único GET fuera de ese repositorio es Factory #767, la fuente
canónica del kill switch global.

El caller utiliza `lease-consumer-caller-${{ github.repository_id }}` y el
reusable utiliza `factory-coordination-${{ github.repository_id }}`. Los grupos
son diferentes para evitar que el caller bloquee al reusable que invoca;
el reusable conserva la exclusión con Coordinación. Todo resultado de permisos ausentes, cambios
de identidad, cuota inferior al 20 %, actividad incompleta o fuente desconocida
falla cerrado.

## Secuencia de distribución por consumidor

1. Validar `Validar`, suite de seguridad, CodeQL/Sonar y revisión FINAL en el
   HEAD exacto del PR de Factory. Su squash no distribuye el reusable por sí mismo.
2. Publicar una versión Factory semántica y promover el **canal protegido `@v1`**
   solo bajo la puerta de release vigente del owner; no usar `@main` desde
   consumidores como sustituto.
3. En **cada** uno de Condor, GrindFlow, brvtal, ControlBot, AutoFactory y
   FactoryRunner, abrir hoja local con V3 propia para copiar/adaptar el caller y
   comprobar la exclusión de concurrencia con su Coordinación existente. El
   archivo instalado debe conservar `permissions` read-only y apuntar a
   `observador-reservas-consumidor.yml@v1`, con su `GITHUB_TOKEN` local.
   Coordinar por PR normal y CI del consumidor; nunca push directo ni token
   cross-repo.
4. Verificar un run `schedule` auténtico de ese repositorio y recuperar su
   artefacto `lease-consumer-evidence-<run_id>`. Contrastar SHA, ID del run,
   evento schedule, repo local, censo completo, permiso, timestamp, `status`
   y cada decisión/hallazgo con GitHub. Las observaciones
   `UNKNOWN`/`deferred_low_quota`, las ejecuciones de `workflow_dispatch`
   y los censos vacíos **no** acreditan ciclos de Fase A.
5. Acumular únicamente **al menos 100 ciclos terminales válidos durante
   al menos 24 horas reales por repositorio**, con cero falsos positivos y
   revisión QA individual de todo hipotético `release`. Una corrida por
   consumidor **no** se puede transferir a otro. La función
   `evaluate_phase_a_candidate` solo calcula candidatos; no autentica por
   sí misma los recibos ni la revisión externa de QA.

## Limitaciones que no se deben ocultar

El transporte portable `_GhReadOnlyAPI` aplica allowlist de rutas y verbos
GET. La fase actual puede certificar actividad **positiva** o vetos positivos;
no certifica ausencia completa de pushes con una búsqueda vacía. Por ello
`preview_integrated_activity` mantiene `UNKNOWN` cuando no puede demostrar
que una reserva quedó realmente inactiva. La compatibilidad bilingüe del censo
de Issues no amplía autoridad ni sustituye la validación del marker V3 en el
colector del repo.

**La Fase B tiene dependencias adicionales independientes:** falta una prueba
autenticada e íntegra de ausencia de actividad durante 30+10 minutos y un
protocolo de bloqueo/CAS compartido real con Coordinación. Mientras eso no
exista, `LeaseGithubPort.read/lock/append/status` seguirá
`PortNotArmed`, incluso si algún repo llegara a superar 100 ciclos en
24 horas. Un artefacto candidato no se puede transformar por sí solo en
`release_authorized:true`; la activación seguirá OFF hasta una implementación
segura, V3 nueva, gates y autorización vigentes.

## Rollback y exposición

Revertir el caller local por PR deja de generar recibos sin tocar ninguna V3.
Revertir el reusable de Factory requiere una release protegida posterior.
Los artefactos se retienen 7 días, omiten tokens, cuerpos y nombres de
titulares y solo contienen números de Issue y códigos de diagnóstico.
No programar recordatorios o tareas ChatGPT. No SQL, credenciales nuevas,
procesamiento de datos reales, deploy, gasto ni go-live.
