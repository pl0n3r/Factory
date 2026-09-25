# Puertas de decisión humana

La fábrica solo interrumpe al dueño por categorías cerradas: dirección de producto, marca, dinero, legal, datos reales de clientes, publicar 1.0.0, mantenimiento de Factory y pasar a live.

Un agente que encuentre una decisión de ese tipo la expresa en el cuerpo del Issue con un único marker estructurado.

## Compatibilidad del marker

El contrato base sigue siendo compatible con puertas existentes:

```html
<!-- factory-human-gate {"category":"money","context":"Cambiar el proveedor incrementa el gasto mensual.","options":[{"id":"A","label":"Mantener proveedor actual"},{"id":"B","label":"Migrar al proveedor nuevo"}],"recommendation":"A","safe_default":"A"} -->
```

El parser también admite campos simples opcionales para que ControlBot presente la decisión sin traducir jerga:

- raíz:
  - `title_simple`: pregunta breve, una línea;
  - `summary_simple`: resumen de hasta 3 líneas;
  - `why_recommended`: una frase;
  - `blocks`: qué trabajo queda bloqueado;
- por opción:
  - `effect`: qué pasa si se elige;
  - `pros[]` y `cons[]`: entre 1 y 5 elementos, texto corto;
  - `risk`: `low`, `medium` o `high`;
  - `cost`: texto corto o vacío;
  - `reversible`: booleano.

Ejemplo enriquecido:

```html
<!-- factory-human-gate {"category":"money","context":"Cambiar el proveedor incrementa el gasto mensual.","title_simple":"¿Cambiamos de proveedor?","summary_simple":"El proveedor nuevo cuesta más, pero reduce trabajo manual.","options":[{"id":"A","label":"Mantener proveedor actual","effect":"Seguimos con el costo y flujo actuales.","pros":["Sin migración"],"cons":["Más trabajo manual"],"risk":"low","cost":"","reversible":true},{"id":"B","label":"Migrar al proveedor nuevo","effect":"Se migra la operación al proveedor nuevo.","pros":["Menos trabajo manual"],"cons":["Aumenta el costo mensual"],"risk":"medium","cost":"+$ mensual","reversible":true}],"recommendation":"A","safe_default":"A","why_recommended":"A evita gasto nuevo mientras se valida el beneficio.","blocks":"Bloquea la automatización del flujo asociado."} -->
```

### Regla para puertas nuevas

La compatibilidad existe para no romper Issues históricos. **Toda puerta nueva escrita por un agente debe incluir los campos simples completos**: `title_simple`, `summary_simple`, `why_recommended`, `blocks` y, en cada opción, `effect`, `pros`, `cons`, `risk`, `cost`, `reversible`.

El esquema sigue cerrado: cualquier campo desconocido, tipo incorrecto, riesgo fuera del enum, lista excesiva o longitud inválida hace que la puerta sea `invalid-gate`.

El contexto y las opciones son acotados. `recommendation` y `safe_default` deben referir opciones existentes. Si no hay marker, el Issue es trabajo autónomo normal. Si hay intención de marker pero el JSON/categoría es inválido, se clasifica como `invalid-gate`: **no entra a la cola y cualquier etiqueta stale se retira**.

## Cola y notificación

Solo Issues creados por actores con asociación `OWNER`, `MEMBER` o `COLLABORATOR` pueden activar la cola. Un Issue externo, aunque contenga un marker sintácticamente válido, nunca etiqueta, asigna ni menciona al dueño. Tras el merge del workflow, un Issue confiable con marker válido recibe la etiqueta única `decisión: dueño`, se asigna idempotentemente al propietario del repositorio y la primera entrada a esa cola lo menciona una sola vez. Las ediciones posteriores no generan otra mención mientras conserve la etiqueta.

Esto usa asignación + mención como transporte dentro de GitHub. La recepción como push en el teléfono depende de GitHub Mobile y de las preferencias externas de la cuenta; la automatización no cambia preferencias ni inventa un canal alternativo.

## Regla operativa

Si no hay respuesta, el agente puede seguir únicamente con la opción declarada como `safe_default` cuando esa opción sea realmente segura y reversible; acciones que por política requieren autorización explícita continúan bloqueadas.

## Seguridad del evento

El clasificador no acepta rutas de archivos por CLI. El workflow confiable alimenta el JSON de `GITHUB_EVENT_PATH` por stdin; Python limita el tamaño del evento y del cuerpo del Issue, valida esquema cerrado y solo emite `status` + `category`, nunca contexto, resúmenes, opciones, costos ni otro contenido del marker.

## Sincronización fail-closed

En eventos `opened|edited|reopened`, el workflow verifica primero la asociación del autor del Issue. Si el origen no es confiable, el marker es inválido o deja de existir, el flujo no menciona al dueño y retira `decisión: dueño` si había quedado de un estado anterior. Un error estructural del marker no puede degradarse silenciosamente a trabajo autónomo.

## Puertas automáticas de privacidad

El reusable workflow `.github/workflows/auditoria-privacidad.yml` puede crear una puerta de categoría `legal` únicamente cuando el mapa `datos.yml` introduce o cambia una finalidad, incorpora una categoría sensible o agrega un proveedor receptor. La puerta usa el marker `factory-human-gate` y mantiene como default seguro continuar en fase `construccion` con estado `documented_not_legally_approved`.

La auditoría nunca copia valores observados del código a Issues: publica únicamente identificadores controlados de señales/proveedores y rutas del repositorio. El Issue técnico de auditoría es idempotente y se cierra automáticamente cuando deja de haber drift. Una puerta legal, en cambio, **no se cierra automáticamente**: requiere la decisión humana correspondiente.

La automatización usa `GITHUB_TOKEN` efímero del mismo repositorio con `contents: read` e `issues: write`; no usa PATs personales ni tokens de larga duración.
