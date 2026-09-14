# Verification Plan

**Change:** cross-encoder-rerank
**Generated:** 2026-07-24
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | model-serving | Cross-encoder reranking endpoint | Rerank reorders candidates by relevance | Given the rerank endpoint, when POSTing a query plus candidates where a later candidate is more relevant, then response is 200 with a `results` array of `{index, score}` ordered by score descending, and the relevant candidate's index comes first | endpoint test: task 2.5 | - [x] |
| 2 | model-serving | Cross-encoder reranking endpoint | Rerank respects the requested top_k | Given the rerank endpoint, when POSTing 10 candidates with `top_k=3`, then `results` contains exactly 3 entries | endpoint test: task 2.6 | - [x] |
| 3 | model-serving | Cross-encoder reranking endpoint | Rerank with an empty candidate list | Given the rerank endpoint, when POSTing an empty `documents` list, then response is 200 with an empty `results` array and no inference is performed | endpoint test: task 2.7 | - [x] |
| 4 | model-serving | Cross-encoder reranking endpoint | Reranker model is not held in the per-tenant model cache | Given the reranker has served a request, when the per-tenant model cache is inspected, then the reranker is absent from it and tenant-model LRU eviction does not evict it | cache-inspection test: task 2.8 | - [x] |
| 5 | model-serving | Cross-encoder reranking endpoint | Rerank returns 401 when JWT is missing | Given no JWT, when POSTing to `/internal/v1/rerank`, then response is 401 (matches existing `TenantContextMiddleware` convention for every other `model_serving` endpoint; deviated from original 403 draft during apply — see proposal open questions) | endpoint test: task 2.9 | - [x] |
| 6 | retrieval-core | Reranker interface | CrossEncoderReranker reorders results by cross-encoder score | Given results and a query, when `rerank` is called and the service ranks a later result highest, then the returned list is ordered by score descending with `document_id`/`chunk_index`/`chunk_text` preserved | unit test: task 3.5 | - [x] |
| 7 | retrieval-core | Reranker interface | CrossEncoderReranker returns None when the service is unavailable | Given the reranking service is unreachable or times out, when `rerank` is called, then it returns `None` without raising | unit test: task 3.6 | - [x] |
| 8 | retrieval-core | Reranking retriever composition | RerankingRetriever over-fetches candidates then truncates to top_k | Given reranking enabled with candidate count 20, when `retrieve` is called with `top_k=5`, then the wrapped retriever is asked for 20, the reranker receives those candidates, and at most 5 are returned | unit test: task 4.6 | - [x] |
| 9 | retrieval-core | Reranking retriever composition | RerankingRetriever falls back to original order when reranking fails | Given reranking enabled but the reranker returns `None`, when `retrieve` is called with `top_k=5`, then the wrapped retriever's original order truncated to 5 is returned and no exception propagates | unit test: task 4.7 | - [x] |
| 10 | retrieval-core | Reranking retriever composition | RerankingRetriever bypasses reranking when disabled | Given the feature flag is disabled, when `retrieve` is called with `top_k=5`, then the wrapped retriever is asked for 5 (not the candidate count) and the reranker is never invoked | unit test: task 4.8 | - [x] |
| 11 | retrieval-core | Reranking retriever composition | RerankingRetriever satisfies the Retriever protocol | Given a `RerankingRetriever` wrapping any retriever, when used where a `Retriever` is expected, then `retrieve` accepts the same arguments and returns `list[RetrievalResult]` | unit test: task 4.9 | - [x] |
| 12 | retrieval-core | Reranking configuration | Reranking defaults are applied when no environment overrides are set | Given no reranking env vars, when configuration loads, then reranking is enabled, candidate count is 20, and the model name defaults to a cross-encoder identifier | unit test: task 1.2 | - [x] |
| 13 | retrieval-core | Reranking configuration | Reranking can be disabled via environment variable | Given `NER_RERANKER_ENABLED=false`, when configuration loads, then `RerankingRetriever` bypasses reranking | unit test: tasks 1.3, 4.8 | - [x] |
| 14 | chat-api | Reranked document context | A relevant chunk ranked below the truncation cutoff is promoted into context | Given a chunk that answers the question but is outside the top 3 by embedding similarity, and reranking enabled, when the question is sent to chat, then response is 200 and that chunk appears in `sources` | end-to-end test: task 5.3 | - [x] |
| 15 | chat-api | Reranked document context | Chat succeeds with unreranked ordering when the reranker is unavailable | Given reranking enabled but the service unavailable, when a question matching chunks is sent, then response is 200 with document chunk sources and at least one citation | end-to-end test: task 5.4 | - [x] |
| 16 | chat-api | Reranked document context | Reranking does not alter the structured entity source | Given a question producing both SQL and chunk results with reranking enabled, when sources are assembled, then the SQL source is unchanged and only chunk ordering is affected | test: task 5.5 | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Model hosting location | AI may register the reranker in `ModelCache` (following the more prominent per-tenant model path in `inference_service.py`) instead of the module-level singleton pattern used by `_base_pipeline`, letting tenant models evict it and consuming tenant-model memory budget | Read the reranker loading code — confirm it is a module-level lazy global (mirroring `_get_base_pipeline`) and that `model_cache.put()` is never called for it |
| 2 | Graceful degradation path | AI may let reranker HTTP errors propagate (raising out of `RerankingRetriever` and failing the chat request) instead of returning `None` and falling back to original ordering, silently violating ADR-007's availability requirement | Confirm `CrossEncoderReranker` catches transport/timeout errors and returns `None`, and that `RerankingRetriever` handles `None` by returning the wrapped order; verify with a test that points the client at a dead endpoint |
| 3 | Index mapping after reranking | AI may return reranked *scores* but reorder the wrong objects — e.g. treating the endpoint's returned `index` as a position in the reranked output rather than an index into the original candidate list — silently scrambling which chunk gets which score | Trace the index mapping explicitly: the endpoint returns original-list indices; confirm the client maps `results[i].index` back into the input `RetrievalResult` list, and test with a case where reranked order differs from input order |
| 4 | Over-fetch vs. top_k confusion | AI may pass `top_k` to the wrapped retriever instead of `rerank_candidate_count`, making reranking a no-op reordering of exactly the results that would have been returned anyway (feature appears to work, delivers no benefit) | Assert in test that the wrapped retriever receives the candidate count (20), not `top_k` (5), when reranking is enabled — scenario 8 covers this and must genuinely assert the wrapped call's argument |
| 5 | Disabled-path cost | AI may implement the feature flag by still over-fetching and then skipping only the rerank call, leaving the extra retrieval cost in place when the feature is off | Confirm the disabled path requests exactly `top_k` from the wrapped retriever (scenario 10) |
| 6 | Concurrent retrieval-layer changes | AI may write `retriever.py`/`__init__.py` edits against this design's snapshot rather than the live file, clobbering `SparseRetriever`/`HybridRetriever` from `hybrid-retrieval-hnsw` or purpose-filter changes from `document-purpose-scoping` | Before editing, re-read `src/shared/retrieval/retriever.py` and `__init__.py`; confirm the final diff only *adds* `RerankingRetriever` and exports, leaving existing retriever classes intact |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-001: Tenant Data Isolation | Tenant-scoped schemas, no cross-tenant data access | The reranker model is shared across tenants; it must remain stateless w.r.t. tenancy and score only caller-supplied candidate texts, reading no tenant storage | Confirm the rerank endpoint and service take only `query` + `documents` from the request body, perform no database access, and retain no per-request state between calls |
| ADR-003: Per-Tenant Model Serving Topology | Shared serving pool, per-tenant routing, version pinning, ONNX Runtime — for *tenant* models | This change adds a shared tenant-agnostic model; it must not alter per-tenant routing, version pinning, or the tenant-model cache behavior | Confirm `inference_service.py`'s tenant path, `ModelCache` behavior, and version resolution are unchanged by the diff; confirm the reranker introduces no per-tenant versioning |
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citations required, graceful degradation if a RAG source is unavailable, P95 < 10s | Reranking must preserve the three-source shape and citation enforcement, must degrade gracefully, and must stay within the latency budget | Confirm `RAGOrchestrator.execute`'s three-source structure and `guardrails.enforce_sources` are unchanged; confirm scenario 15 (reranker down ⇒ chat still succeeds); record measured rerank latency |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (rerank reorders): test output showing a deliberately out-of-order candidate list returned in correct relevance order
- [x] Scenario 2 (top_k respected): test output asserting result count
- [x] Scenario 3 (empty candidates): test output showing 200 + empty results, no inference
- [x] Scenario 4 (not in model cache): test/inspection output showing reranker absent from `ModelCache` and surviving tenant-model eviction
- [x] Scenario 5 (401 without JWT): test output
- [x] Scenario 6 (client reorders correctly): test output verifying index-to-result mapping across a reorder
- [x] Scenario 7 (client returns None on failure): test output against an unreachable endpoint
- [x] Scenario 8 (over-fetch then truncate): test output asserting the wrapped retriever received the candidate count and ≤ top_k returned
- [x] Scenario 9 (fallback on rerank failure): test output showing original order preserved, no exception
- [x] Scenario 10 (disabled bypass): test output asserting wrapped retriever received top_k and reranker was never called
- [x] Scenario 11 (protocol conformance): test substituting `RerankingRetriever` wherever a `Retriever` is expected
- [x] Scenario 12 (config defaults): unit test asserting default flag/count/model values
- [x] Scenario 13 (flag disables): unit test with `NER_RERANKER_ENABLED=false`
- [x] Scenario 14 (relevant chunk promoted): end-to-end test/log showing a chunk outside the embedding top-3 appearing in `sources` after reranking
- [x] Scenario 15 (chat survives reranker outage): end-to-end test with the reranker unavailable, asserting 200 + citations
- [x] Scenario 16 (SQL source untouched): test comparing the SQL source with reranking on vs. off

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Confirmed no new Python dependency was added (`torch`/`transformers` already present)
- [x] Measured rerank latency recorded and confirmed within ADR-007's P95 < 10s end-to-end budget

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — reranker is a module-level singleton, never `model_cache.put()`
- [x] Risk 2 mitigation confirmed — transport errors return `None`, verified against a dead endpoint
- [x] Risk 3 mitigation confirmed — index mapping traced and tested across a genuine reorder
- [x] Risk 4 mitigation confirmed — wrapped retriever demonstrably receives the candidate count, not `top_k`
- [x] Risk 5 mitigation confirmed — disabled path requests exactly `top_k`
- [x] Risk 6 mitigation confirmed — diff of `retriever.py`/`__init__.py` is purely additive; existing retriever classes intact

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `pytest tests/test_reranker_client.py tests/test_reranking_retriever.py -q` → 6 passed (client reorder/None-on-failure; retriever over-fetch/fallback/disabled/protocol conformance) | 6, 7, 8, 9, 10, 11 | agent (apply) | 2026-07-27 |
| 2 | Test output | `pytest tests/test_env_config.py -k "reranking or reranker" -q` → 2 passed (defaults, disabled via env) | 12, 13 | agent (apply) | 2026-07-27 |
| 3 | Test output | `pytest tests/test_chat_api_reranking.py -q` (real Postgres test DB, `hybrid_schema`-style fixtures) → 3 passed (chunk promoted into sources; chat survives reranker returning `None`; SQL source identical on/off) | 14, 15, 16 | agent (apply) | 2026-07-27 |
| 4 | Test output (in rebuilt `model_serving` container, torch/transformers present) | `docker exec ner-project-model_serving-1 python -m pytest test_rerank_endpoint.py -q` → 5 passed (reorder, top_k, empty-list no-inference, absent from `ModelCache` + survives LRU eviction, 401 without JWT) | 1, 2, 3, 4, 5 | agent (apply) | 2026-07-27 |
| 5 | Live measurement | Rebuilt & restarted `model_serving`/`chat_api` containers; `POST /internal/v1/warmup` cold-loaded `cross-encoder/ms-marco-MiniLM-L-6-v2` from HF hub in ~81s (one-time, matches design.md's documented cold-start risk); warm `POST /internal/v1/rerank` over 20 candidates returned in ~1.1s, correctly ranking the two refund-related documents above 18 distractors — well within ADR-007's P95 < 10s budget | 1, structural (latency) | agent (apply) | 2026-07-27 |
| 6 | Regression run | `pytest tests/test_retrieval_foundation.py tests/test_hybrid_retrieval.py tests/test_chunk_metadata_ingest.py -q` → 33 passed; `pytest tests/test_chat_api_rag.py -q` → 1 failed (pre-existing `test_chat_response_sources` disclaimer-wording mismatch, unrelated to this change), 6 passed, 2 skipped — no new failures | regression (tasks 6.1, 6.2) | agent (apply) | 2026-07-27 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** cross-encoder-rerank
**Proposal:** `openspec/changes/cross-encoder-rerank/proposal.md`
**Spec files reviewed:**
  - specs/model-serving/spec.md
  - specs/retrieval-core/spec.md
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
