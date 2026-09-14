## Why

Extracted entity values are persisted only as text. `document_entities.entity_value` holds the raw span (`"two and a half years"`, `"5+ years"`), and `document_entities.normalized_value` holds a *lexical* canonicalization of that same text (casefold, whitespace collapse, punctuation strip, alias map — see `src/extraction_service/services/entity_normalizer.py:63`). Both columns are `TEXT`.

Consequently a query like `YEARS_OF_EXP > 2` cannot be evaluated. The SQL layer (`src/chat_api/services/sql_generator.py`) can only produce string comparisons over text columns, so `normalized_value > '2'` compares lexicographically and silently returns wrong rows. The only alternative today is asking the LLM to interpret the free-text values, which is non-deterministic and unbounded in cost.

This affects every entity type whose meaning is a quantity, a date, a duration, or an amount — not just years of experience — so the fix must be a generic normalization layer, not a `YEARS_OF_EXP` special case.

## What Changes

- Introduce **semantic normalization** as a concept distinct from the existing **lexical normalization**. Lexical normalization maps surface variants of the *same string* onto one canonical string (`ReactJS` → `react`). Semantic normalization maps a text span onto a *typed value* in a canonical unit (`two and a half years` → `2.5` years). The two stay separate: separate module, separate columns, separate configuration.
- Add a per-entity-type **value kind** declaration to the tenant's entity type registry (`public.entity_definitions`): `text` (default, today's behaviour), `number`, `duration`, `money`, `date`, `boolean`. Entity types keep working unchanged when the kind is `text`.
- Add a **normalizer registry** in the extraction service: one deterministic, pure parser per value kind, dispatched by the entity type's declared kind. No LLM, no network. Unparseable values are not an error — they yield NULL typed columns and the row is stored exactly as it is today.
- Extend `document_entities` with sparse **typed value columns** — `value_kind`, `value_number`, `value_number_high`, `value_unit`, `value_date`, `value_date_high` — plus partial indexes for numeric and date filtering. Text columns are untouched, so every existing query keeps working.
- Extend the SQL whitelist so the chat SQL layer may reference the new columns, making `WHERE entity_type = 'YEARS_OF_EXP' AND value_number > 2` a legal, deterministic, index-backed query.
- Extend the backfill utility so previously extracted documents can gain typed values without re-running inference (typed values derive from the stored `entity_value` text, unlike BIO reconstruction).

Not breaking: all new columns are nullable, all new configuration defaults to today's behaviour.

## Capabilities

### New Capabilities

- `structured-entity-values`: the semantic normalization layer — value kinds, the normalizer registry contract, canonical units, range and bound handling (`5+ years`, `3–5 years`), NULL-on-unparseable semantics, and the typed-column persistence contract on `document_entities`.

### Modified Capabilities

- `entity-config`: entity type definitions gain a `value_kind` field (and an optional `value_unit` for the canonical unit), validated against the supported kind set, defaulting to `text`.
- `chat-api`: the `document_entities` whitelist gains the typed value columns so generated SQL may filter, sort, and compare on them.
- `tenant-schema-migrations`: the tenant template and every existing tenant schema gain the new `document_entities` columns and indexes.

Note: the `entity-normalization` capability introduced by the in-flight `normalized-entity-store` change is *not* modified. Lexical canonicalization keeps its current contract; this change layers on top of it.

## Impact

Code:
- `src/extraction_service/services/entity_normalizer.py` — unchanged in behaviour; stays the lexical layer.
- `src/extraction_service/services/semantic_normalizer.py` — **new**; value-kind registry and parsers.
- `src/extraction_service/services/document_entity_store.py` — insert the new columns.
- `src/extraction_service/worker.py:206-227` — one new pass between reconstruction and persistence.
- `scripts/backfill_document_entities.py` — apply the same pass; add a text-only mode that does not re-run inference.
- `src/chat_api/services/sql_generator.py` — whitelist columns; one added line of schema guidance in the prompt.
- `src/gateway/services/entity_service.py`, `src/gateway/models/__init__.py` — `value_kind` / `value_unit` on `EntityDefinition`.
- `alembic/versions/` — two migrations: `document_entities` columns + indexes (tenant schemas), `entity_definitions` columns (public schema).

Out of scope, unchanged: retrieval architecture, entity resolution, vector retrieval, embeddings, reranking, LangGraph orchestration, and prompting beyond the whitelist schema line.

Ordering: this change touches `document_entities`, created by the un-archived `normalized-entity-store` change. It must land after that one.

## Open Questions

- Should the value kind live on `entity_definitions` (tenant-configurable, per-tenant drift possible) or in code as a static type registry (uniform, requires deploy to add a type)? Assumption: `entity_definitions`, because entity types are already tenant-defined there and a code registry could not name a tenant's custom type.
- Which canonical units ship first? Assumption: `duration` → years for experience-like types with a stored `value_unit`; `money` → minor-unit-free decimal in a single stored currency with no FX conversion.
- Should `5+ years` populate `value_number = 5` with an open-ended high bound, or `value_number = 5` only? Assumption: `value_number = 5`, `value_number_high = NULL`, so `value_number >= 5` behaves intuitively; ranges (`3–5 years`) fill both.
- Should changing an entity type's `value_kind` trigger automatic re-normalization of stored rows? Assumption: no — manual backfill invocation, kept as an optional future enhancement.
