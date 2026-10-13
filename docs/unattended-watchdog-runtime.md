# Runtime programado del watchdog desatendido

Estado: **scheduler operativo, efectos limitados a alertas propias**.

## Frecuencia y permisos

`.github/workflows/unattended-watchdog.yml` conserva la cadencia periódica existente de **cada 15 minutos** (`*/15`), admite `workflow_dispatch` y ejecuta una verificación inmediata en cada `push` a `main`. El `push` funciona como evidencia post-merge temprana; no sustituye ni aumenta la frecuencia de la vigilancia periódica.

El job `watchdog` valida `repository`, `refs/heads/main` y un evento allowlisted (`push`, `schedule` o `workflow_dispatch`) antes del primer checkout. **F1G retira el job accesorio `daily-summary` y su cron `0 13 * * *`**: un `push`, un schedule del watchdog o una ejecución manual ya no publican automáticamente el resumen diario. El watchdog de seguridad mantiene `*/15 * * * *`, sin reemplazar el resumen perdido.

Permisos:
- `contents: read`;
- `issues: write` únicamente para abrir/cerrar alertas propias;
- sin secretos nuevos, deploy, releases, producción ni datos reales;
- `concurrency` no cancela un run en progreso.

Los umbrales viven versionados en `config/unattended-watchdog.json`:

- ready sin despacho: **10 min**;
- reserva sin avance: **15 min**;
- STATE stale: **20 min**.

No existen defaults ocultos.

## Frontera con 4C

`scripts/unattended_watchdog_runtime.py` **no recalcula** política 4C. Consume un `GuardDecision` serializado y evidencia 4C, llama a `evaluate_unattended_watchdog()` y traduce la decisión a un plan cerrado de alertas.

El core `scripts/unattended_watchdog.py` sigue puro y sin I/O.

La configuración no acepta rutas CLI: el runtime lee únicamente `config/unattended-watchdog.json` desde una ruta fija derivada del propio módulo. Para pruebas/ejecución offline existe `--input-stdin`, que acepta JSON acotado por tamaño desde la entrada estándar y nunca abre una ruta suministrada por el llamador. Sin `--input-stdin`, el workflow usa GitHub en modo read-only: lista frentes `reservado/en revisión`, lee sus comentarios y delega la proyección STATE/Presence en `scripts/unattended_state_source.py` (#775); si el STATE declara rama, resuelve además su HEAD real y exige binding exacto. Si no existe una única fuente activa coherente, la entrada queda inválida y el resultado es **BLOCKED** con alerta explícita. Nunca se transforma ausencia de evidencia en ALLOW.

Todavía no existe una fuente runtime canónica para fencing/4B. En vez de fabricar un `GuardDecision(ALLOW)`, el adaptador llama al core `evaluate_unattended_guards()` con fencing ausente y consume su `BLOCKED` canónico. La Presence proveniente de #775 conserva heartbeat/capacidad en `UNKNOWN`, por lo que 4C alerta esa falta de evidencia hasta que exista una señal explícita; timestamps GitHub no se reinterpretan como heartbeat ni capacidad.

## Idempotencia y propiedad

Cada alerta creada contiene:

`<!-- factory-unattended-watchdog-alert {"version":1,"fingerprint":"..."} -->`

El runtime solo considera propia una Issue abierta con título `[AUTO][WATCHDOG]`, autor `github-actions[bot]` y exactamente un marker válido. Un fingerprint activo ya abierto no se duplica; markers ambiguos, claves JSON duplicadas o `version=true` se ignoran y nunca autorizan cerrar una Issue.

Por seguridad, una alerta previa solo se reconcilia como resuelta cuando 4C logró validar un STATE y `daily_summary.state_freshness` es exactamente `fresh`; `stale` o `unknown` nunca demuestran resolución y no cierran alertas históricas. La autoridad final puede seguir `BLOCKED`: resolver un fingerprint propio con evidencia fresh no convierte el ciclo en ALLOW ni amplía autoridad.

El runtime no edita/cierra Issues ajenos, PRs, releases ni reservas. La búsqueda incluye alertas propias abiertas y cerradas: si un fingerprint resuelto reaparece, se reabre la misma Issue en vez de crear un duplicado histórico.

El transporte queda fijado a `api.github.com` y al repositorio exacto `pl0n3r/Factory`; el HEAD solo se consulta como `trabajo/issue-N` derivado de un número validado. Antes de la primera escritura, el runtime relee Factory#767 con el parser canónico del kill switch. Cualquier estado distinto de `RUNNING`, lectura inválida o marker ambiguo produce cero mutaciones.

## F1G: resumen diario accesorio suspendido

Por la decisión del dueño en la EPIC **Factory #1296** y la hoja **#1336**,
se suspende exclusivamente el job `daily-summary` y el disparador programado
`0 13 * * *` del workflow. A partir de la integración **el dueño deja de
recibir automáticamente a las 08:00 Bogotá el resumen diario en GitHub Issues**.
No existe entrega alternativa implícita. No se ha desactivado el job
`watchdog` ni su alerta de seguridad cada 15 minutos; `push` a `main`
y `workflow_dispatch` siguen permitidos bajo sus guardas fail-closed.

Se conserva `scripts/unattended_daily_summary.py`, su método idempotente
`publish_once`, la lógica de informes y las pruebas offline. Que el motor
permanezca disponible **no autoriza** a un cron o agente a publicar por otro
canal sin autoridad nueva y sin el kill switch canónico #767. El número de
archivos workflow sigue igual: **31 antes y 31 después**, porque se eliminó
un job del archivo existente en vez de borrar el workflow.

**Rollback exclusivo F1G:** revertir el commit de integración de #1336, o
reponer exactamente en `.github/workflows/unattended-watchdog.yml` el
segundo schedule `0 13 * * *`, el job `daily-summary` con permisos previos
y la exclusión de ese cron en el `if` del job `watchdog`. Revertir asimismo
los tests y este runbook de F1G, **sin revertir** Factory#815, F1A–F1F,
la vigilancia `*/15 * * * *`, ni el guard #767. Un rollback vuelve a habilitar
la entrega antigua: revalidar condiciones humanas y CI antes de fusionarlo.

## Reversión

Para revertir únicamente el repair de **Factory#815**, se revierten sus tres paths reclamados: `.github/workflows/unattended-watchdog.yml`, `tests/test_unattended_watchdog_runtime.py` y `docs/unattended-watchdog-runtime.md`. Eso elimina el trigger post-merge y devuelve la cadencia anterior sin tocar 4B/4C ni las alertas existentes.

Si se retira por completo la capacidad introducida por Factory#769:

1. deshabilitar o revertir `.github/workflows/unattended-watchdog.yml`;
2. conservar las alertas abiertas como evidencia;
3. revertir los cinco paths originales de Factory#769.

No es necesario tocar 4B/4C para ninguna de las dos reversiones.


## Trabajo ready sin timestamp canónico

El colector observa también `estado: disponible`. Si existe al menos un Issue
ready pero GitHub no aporta un timestamp canónico de `ready_since`, el runtime
no inventa edad ni fija `work_ready=false`: entrega evidencia incompleta a 4C
y conserva `BLOCKED`/alerta fail-closed. Una futura fuente explícita puede
cerrar esa frontera sin cambiar la política 4C.
