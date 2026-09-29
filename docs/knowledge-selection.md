# Knowledge Selection v1

#321 adapta Knowledge Item Contract v1 al Context Compiler existente; no crea buscador, store ni motor paralelo.

La misión declara scope exacto project+domain, tags, categorías decision|lesson|constraint|evidence, require_current, max_items (≤12) y now_at. Cada item se valida con knowledge.contract y su freshness proviene exclusivamente de knowledge_item_status().

La selección filtra scope, categoría y tags; rechaza sensitivity distinta de normal; solo proyecta items current. Con require_current=true, si no queda selección compatible/current falla cerrado. No existe score mágico: el orden es determinista por categoría + item_id.

context_items contiene exactamente category, source, text y tags, compatibles con Context Compiler. Provenance, authority_class y estado permanecen en bindings de trazabilidad con authority=unchanged. El adapter no ejecuta Context Compiler.

Boundary: #320 cubre postmortem, #321 selección, #322 E2E lifecycle/context/pruning/guardrails. No crea un Knowledge Engine. Sin embeddings/vector DB, búsqueda externa, scheduler, polling, store documental, Knowledge Engine paralelo ni mutaciones de Knowledge Items.
