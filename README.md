# 🏭 Factory: la fábrica de software de pl0n3r

**Factory es el "manual y la caja de herramientas" que comparten todos los proyectos.** En vez de que cada proyecto (Condor, GrindFlow, BRVTAL, FactoryRunner…) tenga sus propias reglas, su propio CI y sus propios scripts copiados y cada vez más distintos, todo eso vive **una sola vez aquí** y los proyectos lo usan.

> **En una frase:** aquí se define *cómo* se construye el software; en cada proyecto solo se define *qué* se construye.

---

## Operational Cockpit

<!-- factory:status:start -->
| Señal | Estado |
| --- | --- |
| main SHA | UNKNOWN |
| versión | UNKNOWN |
| CI | UNKNOWN |
| release | UNKNOWN |
| health | UNKNOWN |
| smoke/observer | UNKNOWN |
| quality/security | UNKNOWN |
| Issue activo | UNKNOWN |
| PR activo | UNKNOWN |
| último release | UNKNOWN |
<!-- factory:status:end -->

> Este bloque es derivado. UNKNOWN/PENDING significa que falta evidencia canónica. Nunca se escribe GREEN manualmente.

## Work Queue

- **NOW:** [cola automática y prioridades canónicas](PLAN-AGENTES.md#0-dónde-trabajar-modo-dirigido-o-modo-despachador).
- **NEXT:** [Issues ready de Factory](https://github.com/pl0n3r/Factory/issues).
- **LATER:** [épicos y planificación](https://github.com/pl0n3r/Factory/issues?q=is%3Aissue+is%3Aopen).
- **BLOCKED:** bloqueos y puertas se consultan en sus Issues y en [decisiones.yml](decisiones.yml).

Esta vista enlaza las fuentes canónicas y no añade una copia operativa paralela del Roadmap ni del changelog.

## Qué hace el producto

Factory publica contratos y herramientas compartidas para que cada repositorio no mantenga copias divergentes de la misma infraestructura: reusable workflows, scripts deterministas de gobernanza, catálogo de etiquetas, perfiles profesionales y template de proyectos.

Los consumidores usan el kit por canales versionados como `@v1`; las decisiones humanas reservadas siguen en [PLAN-AGENTES.md](PLAN-AGENTES.md) y [decisiones.yml](decisiones.yml).

## Arquitectura en 60 segundos

```mermaid
flowchart LR
    O["Dueño / decisiones"] --> F["Factory · governance/kit"]
    F --> C["Condor"]
    F --> G["GrindFlow"]
    F --> B["BRVTAL"]
    F --> R["FactoryRunner"]
    F --> CB["ControlBot"]
    F --> AF["AutoFactory"]
    F --> N["Proyecto nuevo / template"]
```

Factory es la capa de **governance/kit**. No reemplaza el estado ni la lógica de negocio de los productos.

## Stack e infraestructura

**Stack declarado:** Python 3 + GitHub Actions + reusable workflows.

La ejecución de producto permanece en cada repositorio consumidor; Factory publica contratos, validadores y automatización compartida.

## Ciclo de entrega

Issue → criterios de aceptación → reserva → rama canónica → PR → CI/revisión → merge → release del kit cuando aplica → validación del consumidor.

Un merge no equivale a release y un release no equivale a producción validada. La evidencia operativa permanece en checks, Releases, health/smoke e Issues canónicos.

## Calidad y seguridad

- criterios de aceptación ejecutables y fail-closed;
- acciones de terceros fijadas a SHA cuando el contrato lo exige;
- mínimo privilegio y trust boundaries explícitos;
- límites de rondas de revisión y coordinación anti-duplicación;
- privacidad, secretos y datos personales tratados por las políticas comunes;
- rollback y puertas humanas conservan la autoridad definida en [PLAN-AGENTES.md](PLAN-AGENTES.md).

## Roadmap y fuentes de verdad

- **Cómo trabajan los agentes y prioridad global:** [PLAN-AGENTES.md](PLAN-AGENTES.md)
- **Contrato técnico de Factory:** [AGENTES.md](AGENTES.md)
- **Decisiones vigentes del dueño:** [decisiones.yml](decisiones.yml)
- **Trabajo y aceptación:** [GitHub Issues](https://github.com/pl0n3r/Factory/issues)
- **Cambios revisados:** [Pull Requests](https://github.com/pl0n3r/Factory/pulls)
- **Entregas del kit:** [GitHub Releases](https://github.com/pl0n3r/Factory/releases)
- **README Contract v1:** [docs/readme-contract.md](docs/readme-contract.md)

El README es una portada y una guía humana. No reemplaza ninguna de estas fuentes.

## Desarrollo local

Validación principal del repositorio:

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Mapa de la fábrica

- **Factory:** governance/kit compartido y fuente de contratos comunes.
- **ControlBot:** control plane privado de dashboard, decisiones y orquestación.
- **FactoryRunner:** execution plane autónomo.
- **AutoFactory:** herramienta local/manual independiente.
- **Condor:** producto.
- **GrindFlow:** producto.
- **BRVTAL:** producto.

Los siete repositorios son elegibles para el despachador, pero esa elegibilidad **no mezcla sus responsabilidades arquitectónicas**.

---

## ¿Por qué existe?

Hoy los proyectos los construyen agentes de IA (GPT) de forma autónoma. Funcionó, pero aparecieron cuatro problemas:

| Problema | Ejemplo real |
| --- | --- |
| 🔴 El código llega a producción, pero la base de datos no | Condor quedó caído (HTTP 500) porque las migraciones nunca se aplicaron |
| 🔁 Los agentes deshacen decisiones del dueño | Una decisión aprobada fue revertida por otro agente citando una regla vieja |
| 💸 Trabajo sin freno | Un PR de ~100 líneas acumuló ~70 commits de ida y vuelta con los revisores automáticos |
| 🧬 Cada proyecto evoluciona distinto | Etiquetas, releases y CI diferentes en cada repositorio |

Factory resuelve esto centralizando las reglas y automatizaciones, con límites claros.

---

## ¿Cómo funciona?

```mermaid
flowchart LR
    F["🏭 factory<br/>reglas + CI + scripts"] --> C["Condor"]
    F --> G["GrindFlow"]
    F --> B["BRVTAL"]
    F --> R["FactoryRunner"]
    F --> N["Proyecto nuevo<br/>(desde el template)"]
```

1. **Factory publica el kit:** CI, deploy con rollback, releases, etiquetas, coordinación de agentes y reglas.
2. **Cada proyecto lo usa** con una línea (`uses: pl0n3r/factory/...@v1`) y solo configura lo suyo: dominio, tecnología e idioma.
3. **Una mejora aquí llega a todos los proyectos** automáticamente, sin copiar nada.
4. **Un proyecto nuevo** se crea desde el template y nace con todo funcionando.

### El ciclo de cada cambio (cuando el kit esté listo)

```mermaid
flowchart LR
    I["Issue con criterios<br/>de aceptación"] --> A["Agente con su<br/>rol profesional"]
    A --> P["PR"] --> Q["CI + revisión<br/>(máx. 3 rondas)"]
    Q --> M["Merge automático"] --> D["Deploy: backup →<br/>migración → release"]
    D --> S{"¿Producción<br/>sana?"}
    S -- Sí --> V["🟢 Validado"]
    S -- No --> R["↩️ Rollback<br/>automático"]
```

---

## ¿Qué va a contener?

| Pieza | Para qué sirve |
| --- | --- |
| **CI común** | Las mismas pruebas y controles de calidad en todos los proyectos |
| **Deploy con rollback** | Backup → migración → publicación; si algo falla, vuelve solo a la versión anterior |
| **Releases** | Cada versión crea su tag y su GitHub Release automáticamente |
| **Etiquetas** | Todo Issue y PR con tipo, prioridad y estado, validado |
| **Coordinación** | `/tomar`, `/liberar`: evita que dos agentes hagan lo mismo |
| **Decisiones del dueño como código** | Ningún agente puede revertir una decisión tuya |
| **Roles profesionales** | El agente actúa como DBA, SRE, UX, diseñador, marketing… según la tarea |
| **Métricas y costos** | Tiempo, calidad y costo de cada tarea, con reporte semanal |
| **Template** | Esqueleto para crear un proyecto nuevo ya listo |

---

## Estado actual

✅ **TANDA 1 está cerrada.** Condor, GrindFlow y BRVTAL tienen evidencia de producción verde; Factory publicó `v1.0.0` y el self-test consumidor de `@v1` pasó. La adopción del kit está en **TANDA 2**.

El canal `v1` solo cambia mediante una puerta humana ligada al SHA exacto. Los cambios posteriores de Factory se preparan en `main` y llegan a los consumidores únicamente tras un release protegido `v1.x`.

| Etapa | Estado |
| --- | --- |
| Plan, kit base, roles, orquestación, aceptación, métricas, costos y memoria (#1–#14) | ✅ Cerrado |
| Privacidad como código (#54) | ✅ Cerrado |
| Raíz de confianza del canal v1 (#83) | ✅ Cerrado |
| Publicación `v1.0.0` | ✅ Publicado + self-test en verde |
| Catálogo canónico de etiquetas (#100/#105) | ✅ Integrado en `main` |
| `v1.0.5` | ✅ Publicado; desbloqueó soporte Node y expuso el defecto de permission envelope downstream |
| Candidato de mantenimiento `v1.0.6` (#171) | 🚧 Corrige coordinación reusable/caller; pendiente merge + puerta exact-SHA |
| Release de mantenimiento `v1.x` | 🔐 Requiere puerta `factory-release` por SHA |
| Adopción en Condor, GrindFlow, BRVTAL y FactoryRunner | 🚧 TANDA 2 en curso |
| Revisión jurídica (#53) | 🧭 Decisión humana separada |
| GitHub Pages de la cabina (#35) | 🧭 Default seguro B: no publicar |

### Estado de las tandas

#### TANDA 2 · adopción del kit

TANDA 2 termina **solo cuando los cuatro épicos canónicos estén cerrados como completados**. El estado actual es:

| Proyecto | Épico | Estado |
| --- | --- | --- |
| Condor | #192 | ✅ Completado |
| GrindFlow | #129 | 🚧 Pendiente / bloqueado |
| BRVTAL | #630 | 🚧 Pendiente / bloqueado |
| FactoryRunner | #1 | 🚧 Pendiente / bloqueado |

**Condición global:** mientras cualquiera de esos cuatro épicos siga abierto, TANDA 3 no comienza globalmente.

#### TANDA 3 · desarrollo normal

TANDA 3 comienza cuando los cuatro épicos de TANDA 2 estén completados. Su prioridad operativa es:

**incidente de producción → crítica → alta → media**

Frentes iniciales definidos por `PLAN-AGENTES.md`:

- **Condor:** pedidos, e-commerce, stock y recuperación de cuenta.
- **GrindFlow:** recuperación de cuenta y continuación del roadmap.
- **BRVTAL:** recuperación de cuenta y pendientes de producto.
- **FactoryRunner:** identity/heartbeat → órdenes/eventos → adapters programáticos → browser execution.
- **Factory, ControlBot y AutoFactory:** también forman parte de la cola automática; se despachan por readiness y prioridad sin alterar su rol arquitectónico.

Esta sección es un resumen operativo; [`PLAN-AGENTES.md`](PLAN-AGENTES.md) sigue siendo la fuente de verdad.

El cierre histórico está resumido en **[docs/tanda1-handoff.md](docs/tanda1-handoff.md)** y el proceso de publicación en **[docs/release-bootstrap.md](docs/release-bootstrap.md)**.

### Roadmap cronológico

| Orden | Hito | Estado actual |
| --- | --- | --- |
| 1 | #1–#14 + #54 | ✅ TANDA 1 técnica cerrada |
| 2 | Primer canal `v1` + `v1.0.0` | ✅ Publicado y validado |
| 3 | #100/#105 catálogo de etiquetas | ✅ Integrado en `main` |
| 4 | Release protegido posterior | 🔐 `factory-release` + SHA exacto |
| 5 | Condor#192 · GrindFlow#129 · brvtal#630 · FactoryRunner#1 | 🚧 TANDA 2 |
| 6 | TANDA 3 · desarrollo normal | 🔒 Bloqueada hasta completar los cuatro épicos de TANDA 2 |

---

## ¿Qué hago yo (el dueño)?

**Casi nada.** Esa es la idea. Abres un agente de IA (GPT u otro), le pegas uno de estos prompts y lo dejas trabajar.

### Los dos modos de lanzar un agente

| Modo | Cuándo usarlo | Qué hace el agente |
| --- | --- | --- |
| **Dirigido** | Quieres que trabaje en un proyecto concreto | Lee factory y trabaja **solo** en ese proyecto |
| **Despachador** | Quieres que él decida dónde hace falta | Lee factory, revisa todos los proyectos y **baja al que más lo necesita** |

**Modo dirigido** (cambia el repositorio según el proyecto):

```
Trabajas en el repositorio pl0n3r/Condor. Lee y ejecuta https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md para este repositorio.
```

**Cola automática de Factory:** `pl0n3r/factory`, `pl0n3r/Condor`, `pl0n3r/GrindFlow`, `pl0n3r/brvtal`, `pl0n3r/ControlBot`, `pl0n3r/AutoFactory` y `pl0n3r/FactoryRunner`. Los siete son elegibles; su rol arquitectónico no cambia por entrar en la cola.

**Modo despachador:**

```
Lee y ejecuta https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md en modo despachador.
```

El despachador elige en este orden: HEALTH degradado → incidente abierto → reparación activa válida → decisión tuya ya respondida → prioridad crítica → alta → media. Antes de elegir aplica readiness, reservas, dependencias, PR equivalente y claims de paths para no duplicar trabajo; anuncia en el Issue por qué eligió ese frente y, al terminar, vuelve a elegir. Detalle en la sección 0 de [PLAN-AGENTES.md](PLAN-AGENTES.md).

### Cómo combinarlos

- **Un solo agente:** modo despachador.
- **Varios agentes a la vez:** pueden operar en modo despachador; Factory aplica readiness, reservas y claims para repartir trabajo entre los siete repositorios sin duplicarlo.
- **Algo urgente en un proyecto:** un agente dirigido a ese proyecto.

### Qué más te toca

1. Cuando un agente termine o se detenga, vuelve a lanzarlo con el mismo prompt: él sabe en qué va.
2. Responder solo las decisiones que te corresponden (**producto, marca, dinero, legal, datos reales de clientes, mover/publicar el canal `v1` de Factory o pasar a live**). Te llegan asignadas en GitHub con la etiqueta `decisión: dueño` y aparecen en la cabina.
3. Mirar la **cabina de mando**: https://pl0n3r.github.io/factory/ (estado de todos los proyectos, actualizado cada hora).

### Cómo funciona por dentro

```
Prompt → factory/PLAN-AGENTES.md (cómo trabajar)
       → factory/agentes/roles/<rol>.md (qué profesional ser)
       → AGENTES.md del proyecto (cómo es ese proyecto)
       → trabajo en el proyecto: /tomar → código → PR → CI
```

---

## Proyectos de la fábrica

| Proyecto | Qué es | Sitio |
| --- | --- | --- |
| [Condor](https://github.com/pl0n3r/Condor) | Plataforma multi-empresa: catálogo, inventario, pedidos y tienda pública | [condorapp.com.co](https://www.condorapp.com.co) |
| [GrindFlow](https://github.com/pl0n3r/GrindFlow) | SaaS de gestión corporativa | [grindflow.com.co](https://www.grindflow.com.co) |
| [BRVTAL](https://github.com/pl0n3r/brvtal) | Sitio público y panel editorial DISCADMIN | [brvtal.com.co](https://www.brvtal.com.co) |
| [FactoryRunner](https://github.com/pl0n3r/FactoryRunner) | Execution plane autónomo: agentes, órdenes, adapters y browser execution | En construcción · `control.condorapp.com.co` como target primario |

### Infraestructura y herramientas dentro de la cola automática

- **Factory:** gobierno, kit y capacidades transversales.
- **ControlBot:** centro de mando/control plane privado.
- **FactoryRunner:** execution plane autónomo.
- **AutoFactory:** herramienta local/manual independiente en su arquitectura funcional.
- **Condor, GrindFlow y BRVTAL:** productos.

Los siete repositorios comparten elegibilidad de despacho automático. Esto no fusiona responsabilidades ni convierte AutoFactory en dependencia de FactoryRunner/ControlBot.

---

## Glosario rápido

- **Kit:** el conjunto de herramientas compartidas que publica este repo.
- **Reusable workflow:** un proceso de CI escrito una vez aquí y usado por todos los proyectos.
- **Rollback:** volver automáticamente a la versión anterior si la nueva falla.
- **Migración:** cambio en la estructura de la base de datos que acompaña al código nuevo.
- **Template:** plantilla para crear un proyecto nuevo con todo incluido.
- **Épico:** un Issue grande que agrupa varios Issues más pequeños.


---

## Living Software

**Living Software está integrado y endurecido a nivel de arquitectura/protocolo; #227 cierra el hardening final de provenance.** Ese estado no amplía autoridad externa ni habilita producción autónoma irrestricta.

El objetivo es que Factory pueda observar, recordar, aprender, proponer, experimentar, medir, podar y reparar sin convertir aprendizaje en autoridad. El contrato canónico está documentado en [docs/factory-living-software.md](docs/factory-living-software.md) y las reglas operativas viven en [PLAN-AGENTES.md](PLAN-AGENTES.md#9-living-software-ciclo-operativo-canónico).

El ciclo de alto nivel es:

`observe → learn → experiment → adopt_or_reject → measure → prune`

Ese resumen no reemplaza el lifecycle completo de Constitution. Toda adopción conserva rollback, trazabilidad, invariantes protegidos y límites de autoridad humana.

### Estado de confianza actual

- **#209 Autonomy authority + canonical evidence:** ✅ cerrado.
- **#211 Factory Lab promotion provenance:** ✅ cerrado.
- **#213 Growth/Pruning source evidence:** ✅ cerrado.
- **#215 Repair human authority + immunity provenance:** ✅ cerrado.
- **#221 deterministic renewal retry:** ✅ cerrado.
- **#223 trusted Repair/Immune provenance:** ✅ cerrado en integridad/append-only.
- **#227 non-self-certifiable provenance:** ✅ cerrado; stores caller-built no constituyen trust productivo y Repair/Immune solo aceptan readers autenticados/read-only.

Con #227 cerrado y sus AC verdes, cerrar **#143** significa **arquitectura/protocolo Living Software integrado y endurecido**. No garantiza autonomía completa, no convierte Promotion/Repair en ejecución automática y **no concede autoridad de producción autónoma irrestricta**.

Las puertas humanas vigentes no cambian: dinero, legal, datos reales/personales, borrado irreversible, publicación/live y demás decisiones reservadas siguen fuera de la autoridad autónoma.
