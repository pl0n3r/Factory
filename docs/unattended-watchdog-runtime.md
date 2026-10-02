# Runtime programado del watchdog desatendido

Estado: **scheduler operativo, efectos limitados a alertas propias**.

## Frecuencia y permisos

`.github/workflows/unattended-watchdog.yml` corre cada **15 minutos** y también admite `workflow_dispatch`.

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

El runtime acepta un JSON opcional con `--input` que contiene `guard` y `evidence` con sus shapes canónicos. Si no existe input canónico, falta config/evidencia o aparece UNKNOWN/stale, el resultado es **BLOCKED** y se crea una alerta explícita. Nunca se transforma ausencia de evidencia en ALLOW.

## Idempotencia y propiedad

Cada alerta creada contiene:

`<!-- factory-unattended-watchdog-alert {"version":1,"fingerprint":"..."} -->`

El runtime solo considera propia una Issue abierta con título `[AUTO][WATCHDOG]`, autor `github-actions[bot]` y exactamente un marker válido. Un fingerprint activo ya abierto no se duplica; markers ambiguos, claves JSON duplicadas o `version=true` se ignoran y nunca autorizan cerrar una Issue.

Por seguridad, las alertas previas solo se cierran cuando 4C devuelve `ALLOW`; una lectura inválida o BLOCKED nunca se usa para cerrar evidencia anterior.

El runtime no edita/cierra Issues ajenos, PRs, releases ni reservas. La búsqueda incluye alertas propias abiertas y cerradas: si un fingerprint resuelto reaparece, se reabre la misma Issue en vez de crear un duplicado histórico.

Antes de la primera escritura, el runtime relee Factory#767 con el parser canónico del kill switch. Cualquier estado distinto de `RUNNING`, lectura inválida o marker ambiguo produce cero mutaciones.

## Reversión

1. deshabilitar o revertir `.github/workflows/unattended-watchdog.yml`;
2. conservar las alertas abiertas como evidencia;
3. revertir los cinco paths de Factory#769 si se retira la capacidad.

No es necesario tocar 4B/4C para revertir este runtime.
