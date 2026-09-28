# Lifecycle de conocimiento aprendido

Factory trata guardrails, reglas y heurísticas aprendidas como conocimiento **versionado y revocable**, no como autoridad permanente.

## Estados

`candidate → active → needs_review → deprecated → archived`

- **candidate**: evidencia suficiente para proponer, todavía no habilita autonomía.
- **active**: regla revalidada dentro de su ventana de revisión.
- **needs_review**: la validación envejeció; la regla deja de aumentar autonomía hasta revalidarse.
- **deprecated**: conocimiento sustituido o retirado de uso activo.
- **archived**: historial conservado para auditoría; nunca implica borrado.

## Metadata obligatoria

Todo conocimiento promovible declara:

- provenance verificable y scope `project/domain`;
- `created_at`, `last_validated_at` y `last_useful_at`;
- `content_fingerprint` SHA-256;
- confidence y evidence class;
- política explícita `review_after_days / expires_after_days`;
- history append-only de transiciones.

Una regla `active` cuya revisión vence se interpreta como `needs_review`. Mientras esté vencida, sea `candidate`, `deprecated` o `archived`, **no puede aumentar autonomía**.

## Revalidación

Revalidar exige evidencia nueva, actualiza provenance/fecha/confidence/evidence class y añade una transición trazable a `active`. Revalidar no revive conocimiento ya `deprecated` o `archived`; ese caso requiere una nueva propuesta.

## Pruning

Pruning puede detectar conocimiento:

- duplicado por `content_fingerprint`;
- sin uso reciente;
- envejecido o pendiente de revisión.

El resultado es siempre una **propuesta** `review-consolidation` o `review-retirement`. Nunca contiene una operación delete y siempre declara `history_preserved=true`.

Este lifecycle no modifica Factory Constitution ni las puertas humanas. Solo reduce autonomía cuando la evidencia envejece y conserva trazabilidad cuando una regla se revalida o retira.
