## Context

Entity values reach storage through exactly one path today:

1. `src/extraction_service/worker.py:206` aligns model predictions to source offsets.
2. `merge_wordpieces()` collapses `##` continuation tokens.
3. `reconstruct_entities()` (`entity_normalizer.py:73`) walks the BIO sequence and emits `NormalizedEntity(entity_type, entity_value, normalized_value, confidence, page_number, char_start, char_end)`. `entity_value` is `" ".join(token texts)`; `normalized_value` is `canonicalize(entity_value)`.
4. `insert_document_entities()` (`document_entity_store.py:8`) writes one row per entity into `{tenant_schema}.document_entities`.

`canonicalize()` (`entity_normalizer.py:63`) is the *only* transformation applied to a value. It does NFKC normalization, casefold, whitespace collapse, surrounding-punctuation strip, then a static `ALIAS_MAP` lookup. It is type-agnostic — every entity type gets the same treatment — and it is purely lexical: its output is always a string derived from the input string's characters. It is also imported by `src/chat_api/services/entity_resolver.py:60` and `src/chat_api/graph/nodes.py:240` for mention matching, so its contract cannot shift.

The second place a value is transformed and persisted is `scripts/backfill_document_entities.py:89`, which re-runs inference and then calls the same reconstruct + insert pair. A third table, `{tenant_schema}.extracted_entities`, stores raw per-token rows with no normalization at all. Annotation-side tables (`spans`, `suggested_spans`) store human-marked text and are not part of the extraction path.

On the query side, `src/chat_api/services/sql_generator.py:10` whitelists `document_entities` columns, all of which are `TEXT`, `DOUBLE PRECISION` (confidence), or `INTEGER` (offsets). The generated SQL therefore cannot express a value comparison; the prompt at line 53 explicitly steers the model to `normalized_value = '<literal>'` equality matching.

Entity types are already a first-class, tenant-scoped, versioned resource: `public.entity_definitions` (`src/gateway/models/__init__.py:73`) with `name`, `description`, `examples`, `validation_rule`, `target_table`, `base_label_mapping`, `version`. Tenants define their own type names, so no code-side enum can enumerate them.

Constraints:
- ADR-001 requires per-tenant schema isolation, so any `document_entities` change must be applied to `tenant_template` *and* every existing `tenant_%` schema, matching the pattern in `alembic/versions/026_document_entities.py`.
- The in-flight `normalized-entity-store` change owns `document_entities` and its `entity-normalization` capability. This change is strictly additive on top and must land after it.
- ADR-007's guardrailed RAG path is unchanged; the goal is to move comparison work *out* of the LLM, not to add reasoning.

## Goals / Non-Goals

**Goals:**

- Make `YEARS_OF_EXP > 2`, `SALARY > 1000000`, `NOTICE_PERIOD <= 30`, `CERTIFICATION_EXPIRY < today`, and `DATE BETWEEN x AND y` expressible as deterministic, index-backed SQL predicates.
- Establish semantic normalization as a named layer distinct from lexical normalization, with its own module, configuration, and columns.
- Make adding a new structured entity type a configuration act (set a value kind on the entity definition) rather than a pipeline redesign; make adding a new *kind* a matter of registering one parser.
- Degrade to exactly today's behaviour whenever a value cannot be parsed or a type declares no kind.

**Non-Goals:**

- Changing lexical canonicalization, the alias map, or `canonicalize()`'s contract.
- Retrieval architecture, entity resolution, vector retrieval, embeddings, reranking, LangGraph orchestration.
- LLM-assisted normalization. Every parser in this change is deterministic and pure.
- Currency FX conversion, timezone-aware date arithmetic beyond `DATE`, or unit conversion across kinds.
- Automatic re-normalization when a type's configuration changes.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant data lives in separate Postgres schemas; migrations apply to `tenant_template` and loop over existing `tenant_%` schemas | New `document_entities` columns and indexes must be added in both places by one migration; no cross-tenant table |
| ADR-004-openspec-governance | Spec-driven development; behaviour changes require spec deltas before code | This change ships a new `structured-entity-values` capability plus deltas for `entity-config`, `chat-api`, `tenant-schema-migrations` |
| ADR-007-chatbot-architecture | Chat answers come from a guardrailed RAG pipeline with a whitelisted SQL path | New columns must be added to the SQL whitelist to be reachable; validation rules (SELECT-only, LIMIT, table whitelist) stay as-is |
| ADR-003-model-serving-topology, ADR-006-training-infrastructure, ADR-008-base-model-as-default | Model serving and training topology | Untouched — normalization happens after inference returns, on the worker side |

ADR-002 is superseded in part by ADR-008 and does not constrain this design.

## Decisions

### Decision 1: Semantic normalization is a separate pass, not an extension of `canonicalize()`

**Choice:** Add `src/extraction_service/services/semantic_normalizer.py` exposing `normalize_values(entities, type_config) -> list[NormalizedEntity]`, run as a distinct step in the worker *after* `reconstruct_entities()`. `entity_normalizer.py` is not modified beyond widening the `NormalizedEntity` dataclass with nullable typed fields.

**Rationale:** The two problems have different inputs and different outputs. Lexical normalization is `str -> str`, type-agnostic, and already depended on by the chat-side resolver. Semantic normalization is `(str, value_kind) -> typed value`, type-*dependent*, and needs the tenant's entity type configuration — which `reconstruct_entities()` does not and should not receive. Keeping them separate preserves `canonicalize()`'s contract for its two chat-side callers and keeps the BIO reconstructor a pure function over predictions.

**Alternatives considered:**
- Extend `canonicalize()` to return a structured value — ruled out: it would force a type-config parameter into a pure string function used by `entity_resolver.py` and `nodes.py` for mention matching, where semantic parsing is meaningless and the string return type is load-bearing.
- Normalize at query time in the SQL layer — ruled out: it would mean per-row text parsing inside every query (no index usable), and it puts parsing logic in the component the change is trying to make deterministic.
- Normalize at ingest in the model-serving response — ruled out: serving is tenant-agnostic per ADR-003 and has no access to `entity_definitions`.

### Decision 2: Value kinds are declared on `entity_definitions`, not in a code registry

**Choice:** Add nullable `value_kind VARCHAR(32)` and `value_unit VARCHAR(32)` to `public.entity_definitions`. `value_kind` is validated against a code-owned set: `text` (default), `number`, `duration`, `money`, `date`, `boolean`. `value_unit` names the canonical unit the parser must produce (`years`, `days`, `INR`, …).

**Rationale:** Entity type *names* are tenant-authored — a tenant may create `NOTICE_PERIOD` or `RETAINER_FEE` with no code change. A code-side map from type name to kind could never cover them and would drift per tenant. The kind *vocabulary*, by contrast, is bounded by which parsers exist, so it stays code-owned and validated. This mirrors `validation_rule` and `base_label_mapping`, which already live on this table for the same reason.

**Alternatives considered:**
- Static `dict[str, ValueKind]` in Python — ruled out: cannot express tenant-custom type names; adding a type would require a deploy.
- Infer the kind from observed values — ruled out: non-deterministic, and a type with mixed junk values would flip kinds between extraction runs.
- Store the kind on `document_entities` only — ruled out: it would be a per-row copy with no authoritative source, so a config fix could not be applied consistently.

### Decision 3: Typed values go in sparse typed columns on `document_entities`, not JSONB and not a side table

**Choice:** Extend `document_entities` with `value_kind TEXT`, `value_number DOUBLE PRECISION`, `value_number_high DOUBLE PRECISION`, `value_unit TEXT`, `value_date DATE`, `value_date_high DATE`, all nullable. Add partial indexes `(entity_type, value_number) WHERE value_number IS NOT NULL` and `(entity_type, value_date) WHERE value_date IS NOT NULL`.

**Rationale:** The whole point is deterministic, index-backed SQL that an LLM can be told about in one line of schema description. Native typed columns give real Postgres comparison semantics, real B-tree indexes, and a whitelist entry that reads like every other column. Partial indexes keep the cost proportional to the number of *structured* rows, which will be a minority. Nullable columns mean untouched rows, untouched queries, and no rewrite of existing data.

**Alternatives considered:**
- A single `structured_value JSONB` column — ruled out: every query becomes a cast (`(structured_value->>'number')::float > 2`), the SQL validator and whitelist would need to reason about JSON paths, and expression indexes would be needed per kind anyway. It buys extensibility the sparse-column approach already has, at the cost of the deterministic-SQL goal.
- A separate `document_entity_values` table joined by entity id — ruled out: adds a join to every structured query for no isolation benefit, since `document_entities` is already one row per logical entity and both tables would live in the same tenant schema.
- Reuse `normalized_value` with zero-padded numeric strings — ruled out: breaks lexical matching for `entity_resolver.py`, and range queries on padded text are fragile and unsortable across magnitudes.

### Decision 4: One parser per kind behind a registry, dispatched by declared kind

**Choice:** `semantic_normalizer.py` holds `PARSERS: dict[str, Parser]` where `Parser = Callable[[str, str | None], StructuredValue | None]` — input raw text plus the declared canonical unit, output a `StructuredValue` dataclass or `None`. Adding a kind means writing one pure function and registering it. Parsers handle: spelled-out numerals (`two and a half`), decimals, thousands separators, unit suffixes (`yrs`, `months`, `k`, `lakh`), open bounds (`5+`, `more than three`), and closed ranges (`3-5 years`).

**Rationale:** A registry keyed by a validated vocabulary is the smallest thing that makes the architecture extensible without a redesign: the worker, the store, the migration, and the whitelist are all kind-agnostic. Only the registry grows. Passing the declared unit *into* the parser is what makes the output comparable — `NOTICE_PERIOD` declared in `days` and written `"2 months"` normalizes to `60`, not `2`.

**Alternatives considered:**
- One monolithic `parse_value(text, kind)` with branching — ruled out: adding a kind edits shared code and grows a function every kind's tests must exercise.
- A third-party parser library (`dateparser`, `quantulum3`) as the primary path — ruled out as a *hard* dependency of the architecture; a parser may adopt one internally later without changing the registry contract.

### Decision 5: Unparseable is NULL, never an error

**Choice:** When a parser returns `None`, or the entity type declares no kind, the typed columns are written NULL. The row is persisted exactly as it would be today. Nothing is logged as a failure beyond a counter.

**Rationale:** NER output is noisy; a `YEARS_OF_EXP` span reading `"several"` is normal, not exceptional. Failing the document would make normalization a new source of extraction failures, which is a strictly worse trade than a NULL that simply does not match a numeric filter. `WHERE value_number > 2` correctly excludes rows it cannot evaluate.

**Alternatives considered:**
- Raise and fail the document — ruled out: turns a data-quality issue into an availability issue.
- Fall back to an LLM parse — ruled out: explicitly out of scope, and reintroduces the non-determinism this change removes.

### Decision 6: Backfill derives typed values from stored text, without re-running inference

**Choice:** Add a mode to `scripts/backfill_document_entities.py` that reads existing `document_entities` rows, applies `normalize_values()` to `entity_value`, and `UPDATE`s only the typed columns. Idempotent per document.

**Rationale:** Unlike BIO reconstruction — which needed re-inference because `extracted_entities` has no ordering column (see `normalized-entity-store` design Decision 8) — semantic normalization's only input is the already-stored `entity_value` text plus the type configuration. Re-running inference would be wasted GPU time. This also makes re-normalization after a parser fix cheap.

**Alternatives considered:**
- Re-run full extraction — ruled out: orders of magnitude more expensive for identical output.
- Backfill only on next extraction — ruled out: existing documents would silently never answer structured queries.

### Decision 7: SQL layer change is whitelist plus one schema line

**Choice:** Add the six columns to `WHITELISTED_TABLES["document_entities"]` in `sql_generator.py`, and one sentence to the schema description telling the generator to use `value_number` / `value_date` for comparisons and `normalized_value` for equality. No change to `validate_sql()`, the SELECT-only rule, the LIMIT rule, or any other guardrail.

**Rationale:** The whitelist is a hard gate — without the entries, valid structured SQL is rejected, so this part is mandatory infrastructure rather than prompt work. The single schema sentence is the minimum needed for the capability to be reachable at all; it describes columns, it does not add reasoning instructions.

**Alternatives considered:**
- Deterministic query templates bypassing the LLM for comparison queries — ruled out for this change: it is a retrieval-orchestration change, larger than the problem, and can be layered on later since the columns will already exist.

## Risks / Trade-offs

- [Parser gets a value subtly wrong — `"5"` in a `SALARY` field meaning 5 lakh becomes `5.0`] → Parsers are conservative: patterns they do not recognize with confidence return `None` rather than guessing. `entity_value` is always preserved, so any row can be re-normalized after a parser fix via backfill.
- [Tenants misconfigure `value_kind`, e.g. declaring a free-text type as `number`] → `value_kind` is validated against the supported set on write; a mismatched kind produces NULLs, not corruption, and is reversible by changing the config and re-running backfill.
- [Column proliferation as new kinds arrive — a `geo` kind would want lat/long] → Accepted. The current six columns cover number, range, duration, money, and date semantics. A future kind needing a genuinely different shape is the point at which a JSONB overflow column becomes justified; nothing in this design blocks adding one.
- [Migration cost on large tenant schemas] → `ADD COLUMN ... NULL` is metadata-only in Postgres 11+. Index creation is the real cost; partial indexes keep it proportional to structured rows, and `CREATE INDEX` can be run per schema.
- [Ordering conflict with the un-archived `normalized-entity-store` change] → This change's migration depends on `026` existing. It must be sequenced after that change lands; the tasks list states this explicitly.
- [Two normalization concepts confuse future contributors] → Enforced by structure: separate module, separate columns, separate spec capability, and a naming convention (`normalized_value` = lexical, `value_*` = semantic).

## Migration Plan

1. Land `normalized-entity-store` first (`026_document_entities.py` must exist).
2. Migration A (public schema): add `value_kind`, `value_unit` to `public.entity_definitions`, both nullable, no default backfill — NULL means `text`.
3. Migration B (tenant schemas): add the six typed columns and two partial indexes to `tenant_template.document_entities` and, via the `pg_namespace` loop pattern from `026`, to every existing `tenant_%` schema.
4. Deploy the extraction service with `semantic_normalizer.py` wired into the worker. With no type configured, behaviour is byte-identical to today.
5. Deploy the chat API whitelist change. Structured queries are now possible but return nothing until types are configured and rows normalized.
6. Configure `value_kind` on the entity types that need it.
7. Run the backfill in text-derived mode for existing documents.

Rollback: revert the chat API whitelist (queries fall back to text matching), revert the extraction service (typed columns simply stop being written). The columns themselves are inert when unused and need not be dropped; the migrations' `downgrade()` drops them if a full rollback is wanted.

## Open Questions

- Should `money` store a currency code per row (`value_unit = 'INR'`) or per entity type only? Current assumption: per row, populated from the type's `value_unit`, so a future per-row override is not a schema change.
- Should `CERTIFICATION_EXPIRY < today` resolve `today` in SQL (`CURRENT_DATE`) or be substituted before generation? Current assumption: `CURRENT_DATE`, keeping the comparison inside Postgres.
- Should the annotation UI surface the normalized typed value for review? Deferred — optional enhancement, no infrastructure dependency.
- No in-force ADR needs revisiting for this change.
