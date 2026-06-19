# Verification Plan

**Change:** sp-06-rag-chatbot
**Generated:** 2026-06-18
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-api | RAG chat endpoint | Chat with simple entity count query | Given a tenant with extracted entities, when a Tenant Admin sends "How many organizations?" with null conversation_id, then response has status 200 with `reply`, `sources` (>=1), and `conversation_id` | - [ ] |
| 2 | chat-api | RAG chat endpoint | Chat with document context query | Given a tenant with document chunks, when a user asks about document content, then response references relevant chunks in `sources` with `document_id`, `chunk_index`, `relevance_score` | - [ ] |
| 3 | chat-api | RAG chat endpoint | Chat with NER query | Given a tenant with a promoted NER model, when a user asks about entities in text, then response includes NER sources with `entity_type`, `value`, `confidence` | - [ ] |
| 4 | chat-api | RAG chat endpoint | Chat with existing conversation | Given an existing conversation, when a user sends a message with that conversation_id, then message is appended and history context is included in LLM prompt | - [ ] |
| 5 | chat-api | RAG chat endpoint | Chat without authentication | Given no JWT, when POST is sent to chat endpoint, then response has status 401 | - [ ] |
| 6 | chat-api | SQL query generation and validation | Valid SQL query is executed | Given a natural language question, when the SQL generation produces valid SELECT, then the validation layer passes it and executes in read-only transaction, returning results | - [ ] |
| 7 | chat-api | SQL query generation and validation | Malicious SQL is rejected | Given an LLM-generated DROP TABLE query, when the validation layer inspects it, then the query is rejected and logged, SQL source is skipped | - [ ] |
| 8 | chat-api | SQL query generation and validation | Query with non-whitelisted table is rejected | Given a query referencing pg_authid, when validated, then it is rejected | - [ ] |
| 9 | chat-api | SQL query generation and validation | Query exceeds timeout | Given a query that runs >10s, when executed, then it is cancelled and SQL source is skipped | - [ ] |
| 10 | chat-api | pgvector semantic search | Semantic search returns relevant chunks | Given document chunks with embeddings, when RAG pipeline performs search, then top-K results are returned with `document_id`, `chunk_text`, `similarity_score` | - [ ] |
| 11 | chat-api | pgvector semantic search | Semantic search with empty corpus | Given no document chunks, when search is performed, then pgvector source is skipped | - [ ] |
| 12 | chat-api | NER inference for chat context | NER inference on retrieved chunks | Given retrieved document chunks, when sent to model-serving `/internal/v1/infer`, then response includes entities with `entity_type`, `value`, `confidence` included in chat sources | - [ ] |
| 13 | chat-api | NER inference for chat context | NER inference with no promoted model | Given no promoted model, when NER inference is called, then base model (version 0) is used with CoNLL entity types | - [ ] |
| 14 | chat-api | Conversation CRUD | List conversations for a user | Given a user with 3 conversations, when GETting conversations, then response has status 200 with 3 items each having `id`, `title`, `created_at`, `message_count` | - [ ] |
| 15 | chat-api | Conversation CRUD | Get conversation messages | Given a conversation with 5 messages, when GETting that conversation, then response has status 200 with 5 messages each having `role`, `content`, `sources`, `created_at` | - [ ] |
| 16 | chat-api | Conversation CRUD | Delete conversation | Given a conversation owned by user A, when user A DELETE it, then response has status 204 | - [ ] |
| 17 | chat-api | Conversation CRUD | Delete another user's conversation returns 404 | Given a conversation owned by user A, when user B DELETE it, then response has status 404 | - [ ] |
| 18 | chat-api | Rate limiting | Rate limit exceeded returns 429 | Given a tenant that exceeded 60 req/min, when a chat request is sent, then response has status 429 with Retry-After header | - [ ] |
| 19 | chat-api | Rate limiting | Rate limit headers on successful request | Given a tenant within limits, when a request succeeds, then response includes X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset | - [ ] |
| 20 | chat-api | Guardrail — source citation enforcement | Response without sources is rejected | Given a reply with no sources, when the guardrail layer inspects, then response is replaced with "I couldn't find relevant information" and event is logged | - [ ] |
| 21 | chat-api | Guardrail — blocked question types | Blocked question returns graceful decline | Given a user asks "Write an email", when processed, then response declines gracefully with empty `sources` | - [ ] |
| 22 | chat-api | Guardrail — query complexity limits | Overly complex question is simplified | Given a question requiring 4+ lookups, when complexity guardrail evaluates, then response asks to simplify and complexity score is logged | - [ ] |
| 23 | chat-api | Disclaimer in every response | Response includes disclaimer field | Given a successful chat response, when returned, then `disclaimer` field is present with standard text | - [ ] |
| 24 | embeddable-widget | Hosted widget JS file | Widget JS is served with correct headers | Given a valid tenant slug, when GETting widget.js with tenant param, then status 200 with `Content-Type: application/javascript` and `Access-Control-Allow-Origin: *` | - [ ] |
| 25 | embeddable-widget | Hosted widget JS file | Widget renders chat bubble on page | Given a page with widget script tag, when loaded, then a chat bubble appears bottom-right and clicking opens chat panel | - [ ] |
| 26 | embeddable-widget | Hosted widget JS file | Widget sends messages to chat API | Given an open widget with valid API key, when user types a message, then POST is sent to chat API with key in Authorization header and response is displayed | - [ ] |
| 27 | embeddable-widget | Widget API key management | Generate widget API key | Given an authenticated Tenant Admin, when POSTing to widget-keys, then status 201 with raw key starting `ner_widget_` | - [ ] |
| 28 | embeddable-widget | Widget API key management | List widget API keys | Given a tenant with 2 keys, when GETing widget-keys, then status 200 with 2 keys each having `key_prefix`, `created_at`, `last_used_at` (full key NOT returned) | - [ ] |
| 29 | embeddable-widget | Widget API key management | Revoke widget API key | Given an active key, when DELETE to widget-keys/{key_id}, then status 204 and key is immediately invalidated | - [ ] |
| 30 | embeddable-widget | Widget API key management | Chat with invalid widget API key | Given a revoked key, when widget sends chat request, then status 401 | - [ ] |
| 31 | embeddable-widget | Widget-specific chat endpoint | Widget chat with valid API key | Given a valid widget key, when POST to /api/v1/public/chat with key, then status 200 with `reply` and `sources` (no `conversation_id`) | - [ ] |
| 32 | embeddable-widget | Widget-specific chat endpoint | Widget chat without API key | Given no API key, when POST to /api/v1/public/chat, then status 401 | - [ ] |
| 33 | embeddable-widget | CORS configuration for widget endpoints | Widget endpoint responds to preflight | Given a browser from any origin, when OPTIONS to /api/v1/public/chat, then status 204 with Access-Control-Allow-Origin: * including Authorization and Content-Type headers | - [ ] |
| 34 | chat-ui | Chat screen route and access | Tenant admin accesses chat screen | Given an authenticated tenant_admin, when navigating to /chat, then chat screen renders with sidebar and message area, loading existing conversations | - [ ] |
| 35 | chat-ui | Chat screen route and access | Annotator accesses chat screen | Given an authenticated annotator, when navigating to /chat, then user is redirected to dashboard or sees access-denied | - [ ] |
| 36 | chat-ui | Conversation sidebar | New conversation button creates conversation | Given sidebar displayed, when clicking "New conversation", then a new empty conversation opens with "Send a message to start" | - [ ] |
| 37 | chat-ui | Conversation sidebar | Clicking conversation loads messages | Given a list of conversations, when clicking one, then message history is displayed and conversation is highlighted | - [ ] |
| 38 | chat-ui | Conversation sidebar | Delete conversation from sidebar | Given a conversation, when clicking delete icon, then confirmation appears and upon confirm conversation is deleted and removed from sidebar | - [ ] |
| 39 | chat-ui | Message thread display | Send message and receive response | Given a conversation selected, when typing and pressing Enter, then message appears optimistically, loading indicator shows, response appears, thread auto-scrolls | - [ ] |
| 40 | chat-ui | Message thread display | Source citations are expandable | Given an assistant message with sources, when clicking a citation, then it expands to show `document_id` or `entity_type` and relevant snippet | - [ ] |
| 41 | chat-ui | Role-gated chat access | Business user accesses chat | Given an authenticated business_user, when navigating to /chat, then chat screen renders normally | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | SQL validation layer | AI may implement a blocklist-based validator instead of the required whitelist-based approach (Decision 3), which is less secure | Review SQL validation code — confirm it uses whitelist of allowed tables/columns, not a blocklist of disallowed patterns |
| 2 | pgvector integration | AI may assume pgvector extension is already enabled and skip the migration step | Verify migration includes `CREATE EXTENSION vector;` and the `document_chunks` table with a `vector` column |
| 3 | Three-source RAG orchestration | AI may implement only one or two RAG sources (e.g., SQL only) and silently skip pgvector or NER | Review chat endpoint orchestration code — confirm all three sources are invoked and their results are merged into the response |
| 4 | Widget API key security | AI may store API keys in plaintext or return the full key on list endpoints | Verify keys are stored hashed (SHA-256) and list endpoint returns only `key_prefix`, not the full key |
| 5 | Chat UI role gating | AI may forget to gate the `/chat` route with `<RequireAuth roles={["tenant_admin", "business_user"]}>` | Check `chat/page.tsx` for role guard — annotator and system_admin should be blocked |
| 6 | Guardrail: source citations | AI may skip the guardrail layer entirely or implement it only as a comment/TODO | Verify there is executable code that inspects the response's `sources` array and replaces the reply if empty |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant Data Isolation via Separate DB Schemas | Chat data stored in `tenant_{uuid}` schemas; widget API keys in `public` schema | Confirm `chats` and `chat_messages` tables use tenant-scoped schema; `widget_api_keys` is in `public` schema |
| ADR-003 | Model Serving Topology | NER inference routes through model-serving internal endpoint `/internal/v1/infer` | Confirm chat-api calls model-serving at `/internal/v1/infer`, not directly loading models |
| ADR-007 | Chatbot Architecture — Full RAG with Guardrails | Three-source pipeline; SQL validation, source citations, complexity limits, blocked questions, disclaimers | Verify all five guardrails are implemented: SQL read-only validation, source citation enforcement, complexity limiter, blocked question classifier, disclaimer field |
| ADR-008 | Base Model as Default | When no fine-tuned model promoted, NER uses version 0 with CoNLL labels | Confirm NER inference fallback logic checks for promoted model and routes to base model if absent |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Test output showing RAG chat endpoint returns reply, sources, and conversation_id for entity count query (Scenario 1)
- [ ] Test output showing SQL validation layer accepts valid SELECT and rejects DROP TABLE queries (Scenarios 6-7)
- [ ] Test output showing pgvector search returns top-K results with similarity scores (Scenario 10)
- [ ] Test output showing NER inference via model-serving returns entities with type/value/confidence (Scenario 12)
- [ ] Test output showing conversation CRUD: list, get, delete (Scenarios 14-16)
- [ ] Test output showing cross-user conversation deletion returns 404 (Scenario 17)
- [ ] Test output showing rate limit exceeded returns 429 with headers (Scenario 18)
- [ ] Test output showing guardrail blocks response without sources (Scenario 20)
- [ ] Test output showing guardrail declines blocked question types gracefully (Scenario 21)
- [ ] Test output showing disclaimer field in response (Scenario 23)
- [ ] Test output showing widget JS served with correct headers and CORS (Scenario 24)
- [ ] Test output showing widget API key CRUD: generate, list, revoke (Scenarios 27-29)
- [ ] Test output showing widget chat endpoint works with valid key and rejects without (Scenarios 31-32)
- [ ] Test output showing CORS preflight for widget endpoints (Scenario 33)
- [ ] Screenshot showing chat UI with conversation sidebar and message thread (Scenario 34)
- [ ] Screenshot showing annotator blocked from /chat route (Scenario 35)
- [ ] Screenshot showing source citation expansion in chat UI (Scenario 40)

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] Migration plan reviewed — includes `CREATE EXTENSION vector;` step

### Edge Case Evidence

- [ ] SQL validation uses whitelist approach, not blocklist (Risk 1)
- [ ] pgvector migration includes extension creation (Risk 2)
- [ ] Chat endpoint invokes all three RAG sources (Risk 3)
- [ ] Widget API keys stored hashed; list endpoint returns only key_prefix (Risk 4)
- [ ] Chat UI route gated to tenant_admin and business_user only (Risk 5)
- [ ] Guardrail for source citations is executable code, not a TODO (Risk 6)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
| 9 | | | | | |
| 10 | | | | | |
| 11 | | | | | |
| 12 | | | | | |
| 13 | | | | | |
| 14 | | | | | |
| 15 | | | | | |
| 16 | | | | | |
| 17 | | | | | |
| 18 | | | | | |
| 19 | | | | | |
| 20 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** sp-06-rag-chatbot
**Proposal:** `openspec/changes/sp-06-rag-chatbot/proposal.md`
**Spec files reviewed:**
- specs/chat-api/spec.md
- specs/embeddable-widget/spec.md
- specs/chat-ui/spec.md

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
