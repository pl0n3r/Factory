# Handoff de TANDA 1

Estado: **CERRADA**. Condor, GrindFlow y BRVTAL registraron producción verde y Factory publicó/validó `v1.0.0` con self-test del canal `@v1`.

Este documento conserva el cierre histórico; los Issues fuente siguen siendo la evidencia canónica.

## Cierre técnico

- #1–#14: cerrados conforme al contrato vigente.
- #54: privacidad como código cerrada tras revalidación de los tres productos y evidencia real del auditor.
- #83: raíz de confianza del canal `v1` resuelta.
- `v1.0.0`: GitHub Release publicada y self-test consumidor en verde.
- TANDA 1 global: completada.

## TANDA 2 · EN CURSO

Los productos pueden adoptar el kit publicado en Condor#192, GrindFlow#129 y brvtal#630 siguiendo `PLAN-AGENTES.md`.

Factory continúa manteniendo el kit. Un cambio en `main` no modifica por sí solo el canal publicado `@v1`: debe pasar el proceso de mantenimiento descrito en **[release-bootstrap.md](release-bootstrap.md)**.

## Releases de mantenimiento

El primer release usa la categoría histórica `release-1.0.0`. Cualquier release posterior de la major `v1` usa una puerta humana `factory-release`, aprobación ligada al SHA exacto, movimiento manual del tag mayor y el workflow **Release Factory v1.x**.

**Default seguro:** no mover `v1` ni publicar un release nuevo sin la puerta correspondiente.

## #53 — revisión jurídica humana · SEPARADA

#53 conserva la revisión jurídica de la documentación de datos personales como decisión humana independiente. La evidencia técnica no constituye un dictamen jurídico.

## #35 — exposición pública de la cabina · SEPARADA

#35 sigue siendo una decisión de producto. El default B continúa aplicado hasta una decisión explícita del dueño.
