# FactoryRunner: execution plane canónico

Estado: vigente para Factory #167. Este documento define límites de arquitectura; no implementa el runtime de FactoryRunner #2.

## 1. Separación de autoridad

La fábrica conserva cuatro responsabilidades distintas:

- **Factory gobierna**: políticas, contratos, roles, reusable workflows y límites de autoridad.
- **ControlBot decide**: WorkItems, prioridad, dependencias, elegibilidad, scheduler, reservas, retry, presupuesto, puertas humanas y estado durable.
- **FactoryRunner ejecuta**: recibe una orden tipada, publica capabilities, ejecuta mediante adapters y devuelve eventos/evidencia saneada.
- **AutoFactory permanece independiente** como herramienta local/manual del dueño. No es dependencia, backend ni fallback de FactoryRunner.

FactoryRunner no puede crear trabajo, cambiar prioridades, resolver puertas humanas ni ampliar permissions/capabilities recibidas.

## 2. Target primario: Hostinger Shared/Web Hosting

El target primario de FactoryRunner es la infraestructura actual de `control.condorapp.com.co` en Hostinger Shared/Web Hosting.

El core debe funcionar sin presuponer:

- acceso root;
- Docker o un daemon arbitrario del sistema;
- Chrome/Chromium instalado localmente;
- puertos propios;
- WebSocket entrante;
- procesos persistentes ilimitados.

Puede apoyarse en HTTPS saliente, cron, almacenamiento permitido por el plan y, si el hosting lo habilita de forma comprobada, una aplicación Node.js administrada. Las tareas largas deben ser reanudables e idempotentes.

Las capabilities que requieran sistema operativo, navegador persistente, shell avanzado o sandbox se satisfacen mediante **adapters/backends remotos** conectados de forma saliente y autenticada. La ausencia de una capability se publica como ausencia, nunca se simula.

## 3. Protocolo estable ControlBot → FactoryRunner

El protocolo es independiente del backend físico. Un Runner en Shared Hosting y un Runner temporal en macOS reciben la misma forma de orden.

Campos mínimos de una orden:

- `order_id`
- `attempt_id`
- `generation`
- `project_id`
- `work_item_id`
- `source_ref`
- `executor_kind`
- `provider`
- `profile_alias` / `account_alias`
- `agent_config`
- `roles`
- `instructions_ref`
- `required_capabilities`
- `timeout`
- `resource_budget`
- `workspace_policy`

Las órdenes son **secret-free**. Solo contienen aliases y referencias opacas. No aceptan passwords, tokens, cookies, API keys, claves privadas ni autoridad implícita. Los secretos permanecen en un vault/secret store del execution plane y solo se resuelven dentro del adapter autorizado.

Estados/eventos mínimos: `accepted`, `started`, `heartbeat`, `progress`, `checkpoint`, `waiting_human`, `blocked`, `failed`, `completed`, `cancelled`.

## 4. Estado durable e idempotencia

ControlBot/MariaDB es la fuente de verdad durable para WorkItems, ExecutionOrders, intentos, estado y auditoría. FactoryRunner es reconstructible.

Redis, memoria local, colas efímeras o locks pueden acelerar presencia y coordinación, pero nunca son la única copia de un WorkItem ni deciden su identidad durable.

Cada `order_id` es idempotente. Cada dispatch o requeue crea un `attempt_id` nuevo y una `generation` monotónica controlada por ControlBot. La transferencia de ownership es atómica: solo el attempt vigente puede producir eventos con efecto.

Todo evento de ejecución incluye `order_id`, `attempt_id` y `generation`. ControlBot rechaza eventos de un attempt stale, aunque un Runner anterior recupere conectividad después del handoff. Cuando un adapter puede producir side effects externos, recibe la generation o un `fencing_token` equivalente y debe rechazar writes de attempts stale.

Los estados terminales tienen precedencia durable: una ejecución `completed`, `failed` o `cancelled` no puede ser reabierta por eventos tardíos de una generation anterior. Retries del mismo evento son idempotentes y requeue/recovery nunca permiten dos owners efectivos simultáneos.

Un Runner que reinicia:

1. vuelve a publicar identidad/capabilities y heartbeat;
2. consulta o recibe el estado durable desde ControlBot;
3. reanuda solo si la policy y el estado permiten continuar;
4. no crea una segunda ejecución para el mismo intento sin autorización explícita del control plane.

La pérdida de heartbeat habilita requeue/handoff desde ControlBot, pero no concede autoridad al Runner anterior: el nuevo attempt/generation invalida su ownership previo. El Runner no se autoasigna trabajo.

## 5. Browser y capabilities remotas

`browser.chrome` no implica Chromium local. Puede resolverse mediante un browser-as-a-service o un worker remoto futuro.

La vista interactiva se expone únicamente a través de ControlBot autenticado. VNC, CDP u otros canales de control no se publican directamente a Internet.

El navegador comprometido debe quedar aislado del control plane: perfiles separados, capabilities mínimas, timeouts, evidencia saneada y sin credenciales en órdenes o logs.

## 6. Fallback macOS

macOS es un **fallback de última opción**, no el target inicial.

Solo puede activarse cuando exista evidencia técnica concreta de que una capability necesaria es inviable o operacionalmente desproporcionada en Shared Hosting/adapters remotos.

Reglas:

- usa exactamente el mismo protocolo ControlBot ↔ FactoryRunner;
- registra capabilities dinámicas, sin semántica especial por ubicación;
- no se convierte en fuente de verdad;
- puede aparecer/desaparecer sin perder WorkItems;
- no reutiliza ni transforma AutoFactory.

ControlBot no debe necesitar saber si una ejecución ocurrió en Shared Hosting, un backend remoto o macOS para conservar su modelo de WorkItem.

## 7. Relación con FactoryRunner #2

FactoryRunner #2 implementa el primer runtime Node.js 24 + TypeScript y sus contratos de identity, heartbeat, order y event. Debe respetar este documento, pero #167 no duplica ese runtime ni fija proveedores concretos de browser remoto.

Si #2 demuestra que una assumption concreta del Shared Hosting no es viable, la evidencia se registra antes de activar el fallback macOS. La forma de las órdenes, eventos, capabilities y límites de autoridad no cambia.

## 8. Invariantes

- Factory gobierna, ControlBot decide, FactoryRunner ejecuta.
- AutoFactory permanece local/manual e independiente.
- Shared Hosting es primary; root/Docker/Chromium local no son requisitos.
- Capabilities no disponibles localmente se ofrecen mediante adapters remotos o se declaran ausentes.
- Órdenes secret-free y sin autoridad implícita.
- ControlBot conserva el estado durable.
- Runner reconstructible, heartbeat-driven e idempotente.
- Ownership por `attempt_id` + `generation` monotónica y fencing contra eventos/side effects stale.
- Mac fallback solo con evidencia y con protocolo idéntico.
