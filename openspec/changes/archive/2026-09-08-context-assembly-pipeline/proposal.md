## Why

The pipeline now retrieves well and reranks precisely — and then throws most of it away. `prompt_assembly_node` builds LLM context with `c.chunk_text[:500]`, a **character** slice applied to chunks that ingestion produced as 512-**token** windows. Measured against realistic English prose with the project's own `cl100k_base` tokenizer: a 512-token chunk is ~3391 characters, so `[:500]` retains **77 of 512 tokens — 15%**. The cross-encoder reranker was just built to identify the 5 most relevant chunks; 85% of each of those chunks is then discarded mid-sentence before the model sees it.

Three more assembly defects compound it:
- **No deduplication.** Chunking uses a 128-token overlap by design, so adjacent chunks share ~25% of their text. When two adjacent chunks both survive retrieval, the duplicated span is spent twice against a context window nobody is measuring.
- **Provenance is stripped before the LLM, then re-added after it.** The prompt labels context `Document context (from {document_id})` — a bare UUID. `_enrich_citations` separately resolves real filenames and `page_number` (available since `chunk-metadata-ingest`) but only for the API response. So the system prompt instructs the model to "reference the specific document or entity source" while handing it UUIDs, and the page numbers the ingestion pipeline was extended to capture never reach the model at all.
- **Assembly logic is duplicated.** `SYSTEM_PROMPT` and every truncation constant exist twice — in `RAGOrchestrator._execute_legacy` and in `graph/nodes.py` — so any assembly fix must be made in two places or silently diverge between the `chat_use_graph` paths.

`langgraph-orchestration` already separated assembly into named, traced stages (`source_assembly_node`, `prompt_assembly_node`), so the staging work this change originally scoped is done. What remains is the assembly *quality* work those stages currently do badly.

## What Changes

- Add a `ContextAssembler` that builds LLM context under an explicit **token** budget measured with `tiktoken`, replacing all character-slice and fixed-count truncation (`chunk_text[:500]`, `chunks[:3]`, `sql_results[:10]`, `ner_entities[:5]`).
- Chunks are admitted whole in relevance order until the budget is consumed; a chunk that does not fit is skipped rather than cut mid-sentence, and if no chunk fits, the highest-ranked one is truncated on a **token** boundary as a last resort.
- Deduplicate overlapping chunk text before assembly so the 128-token ingestion overlap is not spent twice.
- Carry provenance into the prompt: each chunk is labeled with its resolved document filename and page number (when known) instead of a raw UUID, so the model can cite what the system prompt already asks it to cite.
- One shared assembler used by both the graph path and the legacy path; `SYSTEM_PROMPT` and all budget constants live in exactly one place.
- Add configuration: `context_token_budget`, `context_max_chunks`, `conversation_history_turns`.
- **BREAKING (prompt-level, not API-level)**: the text sent to the LLM changes shape — more chunk content per chunk, filenames/pages in place of UUIDs. `/api/v1/chat` request/response schemas are unchanged; `sources`/`Citation` output is unchanged.

## Capabilities

### New Capabilities

- `context-assembly`: token-budgeted, deduplicated, provenance-carrying assembly of retrieved chunks, SQL results, NER entities, and conversation history into LLM prompt messages — with a single implementation shared by every chat execution path.

### Modified Capabilities

- `chat-api`: the RAG chat endpoint's document context is assembled under a token budget and labeled with document filename and page number rather than document UUID.

## Impact

- `src/chat_api/services/context_assembler.py` (new — `ContextAssembler`, budget/dedup/provenance logic, single `SYSTEM_PROMPT`)
- `src/chat_api/graph/nodes.py` — `prompt_assembly_node` delegates to `ContextAssembler`; its local `SYSTEM_PROMPT` and inline truncation are removed
- `src/chat_api/services/rag_orchestrator.py` — `_execute_legacy`'s inline assembly and duplicate `SYSTEM_PROMPT` removed, delegating to the same assembler
- `src/shared/config.py` — `context_token_budget`, `context_max_chunks`, `conversation_history_turns`
- Provenance requires document filenames at assembly time. `_enrich_citations` already resolves them but runs in `source_assembly_node`, which is a *separate* node from `prompt_assembly_node` — the resolved names must be made available to assembly (see design; this is the main structural question this change has to answer)
- No database migration, no ingestion change, no retrieval change, no API contract change

## Open Questions

- **Where the resolved document names come from.** `source_assembly_node` already queries `{schema}.documents` for filenames via `_enrich_citations`, but it produces `Citation` objects for the API response, not a name map for the prompt. Options: have `source_assembly_node` also put a `document_id → filename` map on `ChatState` for `prompt_assembly_node` to consume (no extra query), or have the assembler resolve names itself (extra query, but keeps assembly self-contained). Leaning the former — confirm in design.
- **Default token budget.** The chat model is `gpt-4o` (or a configured Azure deployment) with `max_tokens=1000` reserved for the reply. A budget must leave room for the system prompt, conversation history, and the answer. Needs a concrete default that is safe for the smallest plausible configured deployment rather than tuned to `gpt-4o`'s full window — confirm the number in design.
- **Whether the legacy path should be updated or deleted.** `chat_use_graph` defaults to `True`, so `_execute_legacy` is a fallback that `langgraph-orchestration` (still active, 45/47 tasks) may intend to remove. If it is being deleted, wiring it to the new assembler is wasted work; if it is staying, leaving it on the old assembly logic defeats the single-implementation goal. Confirm before implementing.
