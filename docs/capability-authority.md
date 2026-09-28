# Capability × Authority v1

Este contrato materializa el límite que Factory ya declara: **autonomía y autoridad
son dimensiones distintas**. Autonomy Engine puede reducir o aumentar supervisión
operativa; nunca crea acciones, scopes, targets ni clases de autoridad.

## Matriz cerrada

Cada capability declara explícitamente cinco acciones:

`observe → propose → experiment → execute → promote_adopt`

Una acción ausente queda denegada. Cada grant además fija scopes y targets exactos.
Un cambio de nivel de autonomía conserva el mismo fingerprint de autoridad.

## Provenance

Los grants y revocaciones se aceptan únicamente desde
`AuthenticatedDecisionReader`. Stores mutables construidos por el caller sirven
como fixtures, pero no conceden autoridad. Cada evento conserva actor, razón,
`decision_ref`, `source_id` y fingerprint de la decisión.

## Puertas humanas

`money`, `legal`, `personal_data`, `irreversible_delete` y
`authority_expansion` permanecen human-gated. El contrato puede describirlas y
observarlas, pero no convertirlas en ejecución autónoma ni en promoción/adopción.

## Integración con Autonomy Engine

`CapabilityAuthorityRegistry.autonomy_scope()` acepta únicamente los niveles
canónicos del Autonomy Engine y devuelve la misma matriz/fingerprint de autoridad
en todos ellos. Performance, Fitness o Risk pueden modificar supervisión dentro
de esa autoridad; nunca agregan permisos.

## Límites

Este módulo no ejecuta acciones, no persiste grants, no crea credenciales, no
consulta proveedores externos y no sustituye Constitution, Autonomy Engine,
Feedback Mesh ni las puertas humanas.
