## Context

`annotation_service` currently offers one pre-labeling mechanism: `prelabel_document` (`src/annotation_service/api/v1/spans.py`) does a deterministic, synchronous, case-insensitive substring scan of a document's text against each entity type's `examples` list, with longest-match-wins overlap resolution. Results are written to `{tenant_schema}.suggested_spans`, replacing any prior suggestions for that document. A separate endpoint promotes a suggested span into a confirmed `spans` row — this is the existing human-approval gate, and it is not being changed.

This change adds a second suggestion source — an LLM — that a tenant can opt into by supplying QA-pair context on their entity types. It must produce suggestions into the same table, respect the same tenant-schema isolation (ADR-001), and run asynchronously rather than blocking the request thread, following the precedent set by ADR-006 for asynchronous task execution via Celery/RabbitMQ.

## Goals / Non-Goals

**Goals:**
- Generate LLM-based `suggested_spans` for a document that are grounded (verified to exactly match document text) and constrained to the tenant's configured entity types.
- Keep the existing keyword pre-labeling path fully intact and unaffected.
- Run the LLM call asynchronously, off the request thread.
- Cache results so repeated calls on unchanged input cost nothing.
- Record provenance (`source`) on every suggested span, old and new.

**Non-Goals:**
- No UI/frontend work (change 2).
- No changes to `training_service`, BIO tag export, or model training (changes 3–4).
- No BERT-based suggestion generation (change 5).
- No automatic or scheduled retraining (change 6 — and per the project's decision, that change will be human-gated via the existing `training-approval` flow regardless).
- No new entity types are ever created by the LLM — only types already defined via `entity-config` may be suggested.
- No resolution of the PII/data-residency open question from proposal.md — this design assumes an approved LLM provider will be configured per-tenant or globally by the time this is implemented, but does not pick one.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant isolation via separate PostgreSQL schemas, enforced at API/connection/ORM layers | The new endpoint, its Celery task, and the `suggested_spans` write path must resolve `tenant_<uuid>` schema the same way every other `annotation_service` endpoint does (`_schema(tenant_id)` from `get_tenant_id(request)`); the LLM call itself must only ever see one tenant's document/config at a time. |
| ADR-006 | Async task execution via Celery + RabbitMQ, GPU workers on K8s for training specifically | Establishes Celery/RabbitMQ as this system's pattern for "must not block the API." This design follows that pattern for the LLM call, but on a lightweight (non-GPU) queue — an LLM API call is I/O-bound, not GPU-bound, so it must not share the GPU-backed `training.jobs` queue/node pool. |
| ADR-009, ADR-010 | Training hyperparameters and dataset-readiness thresholds | Not applicable to this change — these govern `training_service`, which this change does not touch. Referenced here only to confirm they don't apply, since they partially supersede ADR-006. |

## Decisions

### Decision 1: Separate endpoint, not a parameter on the existing one

**Choice:** Add `POST /api/v1/documents/{doc_id}/prelabel/llm` (or equivalent) as a new endpoint, rather than adding a `source=llm` query param to the existing `/prelabel`.

**Rationale:** The existing endpoint is synchronous and returns the suggestions in its response body. The LLM path is asynchronous (Decision 3) and must return a job handle instead. Overloading one endpoint with two different response contracts (sync body vs. async job handle) based on a param is a worse API than two endpoints with distinct, honest contracts. It also means this change cannot regress the existing endpoint's behavior or tests by construction.

**Alternatives considered:**
- Single endpoint with a `mode` param — rejected: forces a conditional response shape, and risks touching code paths change 1 is meant to leave alone.
- Making the existing endpoint itself async — rejected: out of scope; it works synchronously today and nothing requires changing that.

### Decision 2: Extraction, verification, and storage are three separate steps

**Choice:** The pipeline is: (1) LLM call returns `{entity_type, quote}` pairs only — no offsets; (2) a pure backend function grounds each quote against the document text and computes offsets; (3) grounded results are written to `suggested_spans`. Step 2 has no LLM involvement and is independently unit-testable.

**Rationale:** LLMs are unreliable at counting characters/tokens, so asking them for offsets directly produces silently wrong spans. Separating "what does the LLM think is an entity" from "where exactly is it" makes the grounding logic (the part most likely to have edge-case bugs) plain, deterministic Python that can be tested without ever calling a real LLM.

**Alternatives considered:**
- Ask the LLM to return character offsets directly — rejected: offsets from LLMs are frequently off-by-a-few and unverifiable without doing the same text search anyway, so it adds risk without removing work.
- Ask the LLM to return token indices against a pre-tokenized document — rejected: couples the prompt to a specific tokenization scheme and doesn't avoid the verification step either; verifying a quote against raw text is simpler than verifying token-index alignment.

### Decision 3: Full-document extraction prompt, not QA-answering

**Choice:** Regardless of what QA pairs a tenant configured, every LLM call instructs the model to find *all* spans of *all* the tenant's configured entity types in the given document — using the QA pairs only as few-shot examples of the type of value expected, not as questions to answer for that specific document.

**Rationale:** If the LLM only answered the configured questions, any entity type not covered by a QA pair — or any additional occurrence of a covered type elsewhere in the document — would go unsuggested. Downstream, `export.py`'s BIO tagging marks every token not covered by a span as `O` ("not an entity"). Partial coverage would therefore actively teach a future model that real entities are not entities. This decision is a direct requirement, not just an optimization — see the `llm-prelabeling` spec's extraction-scope requirement.

**Alternatives considered:**
- QA-answering per configured question, run once per question — rejected for the poisoning reason above, and it would also multiply LLM calls per document by the number of QA pairs.

### Decision 4: Grounding failure means "drop", never "best effort"

**Choice:** If a returned quote cannot be located in the document text via exact (case-insensitive) match, that suggestion is discarded entirely. No fuzzy matching, no nearest-match fallback, no partial-offset guess.

**Rationale:** A wrong offset is worse than no suggestion — it either corrupts a training label silently or wastes reviewer time on a suggestion that doesn't correspond to what it claims to point at. This also directly prevents the "computed answer that doesn't literally appear in the text" failure mode identified during design discussion (e.g. an LLM inferring "5 years" from date ranges rather than quoting text).

**Alternatives considered:**
- Fuzzy/approximate matching (e.g. edit-distance) to recover near-misses — rejected for v1: adds non-determinism and a new class of "confidently wrong" spans; can be revisited later with its own spec and evaluation data once real failure rates are observed.

### Decision 5: Cache key is (content hash, entity-config version), not per-request

**Choice:** Before invoking the LLM, compute a cache key from the document's content hash and the tenant's current entity-type configuration (types + QA pairs) version. If a cached, still-valid result exists, return/store it without calling the LLM again.

**Rationale:** Re-running pre-labeling on an unchanged document under an unchanged configuration is a common user action (e.g. clicking "suggest" again after reviewing) and should not cost another LLM call. Keying on configuration version (not just document hash) ensures a tenant adding a new QA pair or entity type invalidates stale cached suggestions automatically.

**Alternatives considered:**
- No caching, always call the LLM — rejected: unnecessary cost and latency for a very common repeat action.
- Cache on document hash alone — rejected: would silently serve stale suggestions after a tenant edits their entity configuration.

### Decision 6: Lightweight Celery queue, separate from the GPU training queue

**Choice:** The LLM pre-labeling task runs on a new, non-GPU Celery queue (e.g. `annotation.llm_jobs`), not on the `training.jobs` queue/node pool established by ADR-006.

**Rationale:** ADR-006's GPU node pool exists specifically for PyTorch fine-tuning; autoscaling it from LLM API calls would be wasteful (GPU pods for network I/O) and couples two operationally different workloads (cheap, frequent LLM calls vs. expensive, infrequent GPU training runs) onto the same scaling policy.

**Alternatives considered:**
- Reuse `training.jobs` — rejected for the reason above; also risks LLM pre-labeling requests queueing behind GPU training jobs at the broker level.

## Risks / Trade-offs

- [LLM output is non-deterministic across calls even for the same document] → Mitigated by caching (Decision 5) for repeat calls; residual run-to-run variance is acceptable since every suggestion still passes through the same human-approval gate before becoming a confirmed span.
- [Grounding step (Decision 2/4) may reject a meaningful fraction of LLM output if the model paraphrases despite prompting] → Track and surface a per-document "N suggested, M grounded" ratio so this is observable, not silent; if the drop rate is high in practice, prompt tuning is a design-level fix, not a spec-level one — flagged as an open question below rather than pre-solved here.
- [Introducing an external LLM dependency into `annotation_service` for the first time] → Scoped behind a provider-agnostic interface so the concrete provider can be swapped without touching the grounding/storage logic; concrete provider choice deferred (open question).
- [Async job means the caller doesn't get suggestions back in the same request] → Consistent with existing async patterns elsewhere in the platform (training jobs); the spec requires a way to poll/fetch job status and, on completion, the resulting suggestions via the existing suggested-spans listing endpoint.

## Migration Plan

1. Alembic migration: add `source` column to `{tenant_schema}.suggested_spans` (all tenant schemas) with a default backfill value of `'keyword'` for any pre-existing rows, and add the QA-pairs column to `public.entity_definitions` (nullable, no backfill needed).
2. Update the existing keyword `prelabel_document` path to write `source='keyword'` explicitly (behavior-neutral change, covered by the modified `annotation-workspace` spec).
3. Add the new Celery queue/task and the new trigger endpoint, gated so it is inert (returns "not configured") for any tenant with no QA pairs on any entity type — this makes the change safe to deploy ahead of any tenant actually using it.
4. Rollback: the migration is additive-only (new column with a default, new nullable column) — safe to leave in place even if the feature is disabled; no destructive rollback step is required. Disabling the feature is a matter of not exposing/calling the new endpoint.

## Resolved Questions

These three were the group-1 hard gates in `tasks.md`. Recorded here rather than in a new ADR
because none of them establishes a pattern beyond this change; the ADR question below is still open.

- **PII / data residency (task 1.1) — resolved: same posture as extraction.** Tenant document text
  may be sent to the configured external LLM provider, on exactly the footing already approved for
  `extraction_service`'s post-processing stage and `chat_api`'s RAG, both of which send tenant
  document content to Azure OpenAI today. No per-tenant opt-in column and no self-hosted fallback is
  introduced by this change; the feature is inert unless a deployment configures the provider, so a
  deployment that has not approved the posture simply never runs it.
- **Provider / model (task 1.2) — resolved: Azure OpenAI via the existing settings.** Pre-labeling
  uses `settings.azure_openai_endpoint`, `azure_openai_api_version`, and
  `azure_openai_chat_deployment` (default `gpt-4o-mini`), with the key read from `openai_api_key`,
  which has no default in `Settings` and is therefore supplied by environment only — the AGENTS.md
  secret-hygiene invariant is satisfied without adding a new secret-class setting. The client stays
  behind a provider-agnostic interface (Decision 7) so the concrete provider can be swapped without
  touching grounding or storage.
- **Duplicate-quote resolution (task 1.3) — approved as designed.** A quote matching multiple
  locations grounds to the first occurrence not already claimed by another grounded suggestion for
  that document, mirroring `prelabel_document`'s overlap rule.

### Decision 7: Provider-agnostic client, Azure OpenAI implementation

**Choice:** `src/annotation_service/services/llm_client.py` defines the interface the pre-labeling
task calls — one method taking a system prompt and a user payload and returning parsed JSON. The
concrete Azure OpenAI implementation is selected by configuration and is the only module that
imports the provider SDK.

**Rationale:** Decision 2 puts grounding and storage on the far side of the LLM call. Keeping the SDK
in one module means the failure modes of the provider (rate limits, timeouts, malformed JSON) are
handled in one place and the deterministic half of the pipeline stays testable with a stub.

## Open Questions

- What should a `source: "llm"` confidence score represent — model-reported likelihood, or something computed from the grounding step (e.g. always 1.0 once grounded, since grounding is a hard match)? Needs a decision before change 5/6 can build meaningful confidence-based routing on top of it.
- No in-force ADR currently addresses "external LLM API usage" as a category (unlike ADR-002/003/008 which address the tenant's *own* trained model). If this pattern is expected to recur (e.g. future changes in this same plan), a new ADR may be warranted after this change — noted here rather than resolved, since ADR authorship is a separate step.
