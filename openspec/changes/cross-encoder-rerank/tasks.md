## 1. Configuration

- [ ] 1.1 Add `reranker_enabled: bool = True`, `reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"`, and `rerank_candidate_count: int = 20` to `Settings` in `src/shared/config.py`
- [ ] 1.2 Unit test: assert the three defaults with no `NER_RERANKER_*` / `NER_RERANK_*` env vars set (covers scenario 12)
- [ ] 1.3 Unit test: assert `NER_RERANKER_ENABLED=false` disables the flag (covers scenario 13, paired with task 4.5)

## 2. Model Serving Rerank Endpoint

- [ ] 2.1 Add `RerankRequest` (`query: str`, `documents: list[str]`, `top_k: int | None`) and `RerankResponse` (`results: list[RerankResult]` where each has `index: int`, `score: float`) to `src/model_serving/api/v1/schemas.py`
- [ ] 2.2 Create `src/model_serving/services/rerank_service.py`: lazy module-level singleton loading `AutoTokenizer` + `AutoModelForSequenceClassification` from `settings.reranker_model`, mirroring `_get_base_pipeline`'s pattern in `inference_service.py` — do NOT use `ModelCache`
- [ ] 2.3 Implement `rerank(query, documents, top_k)` in that service: score each (query, document) pair, return original indices with scores sorted descending, truncated to `top_k`; return an empty list without invoking the model when `documents` is empty
- [ ] 2.4 Create `src/model_serving/api/v1/rerank.py` with `POST /internal/v1/rerank`, following `inference.py`'s router and tenant-context pattern; register the router in `src/model_serving/main.py`
- [ ] 2.5 Test: rerank a candidate list where a later item is most relevant, assert 200 and descending-score ordering with that item's original index first (covers scenario 1)
- [ ] 2.6 Test: 10 candidates with `top_k=3`, assert exactly 3 results (covers scenario 2)
- [ ] 2.7 Test: empty `documents` list, assert 200, empty results, and that the model was not invoked (covers scenario 3)
- [ ] 2.8 Test: after serving a rerank request, assert the reranker is absent from `model_cache` and that loading tenant models to eviction does not evict it (covers scenario 4, Hallucination Risk 1)
- [ ] 2.9 Test: POST without a JWT, assert 403 (covers scenario 5)
- [ ] 2.10 Pre-initialize the reranker in the existing `warmup` router so first-request cold start is paid at startup rather than on a user query

## 3. Reranker Client

- [ ] 3.1 Create `src/shared/retrieval/reranker.py` with a `Reranker` protocol (`rerank(query, results, top_k) -> list[RetrievalResult] | None`)
- [ ] 3.2 Implement `CrossEncoderReranker` in the same module: `httpx.AsyncClient` POST to `{model_serving_url}/internal/v1/rerank`, forwarding the bearer JWT, with an explicit timeout — mirroring `src/chat_api/services/ner_client.py`
- [ ] 3.3 Map the endpoint's returned `index` values back into the input `RetrievalResult` list to produce the reordered output — the returned index refers to a position in the *input* candidate list (covers Hallucination Risk 3)
- [ ] 3.4 Catch transport errors and timeouts, returning `None` rather than raising
- [ ] 3.5 Test: service returns scores ranking a later result highest, assert output order matches scores and `document_id`/`chunk_index`/`chunk_text` are preserved (covers scenario 6)
- [ ] 3.6 Test: point the client at an unreachable endpoint, assert it returns `None` and raises nothing (covers scenario 7, Hallucination Risk 2)

## 4. RerankingRetriever

- [ ] 4.1 Re-read the live `src/shared/retrieval/retriever.py` and `src/shared/retrieval/__init__.py` before editing — `hybrid-retrieval-hnsw` and `document-purpose-scoping` also modify these files; this change must be purely additive to them (covers Hallucination Risk 6)
- [ ] 4.2 Add `RerankingRetriever` to `src/shared/retrieval/retriever.py`, constructed from a wrapped `Retriever` and a `Reranker`, implementing the `Retriever` protocol
- [ ] 4.3 Implement `retrieve`: when enabled, request `settings.rerank_candidate_count` from the wrapped retriever, pass candidates to the reranker, return at most `top_k`; when the reranker returns `None`, return the wrapped ordering truncated to `top_k`
- [ ] 4.4 Implement the disabled path: request exactly `top_k` from the wrapped retriever and never invoke the reranker (covers Hallucination Risk 5)
- [ ] 4.5 Export `Reranker`, `CrossEncoderReranker`, and `RerankingRetriever` from `src/shared/retrieval/__init__.py`, preserving all existing exports
- [ ] 4.6 Test: with reranking enabled and `top_k=5`, assert the wrapped retriever was called with the candidate count (20), the reranker received those candidates, and at most 5 results returned (covers scenario 8, Hallucination Risk 4)
- [ ] 4.7 Test: reranker returns `None`, assert wrapped ordering truncated to `top_k` and no exception (covers scenario 9)
- [ ] 4.8 Test: flag disabled, assert wrapped retriever called with `top_k` and reranker never invoked (covers scenario 10)
- [ ] 4.9 Test: substitute `RerankingRetriever` wherever a `Retriever` is expected, assert signature/return-type conformance (covers scenario 11)

## 5. Wire RAGOrchestrator

- [ ] 5.1 Update `RAGOrchestrator.__init__` in `src/chat_api/services/rag_orchestrator.py` to wrap its existing retriever in a `RerankingRetriever` with a `CrossEncoderReranker`
- [ ] 5.2 Confirm `_vector_source` and `execute`'s three-source structure are otherwise unchanged
- [ ] 5.3 End-to-end test: seed a chunk that answers a question but ranks outside the embedding top-3; with reranking enabled, assert it appears in the chat response `sources` (covers scenario 14)
- [ ] 5.4 End-to-end test: with the reranking service unavailable, assert chat returns 200 with document chunk sources and at least one citation (covers scenario 15)
- [ ] 5.5 Test: for a question producing both SQL and chunk results, assert the SQL source is identical with reranking on vs. off (covers scenario 16)
- [ ] 5.6 Measure and record end-to-end chat latency with reranking enabled; confirm it remains within ADR-007's P95 < 10s budget

## 6. Regression

- [ ] 6.1 Re-run the existing retrieval test suites (`tests/test_retrieval_foundation.py`, plus any suites added by `chunk-metadata-ingest` and `hybrid-retrieval-hnsw`) and confirm all still pass
- [ ] 6.2 Re-run `tests/test_chat_api_rag.py` and confirm no new failures beyond the known pre-existing `test_chat_response_sources` disclaimer-wording failure
- [ ] 6.3 Confirm `poetry`/`pyproject.toml` dependencies are unchanged — `torch` and `transformers` were already present

## 7. Verification & Evidence

- [ ] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 7.6 Run `openspec validate cross-encoder-rerank --type change --strict` and confirm it exits clean before archive.
