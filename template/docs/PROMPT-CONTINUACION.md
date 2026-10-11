# Prompt de continuación — una unidad completa por turno

Este texto es una plantilla del kit Factory para el campo de **prompt personalizado de AutoFactory**. Reduce informes intermedios y orienta cada turno a una unidad de trabajo verificable. No modifica la extensión ni sustituye las reglas de `PLAN-AGENTES.md`, los permisos o los límites del proveedor.

## Mensaje estándar

Copia únicamente el mensaje siguiente en el campo de continuación:

~~~text
Continúa sin parar hasta terminar una unidad de trabajo completa.
Pasos:
(1) relee el estado de tu issue reservado y de su PR;
(2) si no tienes reserva, toma el siguiente issue disponible con prioridad crítica;
(3) implementa, prueba y deja el PR en verde;
(4) si todos los controles están en verde y no hay cambios pedidos, fusiónalo (squash) y comenta el SHA;
(5) pasa de inmediato al siguiente issue disponible.
No te detengas a dar informes de estado; comenta solo hitos (PR abierto, fusionado, bloqueo real).
Si algo está bloqueado de verdad, di el motivo concreto, etiqueta el issue y toma otro.
~~~

## Variante breve QA/seguridad

Para turnos dedicados a revisión, no a implementación, usa en su lugar:

~~~text
Completa una unidad verificable de QA o seguridad: relee el issue y el PR exactos; revisa el cambio y sus controles; reproduce una regresión concreta cuando sea posible; registra un único hallazgo nuevo y accionable o la evidencia de cierre. No te apropies de una reserva ajena, no repitas comentarios de estado ni apruebes por inferencia. Si el frente está bloqueado, documenta la causa y pasa al siguiente frente seguro.
~~~

## Cuándo usarlo

- Usa el mensaje estándar cuando el agente **ya puede trabajar** en un issue reservado o puede solicitar una reserva nueva legítima.
- Usa la variante QA/seguridad al revisar código o pruebas sin escribir sobre los archivos reservados por otro agente.
- Mantén los gates del repositorio: la prioridad no reemplaza una reserva V3, CI exact-SHA, checks obligatorios, bloqueos, el interruptor global ni la autorización para publicar. Una fusión solo es posible si las políticas vigentes la permiten.
- Si Coordinación deniega la reserva, no simules autorización: registra el bloqueo concreto y elige una tarea segura distinta.

## Cómo configurarlo en AutoFactory

1. Abre la configuración **local** de AutoFactory y localiza el campo de **prompt personalizado** para continuar agentes.
2. Copia el bloque del **Mensaje estándar** o el de **Variante breve QA/seguridad** según el rol; no copies todo este documento al chat.
3. Guarda la preferencia local. Respeta la pausa manual, la cadencia, el presupuesto horario y la confirmación de respuesta antes de sugerir otro envío.
4. Comprueba con un caso sintético que la continuación produce un hito verificable. Este documento no habilita clics, envío automático ni acceso a sesiones reales.

## Privacidad y límites

No incluyas en el prompt personalizado ni en comentarios de diagnóstico: **tokens**, claves API, contraseñas, cookies, credenciales, identificadores de cuenta, correos personales, datos de clientes, secretos ni **contenido de chats**. Utiliza solo referencias públicas del repositorio (issue, PR y SHA), sin adjuntar mensajes privados. Nunca pegues claves o trazas de sesión para demostrar el avance.

Este mensaje es una guía de trabajo y no una autorización adicional para gastos, datos reales, despliegues, publicación, cambios irreversibles o salida a live.
