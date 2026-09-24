# Resiliencia de identidades y recuperación de Factory

**Rol:** seguridad + SRE. **Estado:** contrato técnico, no prueba de recuperación real. Este documento no afirma que existan todavía GitHub Apps separadas, copias externas ni un restore exitoso.

## Control preventivo

- Separar identidades de CI, deploy y observador mediante GitHub Apps distintas y permisos mínimos. No reutilizar un token personal para todos los agentes.
- Los workflows solo pueden usar acciones fijadas a SHA; `pull_request_target`, `write-all` y permisos globales de escritura están prohibidos.
- Mantener los secretos en un gestor externo con acceso mínimo. No guardar valores, hashes reversibles, URLs firmadas, identificadores de cuenta privada ni tokens en este repositorio.
- Los registros de recuperación contienen **solo** referencias no sensibles y fecha UTC; el manifiesto con evidencias reales permanece fuera de Git y tiene vigencia máxima de 90 días.

## Respuesta a compromiso o pérdida de acceso

1. **Contener:** desactivar de inmediato la instalación/token afectado y suspender deploys de la identidad comprometida; conservar auditoría y SHA de releases.
2. **Delimitar:** identificar alcance de permisos y periodo de exposición con los registros disponibles; comprobar si otros agentes comparten credenciales.
3. **Rotar:** generar credenciales nuevas para la identidad afectada y revocar las antiguas; no imprimir ni copiar secretos a Issues, PRs o logs.
4. **Recuperar:** comprobar integridad y antigüedad de copia fuera de GitHub, restaurar en entorno aislado y comparar refs, tags y artefactos.
5. **Verificar:** ejecutar CI, smoke y prueba de rollback antes de retomar despliegues; registrar evidencia externa con fecha y referencia no sensible.
6. **Aprender:** documentar causa, ventana, controles preventivos y resultado de restore en `lecciones/` sin datos personales ni credenciales.

## Evidencia auditable

`python3 seguridad/resiliencia.py --audit-workflows` audita un subconjunto deliberadamente conservador de la sintaxis YAML de permisos, eventos y referencias a acciones. **No reemplaza actionlint ni una auditoría semántica de permisos efectiva por evento.** Los falsos negativos por YAML complejo siguen siendo posibles; toda ampliación del contrato debe añadir pruebas.

`python3 seguridad/resiliencia.py --manifest /ruta/privada/evidencia.json` exige un JSON con campos raíz exactos `version`, `project`, `identities`, `checks`. Los roles `ci`, `deploy`, `observer` deben apuntar a referencias públicas y diferentes `github-app:<alias>`, no credenciales. Los cuatro checks `repo_backup`, `secrets_escrow`, `token_rotation`, `restore_drill` exigen `verified_at` UTC y `evidence_ref` no sensible.

**Cierre de #10:** requiere comprobar en sistemas reales GitHub Apps separadas y restauración de una copia externa. Un test exitoso de JSON de ejemplo **no** satisface ese requisito.


## Entradas del auditor

El CLI no acepta rutas suministradas por agentes para auditar workflows: siempre usa `.github/workflows` del repositorio actual. El manifiesto de recuperación se entrega por `stdin` desde una ubicación externa y segura:

```bash
python3 seguridad/resiliencia.py --audit-workflows
python3 seguridad/resiliencia.py --manifest-stdin < /ruta/externa/manifest.json
```

La ruta externa nunca entra al proceso como argumento y no se registra.

Los workflows con escritura declaran esos permisos en el job mínimo que los necesita; el scope global permanece read-only.
