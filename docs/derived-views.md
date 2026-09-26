# Contrato de vistas derivadas

Una vista derivada **nunca es una fuente de verdad**. La semántica pertenece a la fuente canónica; la vista solo materializa o verifica esa información.

## Registro

Cada vista mantenida por Factory se registra en `config/derived_views.json` con:

- `id`: identificador estable.
- `source`: fuente canónica y sus referencias.
- `view`: superficie derivada.
- `mode`: `generated` si existe un generador seguro, o `regression` cuando la fuente todavía no puede consumirse de forma segura.
- `generator`: función determinista obligatoria para `generated`.
- `drift_check`: test/guard que impide publicar una vista divergente.

## Generación determinista

Un generador debe ser una función pura: sin red, reloj, aleatoriedad ni estado mutable externo. La misma instantánea normalizada de la fuente debe producir exactamente los mismos bytes, incluido orden, columnas y saltos de línea.

Factory ofrece `intelligence.derived_views.render_markdown_table` para tablas Markdown simples. El caller declara explícitamente las columnas y la clave de orden.

## Drift check

El guard compara la salida esperada con la vista comprometida y falla cerrado ante cualquier diferencia. No se debe “arreglar” la fuente para hacer pasar el check ni aceptar la vista como nueva fuente canónica.

## Cuando no existe un generador seguro

Use `mode: regression`. La regresión debe comprobar claims concretos contra la fuente canónica y señalar qué dato cambiaría si la fuente cambia. Esto permite proteger una vista mientras se evita inventar una extracción estructurada.

## Primer caso: #239

Factory #239 es el primer caso registrado. El resumen de TANDA 2/TANDA 3 en `README.md` depende de `PLAN-AGENTES.md` y del estado canónico de Issues; como esa combinación todavía no tiene un adaptador seguro y sin red para generación, se registra como `regression`. `tests/test_readme_tandas.py` protege los claims actuales.

La siguiente evolución puede añadir un adaptador estructurado; no debe convertir el README en fuente de verdad.

## Adopción en proyectos

1. Identifique la fuente canónica.
2. Registre la vista en el manifiesto.
3. Elija `generated` solo si puede demostrar determinismo y ausencia de efectos externos; de lo contrario use `regression`.
4. Añada un drift check determinista.
5. Documente el límite y la reversión.
