# Verification Plan

**Change:** uploader-scoped-chat-retrieval
**Generated:** 2026-09-18
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | uploader-scoped-retrieval | Uploader visibility is one rule, stated once | The rule admits the user's own human-ingested document | Given a `purpose='query'` document ingested by the requesting human user, when the rule is evaluated, then the document is visible | unit test: `tests/test_document_visibility_rule.py` | - [ ] |
| 2 | uploader-scoped-retrieval | Uploader visibility is one rule, stated once | The rule denies another user's human-ingested document | Given a document ingested by a different human, when the rule is evaluated for a non-admin user, then the document is not visible | unit test: `tests/test_document_visibility_rule.py` | - [ ] |
| 3 | uploader-scoped-retrieval | Uploader visibility is one rule, stated once | The rule admits source-system content to every user | Given a document ingested by a source system, when the rule is evaluated for any non-admin user of that tenant, then the document is visible | unit test: `tests/test_document_visibility_rule.py` | - [ ] |
| 4 | uploader-scoped-retrieval | Uploader visibility is one rule, stated once | Administrators are unscoped | Given a `tenant_admin` requester and a document ingested by a different human, when the rule is evaluated, then the document is visible | unit test: `tests/test_document_visibility_rule.py` | - [ ] |
| 5 | uploader-scoped-retrieval | Uploader visibility is one rule, stated once | The rule has a single definition | Given the listing path and every chat answer channel, when their predicates are inspected, then each derives from one shared definition and none restates the literal condition | guard test: `tests/test_document_visibility_rule.py::test_predicate_has_one_definition` | - [ ] |
| 6 | uploader-scoped-retrieval | The requesting user is derived from authenticated state, never from input | Tool argument schemas cannot name the requesting user | Given every registered tool, when `args_schema.properties` keys are inspected, then none names the requesting user, uploading user, or ingesting actor | unit test: `tests/test_retrieval_tools.py::test_tool_schemas_expose_no_uploader_keys` | - [ ] |
| 7 | uploader-scoped-retrieval | The requesting user is derived from authenticated state, never from input | A tool argument cannot widen the rule | Given documents from two humans matching a query, when a tool is invoked for user A with any arguments including ones naming B's document, then no result originates from B's document | integration test: `tests/test_uploader_scope_channel_coverage.py`, `tests/test_retrieval_tools.py` | - [ ] |
| 8 | uploader-scoped-retrieval | The requesting user is derived from authenticated state, never from input | A question phrased to request another user's documents does not widen the rule | Given another human's document, when a non-admin asks a question naming that document, its filename, or its content, then the answer does not draw on it | integration test: `tests/test_uploader_scope_channel_coverage.py`, `tests/test_retrieval_foundation.py` | - [ ] |
| 9 | uploader-scoped-retrieval | Every chat answer channel enforces the rule | Semantic retrieval is scoped | Given two users each with a matching `purpose='query'` document, when the first asks that query, then every returned chunk is from the first user's document | end-to-end test: `tests/test_chat_uploader_isolation_end_to_end.py`; integration test: `tests/test_retrieval_foundation.py::TestRetrievalUploaderScoping` | - [ ] |
| 10 | uploader-scoped-retrieval | Every chat answer channel enforces the rule | An aggregate over the relational channel is scoped | Given 2 requester-ingested and 3 other-human-ingested documents, when a `COUNT` question is answered, then the count reflects only visible documents despite aggregation, `GROUP BY`, and any row limit | integration test: `tests/test_sql_generator_uploader_scope.py` | - [ ] |
| 11 | uploader-scoped-retrieval | Every chat answer channel enforces the rule | Entity resolution is scoped | Given a person extracted only from another human's document, when a non-admin's message mentions that person, then no candidate is produced and the name is not presented as resolvable | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |
| 12 | uploader-scoped-retrieval | Every chat answer channel enforces the rule | Citations name only visible documents | Given a non-admin user and a tenant containing other humans' documents, when an answer's citations are assembled, then every citation names a document visible under the rule | end-to-end test: `tests/test_chat_uploader_isolation_end_to_end.py`; `tests/test_uploader_scope_channel_coverage.py` | - [ ] |
| 13 | uploader-scoped-retrieval | Listing and every answer channel agree in both directions | A listable document is answerable | Given a source-system `purpose='query'` document and a non-admin user, when a question would cite it, then it is citable and also listable by that user | integration test: `tests/test_document_visibility.py::test_a_listable_document_is_answerable` | - [ ] |
| 14 | uploader-scoped-retrieval | Listing and every answer channel agree in both directions | An unlistable document is unanswerable | Given another human's `purpose='query'` document, when a non-admin asks a matching question, then it appears in neither the answer, its citations, nor any count behind it, and is also not listable | end-to-end test: `tests/test_chat_uploader_isolation_end_to_end.py`; `tests/test_document_visibility.py::test_an_unlistable_document_is_unanswerable` | - [ ] |
| 15 | uploader-scoped-retrieval | Conversation-owned attachments remain visible to their own uploader | A user's own attachment stays retrievable in its conversation | Given a user who attached a file to a conversation, when they ask a question in that conversation answerable from it, then the attachment's content is retrievable | integration test: `tests/test_uploader_scope_attachments.py` | - [ ] |
| 16 | uploader-scoped-retrieval | Conversation-owned attachments remain visible to their own uploader | An attachment stays out of other conversations | Given that attachment, when the same user asks the same question in a different conversation, then its content is not retrievable | integration test: `tests/test_uploader_scope_attachments.py` | - [ ] |
| 17 | uploader-scoped-retrieval | An answer with no requesting user sees source-system content only | The widget cannot answer from a human upload | Given a tenant whose only matching content is human-uploaded, when a question is asked via the widget channel, then the answer does not draw on it and states it has no supporting source rather than answering unsourced | integration test: `tests/test_chat_uploader_scope_threading.py` (widget channel cases) | - [ ] |
| 18 | uploader-scoped-retrieval | An answer with no requesting user sees source-system content only | The widget answers from source-system content | Given a source-system `purpose='query'` document, when a matching question is asked via the widget, then the answer may draw on it | integration test: `tests/test_chat_uploader_scope_threading.py` (widget channel cases) | - [ ] |
| 19 | uploader-scoped-retrieval | An answer with no requesting user sees source-system content only | A missing requesting user does not widen the rule | Given a channel invoked with no requesting user identity, when the rule is evaluated, then every human-ingested document is excluded and no unscoped fallback occurs | integration test: `tests/test_chat_uploader_scope_threading.py` (widget channel cases) | - [ ] |
| 20 | uploader-scoped-retrieval | Narrowing is observable without recording tenant content | Narrowing is recorded as shape | Given an answer for a non-admin in a tenant holding other users' documents, when it is produced, then telemetry identifies channel and enumerated outcome and contains no filename, entity value, document text, or generated SQL | test + scan: `tests/test_uploader_scoping_telemetry.py`, `scripts/telemetry_scan.py` | - [ ] |
| 21 | uploader-scoped-retrieval | Narrowing is observable without recording tenant content | Metric labels are declared and finite | Given the uploader-scoping metric family, when its label keys and value sets are inspected, then each value set is finite and enumerated at declaration and no label is a user or tenant identifier | unit test: `tests/test_uploader_scoping_telemetry.py::test_metric_labels_are_declared_and_finite` | - [ ] |
| 22 | document-ingestion | Document visibility by ingesting actor (MODIFIED) | A user sees their own uploads | Given a non-admin who uploaded a document, when they list documents, then their own document is listed | integration test: `tests/test_document_visibility.py` | - [ ] |
| 23 | document-ingestion | Document visibility by ingesting actor (MODIFIED) | A user does not see another user's upload | Given two non-admins each having uploaded, when the first lists documents, then the second's document is not listed | integration test: `tests/test_document_visibility.py` | - [ ] |
| 24 | document-ingestion | Document visibility by ingesting actor (MODIFIED) | A system-ingested document is visible tenant-wide | Given a source-system document, when a non-admin lists documents, then it is listed | integration test: `tests/test_document_visibility.py` | - [ ] |
| 25 | document-ingestion | Document visibility by ingesting actor (MODIFIED) | Listing and retrieval agree | Given a source-system `purpose='query'` document and a non-admin, when a question cites it, then it is also listable by that user | integration test: `tests/test_document_visibility.py::test_a_listable_document_is_answerable` | - [ ] |
| 26 | document-ingestion | Document visibility by ingesting actor (MODIFIED) | Listing and retrieval agree in the other direction | Given another human's `purpose='query'` document, when a non-admin asks a matching question, then it is not cited and also not listable | integration test: `tests/test_document_visibility.py::test_an_unlistable_document_is_unanswerable` | - [ ] |
| 27 | document-ingestion | Document visibility by ingesting actor (MODIFIED) | Administrators are unaffected | Given a `tenant_admin`, when they list documents, then every non-deleted document is listed regardless of ingesting actor | integration test: `tests/test_document_visibility.py` | - [ ] |
| 28 | document-ingestion | Chunks carry their document's ingesting actor | A newly written chunk carries the actor | Given a human-ingested document processed to completion, when its chunks are written, then each records that document's ingesting actor kind and uploading user | integration test: `tests/test_chunk_metadata_ingest.py` | - [ ] |
| 29 | document-ingestion | Chunks carry their document's ingesting actor | A source-system document's chunks are marked as such | Given a source-system document processed to completion, when its chunks are written, then each chunk's recorded actor kind is the source-system value | integration test: `tests/test_chunk_metadata_ingest.py` | - [ ] |
| 30 | document-ingestion | Chunks carry their document's ingesting actor | Existing chunks are backfilled | Given chunks written before this change, when the migration has run, then every chunk carries its own document's actor and uploader and none has an absent actor kind | migration test: `tests/test_migration_chunk_uploader_backfill.py` | - [ ] |
| 31 | document-ingestion | Chunks carry their document's ingesting actor | The denormalized value agrees with the document | Given any chunk, when its denormalized actor and uploader are compared with its document's, then they are equal | migration test: `tests/test_migration_chunk_uploader_backfill.py` | - [ ] |
| 32 | retrieval-core | Retriever interface (MODIFIED) | DenseRetriever uses the hnsw index | Given chunks with embeddings and a fixed query, when `DenseRetriever.retrieve` runs, then it executes against the `hnsw` index and results rank by descending similarity | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 33 | retrieval-core | Retriever interface (MODIFIED) | rag_orchestrator retrieves via the Retriever interface | Given the orchestrator needs document context, when `_vector_source` executes, then it calls a `Retriever.retrieve` rather than `EmbeddingService.similarity_search` | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 34 | retrieval-core | Retriever interface (MODIFIED) | Retrieval excludes training-purpose chunks | Given training- and query-purpose chunks both matching, when `DenseRetriever.retrieve` runs, then no training-purpose chunk is returned | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 35 | retrieval-core | Retriever interface (MODIFIED) | A chat query cannot bypass the purpose restriction | Given training-purpose chunks, when `_vector_source` runs with any query text naming them, then the SQL still excludes them and no caller parameter overrides it | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 36 | retrieval-core | Retriever interface (MODIFIED) | Dense retrieval excludes another user's human-ingested chunks | Given two humans' matching `purpose='query'` documents, when `DenseRetriever.retrieve` runs for the first, then no result comes from the second's document | integration test: `tests/test_retrieval_foundation.py` (uploader scoping cases) | - [ ] |
| 37 | retrieval-core | Retriever interface (MODIFIED) | Sparse retrieval excludes another user's human-ingested chunks | Given a term in both documents, when `SparseRetriever.retrieve` runs for the first user, then no result comes from the second's document | integration test: `tests/test_retrieval_foundation.py` (uploader scoping cases) | - [ ] |
| 38 | retrieval-core | Retriever interface (MODIFIED) | Source-system chunks remain retrievable by every user | Given a source-system `purpose='query'` document, when any non-admin retrieves with a matching query, then its chunks may be returned | integration test: `tests/test_retrieval_foundation.py` (uploader scoping cases) | - [ ] |
| 39 | retrieval-core | Retriever interface (MODIFIED) | metadata_filter cannot widen the uploader restriction | Given another human's document, when `retrieve` runs for a non-admin with `metadata_filter` naming that document id, then the result is empty and no exception is raised | integration test: `tests/test_retrieval_foundation.py` (uploader scoping cases) | - [ ] |
| 40 | retrieval-core | Retriever interface (MODIFIED) | An administrator is unscoped by the uploader restriction | Given documents from several humans, when retrieval runs for a `tenant_admin`, then results may come from any of them | integration test: `tests/test_retrieval_foundation.py` (uploader scoping cases) | - [ ] |
| 41 | retrieval-core | Retriever interface (MODIFIED) | SparseRetriever returns full-text matches | Given chunks containing an exact term, when `SparseRetriever.retrieve` runs with it, then the containing chunk is returned, ranked by `ts_rank` descending | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 42 | retrieval-core | Retriever interface (MODIFIED) | SparseRetriever returns no error on zero matches | Given chunks with no overlap with the query, when `SparseRetriever.retrieve` runs, then the result is an empty list and no exception is raised | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 43 | retrieval-core | Retriever interface (MODIFIED) | HybridRetriever fuses dense and sparse results via RRF | Given a chunk matching both semantically and lexically, when `HybridRetriever.retrieve` runs, then it ranks at or near the top and the fused list holds at most `top_k` | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 44 | retrieval-core | Retriever interface (MODIFIED) | HybridRetriever includes dense-only matches when sparse search returns nothing | Given a semantically-matching chunk with no lexical overlap, when sparse returns zero and hybrid runs, then the fused list still includes that chunk | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 45 | retrieval-core | Retriever interface (MODIFIED) | metadata_filter restricts results to one document | Given chunks from two documents both matching, when `retrieve` runs with a `metadata_filter` naming one document id, then every result has that document id and none comes from the other | regression: `tests/test_retrieval_foundation.py` (pre-existing scenarios, must still pass) | - [ ] |
| 46 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied (MODIFIED) | Tool schemas expose no tenancy parameters | Given every registered tool, when `args_schema.properties` keys are inspected, then none is `schema`, `tenant_id`, `tenant`, or `purpose` | unit + integration test: `tests/test_retrieval_tools.py` | - [ ] |
| 47 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied (MODIFIED) | Tool schemas expose no uploader parameters | Given every registered tool, when `args_schema.properties` keys are inspected, then none names the requesting user, uploading user, or ingesting actor | unit + integration test: `tests/test_retrieval_tools.py` | - [ ] |
| 48 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied (MODIFIED) | Tool queries the context's schema only | Given two tenant schemas with matching chunks, when a tool runs with a `ToolContext` for the first, then every result originates from the first schema and none from the second | unit + integration test: `tests/test_retrieval_tools.py` | - [ ] |
| 49 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied (MODIFIED) | Purpose restriction survives the tool layer | Given training- and query-purpose chunks matching, when any document retrieval tool runs with any arguments, then no training-purpose chunk is returned | unit + integration test: `tests/test_retrieval_tools.py` | - [ ] |
| 50 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied (MODIFIED) | Uploader restriction survives the tool layer | Given matching chunks from another human's document, when any document retrieval tool runs for a non-admin with any arguments, then no result comes from that document | unit + integration test: `tests/test_retrieval_tools.py` | - [ ] |
| 51 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied (MODIFIED) | A document scope cannot reach another user's document | Given another human's document, when a tool is invoked with a `document`-type scope naming its id, then no results come from it and no argument-validation error is raised | unit + integration test: `tests/test_retrieval_tools.py` | - [ ] |
| 52 | chat-api | The requesting user reaches every answer channel as execution state | The streaming route scopes identically to the JSON route | Given another human's matching document, when the same question is asked through the JSON route and the streaming route, then neither answer draws on it | end-to-end test: `tests/test_chat_uploader_isolation_end_to_end.py` | - [ ] |
| 53 | chat-api | The requesting user reaches every answer channel as execution state | Interleaved users do not leak scope | Given two non-admins' requests running concurrently in one process, when each reaches retrieval, then each applies the rule for its own user and no orchestrator attribute holds either identity | integration test: `tests/test_chat_uploader_scope_threading.py` | - [ ] |
| 54 | chat-api | The relational answer channel is uploader-scoped | A row-returning statement excludes another user's documents | Given entities from the requester's and another human's documents matching a question, when the relational channel answers, then every row derives from visible documents | integration test: `tests/test_sql_generator_uploader_scope.py` | - [ ] |
| 55 | chat-api | The relational answer channel is uploader-scoped | An aggregate is scoped before aggregation | Given that tenant, when the statement is a `COUNT` projecting no document id, then the count excludes the other human's documents without post-execution row filtering | integration test: `tests/test_sql_generator_uploader_scope.py` | - [ ] |
| 56 | chat-api | The relational answer channel is uploader-scoped | A row limit does not defeat the scope | Given invisible rows that would rank ahead under the generated ordering, when the statement carries a trailing limit, then the result contains only visible rows and is not empty merely because invisible rows consumed the limit | integration test: `tests/test_sql_generator_uploader_scope.py` | - [ ] |
| 57 | chat-api | The relational answer channel is uploader-scoped | Every scopeable relation is reached | Given the relations the generator may reference over the platform tenant schema, when the uploader scope is applied to a statement referencing each, then every reference is rewritten and an unreachable relation causes rejection rather than execution | integration test: `tests/test_sql_generator_uploader_scope.py` | - [ ] |
| 58 | chat-api | The relational answer channel is uploader-scoped | Uploader and conversation scopes compose | Given a statement over a relation reachable by both scopes, when it is prepared for execution, then both constraints are present and neither replaced the other | integration test: `tests/test_sql_generator_uploader_scope.py` | - [ ] |
| 59 | chat-api | Entity resolution is uploader-scoped | Another user's person is not a candidate | Given a person extracted only from another human's document, when a non-admin's message mentions them, then resolution produces no candidate | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |
| 60 | chat-api | Entity resolution is uploader-scoped | A disambiguation prompt names only visible people | Given two people sharing a first name, one from each user's document, when the requester's message mentions that name, then any disambiguation names only the person from the requester's document | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |
| 61 | chat-api | Entity resolution is uploader-scoped | The user's own people still resolve | Given a person extracted from the requester's own document, when their message mentions them, then resolution produces that candidate as before this change | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |

| 62 | chat-api | Entity resolution is conversation-scoped | An attachment's person resolves inside its own conversation | Given a person extracted from a file attached to one conversation, when its uploader mentions them in that same conversation, then resolution produces that candidate | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |
| 63 | chat-api | Entity resolution is conversation-scoped | An attachment's person does not resolve in another conversation | Given that person, when the same user mentions them in a different conversation, then resolution produces no candidate from the attached document | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |
| 64 | chat-api | Entity resolution is conversation-scoped | Tenant-library people stay resolvable from inside a conversation | Given a person extracted from a document owned by no conversation, when its uploader mentions them from inside any conversation, then resolution produces that candidate | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |
| 65 | chat-api | Entity resolution is conversation-scoped | Both rules apply together | Given an attachment, an own library document, a source-system document and a colleague's document each holding a person sharing a first name, when the user mentions that name inside the conversation, then candidates come from the first three and never the colleague's | integration test: `tests/test_entity_resolution_uploader_scope.py` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Single predicate definition (Decision 1) | unit test: `tests/test_document_visibility_rule.py` | Grep for the literal condition (`ingested_by_kind`, `uploaded_by`) across `src/`. Every occurrence outside the shared definition module, the migration, and the chunk-write path is a finding. Confirm the listing path was changed to reference the shared definition rather than left as its own copy. |
| 2 | Fail-closed on absent identity (Decision 6) | unit test: `tests/test_document_visibility_rule.py` | Read the predicate's own branch for `None`/absent user. Confirm it excludes all human-ingested content rather than returning an empty or always-true clause. Verify scenario 19 fails when the branch is inverted. |
| 3 | Relational scope applied on request rather than always | unit test: `tests/test_document_visibility_rule.py` | Read the call site in the execution path: the uploader scope must be unconditional, with no `if` on a resolved scope. Confirm a statement with no document scope still emerges rewritten. |
| 4 | Composition replaced instead of conjoined | unit test: `tests/test_document_visibility_rule.py` | Inspect a rewritten statement over a both-scopes relation and confirm both predicates appear joined by `AND`. Scenario 58 must fail if either is removed. |
| 5 | Backfill leaves rows unmarked | guard test: `tests/test_document_visibility_rule.py::test_predicate_has_one_definition` | Run the migration against a schema with pre-existing chunks. Assert zero rows with NULL `ingested_by_kind` afterwards, per scenario 30. Confirm the migration iterates provisioned schemas the way migrations 022/034/040/041 do. |
| 6 | Telemetry carries tenant content | unit test: `tests/test_retrieval_tools.py::test_tool_schemas_expose_no_uploader_keys` | Run `scripts/telemetry_scan.py`. Read every added log call and metric declaration: structured fields only, enumerated label values, no user or tenant identifier as a label. |
| 7 | `hnsw` recall silently degrades | integration test: `tests/test_uploader_scope_channel_coverage.py` | Run the minority-uploader fixture: a user owning ~10% of matching chunks must still receive `top_k` results when that many exist. A shortfall is a finding, not a tuning preference. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation (topology partially superseded by ADR-017) | Schema-per-tenant isolation enforced below the caller | Uploader scoping is a within-tenant rule that composes with, and never substitutes for, tenant isolation | Run scenario 48: a `ToolContext` for one schema must return nothing from a second schema even when the requesting user id exists in both |
| ADR-007 Chatbot Architecture | The answer pipeline spans pgvector search and generated SQL | A rule on one channel leaves the other open; both must enforce | Confirm scenarios 9, 54–58 pass; grep the chat service for reads of `document_chunks`, `document_entities`, `document_text_spans` and confirm each goes through a `Retriever` or the scope rewrite |
| ADR-011 Conversation-Scoped Chat Attachments | Attachments are conversation-owned `documents` rows | Attachments stay retrievable for their own uploader in their own conversation | Run scenarios 15 and 16 |
| ADR-014 Mandatory Conversation-Scoped Retrieval | Scoping is caller-invisible, denormalized onto chunks, applied to every channel, never model-selected | The uploader rule follows the same pattern and conjoins with the conversation rule rather than replacing it | Run scenarios 51 and 58; confirm the guard test over the SQL whitelist covers the uploader scope-column map as it covers the conversation map |
| ADR-016 Contract-Grounded External SQL Generation | External statements run against the tenant's own published contract | The external channel is out of scope and must not be altered | Confirm `src/chat_api/services/external_sql_generator.py` and `src/shared/external_postgres/` are unmodified in the diff |
| ADR-017 Tenant-Owned PostgreSQL Data Plane | `documents` may resolve to a tenant-owned database | The predicate must be expressible inside the tenant schema, with no join to `public.*` | Capture the SQL executed by each scoped channel and assert no statement names a `public.` control-plane table, mirroring the Design-D10 discipline in `tests/test_document_visibility.py` |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] **End-to-end isolation** (rows 9, 12, 14, 52): test output from `tests/test_chat_uploader_isolation_end_to_end.py`, which drives the real `/api/v1/chat` and `/api/v1/chat/stream` endpoints with a signed JWT against a tenant holding two business users' documents. Record alongside it the mutation check: with the rule's admin branch forced permissive, 4 of these 7 tests fail — evidence the suite can actually detect a regression rather than passing vacuously.

- [ ] Scenarios 1–5 (one rule, stated once): test output for the shared-predicate tests, plus the grep result showing no channel restates the literal condition
- [ ] Scenarios 6–8 (authenticated state only): test output showing tool schemas expose no uploader keys and that arguments and question text cannot widen the rule
- [ ] Scenarios 9–12 (every channel enforces): test output covering retrieval, the relational aggregate, entity resolution, and citation assembly
- [ ] Scenarios 13–14 (both directions agree): test output for the paired listing/answering assertions, including the previously untested direction
- [ ] Scenarios 15–16 (attachments): test output showing an attachment is retrievable in its own conversation and not in another
- [ ] Scenarios 17–19 (no requesting user): test output for the widget channel declining on human-uploaded content and answering from source-system content
- [ ] Scenarios 20–21 (telemetry): `scripts/telemetry_scan.py` output plus the metric-declaration test
- [ ] Scenarios 22–27 (listing visibility, MODIFIED): test output from the extended `tests/test_document_visibility.py`
- [ ] Scenarios 28–31 (chunk denormalization): test output for chunk writes and a migration run against a schema with pre-existing chunks
- [ ] Scenarios 32–45 (retriever interface, MODIFIED): full test output for the retrieval suite, showing the pre-existing scenarios still pass alongside the new uploader ones
- [ ] Scenarios 46–51 (tool layer): test output for the tool-schema and tool-invocation assertions
- [ ] Scenarios 52–53 (execution state): test output for JSON/streaming parity and the interleaved-users case
- [ ] Scenarios 54–58 (relational channel): test output including the aggregate, the row-limit case, the relation-coverage guard, and scope composition
- [ ] Scenarios 59–61 (entity resolution): test output for the candidate, disambiguation, and unchanged-own-people cases
- [ ] Scenarios 62–65 (entity resolution, conversation scope): test output showing an attachment's person resolves only inside its own conversation, and that both rules hold together

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — grep for the literal predicate across `src/`; every hit accounted for
- [ ] Risk 2 mitigation confirmed — absent-user branch read and shown to exclude human-ingested content
- [ ] Risk 3 mitigation confirmed — uploader scope shown to be unconditional at its call site
- [ ] Risk 4 mitigation confirmed — a rewritten statement inspected and both predicates shown conjoined
- [ ] Risk 5 mitigation confirmed — post-migration query shows zero NULL actor kinds across provisioned schemas
- [ ] Risk 6 mitigation confirmed — telemetry scan clean; added log calls and metric labels reviewed
- [ ] Risk 7 mitigation confirmed — minority-uploader recall measured with the result recorded, not assumed

### Rollout Risks To Confirm Before Archive

- [ ] Tenants relying on tenant-wide chat answers identified and notified; `tenant_admin` and source-system ingestion documented as the supported alternatives
- [ ] Widget-running tenants identified and the fail-closed behaviour (Decision 6) confirmed as intended with the change's approver
- [ ] Decision recorded on whether persisted `chat_messages` history is left unfiltered (assumed yes) and whether entity resolution also gains the conversation predicate (design Open Questions)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | unit test: `tests/test_document_visibility_rule.py` | |
| 2 | | | unit test: `tests/test_document_visibility_rule.py` | |
| 3 | | | unit test: `tests/test_document_visibility_rule.py` | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** uploader-scoped-chat-retrieval
**Proposal:** `openspec/changes/uploader-scoped-chat-retrieval/proposal.md`
**Spec files reviewed:**
  - specs/uploader-scoped-retrieval/spec.md
  - specs/document-ingestion/spec.md
  - specs/retrieval-core/spec.md
  - specs/retrieval-tools/spec.md
  - specs/chat-api/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
