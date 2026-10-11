# Liberación automática de reservas V3 — diseño controlado (#1175)

## Qué está implementado y qué NO

Esta entrega introduce un **decisor puro, determinista y sin efectos** en
\`scripts/lease_auto_release.py\`, con regresiones en
\`tests/test_lease_auto_release.py\`. Es una **etapa de preparación**, no un
servicio de liberación activo. No invoca GitHub, no mueve branches ni altera
reservas en producción.

**No se autoriza activar un cron mutante** hasta integrar un colector auténtico
de evidencia y un ejecutor serializado, y demostrar los casos de carrera.
El archivo \`.github/workflows/liberar-reservas.yml\` queda pendiente de la
segunda etapa; el lector no debe interpretar su ausencia como un barrido activo.

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
