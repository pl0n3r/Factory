# Inspector offline del artefacto Fase A de reservas (#1510, parent #1382)

Este helper solo inspecciona localmente un ZIP lease-audit-evidence de GitHub Actions y un JSON de metadatos **obtenido por GitHub autenticado** (endpoint de workflow run exacto, id, repository, head_sha, event, status, conclusion). Se exige schedule, completed/success y coincidencia exacta de identidad; no se realizan consultas de red, cambios de permisos, almacenamiento de datos, ni llamadas de escritura a GitHub. La operación solo calcula SHA-256 de los bytes originales lease-audit-evidence.json, valida el esquema Fase A y rechaza entradas peligrosas/ambiguas. No extrae archivos a disco.

Uso en una estación de QA con los dos archivos descargados por canal confiable:

    python3 -m scripts.lease_phase_a_artifact_qa --artifact /ruta/lease-audit-evidence.zip --run-metadata /ruta/run-metadata.json

El output MATCHED_CANDIDATE **no** dice artifact_attested: true: artifact_attested permanece false, al igual que terminal_certified, release_authorized y mutations. Un archivo local o metadata aportada por un usuario no autentican su procedencia por sí mismos. QA verifica independientemente la respuesta REST, artefacto ID, integridad, SHA/run, repositorio y evento, la cadena exacta y cualquier actividad del titular.

Un UNKNOWN, un run sin reservas, un artefacto ilegible, un estado deferred, una salida con campos secretos o counters inconsistente no cuenta como ciclo. El evaluador existente evaluate_phase_a_candidate es independiente y debe recibir recibos autenticados y la **QA individual** de cada release hipotético.

Se exigen **24 horas**, **100 ciclos** terminales válidos por repositorio, cero falsos positivos y todas las revisiones individuales correctas. El titular y las puertas humanas/operativas conservan la última autoridad.

**No autoriza Fase B**, cambiar el flag en los workflows, liberar reservas, crear comentarios, fusionar, desplegar, publicar Factory@v1, gastar dinero o procesar datos reales. Reversión: eliminar estos tres archivos nuevos mediante revert del único PR, sin alterar la infraestructura ni observadores existentes.
