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
