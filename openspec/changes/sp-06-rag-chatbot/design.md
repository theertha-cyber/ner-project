## Context

SM-05 (Extraction Engine) provides real-time and batch entity extraction, storing extracted entities in `extracted_entities` tables within each tenant schema. Documents are stored with their text content, and document chunks with embeddings have been discussed but not yet implemented. There is no conversational interface to query extracted entities, search document context, or embed entity-aware Q&A into tenant applications.

ADR-007 (Chatbot Architecture) already defines the overall approach: a three-source RAG pipeline combining structured entity SQL queries, pgvector semantic search over document chunks, and live NER model inference, with guardrails for SQL validation, source citations, query complexity limits, blocked question types, and disclaimers.

The gateway and model-serving layer (SM-05) are in place. pgvector extension is not yet enabled on PostgreSQL. Document chunking and embedding is not yet implemented.

## Goals / Non-Goals

**Goals:**

- New `src/chat-api/` FastAPI microservice — chat endpoint (`POST /api/v1/tenants/{tid}/chat`), conversation CRUD, widget API key management, guardrail enforcement
- Three-source RAG pipeline: controlled SQL generation over extracted entities, pgvector semantic search over document chunks, live NER inference via model-serving internal endpoint
- SQL validation layer — parses and constrains generated SQL to read-only queries on tenant-scoped tables
- Conversation persistence — `chats` and `chat_messages` tables in each tenant schema
- Embeddable widget — hosted JS widget file at `GET /api/v1/public/widget.js`, tenant-specific API keys, CORS-safe endpoints
- Internal chat UI — `src/portal/app/(auth)/chat/page.tsx` with conversation sidebar, message thread, and source citation expansion
- Rate limiting per tenant (distinct limits for internal API vs widget API)
- pgvector extension enabled on PostgreSQL; `document_chunks` table created in each tenant schema

**Non-Goals:**

- LLM fine-tuning per tenant — uses a shared LLM (OpenAI GPT-4o-class) with prompt-based tenant scoping
- Streaming responses — MVP uses request/response; streaming deferred to post-MVP
- Voice/multimodal input — text-only for MVP
- Cross-tenant chat or analytics — every query is scoped to a single tenant
- Chatbot training on tenant data — no RAG source documents are used to fine-tune the LLM itself
- Real-time document chunking — chunks are pre-computed at document upload/OCR time (this is a change to the document processing pipeline that will be coordinated with SM-02)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant Data Isolation via Separate DB Schemas | All chat data stored in `tenant_{uuid}` schemas; widget API keys in `public` schema |
| ADR-003 | Model Serving Topology | Live NER inference routes through model-serving internal endpoint `/internal/v1/infer` |
| ADR-007 | Chatbot Architecture — Full RAG with Guardrails | Three-source pipeline (SQL + pgvector + NER); guardrails: SQL validation, source citations, complexity limits, blocked questions, disclaimers |
| ADR-008 | Base Model as Default | When no fine-tuned model is promoted, NER inference uses base model (version 0) with CoNLL labels |

## Decisions

### Decision 1: Standalone Chat API Microservice

**Choice:** Create a new `src/chat-api/` FastAPI microservice rather than embedding chat logic in the existing extraction service or gateway.

**Rationale:** The chat API has a unique dependency profile (OpenAI/LLM client, pgvector queries, SQL generation library, guardrail schemas) and scaling pattern (LLM calls are high-latency, I/O-bound). Keeping it separate from extraction-service (CRUD-heavy) and model-serving (CPU/memory-bound inference) allows independent scaling and deployment.

**Alternatives considered:**
- Embed in extraction-service — would couple CRUD logic with LLM orchestration; extraction-service would need OpenAI API key access; scaling extraction for chat volume would scale extraction unnecessarily
- Embed in gateway — violates gateway's responsibility as a thin routing layer; would require gateway to manage LLM connections, pgvector queries, and guardrail logic

### Decision 2: Direct RAG Pipeline (No LangChain/LlamaIndex)

**Choice:** Build the three-source RAG pipeline directly using HTTP calls (to model-serving), SQL queries (to PostgreSQL), and OpenAI API calls, without LangChain or LlamaIndex.

**Rationale:** The three-source pattern is simple and well-defined: (1) generate SQL from natural language via LLM → validate → execute → format results, (2) embed query → pgvector similarity search, (3) call model-serving for NER on relevant snippets. LangChain adds abstraction overhead, versioning complexity, and makes guardrail enforcement harder to audit. Building direct keeps the guardrail layer explicit and testable.

**Alternatives considered:**
- LangChain — faster initial iteration but harder to customize guardrail enforcement; abstraction leaks under complex requirements
- LlamaIndex — similar trade-offs to LangChain; more focused on document indexing which we handle at upload time

### Decision 3: SQL Validation Layer with Read-Only Transactions

**Choice:** A dedicated SQL validation layer that (a) restricts generated SQL to SELECT queries only, (b) validates table names against a whitelist of tenant-scoped tables (extracted_entities, document_chunks, etc.), (c) validates column names against a whitelist per table, (d) enforces a LIMIT clause, (e) rejects UNION, subqueries, JOINs on non-whitelisted relations, and (f) executes in a read-only transaction with a 10-second timeout.

**Rationale:** ADR-007 mandates that SQL queries be validated before execution. A whitelist-based approach is more secure than a blocklist (which attackers can bypass). Read-only transactions provide a second line of defense — even if validation misses something, the transaction cannot modify data.

**Alternatives considered:**
- LLM-only validation (ask the LLM to self-validate) — unreliable; LLMs can hallucinate approval of their own SQL
- Execute with restricted PostgreSQL role — requires creating a dedicated role per tenant with read-only grants on specific tables; higher operational overhead for MVP

### Decision 4: Pre-Computed Document Chunks at Upload Time

**Choice:** Document chunking and embedding happens at document upload/processing time (as a step in the ingestion pipeline, coordinated with SM-02), not at chat time. Chunks are stored in a `document_chunks` table (`tenant_template` schema) with columns: `id`, `document_id`, `chunk_index`, `chunk_text`, `embedding` (vector), `created_at`.

**Rationale:** Pre-computing embeddings avoids per-query latency of chunking + embedding. The embedding model (text-embedding-3-small) is called once per upload rather than once per chat query. This adds minimal overhead to the ingestion pipeline and drastically improves chat response time.

**Alternatives considered:**
- On-the-fly chunking at chat time — adds 1-3 seconds per query; simple initial implementation but poor UX
- Separate chunking service — cleaner separation of concerns but over-engineering for MVP

### Decision 5: Widget API Keys in Public Schema

**Choice:** Tenant-specific API keys stored in a `widget_api_keys` table in the `public` schema. Keys are UUIDs generated at tenant creation or on-demand. Widget endpoints authenticate via `Authorization: Bearer <widget_key>`. Each key is scoped to a single tenant and has read-only permissions on that tenant's extracted entities and document chunks.

**Rationale:** Unlike user JWTs (which carry tenant_id in claims), widget API keys must work for anonymous external users. Storing keys in a hashed form in `public` schema allows key validation without a tenant context. A single `tenant_id` lookup from the key provides the tenant scope.

**Alternatives considered:**
- JWT for widgets — requires widget users to have JWTs; impractical for external embedding
- No auth on widget endpoints — insecure; would leak tenant data

## Risks / Trade-offs

- [LLM latency makes P95 > 10s] → Implement query caching for common question patterns; consider streaming for post-MVP; alert at P95 > 10s per ADR-007 compliance
- [SQL validation layer false positive blocks valid queries] → Return actionable error message with the generated SQL for admin debugging; log all blocked queries with the generated SQL for review
- [pgvector performance degrades with many chunks] → Create IVFFlat index on embeddings; benchmark at 10k, 100k, 1M chunks per tenant; consider partitioning by document if needed
- [OpenAI API key cost grows with query volume] → Track cost per tenant; implement daily budget caps; evaluate open-source self-hosting for production scale
- [Widget API key leaks in client-side JS] → Keys are read-only and scoped to single tenant; rotate on compromise; log all widget API access; rate-limit aggressively

## Migration Plan

1. Enable pgvector extension on PostgreSQL (`CREATE EXTENSION vector;`)
2. Create `document_chunks` table in `tenant_template` schema (migration)
3. Add document chunking step to SM-02 document processing pipeline (upload → OCR → chunk → embed → store)
4. Create `chat_messages` and `widget_api_keys` tables (migration)
5. Create `src/chat-api/` — FastAPI scaffolding, config, database setup, auth middleware
6. Implement SQL generation and validation layer
7. Implement pgvector similarity search endpoint (internal)
8. Implement NER inference integration (call model-serving)
9. Implement three-source RAG orchestration in chat endpoint
10. Implement conversation CRUD endpoints
11. Implement widget API key management
12. Implement hosted widget JS file
13. Create `src/portal/app/(auth)/chat/page.tsx` — chat UI with conversation sidebar and message thread
14. Wire gateway routes for chat-api service
15. Add CORS configuration for widget endpoints

Rollback: Remove gateway routes for chat-api; stop chat-api service; chat data remains in database; widget JS returns 404; portal `/chat` route shows placeholder.

## Open Questions

- What OpenAI model should be used for SQL generation vs response generation? (Single model for both, or separate models?)
Answer: Use Azure openai model for both
- What chunk size and overlap strategy? (Proposed: 512 tokens with 128-token overlap, aligned with embedding model context window.)
- Should the widget JS be a simple CSS-in-JS bundle or link to a separately hosted CSS file? (Proposed: CSS-in-JS to minimize external requests.)
Answer: separate hosted css file
- ADR-007 assumes OpenAI GPT-4o-class with tenant-scoped API keys. Should we use a single shared API key for all tenants (simpler) or per-tenant keys (better isolation)? (Proposed: single shared key for MVP, per-tenant key for production.)
Answer: shared for now.