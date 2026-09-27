# Factory Queue v1

Factory mantiene una sola cola de trabajo para productos, ventures e instituciones. Este documento describe únicamente el contrato de origen introducido por Factory #269/#270. Readiness, ranking, ejecución y feedback se integran en los slices posteriores.

## WorkItem v1

Todo origen produce el mismo objeto, sin importar si el trabajo fue pedido por una persona (`directed`) o materializado por un sistema (`automatic`).

Campos requeridos:

| Campo | Contrato |
| --- | --- |
| `work_id` | Identificador del trabajo observado. |
| `origin_mode` | `directed` o `automatic`. |
| `origin_system` | Productor canónico (`human`, `controlbot`, `aegis`, `momentum`, `capital`, `factory`, `runner`, `autofactory`, `venture`, `product`). |
| `group_id` | Scope superior de negocio. |
| `work_type` | Tipo de trabajo tipado, no limitado a software. |
| `requested_capabilities[]` | Capacidades requeridas, sin nombres de modelos. |
| `required_roles[]` | Roles profesionales necesarios. |
| `authority_level` | Autoridad solicitada/declarada; #270 solo valida forma, no concede permisos. |
| `producer_ref` / `requested_by` | Productor o solicitante; ambos son alias y, si coexisten, deben coincidir. |
| `priority_class` | `critical`, `high` o `medium`. |
| `depends_on[]` | Dependencias declaradas. |
| `claims[]` | Recursos reclamados. |
| `policy_ref` | Política/Constitución aplicable. |
| `evidence_refs[]` | Evidencia atribuible disponible. |
| `idempotency_key` | Clave declarada por el productor para deduplicación estable. |

Campos opcionales: `venture_id`, `project_id`, `repository_ref`, `severity`, `budget_ref`, `approval_ref` y `observed_at`. `repository_ref` es opcional porque contenido, soporte, finanzas, compliance y otros trabajos no-code no necesitan inventar un repositorio.

## Fronteras del contrato

`WorkItem` expresa intención y scope. No contiene `provider`, `model` ni `executor`; el AI Gateway/Model Router decide eso posteriormente bajo política. Tampoco concede budget, approval ni autoridad por el mero hecho de declarar referencias: esos gates pertenecen a readiness.

El validador falla cerrado ante campos desconocidos, listas fuera de límites, identificadores inválidos, referencias sobredimensionadas y valores con formas comunes de secreto. La salida normaliza colecciones semánticamente tipo set para que orden y duplicados no cambien la identidad del trabajo.

## Idempotencia y fingerprints

- `canonical_payload()` serializa el WorkItem validado de forma determinista.
- `work_fingerprint()` identifica el contenido completo del WorkItem.
- `idempotency_scope()` combina `group_id`, `venture_id`, `project_id`, `work_type` e `idempotency_key`.

El scope de idempotencia excluye deliberadamente `origin_system` y `work_id`: dos instituciones pueden observar el mismo trabajo sin crear dos unidades ejecutables. Cambiar de venture, proyecto o tipo de trabajo genera un scope distinto y evita colisiones entre dominios.

## Tipos de trabajo soportados

`engineering`, `security`, `infrastructure`, `operations`, `data_analytics`, `product`, `content`, `marketing_growth`, `sales_support`, `finance_analysis`, `compliance_review` y `knowledge_documentation`.

## Fuera de este slice

Factory #271 integrará WorkItem con readiness y Dispatcher V2. #272 añadirá evidencia/feedback de ejecución y #273 cubrirá el escenario E2E multi-origen/multi-institución. Este módulo no consulta servicios, no persiste la cola y no ejecuta agentes.

## Feedback atribuible de ejecución

Factory Queue v1 cierra el ciclo operativo con un feedback terminal que conserva provenance hacia el WorkItem canónico. El flujo es:

`WorkItem → readiness/dispatch → ejecución → evidence/feedback`

El feedback no es una segunda cola ni un mecanismo de prioridad. Es evidencia posterior a la ejecución y **no concede autoridad**, presupuesto, aprobación, ranking ni permiso adicional.

Campos requeridos del contrato de feedback:

- `work_id`: identidad del WorkItem observado;
- `work_fingerprint`: fingerprint canónico recomputado desde el WorkItem;
- `idempotency_scope`: scope estable usado para deduplicación cross-origin;
- `executor_ref`: ejecutor concreto que produjo el outcome;
- `producer_ref`: productor original del WorkItem, que debe coincidir;
- `status`: estado terminal `success|failed|rejected|cancelled`;
- `evidence_refs[]`: referencias de evidencia no vacías y sin duplicados;
- `observed_at`: timestamp con zona horaria y freshness válida.

La validación falla cerrada si provenance, fingerprint, scope, productor, evidencia, estado o freshness no corresponden al WorkItem. La identidad del feedback se deriva del payload normalizado, por lo que evidence refs equivalentes en distinto orden producen el mismo identificador y no crean duplicación lógica.

### Handoff a #273

El escenario E2E de #273 debe construir un WorkItem válido, pasarlo por readiness/Dispatcher V2, simular una ejecución terminal y producir feedback mediante `validate_execution_feedback()`. La evidencia E2E debe demostrar que el resultado conserva `work_fingerprint` e `idempotency_scope`, que entradas stale/inconsistentes fallan cerrado y que ninguna etapa introduce una jerarquía de despacho paralela.

## Escenario E2E multi-origen y multi-institución

Factory Queue v1 queda validada de extremo a extremo con el siguiente flujo canónico:

`WorkItem → readiness → Dispatcher V2 → ejecución terminal → evidence/feedback`

El escenario de #273 prueba dos observaciones equivalentes del mismo trabajo provenientes de instituciones distintas. Ambas comparten `idempotency_scope`, por lo que no se materializan como dos unidades ejecutables. La selección continúa usando exclusivamente readiness y Dispatcher V2 existentes.

Tras la selección, el outcome terminal se transforma en feedback atribuible que conserva `work_fingerprint`, `idempotency_scope`, productor, ejecutor, evidencia y freshness. Provenance inconsistente, evidencia ausente o feedback stale fallan cerrado.

Este slice constituye el **cierre funcional de Factory Queue v1** del épico #269. No añade una cola nueva, un ranking alternativo ni autoridad adicional; únicamente demuestra la composición coherente de los contratos entregados por #270, #271 y #272.

