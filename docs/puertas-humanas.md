# Puertas de decisión humana

La fábrica solo interrumpe al dueño por siete categorías cerradas: dirección de producto, marca, dinero, legal, datos reales de clientes, publicar 1.0.0 y pasar a live.

Un agente que encuentre una decisión de ese tipo la expresa en el cuerpo del Issue con un único marker estructurado:

```html
<!-- factory-human-gate {"category":"money","context":"Cambiar el proveedor incrementa el gasto mensual.","options":[{"id":"A","label":"Mantener proveedor actual"},{"id":"B","label":"Migrar al proveedor nuevo"}],"recommendation":"A","safe_default":"A"} -->
```

El contexto y las opciones son acotados; no se permiten campos extra. `recommendation` y `safe_default` deben referir opciones existentes. Si no hay marker, el Issue es trabajo autónomo normal. Si hay intención de marker pero el JSON/categoría es inválido, se clasifica como `invalid-gate`: **no entra a la cola y cualquier etiqueta stale se retira**.

## Cola y notificación

Solo Issues creados por actores con asociación `OWNER`, `MEMBER` o `COLLABORATOR` pueden activar la cola. Un Issue externo, aunque contenga un marker sintácticamente válido, nunca etiqueta, asigna ni menciona al dueño. Tras el merge del workflow, un Issue confiable con marker válido recibe la etiqueta única `decisión: dueño`, se asigna idempotentemente al propietario del repositorio y la primera entrada a esa cola lo menciona una sola vez. Las ediciones posteriores no generan otra mención mientras conserve la etiqueta.

Esto usa asignación + mención como transporte dentro de GitHub. La recepción como push en el teléfono depende de GitHub Mobile y de las preferencias externas de la cuenta; #9 no debe cerrarse hasta comprobar esa entrega real. La automatización no cambia preferencias ni inventa un canal alternativo.

## Regla operativa

Si no hay respuesta, el agente puede seguir únicamente con la opción declarada como `safe_default` cuando esa opción sea realmente segura y reversible; acciones que por política requieren autorización explícita continúan bloqueadas.

## Seguridad del evento

El clasificador no acepta rutas de archivos por CLI. El workflow confiable alimenta el JSON de `GITHUB_EVENT_PATH` por stdin; Python limita el tamaño del evento y del cuerpo del Issue, valida esquema cerrado y solo emite `status` + `category`, nunca el contexto u opciones.

## Sincronización fail-closed

En eventos `opened|edited|reopened`, el workflow verifica primero la asociación del autor del Issue. Si el origen no es confiable, el marker es inválido o deja de existir, el flujo no menciona al dueño y retira `decisión: dueño` si había quedado de un estado anterior. Un error estructural del marker no puede degradarse silenciosamente a trabajo autónomo.
