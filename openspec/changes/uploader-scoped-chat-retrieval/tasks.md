## 1. Shared predicate definition

- [x] 1.1 Create `src/shared/document_visibility.py` exposing the uploader-visibility rule once: the requesting-user value object (user id + role), a `is_unscoped(role)` check, and SQL fragment builders for the two shapes each channel needs — a predicate over a row carrying the denormalized columns, and a predicate reaching a document through `document_id`. No channel restates the literal condition. (scenarios 1–4)
- [x] 1.2 Define the absent-requesting-user branch explicitly in the same module: no requesting user means every human-ingested document is excluded, never an always-true or empty clause. (scenario 19)
- [x] 1.3 Add `tests/test_document_visibility_rule.py` — unit tests for the predicate over own/other/source-system/admin/absent-user, and an assertion that the module is the only definition. (scenarios 1–4, 19)
- [x] 1.4 Add a guard test asserting the literal condition appears in `src/` only in the shared module, the migration, and the chunk-write path. (scenario 5)

## 2. Telemetry

- [x] 2.1 Declare the uploader-scoping metric family in `src/shared/observability/domain_metrics.py` with enumerated channel and outcome label sets and no user or tenant identifier label; add the named recorder that coerces out-of-set values. (scenario 21)
- [x] 2.2 Add `tests/test_uploader_scoping_telemetry.py` — label keys and value sets are exactly as declared, an out-of-set outcome records as the catch-all, no user/tenant label exists, and no emitted record contains a filename, entity value, chunk text, or generated SQL. (scenarios 20, 21)
- [x] 2.3 Confirm `scripts/telemetry_scan.py` passes with the new family and call sites. (scenario 20)

## 3. Chunk denormalization and migration

- [x] 3.1 Add `uploaded_by` and `ingested_by_kind` to `document_chunks` in a new `alembic/versions/0NN_*` migration, on `tenant_template` and every provisioned tenant schema, nullable, following the pattern of migrations 022/034/040/041. (scenario 30)
- [x] 3.2 Backfill both columns from each chunk's parent document, per schema, in batches; make the migration re-runnable and assert zero rows with an absent actor kind on completion. (scenarios 30, 31)
- [x] 3.3 Denormalize both values onto chunk writes in `src/document_service/services/ocr_worker.py`, in the same insert that writes `purpose` and `conversation_id`. (scenarios 28, 29)
- [x] 3.4 Extend `tests/test_chunk_metadata_ingest.py` — a human-ingested document's chunks carry its actor and uploader; a source-system document's chunks carry the source-system value. (scenarios 28, 29)
- [x] 3.5 Add `tests/test_migration_chunk_uploader_backfill.py` — run the migration against a schema holding pre-existing chunks; every chunk ends up carrying its own document's actor and uploader, and none is left absent. (scenarios 30, 31)

## 4. Retrieval enforcement

- [x] 4.1 Add the uploader-visibility clause to the dense and sparse SQL in `src/shared/retrieval/retriever.py`, built from the shared definition and sited beside `_conversation_clause` and `_hidden_documents_clause`; it is unconditional and unreachable from `metadata_filter`. (scenarios 36, 37, 39)
- [x] 4.2 Carry the requesting user on the retrieval call path so `HybridRetriever` and `RerankingRetriever` inherit it without their own copies of the rule. (scenarios 36, 37)
- [x] 4.3 Extend `tests/test_retrieval_foundation.py` — dense and sparse exclude another human's document; source-system chunks stay retrievable by everyone; `metadata_filter` naming an invisible document returns empty without raising; a `tenant_admin` is unscoped. (scenarios 36–40)
- [x] 4.4 Confirm the pre-existing retriever scenarios still pass unchanged — hnsw index use, orchestrator call path, purpose exclusion and its bypass guard, sparse behaviour, hybrid fusion, and `metadata_filter` narrowing. (scenarios 32–35, 41–45)
- [x] 4.5 Add `tests/test_retrieval_hnsw_recall.py` — a minority-uploader fixture where the requesting user owns roughly a tenth of matching chunks still returns `top_k` results when that many visible matches exist; record the measured figure. (Risk 7)

## 5. Tool layer

- [x] 5.1 Add the requesting user and role to `ToolContext` in `src/shared/retrieval/tools/base.py`, constructed from authenticated request state only, and extend `FORBIDDEN_ARG_KEYS` with the uploader-related keys. (scenarios 6, 47)
- [x] 5.2 Extend `tests/test_retrieval_tools.py` — no tool's `args_schema` names tenancy or uploader parameters; the uploader restriction survives any argument values; a `document`-type scope naming an invisible document returns nothing without an argument-validation error. (scenarios 46–51)

## 6. Orchestration threading

- [x] 6.1 Thread the requesting user and role from `request.state` through `RAGOrchestrator` into graph state and onto `ToolContext`, following the existing `conversation_id` path, on both the JSON and streaming routes in `src/chat_api/api/v1/chat.py`. (scenarios 52, 53)
- [x] 6.2 Verify no request-scoped value is assigned to the shared orchestrator instance or any collaborator it holds. (scenario 53)
- [x] 6.3 Set the absent-requesting-user case explicitly for the widget channel in `src/chat_api/api/v1/public.py`, so it answers under the fail-closed rule rather than inheriting an unscoped default. (scenarios 17–19)
- [x] 6.4 Add `tests/test_chat_uploader_scope_threading.py` — JSON and streaming routes scope identically; concurrent requests from two users each apply their own rule; the widget declines on human-uploaded content and answers from source-system content. (scenarios 17–19, 52, 53)

## 7. Relational answer channel

- [x] 7.1 Add `apply_uploader_scope` beside `apply_conversation_scope` in `src/chat_api/services/sql_generator.py`, reusing the inline-view rewrite and the scope-column map shape, built from the shared definition. (scenarios 54, 57)
- [x] 7.2 Apply it unconditionally to every generated statement over the platform's own tenant schema — not only to statements carrying a document scope — and confirm it conjoins with, rather than replaces, the conversation scope. (scenarios 55, 58)
- [x] 7.3 Extend the whitelist guard test so a whitelisted relation missing from the uploader scope-column map fails the build, matching the existing conversation-scope guard. (scenario 57)
- [x] 7.4 Add `tests/test_sql_generator_uploader_scope.py` — row-returning statements exclude another human's documents; a `COUNT` is scoped before aggregation; a trailing `LIMIT` does not defeat the scope and does not wrongly empty the result; both scopes appear conjoined. (scenarios 54–58)

## 8. Entity resolution

- [x] 8.1 Apply the uploader-visibility predicate to both `document_entities` reads in `src/chat_api/services/entity_resolver.py`, and carry the requesting user into that path. (scenarios 59–61)
- [x] 8.2 Resolve the design Open Question on whether the same two reads also gain the conversation predicate; record the decision in `design.md` before implementing, and implement whichever way it is settled. (design Open Questions, Risk 2)
- [x] 8.3 Extend `tests/test_entity_resolution_flow.py` — another user's person yields no candidate; a disambiguation names only visible people; the requester's own people resolve exactly as before. (scenarios 59–61)

## 9. Citations and cross-channel agreement

- [x] 9.1 Confirm citation assembly in `src/chat_api/services/context_assembler.py` and `src/chat_api/services/rag_orchestrator.py` can only name documents the scoped channels returned, and add an assertion rather than relying on upstream filtering. (scenario 12)
- [x] 9.2 Point the listing path in `src/document_service/api/v1/documents.py` at the shared definition instead of its own inline predicate, leaving its behaviour unchanged. (scenarios 5, 22–27)
- [x] 9.3 Extend `tests/test_document_visibility.py` with the paired both-directions assertions — a listable document is answerable, and an unlistable one is absent from the answer, its citations, and any count behind it. (scenarios 13, 14, 25, 26)
- [x] 9.4 Add `tests/test_uploader_scope_channel_coverage.py` — capture the SQL executed by each scoped channel and assert no statement names a `public.` control-plane table, and that every channel reaching `document_chunks`, `document_entities` or `document_text_spans` carries the predicate. (scenarios 9–11, ADR-017)
- [x] 9.5 Add `tests/test_uploader_scope_attachments.py` — a user's own attachment is retrievable in its own conversation and not in another. (scenarios 15, 16)
- [x] 9.6 Add the phrasing-attack case to the channel-coverage tests: a question naming another user's document, filename, or content does not widen the rule. (scenarios 7, 8)

## 10. Rollout

- [ ] 10.1 Identify tenants whose chat answers currently span multiple uploaders, and tenants running the embeddable widget, using the narrowing metric from group 2 before the enforcement in groups 4–8 is enabled.
- [x] 10.2 Document `tenant_admin` and source-system ingestion as the supported ways to keep a shared corpus shared, and notify affected tenants of the behaviour change.
- [ ] 10.3 Confirm with the change's approver that the fail-closed widget behaviour and the no-per-tenant-switch decision are intended before enforcement ships. (design Decisions 5, 6)

## 11. Verification & Evidence

- [ ] 11.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 11.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 11.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 11.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 11.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 11.6 Run `openspec validate uploader-scoped-chat-retrieval --type change --strict` and confirm it exits clean before archive.
