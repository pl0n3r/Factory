# Contrato técnico de cumplimiento y licencia de dependencias

Estado: **propuesta de gate documental**, no certificación jurídica de Condor, GrindFlow o BRVTAL.

## Objetivo y límites

El script `seguridad/cumplimiento.py` comprueba que un producto tenga un inventario documental *referenciado* y que las dependencias de sus archivos de bloqueo declaren licencias. No consulta datos de titulares, no decide si una excepción legal aplica y no declara compatible una expresión SPDX. La revisión material de términos, retención, transferencias, proveedores y licencias sigue siendo jurídica y de producto.

Para Colombia, comprobar el alcance y la aplicación de la Ley 1581 de 2012, incluida autorización y sus excepciones, a cada tratamiento real, no asumir que un formato genérico equivale a cumplimiento: https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981 y orientación SIC https://sedeelectronica.sic.gov.co/politica-de-tratamiento-de-datos-personales. Las expresiones de licencia se identifican con SPDX (https://spdx.org/licenses/). El detector no consulta el catálogo SPDX en línea, y **su salida no confirma que una licencia exista en dicho catálogo ni que dos licencias sean compatibles**.

## Contrato de privacidad por producto

Guardar un JSON para cada tratamiento (no un único documento ficticio para todo un SaaS). Campos exactos: `version: 1`, `project` (`pl0n3r/Condor`, `pl0n3r/GrindFlow` o `pl0n3r/brvtal`), `scope`, `purpose` (códigos sin texto libre), `data_categories` (códigos), `consent_or_exception` (`consent_documented`, `exception_for_legal_review`, `no_personal_data`), `evidence` y `reviewed_at` UTC.

`evidence` exige siete referencias no sensibles a evidencias revisadas: `privacy_policy`, `terms`, `processing_register`, `rights_channel`, `retention_schedule`, `vendor_review`, `legal_review`. No guardar nombres de titulares, correos reales, bases de datos ni enlaces firmados en este manifiesto. El validador rechaza campos adicionales y revisiones con más de 365 días conforme a la **política interna de refresco**, no a un plazo legal general.

**Importante:** `exception_for_legal_review` solo deja constancia de que una excepción fue planteada: no autoriza tratar datos por sí sola. `consent_documented` tampoco demuestra la validez del consentimiento. El responsable debe contrastar evidencias y hechos del producto antes de activar producción.

## Inventario de licencias

`--composer-lock` inspecciona `packages` y `packages-dev`; `--npm-lock` inspecciona `packages` incluidas las transitivas. Falta de licencia, licencia indeterminada, versión faltante y formato no reconocido → error. Licencias múltiples declaradas como array de Composer → revisión manual antes de automatizar. Las expresiones simples `MIT OR Apache-2.0` se conservan como texto; no hay resolución de compatibilidad, recursividad SPDX completa ni búsqueda de licencias faltantes en la red.

Ejemplo de invocación para un producto con ambos gestores:

```bash
python3 seguridad/cumplimiento.py \
  --privacy ruta-privada/revision-producto.json \
  --composer-lock producto/composer.lock \
  --npm-lock producto/package-lock.json
```

Sin Composer/npm: `--stdlib-only` indica explícitamente ausencia de esos gestores, **no confirma la ausencia universal de dependencias**. Para Python, Go o bibliotecas descargadas manualmente, incorporar antes un escáner y un contrato específicos.

La salida exitosa conserva estados `documented_not_legally_approved` e `identifiers_present_review_required`; no publicar `compliant: true` o «licencias aprobadas» automáticamente. Los resultados no incluyen datos del manifiesto ni nombres de dependencias; los errores tampoco imprimen payloads.

## Ruta de integración y evidencia pendiente de #12

- Las pruebas propias son `PYTHONPATH=seguridad python3 -m unittest discover -s seguridad -p 'test_cumplimiento.py'`.
- La integración a `seguridad.yml` debe hacerse tras resolver su conflicto de propiedad con el PR #25, ejecutando tests y gate solo en el repositorio producto que adjunte una revisión real.
- Cada proyecto debe aportar al menos una evidencia documentada y verificada por tratamiento y los archivos lock reales de su stack. Un fixture de tests **no** es prueba de cumplimiento de ningún producto.
- Cierre de #12 requiere CI y evidencia de la revisión material, no únicamente la estructura o la salida del script.
