Última actualización automática: 2026-10-19T08:31:57Z | SHA de origen: e099ba4d0cc76373dd7a96adaea10cd7dd15b75b

# Carpeta para revisión jurídica — Factory

Estado: documented_not_legally_approved. Esta documentación NO está aprobada jurídicamente.

Versión del repositorio: 1.0.37. SHA del checkout origen: e099ba4d0cc76373dd7a96adaea10cd7dd15b75b. Fecha UTC: 2026-10-19T08:31:57Z.

Entregue todos los archivos de esta carpeta al abogado, o el archivo paquete-completo.md como documento único. Las plantillas .tpl conservan variables sin rellenar y NO deben publicarse como documentos jurídicos definitivos.

## Documentos y revisión requerida

| Documento fuente copiado | Verificación del abogado |
| --- | --- |
| docs/cumplimiento-datos-licencias.md | Cumplimiento de privacidad y licencias |
| legal/reglas-datos.yml | Reglas de detección de categorías de datos y señales de proveedores |
| legal/plantillas/aviso-privacidad.md.tpl | Aviso, consentimiento y autorización |
| legal/plantillas/canal-derechos.md.tpl | Canal de derechos, trámites y plazos |
| legal/plantillas/politica-tratamiento.md.tpl | Política de tratamiento, finalidades y bases |
| legal/plantillas/registro-tratamientos.md.tpl | Inventario de tratamientos reales |
| legal/plantillas/retencion.md.tpl | Retención y eliminación |
| legal/plantillas/terminos-condiciones.md.tpl | Términos, responsabilidad y jurisdicción |

## Hechos del responsable por confirmar (nunca inventar)

- [ ] Nombre o razón social del responsable.
- [ ] Identificación o NIT aplicable.
- [ ] Dirección física y jurisdicción efectiva.
- [ ] Contacto/canal para ejercer derechos.
- [ ] Tratamientos, finalidades y bases efectivas por producto.
- [ ] Autorizaciones, excepciones y evidencia real.
- [ ] Retenciones y mecanismos de eliminación.
- [ ] Contratos de encargados/subprocesadores y transferencias.
- [ ] Condiciones comerciales, licencias y responsabilidades.
- [ ] Aprobación jurídica previa a cualquier live.

## Servicios observados en la configuración técnica

- GitHub / GitHub Actions: repositorios y automatizaciones.
- SonarCloud: controles de calidad y seguridad de código.
- CodeRabbit: análisis automatizado de pull requests.

Estos servicios técnicos NO prueban transferencia de datos personales de clientes ni son un inventario validado de encargados. El abogado debe comprobar el uso real y las relaciones jurídicas. Las señales de Google Analytics, Sentry, Supabase, Dropbox y Google Drive en legal/reglas-datos.yml sirven para detección y NO significan que estos servicios estén activos.

## Límites

Este paquete conserva bytes de las fuentes; no crea hechos legales, consentimientos ni plazos. El SHA de origen identifica el checkout desde el que se exportó el paquete y puede diferir del SHA de main después de un squash merge sin que exista desfase de documentos.
