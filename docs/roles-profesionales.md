# Roles profesionales del kit

Factory usa un catálogo cerrado de 16 perfiles en `agentes/roles/`. Ese catálogo es la fuente canónica de las etiquetas `rol: …` / `role: …`; no se mantiene una segunda copia manual de roles en `labels/*.json`.

## Contrato de PR

El cuerpo del PR incluye:

- `Rol(es): slug1, slug2`
- `Rol primario: slug1`
- todos los items de checklist de cada rol como `- [x] …`
- si el cambio toca esquema, seguridad, deploy/workflows o UX pública: `Revisión cruzada: <slug>`, distinto del rol primario y permitido para ese riesgo.

El motor deriva roles obligatorios de archivos tocados y tipo/contexto del Issue. Roles adicionales son válidos cuando representan trabajo profesional real; el rol primario debe estar declarado.

## Etiquetas

- Proyectos en español: `rol: <slug>`.
- BRVTAL/inglés: `role: <name>`.

`mode=sync` crea/actualiza las etiquetas desde el catálogo canónico. `mode=suggest` asigna las etiquetas a la entidad del evento. `mode=validate` comprueba roles, etiquetas, checklists y revisión cruzada.

## Fronteras de seguridad

- El workflow siempre ejecuta el kit publicado `@v1`; el caller no elige una ref.
- `validate` es read-only y solo acepta el PR actual.
- `sync` escribe únicamente desde `push|workflow_dispatch` de la rama principal.
- `suggest` solo puede modificar la entidad del evento `issues|pull_request`, o una entidad explícita bajo `workflow_dispatch` en la rama principal.
- El contexto entra al validador por stdin con tamaño acotado; el CLI no acepta rutas de catálogo, perfiles ni contexto.
- La clasificación es determinista y explicable; ningún texto remoto se ejecuta como código o shell.

La adopción automática en Condor, GrindFlow y BRVTAL pertenece a Tanda 2, después de publicar `v1`.
