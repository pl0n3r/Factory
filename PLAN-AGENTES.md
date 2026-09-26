# Plan de agentes de la fábrica

> Instrucciones del dueño (@pl0n3r) para **todo agente de IA** que trabaje en pl0n3r/Condor, pl0n3r/GrindFlow, pl0n3r/brvtal, pl0n3r/factory, pl0n3r/ControlBot, pl0n3r/AutoFactory o pl0n3r/FactoryRunner.
> Léelo completo una vez al arrancar. Este archivo manda sobre cualquier costumbre tuya; AGENTES.md/AGENTS.md de cada repo manda en lo técnico de ese repo.

## 0. Dónde trabajar: modo dirigido o modo despachador

**Modo dirigido:** si el prompt del dueño nombra un repositorio ("trabaja en pl0n3r/Condor"), trabajas **solo ahí** hasta terminar o detenerte. No saltas a otro proyecto.

**Modo despachador:** si el prompt solo te apunta a factory (sin nombrar proyecto), eliges **tú** el proyecto que más te necesita, con este orden y tomando el **primer** caso que aplique:

**Cola canónica de productos:** Condor, GrindFlow, BRVTAL y FactoryRunner. **ControlBot y AutoFactory quedan fuera del despacho automático de producto**: ControlBot es el control plane y AutoFactory una herramienta local/manual; ambos solo se trabajan en modo dirigido o cuando bloquean explícitamente a uno de los cuatro productos. Factory mantiene el kit cuando ese mantenimiento bloquea la cola.

1. Un producto con producción caída o no VERDE (sección 6) → ese producto.
2. Un Issue abierto de incidente (`tipo: incidente` / `type: incident` o `[AUTO]`) → su repo.
3. Una decisión del dueño ya respondida que desbloquea trabajo → su repo.
4. El Issue `prioridad: crítica` / `priority: critical` disponible más antiguo en Condor, GrindFlow, BRVTAL o FactoryRunner; si no hay candidato y un Issue de Factory bloquea a esos productos, toma Factory.
5. Lo mismo con `prioridad: alta` y después `media`.
6. Dentro de la misma prioridad, el trabajo que desbloquea más trabajo.

Reglas del despachador:
- Una reserva activa conserva exclusividad para trabajo no planificado. Solo pueden coexistir líneas cuando el candidato y cada línea activa relevante están materializados por el orquestador, sus dependencias están completadas y los claims de paths son disjuntos. Si Factory no puede demostrarlo, falla cerrado y pasa al siguiente candidato. Tras perder una carrera de reserva, vuelve a evaluar el despacho sobre el estado actual.
- Antes de bajar, **anuncia tu elección** como primer comentario del Issue elegido: `Despacho: elegí <repo>#<n> porque <regla N>`.
- Al bajar al proyecto, lee su AGENTES.md/AGENTS.md y sigue este plan como si te hubieran dirigido ahí.
- Al terminar ese trabajo, vuelve a aplicar el despacho desde el paso 1.
- **ControlBot (privado)** resume el estado de la fábrica; la fuente de verdad sigue siendo GitHub y los `/health` reales. No existe cabina pública.
- ControlBot y AutoFactory no compiten por prioridad dentro de la cola canónica; se atienden por modo dirigido o por dependencia explícita de un producto.

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

Toda puerta nueva con marker `factory-human-gate` debe incluir también los campos simples para ControlBot: `title_simple`, `summary_simple`, `why_recommended`, `blocks` y, por opción, `effect`, `pros`, `cons`, `risk`, `cost`, `reversible`. El parser conserva compatibilidad con puertas históricas sin esos campos, pero los agentes no deben crear nuevas puertas en el formato antiguo.

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

- Si tu repo ya cumplió su parte y otro no, **no avances**: comenta en tu épico que esperas y detente.
- `factory` solo construye en la tanda 1; después mantiene el kit.
- **Si producción de tu repo deja de estar en VERDE en cualquier momento, vuelves a la tanda 1 de tu repo antes que nada.**

### Definición de VERDE

Aplica a Condor, GrindFlow y BRVTAL. **FactoryRunner** usa el mismo principio: antes de su primer runtime desplegado exige CI exact-main Node, tests/build reproducibles, release versionada y cero incidentes; desde su primer despliegue añade `/health` equivalente, smoke y SHA exacto.

1. `/health` (o equivalente) responde 200 con la versión y el SHA exactos de main y, si aplica, `schema_up_to_date: true`.
2. Home, login del admin y el panel principal del admin responden sin 5xx.
3. El smoke/observador de producción pasa en su última corrida.
4. No queda ningún Issue abierto de incidente (`tipo: incidente`/`type: incident`) ni ningún `[AUTO]` de fallo de producción.
5. El último CI de main pasa.

**ControlBot y AutoFactory no forman parte del gate automático de productos.** Conservan sus contratos de salud/entrega cuando se trabajen en modo dirigido, sin bloquear la cola Condor/GrindFlow/BRVTAL/FactoryRunner.

---

## 7. Decisiones del dueño vigentes (no se revierten nunca)

- Migraciones aditivas automáticas con backup en post-deploy (Condor D-054).
- Escrituras autónomas en producción durante la fase de desarrollo (Condor #185, GrindFlow #126, brvtal #628), con backup previo. **SQL destructivo o borrado irreversible siguen requiriendo autorización.**
- Sistema común de releases del kit en los cuatro productos canónicos: Condor, GrindFlow, BRVTAL y FactoryRunner (en BRVTAL reemplaza a `update-release-metadata.yml`). ControlBot y AutoFactory conservan sus contratos cuando se trabajen en modo dirigido.
- Etiquetas obligatorias (tipo + prioridad + estado) en todo Issue y PR (BRVTAL en inglés).
- **ControlBot es el centro de control privado de la fábrica** (pl0n3r/ControlBot): dashboard, decisiones y orquestación viven allí. **FactoryRunner** es el execution plane autónomo de la cola canónica. **AutoFactory** queda como herramienta local/manual independiente y no se modifica por la cola automática.
- **D-060 — administración de staff:** ControlBot administra únicamente cuentas de staff/administración de cada producto mediante el contrato común `/ops/staff`; los clientes finales permanecen y se administran en su propio producto. Las altas son por invitación y los resets los envía el producto; ControlBot nunca define ni recibe contraseñas/tokens. El contrato falla cerrado sin credencial configurada, exige firma/anti-replay/allowlist/rate limit/auditoría y no permite borrado físico.
- Roles profesionales por tarea (factory#2).
- Factory no genera trabajo para el dueño.
- **Uso de Hostinger (D-059), para todos los agentes conectados al MCP remoto de Hostinger, incluidos Claude y GPT:** mirar y diagnosticar es libre; cambiar DNS, bases de datos, cron o despliegues exige backup previo y dejarlo registrado en el Issue; borrar sitios, bases de datos o archivos requiere autorización explícita del dueño; **comprar, renovar o cambiar planes y pagos nunca lo hace un agente** (es una decisión de dinero del dueño).
- **Datos personales siempre documentados** (Ley 1581): si un cambio agrega, modifica o elimina un dato personal, un formulario que lo recoja o un servicio externo que lo reciba (analítica, Sentry, email, pagos…), actualiza `datos.yml` del proyecto **en el mismo PR** y regenera los documentos cuando exista el generador (factory#54). Si cambia una finalidad, entra un dato sensible o un proveedor nuevo recibe datos, abre una puerta `legal` para el dueño. Los datos del responsable quedan como `[COMPLETAR POR EL DUEÑO]` hasta la puerta `go-live`.

Si una regla escrita en un repo contradice esta lista, **gana esta lista**; corrige la regla del repo en el mismo PR.

---

## 8. Antipatrones prohibidos

- ❌ Abrir un PR paralelo sobre un Issue reservado activo (<30 min).
- ❌ Repetir el mismo arreglo esperando otro resultado (patrón de "6 hotfixes seguidos").
- ❌ Declarar "listo" sin evidencia en producción.
- ❌ Silenciar un test, un linter o un hallazgo de seguridad para pasar el CI.
- ❌ Comentarios de "sigo trabajando…", "esperando CI…".
- ❌ Pedir al dueño algo que puedes decidir tú según AGENTES.md.
- ❌ Crear Issues o PRs sin etiquetas completas.

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

**FactoryRunner** adopta Factory v1 desde su primer PR funcional: Node.js 24/TypeScript, CI `stack: node`, coordinación, etiquetas, aceptación, roles, política, privacidad y release. ControlBot y AutoFactory quedan fuera de esta cola automática; sus adopciones previas se conservan y se trabajan solo en modo dirigido.

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
- **ControlBot / AutoFactory:** solo modo dirigido o dependencia explícita; no compiten en la cola automática de producto.

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

La arquitectura/protocolo Living Software y sus fronteras de evidencia previstas para #143 están integradas y endurecidas:

- **#209** — Autonomy authority + evidencia canónica: ✅ cerrado; authority scope estructurado y Fitness/Risk se recomputan desde inputs fuente.
- **#211** — Factory Lab promotion provenance: ✅ cerrado; la promoción revalida provenance y evidencia fuente antes de producir una decisión confiable.
- **#213** — Growth/Pruning source evidence: ✅ cerrado; growth/pruning recompone candidatos desde evidencia fuente verificable.
- **#215** — Repair human authority + immunity provenance: ✅ cerrado; Repair/Immune validan estructura, scope e integridad sin ampliar ejecución.
- **#221** — retry de renovación v2: ✅ cerrado; successor determinista y revalidación de contrato/task/HEAD evitan sesiones stale.
- **#223** — provenance confiable de Repair/Immune: ✅ cerrado; decisiones e incidentes se resuelven desde fuentes/handles confiables y append-only, no desde payloads autocertificados.

El cierre de **#143** significa que la **arquitectura/protocolo Living Software está integrada y endurecida** dentro de la autoridad ya existente. **No significa producción autónoma irrestricta**, no convierte Repair o Promotion en ejecución automática y no elimina ninguna puerta humana.

Dinero, legal, datos reales/personales, borrado irreversible, publicación/live y cualquier otra decisión reservada siguen requiriendo sus puertas humanas canónicas. Ante evidencia inválida, fuente no confiable o conflicto de autoridad, Living Software continúa fallando cerrado.
