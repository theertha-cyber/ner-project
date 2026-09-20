## Why

The `document-ingestion` capability already states the rule this change finishes: an ingesting actor is recorded on every document and listing restricts a non-administrative user to their own human-ingested documents "**so that document listing and chat retrieval agree on what a user may see**". Only one direction of that agreement was ever built. Listing enforces it (`list_documents`, `src/document_service/api/v1/documents.py:268-271`); **no chat answer channel does**. The string `uploaded_by` appears nowhere in `src/chat_api`, `src/shared/retrieval`, or `src/analytics_service` — `DenseRetriever.retrieve` (`src/shared/retrieval/retriever.py:106`) and `SparseRetriever` filter on `purpose='query'`, the ADR-014 conversation clause and the CAP-3 hidden-document clause, and nothing else.

The consequence lands squarely on the platform's own HR-screening use case. Business user 1 uploads resumes A, B and C; business user 2 uploads D and E. User 1 asks which candidates know Python, and the assistant answers with candidate D — name, organization, skills and a quoted snippet of D's resume — sourced from a document user 1 cannot even see listed in the Documents library. The existing spec's "Listing and retrieval agree" scenario only covers the source-system direction, so the human-upload direction has never failed a test. This is a live confidentiality gap between two users of the same tenant, not a theoretical one.

## What Changes

- **BREAKING (answer behaviour):** a chat answer for a non-administrative user is restricted to documents that user ingested, plus documents no human ingested. Tenants relying on tenant-wide chat answers across colleagues' uploads will see fewer results. This is the point of the change, and the rollout risk is carried in `verification.md`.
- The visibility rule is stated once, as the same predicate listing already uses — `ingested_by_kind <> 'human' OR uploaded_by = <requesting user>` — and `tenant_admin` is unscoped, exactly as in the library.
- **Semantic retrieval** (`DenseRetriever`, `SparseRetriever`, and therefore `HybridRetriever` and `RerankingRetriever`) applies the predicate unconditionally in SQL, as a sibling of the existing purpose and conversation restrictions — not as an optional `metadata_filter`.
- **`document_chunks` gains denormalized `uploaded_by` and `ingested_by_kind` columns**, mirroring how `purpose` (migration 022) and `conversation_id` (migration 041) were denormalized, so the vector path filters without a join that would defeat the `hnsw` index plan.
- **The relational answer channel** gains an uploader scope built on the existing inline-view rewrite (`apply_conversation_scope` in `src/chat_api/services/sql_generator.py:729`), so the restriction survives aggregation, `GROUP BY` and `LIMIT` — a `COUNT(*)` over `document_entities` must not count another user's documents.
- **Entity resolution** (`src/chat_api/services/entity_resolver.py:165,185`) applies the same restriction. It queries `document_entities` tenant-wide today and is how a candidate's *name* reaches the user during disambiguation, before any retrieval result exists.
- **The requesting user is carried on `ToolContext`** from authenticated request state, threaded exactly as `conversation_id` already is, and added to `FORBIDDEN_ARG_KEYS` so no LLM-generated or user-generated tool argument can name or widen it.
- **BREAKING (widget answers):** the embeddable widget channel (`src/chat_api/api/v1/public.py`) answers under a tenant service token with no end user at all. Absence of a requesting user is treated as "no human", so the widget may answer only from source-system-ingested content. A tenant whose widget today answers from staff uploads will find it answers from nothing until that content arrives through a source system. This is the fail-closed reading, and it is called out as a rollout risk rather than buried.
- Conversation-owned chat attachments keep working unchanged: they are already ingested with `ActorKind.HUMAN` and the uploader's id (`src/chat_api/api/v1/chat.py:246`), so the new predicate admits them for their own uploader and the ADR-014 conversation clause continues to bound them.

## Capabilities

### New Capabilities

- `uploader-scoped-retrieval`: the visibility rule for human-ingested content across every chat answer channel — that a document's ingesting actor determines which users may retrieve from, aggregate over, or be shown entities from it; that the rule is derived from authenticated request state and is not reachable from a tool argument, a generated statement or a caller-supplied scope; that source-system content stays tenant-wide; and that listing and every answer channel are required to agree in both directions.

### Modified Capabilities

- `document-ingestion`: the "Document visibility by ingesting actor" requirement gains the missing direction — a human-ingested document that listing denies a user SHALL NOT be citable, countable or nameable in that user's chat answers. Chunk writing additionally denormalizes the ingesting actor onto `document_chunks`.
- `retrieval-core`: the `Retriever` interface gains a second unconditional, caller-uncontrollable restriction alongside `purpose='query'` — the uploader-visibility predicate.
- `retrieval-tools`: "Tenant scope is caller-supplied, never argument-supplied" extends to the requesting user; `ToolContext` carries it and `args_schema` may not declare it.
- `chat-api`: the relational answer channel applies an uploader scope to every generated statement, and entity resolution restricts its `document_entities` reads the same way.

## Impact

- `src/shared/retrieval/retriever.py` — an uploader-visibility clause in the dense and sparse SQL, built like `_conversation_clause` and `_hidden_documents_clause`.
- `src/shared/retrieval/tools/base.py` — `requesting_user_id` and `uploader_unscoped` on `ToolContext`; `FORBIDDEN_ARG_KEYS` grows.
- `src/chat_api/graph/nodes.py`, `src/chat_api/services/rag_orchestrator.py` — thread the requesting user from request state through graph state into `ToolContext`, following the `conversation_id` path exactly.
- `src/chat_api/services/sql_generator.py` — `apply_uploader_scope` beside `apply_conversation_scope`, applied to every statement rather than on request.
- `src/chat_api/services/entity_resolver.py` — the predicate on both `document_entities` reads.
- `src/chat_api/api/v1/chat.py` — pass `user_id` and `role` from `request.state` into the orchestrator call on both the JSON and streaming routes.
- `src/document_service/services/ocr_worker.py` — denormalize `uploaded_by` and `ingested_by_kind` onto `document_chunks` at write time, beside `purpose` and `conversation_id`.
- `alembic/versions/0NN_*` — the two chunk columns on `tenant_template` and every provisioned tenant schema, plus a backfill from `documents`, following migrations 022/034/040/041.
- `src/shared/observability/domain_metrics.py` — a declared family recording how often an answer channel narrowed a result set, with a finite label set and no tenant content.
- Tests: `tests/test_retrieval_foundation.py`, `tests/test_document_visibility.py`, `tests/test_sql_generator_*`, `tests/test_entity_resolution*.py`, plus new files named in `verification.md`.
- **Out of scope, deliberately:** the external PostgreSQL channel (ADR-016) runs against the tenant's own database, which has no platform `documents` table and therefore no ingesting actor to scope by; `src/analytics_service` serves the portal's dashboards rather than a chat answer, and its own visibility question is a separate change.
- **Downstream:** this change is a prerequisite for a later change letting a user open a cited document's original in the chat UI. That viewer's authorization rule follows from the rule settled here. The viewer is not designed in this change.

## Open Questions

- **Should the rule be tenant-configurable?** A single-team tenant that deliberately pools uploads is now restricted. The assumption taken here is **no** — one rule, matching listing, with no per-tenant switch — because a configurable isolation boundary is one that can be misconfigured into the gap this change closes, and because the tenant-wide behaviour remains available by giving the users `tenant_admin` or by ingesting through a source system. Confirm before implementation; a switch is far cheaper to add now than to retrofit.
- **What happens to conversations answered under the old rule?** Historical `chat_messages` rows retain citations to documents the user may no longer retrieve. The assumption is that persisted history is left untouched and is not retroactively filtered; only new answers are scoped. Tracked as a risk in `verification.md`.
- **Is fail-closed right for the widget?** The alternative readings are that a widget should see all source-system *and* all human-uploaded content (which reproduces the gap this change closes, for an anonymous caller), or that the widget should be excluded from this change entirely. The assumption taken here is the fail-closed one. It is the most consequential assumption in this proposal for any tenant running the widget, and should be confirmed explicitly.
- **Does the `hnsw` plan actually hold with the added predicate?** The denormalization is chosen precisely so it should, but the top-k recall effect of a selective filter on an approximate index needs measuring rather than assuming, and is recorded as a verification risk.
