# Quality Contract en Project DNA

#344 conecta Project DNA con Quality Engineering sin duplicar el contrato.

Project DNA conserva su versión base v1 y usa el namespace extensible:

`extensions.quality_contract`

La extensión contiene únicamente:

- `version`;
- `source_ref`;
- `fingerprint` SHA-256 del Quality Contract canónico validado por #343.

## Reglas

- El Quality Contract completo **no se copia** dentro de Project DNA.
- Project DNA **no infiere** quality gates desde stack, rutas, frameworks o capabilities.
- Si no se aporta explícitamente un Quality Contract, `discover_project_dna()` conserva `extensions={}`.
- `attach_quality_contract()` valida primero Project DNA y Quality Contract, luego recalcula el fingerprint de Project DNA.
- `validate_project_dna()` valida el shape cerrado de `extensions.quality_contract` cuando existe.
- El namespace general `extensions` permanece abierto para futuras capacidades.

Esto deja a #345 la compilación Risk/DoD. Project DNA solo declara qué contrato gobierna el proyecto; no decide sus gates.
