# Compatibilidad de permisos reusable ↔ caller

`reusable_permission_compat.py` define un contrato **puro y fail-closed** para comparar el permission envelope máximo que requiere un workflow reusable con el envelope que concede cada caller.

## Semántica

- niveles: `none < read < write`;
- scopes omitidos por el caller equivalen a `none`;
- scopes o niveles desconocidos invalidan el contrato;
- un reusable es compatible solo si, para cada scope requerido, el caller concede un nivel igual o mayor;
- un conjunto de consumidores es compatible solo si **todos** sus callers lo son. No existe mayoría, promedio ni excepción implícita.

El resultado es determinista y estructurado: `compatible`, `reason`, `missing` y `errors`. Para conjuntos de callers se añade la lista ordenada `callers`.

## Límite

El módulo no lee YAML, GitHub, red, archivos, variables de entorno, secretos ni credenciales. Tampoco modifica permisos. Su único trabajo es validar mapas ya extraídos por un adaptador confiable.

La integración posterior con la puerta de release debe obtener los envelopes de callers reales o fixtures con provenance y alimentar este contrato; cualquier evidencia ausente o inválida debe conservar el bloqueo.
