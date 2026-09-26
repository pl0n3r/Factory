# Definition-of-Done Compiler v1

Definition-of-Done Compiler deriva el contrato de evidencia que debe existir
antes de considerar terminada una tarea. No ejecuta pruebas ni concede autoridad:
solo produce requisitos verificables por máquina a partir de la tarea y de un
Project DNA validado.

## Entradas

La tarea declara:

- `change_type`: `code`, `database`, `ci`, `docs`, `security` o
  `unknown`;
- `surfaces`: superficies afectadas, por ejemplo `api`, `web`,
  `database`, `ci` o `release`;
- `risk`: `low`, `medium`, `high` o `unknown`.

Project DNA aporta el fingerprint y el conocimiento verificable del software.

## Invariantes Factory

Todos los contratos conservan como mínimo:

- CI requerida;
- cero hallazgos de revisión abiertos;
- alcance limitado a rutas reclamadas.

Estas invariantes no desaparecen por tipo de cambio, superficie o riesgo.

## Evidencia dinámica

El compilador añade evidencia según el cambio real. Ejemplos:

- código: tests del scope + análisis estático;
- base de datos: verify-plan, backup y compatibilidad de esquema;
- CI: validación de workflow + ejecución representativa;
- docs: lint y links;
- seguridad: scan + casos negativos;
- riesgo medio/alto: plan de rollback; riesgo alto añade smoke exact-SHA.

Cada evidencia tiene `kind` (`test` o `check`) y un `target` con namespace,
por lo que puede ser consumida por automatización posterior.

## Fail-safe ante contexto incompleto

Si el tipo, riesgo, superficies o cualquier dimensión relevante del Project DNA
permanece `unknown`, el compilador no reduce el estándar. Cambia a
`safe-fallback` y exige, además de las invariantes:

- suite completa;
- análisis estático;
- security scan;
- rollback plan;
- completar contexto antes de promoción.

Así, ignorancia nunca equivale a menos evidencia.

## Fuera de alcance

Este componente no ejecuta tests, no hace deploy, no decide puertas humanas y no
promueve releases.
