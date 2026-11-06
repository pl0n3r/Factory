# Verificación Factory · lote 05/18 · Issue #2021

**Fuente:** contrato de [Factory #2021](https://github.com/pl0n3r/Factory/issues/2021), conjunto fijo de 70 unidades. **Base examinada:** `main@67aeb1e4381664860de0cbca2915c0b2a1e2d276` (5-nov-2026). No modifica la matriz; su consolidación pertenece a otra hoja.

## Alcance y criterios de verdad

- **A** = prueba sintética ejecutable contra el código real citado, mediante `tests/test_verificacion_factory_05.py`; es evidencia de contrato local, no prueba exacta de producción, release ni adopción.
- **B** = exige evidencia externa adicional: los snapshots interrepositorios y la ejecución de poda real quedan sin certificar. No se transforma `NO_VERIFICABLE` en `CUBIERTO`.
- Todas las 70 unidades conservan **estado en la matriz: `NO_VERIFICABLE`** hasta que la hoja de consolidación reconcilie test + PR fusionado + evidencia con la semántica exacta.
- No se crea código nuevo ni se altera `docs/matriz-cobertura.md`, `Factory@v1`, producción o datos reales.
- Los testigos de esta tabla son nombres de métodos del fichero de pruebas de esta misma hoja; su resultado no se presupone antes de `CI/Validar` y `Tests de scripts` sobre el HEAD.

## Resultado por unidad (70/70)

| ID de matriz | Contrato / texto contrastado | Fuente causal | Testigo de regresión | Límite |
| --- | --- | --- | --- | --- |
| `docs/fitness-engine.md:L30-U1` | Fitness informa el bloqueo | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L37-U1` | `improved`: mejora según su dirección; | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L38-U1` | `equal`: no cambia; | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L39-U1` | `regressed`: empeora; | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L40-U1` | `unknown`: falta baseline o candidate. | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L50-U1` | cualquier regresión protegida → `blocked`; | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L51-U1` | cualquier dato faltante → `inconclusive`; | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L52-U1` | regresiones no protegidas mezcladas con mejoras → `mixed`; | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L53-U1` | una o más mejoras sin regresiones/faltantes → `improved`; | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L54-U1` | todo igual → `equal`. | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L56-U1` | `can_claim_improvement=true` solo para `improved`. | `evolution/fitness.py` | `test_fitness_states_and_claims` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L62-U1` | por vector, se rechazan números no finitos y el resultado incluye un fingerprint | `evolution/fitness.py` | `test_fitness_source_and_guards` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L69-U1` | Solo compara evidencia entregada explícitamente. | `evolution/fitness.py` | `test_fitness_source_and_guards` | A: comportamiento offline comprobable; no acredita producción |
| `docs/fitness-engine.md:L75-U1` | `reversibility` y `authority` son siempre protegidas. | `evolution/fitness.py` | `test_fitness_source_and_guards` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L10-U1` | Solo normaliza | `evolution/growth.py; evolution/pruning.py` | `test_growth_reuse_and_candidate` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L20-U1` | capacidad requerida; | `evolution/growth.py; evolution/pruning.py` | `test_growth_reuse_and_candidate` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L21-U1` | valor esperado; | `evolution/growth.py; evolution/pruning.py` | `test_growth_reuse_and_candidate` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L22-U1` | fingerprint del gap; | `evolution/growth.py; evolution/pruning.py` | `test_growth_reuse_and_candidate` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L23-U1` | evidencia origen; | `evolution/growth.py; evolution/pruning.py` | `test_growth_reuse_and_candidate` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L24-U1` | rollback reversible. | `evolution/growth.py; evolution/pruning.py` | `test_growth_reuse_and_candidate` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L30-U1` | `evaluate_pruning()` exige evidencia medible: | `evolution/growth.py; evolution/pruning.py` | `test_pruning_thresholds_and_safety` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L33-U1` | edad >= 90 días; | `evolution/growth.py; evolution/pruning.py` | `test_pruning_thresholds_and_safety` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L34-U1` | valor <= 0.25; | `evolution/growth.py; evolution/pruning.py` | `test_pruning_thresholds_and_safety` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L35-U1` | al menos 2 referencias de evidencia. | `evolution/growth.py; evolution/pruning.py` | `test_pruning_thresholds_and_safety` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L37-U1` | Solo si las cuatro condiciones se cumplen se marca `eligible=true`. | `evolution/growth.py; evolution/pruning.py` | `test_pruning_thresholds_and_safety` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L43-U1` | parent fingerprint; | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L44-U1` | fingerprint de la evaluación; | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L46-U1` | `history_preserved=true`. | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L48-U1` | La ejecución real debe atravesar Evolution Engine y Factory Lab. | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | B: ejecución Evolution Engine/Factory Lab externa al fixture |
| `docs/growth-pruning.md:L52-U1` | Nunca pueden podarse las dimensiones constitucionales: | `evolution/growth.py; evolution/pruning.py` | `test_pruning_thresholds_and_safety` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L60-U1` | Pruning falla cerrado antes de evaluar uso/edad/valor para cualquiera de ellas. | `evolution/growth.py; evolution/pruning.py` | `test_pruning_thresholds_and_safety` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L64-U1` | borrar historia; | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L65-U1` | retirar Constitution o controles protegidos; | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L66-U1` | mutar stable; | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | A: comportamiento offline comprobable; no acredita producción |
| `docs/growth-pruning.md:L67-U1` | promover candidatos automáticamente. | `evolution/growth.py; evolution/pruning.py` | `test_pruning_lineage_and_no_direct_mutation` | A: comportamiento offline comprobable; no acredita producción |
| `docs/inventario-tecnico-datos-productos.md:B01` | Inventario anclado a SHA por producto; cambios de fuente invalidan cualquier inferencia de estado ac | `docs/inventario-tecnico-datos-productos.md` | `test_inventory_is_historical_not_legal_approval` | B: snapshots ajenos históricos; revalidar SHA externo |
| `docs/inventario-tecnico-datos-productos.md:B02` | Clasificar proveedores observados y no convertir un gateway nulo o tags externos en proveedor/contra | `docs/inventario-tecnico-datos-productos.md` | `test_inventory_is_historical_not_legal_approval` | B: snapshots ajenos históricos; revalidar SHA externo |
| `docs/inventario-tecnico-datos-productos.md:B03` | Distinguir TTL técnicos observables (invitation/dedupe/CAPTCHA) de calendarios generales de retenció | `docs/inventario-tecnico-datos-productos.md` | `test_inventory_is_historical_not_legal_approval` | B: snapshots ajenos históricos; revalidar SHA externo |
| `docs/issue-contract-preflight.md:L3-U1` | Antes de publicar `/tomar`, un agente puede validar localmente que el body del Issue cumple **los do | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/issue-contract-preflight.md:L19-U1` | valida primero las secciones y criterios con `aceptacion_kit.parse_contract`; | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/issue-contract-preflight.md:L20-U1` | fija el fingerprint con `contract_fingerprint`; | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/issue-contract-preflight.md:L21-U1` | valida el marker con `orquestador_kit.parse_task_marker`; | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/issue-contract-preflight.md:L22-U1` | fija su identidad con `task_marker_fingerprint`. | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/issue-contract-preflight.md:L24-U1` | Un marker ausente o inválido bloquea el preflight. | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/issue-contract-preflight.md:L28-U1` | Este comando **no reserva trabajo** y no autoriza ningún cambio. | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/issue-contract-preflight.md:L28-U2` | Solo valida texto local reutilizando los parsers canónicos de Factory. | `scripts/issue_contract_preflight.py` | `test_issue_preflight_accepts_and_rejects_offline` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L9-U1` | **candidate**: evidencia suficiente para proponer, todavía no habilita autonomía. | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L10-U1` | **active**: regla revalidada dentro de su ventana de revisión. | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L11-U1` | **needs_review**: la validación envejeció | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L11-U2` | la regla deja de aumentar autonomía hasta revalidarse. | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L12-U1` | **deprecated**: conocimiento sustituido o retirado de uso activo. | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L13-U1` | **archived**: historial conservado para auditoría | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L13-U2` | nunca implica borrado. | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L19-U1` | provenance verificable y scope `project/domain`; | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L20-U1` | `created_at`, `last_validated_at` y `last_useful_at`; | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L21-U1` | `content_fingerprint` SHA-256; | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L22-U1` | confidence y evidence class; | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L23-U1` | política explícita `review_after_days / expires_after_days`; | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L24-U1` | history append-only de transiciones. | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L26-U1` | Mientras esté vencida, sea `candidate`, `deprecated` o `archived`, **no puede aumentar autonomía**. | `evolution/knowledge_lifecycle.py` | `test_knowledge_states_autonomy_and_history` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L30-U1` | Revalidar exige al menos una **identidad de evidencia nueva**. | `evolution/knowledge_lifecycle.py` | `test_knowledge_revalidation_rejects_replay` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L30-U2` | La identidad puede ser la fuente histórica simple o una fuente versionada como `source@sha256:<diges | `evolution/knowledge_lifecycle.py` | `test_knowledge_revalidation_rejects_replay` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L30-U3` | Repetir la misma fuente base es válido solo cuando cambia esa identidad verificable | `evolution/knowledge_lifecycle.py` | `test_knowledge_revalidation_rejects_replay` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L30-U4` | reenviar exactamente la misma identidad se rechaza y no refresca timestamps, estado ni autonomía. | `evolution/knowledge_lifecycle.py` | `test_knowledge_revalidation_rejects_replay` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L30-U5` | La revalidación actualiza provenance/fecha/confidence/evidence class y añade una transición trazable | `evolution/knowledge_lifecycle.py` | `test_knowledge_revalidation_rejects_replay` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L30-U6` | Revalidar no revive conocimiento ya `deprecated` o `archived` | `evolution/knowledge_lifecycle.py` | `test_knowledge_revalidation_rejects_replay` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L30-U7` | ese caso requiere una nueva propuesta. | `evolution/knowledge_lifecycle.py` | `test_knowledge_revalidation_rejects_replay` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L36-U1` | duplicado por `content_fingerprint`; | `evolution/knowledge_lifecycle.py` | `test_knowledge_pruning_is_review_only` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L37-U1` | sin uso reciente; | `evolution/knowledge_lifecycle.py` | `test_knowledge_pruning_is_review_only` | A: comportamiento offline comprobable; no acredita producción |
| `docs/knowledge-lifecycle.md:L38-U1` | envejecido o pendiente de revisión. | `evolution/knowledge_lifecycle.py` | `test_knowledge_pruning_is_review_only` | A: comportamiento offline comprobable; no acredita producción |

## Brechas de autoridad y consolidación

1. **Inventario B01–B03:** `docs/inventario-tecnico-datos-productos.md` consigna los SHAs observados de Condor, GrindFlow y BRVTAL y distingue observación técnica de aprobación. Es evidencia histórica, no lectura autenticada actual de cada repositorio; una reconciliación cross-repo exact-SHA es condición de verificación productiva.
2. **Pruning L48-U1:** los fixtures verifican la propuesta reversible `prune-candidate`, no una ejecución a través de Evolution Engine/Factory Lab. Esa ejecución queda fuera de este lote y nunca autoriza borrado, modificación de stable o promoción automática.
3. **Fitness/Growth/Lifecycle/Preflight:** los tests locales ejecutan funciones canónicas con casos positivos, negativos y fallos cerrados. No validan despliegue, aceptación humana ni flujos externos.
4. **Siguiente consolidación:** comparar los 70 IDs y sus evidencias con `docs/matriz-cobertura.md` en un claim autorizado de la hoja de consolidación, después del PR fusionado. Cualquier fila sin predicado completo conserva `NO_VERIFICABLE`, sin declaración de cobertura integral.

## Reproducción

```bash
python3 -m unittest discover -s tests -p 'test_verificacion_factory_05.py' -v
```
