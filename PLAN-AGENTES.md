# Plan de agentes de la fábrica

> Instrucciones del dueño (@pl0n3r) para **todo agente de IA** que trabaje en pl0n3r/Condor, pl0n3r/GrindFlow, pl0n3r/brvtal, pl0n3r/factory, pl0n3r/ControlBot o pl0n3r/AutoFactory.
> Léelo completo una vez al arrancar. Este archivo manda sobre cualquier costumbre tuya; AGENTES.md/AGENTS.md de cada repo manda en lo técnico de ese repo.

## 0. Dónde trabajar: modo dirigido o modo despachador

**Modo dirigido:** si el prompt del dueño nombra un repositorio ("trabaja en pl0n3r/Condor"), trabajas **solo ahí** hasta terminar o detenerte. No saltas a otro proyecto.

**Modo despachador:** si el prompt solo te apunta a factory (sin nombrar proyecto), eliges **tú** el proyecto que más te necesita, con este orden y tomando el **primer** caso que aplique:

1. Un producto con producción caída o no VERDE (sección 6) → ese producto.
2. Un Issue abierto de incidente (`tipo: incidente` / `type: incident` o `[AUTO]`) → su repo.
3. Una decisión del dueño ya respondida que desbloquea trabajo → su repo.
4. El Issue `prioridad: crítica` / `priority: critical` disponible más antiguo en factory, Condor, GrindFlow, BRVTAL, ControlBot o AutoFactory.
5. Lo mismo con `prioridad: alta` y después `media`.
6. Dentro de la misma prioridad, el trabajo que desbloquea más trabajo.

Reglas del despachador:
- **Nunca** tomes un repo donde otro agente tiene una reserva activa (actividad de menos de 30 minutos); pasa al siguiente candidato.
- Antes de bajar, **anuncia tu elección** como primer comentario del Issue elegido: `Despacho: elegí <repo>#<n> porque <regla N>`.
- Al bajar al proyecto, lee su AGENTES.md/AGENTS.md y sigue este plan como si te hubieran dirigido ahí.
- Al terminar ese trabajo, vuelve a aplicar el despacho desde el paso 1.
- **ControlBot (privado)** resume el estado de la fábrica; la fuente de verdad sigue siendo GitHub y los `/health` reales. No existe cabina pública.
- Mientras el MVP de ControlBot (ControlBot#3, #4 y dashboard) no exista, sus Issues críticos van justo después de los incidentes porque reducen trabajo manual del dueño.

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

## 3. Reglas de eficiencia (tiempo, tokens, costo)

| Regla | Límite |
| --- | --- |
| Commits por PR | **≤ 10** |
| Rondas de hallazgos de revisores automáticos (Sonar, CodeRabbit…) | **≤ 3**; después `estado: bloqueado` + resumen, y sigues con otra cosa |
| Intentos del mismo enfoque que falla | **≤ 2**; al tercero **cambia de enfoque** o escala con evidencia |
| Revisar CI/checks | **una vez** al terminar; **nunca polling** en bucle |
| Comentarios en GitHub | uno por hito; nada de comentarios de progreso intermedio |
| Agentes por repo | **uno** (factory admite un segundo, ver tanda 1) |

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

**En todos los repos (factory, Condor, GrindFlow, BRVTAL, ControlBot, AutoFactory):** antes de implementar, carga el **perfil completo** de cada rol desde [`pl0n3r/factory/agentes/roles/`](https://github.com/pl0n3r/factory/tree/main/agentes/roles) (`<rol>.md`) y completa su checklist en el PR; la tabla de arriba es solo el resumen. Etiqueta el Issue y el PR con cada rol asumido: `rol: <rol>` (en BRVTAL, `role: <role>` en inglés); si aún no sabes cuál, `rol: pendiente` / `role: pending`.

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
| **2** | Los épicos pl0n3r/Condor#192, pl0n3r/GrindFlow#129 y pl0n3r/brvtal#630 están cerrados como completados |
| **3** | Continua: desarrollo normal |

- Si tu repo ya cumplió su parte y otro no, **no avances**: comenta en tu épico que esperas y detente.
- `factory` solo construye en la tanda 1; después mantiene el kit.
- **Si producción de tu repo deja de estar en VERDE en cualquier momento, vuelves a la tanda 1 de tu repo antes que nada.**

### Definición de VERDE

Aplica a Condor, GrindFlow y BRVTAL y, **desde su primer despliegue, también a ControlBot**:

1. `/health` (o equivalente) responde 200 con la versión y el SHA exactos de main y, si aplica, `schema_up_to_date: true`.
2. Home, login del admin y el panel principal del admin responden sin 5xx.
3. El smoke/observador de producción pasa en su última corrida.
4. No queda ningún Issue abierto de incidente (`tipo: incidente`/`type: incident`) ni ningún `[AUTO]` de fallo de producción.
5. El último CI de main pasa.

**AutoFactory es una extensión, no un servicio web.** Su equivalente de entrega VERDE no usa `/health` ni deploy de servidor: CI del SHA exacto en verde; paquete/artefacto versionado reproducible para Chrome y Safari cuando aplique; smoke de instalación/carga sobre los navegadores soportados; cero incidentes/`[AUTO]` abiertos de la extensión; y una versión anterior instalable como reversión.

---

## 7. Decisiones del dueño vigentes (no se revierten nunca)

- Migraciones aditivas automáticas con backup en post-deploy (Condor D-054).
- Escrituras autónomas en producción durante la fase de desarrollo (Condor #185, GrindFlow #126, brvtal #628), con backup previo. **SQL destructivo o borrado irreversible siguen requiriendo autorización.**
- Sistema común de releases del kit en todos los proyectos, incluidos ControlBot y AutoFactory (en BRVTAL reemplaza a `update-release-metadata.yml`).
- Etiquetas obligatorias (tipo + prioridad + estado) en todo Issue y PR (BRVTAL en inglés).
- **ControlBot es el centro de control privado de la fábrica** (pl0n3r/ControlBot): dashboard, decisiones del dueño y orquestación viven allí; nunca se publican en GitHub Pages ni en una URL pública. AutoFactory es la extensión que integra agentes de ChatGPT web con ControlBot (AutoFactory#1).
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
- **Segundo agente opcional:** si ya hay otro agente en factory, tú solo tomas #5–#12, con archivos exclusivos `metricas/`, `seguridad/`, `docs/`, `lecciones/` y `.github/workflows/{metricas,costos,seguridad}.yml`. No tocas archivos del otro agente (abre un Issue si necesitas algo) y haces rebase sobre main antes de cada push.
- Al terminar: comenta la guía de adopción del kit v1.0.0 en Condor#192, GrindFlow#129 y brvtal#630, y detente.

---

## TANDA 2: adoptar el kit (Condor, GrindFlow, BRVTAL, ControlBot y AutoFactory)

Guía: el comentario de adopción en tu épico (Condor#192, GrindFlow#129, brvtal#630 y **ControlBot#2**).

**ControlBot y AutoFactory** adoptan el kit en esta tanda, pero **no bloquean** el paso de Condor, GrindFlow y BRVTAL a la tanda 3. En ControlBot, #2 va antes que cualquier funcionalidad. AutoFactory adopta solo capacidades compatibles con una extensión: CI JavaScript, coordinación, etiquetas, releases, política, métricas y monitoreo de artefactos; sin inventar un servidor.

1. Reemplaza CI, coordinación, etiquetas, release, observador/smoke y deploy locales por reusable workflows del kit (`uses: pl0n3r/factory/...@v1`) cuando la superficie exista. Elimina copias locales divergentes.
2. Crea `decisiones.yml` con la lista de la sección 7.
3. Adopta el núcleo común de AGENTES.md del kit y conserva solo la capa propia del proyecto.
4. En productos web y ControlBot, activa deploy con rollback, merge queue/auto-merge, métricas y monitoreo. **En AutoFactory, el equivalente es empaquetado/release versionado y reversible de la extensión; no hay deploy de servidor.**
5. Cierra como resueltos por el kit: Condor #188 y #190; GrindFlow #123, #124 y #125; brvtal #624, #625 y #627.
6. Valida con un PR de prueba que pase el CI del kit y se integre. Para productos web/ControlBot debe terminar en producción validada o rollback automático. **Para AutoFactory debe producir el artefacto exacto de la extensión, pasar smoke de instalación/carga en Chrome y Safari cuando aplique, y conservar una versión anterior instalable como rollback.**

Condor, GrindFlow, BRVTAL y ControlBot solo terminan su adopción con sus 5 puntos de VERDE. AutoFactory termina con el equivalente de extensión definido en §6. Publica la evidencia en el Roadmap/Issue canónico y detente.

---

## TANDA 3: desarrollo normal

Retoma desde tu Roadmap (Condor#1, GrindFlow#2, brvtal#533 y ControlBot#1), donde estaba antes de la auditoría, más los Issues críticos y altos:
- Condor: #183/#184 (pedidos, e-commerce y stock) y #191 (recuperación de cuenta y cambio de contraseña).
- GrindFlow: #127 (recuperación de cuenta y cambio de contraseña).
- BRVTAL: #629 (account recovery and password change) y #623 si sigue abierto.
- **ControlBot:** después de #2, MVP en este orden: #3 (aprobaciones con un clic), #4 (centro de decisiones), dashboard y dirección visual #18; luego #5–#17 según prioridad.
- **AutoFactory:** #1 (puente con ControlBot: identidad de cuenta, latido, órdenes y límites).

Elige siempre el siguiente trabajo así: **incidente de producción > prioridad crítica > alta > media**, y dentro de la misma prioridad, el que desbloquea más trabajo.
