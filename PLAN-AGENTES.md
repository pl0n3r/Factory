# Plan de agentes de la fábrica

> Instrucciones del dueño (@pl0n3r) para **todo agente de IA** que trabaje en pl0n3r/Condor, pl0n3r/GrindFlow, pl0n3r/brvtal, pl0n3r/factory, pl0n3r/ControlBot, pl0n3r/AutoFactory o pl0n3r/FactoryRunner.
> Léelo completo una vez al arrancar. Este archivo manda sobre cualquier costumbre tuya; AGENTES.md/AGENTS.md de cada repo manda en lo técnico de ese repo.

## 0. Dónde trabajar: modo dirigido o modo despachador

**Modo dirigido:** si el prompt del dueño nombra un repositorio ("trabaja en pl0n3r/Condor"), trabajas **solo ahí** hasta terminar o detenerte. No saltas a otro proyecto.

**Modo despachador:** si el prompt solo te apunta a factory (sin nombrar proyecto), eliges **tú** el proyecto que más te necesita, con este orden y tomando el **primer** caso que aplique:

**Cola automática canónica:** Factory, Condor, GrindFlow, BRVTAL, ControlBot, AutoFactory y FactoryRunner. Los siete repositorios son elegibles para despacho automático. Su inclusión en la cola no altera sus responsabilidades arquitectónicas: Factory gobierna el kit, ControlBot es el control plane privado, FactoryRunner es el execution plane, AutoFactory sigue siendo una herramienta local/manual y Condor/GrindFlow/BRVTAL son productos.

1. Un repositorio con HEALTH degradado según su contrato real de operación → ese repo.
2. Un Issue abierto de incidente (`tipo: incidente` / `type: incident` o clasificación AUTO equivalente) → su repo.
3. Una reparación activa válida de HEALTH/INCIDENT → continuar ese frente antes de abrir trabajo paralelo.
4. Una decisión del dueño ya respondida que desbloquea trabajo → su repo.

**Gate de tanda antes de prioridades:** antes de aplicar las reglas 5–7, determina la primera tanda global no terminada según la sección 6. El trabajo normal de producto que dependa de una tanda posterior no es ready aunque tenga etiqueta `available` / `estado: disponible`, aunque `/tomar` haya sido solicitado o aunque exista una reserva activa: esos estados no sobreescriben este gate. HEALTH, incidentes, reparaciones activas y decisiones del dueño ya resueltas conservan su preempción. La excepción explícita de la sección 6 para mantenimiento, gobernanza y hardening transversal de Factory también se conserva.

5. El Issue ready de `prioridad: crítica` / `priority: critical` mejor posicionado por el desempate de la regla 7 entre los siete repositorios.
6. Lo mismo con `prioridad: alta` y después `media`, aplicando el mismo desempate.
7. Dentro de la misma prioridad: desbloqueo → impacto transversal → continuidad → menor riesgo/esfuerzo → antigüedad.

Reglas del despachador:
- Una reserva activa conserva exclusividad para trabajo no planificado. Solo pueden coexistir líneas cuando el candidato y cada línea activa relevante están materializados por el orquestador, sus dependencias están completadas y los claims de paths son disjuntos. Si Factory no puede demostrarlo, falla cerrado y pasa al siguiente candidato. Tras perder una carrera de reserva, vuelve a evaluar el despacho sobre el estado actual.
- Antes de bajar, **anuncia tu elección** como primer comentario del Issue elegido: `Despacho: elegí <repo>#<n> porque <regla N>`.
- Al bajar al proyecto, lee su AGENTES.md/AGENTS.md y sigue este plan como si te hubieran dirigido ahí.
- Al terminar ese trabajo, vuelve a aplicar el despacho desde el paso 1.
- **ControlBot** (repositorio público, acceso al panel restringido; D-062) resume el estado de la fábrica; la fuente de verdad sigue siendo GitHub y los `/health` reales. No existe cabina pública.
- Factory, ControlBot y AutoFactory compiten dentro de la misma cola automática con las mismas reglas de readiness y prioridad. Su naturaleza arquitectónica no les da prioridad artificial ni los excluye.

### Escalera cuando no existe trabajo `ready`

Que el ranking normal no encuentre candidato **no significa que el agente quede ocioso**. Aplica, en este orden y sin desplazar las reglas 1–7:

1. reconciliar bloqueos cuya condición declarada ya esté satisfecha con evidencia verificable; el desbloqueo debe ser idempotente y citar la evidencia;
2. tomar trabajo de calidad/seguridad/hardening/deuda/rendimiento ya materializado y seguro;
3. tomar relleno **curado**, reversible, de riesgo/esfuerzo bajos, sin gasto ni ampliación de autoridad; cada filler debe declarar esas propiedades de forma explícita y el tope absoluto es **2 en paralelo**; metadata ausente, gasto, riesgo/esfuerzo alto o un límite mayor a 2 fallan cerrado;
4. proponer un único tramo `product-direction` cuando corresponda, incluidos los casos de cola totalmente bloqueada en cualquiera de los siete repos;
5. si no existe ninguna acción segura, publicar el motivo concreto y qué evidencia/decisión falta. La parada silenciosa queda prohibida.

El dispatcher conserva `select_next` como ranking fail-closed y usa la escalera como envolvente: un fallback nunca convierte un candidato bloqueado en ejecutable ni preempte trabajo normal. El tiempo entre fin de trabajo y siguiente `Despacho:` se mide por agente/repo; superar el umbral operativo degrada Quality Health hasta que exista un siguiente despacho.

### Política de tres carriles hasta live — Factory#683

- **Carril 1 — auto-alimentado:** calidad, seguridad, hardening, deuda técnica y rendimiento siguen entrando por señales verificables ([AUTO], vulnerabilidades, bugs, CI y Quality Health) y se despachan sin puerta de dirección de producto.
- **Carril 2 — dirección de producto:** cuando Factory, Condor, GrindFlow, BRVTAL, ControlBot, AutoFactory o FactoryRunner tengan **como máximo 1 leaf elegible** —incluido el caso de cero leaves porque todo esté bloqueado—, el dispatcher propone anticipadamente un único siguiente tramo con objetivo, leaves, criterios de aceptación ejecutables y dependencias. La propuesta usa una puerta product-direction; mientras no exista aprobación explícita, no se materializa ningún leaf como estado: disponible.
- Un leaf `product-direction` aprobado no puede etiquetarse `available` / `estado: disponible` hasta que su body materializado pase el mismo preflight de aceptación usado por `/tomar`; si el contrato generado falla, el dispatcher falla cerrado y no publica readiness.
- **Carril 3 — preparación del live:** se puede mantener evidencia y checklist de readiness, pero ningún agente cambia la fase ni ejecuta go-live. El live sigue siendo una decisión exclusiva del dueño.
- El trigger del carril 2 es idempotente por repositorio: si ya existe una puerta de dirección abierta, no crea otra; con **2 o más leaves elegibles** considera que existe trabajo suficiente y tampoco abre una puerta anticipada. No introduce scheduler ni backlog paralelo.
- Tras crear una puerta product-direction, el despachador debe **releer las puertas abiertas y reconciliar post-create** antes de devolver control: si hubo creadores concurrentes, conserva la instancia válida más antigua por created_at (desempate por número de Issue) y cierra las posteriores como duplicadas sin concederles autoridad ni materializar leaves.
- Factory, Condor, GrindFlow, BRVTAL, ControlBot, AutoFactory y FactoryRunner pueden mantener una puerta de dirección de siguiente tramo en paralelo; el desempate global existente sigue mandando. En ControlBot, AutoFactory y FactoryRunner la puerta no salta bloqueos de autoridad, live, gasto ni proveedores: solo propone trabajo dentro de las decisiones vigentes. El paralelismo no inventa cuotas: CI/API/cuentas se observan mediante Factory#584 y AutoFactory#62 y conservan límites, claims, reservas y gates actuales.
- Backblaze B2 no se provisiona antes de live; la decisión queda registrada como código junto con la opción A vigente de AutoFactory#79.

Bloqueos intencionales que el carril nuevo **no** puede saltar:

| Frente | Causa | Condición de desbloqueo |
| --- | --- | --- |
| ControlBot#45 | Backup real aplazado hasta live. | Orden explícita del dueño de salir a live y autoridad correspondiente. |
| ControlBot#182 | Recovery real depende del proveedor/credenciales de live. | Orden explícita del dueño de salir a live y provisión autorizada. |
| Factory#305 | El contrato puro puede evolucionar, pero el backup real B2 sigue fuera de construcción. | Orden explícita del dueño de salir a live; sin gasto ni credenciales antes. |
| AutoFactory#70 | SonarCloud mantiene Reliability C y AutoFactory#79 eligió A: no parchear por inferencia. | nueva evidencia SonarCloud directa/canónica sobre un SHA pertinente o nueva decisión explícita que sustituya A. |
| Condor#389 | La preparación puede avanzar, pero el go-live permanece cerrado. | Orden explícita del dueño de salir a live. |

## Tu misión en una línea

**Entregar cambios que funcionen en producción, con el mínimo de tiempo, tokens y ruido, sin romper nada y sin pedirle trabajo al dueño.**

---

## 1. Arranque (máximo 10 minutos, en paralelo)

Haz estas lecturas **en paralelo** (varias llamadas a la vez), no una por una:

1. AGENTES.md / AGENTS.md del repo (completo).
2. SHA de `main`, PRs abiertos, Issues con `estado: reservado`/`status: reserved` y los que llevan `prioridad: crítica`/`priority: critical`.
3. Estado real de producción: `/health` y el último run del smoke/observador.
4. `lecciones/` y `decisiones.yml` si ya existen (memoria de la fábrica).

Luego **determina tu tanda** (sección 6) y **escribe tu plan en 3–7 viñetas** como primer comentario del Issue que tomes. Nada de código antes de tener el plan.

---

## 2. Protocolo de trabajo: el bucle que debes seguir

```
ENTENDER → PLANIFICAR → EJECUTAR EN PASOS PEQUEÑOS → VERIFICAR → ENTREGAR → DEJAR MEMORIA
```

### Entender
- Reproduce el problema o confirma el estado **con evidencia** (comando, HTTP, test) antes de cambiar nada. Nunca asumas: verifica en el código y en producción.
- Si el Issue no tiene criterios de aceptación verificables, **escríbelos tú** en el Issue antes de implementar (formato: "Dado… cuando… entonces…" o nombre del test).

### Planificar
- Busca primero si **ya existe** algo que resuelva la mitad: reutiliza antes de escribir.
- Elige la **solución más simple que cumple** los criterios. Si dudas entre dos, elige la más fácil de revertir.
- Estima: si el cambio supera ~400 líneas o toca más de un área, **pártelo** en varios PRs independientes.

### Ejecutar
- Cambios pequeños y coherentes. Un commit = una idea.
- **Agrupa localmente** y haz push por bloque lógico, no por cada arreglo.
- Imita el estilo del código que rodea: nombres, comentarios, idioma.

### Verificar (antes de hacer push)
- Corre **localmente** las pruebas relevantes al cambio (no todo el suite si no hace falta).
- Autorrevisión obligatoria con esta lista:
  - [ ] ¿Cumple cada criterio de aceptación? (evidencia por criterio)
  - [ ] ¿Qué pasa con entradas vacías, nulas, duplicadas, concurrentes, muy grandes?
  - [ ] ¿Filtra secretos, PII o SQL en logs/respuestas?
  - [ ] ¿Rompe algo en producción si el deploy queda a medias?
  - [ ] ¿Hay test que falle si alguien revierte este cambio?

### Entregar
- PR con la plantilla de la sección 5. Revisa el CI **una sola vez** al terminar.

### Dejar memoria
- Si algo te costó más de lo esperado o encontraste una trampa, agrégala a `lecciones/` (o como comentario en el Issue si aún no existe) en 3 líneas: **qué pasó, por qué, cómo evitarlo**.

---

### Renovación explícita de un contrato v2 durante un PR

Si los criterios de aceptación de un Issue con reserva v2 necesitan evolucionar, no edites silenciosamente el fingerprint ni uses `/migrar-contrato` (reservado a v1 legacy). El dueño de la sesión actual debe modificar los criterios humanos y el marker máquina juntos, validar que forman un contrato ejecutable y comentar `/renovar-contrato <UUID_ACTUAL>` en el Issue. El coordinador compara el contrato anterior con el nuevo, verifica owner, UUID, rama canónica, HEAD y único PR, publica checks fallidos sobre el HEAD exacto del **contrato anterior**, registra nueva sesión/fingerprint y sincroniza metadata del mismo PR. Hasta obtener evidencia nueva sobre el contrato renovado, los checks previos no autorizan merge.

Ante fallo o carrera, se conserva la sesión anterior o se falla cerrado con checks invalidados; no se destruyen rama ni PR. `/liberar` + `/tomar` sigue disponible para abandonar el trabajo, pero cierra PR y rama. Nunca usar `/renovar-contrato` para ocultar una revisión fallida ni para eludir una decisión humana.

El retry de renovación v2 usa un **successor UUID determinista** derivado de Issue, UUID anterior, fingerprint de aceptación, fingerprint de task y HEAD exacto. La reconciliación es idempotente para los cuatro estados parciales `old/old`, `old/new`, `new/old` y `new/new`: nunca crea una tercera identidad por repetir el mismo comando. Antes de aceptar un successor histórico, el coordinador recomputa acceptance/task/HEAD actuales; cualquier drift o una tercera sesión ganadora falla cerrado y se preserva. La invalidación canónica se expresa con **un único `Validar`** en failure sobre el HEAD anterior; los retries no fabrican checks adicionales para aparentar progreso.

## 3. Reglas de eficiencia (tiempo, tokens, costo)

| Regla | Límite |
| --- | --- |
| Commits por PR | **≤ 10** |
| Rondas de hallazgos de revisores automáticos (Sonar, CodeRabbit…) | **≤ 3**; después `estado: bloqueado` + resumen, y sigues con otra cosa |
| Intentos del mismo enfoque que falla | **≤ 2**; al tercero **cambia de enfoque** o escala con evidencia |
| Revisar CI/checks | **una vez** al terminar; **nunca polling** en bucle |
| Comentarios en GitHub | uno por hito; nada de comentarios de progreso intermedio |
| Agentes por repo | **uno por defecto**; para tareas planificadas, tantos como nodos listos con dependencias satisfechas y claims disjuntos demuestre el DAG |

Trucos para gastar menos:
- **Lee solo lo necesario:** busca con `grep`/búsqueda de código y abre los fragmentos relevantes, no archivos completos de miles de líneas.
- **Paraleliza** lecturas y comandos independientes.
- **No re-derives** lo que ya está en el Issue, el PR o `lecciones/`.
- **Salida concisa:** en comentarios y PRs, resultado primero, detalle después; tablas en vez de párrafos.
- Si un revisor automático marca algo **no válido**, respóndelo una vez con la razón técnica y no cambies el código por complacer a la herramienta.
- **Progreso visible y estado compacto:** actualizaciones solo en transiciones significativas (qué se confirmó y qué sigue), nota `STATE` por hitos y separación prompt/integración; formato y ejemplos en [`docs/conversacion-agentes.md`](docs/conversacion-agentes.md).

---

## 4. Juicio profesional: actúa como el experto que la tarea exige

Antes de empezar, decide **qué rol(es)** exige la tarea y declara cada uno en el PR. Piensa como ese profesional:

| Rol | Pregunta que siempre se hace |
| --- | --- |
| Ingeniería de software | ¿Es lo más simple que funciona y es fácil de cambiar mañana? |
| DBA | ¿Índices, locks, migración expand/contract, backup y restore probados? |
| SRE / infraestructura | ¿Qué pasa si falla a la mitad? ¿Hay rollback? ¿Cómo me entero? |
| Seguridad | ¿Quién puede abusar de esto? ¿Qué secreto o dato se expone? |
| QA | ¿Qué test fallaría si esto se rompe? ¿Probé el caso borde? |
| UX / diseño | ¿Estados vacío/carga/error/sin permiso? ¿Móvil? ¿Accesible (WCAG AA)? |
| Producto | ¿Resuelve el problema real del usuario o solo el síntoma? |
| Marketing / SEO / contenido | ¿Mensaje claro? ¿Metadatos, rendimiento y analítica sin PII? |

Cambios de riesgo (esquema, seguridad, deploy, UX pública) → haz una **segunda pasada con otro rol** antes de entregar.

**En todos los repos (factory, Condor, GrindFlow, BRVTAL, FactoryRunner, ControlBot, AutoFactory):** antes de implementar, carga el **perfil completo** de cada rol desde [`pl0n3r/factory/agentes/roles/`](https://github.com/pl0n3r/factory/tree/main/agentes/roles) (`<rol>.md`) y completa su checklist en el PR; la tabla de arriba es solo el resumen. Etiqueta el Issue y el PR con cada rol asumido: `rol: <rol>` (en BRVTAL, `role: <role>` en inglés); si aún no sabes cuál, `rol: pendiente` / `role: pending`.

---

## 5. Formatos obligatorios

### PR
```
## Qué y por qué
<2–4 líneas: problema, causa raíz y solución>

Rol(es): <ej. SRE + DBA>
Closes #N · Reserva: <UUID>

## Criterios de aceptación
- [x] <criterio 1> — evidencia: <comando/test/URL>
- [x] <criterio 2> — evidencia: …

## Riesgo y reversión
<qué puede fallar y cómo se revierte>

## Fuera de alcance
<lo que NO hace este PR>
```

### Escalamiento al dueño (solo producto, dinero, legal, datos reales de clientes o salir a live)
```
🧭 DECISIÓN NECESARIA
Contexto: <1–2 líneas>
Opciones: A) … B) …
Recomiendo: <A/B> porque <razón>
Si no hay respuesta, sigo con: <opción por defecto segura>
```

Toda puerta nueva con marker `factory-human-gate` debe incluir también `explain_simple` en la raíz y en cada opción, explicando la pregunta y las respuestas como a alguien de 12 años, sin jerga ni presión, además de los campos simples para ControlBot: `title_simple`, `summary_simple`, `why_recommended`, `blocks` y, por opción, `effect`, `pros`, `cons`, `risk`, `cost`, `reversible`. El parser conserva compatibilidad con puertas históricas sin esos campos, pero los agentes no deben crear nuevas puertas en el formato antiguo.

Nunca te quedes esperando: deja la opción por defecto y sigue con otro trabajo.

### Cuando te bloqueas (tras 2 intentos fallidos)
```
⛔ BLOQUEADO
Intenté: 1) … → resultado  2) … → resultado
Causa probable: <con evidencia>
Siguiente enfoque propuesto: <diferente de los anteriores>
```

---

## 6. Cómo determinar tu tanda

Toma la **primera** tanda cuya condición de "terminada" no se cumple:

| Tanda | Terminada cuando |
| --- | --- |
| **1** | pl0n3r/Condor#1, pl0n3r/GrindFlow#2 y pl0n3r/brvtal#533 tienen el comentario "🟢 PRODUCCIÓN EN VERDE"/"🟢 PRODUCTION GREEN" con evidencia **y** pl0n3r/factory tiene el tag `v1.0.0` |
| **2** | Los épicos pl0n3r/Condor#192, pl0n3r/GrindFlow#129, pl0n3r/brvtal#630 y pl0n3r/FactoryRunner#1 están cerrados como completados |
| **3** | Continua: desarrollo normal |

- Para Condor, GrindFlow, BRVTAL y FactoryRunner, si el repo ya cumplió su parte de la tanda y otro no, **no avances a trabajo dependiente de la tanda siguiente**: comenta en tu épico que esperas y detente.
- Esta regla de espera por tanda **no bloquea a Factory**: mantenimiento del kit, gobernanza, hardening y capacidades transversales permanecen elegibles cuando sean el candidato ready de mayor prioridad.
- **Si producción de tu repo deja de estar en VERDE en cualquier momento, vuelves a la tanda 1 de tu repo antes que nada.**

### Definición de VERDE

Aplica a Condor, GrindFlow y BRVTAL. **FactoryRunner** usa el mismo principio: antes de su primer runtime desplegado exige CI exact-main Node, tests/build reproducibles, release versionada y cero incidentes; desde su primer despliegue añade `/health` equivalente, smoke y SHA exacto.

1. `/health` (o equivalente) responde 200 con la versión y el SHA exactos de main y, si aplica, `schema_up_to_date: true`.
2. Home, login del admin y el panel principal del admin responden sin 5xx.
3. El smoke/observador de producción pasa en su última corrida.
4. No queda ningún Issue abierto de incidente (`tipo: incidente`/`type: incident`) ni ningún `[AUTO]` de fallo de producción.
5. El último CI de main pasa.

**ControlBot y AutoFactory forman parte de la cola automática**, pero conservan contratos de salud/entrega propios. La ausencia de un gate de producción idéntico al de los productos no los excluye: se evalúan con evidencia adecuada a su arquitectura y estado real.

---

## 7. Decisiones del dueño vigentes (no se revierten nunca)

- Migraciones aditivas automáticas con backup en post-deploy (Condor D-054).
- Escrituras autónomas en producción durante la fase de desarrollo (Condor #185, GrindFlow #126, brvtal #628), con backup previo. **SQL destructivo o borrado irreversible siguen requiriendo autorización.**
- Sistema común de releases del kit en Condor, GrindFlow, BRVTAL y FactoryRunner (en BRVTAL reemplaza a `update-release-metadata.yml`). ControlBot y AutoFactory conservan sus contratos técnicos propios, pero ambos siguen siendo elegibles para despacho automático.
- Etiquetas obligatorias (tipo + prioridad + estado) en todo Issue y PR (BRVTAL en inglés).
- **ControlBot es el centro de control de la fábrica (panel de acceso restringido; repositorio público, D-062)** (pl0n3r/ControlBot): dashboard, decisiones y orquestación viven allí. **FactoryRunner** es el execution plane autónomo. **AutoFactory** permanece como herramienta local/manual independiente. Los tres, junto con Factory, Condor, GrindFlow y BRVTAL, son elegibles para la cola automática; elegibilidad de despacho no significa dependencia arquitectónica.
- **D-060 — administración de staff:** ControlBot administra únicamente cuentas de staff/administración de cada producto mediante el contrato común `/ops/staff`; los clientes finales permanecen y se administran en su propio producto. Las altas son por invitación y los resets los envía el producto; ControlBot nunca define ni recibe contraseñas/tokens. El contrato falla cerrado sin credencial configurada, exige firma/anti-replay/allowlist/rate limit/auditoría y no permite borrado físico.
- **D-062 — repositorios públicos:** los siete repositorios de la fábrica son públicos; «privado» significa acceso restringido a paneles y datos, no visibilidad del repo. Nada de secretos, tokens ni datos de clientes en repos.
- **D-063 — legal no bloquea bajo atestación de construcción segura:** solo con `phase=construccion`, nada live y sin datos reales de clientes, confirmados por `d063_attestation.nothing_live=true` y `d063_attestation.no_real_customer_data=true`, la puerta legal o de privacidad es informativa y no detiene el trabajo. Ausencia, `false`, `null`, invalidez o `phase=live` falla cerrado. La revisión jurídica y `go-live` se resuelven antes de salir a live, que sigue requiriendo decisión explícita del dueño.
- Roles profesionales por tarea (factory#2).
- Factory no genera trabajo para el dueño.
- **Uso de Hostinger (D-059), para todos los agentes conectados al MCP remoto de Hostinger, incluidos Claude y GPT:** mirar y diagnosticar es libre; cambiar DNS, bases de datos, cron o despliegues exige backup previo y dejarlo registrado en el Issue; borrar sitios, bases de datos o archivos requiere autorización explícita del dueño; **comprar, renovar o cambiar planes y pagos nunca lo hace un agente** (es una decisión de dinero del dueño).
- **Datos personales siempre documentados** (Ley 1581): si un cambio agrega, modifica o elimina un dato personal, un formulario que lo recoja o un servicio externo que lo reciba (analítica, Sentry, email, pagos…), actualiza `datos.yml` del proyecto **en el mismo PR** y regenera los documentos cuando exista el generador (factory#54). Si cambia una finalidad, entra un dato sensible o un proveedor nuevo recibe datos, abre una puerta `legal`. Solo es **informativa** cuando D-063 está explícitamente atestiguada en `datos.yml`; si falta cualquier precondición, permanece bloqueante y falla cerrado. Los datos del responsable quedan como `[COMPLETAR POR EL DUEÑO]` hasta la puerta `go-live`.

Si una regla escrita en un repo contradice esta lista, **gana esta lista**; corrige la regla del repo en el mismo PR.

---

## 8. Antipatrones prohibidos

- ❌ Abrir un PR paralelo sobre un Issue reservado activo (<30 min).
- ❌ Repetir el mismo arreglo esperando otro resultado (patrón de "6 hotfixes seguidos").
- ❌ Declarar "listo" sin evidencia en producción.
- ❌ Silenciar un test, un linter o un hallazgo de seguridad para pasar el CI.
- ❌ Comentarios de "sigo trabajando…", "esperando CI…".
- ❌ Mensajes de progreso vacíos («sigo revisando», «déjame pensar») o narrar cada tool call.
- ❌ Pedir al dueño algo que puedes decidir tú según AGENTES.md.
- ❌ Crear Issues o PRs sin etiquetas completas.
- ❌ Poner `estado: bloqueado` sin un comentario con la **causa** y la **condición de desbloqueo**, o bloquear varios Issues en masa sin ese comentario en cada uno. Quien cierra la causa desbloquea; un bloqueo sin causa vigente se restaura a `estado: disponible`. Lección: `factory-20260929-bloqueos-sin-causa`.

---

## TANDA 1

### Condor: producción en verde
- Crítico: PR #205 (backup previo por PDO, Closes #200) destraba las migraciones de D-054 que dejaron `/`, `/health`, `/marcela-arias-tienda` y el centro de control en 500. Termínalo e intégralo; no abras otro frente sobre el backup.
- Tras el deploy, verifica los 5 puntos de VERDE, incluyendo `/marcela-arias-tienda` y el centro de control.
- Al terminar: comenta "🟢 PRODUCCIÓN EN VERDE" en Condor#1 con la evidencia de los 5 puntos y detente.

### GrindFlow: producción en verde
- Crítico: el Production Smoke (#121, #73). El usuario sintético ya se aprovisiona (#130, #132); termina el PR #133 (bootstrap OIDC) o el arreglo que falte hasta que el smoke pase. Si falta una variable en el `.env` de producción, documéntala en el PR y en #121.
- Al terminar: comenta "🟢 PRODUCCIÓN EN VERDE" en GrindFlow#2 con la evidencia y detente.

### BRVTAL: production green (English)
- Production health is already OK; confirm the 5 GREEN points. The authenticated production smoke currently shows *skipped*: make it actually run and pass.
- Finish #623 / PR #626 (slow DISCADMIN) if still open: release the PHP session lock on read-only requests, one shared `/auth`, memoized `information_schema` checks, paginated listings; record before/after dashboard timing.
- When done: comment "🟢 PRODUCTION GREEN" on brvtal#533 with the evidence and stop.

### factory: construir el kit
- Orden: #14 arranque → #1 kit v1 completo (ci, deploy con rollback, release, observar, coordinación, etiquetas es/en, política con `decisiones.yml` y tope de 3 rondas) → #2 roles → #3 orquestador → #4 especificaciones ejecutables → #5 evaluación de agentes → #7 costos → #8 memoria (`lecciones/`) → #9 puertas humanas → #6, #10, #11, #12 → `template/`.
- **Extrae de lo que ya funciona en pl0n3r/Condor** en vez de inventar. Todo configurable por inputs: stack (Symfony, Laravel, PHP plano), dominio, fuente de versión, idioma de etiquetas y fase `construccion|live`.
- Acciones fijadas a SHA, mínimo privilegio, `concurrency` y filtros `if:`.
- Mantén el README al día: la tabla "Estado actual" refleja lo que ya existe.
- Publica `v1.0.0` cuando #1 a #14 estén cerrados y el template pase su propio CI.
- **Paralelismo en factory:** no hay un cupo fijo de “segundo agente”. El trabajo no planificado conserva una sola línea activa; las tareas materializadas por el orquestador pueden coexistir únicamente con dependencias satisfechas y claims de paths disjuntos, y cada agente debe reevaluar el DAG si pierde una carrera de reserva.
- Al terminar: comenta la guía de adopción del kit v1.0.0 en Condor#192, GrindFlow#129 y brvtal#630, y detente.

---

## TANDA 2: adoptar el kit (Condor, GrindFlow, BRVTAL y FactoryRunner)

Guía: el comentario de adopción en tu épico (Condor#192, GrindFlow#129, brvtal#630 y **FactoryRunner#1**).

**FactoryRunner** adopta Factory v1 desde su primer PR funcional: Node.js 24/TypeScript, CI `stack: node`, coordinación, etiquetas, aceptación, roles, política, privacidad y release. ControlBot y AutoFactory también permanecen elegibles para la cola automática, aunque no formen parte del gate histórico de adopción de estos cuatro productos.

1. Reemplaza CI, coordinación, etiquetas, release, observador/smoke y deploy locales por reusable workflows del kit (`uses: pl0n3r/factory/...@v1`) cuando la superficie exista. Elimina copias locales divergentes.
2. Crea `decisiones.yml` con la lista de la sección 7.
3. Adopta el núcleo común de AGENTES.md del kit y conserva solo la capa propia del proyecto.
4. En Condor, GrindFlow y BRVTAL activa deploy con rollback, merge queue/auto-merge, métricas y monitoreo. En FactoryRunner activa CI Node, coordinación, release, métricas y health del runner; no inventes deploy de browser/runtime hasta que exista un target ejecutable.
5. Cierra como resueltos por el kit: Condor #188 y #190; GrindFlow #123, #124 y #125; brvtal #624, #625 y #627; FactoryRunner #1 cuando su bootstrap y CI exacto estén integrados.
6. Valida con un PR de prueba que pase el CI del kit y se integre. Condor, GrindFlow y BRVTAL deben terminar en producción validada o rollback automático. FactoryRunner debe terminar con CI Node exact-main, tests/build reproducibles, release versionada y cero incidentes; cuando tenga runtime desplegado, añade health/smoke exactos.

Los cuatro productos solo terminan su adopción con evidencia publicada en su Roadmap/Issue canónico.

---

## TANDA 3: desarrollo normal

Retoma desde tu Roadmap (Condor#1, GrindFlow#2, brvtal#533 y FactoryRunner#1), donde estaba antes de la auditoría, más los Issues críticos y altos:
- Condor: #183/#184 (pedidos, e-commerce y stock) y #191 (recuperación de cuenta y cambio de contraseña).
- GrindFlow: #127 (recuperación de cuenta y cambio de contraseña).
- BRVTAL: #629 (account recovery and password change) y #623 si sigue abierto.
- **FactoryRunner:** continúa su roadmap #1: runner identity/heartbeat → órdenes/eventos → adapters programáticos → browser execution compatible con el target de hosting.
- **Factory / ControlBot / AutoFactory:** continúan en desarrollo normal dentro de la misma cola automática, respetando su roadmap, arquitectura, readiness y prioridad reales.

Elige siempre el siguiente trabajo así: **incidente de producción > prioridad crítica > alta > media**, y dentro de la misma prioridad, el que desbloquea más trabajo.


---

## 9. Living Software: ciclo operativo canónico

Factory integra **Living Software a nivel de arquitectura y protocolo**. Esta integración no amplía autoridad, no sustituye puertas humanas y no autoriza promoción autónoma nueva por sí sola.

### Ciclo continuo

El ciclo operativo de alto nivel es:

`observe → remember → learn → propose → shadow → experiment → validate → adopt_or_reject → measure → prune → rollback`

`adopt_or_reject` es la vista operativa del estado máquina `promote_or_reject` definido por Constitution/Evolution Engine. Adoptar significa aceptar una evolución **dentro de la autoridad ya existente**; nunca significa conceder permisos nuevos.

Handoffs canónicos:

1. **Project DNA** descubre señales verificables del software.
2. **Context Compiler** limita el contexto de misión.
3. **Definition-of-Done Compiler** deriva evidencia exigible.
4. **Risk Compiler** deriva riesgo, blast radius y controles.
5. **Fitness Engine** compara candidate vs baseline sin score mágico.
6. **Evolution Engine** conserva lifecycle e historia append-only.
7. **Autonomy Engine** solo reduce supervisión para authority class `operational` con Fitness/Risk recomputados desde inputs fuente.
8. **Factory Lab** evalúa en shadow contra `stable`; no ejecuta promociones.
9. **Experience Guardrails**, **Growth/Pruning** e **Immune/Repair** convierten experiencia en candidatos reversibles, sin reescribir historia ni Constitución.
10. La promoción, cuando corresponda, usa evidencia canónica y las puertas humanas ya vigentes.

### Autoridad humana y fail-closed

Living Software **no cambia** las decisiones del dueño de la sección 7. Dinero, legal, datos reales/personales, borrado irreversible, publicación/live y cualquier otra puerta humana vigente continúan requiriendo su mecanismo canónico.

Ante discrepancia entre documentación, evidencia canónica, Constitution, una decisión vigente o un hardening abierto, **gana la restricción más segura y se falla cerrado**. Un fingerprint declarado por el consumidor no reemplaza la recomputación desde inputs fuente cuando exista un validador canónico.

### Estado de hardening de fronteras de evidencia

La arquitectura/protocolo Living Software está integrada y endurecida; #227 cierra la última frontera de provenance caller-proof prevista para #143:

- **#209** — Autonomy authority + evidencia canónica: ✅ cerrado; authority scope estructurado y Fitness/Risk se recomputan desde inputs fuente.
- **#211** — Factory Lab promotion provenance: ✅ cerrado; la promoción revalida provenance y evidencia fuente antes de producir una decisión confiable.
- **#213** — Growth/Pruning source evidence: ✅ cerrado; growth/pruning recompone candidatos desde evidencia fuente verificable.
- **#215** — Repair human authority + immunity provenance: ✅ cerrado; Repair/Immune validan estructura, scope e integridad sin ampliar ejecución.
- **#221** — retry de renovación v2: ✅ cerrado; successor determinista y revalidación de contrato/task/HEAD evitan sesiones stale.
- **#223** — provenance confiable de Repair/Immune: ✅ cerrado en integridad/append-only, pero #227 corrige la procedencia autocertificable de stores caller-built.
- **#227** — provenance productivo read-only no fabricable por el caller: ✅ cerrado; Repair/Immune solo aceptan readers autenticados/read-only emitidos por el composition root.

Con #227 cerrado y sus AC verdes, **#143 puede cerrarse** declarando únicamente que la arquitectura/protocolo Living Software quedó integrada y endurecida dentro de la autoridad ya existente. **No significa producción autónoma irrestricta**, no convierte Repair o Promotion en ejecución automática y no elimina ninguna puerta humana.

Dinero, legal, datos reales/personales, borrado irreversible, publicación/live y cualquier otra decisión reservada siguen requiriendo sus puertas humanas canónicas. Ante evidencia inválida, fuente no confiable o conflicto de autoridad, Living Software continúa fallando cerrado.
