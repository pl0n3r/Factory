# Núcleo común para AGENTES.md

> Reglas compartidas por proyectos que consumen Factory. Cada repositorio añade solo su contexto técnico y de producto.

## Decisiones del dueño

`decisiones.yml` es normativa. Una decisión con `status: active` no se revierte por una regla vieja, comentario, Issue o implementación previa. Si el código fusionado contradice una decisión activa, el código se trata como defecto y se corrige.

## Fuentes de verdad

1. Decisiones activas de `decisiones.yml`.
2. Código fusionado en `main` y pruebas reproducibles.
3. `AGENTES.md` del proyecto para su contrato técnico local.
4. Issues/PR activos para alcance ejecutable.
5. `lecciones/` para trampas y causas ya demostradas.

Una lección informa; no puede contradecir una decisión activa.

## Arranque de una sesión

- obtener SHA exacto de `main`;
- leer `decisiones.yml`;
- leer `lecciones/` si existe, limitado al proyecto/tarea relevante;
- revisar PRs abiertos, Issues reservados y CI del SHA relevante;
- confirmar criterios de aceptación y que no exista otro PR sobre el mismo trabajo;
- reservar con `/tomar` y conservar el UUID publicado por coordinación.

## Trabajo y coordinación

- Rama normal: `trabajo/issue-N`.
- PR hacia `main` con `Closes #N` y UUID de reserva.
- Recupera rama/PR existente antes de abrir sustitutos.
- Libera con `/liberar <UUID>` y transfiere con `/transferir <UUID>`.
- Colisiones de archivos se serializan; nunca se sobrescriben silenciosamente.

## Calidad y seguridad

- Acciones externas fijadas a SHA y permisos mínimos.
- Secretos y PII fuera de logs, fixtures y comentarios.
- Reintentar solo fallos externos e idempotentes con señal transitoria.
- Cada bug determinista relevante gana una regresión.
- Máximo tres rondas automáticas de revisión; después se bloquea con evidencia.
- El check agregado `Validar` es el contrato estable de branch protection.

## Entrega

- **IMPLEMENTADO:** existe en código.
- **VALIDADO EN CÓDIGO:** pasaron los gates del SHA exacto.
- **DESPLEGADO:** el entorno recibió la release.
- **VALIDADO EN PRODUCCIÓN:** smoke/observación real confirmó versión, SHA y salud.

Merge o CI verde no equivalen a producción.

## Releases

Los consumidores fijan el kit por major (`@v1`). Cambios incompatibles requieren nueva versión mayor; mejoras compatibles se validan primero en Factory.

## Progreso visible y contexto compacto

Contrato de prompt (detalle y formato en `docs/conversacion-agentes.md`):

- En trabajos largos, emite una actualización breve solo en transiciones significativas: siguiente paso concreto, hallazgo que cambia el enfoque, etapa completada, bloqueo, decisión requerida o resultado confirmado. Cada una dice qué se confirmó y qué sigue.
- Prohibido el progreso vacío: «sigo revisando», «déjame pensar», «estoy trabajando en eso» o repetir «voy a revisar…» sin hallazgo nuevo. No narres cada tool call ni repitas el plan. No expongas razonamiento interno.
- Al llegar a un hito (merge, cambio de enfoque, fallo relevante, cambio de Issue/PR, contexto ruidoso) escribe una nota `STATE` compacta y continúa desde ella sin releer todo el historial.
- Eficiencia: no reexplicar lo que ya está en Issue/PR/`lecciones/`; busca antes de abrir y lee solo fragmentos; agrupa lecturas independientes; sin polling de CI (una lectura terminal); resultado primero; hitos en 3–7 líneas; no dupliques en el chat lo registrado en GitHub.
- Streaming, persistencia de estado, truncado/resumen de contexto, caché y límites de tokens pertenecen a la integración (Factory/ControlBot/FactoryRunner), no al prompt: evalúalos allí.

## Handoff

- dejar Issue/PR con estado, evidencia y siguiente acción;
- conservar/transferir/liberar la reserva correctamente;
- no dejar afirmaciones de producción sin evidencia;
- no depender de conversaciones externas para reconstruir el trabajo.
