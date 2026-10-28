# Factory #1613 — evaluación offline de política de release

## Autoridad y límites

Esta hoja descompone Factory #1080 después de la autorización específica
[Factory #1558/A](https://github.com/pl0n3r/Factory/issues/1558). La opción A
autoriza exclusivamente estas pruebas y documentación; **NO** permite publicar
versiones, mover Factory@v1, cambiar permisos ni retirar las puertas humanas.

El evaluador es una función pura. No consulta GitHub, lee archivos, crea tareas,
autentica fuentes ni posee permisos de publicación. Sus entradas son
**afirmaciones del caller** que deben verificarse independientemente.
Incluso evidence_authenticated=true y journal_verified=true son valores
del fixture, nunca una atestación del módulo.

## Contrato de entrada

Snapshot dict de claves exactas: candidate_sha, observed_main_sha,
published_v1_sha, v1_tag_protected, evidence_authenticated,
kill_switch_state, freeze_active, security_veto, owner_decision y checks.
Los SHA son hexadecimales ASCII de 40 caracteres. La decisión exige option=A,
category=factory-release, owner=pl0n3r, journal_verified=true y el mismo SHA
candidato. Cualquier campo extra, desconocido, ausencia o mismatch falla cerrado.

Cada check incluye name, head_sha, status, conclusion y authenticated. Todos
deben tener el mismo SHA candidato y estado completed/success. Se exigen
Validar, SonarCloud Code Analysis y CodeQL. La protección de v1 debe constar
activa, sin freeze, veto de seguridad ni kill switch distinto de RUNNING.
Todos los valores deben autenticarse fuera de este módulo.

## Salidas y casos negativos

Se devuelve BLOCKED y razón, o REVIEW_ONLY si las afirmaciones pasaron la
comprobación offline. Ambos mantienen:

- authorizes_release=false; mutations=0;
- network_calls=0; release_tag_writes=0.

REVIEW_ONLY nunca significa autorización de release, validación en producción
o decisión del dueño. Cambios de main, journal ausente/incorrecto, freeze,
kill switch pausado, evidencia UNKNOWN, checks fallidos/pendientes y veto de
seguridad se bloquean. La misma entrada da la misma salida sin efectos.
Los tests de CI usan exclusivamente identidades sintéticas.

## Validación y publicación separada

Ejecutar en la raíz:

    python3 -m unittest tests.test_release_auto_policy -v
    python3 -m unittest discover -s tests -p 'test_*.py'

El PR exige aceptación ejecutable, Validar, SonarCloud, CodeQL, revisión FINAL
de CodeRabbit y reserva V3 auténtica. Fusionar esta hoja **NO** publica release.
Una publicación real exige candidato exact-SHA, freeze, puerta factory-release,
voto aislado del OWNER, journal bot, bootstrap protegido y recibo terminal,
compatibilidad de consumidores y autorización nueva de SHA/versión.

Reversión: revertir el squash del PR #1613; no hay estado externo que limpiar.
