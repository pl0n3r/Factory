# Vistas derivadas

Factory define un contrato para que documentación, dashboards y status puedan derivarse sin convertirse en fuentes de verdad.

Para adoptar el patrón:

1. Identifique la fuente canónica.
2. Declare la vista derivada y su modo: `generated` o `regression`.
3. Use un generador puro cuando la fuente pueda consumirse de forma segura; nunca use reloj, red o estado mutable para producir la salida.
4. Añada un drift check que falle cerrado cuando la vista diverja.
5. Mantenga la autoridad en la fuente canónica y documente la ruta de reversión.

Si no existe todavía un adaptador seguro para la fuente, use una regresión contra claims concretos en lugar de inventar una segunda fuente.

Este documento es una guía de adopción; la fuente canónica del proyecto sigue siendo la definida por sus contratos locales y Factory.
