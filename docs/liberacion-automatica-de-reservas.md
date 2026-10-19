# Liberación automática de reservas V3 — diseño controlado (#1175)

### Fase A distribuida (#1382) — sólo observación

La auditoría empieza en Factory y se adoptará separadamente en cada consumidor
mediante Coordinación `@v1` y su propio `GITHUB_TOKEN`. **No existe censo
central entre repositorios ni credencial compartida multi-repo.** El observador
ejecuta GET autenticados contra el repositorio local, informa decisiones
hipotéticas y vetos en el resumen de cada run/artefacto, y mantiene **0
escrituras, 0 reservas liberadas**. `UNKNOWN`, 403 y fuente incompleta no
acreditan inactividad ni crean autoridad para mutar.

**CI activo como veto de observación (no prueba de inactividad).**
`collect_activity(..., allow_ci_veto_only=True)` permite emitir evidencia
`ci_veto_only=true` únicamente cuando los checks o runs de la rama están
autenticados, paginados y estables entre lecturas. Solo se usa desde
`LeaseGithubPort.read_observation()` y el preview GET-only: devuelve
`read_only/wait`, aunque la última actividad positiva sea antigua. La ruta
`read()` y cualquier ejecución mutante conservan el rechazo de esa evidencia.
Si el CI finaliza, las fuentes discrepan, cambia el HEAD o falta procedencia,
la observación vuelve a `UNKNOWN`. **Un veto tipado nunca demuestra la
ausencia de pushes y no acredita una decisión hipotética `release`**.
Continúa pendiente una auditoría negativa de pushes completa y autenticada.

El cron de Factory genera además `lease-audit-evidence.json` con
`run_id`, `head_sha`, repositorio y resultados por Issue (acción,
motivo, minutos, fuente y autoridades negativas), limitado por whitelist de
campos. Cuando hay `UNKNOWN`, persiste únicamente un registro mínimo sin
cuerpo ni cabeceras REST. El filtro exige exactamente **un objeto JSON
válido por Issue**; si el CLI emite dos registros, datos fuera de esquema
o JSON inválido, conserva `UNKNOWN` y no acredita el ciclo. Un artefacto de GitHub Actions vinculado al run
programado conserva este manifiesto 7 días; no se envía a comentarios.
El manifiesto declara siempre `terminal_certified=false`: ni `success`
ni `candidate_terminal` certifican los 24 h, los 100 ciclos o el QA.
Una subida fallida o un artefacto ausente tampoco certifica el run.

Con cuota REST inferior al 20 %, el ciclo publica `deferred_low_quota`,
omite el censo y termina en verde; ese run **no cuenta** como observación válida.
El cron también escribe un manifiesto tipado con `issues=[]`, cero
observaciones, `terminal_certified=false` y autoridad de liberación negativa,
sin llamadas REST adicionales. El artefacto vinculado al run distingue
aplazamiento de auditoría completa, pero no certifica QA.

Antes de considerar la Fase B se exigen **24 horas** reales y **100 ciclos**
**terminales y válidos por repositorio**, **cero falsos positivos** y **QA individual**
documentada de cada decisión hipotética `release`. No cuentan los ticks de
cron no ejecutados, los runs aplazados o las observaciones `UNKNOWN`.
Cualquier falso positivo o resultado sin procedencia autenticada bloquea la
activación. El flag `FACTORY_LEASE_AUTO_RELEASE_ENABLED` permanece en
`false`; mover `@v1` y activar liberaciones requieren puertas independientes.


## Qué está implementado y qué NO

Esta entrega introduce un **decisor puro, determinista y sin efectos** en
\`scripts/lease_auto_release.py\`, con regresiones en
\`tests/test_lease_auto_release.py\`. Es una **etapa de preparación**, no un
servicio de liberación activo. No invoca GitHub, no mueve branches ni altera
reservas en producción.

**No se autoriza activar un cron mutante** hasta integrar un colector auténtico
de evidencia y un ejecutor serializado, y demostrar los casos de carrera.
El workflow \`.github/workflows/liberar-reservas.yml\` es una auditoría de
solo lectura cada 10 minutos: en `pull_request` ejecuta contratos **offline**
sin consumir cuota REST; en `schedule/workflow_dispatch` de `main` requiere
cuota >=20 %, consulta por GET un **censo agregado** de Issues abiertos y
vuelve a comprobar #767 antes de publicar conteos. Ese censo **no acredita
inactividad individual**, no libera reservas ni modifica sus marcadores.
La integración autenticada del mutador sigue pendiente.

## Inspector REST agregado en la rama de #1175 (NO operativo)

El PR #1248 incorpora `scripts/lease_github_port.py` como **frontera
únicamente de lectura**, y `tests/test_lease_github_port.py` con fakes.
El inspector consume `collect_activity()` y vuelve a consultar el
interruptor **global** `/repos/pl0n3r/Factory/issues/767` antes y después.
Valida el objeto mediante el parser canónico (incluido el rechazo de claves
JSON repetidas), sin sustituir la fuente por un Issue local del consumidor.
Una observación positiva emite solo `RECENT_ACTIVITY`; la ausencia,
ambigüedad, cuota baja, 403, 429, paginación parcial o carrera emite `UNKNOWN`.
Ninguno de esos resultados autoriza liberación.

**Implementado en modo GET-only:** `recovery_note()` verifica procedencia
de `github-actions[bot]`, nota de recuperación, UUID/SHA/pins y comentarios
paginados con doble lectura. `recovery_label()` comprueba el evento `labeled`
atribuido al mismo bot, correlacionado con la nota, y repite el timeline.
Los dos métodos fallan cerrados ante páginas incompletas, cambios concurrentes,
403/429 o datos ambiguos. El Port compara también el conjunto de etiquetas,
asignados y comentarios entre lecturas, aun si `updated_at` no varía.

**Aún falta** una prueba autenticada y completa de **ausencia de actividad**
del titular durante la ventana, junto con el verdadero lock del Port y las
operaciones CAS de escritura. Por ello `read/lock/append/status` continúan
rechazados mediante `PortNotArmed`, incluso si un caller activa
`mutations_authorized`. El cron no importa ese Port, mantiene
`contents: read`, `issues: read` y **cero escrituras**. Compartir el grupo
`factory-coordination-${{ github.repository_id }}` para cron/dispatch es
una exclusión a nivel workflow, no un CAS del Issue; los PR tienen un grupo
independiente. Ninguna prueba parcial satisface AC-03 o autoriza activar
`FACTORY_LEASE_AUTO_RELEASE_ENABLED`.

## Semántica temporal explícita

Hay una contradicción en la solicitud original: «liberar a los 30 minutos»
frente a «30 minutos inactivo → recuperación → 10 minutos adicionales».
El decisor implementa conservadoramente el **alcance más restrictivo**:

1. Reserva en \`reservado\` o \`en revisión\`: después de **30 minutos**
   sin actividad atribuible verificable propone \`mark_recovery\`.
2. Estado \`requiere recuperación\`: tras **10 minutos completos desde
   la marca autenticada** y al menos 40 minutos de inactividad, propone
   \`release\`.
3. Con cron de 10 minutos, la liberación suele ocurrir a los **40–50
   minutos**, y puede tardar más por ejecución retrasada, cuota o protección.
   Por tanto **no se promete liberación efectiva a los 30 minutos**.

La propiedad \`libera_en_min\` es un tiempo mínimo restante según evidencia,
**no una promesa de cron ni una fecha de expiración con autoridad propia**.

El inspector de solo lectura expone este límite únicamente tras una
observación positiva autenticada de actividad reciente (actividad + 40 min).
Para un estado `UNKNOWN` devuelve `None`. El campo NO predice el momento del
cron, no sustituye el tiempo de la etiqueta de recuperación ni habilita
escrituras: sigue pendiente la fuente completa de ausencia de actividad y el
CAS real de AC-03. El cron actual no publica este dato por Issue.

El runner de preparación ofrece `observe_recent_activity([issue], port, now=...)`
para obtener una proyección mínima del inspector auténtico: Issue, estado
`RECENT_ACTIVITY`/ `UNKNOWN` y `libera_en_min` si es verificable. Limita a
**un Issue por invocación** (GETs acotados), rechaza entradas inválidas,
mantiene UUID/titular/cuerpos fuera del resultado y fija
`release_authorized=False`. Ante errores de red, pausa, carrera o cuota,
la respuesta es `UNKNOWN`, plazo ausente y cero escrituras. Es una API
inyectable y offline: **aún no está conectada al cron**, no recopila evidencia
negativa de inactividad, no constituye aceptación AC-03 ni ejecuta la
transición mutante.

## Evidencia que un colector futuro deberá probar

- Identidad canónica del Issue, reserva V3 actual, UUID, titular, claim,
  \`trabajo/issue-N\` y SHA auténtico de rama; paginación completa de
  comentarios de Issue, PRs, reviews y checks/runs, sin 403 ni huecos.
- Último commit real de la rama y comentarios atribuibles al titular,
  cronología de la etiqueta recuperación emitida por bot confiable,
  y regreso o recuperación del titular, sin confiar en timestamps del
  payload del Issue ni fechas Git futuras.
- Estado cerrado de protección: \`live\`, \`CHANGES_REQUESTED\` vigente,
  CI del titular ejecutándose, PR abierto con conflicto o review
  bloqueante; con duda, no mutar.
- Kill switch global Factory #767 canónico y RUNNING, fase de construcción
  obtenida de fuente autenticada, y cuota REST >=20%.
- Lock distribuido común con coordinación, doble lectura **bajo lock** de
  UUID, estado/HEAD, actividad, reviews, checks, switch y rate-limit.
  La lectura previa nunca equivale a un compare-and-swap de GitHub.
- Persistencia auditada de la liberación: marker V3 \`active:false\` con
  el mismo UUID, aceptación y claims originales; anotación de motivo,
  último SHA y evidencia, \`estado: disponible\` sin borrar la rama,
  y reconciliación idempotente si falla una escritura intermedia.

**Nota de compatibilidad QA:** el flujo actual de \`/tomar\` **NO**
re-adopta automáticamente una rama huérfana conservada: con branch existente
y reserva V3 \`active:false\`, \`reserve_work\` devuelve el error que exige
\`/adoptar-contrato-huerfana\`. Por tanto la adopción operativa documentada
es **EXPLÍCITA**, con actor autorizado, contrato V3 comprobado y lock
compartido; no prometer «/tomar adopta». Una modificación de ese comando
exigiría una tarea y reserva separadas sobre \`scripts/coordinar_trabajo.py\`,
que este Issue no reclama.

La re-adopción usa el contrato existente
\`/adoptar-contrato-huerfana\` **solo tras desactivación inequívoca** de
la reserva previa. No inferir que \`/tomar\` puede adoptar una rama huérfana
sin esa etapa.

## Bloqueo de AC-03: CAS real entre GitHub Issues y Coordinación

**Estado:** diseño de integración pendiente, no funcionalidad operativa. Esta
sección no modifica el marker de aceptación, la reserva V3, el coordinador ni
el permiso de escritura del cron.

### Garantías disponibles (y cuáles no)

- En `.github/workflows/coordinacion-trabajo.yml` los comandos /tomar,
  /liberar y la recuperación usan el grupo
  `factory-coordination-${{ github.repository_id }}`, con
  `cancel-in-progress: false`. La auditoría programada comparte ese grupo;
  sus ejecuciones de PR utilizan otro. Es exclusión entre *esas ejecuciones*,
  no un lock arbitrario adquirible desde Python ni un CAS de Issues. Mantener
  una cola no destructiva y verificar la procedencia del workflow antes de
  escribir es imprescindible.
- Las lecturas condicionales `If-None-Match` de GitHub REST son para GET.
  GitHub documenta que las peticiones condicionales sobre POST/PATCH/PUT/DELETE
  no están soportadas salvo indicación expresa del endpoint. Por ello un
  GET + comparación local + PATCH del Issue **no es CAS atómico**, aun con
  dos lecturas y `updated_at` estable.
- GitHub GraphQL **`updateRefs`** sí ofrece un `RefUpdate.beforeOid`
  que condiciona atómicamente el cambio de una referencia Git al OID previo.
  Es una primitiva candidata para un journal/fence duradero de transiciones,
  **no** un CAS de etiquetas/comentarios. No asumir que toda mutación de Issues
  respeta ese fence. No usar el HEAD de la rama de trabajo como candado ni
  hacer force-push para adquirirlo.

Referencias oficiales: [REST y solicitudes condicionales](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api),
[GraphQL Git: updateRefs/beforeOid](https://docs.github.com/en/graphql/reference/git) y
[Actions concurrency](https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency).

### Contrato necesario antes de implementar Port.lock/append/status

1. **Escritor común**: Coordinación y liberador deben acordar el mismo
   journal/fence y la misma exclusión. Adaptar al escritor canónico
   `scripts/coordinar_trabajo.py` para respetar ese protocolo **requiere un
   claim/contrato propio**, pues no está dentro de los ocho paths reservados
   por #1175. Ninguna versión parcial de este PR puede suplantarlo.
2. **Adquisición demostrable**: recibir el contexto autenticado de ejecución
   de Actions desde la entrada canónica `main`, comprobar grupo y repo ID,
   y ejecutar una transición de `beforeOid` a `afterOid` *reales* sin
   `force`. Un error de precondición, respuesta incompleta, 403/429 o
   timeout devuelve UNKNOWN; nunca se asume posesión del lock por un
   objeto `with` local ni por una variable de entorno sin autenticar.
3. **Lectura con atribución**: demostrar ausencia de actividad del *agente
   titular*, no meramente del login `pl0n3r` compartido por otras sesiones.
   Los timestamps editables del autor de un commit y los resultados
   `commits?since=` no demuestran ausencia de pushes; una ventana parcial,
   sesión no atribuible o paginación incompleta producen UNKNOWN.
4. **Precondición bajo exclusión**: #767 CLOSED/RUNNING en su URL absoluta,
   `construccion`, presupuesto efectivo >=20 %, último marker bot y
   `reservation_id`, HEAD de rama, contrato de aceptación/claim pin,
   Issue/etiquetas, comentarios completos, nota y evento de recuperación,
   reviews/CI/push del titular revalidados. Si cualquiera cambia, no mutar.
5. **Commit y reconciliación**: tras acreditar el fence y el estado exacto,
   registrar un ID idempotente de operación en el journal; publicar a través
   de un escritor autorizado el marker V3 de bot `active:false` (mismo UUID
   y pins), transicionar la etiqueta a `estado: disponible`, releer y
   comprobar terminalidad. Una caída entre comentario y etiqueta mantiene
   `partial/UNKNOWN`: reanudar solo con el mismo ID y nuevo fence validado,
   sin segundo marker y sin perder la rama huérfana.
6. **Pruebas contractuales**: dos ejecutores concurrentes con el mismo
   `beforeOid` (solo uno vence), cambio externo de UUID/HEAD/claim bajo
   carrera, recuperación del titular entre lecturas, lock sin procedencia,
   escritor de Coordinación que ignora fence, fallo después del comentario,
   reintento idempotente, 403/429, eventos históricos ambiguos y kill switch
   PAUSED. AC-03 debe ejercer la ruta REAL y verificar la ausencia de doble
   escritura, no simplemente crear el método con el nombre exigido.

**Criterio de salida:** hasta que ambos escritores participen del protocolo
atómico, exista una fuente verificable de inactividad del titular y un dry-run
autenticado muestre los negativos, `LeaseGithubPort.read/lock/append/status`
siguen `PortNotArmed`. Feature flag OFF, cero POST/PATCH/DELETE del cron,
PR DRAFT, y ninguna aceptación/merge/go-live por inferencia. Esta restricción
es de seguridad de la funcionalidad, no un fallo que deba ignorar `Validar`.

## Criterios y puertas para activar

- AC-01: decisor y negativos 29/30/39/40/49/50 min, quota 19/20%,
  datos ausentes, PAUSED, fase live, CHANGES_REQUESTED, CI activo.
- AC-02: compatibilidad del test existente de coordinación, que evita
  robar reservas sin evidencia temporal válida.
- Preparación ya comprobada: cron de 10 minutos, modo PR offline,
  censo GET-only con doble comprobación de #767, serialización de workflows
  y pruebas de decisiones/carreras con fakes. Ninguna parte escribe en GitHub.
- Bloqueos pendientes: prueba autoritativa de ausencia de push/comentarios/
  actividad y CI del titular durante 30+10 min; `Port.read` íntegro,
  `Port.lock` compartido real, escrituras CAS idempotentes con prueba de
  aceptación AC-03, 403/429 y relectura de notas/etiquetas bajo lock;
  observación de dry-run real, todas las gates exact-HEAD verdes y revisión
  de seguridad antes de habilitar cualquier mutación.
- No habilitar release, auto-merge, movimiento de \`v1\`, deploy ni live
  mediante este trabajo.

**Reversión:** revertir el PR de preparación elimina decisor, tests y esta
guía, sin modificar estado remoto de reserva alguno.
