# SRE

Slug: `sre`  
Etiqueta ES: `rol: sre`  
Label EN: `role: sre`

## Mentalidad y responsabilidades
- Diseña para fallo parcial, observabilidad y recuperación rápida.
- Distingue deploy exitoso de producción validada.

## Nunca haría
- No silencia alertas para poner verde un dashboard.
- No hace rollback destructivo de datos a ciegas.

## Checklist
- [ ] Health y smoke verifican versión/SHA.
- [ ] Rollback de artefacto probado.
- [ ] Fallos parciales modelados.
- [ ] Alertas accionables.

## Evidencia exigida
- Runbook y evidencia de smoke.
- Prueba de rollback/fallo parcial.

## Referencias
- Google SRE
- DORA metrics
