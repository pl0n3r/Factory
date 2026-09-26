# Autonomy Engine v1

Autonomy Engine modela autonomía como una capacidad **ganada por evidencia**,
reversible y separada de la autoridad.

## Escalera cerrada

Una capacidad solo puede recorrer, de a un nivel:

`observe → propose → shadow → supervised → autonomous`

No hay saltos. Cada promoción queda registrada en historia append-only con
razón, evidencia y fingerprints de Fitness y Risk.

## Condiciones de promoción

Una promoción exige:

- Fitness completo, sin dimensiones faltantes ni regresiones protegidas;
- claim `equal` o `improved`;
- Risk con contexto crítico completo;
- evidencia no vacía.

El nivel `autonomous` no se concede con riesgo `high`.

## Fallos y downgrade

Los fallos nunca se esconden:

- `minor`: baja un nivel;
- `major`: baja dos niveles;
- `critical`: revoca hasta `observe`.

Cada downgrade crea una nueva entrada; la historia previa no se modifica.

## Autoridad constitucional

La autonomía no agrega permisos. Todos los niveles conservan exactamente el
mismo fingerprint de autoridad constitucional, los invariantes protegidos y
`external_permissions_added=[]`.

Dinero, decisiones legales, datos personales y borrado irreversible siguen fuera
de la autoridad autónoma. Subir de nivel significa menos supervisión operativa
para una capacidad ya permitida, no más poder.

## Fuera de alcance

Autonomy Engine no crea credenciales, no modifica rulesets, no concede permisos
externos, no ejecuta dinero/legal/datos/borrados y no sustituye puertas humanas.
