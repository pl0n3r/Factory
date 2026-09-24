# Especificaciones con criterios de aceptación ejecutables

Factory distingue dos capas de calidad:

1. **gates genéricos**, como lint, tests globales, coordinación, CodeQL y Sonar;
2. **criterios específicos del Issue**, definidos como `AC-NN` y verificados por el job `Criterios de aceptación`.

Un PR no está “hecho” si solo pasa la primera capa.

## Secciones obligatorias

El Issue debe contener exactamente una sección no vacía para:

- `### Contexto`;
- `### Alcance`;
- `### Fuera de alcance`;
- `### Criterios de aceptación`;
- `### Contrato ejecutable`.

Los criterios humanos usan:

`- [ ] [AC-01] descripción verificable`

El estado visual del checkbox es informativo. La fuente de verdad de cumplimiento es el job de CI.

## Marker máquina

El contrato enlaza cada ID humano con evidencia:

```html
<!-- factory-acceptance {"version":1,"criteria":[
  {"id":"AC-01","kind":"test","target":"tests/test_api.py::ApiTests::test_crea_recurso"},
  {"id":"AC-02","kind":"check","target":"E2E checkout"}
]} -->
```

Los IDs del marker deben coincidir exactamente con los IDs humanos.

### kind=test

Solo acepta un target con forma:

`ruta/test_archivo.py::Clase::test_metodo`

La ruta debe vivir en un directorio de tests permitido (`tests/`, `metricas/`, `seguridad/`, `lecciones/` o `producto/`), ser relativa y segura. Factory carga ese archivo y ejecuta **exactamente un** caso unittest. No evalúa shell del Issue.

### kind=check

Exige un check run del mismo SHA con nombre exacto, `status=completed` y `conclusion=success`. Si existen varias ejecuciones con ese nombre, manda la de ID más reciente.

`Validar` y `Criterios de aceptación` no pueden referenciarse como evidencia para evitar ciclos/autovalidación.

## Orden de CI

En Factory:

`Lint + Tests + Coordinación → Criterios de aceptación → Validar`

El job de aceptación consulta los check-runs **después** de que sus dependencias terminaron, por lo que un criterio `kind=check` no depende de polling.

Para consumidores, `.github/workflows/aceptacion.yml` expone el mismo gate reusable. El template incluye un caller que deriva el Issue desde la rama `trabajo/issue-N`.

## Issue Form obligatorio

`.github/ISSUE_TEMPLATE/trabajo.yml` exige las cinco secciones y `config.yml` deshabilita blank issues. El formulario no inventa criterios: el agente redacta AC-NN y el marker máquina con evidencia concreta.

## Compatibilidad

Los PR históricos abiertos deberán migrar su Issue al contrato cuando vuelvan a sincronizarse con `main`. No se fabrican criterios retrospectivos; al retomar cada Issue se documenta el comportamiento que realmente debe probarse.
