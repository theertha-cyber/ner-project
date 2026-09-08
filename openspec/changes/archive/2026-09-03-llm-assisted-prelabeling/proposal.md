## Why

Tenants annotate training documents entirely by hand today; the only pre-labeling assist is a deterministic keyword matcher (`prelabel_document` in `spans.py`) that scans for literal example phrases. It only catches exact substring matches and requires no LLM cost, but it produces low recall on anything that isn't an exact phrase match, so annotators still label most entities from scratch. Tenants that can supply a handful of example question-answer pairs (e.g. HR: "How many years of experience does X have? -> X has 10 years") could get materially better first-pass suggestions from an LLM, cutting manual annotation effort, while keeping the same human-approval gate that already exists for suggested spans. This is change 1 of a 6-change plan to introduce LLM- and, later, BERT-assisted annotation; this change adds the LLM suggestion source only — no UI, no training pipeline changes.

## What Changes

- Add a new LLM-based pre-labeling capability that generates `suggested_spans` for a document, as an alternative source alongside the existing keyword matcher (which is unchanged and remains the default when no LLM context is configured).
- Add an optional QA-pairs field to entity type configuration (`entity-config`), used only as few-shot context for the LLM prompt — never as a literal label source for a specific document. The LLM performs full-document extraction across all configured entity types on every call, so entities outside the QA pairs' topics are not silently left unlabeled.
- Add a grounding/verification step: the LLM must return verbatim quotes from the document; a backend step locates each quote's character offsets and verifies an exact (case-insensitive) match before storage. Non-matching quotes are dropped, not stored, not force-fit.
- Add a `source` column to `suggested_spans` (`keyword` | `llm`) via an Alembic migration, and require the existing keyword pre-labeling path to populate it as `keyword` going forward.
- Run LLM pre-labeling asynchronously via the existing Celery/RabbitMQ worker infrastructure (matching the pattern in `training_service/worker.py`), not synchronously in the request path.
- Cache LLM pre-labeling results keyed on (document content hash, entity-type configuration version) so re-running against an unchanged document and configuration is free.
- **BREAKING**: none. The existing keyword pre-label endpoint and its response shape are unchanged; this change only adds a new endpoint/source and a new (nullable-safe, backfilled) column.

## Capabilities

### New Capabilities

- `llm-prelabeling`: LLM-driven span suggestion generation for a document — trigger endpoint, extractive-only LLM prompting constrained to the tenant's configured entity types, verbatim-quote grounding/verification against document text, async execution, and content-hash-based caching.

### Modified Capabilities

- `entity-config`: entity type definitions gain an optional QA-pairs field (question/answer examples) used as LLM prompt context. No change to `examples` or `base_label_mapping` semantics.
- `annotation-workspace`: the Pre-labeling requirement is extended so every suggested span records its `source` (`keyword` or `llm`); the existing keyword pre-labeling scenario is unchanged in behavior but now also asserts `source: "keyword"` on its output.

## Impact

- **Database**: new `source` column on `{tenant_schema}.suggested_spans` (Alembic migration under `alembic/`); new QA-pairs column on `public.entity_definitions`.
- **Backend**: new endpoint(s) and service logic in `src/annotation_service` (trigger + grounding/verification); new Celery task, likely alongside `src/training_service/worker.py`'s pattern or a new task module, reusing its service-token pattern (`_make_service_token`) for service-to-service auth.
- **External dependency**: an LLM API call is introduced into the annotation pipeline for the first time. Provider/model choice and per-tenant data-handling policy are open questions (see below), not resolved by this change.
- **No impact**: `annotation_service`'s span CRUD, the existing keyword pre-label endpoint, `export.py`, or anything in `training_service` — all unchanged. No UI/frontend changes in this change.

## Open Questions

- **PII / data residency**: is sending tenant documents (e.g. HR/résumé content) to an external LLM API acceptable for every tenant, or does this need a per-tenant opt-in / self-hosted-model fallback? This change should not proceed to implementation without an answer, but the spec itself is written provider-agnostically so the answer doesn't block spec review.
- **LLM provider/model**: not chosen yet; design.md should name a default while keeping the integration swappable.
- **Duplicate-quote resolution rule**: when a quote the LLM returns matches multiple locations in the document, this proposal takes "first occurrence not already covered by another suggested span" (mirroring the existing keyword matcher's longest-match-wins overlap handling) — flagged here for review since it affects recall.
- **Confidence score semantics for `source: "llm"`**: the keyword matcher's confidence is a fixed heuristic (0.85). What the LLM's confidence score should represent, and whether it's model-reported or computed, needs a decision in design.md — later changes (5, 6) may depend on this being meaningful.
