## Why

SM-05 (Extraction Engine) extracts structured entities from tenant documents, but there is no mechanism to query that data conversationally, search source document context, or embed entity-aware Q&A into tenant's own applications. SM-06 bridges that gap — it delivers a three-source RAG chatbot (SQL over extracted entities, pgvector semantic search over document chunks, live NER inference) with an internal chat UI for tenant admins, an embeddable widget for external sites, guardrails against hallucination and data leakage, and conversation history per user. Without SM-06, the platform's core entity extraction payload is only accessible via raw APIs, limiting its value for non-technical users and external integrations.

## What Changes

- New **Chat API service** — `POST /api/v1/tenants/{tid}/chat` orchestrates three RAG sources (controlled SQL generation on extracted entity tables, pgvector similarity search on document chunks, real-time NER via model-serving), enforces guardrails (SQL validation, source citation, query complexity limits, blocked question types, disclaimers), and returns structured responses with citations.
- New **Conversation History** — persistence of chat messages per `{tenant, user, conversation}`, with conversation list and single-conversation retrieval endpoints.
- New **Embeddable Widget Infrastructure** — hosted JS widget file (`GET /api/v1/public/widget.js` per tenant), CORS-safe API endpoints authenticated via tenant-specific API keys (Bearer token, not user JWT), and a lightweight widget UI framework.
- New **Chat UI** — internal chat screen integrated into the portal (`/chat` route) for tenant_admin and business_user roles, with conversation sidebar, message thread, and source citation display.

## Capabilities

### New Capabilities

- `chat-api`: Core RAG chat endpoint that combines structured entity SQL search, pgvector semantic search, and live NER inference with guardrails (SQL validation, source citations, complexity limits, blocked question types, disclaimers); conversation CRUD and message persistence; rate limiting per tenant.

- `embeddable-widget`: Hosted JS widget served at a per-tenant public URL; lightweight chat UI for embedding in tenant's external websites; authenticated via tenant-specific API keys (not user JWT); CORS-safe endpoints; same RAG pipeline as internal chat but scoped to the widget's API key permissions.

- `chat-ui`: Internal chat screen at `/chat` in the portal SPA; conversation sidebar (new, list, delete); message thread with streaming-style response rendering; source citation expansion panel; role-gated (tenant_admin, business_user).

### Modified Capabilities

- *(none — this is the first chatbot capability)*

## Impact

- **New service**: `src/chat-api/` — FastAPI microservice for chat orchestration, SQL generation, pgvector search, NER integration, guardrail enforcement, conversation persistence, and widget API key management.
- **Database**: New `chats` and `chat_messages` tables in `tenant_template` schema; new `widget_api_keys` table in `public` schema; pgvector extension required on PostgreSQL for document chunk embeddings.
- **Dependencies**: openai (LLM calls), pgvector (semantic search), langchain or similar (RAG orchestration — optional, may build direct), pydantic (guardrail schemas).
- **Config**: `.env` entries for OpenAI API key (`OPENAI_API_KEY`), pgvector embedding dimension/model, rate limit settings, guardrail configuration (max query complexity, blocked question patterns).
- **Frontend**: New route `/chat` in `src/portal/app/(auth)/chat/page.tsx`; shared UI primitives reused from SP-01.
- **Gateway**: New routes for chatbot service endpoints; CORS configuration for embeddable widget origins.
- **Downstream**: No downstream consumers; SM-07 (Analytics & Reporting) may consume conversation metadata for chatbot usage analytics.

## Open Questions

- Should the chatbot use LangChain/LlamaIndex for RAG orchestration, or build the three-source pipeline directly? (Direct build gives more control over guardrail enforcement; LangChain provides faster iteration.)
- What embedding model should pgvector use for document chunk vectors? (Proposed: `text-embedding-3-small` from OpenAI; needs API key access.)
- Should chunking happen at document upload time (SM-02) or at chat time? (Proposed: at upload time, stored in a new `document_chunks` table with pre-computed embeddings.)
- What is the default rate limit per tenant? (Proposed: 60 requests/minute for internal API, 20 requests/minute for widget API.)
