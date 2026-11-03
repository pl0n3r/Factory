# CodeRabbit: una solicitud FINAL y cambios posteriores al HEAD

## Incidente y evidencia
Factory #2003 / GrindFlow #739, PR #838: HEAD de referencia inicial
`1c2d65baa155587a0c4045051cdbdbf374c30753`. La timeline autenticada
posteriormente registró otro HEAD `e4c9a70df9919b6f6661df75a6f4bbc72daf7e59`;
la validez de los gates siempre se reevalúa contra el HEAD vigente.
La petición final del propietario fue comentario #6593527672, seguida de un
`Review rate limited` emitido por CodeRabbit **para un SHA anterior**.
El HEAD actual muestra `CodeRabbit: skipped`. No existe una revisión
terminal de CodeRabbit sobre el HEAD actual. Los checks técnicos verdes,
el comentario previo, el bot previo y el `skipped` no la sustituyen.

## Contradicción y resolución segura
La política exige exactamente un retry OWNER y un rate-limit auténtico del
**mismo HEAD** para el fallback SHA-less. Repetir `@coderabbitai review`
en el PR original incumpliría la instrucción de realizar una sola petición
FINAL por PR y consumiría cuota compartida sin autorización especial.

La corrección de Factory #2003 es **fail-closed**: cuando una timeline
autenticada demuestra una sola petición OWNER y un rate-limit oficial
anteriores al commit final, Policy emite un motivo preciso en vez de la
instrucción engañosa de volver a solicitar la revisión. El resultado sigue
siendo ERROR y NO-GO; no se convierte una fuente de calidad UNKNOWN en
`APPROVED`, `success` ni `D-070`. Las pruebas de identidad, timeline,
CI, reserva y seguridad siguen obligatorias.

## Reentrada válida, solo con decisión expresa del OWNER
- **A — autorizar la sustitución del PR**, no un bypass. El OWNER debe
  aprobar expresamente un nuevo PR/revisión con consumo de la cuota
  compartida; cerrar el PR antiguo y liberar su reserva solo mediante el
  procedimiento canónico, sin force-push que oculte pruebas. Crear un nuevo
  contrato/lease V3 válido y un PR nuevo que reproduzca fielmente la solución
  requerida; sobre el HEAD definitivo, con todos los checks en verde, enviar
  **una sola** revisión FINAL del nuevo PR. Exigir respuesta oficial
  auténtica terminal y exact-HEAD, sin vulnerabilidades o bugs graves,
  antes del squash. Un rate-limit del PR antiguo no migra al nuevo.
- **B — conservar el veto (predeterminado)**. Si no hay aprobación expresa
  o no hay fuente nueva de calidad auténtica y exact-HEAD, mantener PR #838
  abierto y bloqueado; no repetir comandos, no usar D-070 fuera de sus
  requisitos, no ocultar el check y no fusionar.

También es válida una revisión terminal de CodeRabbit que el proveedor
publique espontáneamente sobre el mismo HEAD, **si** GitHub autentica
identidad, cobertura y finalización y no hay findings graves. No se
presume que tal revisión vaya a llegar.

## Evidencia y gobierno
Conservar en el Issue un registro inequívoco de la opción escogida, el
SHA exacto, quién autorizó, los checks y el nuevo identificador de PR.
**El documento no es autorización y no crea un journal humano.**
La decisión A requiere un acto nuevo y expreso del OWNER; un mensaje
genérico como «sigue», un `skipped`, una respuesta rate-limit antigua o
una revisión sin HEAD verificable no constituyen aprobación.

El cambio de diagnóstico aquí propuesto no altera D-069/D-070, la
protección de ramas, CI `Validar`, CodeQL, SonarCloud, CodeRabbit,
las reservas V3, el kill switch ni el veto a findings high/critical.
En fase `live` no hay autofusión. No mover `Factory@v1`, no ejecutar
deploys ni interactuar con datos reales por este procedimiento.
