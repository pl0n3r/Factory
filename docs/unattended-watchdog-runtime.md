# Runtime programado del watchdog desatendido

Estado: **scheduler operativo, efectos limitados a alertas propias**.

## Frecuencia y permisos

`.github/workflows/unattended-watchdog.yml` corre cada **15 minutos** en los slots UTC **07/22/37/52**, admite `workflow_dispatch` y ejecuta una verificación inmediata en cada `push a `main``. El `push` funciona como evidencia post-merge temprana; no sustituye la vigilancia periódica.

El job `watchdog` valida `repository`, `refs/heads/main` y un evento allowlisted (`push`, `schedule` o `workflow_dispatch`) antes del primer checkout. El job `daily-summary` sigue restringido exclusivamente al schedule diario `0 13 * * *`; un `push` nunca publica el resumen.

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
