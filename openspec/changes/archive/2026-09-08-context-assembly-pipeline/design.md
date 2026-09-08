## Context

Chat execution has two paths behind `settings.chat_use_graph` (default `True`): the LangGraph path (`src/chat_api/graph/`) and `RAGOrchestrator._execute_legacy`. Both build LLM context with identical inline logic and their own copy of `SYSTEM_PROMPT`. `langgraph-orchestration` already split the graph path into named traced stages — `source_assembly_node` (builds `Source`/`Citation` objects for the API response) and `prompt_assembly_node` (builds `prompt_messages` for the LLM) — and `builder.py` wires them in that order (`source_assembly` → `prompt_assembly`), so a data dependency from the former to the latter is already satisfied by the graph topology.

The assembly those stages perform is where the defects are. Measured with the project's own `cl100k_base` tokenizer on realistic English prose: a 512-token chunk is ~3391 characters, so `prompt_assembly_node`'s `c.chunk_text[:500]` retains 77 tokens — **15% of the chunk**. Ingestion produces chunks with a deterministic 128-token overlap, so adjacent chunks share text that is currently spent twice. `_enrich_citations` resolves document filenames and `page_number` for the response but the prompt receives bare UUIDs.

Upstream state this builds on: `retrieval-foundation`, `chunk-metadata-ingest` (page/char metadata on `RetrievalResult`), `hybrid-retrieval-hnsw`, `document-purpose-scoping` (all archived), and `cross-encoder-rerank` (applied, pending sign-off) — chunks arriving at assembly are hybrid-retrieved, purpose-scoped, and cross-encoder reranked, i.e. in *relevance* order rather than document order.

In-force ADRs (supersession graph checked: ADR-008 partially supersedes ADR-002 for base-model fallback only; ADR-003 explicitly unaffected by it; no ADR exists for the LangGraph work): **ADR-007** (chatbot architecture — citations required, graceful degradation, P95 < 10s, LLM cost scales with volume) and **ADR-001** (tenant isolation) constrain this change.

## Goals / Non-Goals

**Goals:**

- Token-budgeted assembly using `tiktoken`, eliminating every character-slice and magic-count truncation in the prompt path.
- Whole chunks in the prompt, admitted in relevance order until the budget binds — no mid-sentence cuts.
- Deduplication of the deterministic ingestion overlap.
- Document filename and page number in the prompt, replacing raw UUIDs.
- Exactly one assembly implementation, shared by both execution paths.

**Non-Goals:**

- No context *compression* or summarization of chunks (an LLM-based compression stage is a plausible later change; this change only stops wasting the budget it already has).
- No query rewriting, multi-query retrieval, or changes to retrieval/reranking.
- No change to `Source`/`Citation` construction or the `/api/v1/chat` contract — this change alters what the LLM is *given*, not what the API returns.
- No regrouping of chunks by document (see Decisions — reranking established relevance order and regrouping would fight it).
- No removal of `_execute_legacy` — that is `langgraph-orchestration`'s call, not this change's.

## Decisions

**`ContextAssembler` lives in `src/chat_api/services/context_assembler.py`, not `src/shared/retrieval/`.**
Assembly consumes retrieval output but is chat-specific: it owns `SYSTEM_PROMPT`, conversation-history formatting, and OpenAI message shape. `document_service` has no use for it, and `src/shared/retrieval/` is deliberately scoped to models/protocol/chunking/retrievers/reranker. Keeping assembly in `chat_api` respects that boundary.

**Budget is enforced in tokens via `tiktoken` `cl100k_base` — the same encoding `src/shared/retrieval/chunking.py` uses to *produce* chunks.**
Using the same tokenizer on both ends means a chunk built as 512 tokens is measured as 512 tokens at assembly, so budget arithmetic is exact rather than an estimate. `tiktoken` is already a dependency.

**Whole-chunk admission: chunks are added in arrival (relevance) order while they fit; a chunk that does not fit is skipped, not cut.**
A chunk cut mid-sentence can be worse than no chunk — it can strand a subject from its verb and invite misreading. Skipping preserves the coherence of everything admitted. Last-resort exception: if the *first* chunk alone exceeds the budget, it is truncated on a **token** boundary (never a character boundary) so the pipeline degrades to "partial best chunk" instead of "empty context".
Alternative considered: proportionally shrink every chunk to fit — rejected, produces uniformly mutilated context instead of a coherent subset.

**Default `context_token_budget = 6000`, with an honest note on what it does and does not fix.**
At current settings the budget rarely binds: `retrieval_top_k=5` × `chunk_size=512` caps retrieved chunk content at ~2560 tokens, well under 6000, leaving room for SQL results, NER entities, history, and the 1000-token reply allowance. This is deliberate — **the correctness fix here is removing the 500-character slice, not the budget itself.** The budget exists as a rail so that raising `retrieval_top_k` or `chunk_size` later cannot silently overflow the model window. 6000 is safe on any model with a ≥16k window, including the configured Azure default (`gpt-4o-mini`), rather than being tuned to `gpt-4o`'s full 128k.

**Deduplication targets the known deterministic overlap: same `document_id`, adjacent `chunk_index`.**
The 128-token overlap is not incidental — `chunk_text(overlap=128)` produces it, so the overlapping pairs are exactly identifiable rather than something to guess at with a similarity threshold. The assembler groups admitted chunks by `document_id`, and where two admitted chunks have adjacent `chunk_index`, trims the shared boundary text from the later-positioned one. A cheap full-containment check runs as a general guard for any other duplicate. Because reranking reorders chunks by relevance, adjacency must be detected across the whole admitted set, not just between neighbours in the list.
Alternative considered: shingle/Jaccard similarity dedup — rejected as unnecessary machinery for an overlap whose size and location are already known exactly.

**Dedup and truncation operate on copies for the prompt only; `RetrievalResult` objects and the `Source`/`Citation` objects built from them are never mutated.**
`Citation.context_snippet` carries the chunk text into the API response, and users should see the real retrieved snippet, not a prompt-optimised trim. Assembly is read-only with respect to its inputs.

**Provenance: `source_assembly_node` publishes a `document_names: dict[str, str]` map onto `ChatState`; `prompt_assembly_node` consumes it.**
Resolves the proposal's first open question. `_enrich_citations` already queries `{schema}.documents` for exactly this map — re-querying inside the assembler would duplicate a round trip and risk the prompt and the citations disagreeing about a filename. The graph already guarantees `source_assembly` runs before `prompt_assembly`, so no topology change is needed. For the legacy path, `_execute_legacy` passes the map directly since it computes both in one function.
Prompt label format becomes `Document "<filename>" (page <n>):` with graceful fallback to the document id when the filename is unresolved and omission of the page clause when `page_number` is `None` (still the case for chunks ingested before `chunk-metadata-ingest`).

**Chunks stay in relevance order in the prompt; no regrouping by document.**
The full retrieval stack — hybrid fusion, then cross-encoder reranking — exists to produce a relevance ordering. Regrouping by document would discard that signal in the prompt. Relevance-ordered context also puts the strongest evidence earliest, which is where models weight most reliably.

**Both execution paths delegate to the assembler, including `_execute_legacy`.**
Resolves the proposal's third open question. `langgraph-orchestration` may later delete `_execute_legacy`; deleting a short delegation call at that point is trivial. Leaving legacy on the old inline logic in the meantime would mean the two `chat_use_graph` paths build materially different prompts — the exact divergence this change exists to eliminate.

## Risks / Trade-offs

- **[Risk] Sending ~6× more chunk content per query raises per-query LLM token cost, which ADR-007 flags as scaling with volume** → Mitigation: this is the intended correction, not a regression — the current 15% retention is silently discarding retrieved evidence the system paid to retrieve, rerank, and embed. Budget and `context_max_chunks` bound the ceiling; the increase is measured and recorded during verification so the cost change is explicit rather than discovered later on a bill.
- **[Risk] Larger prompts increase LLM latency against ADR-007's P95 < 10s** → Mitigation: measure end-to-end chat latency before and after and record it; the budget is the tuning lever if it binds.
- **[Risk] Dedup trimming could remove text that is not actually duplicated (e.g. a document that legitimately repeats a passage), corrupting context** → Mitigation: trim only where `document_id` matches *and* `chunk_index` values are adjacent — the exact signature of ingestion overlap; verify with a test that a document containing genuinely repeated text across non-adjacent chunks is left intact.
- **[Risk] Answer quality could regress if more context dilutes the signal ("lost in the middle")** → Mitigation: relevance ordering puts strongest evidence first; `context_max_chunks` allows capping breadth independently of the token budget if dilution is observed.
- **[Risk] Two active changes (`langgraph-orchestration`, `cross-encoder-rerank`) are touching `graph/nodes.py` and the retrieval stack concurrently** → Mitigation: re-read `graph/nodes.py`, `graph/state.py`, and `rag_orchestrator.py` at apply time rather than trusting this design's snapshot; this change's edits to `nodes.py` are confined to `prompt_assembly_node`'s body plus one added key in `source_assembly_node`'s return.
- **[Risk] Assembler needs a token count for SQL results and NER entities too, and those are JSON blobs whose token cost is easy to underestimate** → Mitigation: budget accounting measures every component's rendered string, not just chunks; a test asserts the total assembled prompt stays within budget when SQL and NER content are both present and large.

## Migration Plan

Pure code change — no migration, no backfill, no re-ingestion, no API contract change. Deploy as a normal release. Rollback is a code revert; additionally, setting `context_token_budget` low would approximate the old behaviour but is not a real rollback path (the character slice is gone), so revert is the intended mechanism. No coordination with `model_serving` or `document_service` required.

## Open Questions

- No in-force ADR needs revisiting. ADR-007's citation-enforcement and graceful-degradation guarantees are untouched (assembly changes prompt content only; `guardrails.enforce_sources` still runs on the reply), and its cost/latency consequences are explicitly measured in verification rather than assumed benign.
- Resolved from proposal: document names flow via `ChatState` (no extra query), default budget 6000 tokens, and both execution paths are wired to the shared assembler.
- Worth a reviewer's judgement: whether `context_max_chunks` should default to `retrieval_top_k` (i.e. admit everything retrieval returns and let the budget be the only limiter) or to a smaller fixed number. This design defaults it to `retrieval_top_k` so retrieval settings remain the single place that controls breadth.
