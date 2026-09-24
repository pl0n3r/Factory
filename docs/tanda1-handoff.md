# Handoff de TANDA 1

Estado: **#9, #10 y #12 están cerrados; TANDA 1 sigue abierta y `v1.0.0` no está publicado**.

Este documento no reemplaza los Issues fuente. Resume el estado canónico que debe usar un agente para continuar Factory sin reconstruir el historial ni reabrir gates ya resueltos.

## #9 — puertas de decisión humana · CERRADO

La clasificación de puertas, etiqueta `decisión: dueño`, asignación, mención única, limpieza e idempotencia fueron verificadas. La evidencia material pendiente también se obtuvo: el dueño confirmó la recepción efectiva del push móvil generado por una puerta real. Ya no falta **confirmar externamente** esa recepción.

**Regla que permanece:** un workflow verde o un comentario en GitHub no sustituyen evidencia humana cuando el criterio exige observar la recepción en el dispositivo.

## #10 — resiliencia del dueño y de la fábrica · CERRADO

El restore real desde una copia externa a GitHub fue verificado. La decisión vigente del dueño y #72 establecen un modelo por **capacidades**; no se requieren tres aplicaciones GitHub separadas:

- CI: `github-token:ephemeral` con permisos mínimos por job;
- observador: `github-token:ephemeral` de alcance mínimo + endpoints `/health` públicos cuando aplica;
- deploy: `hostinger:git`, sin credencial GitHub persistente de Factory;
- escritura cross-repo: requiere una **GitHub App dedicada** y de mínimo privilegio.

No se admiten PATs personales ni tokens de larga duración. El manifiesto operativo actual es v2; v1 queda solo para diagnóstico/migración.

## #12 — cumplimiento técnico de datos/licencias · CERRADO

Los AC técnicos, el inventario de datos/licencias y la evidencia reproducible de dependencias quedaron integrados. BRVTAL conserva el snapshot npm ligado al SHA auditado y al run `36001724208`, con lock reproducible y validación mediante `inspect_npm()`.

La evidencia material de cada producto continúa en sus Issues dedicados y la **revisión jurídica humana permanece separada en #53**. Cerrar #12 no equivale a afirmar aprobación jurídica ni cumplimiento legal definitivo.

## #13 — épico de madurez · ABIERTO

#13 **ya no está bloqueado por #9, #10 ni #12**. Permanece abierto mientras se completa el frente crítico actual de privacidad como código (#54), incluido el set documental generado de #71 y las condiciones restantes definidas por el propio épico #54.

No se debe reabrir un gate histórico para suplir trabajo nuevo: el trabajo pendiente debe conservar su Issue y su evidencia propios.

## #53 — revisión jurídica humana · SEPARADA

#53 conserva la revisión jurídica de la documentación de datos personales como decisión humana independiente. Factory puede generar, verificar y mantener documentación técnica, pero no convierte esa evidencia en un dictamen jurídico automático.

## #35 — exposición pública de la cabina · SEPARADA

#35 es una decisión de producto. El default B sigue aplicado: **no publicar GitHub Pages todavía**. Mientras se mantenga ese default privado, #35 no bloquea el cierre técnico de TANDA 1.

## Primer release de Factory

Los tags `v1` y `v1.0.0` siguen **ausentes/no publicados** mientras TANDA 1 permanezca abierta.

Antes del primer release:

1. cerrar #1–#14 conforme al contrato vigente, incluido #13;
2. completar los frentes críticos que #13 haya incorporado como requisito de cierre;
3. resolver explícitamente la puerta humana `release-1.0.0`;
4. revalidar el HEAD exacto de `main`;
5. seguir **[release-bootstrap.md](release-bootstrap.md)** para crear el primer `v1`;
6. validar un consumidor real de `@v1`;
7. recién entonces iniciar TANDA 2.

**Default seguro:** `v1.0.0` permanece **no publicado y no autorizado** mientras #13/TANDA 1 sigan abiertos.
