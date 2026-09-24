# 🏭 Factory: la fábrica de software de pl0n3r

**Factory es el "manual y la caja de herramientas" que comparten todos los proyectos.** En vez de que cada proyecto (Condor, GrindFlow, BRVTAL…) tenga sus propias reglas, su propio CI y sus propios scripts copiados y cada vez más distintos, todo eso vive **una sola vez aquí** y los proyectos lo usan.

> **En una frase:** aquí se define *cómo* se construye el software; en cada proyecto solo se define *qué* se construye.

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

🚧 **Kit v1 en cierre de madurez.** El bootstrap, kit base, roles, orquestación, aceptación ejecutable, métricas, costos, feedback de producto y memoria institucional ya están integrados. #9 y #10 conservan bloqueos externos verificables; #11 implementa el camino previo a producción.

| Etapa | Estado |
| --- | --- |
| Plan y reglas definidos | ✅ Hecho |
| Arranque del repositorio (#14) | ✅ Hecho |
| Kit base reusable (#1) | ✅ Integrado |
| Roles + orquestación + aceptación (#2–#4) | ✅ Integrado |
| Métricas + costos + feedback (#5–#7) | ✅ Integrado |
| Memoria institucional (#8) | ✅ Integrado |
| Puertas humanas (#9) | ⛔ Implementado · falta confirmar push móvil real |
| Resiliencia (#10) | ⛔ Slice técnico verde · faltan identidades separadas + restore externo |
| Entornos previos (#11) | 🚧 En implementación |
| Legal y datos (#12) | ⏳ Siguiente |
| Publicación v1.0.0 | ⏳ Tras cerrar requisitos pendientes y validar template |

### Roadmap cronológico

| Orden | Issue | Estado |
| --- | --- | --- |
| ✅ | [#14](https://github.com/pl0n3r/factory/issues/14) | Arranque integrado |
| ✅ | [#1](https://github.com/pl0n3r/factory/issues/1) | Kit común base integrado |
| ✅ | [#2](https://github.com/pl0n3r/factory/issues/2) | Roles profesionales integrados |
| ✅ | [#3](https://github.com/pl0n3r/factory/issues/3) · [#4](https://github.com/pl0n3r/factory/issues/4) | Orquestador · aceptación ejecutable |
| ✅ | [#5](https://github.com/pl0n3r/factory/issues/5) · [#7](https://github.com/pl0n3r/factory/issues/7) | Evaluación de agentes · costos |
| ✅ | [#6](https://github.com/pl0n3r/factory/issues/6) · [#8](https://github.com/pl0n3r/factory/issues/8) | Feedback de producto · memoria |
| ⛔ | [#9](https://github.com/pl0n3r/factory/issues/9) · [#10](https://github.com/pl0n3r/factory/issues/10) | Implementación técnica lista; evidencia externa pendiente |
| 🚧 | [#11](https://github.com/pl0n3r/factory/issues/11) | Entorno preview previo a producción |
| ⏳ | [#12](https://github.com/pl0n3r/factory/issues/12) | Cumplimiento legal y datos |
| — | [#13](https://github.com/pl0n3r/factory/issues/13) | Épico de madurez |

---

## ¿Qué hago yo (el dueño)?

**Casi nada.** Esa es la idea.

1. Abrir un agente en cada repositorio (factory, Condor, GrindFlow, BRVTAL) con **este único prompt**:

   ```
   Lee y ejecuta https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md para el repositorio en el que estás trabajando.
   ```

2. Cuando un agente termine o se detenga, volver a lanzarlo con el mismo prompt: él solo sabe en qué etapa va.
3. Responder únicamente las decisiones que te corresponden: **producto, dinero, legal, datos reales de clientes o salir a producción (live)**.

El detalle de etapas y reglas para los agentes está en **[PLAN-AGENTES.md](PLAN-AGENTES.md)**.

---

## Proyectos de la fábrica

| Proyecto | Qué es | Sitio |
| --- | --- | --- |
| [Condor](https://github.com/pl0n3r/Condor) | Plataforma multi-empresa: catálogo, inventario, pedidos y tienda pública | [condorapp.com.co](https://www.condorapp.com.co) |
| [GrindFlow](https://github.com/pl0n3r/GrindFlow) | SaaS de gestión corporativa | [grindflow.com.co](https://www.grindflow.com.co) |
| [BRVTAL](https://github.com/pl0n3r/brvtal) | Sitio público y panel editorial DISCADMIN | [brvtal.com.co](https://www.brvtal.com.co) |

---

## Glosario rápido

- **Kit:** el conjunto de herramientas compartidas que publica este repo.
- **Reusable workflow:** un proceso de CI escrito una vez aquí y usado por todos los proyectos.
- **Rollback:** volver automáticamente a la versión anterior si la nueva falla.
- **Migración:** cambio en la estructura de la base de datos que acompaña al código nuevo.
- **Template:** plantilla para crear un proyecto nuevo con todo incluido.
- **Épico:** un Issue grande que agrupa varios Issues más pequeños.
