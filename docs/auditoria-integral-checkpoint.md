# Checkpoint integral de auditoría · siete repos

Herramienta offline para un operador: no consulta GitHub, no reserva, no publica, no escribe artefactos y no ejecuta el dispatcher. Solo lee el archivo JSON ficticio de nombre fijo audit-integral-fixture.json dentro del directorio de trabajo y entrega JSON determinista y saneado por stdout.

```sh
python3 scripts/audit_integral_checkpoint.py audit-integral-fixture.json
python3 -m unittest tests.test_audit_integral_checkpoint -v
```

## Formato de entrada v1
Objeto de claves exactas `version: 1`, `as_of` (UTC `YYYY-MM-DDTHH:MM:SSZ`), `kill_switch` (`RUNNING|PAUSED|UNKNOWN`) y `repositories` (exactamente los siete nombres de `scripts/work_inventory.py::CANONICAL_REPOSITORIES`). Cada repo usa `repo`, `sha` (40 hex), `observed_at`, `ref`, `leaves`, `incidents`. La evidencia y el snapshot deben tener menos de 24 horas respecto a `as_of` sin marcas futuras.

Una hoja de `leaves` usa `issue` (entero), `state` (`available|reserved|in_review|blocked|completed`), `required_ac` (lista de AC obligatorios), `acceptance` (objetos `id,status,ref`, estado `passed|pending|failed|unknown`), `depends_on` (IDs `pl0n3r/Factory#2157`), `claims` (rutas relativas), `ref`, `pr` (null u objeto `number,state,sha,ref`), `qa` (`status,sha,observed_at,ref`) y `production` (`state,sha,observed_at,ref,pending`).

QA admite `success|pending|failure|unknown`; producción `VALIDATED_IN_PRODUCTION|PENDING|UNKNOWN`; `pending` admite solo `deployment|migration|smoke|rollback|approval|backup|identity|other`. Los incidentes son objetos `issue,state,ref` (`open|resolved`). Las referencias deben ser URLs explícitas de GitHub relativas a los siete repos canónicos, nunca se consultan ni se infieren.
## Interpretación y límites
Cada repo/hoja se clasifica `auditoria_open`, `auditable`, `blocked` o `unknown`; la salida solo contiene IDs, estados, SHA, razones codificadas y referencias suministradas que pasaron el validador. `auditable` representa exclusivamente un conjunto de afirmaciones locales estructuradas: **no autentica fuentes, no autoriza operaciones ni valida producción**. Depende de PR fusionado, QA/AC terminados y evidencia terminal de producción exact-SHA sin pendientes. Solo los operadores pueden comprobar la autenticidad de esos recibos fuera de la herramienta.

Dependencias abiertas, ciclos, claims solapados, incidentes y producción pendiente bloquean. Duplicados, datos malformados o no verificables, fuentes caducadas y kill switch distinto de `RUNNING` fallan cerrado. `CI success` **no equivale** a `production green`. El CLI emite `unknown` saneado y código de salida 2 ante fixtures inválidos.
No introducir datos reales, secretos, PII ni logs. El operador debe registrar las referencias verificadas en [Factory #2156](https://github.com/pl0n3r/Factory/issues/2156), sin ampliar permisos por la presencia de una URL.
