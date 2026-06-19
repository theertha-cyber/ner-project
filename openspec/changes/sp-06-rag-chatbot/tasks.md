## 1. Infrastructure & Database Setup

- [ ] 1.1 Enable pgvector extension on PostgreSQL (`CREATE EXTENSION vector;`)
- [ ] 1.2 Create migration: add `document_chunks` table to `tenant_template` schema (`id`, `document_id`, `chunk_index`, `chunk_text`, `embedding vector(1536)`, `created_at`)
- [ ] 1.3 Create migration: add `conversations` and `chat_messages` tables to `tenant_template` schema
- [ ] 1.4 Create migration: add `widget_api_keys` table to `public` schema (`id`, `tenant_id`, `key_hash`, `key_prefix`, `created_at`, `last_used_at`, `revoked_at`)
- [ ] 1.5 Create IVFFlat index on `document_chunks.embedding` for similarity search performance
- [ ] 1.6 Add document chunking step to SM-02 document processing pipeline (upload → chunk → embed → store)

## 2. Chat API Service Scaffolding

- [ ] 2.1 Create `src/chat-api/` FastAPI project structure with config, database setup, auth middleware
- [ ] 2.2 Implement tenant context middleware (extract tenant_id from JWT for internal API, from API key for widget API)
- [ ] 2.3 Add `.env` entries for `OPENAI_API_KEY`, pgvector embedding model, rate limit settings, guardrail config
- [ ] 2.4 Implement health check endpoint

## 3. SQL Generation & Validation Layer

- [ ] 3.1 Implement SQL generator that takes natural language + conversation context and calls OpenAI to produce SELECT SQL
- [ ] 3.2 Implement SQL validation layer: whitelist-based table/column validation, SELECT-only enforcement, LIMIT enforcement, anti-subquery/anti-JOIN checks
- [ ] 3.3 Implement read-only transaction execution with 10-second timeout
- [ ] 3.4 Implement logging for rejected/malicious SQL queries
- [ ] 3.5 Write tests: valid SQL passed (Scenario 6), malicious SQL rejected (Scenario 7), non-whitelisted table rejected (Scenario 8), timeout handling (Scenario 9)
- [ ] 3.6 Update verification.md §1 rows 6-9 with Verification Artifact names

## 4. pgvector Semantic Search

- [ ] 4.1 Implement embedding function that calls OpenAI text-embedding-3-small to vectorize user queries
- [ ] 4.2 Implement pgvector similarity search query (cosine similarity, configurable top-K, default 5)
- [ ] 4.3 Write tests: search returns relevant chunks (Scenario 10), empty corpus returns no results (Scenario 11)
- [ ] 4.4 Update verification.md §1 rows 10-11 with Verification Artifact names

## 5. NER Inference Integration

- [ ] 5.1 Implement HTTP client to call model-serving internal endpoint `/internal/v1/infer` with JWT forwarding
- [ ] 5.2 Implement fallback to base model (version 0) when no promoted model exists per ADR-008
- [ ] 5.3 Write tests: NER on retrieved chunks (Scenario 12), NER with no promoted model (Scenario 13)
- [ ] 5.4 Update verification.md §1 rows 12-13 with Verification Artifact names

## 6. RAG Orchestration

- [ ] 6.1 Implement three-source RAG orchestrator: call SQL → pgvector → NER in parallel, merge results
- [ ] 6.2 Implement system prompt that constrains LLM to tenant-scoped data and formats response with citations
- [ ] 6.3 Implement chat endpoint `POST /api/v1/tenants/{tid}/chat` with conversation_id handling
- [ ] 6.4 Write tests: entity count query (Scenario 1), document context query (Scenario 2), NER query (Scenario 3), existing conversation (Scenario 4), no auth returns 401 (Scenario 5)
- [ ] 6.5 Update verification.md §1 rows 1-5 with Verification Artifact names

## 7. Conversation CRUD

- [ ] 7.1 Implement `GET /api/v1/tenants/{tid}/chat/conversations` (list, ordered by most-recent-message)
- [ ] 7.2 Implement `GET /api/v1/tenants/{tid}/chat/conversations/{conv_id}` (get messages)
- [ ] 7.3 Implement `DELETE /api/v1/tenants/{tid}/chat/conversations/{conv_id}` (scoped to owner)
- [ ] 7.4 Write tests: list conversations (Scenario 14), get messages (Scenario 15), delete own conversation (Scenario 16), delete another's returns 404 (Scenario 17)
- [ ] 7.5 Update verification.md §1 rows 14-17 with Verification Artifact names

## 8. Guardrails

- [ ] 8.1 Implement source citation enforcement guardrail: reject responses with empty `sources` array, return fallback message
- [ ] 8.2 Implement blocked question type classifier: detect classification, content generation, summarization, cross-tenant, PII queries
- [ ] 8.3 Implement query complexity limiter: count required source lookups, reject if >3
- [ ] 8.4 Implement disclaimer injection: add `disclaimer` field to every response
- [ ] 8.5 Write tests: empty sources rejection (Scenario 20), blocked question (Scenario 21), complexity limit (Scenario 22), disclaimer field (Scenario 23)
- [ ] 8.6 Update verification.md §1 rows 20-23 with Verification Artifact names

## 9. Rate Limiting

- [ ] 9.1 Implement per-tenant rate limiter (sliding window, 60 req/min for internal API, 20 req/min for widget API)
- [ ] 9.2 Add rate limit response headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`)
- [ ] 9.3 Write tests: rate limit exceeded returns 429 (Scenario 18), rate limit headers on success (Scenario 19)
- [ ] 9.4 Update verification.md §1 rows 18-19 with Verification Artifact names

## 10. Widget API Key Management

- [ ] 10.1 Implement `POST /api/v1/tenants/{tid}/widget-keys` (generate UUID key with `ner_widget_` prefix, store SHA-256 hash)
- [ ] 10.2 Implement `GET /api/v1/tenants/{tid}/widget-keys` (list with key_prefix only)
- [ ] 10.3 Implement `DELETE /api/v1/tenants/{tid}/widget-keys/{key_id}` (revoke, set revoked_at)
- [ ] 10.4 Write tests: generate key (Scenario 27), list keys (Scenario 28), revoke key (Scenario 29), invalid key rejected (Scenario 30)
- [ ] 10.5 Update verification.md §1 rows 27-30 with Verification Artifact names

## 11. Widget JS File

- [ ] 11.1 Implement `GET /api/v1/public/widget.js` — serve hosted JS file with tenant-specific config
- [ ] 11.2 Implement widget JS: chat bubble UI, slide-over panel, message input, API call with widget key
- [ ] 11.3 Add CORS headers to widget JS endpoint (`Access-Control-Allow-Origin: *`)
- [ ] 11.4 Write tests: widget JS served with correct headers (Scenario 24), CORS preflight (Scenario 33)
- [ ] 11.5 Update verification.md §1 rows 24, 33 with Verification Artifact names

## 12. Widget Chat Endpoint

- [ ] 12.1 Implement `POST /api/v1/public/chat` — widget-specific chat endpoint authenticated via API key
- [ ] 12.2 Resolve tenant_id from API key, call same RAG pipeline as internal chat (single-turn, no conversation history)
- [ ] 12.3 Write tests: widget chat with valid key (Scenario 31), widget chat without key (Scenario 32)
- [ ] 12.4 Update verification.md §1 rows 31-32 with Verification Artifact names

## 13. Chat UI (Frontend)

- [ ] 13.1 Create `src/portal/app/(auth)/chat/page.tsx` with `<RequireAuth roles={["tenant_admin", "business_user"]}>`
- [ ] 13.2 Implement conversation sidebar component with list, "New conversation" button, delete with confirmation
- [ ] 13.3 Implement message thread component with optimistic send, loading indicator, auto-scroll
- [ ] 13.4 Implement source citation expansion panel (click to show source details)
- [ ] 13.5 Write tests: tenant admin access (Scenario 34), annotator blocked (Scenario 35), business user access (Scenario 41), new conversation (Scenario 36), load messages (Scenario 37), delete conversation (Scenario 38), send/receive message (Scenario 39), source expansion (Scenario 40)
- [ ] 13.6 Update verification.md §1 rows 34-41 with Verification Artifact names

## 14. Gateway Routes & CORS

- [ ] 14.1 Add gateway routes for chat-api service endpoints (`/api/v1/tenants/{tid}/chat/*`, `/api/v1/public/*`)
- [ ] 14.2 Add CORS configuration for widget endpoints (allow any origin, Authorization and Content-Type headers)
- [ ] 14.3 Write integration test: gateway proxies chat requests to chat-api

## 15. Verification & Evidence

- [ ] 15.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 15.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 15.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 15.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 15.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 15.6 Run `openspec validate sp-06-rag-chatbot --type change --strict` and confirm it exits clean before archive.
