# Paquete para revisión jurídica — Factory

Estado: documented_not_legally_approved

Origen: 6e5000a2e747673644c7ef7600480bdc984c097e · Fecha: 2026-10-21T05:38:40Z

---

## Fuente: docs/cumplimiento-datos-licencias.md

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

`--composer` inspecciona el `./composer.lock` canónico (`packages` y `packages-dev`); `--npm` inspecciona el `./package-lock.json` canónico, incluidas las transitivas. El CLI no acepta rutas arbitrarias. La evidencia de privacidad entra por `stdin`, por lo que su ubicación privada nunca se pasa como argumento. Falta de licencia, licencia indeterminada, versión faltante y formato no reconocido → error. Licencias múltiples declaradas como array de Composer → revisión manual antes de automatizar. Las expresiones simples `MIT OR Apache-2.0` se conservan como texto; no hay resolución de compatibilidad, recursividad SPDX completa ni búsqueda de licencias faltantes en la red.

Ejemplo de invocación para un producto con ambos gestores:

```bash
python3 seguridad/cumplimiento.py --composer --npm \
  < ruta-privada/revision-producto.json
```

Sin Composer/npm: `--stdlib-only` indica explícitamente ausencia de esos gestores, **no confirma la ausencia universal de dependencias**. Para Python, Go o bibliotecas descargadas manualmente, incorporar antes un escáner y un contrato específicos.

La salida exitosa conserva estados `documented_not_legally_approved` e `identifiers_present_review_required`; no publicar `compliant: true` o «licencias aprobadas» automáticamente. Los resultados no incluyen datos del manifiesto ni nombres de dependencias; los errores tampoco imprimen payloads.

## Ruta de integración y evidencia pendiente de #12

- Las pruebas propias son `PYTHONPATH=seguridad python3 -m unittest discover -s seguridad -p 'test_cumplimiento.py'`.
- `seguridad.yml` ya ejecuta `unittest discover -s seguridad -p 'test_*.py'`; al integrar este slice, las regresiones de cumplimiento quedan dentro de `Validar puertas del candidato` sin modificar el workflow.
- Cada proyecto debe aportar al menos una evidencia documentada y verificada por tratamiento y los archivos lock reales de su stack. Un fixture de tests **no** es prueba de cumplimiento de ningún producto.
- Cierre de #12 requiere CI y evidencia de la revisión material, no únicamente la estructura o la salida del script.


---

## Fuente: legal/reglas-datos.yml

{
  "version": 1,
  "owner_placeholder": "[COMPLETAR POR EL DUEÑO]",
  "categories": {
    "identification": {
      "signals": [
        "name",
        "full_name",
        "first_name",
        "last_name",
        "document",
        "document_number",
        "id_number"
      ],
      "sensitive": false,
      "explicit_consent_required": false,
      "maximum_retention": "review_required"
    },
    "contact": {
      "signals": [
        "email",
        "phone",
        "mobile",
        "address",
        "contact_name"
      ],
      "sensitive": false,
      "explicit_consent_required": false,
      "maximum_retention": "review_required"
    },
    "financial": {
      "signals": [
        "bank_account",
        "card_token",
        "billing_address",
        "payment_reference"
      ],
      "sensitive": false,
      "explicit_consent_required": false,
      "maximum_retention": "review_required"
    },
    "location": {
      "signals": [
        "latitude",
        "longitude",
        "location",
        "geo",
        "ip_address"
      ],
      "sensitive": false,
      "explicit_consent_required": false,
      "maximum_retention": "review_required"
    },
    "authentication": {
      "signals": [
        "password_hash",
        "totp_secret",
        "recovery_code",
        "session_token"
      ],
      "sensitive": true,
      "explicit_consent_required": true,
      "maximum_retention": "review_required"
    },
    "sensitive": {
      "signals": [
        "health",
        "biometric",
        "religion",
        "ethnicity",
        "political_opinion",
        "sexual_orientation"
      ],
      "sensitive": true,
      "explicit_consent_required": true,
      "maximum_retention": "review_required"
    },
    "usage": {
      "signals": [
        "analytics_id",
        "device_id",
        "event_name",
        "user_agent",
        "traffic_hash"
      ],
      "sensitive": false,
      "explicit_consent_required": false,
      "maximum_retention": "review_required"
    }
  },
  "provider_signals": {
    "google_analytics": [
      "google-analytics.com",
      "googletagmanager.com"
    ],
    "sentry": [
      "sentry.io"
    ],
    "supabase": [
      "supabase.co"
    ],
    "dropbox": [
      "dropboxapi.com",
      "dropbox.com"
    ],
    "google_drive": [
      "drive.googleapis.com",
      "accounts.google.com"
    ]
  },
  "required_treatment_fields": [
    "id",
    "category",
    "fields",
    "purpose",
    "basis",
    "retention",
    "consent",
    "providers"
  ],
  "material_changes": [
    "purpose",
    "sensitive",
    "new_provider"
  ],
  "documents": [
    "politica-tratamiento.md",
    "aviso-privacidad.md",
    "terminos-condiciones.md",
    "registro-tratamientos.md",
    "canal-derechos.md",
    "retencion.md"
  ]
}


---

## Fuente: legal/plantillas/aviso-privacidad.md.tpl

# Aviso de privacidad y autorización

> Estado: borrador técnico generado; **revisión jurídica requerida**.

## Responsable

- Nombre o razón social: {{CONTROLLER_NAME}}
- Identificación: {{CONTROLLER_IDENTIFIER}}
- Dirección: {{CONTROLLER_ADDRESS}}
- Canal de derechos: {{RIGHTS_EMAIL}}

## Producto

`{{PROJECT}}`

## Tratamientos documentados

{{TREATMENTS_TABLE}}

## Autorización técnica pendiente

La integración que recoja autorización debe presentar una **casilla no premarcada** y un enlace visible a la política de tratamiento antes de registrar la decisión de la persona. Para tratamientos que requieran consentimiento explícito, la implementación debe conservar evidencia verificable de esa decisión.

Este borrador **no acredita que exista consentimiento**, no sustituye la revisión jurídica y no autoriza por sí mismo ningún tratamiento.


---

## Fuente: legal/plantillas/canal-derechos.md.tpl

# Canal para ejercer derechos sobre datos personales

> Estado: borrador técnico generado; **revisión jurídica requerida**.

Producto: `{{PROJECT}}`

## Responsable y canal

- Nombre o razón social: {{CONTROLLER_NAME}}
- Identificación: {{CONTROLLER_IDENTIFIER}}
- Dirección: {{CONTROLLER_ADDRESS}}
- Canal de derechos: {{RIGHTS_EMAIL}}

## Procedimiento pendiente

- Requisitos de la solicitud: [COMPLETAR POR EL DUEÑO] — revisión jurídica requerida.
- Flujo interno de atención: [COMPLETAR POR EL DUEÑO] — revisión jurídica requerida.
- Plazos aplicables: [COMPLETAR POR EL DUEÑO] — deben ser definidos con revisión jurídica; este kit no inventa un plazo legal.

El canal debe contemplar solicitudes de acceso, rectificación/corrección, actualización, portabilidad, supresión/eliminación o revocación del consentimiento cuando corresponda. La identidad, legitimación y representación deben verificarse antes de tramitar solicitudes; los procedimientos y plazos siguen sujetos a revisión jurídica. Este documento describe una frontera técnica y no constituye aprobación jurídica.


---

## Fuente: legal/plantillas/politica-tratamiento.md.tpl

# Política de tratamiento de datos personales

> Estado: documento técnico generado; **no constituye aprobación jurídica**.

## Responsable

- Nombre o razón social: {{CONTROLLER_NAME}}
- Identificación: {{CONTROLLER_IDENTIFIER}}
- Dirección: {{CONTROLLER_ADDRESS}}
- Canal de derechos: {{RIGHTS_EMAIL}}

## Producto

`{{PROJECT}}`

## Tratamientos documentados

{{TREATMENTS_TABLE}}

## Derechos y revisión

Las solicitudes de acceso, rectificación/corrección, actualización, portabilidad, supresión/eliminación o revocación del consentimiento, cuando corresponda, se canalizan mediante el canal de derechos indicado arriba, previa verificación de identidad y legitimación. La portabilidad no implica que exista un servicio automatizado de exportación. Las finalidades, bases, consentimientos, proveedores y retenciones aquí documentadas requieren la revisión jurídica aplicable antes de declararse aprobadas.


---

## Fuente: legal/plantillas/registro-tratamientos.md.tpl

# Registro de tratamientos

> Estado: inventario técnico generado; **revisión jurídica requerida**.

Producto: `{{PROJECT}}`

{{REGISTER_SECTIONS}}


---

## Fuente: legal/plantillas/retencion.md.tpl

# Tabla de retención

> Estado: calendario técnico documentado; **revisión jurídica requerida**.

Producto: `{{PROJECT}}`

| Tratamiento | Categoría | Retención declarada | Máximo común |
| --- | --- | --- | --- |
{{RETENTION_ROWS}}


---

## Fuente: legal/plantillas/terminos-condiciones.md.tpl

# Términos y condiciones

> Estado: borrador técnico generado; **revisión jurídica requerida antes de publicación**.

Producto: `{{PROJECT}}`

## Responsable

- Nombre o razón social: {{CONTROLLER_NAME}}
- Identificación: {{CONTROLLER_IDENTIFIER}}
- Dirección: {{CONTROLLER_ADDRESS}}
- Canal de derechos: {{RIGHTS_EMAIL}}

## Condiciones pendientes de definición

- Condiciones comerciales: [COMPLETAR POR EL DUEÑO] — revisión jurídica requerida.
- Niveles de servicio (SLA), si aplican: [COMPLETAR POR EL DUEÑO] — revisión jurídica requerida.
- Garantías y limitaciones aplicables: [COMPLETAR POR EL DUEÑO] — revisión jurídica requerida.
- Jurisdicción y mecanismo de solución de controversias: [COMPLETAR POR EL DUEÑO] — revisión jurídica requerida.

Este documento no inventa ni presume condiciones del producto. Los hechos comerciales y jurídicos anteriores deben completarse y aprobarse antes de su uso público.


---

