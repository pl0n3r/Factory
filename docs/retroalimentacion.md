# Retrospectiva diaria: candidato previo a publicación

## Contrato y estado

Este workflow (`.github/workflows/retro-diaria.yml`) se ejecuta con agenda diaria o manualmente. **Actualmente es build-ahead offline, no un publicador conectado.** Solo observa el interruptor canónico Factory #767 y verifica que el SHA de la ejecución coincida con `main` antes del checkout. Un fallo de lectura o un estado distinto de `RUNNING` aborta el job.

El gate `publication_candidate` se ejecuta desde el mismo bloque Python del workflow y se prueba sin red mediante `tests/test_retro_publicacion.py`. Su salida `CANDIDATE` representa *únicamente* que un snapshot suministrado al evaluador pasó los controles puros. `publication_allowed` permanece **false** incluso en ese caso. Ni esa salida ni un CI verde acreditan fuentes de GitHub por sí solos.

## Requisitos para futuras fuentes autenticadas

Un colector pendiente deberá obtener exclusivamente por API autenticada: identidad exacta de repositorio/HEAD, inventario completo (sin truncamientos ni deriva entre páginas), todos los tipos de evento de `scripts/retro_diaria.py::EVENT_KINDS`, eventos terminales, fechas UTC y cuota restante al menos del 20 %. Debe rechazar HTTP 403/429, latencia o conflictos con `UNKNOWN`. El evaluador nunca convierte un inventario parcial en conteos cero.

El ejecutor futuro deberá verificar bajo el lock canónico una reserva V3 activa con UUID/owner/claims exactos, el switch #767, permisos mínimos y deduplicación de publicación antes y después de la operación. **Ningún executor, credencial de escritura o API mutante está conectado en este PR.** El workflow concede solo `contents: read`, `issues: read` y `pull-requests: read`; no publica comentarios, no edita Issues, no crea releases y no toca `Factory@v1`.

## Puertas y reversión

- **AC-01:** rechazar sources sin autenticación, incompletas, checks pendientes/rojos, SHA distinto, clases de eventos ausentes, duplicados contradictorios y eventos posteriores al reloj.
- **AC-02:** negar cuota insuficiente o booleana, lease ausente/forjada/inactiva, IDs duplicados, `workflow_run`/ `issue_comment`, live, PAUSED y HEAD ajeno.
- Regresión offline: `python3 -m unittest tests.test_retro_publicacion -v`.
- Reversión: revertir los tres paths exclusivos de #1160. No modificar motores previos de #1157/#1158/#1159.

Este documento no declara retrospectivas publicadas, integración productiva, live ni fuentes realmente verificadas. El modo programado, sin colector conectado, devuelve `UNKNOWN` por diseño.
