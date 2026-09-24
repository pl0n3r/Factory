# Inventario técnico de datos por producto

Estado: **evidencia técnica para revisión material**. Este documento no es aprobación jurídica, no sustituye una política de tratamiento, no define bases legales y no certifica cumplimiento. Describe únicamente lo observado en los repositorios auditados y deja explícito lo que sigue requiriendo decisión humana.

## Snapshot auditado

- Condor: `02be616b1bb8f33f7da601a0cca33e5c0e4dcc79`
- GrindFlow: `8c59ea017b5cb8f90985cf9aae8e32d59f93c65c`
- BRVTAL: `138b1babac0ff6797ad9e0f3ccb0fbda0f793452`

La revisión es read-only sobre esos SHA. Si cualquiera cambia, este inventario debe considerarse histórico hasta revalidarlo.

## Cómo leer este mapa

- **Dato observado**: existe un campo, flujo o identificador concreto en código/esquema.
- **Finalidad técnica observable**: propósito que puede inferirse directamente del comportamiento del software, sin convertirlo en fundamento jurídico.
- **Tercero/proveedor**: servicio externo nombrado o invocado por el código.
- **Retención explícita**: plazo o expiración codificados. Si no existe plazo visible, se registra como desconocido.
- **Riesgo de expansión**: campo libre, metadata o telemetría capaz de recibir más información de la que su nombre sugiere.

No se incluyen valores reales de producción, datos de titulares, secretos, tokens ni credenciales.

---

## Condor

### Datos observados

**Identidad de usuarios**

Fuente principal: `src/Domain/Identity/Entity/User.php`.

- correo electrónico;
- nombre visible;
- hash de contraseña;
- roles;
- estado activo/inactivo;
- fecha de creación.

Finalidad técnica observable: autenticación, autorización y representación del usuario dentro de la plataforma.

**Clientes comerciales**

Fuente principal: `src/Domain/Commerce/Entity/Customer.php`.

- nombre;
- correo opcional;
- teléfono opcional;
- notas libres opcionales;
- categoría comercial;
- relación con tenant.

El campo `notes` admite texto libre de hasta 5000 caracteres. Técnicamente puede contener información adicional no estructurada; por tanto debe tratarse como una zona de riesgo de expansión y no asumirse que contiene solo datos comerciales mínimos.

**Invitaciones de cuenta**

Fuente: `src/Domain/Identity/Entity/AccountInvitation.php`.

- referencia al usuario invitado;
- tenant cuando aplica;
- tipo de invitación;
- hash del token de invitación;
- usuario creador;
- expiración;
- fechas de consumo/revocación/creación/actualización.

El token se almacena como hash. La invitación tiene expiración técnica, pero no se observó en esta auditoría un plazo general de borrado del registro ya consumido o revocado.

**Preferencias y entregas de notificación**

Fuentes:
- `src/Domain/Notification/Entity/NotificationPreference.php`;
- `src/Domain/Notification/Entity/NotificationDelivery.php`.

Se observan:
- usuario;
- evento;
- canal;
- preferencia habilitada;
- payload JSON de entrega;
- estado;
- número de intentos;
- último error sanitizado;
- fechas de disponibilidad, entrega, creación y actualización.

El `payload` es JSON flexible: debe revisarse por evento antes de asumir minimización, porque su esquema no queda cerrado por la entidad.

**Auditoría**

Fuente: `src/Domain/Audit/Entity/AuditEvent.php`.

- tenant;
- ID del usuario actor, cuando existe;
- acción;
- tipo e ID de entidad;
- contexto JSON;
- fecha.

El contexto es flexible y debe permanecer libre de PII innecesaria. No se observó aquí un plazo general de retención del historial de auditoría.

**Observabilidad y diagnóstico**

Fuentes:
- `src/Domain/Observability/Entity/ErrorIncident.php`;
- `src/Domain/Observability/Entity/DiagnosticShare.php`;
- configuración de `ErrorSanitizer` en `config/services.yaml`.

Los incidentes guardan:
- request ID;
- status HTTP;
- método;
- nombre de ruta;
- clase y mensaje de excepción;
- fingerprint;
- versión y SHA de release;
- traza acotada;
- fecha.

Los enlaces de diagnóstico usan token hash y fecha de expiración/revocación. Existe un sanitizador dedicado en la infraestructura, pero esta auditoría no convierte su mera existencia en garantía de que cualquier mensaje/contexto futuro esté libre de datos personales.

### Terceros y transferencias técnicas observables

El binding actual de correo transaccional es `NullTransactionalEmailGateway`: no entrega correo real y evita registrar el destinatario. El propio adaptador deja previsto que un proveedor real sustituya ese binding en el futuro.

No se identificó en este snapshot un ESP concreto configurado en código. Por tanto el proveedor de correo real, si existe fuera del repositorio, queda **desconocido** para esta evidencia.

### Retenciones/expiraciones explícitas

- invitaciones: tienen `expires_at`, además de consumo/revocación;
- diagnostic shares: tienen expiración y revocación;
- no se observó un calendario general codificado para usuarios, clientes, notas, auditoría, entregas de notificación o incidentes.

### Preguntas materiales pendientes

1. ¿Qué base/autorización real respalda nombre, correo, teléfono y notas de clientes por cada tenant?
2. ¿Está permitido introducir información sensible o no necesaria en `Customer.notes`? Si no, ¿qué controles y política lo prohíben?
3. ¿Cuál es el calendario real de borrado/anominización de clientes, auditoría, notificaciones e incidentes?
4. ¿Qué proveedor enviará correos reales y bajo qué contrato/ubicación cuando se reemplace el gateway nulo?
5. ¿Qué contenido exacto puede aparecer en payloads de notificación, contextos de auditoría y mensajes de error?
6. ¿Cuál es la distribución de responsabilidades entre plataforma y cada tenant frente a los datos de sus clientes?

---

## GrindFlow

### Datos observados

**Identidad y membresías**

Fuentes:
- `app/Models/User.php`;
- `database/migrations/2026_09_18_000100_create_identity_tables.php`.

Se observan:
- nombre;
- correo;
- contraseña hasheada;
- fecha de verificación de correo;
- rol de plataforma;
- remember token;
- membresías y roles por organización;
- timestamps.

Finalidad técnica observable: autenticación, autorización y tenancy.

**Conexiones OAuth con Google Drive y Dropbox**

Fuentes:
- `app/Models/MediaConnection.php`;
- `database/migrations/2026_09_18_150000_create_media_connections_table.php`;
- `app/Services/Media/Connections/GoogleOAuthClient.php`;
- `app/Services/Media/Connections/DropboxOAuthClient.php`;
- `app/Services/Media/Connections/MediaConnectionTokenProvider.php`.

Se observan:
- usuario que autorizó;
- proveedor;
- etiqueta de conexión;
- identificador de cuenta;
- access token cifrado;
- refresh token cifrado;
- expiración del token;
- scopes;
- cursor de sincronización;
- root path;
- timestamps de escaneo;
- errores;
- metadata.

Google Drive solicita scope `drive.readonly`. Dropbox usa OAuth con acceso offline. Los tokens se almacenan cifrados mediante el contexto de organización/proveedor.

Proveedores identificados técnicamente: **Google Drive/Google OAuth** y **Dropbox/Dropbox OAuth**.

**Media vault e ingestión**

Fuente: `database/migrations/2026_09_18_050000_create_media_vault_tables.php`.

Se observan:
- archivos y derivados almacenados;
- nombre original del archivo;
- tipo MIME;
- tamaño;
- SHA256;
- storage disk/key;
- usuario que ingirió;
- source type/source ref;
- metadata;
- estado y timestamps.

Los archivos y sus metadatos pueden contener datos personales por su propio contenido o nombre, aunque el esquema no pueda clasificarlos automáticamente.

**Tráfico y atribución**

Fuentes:
- `app/Services/Traffic/VisitorFingerprint.php`;
- `app/Services/Traffic/TrafficAttributionRecorder.php`;
- `database/migrations/2026_09_19_033000_create_traffic_attribution_tables.php`.

El software:
- obtiene la IP de la petición;
- calcula un HMAC SHA-256 con clave privada, ID del tracked link e IP;
- almacena solo `visitor_hash`, no la IP cruda en las tablas de dedupe;
- registra fecha del último conteo;
- agrega clics por día y tracked link.

La ventana anti-duplicado es de 10 minutos y el registro `tracked_link_dedupes` se poda después de **24 horas**. Los agregados diarios de clics no tienen un plazo de eliminación explícito observado en esta auditoría.

**Tracked links**

Se observan creador, token, etiqueta, URL destino, canal, campaña, estado y métricas agregadas. Las URLs y etiquetas pueden contener identificadores o parámetros de terceros y requieren disciplina de configuración.

**Supabase**

Fuente: `src/lib/supabase/service.ts`.

Existe un cliente server-only con `SUPABASE_SERVICE_ROLE_KEY` que omite RLS para tres casos documentados: subida anónima ya autorizada por token, workers/callbacks y publicación programada.

La existencia de este cliente identifica **Supabase** como un tercero/plataforma de datos en la arquitectura cuando esa capa está desplegada. Región, contrato, residencia y retención no se deducen del código.

### Retenciones/expiraciones explícitas

- visitor fingerprint/dedupe: poda después de 24 horas;
- deduplicación de clics: ventana de 10 minutos;
- OAuth state: configuración con TTL por defecto de 600 segundos;
- direct upload: TTL por defecto de 15 minutos;
- access tokens: guardan expiración y se refrescan;
- no se observó en este snapshot un calendario general de borrado para usuarios, memberships, conexiones OAuth, refresh tokens, media, metadatos o métricas diarias.

### Preguntas materiales pendientes

1. ¿Qué finalidades y bases/autorizaciones reales aplican a usuarios y miembros de organizaciones?
2. ¿Cuándo se eliminan/revocan conexiones, refresh tokens y metadatos tras desconexión o terminación del servicio?
3. ¿Qué política controla nombres de archivo, source refs y metadata para impedir incorporar datos innecesarios?
4. ¿Qué contrato, región, subencargados y retención aplican a Supabase en producción?
5. ¿Qué contratos/condiciones y responsabilidades aplican a Google Drive y Dropbox?
6. ¿Cuál es la justificación material del visitor fingerprint derivado de IP y cómo se informa al visitante?
7. ¿Cuánto tiempo se conservan métricas diarias agregadas y tracked links?
8. ¿Los medios pueden contener datos de terceros, modelos, artistas u otras personas? ¿Qué proceso cubre autorización, retiro y eliminación?

---

## BRVTAL

### Datos observados

**Administradores**

Fuentes:
- `database/schema.sql`;
- `config/admin_auth.php`.

Se observan:
- correo;
- nombre;
- hash de contraseña;
- estado activo;
- última fecha de login;
- timestamps.

La sesión administrativa almacena IDs y timestamps de autenticación/actividad y usa cookie HttpOnly/SameSite Strict.

**TOTP y recuperación**

Fuentes:
- `database/migration_totp_foundation.sql`;
- `config/totp_auth.php`;
- `config/totp_rate_limit.php`.

Se observan:
- secreto TOTP cifrado;
- estado y fecha de confirmación;
- códigos de recuperación hasheados;
- fecha de uso de código;
- email pendiente de TOTP dentro de la sesión temporal;
- rate-limit derivado de hash de IP + admin ID + scope.

El pending TOTP expira técnicamente a los 600 segundos.

**Contacto público**

Fuentes:
- `api/contact.php`;
- `config/public_contact.php`.

El formulario recibe:
- nombre;
- correo;
- asunto;
- mensaje.

El servidor construye un correo con esos campos y lo entrega mediante `mail()` al buzón configurado. No se observó persistencia de esos cuatro campos en la base de datos de BRVTAL dentro de este flujo; la retención posterior depende del sistema/buzón de correo y no está definida por este código.

Para rate limit:
- resuelve IP del cliente;
- almacena una clave SHA-256 derivada de la IP, no la IP cruda, junto con timestamps;
- ventana por defecto: 900 segundos;
- límite por defecto: 5 intentos;
- los buckets vencidos se eliminan al procesar nuevas solicitudes.

El CAPTCHA propio tiene expiración de 600 segundos.

**Analítica pública**

Fuentes:
- `config/public_analytics.php`;
- `js/public-analytics.js`;
- `docs/ANALYTICS-MEASUREMENT.md`.

BRVTAL carga **Google Tag Manager** automáticamente cuando hay un contenedor válido configurado.

Bootstrap observado:
- `analytics_storage: granted`;
- `ad_storage: denied`;
- `ad_user_data: denied`;
- `ad_personalization: denied`;
- no se exige diálogo de aceptación de Analytics en el runtime actual.

El contrato de medición declara eventos estructurados de página, secciones, scroll, navegación y outbound clicks. El runtime documenta que no pretende recolectar valores de formularios, correos, nombres, IPs, query strings ni datos de sesión/admin.

GTM puede cargar destinos adicionales configurados fuera del repositorio; el documento de BRVTAL menciona GA4 como destino previsto/opcional. La configuración real del contenedor, retención de GA4 y destinos adicionales no son observables desde este repo.

**Contenido editorial**

El esquema incluye artistas, nombres, biografías, URLs sociales/web, eventos, media y otros contenidos públicos. Según el contenido real, algunos registros pueden describir personas identificables; el código por sí solo no determina la fuente, autorización o naturaleza jurídica de cada contenido.

### Retenciones/expiraciones explícitas

- sesión admin: timeout idle de 7 días;
- sesión admin: timeout absoluto/cookie de 30 días;
- pending TOTP: 10 minutos;
- rate-limit TOTP: ventana de 15 minutos y bloqueo de 15 minutos;
- CAPTCHA de contacto: 10 minutos;
- rate-limit de contacto: ventana de 15 minutos;
- retención del correo de contacto en el buzón: desconocida;
- retención de GTM/GA4: desconocida desde el repositorio;
- retención de cuentas admin, secretos TOTP, actividad editorial y contenido público: sin calendario general observado aquí.

### Terceros y dependencias relevantes

- Google Tag Manager; GA4 puede estar configurado dentro del contenedor.
- El transporte de contacto usa el MTA/proveedor de correo del hosting, no identificado por el código.
- `package.json` declara `@playwright/test ^1.55.0`, pero no existe lockfile npm.
- CI usa `npm install`, por lo que la resolución npm no está fijada de forma reproducible.
- `discadmin/qrcode.min.js` está vendorizado y acompañado por `discadmin/qrcode.LICENSE` MIT.

### Preguntas materiales pendientes

1. ¿Qué fundamento y mecanismo de transparencia se adopta para GTM/GA4 con `analytics_storage` concedido por defecto?
2. ¿Qué tags/destinos reales existen dentro del contenedor GTM de producción y qué datos reciben?
3. ¿Cuál es la retención del buzón que recibe formularios de contacto y quién tiene acceso?
4. ¿Quién opera el MTA/proveedor de correo y dónde procesa los mensajes?
5. ¿Qué calendario aplica a cuentas admin, TOTP, recovery codes, logs y actividad?
6. ¿Qué política cubre datos de artistas/colaboradores/personas que aparecen en contenido editorial?
7. ¿Debe incorporarse un `package-lock.json` o un mecanismo reproducible equivalente antes de cerrar el inventario de licencias?
8. ¿Qué proceso responde solicitudes de acceso, corrección, eliminación o retiro respecto de contacto y contenido?

---

## Matriz de terceros identificados

| Producto | Tercero/capa | Evidencia técnica | Dato/flujo potencial |
| --- | --- | --- | --- |
| Condor | Proveedor de correo real | No identificado; gateway actual es nulo | Destinatario y contenido de correo futuro |
| GrindFlow | Google Drive / Google OAuth | OAuth + scope drive.readonly | Identificador de cuenta, tokens, archivos/metadata |
| GrindFlow | Dropbox / Dropbox OAuth | OAuth offline | Identificador de cuenta, tokens, archivos/metadata |
| GrindFlow | Supabase | Service role server-only | Datos de backend según flujos desplegados |
| BRVTAL | Google Tag Manager | Script público GTM | Eventos/medición pública |
| BRVTAL | GA4 u otros tags | Configurable dentro de GTM | Desconocido hasta auditar el contenedor |
| BRVTAL | MTA/proveedor de correo | PHP `mail()` | Nombre, email, asunto, mensaje |

La tabla identifica integraciones; no decide si una entidad actúa como responsable, encargado, subencargado u otra figura.

## Retenciones técnicas explícitas resumidas

| Producto | Registro/flujo | Expiración o ventana observada |
| --- | --- | --- |
| Condor | Invitación | `expires_at` por invitación |
| Condor | Diagnostic share | `expires_at` + revocación |
| GrindFlow | Traffic dedupe hash | poda > 24 h |
| GrindFlow | Anti-dedupe de clic | 10 min |
| GrindFlow | OAuth state | 600 s por defecto |
| GrindFlow | Direct upload | 15 min por defecto |
| BRVTAL | Admin idle session | 7 días |
| BRVTAL | Admin absolute session/cookie | 30 días |
| BRVTAL | TOTP pending | 600 s |
| BRVTAL | TOTP rate limit | 15 min |
| BRVTAL | Contact CAPTCHA | 600 s |
| BRVTAL | Contact rate limit | 15 min |

Todo lo no listado debe considerarse **sin plazo técnico verificado en esta auditoría**, no como retención infinita aprobada.

## Preguntas materiales pendientes transversales

1. Identificar responsable/encargado y finalidad real por tratamiento y producto.
2. Confirmar política de privacidad/términos vigentes y el canal operativo de derechos.
3. Definir calendario de retención, eliminación y respaldo para cada categoría.
4. Documentar proveedores, contratos, regiones, subencargados y transferencias aplicables.
5. Revisar campos libres (`notes`, payloads, metadata, contextos, logs) y aplicar minimización.
6. Definir tratamiento de medios/contenido que pueda incluir terceros identificables.
7. Confirmar mecanismos de transparencia/consentimiento o la base aplicable para medición web.
8. Validar inventarios de licencias contra lockfiles reales y resolver BRVTAL sin inventar `--stdlib-only`.

## Frontera de cierre de #12

Este documento reduce la incertidumbre técnica, pero **no es aprobación jurídica** y no cierra #12.

Para cierre material siguen faltando, como mínimo, referencias vigentes por tratamiento a:
- política de privacidad;
- términos;
- registro de tratamientos;
- canal de derechos;
- calendario de retención;
- revisión de proveedores;
- revisión jurídica humana con fecha.

La evidencia final no debe contener PII real ni secretos.