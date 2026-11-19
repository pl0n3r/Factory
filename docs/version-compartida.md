# Archivos de versión compartidos

Factory#2163. El bump de versión obligatorio en cada PR desplegable y las reservas exclusivas de rutas hacían que solo una hoja a la vez pudiera terminar: todas necesitaban `config/version.php` / `package.json`.

## Qué cambia

Un consumidor declara hasta 4 archivos de versión en su llamada al reusable de coordinación:

```yaml
uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
with:
  operation: validate
  shared_version_paths: '["config/version.php","package.json"]'
```

Para esos archivos, el coordinador:

- no los cuenta como colisión entre dos PRs abiertos **si ambos** solo cambian su línea de versión;
- deja que aparezcan en el diff de un PR aunque su hoja no los reclame (`validar-claims-pr`).

## Qué cuenta como «solo versión»

El patch del archivo (diff exact-HEAD de GitHub) solo puede cambiar, como máximo, 2 líneas en cada sentido, y todas deben ser de este tipo:

- `const <PREFIJO>_VERSION = '0.1.263';` o `const <PREFIJO>_RELEASE_DATE = '2026-11-20';`
- `"version": "0.1.263",`

Cualquier otra línea, un patch ausente o truncado, o un rename hacen que la exención no aplique: rige la regla exclusiva de siempre.

## Reglas para las hojas

- No incluir los archivos declarados en «Rutas reclamadas».
- Subir la versión en el PR. Si otro PR se fusiona antes con el mismo número, rebasar y subir al siguiente: el chequeo de versión del consumidor exige que el PR quede por encima de su base.
- Si la hoja necesita cambiar algo más que la versión en esos archivos (p. ej. dependencias en `package.json`), sí los reclama: ese cambio sigue siendo exclusivo.

## Sin declarar

Si el consumidor no pasa `shared_version_paths` (o lo deja vacío), el comportamiento es idéntico al anterior. Un valor inválido (no JSON, más de 4 rutas, directorios, comodines, rutas relativas o duplicadas) hace fallar el job antes de leer GitHub.

## Límites

- La lista no se aplica en `/tomar`: si una hoja reclama un archivo declarado, la reserva sigue siendo exclusiva.
- Activarlo en cada consumidor requiere publicar Factory y mover `v1`, y luego un cambio en su `work-coordination.yml`.
