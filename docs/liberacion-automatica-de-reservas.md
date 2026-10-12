# Liberación automática de reservas V3 — diseño controlado (#1175)

## Qué está implementado y qué NO

Esta entrega introduce un **decisor puro, determinista y sin efectos** en
\`scripts/lease_auto_release.py\`, con regresiones en
\`tests/test_lease_auto_release.py\`. Es una **etapa de preparación**, no un
servicio de liberación activo. No invoca GitHub, no mueve branches ni altera
reservas en producción.

**No se autoriza activar un cron mutante** hasta integrar un colector auténtico
de evidencia y un ejecutor serializado, y demostrar los casos de carrera.
El workflow \`.github/workflows/liberar-reservas.yml\` está presente
como auditoría de solo lectura cada 10 minutos: ejecuta contratos locales tras
preflight de cuota >=20%; **no consulta actividad real ni modifica reservas**.
La integración autenticada/ejecutora queda pendiente de otra etapa.

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

**Aún falta** un audit trail autenticado y completo para demostrar que no hubo
push/actividad del titular durante toda la ventana, con procedencia de sesión,
más el lock/CAS compartido real y prueba de recuperación parcial. Por ello los
métodos `read/lock/append/status/recovery_note/recovery_label` del Port
siguen rechazados de forma explícita, incluso si el caller intenta activar
`mutations_authorized`. El workflow cron de 10 minutos **no importa** ese
Port y continúa solo en modo auditoría, `contents: read`, cero escrituras.
Las pruebas de este inspector no satisfacen por sí solas AC-03/04 de mutación
ni autorizan activar `FACTORY_LEASE_AUTO_RELEASE_ENABLED`.

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

## Criterios y puertas para activar

- AC-01: decisor y negativos 29/30/39/40/49/50 min, quota 19/20%,
  datos ausentes, PAUSED, fase live, CHANGES_REQUESTED, CI activo.
- AC-02: compatibilidad del test existente de coordinación, que evita
  robar reservas sin evidencia temporal válida.
- Bloqueos de implementación pendiente: colector GitHub y ejecución
  serializada con pruebas de carrera, workflow programado cada 10 min,
  permisos mínimos y revisión independiente de seguridad.
- No habilitar release, auto-merge, movimiento de \`v1\`, deploy ni live
  mediante este trabajo.

**Reversión:** revertir el PR de preparación elimina decisor, tests y esta
guía, sin modificar estado remoto de reserva alguno.
