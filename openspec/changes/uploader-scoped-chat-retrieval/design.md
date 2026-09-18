## Context

The platform records an ingesting actor on every document and uses it to scope the Documents library: a non-administrative user lists only their own human-ingested documents, plus everything a source system ingested (`list_documents`, `src/document_service/api/v1/documents.py:262-271`). The `document-ingestion` spec states that this exists "so that document listing and chat retrieval agree on what a user may see", and its existing scenarios verify one direction only — that a source-system document the user *can* list is also citable.

The other direction was never built. `DenseRetriever.retrieve` (`src/shared/retrieval/retriever.py:106`) and `SparseRetriever` restrict on `purpose='query'`, the ADR-014 conversation clause and the CAP-3 hidden-document clause. No uploader predicate exists anywhere in `src/chat_api`, `src/shared/retrieval` or `src/analytics_service`. In the platform's own HR-screening scenario, one recruiter's question returns another recruiter's candidate — name, skills and a quoted resume snippet — from a document the asker cannot see listed.

The shape of the fix is already established by ADR-014, which faced the identical problem for conversation ownership one layer down: a caller-invisible predicate compiled into every retrieval channel, derived from authenticated request state, with the model-facing `scope` argument able to narrow but never widen. This design adds a second predicate of the same kind, and deliberately reuses ADR-014's mechanisms rather than inventing parallel ones.

Three constraints shape the work. Chat answers reach document data through more channels than retrieval — the relational SQL path and entity resolution both read platform tables directly. The vector path cannot afford a join between the `hnsw` index scan and ranking, which is why ADR-014 denormalized `conversation_id` onto chunks. And ADR-017's tenant-owned data plane means `documents` may resolve to a different database from the control-plane tables, so any predicate must be expressible within the tenant schema alone.

## Goals / Non-Goals

**Goals:**

- One uploader-visibility rule, defined once, applied identically by document listing and by every chat answer channel over platform-owned tenant data.
- Enforcement derived from authenticated request state, unreachable and unwidenable from an LLM argument, a generated statement, a `metadata_filter`, or a caller-supplied `scope`.
- Both directions of the listing/answering agreement verified, closing the untested half of the existing `document-ingestion` requirement.
- Source-system content stays tenant-wide, so the Azure Blob sync integration is unaffected.
- The vector path keeps its `hnsw` index plan.
- A defined, fail-closed answer for a channel with no authenticated end user.

**Non-Goals:**

- The external PostgreSQL channel (ADR-016). It runs against the tenant's own database, which has no platform `documents` table and no ingesting actor; the rule is not expressible there and the data is not platform-owned.
- `src/analytics_service`. It serves portal dashboards, not chat answers. Its visibility question is real but separate, and folding it in here would widen this change into the portal's analytics surface.
- Retroactive filtering of persisted `chat_messages`. History answered under the old rule is left as written.
- Any per-tenant configuration switch for the rule (see Decision 5).
- Moving enforcement to PostgreSQL Row-Level Security (see Open Questions).
- The citation-chip document viewer. It depends on this change's outcome and is specified separately.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation (partially superseded by ADR-017 on topology only; schema-per-tenant and control-plane rules in force) | Schema-per-tenant isolation, enforced below the caller | Uploader scoping composes with tenant isolation and never replaces it; it is a within-tenant rule only |
| ADR-007 Chatbot Architecture | The answer pipeline spans pgvector document search and generated SQL | A rule applied to one channel leaves the other open; every channel must be covered |
| ADR-011 Conversation-Scoped Chat Attachments | Attachments are `documents` rows owned by one conversation, hard-deleted with it | Attachments are already uploader-owned; the new predicate must admit them for their own uploader |
| ADR-014 Mandatory Conversation-Scoped Retrieval | Scoping is a caller-invisible guardrail applied to every channel, denormalized onto chunks, never a model-selected argument | This design follows the same pattern, reuses the same mechanisms, and must compose with the conversation predicate as a conjunction |
| ADR-016 Contract-Grounded External SQL Generation | External statements run against the tenant's published contract on their own database | The external channel is out of scope; its data is not platform-owned |
| ADR-017 Tenant-Owned PostgreSQL Data Plane | `documents` may live in a tenant-owned database, separate from control-plane tables | The predicate must be expressible inside the tenant schema; no join to `public.*` control-plane tables |

## Decisions

### Decision 1: One shared predicate definition, not one per channel

**Choice:** Define the rule once — a single module exposing the visibility condition and the SQL fragments each channel needs — and have the listing path, the retrievers, the SQL scope rewrite and entity resolution all reference that definition. Place it in `src/shared/` so both `document_service` and `chat_api` can import it without either depending on the other.

**Rationale:** The bug being fixed is precisely that two places implemented "what a user may see" and only one of them was right. Fixing it by writing the condition a fourth and fifth time reproduces the failure mode at larger scale. A shared definition also makes the agreement testable as a property — the listing predicate and the retrieval predicate are the same object — rather than as two assertions that happen to match today.

**Alternatives considered:**
- Restate the predicate in each channel, as the conversation clause is today (`_conversation_clause` in the retriever and `_conversation_predicate` in the SQL generator are two implementations of one rule, kept in step by a comment). Ruled out: that duplication is already a latent defect, and this change would add three more copies.
- Put the definition in `document_service` and import it from `chat_api`. Ruled out: it would make the chat service depend on the document service package, which the current layering avoids; `src/shared/retrieval` exists precisely because `src/shared` never imports `src.chat_api`.

### Decision 2: Denormalize the ingesting actor onto `document_chunks`

**Choice:** Add `uploaded_by` and `ingested_by_kind` to `document_chunks`, written at chunk-write time from the parent document alongside `purpose` and `conversation_id`, and backfilled for existing rows.

**Rationale:** This is the same trade ADR-014 made for `conversation_id`, for the same reason, and its alternatives table already rules out the join: it "adds a join between the `hnsw` index scan and the vector ranking on the hot path, and cannot be expressed in the single-table inline-view rewrite the SQL path uses". Both facts are immutable after ingestion — a document is never reassigned to a different uploader — so the denormalized copy cannot drift. Two columns rather than a precomputed boolean, because the visible/not-visible answer depends on *which* user is asking and cannot be materialized per row.

**Alternatives considered:**
- Join `document_chunks` to `documents` in the retriever SQL. Ruled out by ADR-014's stated rationale, unchanged here.
- A single denormalized "visible to everyone" boolean. Ruled out: it collapses the two facts into one and loses the uploader identity the predicate needs; a source-system document is visible to all, but a human-ingested one is visible to exactly one user, which no row-level boolean can express.
- Materialized per-user visibility table. Ruled out: quadratic in users × documents, and it would need maintaining on every user and document change to answer a question two columns answer directly.

### Decision 3: The relational channel reuses the inline-view rewrite

**Choice:** Add `apply_uploader_scope` beside `apply_conversation_scope` in `src/chat_api/services/sql_generator.py`, using the same relation-reference rewrite, the same scope-column map shape, and the same "applies to every statement, not on request" discipline. Relations carrying the denormalized columns are constrained directly; the rest are reached with `document_id IN (SELECT id FROM documents WHERE <predicate>)`, exactly as the conversation scope already does.

**Rationale:** The rewrite exists because an appended `WHERE` and a post-execution row filter both fail the cases that matter: the scope has to survive aggregation, `GROUP BY` and `LIMIT`. A `COUNT(*)` over `document_entities` projects no `document_id` to filter afterwards, and a limit-truncated result filtered after execution turns into a wrongly-empty answer — a failure this codebase has already had once and fixed this way. Reusing the mechanism means the uploader scope inherits those properties instead of rediscovering them.

**Alternatives considered:**
- Pass the requesting user into the prompt and ask the generator to filter. Ruled out for the reason ADR-014 gives: an isolation guarantee in model-controlled data is not a guarantee.
- Filter returned rows after execution. Ruled out: breaks under aggregation and under `LIMIT`, as above.

### Decision 4: Thread the requesting user exactly where `conversation_id` is threaded

**Choice:** Carry the user's id and role from `request.state` through the orchestrator call, into graph state, onto `ToolContext`, following the existing `conversation_id` path end to end; and add the corresponding keys to `FORBIDDEN_ARG_KEYS` in `src/shared/retrieval/tools/base.py`.

**Rationale:** That path is already established, already carries an isolation-critical value, and already satisfies the "Per-request authorization context isolation" requirement by keeping request-scoped values out of the shared orchestrator instance. Inventing a second mechanism for a second isolation value would double the surface where a future call site can forget one.

**Alternatives considered:**
- Decode the user from the JWT inside the retriever. Ruled out: `src/shared/retrieval` does not and should not know about the auth scheme, and it would make every retriever call site depend on a token being present.
- A context variable (`contextvars`). Ruled out: implicit ambient state is exactly what the per-request isolation requirement exists to prevent, and it would be invisible at the call sites that must be audited.

### Decision 5: One rule, no per-tenant switch

**Choice:** Ship a single rule with no configuration flag.

**Rationale:** A configurable isolation boundary is one that can be misconfigured back into the gap being closed, and the default would have to be chosen for existing tenants either way. The tenant-wide behaviour remains reachable by legitimate means — grant the users `tenant_admin`, or ingest shared corpora through a source system, which is what the source-system exemption is for. Adding a flag later is cheap; removing one after tenants depend on it is not.

**Alternatives considered:**
- A per-tenant `chat_visibility` setting on the integration profile. Ruled out for now, and recorded in the proposal's Open Questions rather than decided silently, because it is genuinely arguable for single-team tenants.

### Decision 6: No requesting user means source-system content only

**Choice:** The embeddable widget channel (`src/chat_api/api/v1/public.py`), which answers under a tenant service token with no end user, is treated as "no human" — it may answer only from documents no human ingested.

**Rationale:** The absent-identity case has to resolve to something, and the two candidates are "see everything" and "see nothing human". A public, embeddable surface that can quote a staff member's uploaded resume to an anonymous visitor is the more damaging failure, and it is the failure the caller cannot detect. Fail-closed also matches how the conversation rule already treats a missing conversation: "with no conversation in context, only null-owned chunks are admitted".

**Alternatives considered:**
- Exempt the widget. Ruled out: it becomes a bypass channel for the rule, reachable by anyone with the widget key.
- Give the widget an unscoped service identity. Ruled out: same outcome as exempting it, with the additional problem of an identity that looks authorized in logs.

## Risks / Trade-offs

- [The channel enumeration is now two rules deep, and ADR-014 already named this as its main liability: "a future channel that reaches `document_chunks` or `documents` without going through a `Retriever` or through the SQL scope rewrite would not inherit the rule"] → Keep the scope-column map beside the query whitelist and extend the existing guard test so a whitelisted relation missing from the uploader map fails the build, matching how conversation scoping is guarded today. Raise RLS explicitly under Open Questions rather than letting the enumeration grow silently.
- [**Entity resolution is an unenumerated channel that ADR-014 missed.** `src/chat_api/services/entity_resolver.py:165,185` reads `document_entities` with neither the conversation predicate nor any uploader predicate, so conversation-owned attachment entities are already visible across conversations — a live gap in a guarantee ADR-014 states as met] → This change adds the uploader predicate to those two reads regardless. Whether to also add the conversation predicate in the same lines is raised in Open Questions; it is close to free here and the alternative is leaving a known ADR-014 hole open with a comment next to it.
- [A selective predicate on an approximate `hnsw` index can change effective top-k recall: the index returns its nearest neighbours and the filter removes some, so a user whose documents are a small fraction of the tenant's may get fewer results than `top_k` even when more matches exist] → Measure before shipping, with a tenant fixture where the requesting user owns a minority of matching chunks; if recall degrades, raise the pre-filter candidate count for the dense path rather than dropping the predicate. This is recorded as a verification risk with a measured pass criterion, not an assumption.
- [Tenants relying on tenant-wide chat answers lose results the day this deploys, with no warning and no diagnosis path — the assistant simply knows less] → Ship the narrowing metric before the behaviour, so the effect is observable per channel; announce to affected tenants; document `tenant_admin` and source-system ingestion as the supported ways to keep a shared corpus shared.
- [Widget deployments answering from staff uploads go quiet (Decision 6)] → The most user-visible break in the change. Called out as BREAKING in the proposal, and the guardrail's existing "no supporting source" path means the widget declines rather than answering unsourced.
- [The backfill rewrites every `document_chunks` row in every tenant schema] → Add the columns nullable, backfill in batches per schema, then enforce; follow the pattern migrations 022/034/040/041 established for the same table, and make the migration re-runnable.
- [Historical conversations keep citations to documents the user may no longer open, so the later document-viewer change will show denials on old messages] → Accepted and stated; the viewer change specifies the denial state rather than this change rewriting history.

## Migration Plan

1. Land the shared predicate definition and the metric with no call sites changed. Nothing behaves differently; the definition is exercised only by its own tests.
2. Migration: add `uploaded_by` and `ingested_by_kind` to `document_chunks` on `tenant_template` and every provisioned tenant schema, nullable; backfill from `documents` per schema in batches; assert no row is left with an absent actor kind. Re-runnable, following migrations 022/034/040/041.
3. Chunk writing denormalizes both columns, so rows written between the backfill and the cutover are already correct.
4. Enforce, channel by channel, each behind its own tests: retrievers, then the SQL rewrite, then entity resolution. Each step is independently revertable.
5. Thread the requesting user through the orchestrator and `ToolContext`; extend `FORBIDDEN_ARG_KEYS`.
6. Measure `hnsw` recall against the minority-uploader fixture and decide the dense candidate count.
7. **Rollback:** revert steps 4–5 to restore prior answer behaviour; the added columns and the backfill are additive and can stay. No data is destroyed at any step, and nothing outside chat answering changes, so rollback is a code revert rather than a data migration.

## Operating the rule after it ships

The rule narrows what chat can answer, so a tenant that legitimately wants a pooled
corpus needs a supported way to keep one. There are two, and both are existing mechanisms
rather than anything added here:

- **Ingest shared content through a source system.** Anything whose ingesting actor is
  not a human stays visible to every user of the tenant. This is what the source-system
  exemption is for, and it is why the Azure Blob sync integration is unaffected: synced
  documents remain tenant-wide. A tenant with a shared library of reference material
  should be delivering it this way, not by having one person upload it through the
  portal.
- **Grant `tenant_admin`.** An administrator is unscoped in chat exactly as they already
  are in the Documents library.

What is *not* supported is the previous behaviour — every user's uploads answerable by
every other user — because that is the gap this change closes. A tenant relying on it
will see fewer results the day this deploys, with no error and no warning in the answer
itself. That is why the narrowing metric ships first (see the Migration Plan): it makes
the effect visible per channel before the enforcement is switched on, so affected tenants
can be identified and told rather than discovering it through a wrong answer.

A single recruiter uploading resumes and asking about them is unaffected, which is the
common case. The case that changes is two people uploading into one tenant and expecting
to see each other's documents — which the Documents library already refused to show them.

## Open Questions

- **Is this the change that should move enforcement to Row-Level Security?** ADR-014 rejected RLS "for now" and named it "the intended successor" should channel enumeration become unmanageable, while noting it is a platform-wide posture change warranting its own change and ADR. This design adds a second enumerated rule across the same channels and uncovers a third channel ADR-014's enumeration missed — which is evidence that the threshold ADR-014 described is being approached. Recommendation: proceed with enumeration here, because RLS would govern ingestion, extraction, analytics and hard delete as well and cannot be scoped to this fix, but record the pressure so the successor ADR has the evidence. The `adr` step should decide whether this warrants an ADR that depends on ADR-014 or one that supersedes it.
- ~~**Should entity resolution also gain the conversation predicate in this change?**~~ **Resolved: yes.** Both predicates are applied to both `document_entities` reads in `entity_resolver.py`. The conversation predicate is built by a local `_conversation_predicate_via_document` helper rather than the shared uploader module, because it implements ADR-014's rule, not this change's — the two are conjoined, and neither relaxes the other. This closes a gap in ADR-014's channel enumeration: that path reads `document_entities` outside both the `Retriever` implementations and the generated-SQL rewrite, so a person extracted from a file attached in one conversation resolved from every other conversation of the tenant, while the ADR stated the guarantee as met. Verified by `tests/test_entity_resolution_uploader_scope.py`.
- **Is fail-closed correct for the widget (Decision 6)?** Confirmed assumption, not a settled decision; it is the most consequential behaviour change here for any tenant running the widget.
- **Should the rule be tenant-configurable (Decision 5)?** Carried from the proposal. Cheap now, expensive later.
