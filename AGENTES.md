# AGENTES.md: factory

> Contrato técnico del repositorio pl0n3r/factory. El **cómo trabajar** (prioridades, límites, formatos, roles y decisiones del dueño) está en [PLAN-AGENTES.md](PLAN-AGENTES.md) y manda sobre este archivo si se contradicen.

## Qué es este repositorio

El kit común de la fábrica: reusable workflows, composite actions, scripts de gobernanza, catálogos de etiquetas, núcleo común de AGENTES.md y template de proyectos. Lo consumen pl0n3r/Condor, pl0n3r/GrindFlow y pl0n3r/brvtal.

**Regla del dueño:** factory no genera trabajo para el dueño. Todo se configura vía `gh`/API.

## Flujo obligatorio

1. Comenta `/tomar` en el Issue y espera la reserva del bot (UUID).
2. Trabaja solo en la rama `trabajo/issue-N`.
3. Abre el PR con la plantilla, `Closes #N` y la reserva declarada.
4. El check agregado **`Validar`** debe pasar; `main` está protegido y solo acepta PRs.
5. Libera con `/liberar <UUID>` si abandonas el trabajo.

## Estructura

| Ruta | Contenido |
| --- | --- |
| `.github/workflows/ci.yml` | CI del propio repo: actionlint, tests de scripts, coordinación y `Validar` |
| `.github/workflows/coordinacion-trabajo.yml` | `/tomar`, `/liberar`, `/transferir` y recuperación de reservas inactivas |
| `scripts/` | Scripts en Python sin dependencias externas |
| `tests/` | `unittest` de cada script |
| `PLAN-AGENTES.md` | Protocolo común de agentes y tandas |

A medida que avance el kit (#1) se agregan reusable workflows con `on: workflow_call`, `actions/`, `labels/`, `agentes/` y `template/`.

## Reglas técnicas del kit

- **Reusable workflows** configurables por `inputs` (stack, dominio, fuente de versión, idioma de etiquetas, fase `construccion|live`); nada específico de un proyecto dentro del kit.
- Acciones de terceros **fijadas a SHA**; `permissions` mínimos por job; `timeout-minutes` explícito; `concurrency` y filtros `if:` a nivel de job para no cargar GitHub.
- Scripts en Python 3 de biblioteca estándar, con tests `unittest`; nada de secretos en logs.
- **Versionado:** tags `vN.M.P`; los proyectos consumen `@vN`. Un cambio incompatible sube la versión mayor.
- Todo cambio se prueba primero aquí antes de publicarse a los proyectos.

## Idioma

Español para documentación, Issues y PRs. Las etiquetas del kit se publican en español (`labels/es.json`) y en inglés (`labels/en.json`) con el mismo sistema.

## Orquestación preventiva

Para épicos que se dividen en trabajo paralelo, declara un marker factory-plan y ejecuta /planificar antes de reservar tareas hijas.

- Cada tarea planificada tiene owner, roles derivados, orden, dependencias y paths reclamados.
- /tomar falla si hay dependencias abiertas o claims solapados con otra tarea activa.
- Si dos tareas necesitan tocar la misma ruta, el DAG debe serializarlas mediante depends_on.
- No edites owner/paths/dependencias de una tarea ya reservada o en revisión; replantea el épico antes de iniciar trabajo.

Consulta docs/orquestador.md para el contrato completo.

## Criterios de aceptación ejecutables

Antes de `/tomar`, el Issue debe contener Contexto, Alcance, Fuera de alcance, criterios humanos `AC-NN` y un marker `factory-acceptance` consistente.

- Cada `AC-NN` apunta a un test `unittest` exacto o a un check GitHub exacto.
- No se permiten comandos shell provenientes del Issue.
- `Criterios de aceptación` debe pasar en el PR; `Validar` depende de ese job.
- Gates genéricos verdes son necesarios, pero no suficientes para declarar el trabajo hecho.
- Si cambia el comportamiento esperado, actualiza primero el Issue y su evidencia ejecutable antes de modificar código.

Consulta `docs/aceptacion-ejecutable.md` para el contrato completo.

## Roles profesionales por tarea

Después de obtener la reserva con `/tomar`, revisa las etiquetas `rol: …` / `role: …` del Issue y carga **todos** los perfiles correspondientes desde `agentes/roles/<rol>.md`.

- Declara en el PR los roles asumidos y completa el checklist de cada perfil.
- Si el clasificador exige un rol adicional por los archivos modificados, inclúyelo.
- Cambios de esquema, seguridad, deploy o UX pública requieren **revisión cruzada** por un rol distinto al implementador.
- Los perfiles de rol complementan este contrato; no sustituyen `PLAN-AGENTES.md`, `decisiones.yml` ni las lecciones vigentes.

