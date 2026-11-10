# Auditoría offline del trust root de Factory@v1 — #2100 / #1080

Esta hoja existe por la decisión de desarrollo **#2075/A** y su journal v2. **No** modifica la decisión histórica #185 del dueño de mover el tag manualmente. La evaluación de release_auto_trust_root_audit.py es sintética y **sin autorización** de publicación: procesa declaraciones sin autenticarlas. Incluso REVIEW_ONLY siempre devuelve authorizes_release=false, mutations=0, network_calls=0, tag_writes=0 y release_writes=0.

## Estado observado en el momento del diseño

El ruleset factory-v1-trust-root (id 23958613) protege refs/tags/v1 mediante creation, update y deletion. Su bypass real observado es solo RepositoryRole id=5: la automatización de GitHub Actions no tiene privilegio de actualizar el tag. La GitHub Actions App genérica (id 15368) **no** es una alternativa segura para dar acceso amplio.

## Contrato de prueba

El ejemplo positivo de los tests es **ficticio**: App de release dedicada con ID sintético 820201, instalación selected únicamente en pl0n3r/Factory, contents:write, metadata:read y un único bypass de tipo Integration coincidente, además del bypass humano id 5. Produce solo REVIEW_ONLY; no acredita presencia real de esa App, autenticación del transporte ni instalación. Ausencias, más permisos, repositorios extra, bypass genérico/duplicado, ruleset inesperado o desactivado devuelven BLOCKED.

El caller externo debe verificar procedencia por separado (API autenticada, identidad de la instalación, repositorios, permisos, ruleset y HEAD exacto). Ningún campo del snapshot es una credencial ni un permiso efectivo.

## Para cualquier activación futura

Hace falta autorización específica del propietario para la identidad de automatización y cambio del trust root, además de configuración administrativa, protección de la App, secretos bajo control del dueño, pruebas de compatibilidad, freeze y gates de release exact-SHA, CI/seguridad, rollback y proceso de habilitación. **No** se deduce de #2075/A ni de este ensayo una autorización para publicar, mover tags o desactivar la puerta actual. Ninguna fuente declarativa reemplaza el voto OWNER ni la validación de producción.

Reversión: revertir el squash de la hoja elimina exactamente el script, el test y este runbook, sin cambiar la distribución existente.
