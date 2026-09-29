## Why

`entity-sensitivity-classification` lets a Tenant Admin mark an entity type `pattern` or
`local_only`, but that classification is currently inert — nothing reads it. LLM pre-labeling
(`extract_and_ground_document`) still sends the tenant's full, real document text to the external
LLM provider on every call, regardless of what any entity type is classified as. For a tenant
whose documents carry information like a foster-care client's name, date of birth, or home
address, marking `child_name` as `local_only` today changes nothing about what actually reaches
the LLM provider. This change is what makes the classification take effect: original document in,
a safe copy generated locally, only the safe copy sent to the external LLM, its output combined
with what was found locally, and the correct (real-text) annotations saved — exactly as today,
from the reviewer's point of view.

## What Changes

- Before any call to the external LLM provider, the system detects every span of every `pattern`-
  and `local_only`-sensitivity entity type directly against the real document text:
  - `pattern` types via their configured `validation_rule` regex (no model, no network call).
  - `local_only` types via the tenant's own already-hosted extraction model
    (`POST /internal/v1/infer` on `model_serving`), mapped to entity types through each type's
    existing `base_label_mapping`.
- A masked copy of the document text is built from those detections — each found span replaced
  with a type-and-index placeholder (e.g. `⟦PERSON_1⟧`) — along with a mapping from offsets in the
  copy back to offsets in the original text.
- Only the masked copy is sent to the external LLM provider. The prompt's entity-type list sent
  externally includes `open`-sensitivity types only; `pattern` and `local_only` types are never
  named or extracted by the external call.
- The LLM's returned quotes are grounded against the masked copy (not the original), then
  translated back to the original document's offsets before being combined with the locally
  detected spans and stored — unchanged storage step, unchanged reviewer experience.
- **Fail closed, not open**: if local detection cannot complete for a document (the local model
  is unreachable, a regex fails to compile), the system does not fall back to sending the
  original text — the job fails, distinguishably from an external-provider failure.
- **BREAKING (spec-level)**: triggering LLM pre-labeling for a tenant that has an active
  `local_only` entity type with no `base_label_mapping` configured now returns 422 — there is no
  local mechanism to detect that type, so the system refuses rather than silently running
  pre-labeling with an unprotected sensitive type.
- `{tenant_schema}.suggested_spans.source` gains two new values, `pattern` and `local_model`,
  alongside the existing `keyword` and `llm`.
- The entity-configuration cache key (`entity_config_version`) now includes each entity type's
  `sensitivity`, so reclassifying a type invalidates any pre-existing cached LLM result for that
  tenant.

## Capabilities

### Modified Capabilities

- `llm-prelabeling`: **Extraction Scope**, **Grounding and Verification**, **Suggested Span
  Storage and Source Tracking**, and **Result Caching** change as described above. Four
  requirements are added: **Safe-Copy Generation**, **Local-Only Type Coverage Requirement**,
  **Fail-Closed on Local Detection Failure**, and **Placeholder Stability Within a Document**.

### New Capabilities

(none)

## Impact

- **Backend**: new `src/annotation_service/services/pii_masking.py` — pattern detection (pure,
  regex over `validation_rule`), a `LocalModelClient` protocol calling `model_serving`'s existing
  `/internal/v1/infer` endpoint (mirroring the `LLMClient`/`StubLLMClient` shape already
  established in `llm_client.py`), placeholder substitution, and offset-mapping/translation.
  `worker.py::extract_and_ground_document` is the single call site modified: it builds the masked
  copy before calling `client.complete_json`, grounds the external result against the masked copy,
  translates offsets back, and merges with the local detections before `replace_suggested_spans`
  writes them — same as today. `llm_prelabel.py::build_entity_type_block` /
  `build_user_payload` take a pre-filtered (`open`-only) entity-type list rather than filtering
  internally. `src/shared/entity_config_version.py`'s `CONFIG_FIELDS` gains `sensitivity`. The
  single-document trigger endpoint and `seed_bootstrap.py`'s batch trigger both gain the
  local_only-coverage check (422 `LOCAL_ONLY_TYPE_NOT_COVERED`) before enqueueing.
- **Database**: migration `054_masking_suggestion_sources.py` extends
  `ck_suggested_spans_source` (added in `038b`) from `('keyword', 'llm')` to
  `('keyword', 'llm', 'pattern', 'local_model')`, applied via `apply_to_all_tenant_schemas`, the
  same mechanism `038b` used and the same one its own comment anticipated ("a BERT-backed source
  is planned for a later change in this same plan").
- **seed-bootstrap**: no spec changes. Its **Batch Pre-labeling** requirement already states the
  batch job "SHALL apply the same extraction, grounding, verification, and entity type
  constraints as single-document LLM pre-labeling" — this change's behavior is inherited by the
  batch path through `extract_and_ground_document` with no separate spec delta needed. The
  local_only-coverage check is added to the batch trigger endpoint for the same reason the
  existing 5-document cap and entity-type-count checks are enforced there, not only in the
  single-document trigger.
- **No impact**: the keyword pre-labeling path, manual annotation, the human-approval gate spans
  still pass through before becoming confirmed, entity type CRUD (delivered by
  `entity-sensitivity-classification`), and the portal's suggested-spans review UI — a reviewer
  sees the same real text they always have, since masking only ever affects what the *external
  LLM* sees, never what is stored or displayed.

## Open Questions

- **Rollout gate.** `entity-sensitivity-classification` backfilled every existing entity type to
  `open`. The moment this change ships, masking only protects a tenant's data for types someone
  has since reclassified. Whether Tenant Admins are expected to review classifications before
  this ships, or whether this change should itself add a one-time "review your entity types"
  interstitial before a tenant's next pre-labeling run, is a product decision left open here.
- **Coverage gap for custom `local_only` types.** The local model's coverage is limited to what
  `base_label_mapping` can express — PER, ORG, LOC, MISC. A `local_only` type with no plausible
  base-label mapping (e.g. a domain-specific free-text field with no CoNLL analogue) is exactly
  the case the new **Local-Only Type Coverage Requirement** refuses to run pre-labeling for,
  rather than silently leaving it uncovered — but that also means such a tenant cannot use
  automated pre-labeling at all until a plausible mapping is found or the type is reclassified.
  Whether a future change should add a dedicated local extraction path for unmapped `local_only`
  types is left open.
