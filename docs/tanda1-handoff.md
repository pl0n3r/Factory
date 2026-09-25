# Handoff de TANDA 1

Estado: **CERRADA**. Condor, GrindFlow y BRVTAL registraron producción verde y Factory publicó/validó `v1.0.0` con self-test del canal `@v1`.

Este documento conserva el cierre histórico; los Issues fuente siguen siendo la evidencia canónica.

## #9 — puertas de decisión humana · CERRADO

La clasificación de puertas, asignación y recepción móvil real quedaron verificadas. Las decisiones humanas siguen siendo explícitas y nunca se infieren de un workflow verde.

## #10 — resiliencia del dueño y de la fábrica · CERRADO

El modelo vigente es por capacidades: CI y observación usan `github-token:ephemeral` con mínimo privilegio; deploy usa `hostinger:git`; la escritura cross-repo requiere una **GitHub App dedicada**. El diseño evita multiplicar identidades cuando una capacidad de mínimo privilegio es suficiente.

## #12 — cumplimiento técnico de datos/licencias · CERRADO

La evidencia técnica de datos/licencias quedó integrada. Cerrar #12 **no equivale a afirmar aprobación jurídica**; la revisión humana permanece separada en #53.

## #13 — épico de madurez · CERRADO

#13 y #54 quedaron cerrados antes del primer release. El frente de privacidad incluyó #71/#78 y la adopción del contrato ampliado de seis documentos.

## Cierre técnico

- #1–#14: cerrados conforme al contrato vigente.
- #54: privacidad como código cerrada tras revalidación de los tres productos y evidencia real del auditor.
- #83: raíz de confianza del canal `v1` resuelta.
- `v1.0.0`: GitHub Release publicada y self-test consumidor en verde.
- TANDA 1 global: completada.

## TANDA 2 · EN CURSO

La cola canónica actual adopta el kit publicado en Condor#192, GrindFlow#129, brvtal#630 y FactoryRunner#1 siguiendo `PLAN-AGENTES.md`. El cierre de TANDA 1 anterior permanece histórico y no se reescribe.

Factory continúa manteniendo el kit. Un cambio en `main` no modifica por sí solo el canal publicado `@v1`: debe pasar el proceso de mantenimiento descrito en **[release-bootstrap.md](release-bootstrap.md)**.

## Releases de mantenimiento

El primer release usa la categoría histórica `release-1.0.0`. Cualquier release posterior de la major `v1` usa una puerta humana `factory-release`, aprobación ligada al SHA exacto, movimiento manual del tag mayor y el workflow **Release Factory v1.x**.

**Default seguro:** no mover `v1` ni publicar un release nuevo sin la puerta correspondiente.

## #53 — revisión jurídica humana · SEPARADA

#53 conserva la revisión jurídica de la documentación de datos personales como decisión humana independiente. El cierre técnico no equivale a afirmar aprobación jurídica.

## #35 — exposición pública de la cabina · SEPARADA

#35 sigue siendo una decisión de producto. El default B continúa aplicado; **#35 no bloquea el cierre técnico de TANDA 1**.
