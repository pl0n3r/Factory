# Preflight F2B — consumidores de reusables de Factory

Esta prueba **solo lee** los workflows de seis checkouts existentes en una raíz local: `Condor`, `GrindFlow`, `brvtal`, `ControlBot`, `AutoFactory` y `FactoryRunner`. No accede a GitHub, no utiliza secretos ni modifica referencias/tags. Forma parte de la fase F2 del [épico #1296](https://github.com/pl0n3r/Factory/issues/1296).

```bash
python3 scripts/f2_caller_preflight.py --root /ruta/a/checkouts --target readme.yml
python3 scripts/f2_caller_preflight.py --root /ruta/a/checkouts --target roles.yml --target etiquetas.yml
python3 -m unittest tests.test_f2_caller_preflight
```

**Contrato:** devuelve JSON determinista y código `2` (`BLOCKED`) si falta algún checkout, falta su directorio `.github/workflows`, hay archivos YAML ilegibles o encuentra `uses: pl0n3r/factory/.github/workflows/<target>@<ref>` dentro de las seis fuentes. Reconoce `.yml` y `.yaml`, referencias `@v1` y refs inmovilizadas. El código `0` (`SAFE`) significa **solo** que no se observaron callers de esos targets en los seis checkouts inspeccionados, no que puedan borrarse inmediatamente.

## Límites y puerta de adopción

- Este inventario no representa otros forks, callers externos, branches ni repositorios a los que no se tenga acceso. Para publicar un reemplazo o retirar un reusable hace falta otro contrato V3 con los consumidores migrados, regresiones, gates de release y prueba de no ruptura en cada caller.
- Preservar CI, privacidad, CodeQL, Sonar, roles, permisos mínimos, etiquetas exigidas, `Factory@v1` y revisión CodeRabbit final. Ni el preflight ni su `SAFE` autorizan mover un tag o saltar una puerta humana.
- Un reporte `BLOCKED` no debe resolverse suprimiendo la referencia en una rama ajena; la migración corresponde a los repos consumidores mediante sus propias reservas V3.

**Reversión:** squash-revert exclusivamente de esta hoja (un script, su test y el documento); no deja cambios en workflows o productos.
