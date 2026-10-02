# Validación de coordinación post-merge

## Problema

La coordinación valida cada PR mientras está abierto: rama canónica, relación con
el Issue, reserva activa, contrato de aceptación y colisiones. Un evento
`pull_request: closed` también ocurre después de un merge. Si ese merge usa
`Closes #N`, GitHub puede cerrar el Issue antes de que una revalidación tardía
termine; volver a exigir entonces que el Issue siga abierto produce un falso rojo
sobre trabajo que ya fue aceptado y fusionado.

## Contrato

El evento de merge es terminal para el gate `validar-pr`.

- El caller canónico conserva `pull_request: closed`, porque `pr-event` todavía
  debe reconciliar la reserva y el estado.
- El job `validar-pr` del caller solo invoca `operation: validate` cuando
  `github.event.pull_request.merged != true`.
- El reusable aplica la misma defensa: una llamada `validate` originada por un
  payload `pull_request` con `merged == true` queda en `skipped`.
- Un cierre **sin merge** tiene `merged == false` y no recibe esta excepción.

La defensa doble evita que un consumidor antiguo o un wiring parcial convierta
un merge válido en un check rojo, sin convertir el estado `closed` por sí solo
en autoridad para saltarse validaciones.

## Frontera de seguridad

La neutralidad post-merge no cambia `validate_pull()`. Para cualquier PR que
siga abierto, el coordinador conserva el comportamiento fail-closed existente:
el Issue debe estar abierto, la branch debe ser `trabajo/issue-N`, la reserva y
su identidad deben ser válidas, la relación de cierre debe corresponder y no
puede haber colisiones incompatibles.

Un PR abierto cuyo Issue fue cerrado manualmente continúa fallando con
`Issue #N debe estar abierto durante el PR`. Un PR cerrado sin merge tampoco se
trata como fusionado.

## Evidencia reproducible

El contrato se cubre en:

- `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral`;
- `tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate`;
- `tests/test_coordinar_trabajo.py::CoordinacionTests::test_open_pr_with_closed_issue_still_fails_closed`.

La suite `Tests de scripts` es la evidencia agregada requerida por Factory.
La reversión es un revert de estos cambios declarativos y no requiere migración
de datos ni cambios de permisos.
