## Why

The platform has no way for a tenant to say "this entity type must never leave our infrastructure."
Today every active entity type is treated identically by LLM pre-labeling: its name, description,
and examples go into the prompt sent to the external LLM provider, and the LLM sees the tenant's
raw document text in full. For a tenant whose documents carry information like a foster-care
client's name, date of birth, or home address, there is currently no way to mark those entity
types as different in kind from, say, `organization` or `document_date` — everything is one
undifferentiated bucket.

This change adds the classification only — a `sensitivity` tier on each entity type, set by the
Tenant Admin the same place they already configure entity types. It changes no behavior of LLM
pre-labeling itself; a follow-up change (`automated-annotation-pii-masking`) is what makes the
pipeline act on this classification. Splitting them this way means this change ships as pure,
low-risk foundation: every existing and newly-created entity type defaults to the classification
that matches today's actual behavior (`open`), so nothing observable changes until the second
change is built on top of it.

## What Changes

- `public.entity_definitions` gains a `sensitivity` column: one of `open` (default), `pattern`, or
  `local_only`.
- The entity-type create and update endpoints (`src/gateway/api/v1/entity_types.py`) accept and
  return `sensitivity`.
- A `pattern`-sensitivity entity type SHALL have a `validation_rule` set — the existing regex field
  is reused as the shape a future local detector matches against, rather than adding a second
  regex column with the same purpose. Creating or updating a `pattern`-sensitivity type with no
  `validation_rule` is rejected with 422.
- A `local_only`-sensitivity type requires no extra configuration — it is free-text PII that a
  future local model (not a regex) will be responsible for finding.
- The portal's entity-types screen gains a sensitivity selector on the create/edit form, with
  `open` as the default choice.
- **Not in scope**: nothing about LLM pre-labeling, masking, or what gets sent to the external
  provider changes in this change. `sensitivity` is inert until `automated-annotation-pii-masking`
  reads it.

## Capabilities

### Modified Capabilities

- `entity-config`: **Entity Type Definition** gains the `sensitivity` field. One requirement is
  added: **Entity Type Sensitivity Classification**.

### New Capabilities

(none)

## Impact

- **Database**: migration `053_entity_type_sensitivity.py` adds
  `sensitivity TEXT NOT NULL DEFAULT 'open'` with a CHECK constraint restricting it to
  `open` / `pattern` / `local_only`, to `public.entity_definitions`. Existing rows backfill to
  `open` — the value that already describes their current (unrestricted) treatment by LLM
  pre-labeling, so the migration changes no runtime behavior by itself.
- **Backend**: `EntityTypeCreate` / `EntityTypeUpdate` schemas and the create/update handlers in
  `src/gateway/api/v1/entity_types.py` gain `sensitivity`, with the `pattern`-requires-
  `validation_rule` check added at the same validation point that already checks `value_kind`
  against its supported set. `load_active_entity_config` / `load_active_entity_config_sync`
  (`src/shared/entity_config_version.py`) SHALL include `sensitivity` in what they select, so it
  is available wherever an entity type's active configuration is already loaded — including the
  one call site (`extract_and_ground_document`) the next change will need it from.
- **Frontend**: the entity-types create/edit form gains a sensitivity selector; the entity-types
  list/detail view displays it.
- **No impact**: LLM pre-labeling (`llm_prelabel.py`, `worker.py`), the entity-config-version
  cache-key hash, and any prompt sent to the external LLM. All are addressed by
  `automated-annotation-pii-masking`.

## Open Questions

- Every entity type across every existing tenant backfills to `open` — including any tenant
  already handling sensitive documents today. This change alone does not put them at any *new*
  risk (their documents already flow to the external LLM unmasked today), but it also does not
  protect them the moment `automated-annotation-pii-masking` ships, unless someone has gone back
  and reclassified their types by then. Whether that reclassification is a manual rollout task per
  tenant, or whether `automated-annotation-pii-masking` should gate itself behind an explicit
  per-tenant confirmation, is left to that change's design — flagged here so it isn't lost.
