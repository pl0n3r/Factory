# Modo desatendido seguro — contrato operativo canónico

Estado: **aprobado por el dueño · Tramo 4A · contrato, no runtime**.

Este documento define la semántica que deben respetar los slices posteriores del
modo desatendido seguro. No implementa schedulers, circuit breakers, watchdogs,
resúmenes ni automatismos de producción. GitHub, los contratos de HEALTH/smoke,
las reservas y las puertas humanas existentes siguen siendo autoridad.

## 1. Principios de autoridad

1. El modo desatendido seguro **no amplía autoridad**.
2. Ninguna clasificación, SLO, watchdog, resumen o señal automática transforma
   una acción prohibida o gated en una acción autorizada.
3. UNKNOWN, stale, evidencia contradictoria o configuración ausente **fallan
   cerrado**; nunca equivalen a GREEN.
4. Go-live, gasto/pagos, borrado irreversible, cambios destructivos, secretos,
   credenciales, datos reales/personales y cualquier producción que requiera
   backup previo conservan exactamente sus puertas vigentes.
5. Un rollback automático futuro solo podrá actuar sobre artefactos/configuración
   reversibles dentro de autoridad ya concedida. Nunca hará rollback destructivo
   de datos a ciegas.

## 2. Clasificación de riesgo

Toda tarea se clasifica antes de ejecutar:

| Riesgo | Criterio operativo | Revisión |
| --- | --- | --- |
| **Bajo** | Cambio reversible, acotado, sin live/gasto/datos reales/secretos ni ampliación de autoridad; evidencia y rollback claros. | Revisión normal del rol primario. |
| **Medio** | Cambio transversal o cercano a runtime/operación, todavía reversible y dentro de autoridad existente. | Revisión cruzada cuando el dominio afectado lo requiera. |
| **Alto** | Seguridad/autorización, datos reales/personales, backup/restore, producción, irreversible/destructivo, release/go-live, dinero o blast radius amplio. | **Segunda pasada obligatoria por otro rol** antes de entregar, además de cualquier puerta humana ya existente. |

La clasificación de riesgo no sustituye la prioridad del dispatcher ni crea una
excepción a las reglas 1–7.

## 3. Severidad operativa S1–S3

La severidad describe impacto observado; no concede permisos adicionales.

- **S1 — crítico inmediato:** pérdida/corrupción de datos real o inminente,
  compromiso de seguridad material, indisponibilidad amplia o acción peligrosa
  irreversible en curso. **Interrumpe al dueño** y exige pausar el alcance
  afectado; una futura pausa global solo podrá activarse dentro de su contrato.
- **S2 — grave:** degradación significativa, incidente con usuarios/servicios o
  riesgo operativo serio que requiere decisión rápida pero no cumple S1.
  **Interrumpe al dueño** y prioriza reparación segura.
- **S3 — contenido:** defecto acotado sin daño material activo ni necesidad de
  decisión inmediata. **No interrumpe al dueño**; entra por la cola normal con
  evidencia y prioridad correspondiente.

Si la severidad no puede determinarse con evidencia suficiente, usa
`UNKNOWN`, falla cerrado para acciones sensibles y sigue recopilando evidencia.

## 4. Handoff `STATE`

Todo handoff entre agentes o ciclos desatendidos usa un bloque `STATE` mínimo:

```yaml
STATE:
  work_identity: "<repo>#<issue> / PR / task_key"
  repository: "<owner/repo>"
  branch: "<branch o null>"
  head_sha: "<sha exacto o null>"
  reservation_id: "<uuid o null>"
  risk: "low|medium|high|UNKNOWN"
  severity: "S1|S2|S3|UNKNOWN"
  evidence:
    - "<check/run/health/smoke/ref verificable>"
  last_state: "<último estado confirmado>"
  next_action: "<siguiente transición segura>"
  blockers:
    - "<causa + condición de desbloqueo>"
  updated_at: "<timestamp UTC>"
```

Reglas:

- no incluir secretos, tokens, passwords, credenciales, PII, datos personales ni
  payloads sensibles;
- no inventar SHA, reserva, HEALTH, smoke o decisión;
- un campo desconocido se escribe como `UNKNOWN`/`null`, no se rellena por
  inferencia;
- el handoff resume evidencia, no reemplaza GitHub ni los contratos de salud.

## 5. SLOs operativos

Los SLOs del modo desatendido son **objetivos configurables y ajustables con
evidencia**, no permisos. Cada repo puede configurar objetivos para:

- latencia de detección de HEALTH/incidente;
- freshness máxima de evidencia y `STATE`;
- latencia entre trabajo terminado y siguiente despacho;
- tiempo hasta checkpoint/pausa segura;
- tiempo hasta decisión de rollback cuando un smoke permanece rojo;
- entrega del resumen diario.

Los valores numéricos viven en configuración/evidencia del repositorio o en una
decisión explícita; este contrato **no inventa defaults de producto, gasto ni
proveedor**. Si un objetivo no está configurado, su estado es `UNKNOWN`.
Incumplir o desconocer un SLO puede degradar health/abrir reparación, pero nunca
autoriza saltar gates ni marcar GREEN.

## 6. Pausa global, circuit breakers y techos

Los slices runtime posteriores deben respetar estas reglas:

- **pausa global:** impide iniciar trabajo autónomo nuevo y lleva trabajo activo a
  un checkpoint seguro; observación, evidencia y reparación de una emergencia
  conservan su autoridad existente;
- **circuit breaker:** abre ante la condición configurada y verificable para su
  superficie; configuración ausente o contradictoria impide acción autónoma;
- **techos de uso/gasto/paralelismo:** solo usan límites declarados por la fuente
  canónica correspondiente. Nunca se infiere presupuesto ni se compra/renueva;
- **blast radius:** la acción automática más amplia permitida es la mínima
  superficie reversible que ya esté autorizada. Si no puede demostrarse, pausa;
- **smoke rojo sostenido:** habilita un futuro rollback solo cuando el rollback
  sea reversible, esté dentro de autoridad y tenga evidencia exact-SHA; si hay
  datos destructivos o autoridad dudosa, pausa y escala en vez de revertir;
- **backup:** cuando el contrato vigente exige backup previo, el modo desatendido
  no puede ejecutar la acción sin evidencia verificable del backup.

## 7. Watchdog y resumen diario

El watchdog futuro observa actividad, locks, reservations, CI/health y freshness.
No crea trabajo por sí mismo fuera de la escalera canónica. Cuando detecte
staleness o ausencia de progreso según configuración, produce evidencia y aplica
la transición segura definida por el contrato; no inventa estado.

El resumen diario debe ser compacto y contener como mínimo: frentes activos,
STATE/freshness, incidentes/S1/S2, blockers, gates humanos pendientes, cambios
integrados/revertidos y próximos pasos. Nunca incluye secretos o datos sensibles.

## 8. Simulacro controlado

El simulacro E2E solo se ejecuta después de integrar las guardas runtime y el
watchdog/resumen. Debe usar alcance controlado, reversible y sin datos reales ni
gasto no autorizado. Debe demostrar al menos: pausa, circuit breaker, techo,
handoff STATE, stale/UNKNOWN fail-closed, smoke rojo y rollback/stop seguro.

## 9. Orden serial del Tramo 4

1. **4A — contrato** (este documento): riesgo, S1–S3, STATE, SLOs, autoridad y
   blast radius.
2. **4B — guardas runtime:** pausa global, circuit breakers y techos.
3. **4C — watchdog + resumen diario:** freshness, actividad y handoffs.
4. **4D — simulacro E2E controlado:** prueba integrada y reversible.

Cada slice debe existir como leaf materializado con criterios ejecutables,
dependencias satisfechas y claims disjuntos. Un slice posterior no se ejecuta por
inferencia ni por el mero hecho de que este contrato exista.
