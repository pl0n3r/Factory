# Plan de agentes de la fábrica

> Instrucciones del dueño (@pl0n3r) para **todo agente de IA** que trabaje en pl0n3r/Condor, pl0n3r/GrindFlow, pl0n3r/brvtal, pl0n3r/factory, pl0n3r/ControlBot, pl0n3r/AutoFactory o pl0n3r/FactoryRunner.
> Léelo completo una vez al arrancar. Este archivo manda sobre cualquier costumbre tuya; AGENTES.md/AGENTS.md de cada repo manda en lo técnico de ese repo.

## Tarjeta de arranque del agente

> **Misión:** ejecutar el trabajo correcto con evidencia real de GitHub/producción, sin pedirle al dueño que reconstruya el estado y sin inventar readiness.

Consulta [ESTADO.md](ESTADO.md) como **vista rápida derivada** del estado vigente. Es una vista generada/fail-closed; GitHub, los `/health` y los smoke/observer reales conservan la autoridad operativa.

### Interruptor global antes de cualquier mutación

Antes del primer comentario de despacho, `/tomar`, branch, PR o escritura de código de **cada ciclo**, abre exactamente:

`https://api.github.com/repos/pl0n3r/Factory/issues/767`

y valida el único marker cerrado `factory-unattended-kill-switch` con el contrato de `scripts/unattended_kill_switch.py`.

- `RUNNING` es el único estado que no añade pausa: produce `global_pause=false` y las demás guardas 4B siguen mandando.
- `PAUSED`, fuente ausente/ilegible, Issue/creador inesperado, marker ausente/duplicado o contenido inválido producen pausa fail-closed; **cero mutaciones**. `user.login` identifica al creador del Issue y no demuestra quién hizo la última edición del body.
- Si no es verificablemente `RUNNING`, responde una sola línea al dueño y detente: `PAUSADO: kill switch global no está en RUNNING (<razón>).`
- Un agente nunca cambia el marker por iniciativa propia. Solo una instrucción explícita del dueño para pausar/reanudar autoriza editarlo.
- El switch impide **nuevo trabajo/mutaciones**; no mata procesos remotos que ya estuvieran ejecutándose.

### Preflight de capacidades

Antes de despachar, confirma que puedes **abrir URLs exactas**, **leer GitHub** y **comentar Issues** usando el conector autenticado de GitHub o navegación/API equivalente. Si falta cualquiera de esas capacidades, responde una sola línea y detente:

`PARADO: falta acceso a GitHub para abrir URLs exactas, leer estado y comentar Issues.`

No pidas al dueño el estado del repo, no sustituyas una URL exacta por búsqueda general y no entres en un bucle de disculpas/reintentos.

### Fuentes exactas para obtener estado

**Preferida:** conector autenticado de GitHub. Si solo existe acceso HTTP público, usa las rutas canónicas siguientes y conserva sus mayúsculas/minúsculas:

| Repo | Issues abiertos | PRs abiertos |
| --- | --- | --- |
| Factory | `https://api.github.com/repos/pl0n3r/Factory/issues?state=open` | `https://api.github.com/repos/pl0n3r/Factory/pulls?state=open` |
| Condor | `https://api.github.com/repos/pl0n3r/Condor/issues?state=open` | `https://api.github.com/repos/pl0n3r/Condor/pulls?state=open` |
| GrindFlow | `https://api.github.com/repos/pl0n3r/GrindFlow/issues?state=open` | `https://api.github.com/repos/pl0n3r/GrindFlow/pulls?state=open` |
| BRVTAL | `https://api.github.com/repos/pl0n3r/brvtal/issues?state=open` | `https://api.github.com/repos/pl0n3r/brvtal/pulls?state=open` |
| ControlBot | `https://api.github.com/repos/pl0n3r/ControlBot/issues?state=open` | `https://api.github.com/repos/pl0n3r/ControlBot/pulls?state=open` |
| AutoFactory | `https://api.github.com/repos/pl0n3r/AutoFactory/issues?state=open` | `https://api.github.com/repos/pl0n3r/AutoFactory/pulls?state=open` |
| FactoryRunner | `https://api.github.com/repos/pl0n3r/FactoryRunner/issues?state=open` | `https://api.github.com/repos/pl0n3r/FactoryRunner/pulls?state=open` |

Para CI usa `https://api.github.com/repos/<owner>/<repo>/actions/runs?per_page=20`; para archivos abre la ruta exacta del repositorio o su equivalente raw/API. HEALTH y smoke se verifican contra el contrato real de cada producto; una etiqueta o un tag nunca sustituyen la observación productiva.

La API REST pública **sin autenticar** tiene un límite primario de **60 solicitudes por hora por IP**. Con varios agentes, usa el conector autenticado para evitar compartir ese presupuesto público y reducir carreras.

### Árbol de despacho vigente

No redefine prioridades: aplica la sección 0 y la evidencia viva, en este orden resumido:

`reglas 1–4 de la sección 0 → gate de tanda → reglas 5–7 → desempate de la regla 7`; toma siempre el primer caso aplicable.

Si no existe trabajo `ready`, aplica la **escalera no ociosa ya integrada por Factory#699/#702** en la sección 0; no conviertas un bloqueo en ejecutable ni inventes un backlog paralelo.

**Firma de ciclo:** `Despacho (<id>)`. Usa un identificador trazable del frente/ciclo; el primer comentario del Issue conserva el formato canónico de la sección 0.

### Prohibiciones esenciales

- No inventar estado, HEALTH, checks, reservas, decisiones ni producción.
- No escribir en una línea con reserva ajena ni saltar claims/dependencias.
- No tratar `available` como autoridad para saltar tandas, puertas humanas o go-live.
- No gastar, publicar/live, usar datos reales ni tomar decisiones reservadas al dueño.
- No hacer polling de CI; una lectura terminal al final del cambio.
- Tras cerrar/liberar un frente, volver a ejecutar el árbol de despacho.

---

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
- **Preflight exact-main antes de reapertura o repair:** antes de reabrir un Issue cerrado como `completed`/`duplicate`, o de materializar un repair/decomposición porque un AC parece faltar, relee el Issue y su contrato vigente, resuelve el SHA exacto actual de `main` y verifica los AC y paths reclamados contra el árbol actual de `main` y los PRs fusionados relevantes.
- Si `main` ya satisface el contrato, **no reabras el Issue, no ejecutes `/tomar`, no crees `trabajo/issue-N` ni abras PR**. Publica únicamente una reconciliación con evidencia exact-main que identifique el SHA y el PR/commit que ya cubre el contrato.
- **Preflight exact-main antes de cierre/reconciliación terminal:** si vas a cerrar/cancelar un Issue o PR, marcar `completed`/`duplicate`/`not_planned` o liberar su lease porque supones que `main` u otro PR ya satisface el contrato, ejecuta el mismo preflight contra el SHA exacto actual de `main`, AC y paths reclamados y PRs fusionados relevantes.
- Si `main` **no** satisface el contrato, **no cierres ni canceles el Issue/PR, no marques `completed`/`duplicate`/`not_planned` y no liberes la lease por “ya satisfecho”**. Conserva la línea activa y publica la evidencia exact-main que demuestra el delta pendiente.
- Si durante cualquiera de estos preflights otra línea cambia el Issue, la rama, `main` o un PR relevante, descarta el snapshot previo y **relee el estado actual antes de cualquier mutación**. Una lectura stale nunca autoriza reapertura, reserva, branch, PR, cierre/cancelación terminal ni liberación por reconciliación.
- Este guard existe por los patrones observados `#699 → #703/#704/#705` y `#741/#763`: el primero materializó trabajo ya integrado desde un snapshot viejo; el segundo cerró trabajo activo porque una reconciliación stale atribuyó a `#762` un contrato que exact-main todavía no contenía. El preflight debe fallar cerrado en ambos sentidos.
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
- **D-068 / Factory#796 — autorización permanente acotada:** una propuesta `product-direction` puede tratarse como opción A sin `/decidir` solo cuando evidencia explícita demuestra kill switch `RUNNING`, producción del repo en VERDE, aceptación ejecutable y ausencia de cualquiera de los límites human-only de D-068. La materialización deja `Materialización bajo autorización permanente del dueño (#796)` con `proposal_sha256`; nunca fabrica un journal humano. Fuera de esos límites se conserva la puerta humana con opción segura y el dispatcher continúa con otro frente.
- **Runway D-068:** mientras quede roadmap dentro de la autorización, cada repo busca mantener al menos **3 hojas elegibles**; quedar por debajo exige una causa explícita y auditable (dependencia, límite de autoridad o ausencia de trabajo acotado), nunca una hoja inventada. Con contexto D-068, el dispatcher repone runway cuando quedan 0–2 hojas; sin ese contexto conserva el trigger histórico de Carril 2 (0–1).
- **Inventario inicial D-068:** los temas enumerados en Factory#796 §4 permanecen como **iniciativas explícitas** hasta que un tramo los materialice con aceptación ejecutable. Su causa canónica mientras sigan en ese estado es `pendiente de materialización product-direction` o, si aplica, la puerta humana concreta que los limita. Una iniciativa no es un leaf disponible y **no cuenta para el piso de 3** hasta existir como Issue leaf con contrato ejecutable.
- **Carril 3 — preparación del live:** se puede mantener evidencia y checklist de readiness, pero ningún agente cambia la fase ni ejecuta go-live. El live sigue siendo una decisión exclusiva del dueño.
- El trigger del carril 2 es idempotente por repositorio. **Sin contexto D-068**, conserva el comportamiento histórico: con **2 o más leaves elegibles** existe trabajo suficiente. **Con contexto D-068 válido**, el piso de runway manda: **3 o más** son suficientes y 0–2 intentan reponer. Si ya existe una puerta abierta, solo puede reutilizarse bajo D-068 cuando el `proposal_sha256` conocido coincide; un mismatch falla cerrado y no materializa. No introduce scheduler ni backlog paralelo.
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
- **D-068 — autonomía nocturna acotada (Factory#796):** mientras siga activa, las puertas `product-direction` dentro de límites seguros usan A con provenance del Issue y SHA de propuesta, sin esperar al dueño. **Nunca** incluye go-live, gasto/compras/planes, proveedores de pago o traducción, Backblaze/offsite real, datos reales/personales, secretos/credenciales, destructivo/irreversible, producción sin backup verificado, decisiones de descarte/rediseño de GrindFlow, puertas legal/privacidad vigentes o leaves sin aceptación ejecutable. D-064 sigue mandando fuera de esos límites. Riesgo alto exige segunda pasada por otro rol antes de entregar; UNKNOWN falla cerrado.
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

## TANDAS 1 y 2 — historial archivado

**ARCHIVADO · ya cumplido · no aplicar.** Las tareas históricas de TANDA 1 y TANDA 2
se conservan en [docs/archivo/plan-agentes-tandas-1-2.md](docs/archivo/plan-agentes-tandas-1-2.md)
solo para auditoría. El estado vigente está en [ESTADO.md](ESTADO.md) y el gate
operativo continúa definido por la sección 6 de este plan. El gate histórico de
TANDA 2 sigue siendo: Condor#192, GrindFlow#129, brvtal#630 y **FactoryRunner#1**.
No reabras ni ejecutes trabajo histórico desde el archivo.

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


## Modo desatendido seguro — contrato aprobado (Tramo 4)

El dueño aprobó el **modo desatendido seguro** como contrato operativo. El detalle
canónico vive en
[docs/unattended-safe-mode.md](docs/unattended-safe-mode.md). Este contrato
**no amplía autoridad**: clasificar riesgo/severidad o cumplir un SLO nunca
autoriza go-live, gasto, acciones irreversibles, uso de credenciales/datos reales
ni producción sin backup previo cuando ya aplica esa puerta.

Resumen obligatorio:

- riesgo **bajo / medio / alto**; todo cambio de riesgo alto requiere **segunda
  pasada de revisión por otro rol** antes de entregar;
- severidad **S1 / S2 / S3**; solo **S1 y S2 interrumpen al dueño**; S3 entra por
  la cola normal con evidencia;
- cada handoff usa un bloque **`STATE`** mínimo, trazable y sin secretos,
  credenciales, PII ni payloads sensibles;
- cuando exista trabajo activo con reserva canónica, cada handoff/checkpoint material publica además en el Issue de trabajo exactamente un marker cerrado `factory-state` con `version=1` y el objeto STATE v4A; repo/work_identity/reservation/branch deben coincidir con la evidencia GitHub vigente;
- el marker `factory-state` es **evidencia derivada**, no autoridad: no sustituye HEALTH, checks, smoke, la reserva confiable ni el kill switch; si un campo no puede demostrarse, usa UNKNOWN/null donde el schema lo permita y nunca inventes heartbeat/capacidad para hacer GREEN;
- los **SLOs son objetivos configurables y ajustables con evidencia**; ausencia,
  stale/UNKNOWN o incumplimiento nunca se convierten en GREEN ni saltan gates;
- pausa global, circuit breakers, techos configurados de uso/gasto/paralelismo,
  blast radius, rollback seguro ante smoke rojo sostenido, watchdog de actividad,
  resumen diario, **Informe de la noche** idempotente y simulacro controlado están aprobados como contrato, pero su
  runtime se implementa únicamente por slices materializados y seriales; el Informe de la noche usa marker propio, se publica una sola vez por fecha local y no sustituye el resumen diario;
- orden posterior: **guardas runtime de pausa/disyuntor/techos → watchdog +
  resumen → simulacro E2E controlado**. No materialices ni ejecutes un slice
  posterior antes de completar el anterior.

Ante duda de autoridad, configuración ausente o evidencia inconsistente, falla
cerrado y conserva las puertas humanas existentes.

---

## 9. Living Software: ciclo operativo canónico

Factory integra **Living Software a nivel de arquitectura y protocolo**. La
arquitectura/protocolo Living Software está integrada y endurecida dentro de la
autoridad ya existente; **no amplía autoridad**, **no sustituye puertas humanas**
y no autoriza producción autónoma irrestricta.

El contrato, lifecycle, handoffs y el hardening histórico **#209–#227** viven en
[docs/factory-living-software.md](docs/factory-living-software.md), que es la
referencia canónica para ese detalle. `PLAN-AGENTES.md` conserva únicamente el
límite operativo: Dinero, legal, datos reales/personales, borrado irreversible y
publicación/live siguen sujetos a sus puertas humanas vigentes. Ante evidencia
inválida, fuente no confiable o conflicto de autoridad, Living Software
**continúa fallando cerrado**.
