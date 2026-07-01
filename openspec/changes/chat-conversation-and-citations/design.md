## Context

The chatbot UI at `/chat` renders a conversation sidebar and message area. Clicking "New conversation" calls `handleNewConversation` which sets `activeConvId = null` and `messages = []`. The render guard `{activeConvId || messages.length > 0 ? <ChatInput /> : "Select..."}` then evaluates to `false`, hiding the input entirely — the user is stuck.

On the backend, conversations are currently created only as a side effect of the `POST /api/v1/chat` endpoint when `conversation_id` is null. There is no dedicated conversation creation endpoint.

For citations: the `Source` model has a `source_type` discriminator (`sql`, `ner`, `document_chunk`). Each is rendered differently in the frontend `SourceCitation` component. The SQL source exposes raw JSON output. No source carries a human-readable document name. The `entities` table stores `entity_id` as a UUID referencing `entity_definitions.id` (public schema), so even SQL results don't show the entity type name without a cross-schema JOIN.

ADR-007 mandates "source citations with traceability" and "every response must include `sources` array with at least one citation" — but the current implementation falls short of meaningful traceability.

## Goals / Non-Goals

**Goals:**
- "New conversation" button immediately creates a backend conversation and shows a ready input
- Every citation always includes a human-readable document name (`document_name`)
- Unify all source types into a single `Citation` model rendered uniformly in the frontend
- Enrich SQL and NER sources with document names via a batch-resolution step
- Teach the SQL generator to join with `documents` table for entity queries
- Maintain backwards-compatible API responses for existing widget integrations

**Non-Goals:**
- Clickable document links in citations (requires document viewer route — future scope)
- Document preview or inline viewer within chat
- Cross-document entity deduplication (each citation maps to one entity-in-document)
- Caching citation results across conversations
- Modifying the widget chat API (widget continues with current `Source` model)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 | OpenSpec Spec-Driven Development Governance | All changes require spec delta, design, tasks, and verification artifacts |
| ADR-007 | Chatbot Architecture with Full RAG and Guardrails | Citations must be traceable to source documents; every response needs sources; guardrails must enforce citation presence |
| ADR-008 | Base Model as Default Inference Model (Version 0) | NER inference always has a fallback model — relevant for NER source citations |

## Decisions

### Decision 1: New dedicated `POST /api/v1/chat/conversations` endpoint

**Choice:** Add a lightweight endpoint that creates an empty conversation row and returns `{id, title, created_at}`. The frontend calls this on button click, sets the returned ID as active, and shows the input.

**Rationale:** The existing `POST /api/v1/chat` creates a conversation only as a side effect of sending a message. Using it to create an empty conversation would require sending a null/empty message, which violates the schema's `min_length: 1` constraint. A separate endpoint keeps creation and messaging orthogonal.

**Alternatives considered:**
- Modify `POST /api/v1/chat` to accept empty messages when `conversation_id` is null — violates REST semantics; the endpoint is for chat, not conversation management.
- Create conversation purely on frontend (optimistic UUID, no backend row until first message) — would break if user navigates away before sending; sidebar would show phantom conversations.

### Decision 2: Unified `Citation` model, with `Source` retained for widget backwards compatibility

**Choice:** Introduce a new `Citation` model with `document_name`, `entity_type`, `entity_value`, `confidence`, `context_snippet`, `page_number`. The internal chat API returns `Citation[]` as `sources`. The widget API continues to use the existing `Source` model. The `Citation` model carries a `source_type` field internally for debugging but the frontend ignores it.

**Rationale:** The widget embed API is consumed by external sites and should not break. The internal portal chat can evolve independently. Both models share the same JSON field name `sources` in the response, so the frontend treats them uniformly via a union type.

**Alternatives considered:**
- Modify `Source` in place — would break widget integration without a migration window.
- Two separate response fields (`citations` and `sources`) — forces every frontend to always handle both; adds unnecessary complexity.

### Decision 3: Citation enrichment via batch query in the orchestrator

**Choice:** After collecting all three source types, the RAG orchestrator runs a single batch query to resolve `document_id → document_name` and `entity_id → entity_type_name`. It uses `LEFT JOIN` against the `documents` table (tenant schema) and `entity_definitions` table (public schema) to fill in missing fields.

**Rationale:** A batch approach requires one round-trip regardless of how many sources exist. Individual lookups per source would be N queries. Joining across schemas is straightforward since the entity_definitions table is globally readable.

**Alternatives considered:**
- Force the SQL generator to always include `d.filename` — works for detail queries but not for aggregates (`COUNT(*)`).
- Enrich at the SQL generator level per-query — would need to parse generated SQL to extract entity_id references, which is fragile.

### Decision 4: Always render `ChatInput` when `activeConvId` is set

**Choice:** Change the render guard from `{activeConvId || messages.length > 0 ? <ChatInput /> : "..."}` to `{activeConvId ? <ChatInput /> : "..."}`. Once a conversation is active (even empty), the input is always visible. Show placeholder "Send a message to start" in the message area.

**Rationale:** Simplest fix for the bug. The input should only be hidden when there is no active conversation at all. An empty conversation is a valid state.

**Alternatives considered:**
- Keep the old guard but set a dummy message — hacky; would show a phantom bubble.
- Show input unconditionally — confuses the user when no conversation exists.

## Risks / Trade-offs

- [Citation enrichment adds an extra DB query per chat turn] → Single batch query with a 5-second timeout; if it fails, sources are returned without document names (graceful degradation).
- [Entity type name resolution requires cross-schema JOIN to `entity_definitions` in public schema] → The public schema is always accessible; the enrichment query uses schema-qualified table names.
- [Widget API continues with old `Source` model, creating two models to maintain] → The widget model is simpler and stable; changes to it are rare. Both models share the same basic fields.
- [New conversation endpoint could be abused to create unlimited empty conversations] → Rate limiting already applies per-tenant; the endpoint uses the same rate limiter as the chat endpoint.

## Migration Plan

1. Add `Citation` model to `schemas.py` — new model, `Source` unchanged.
2. Add `POST /api/v1/chat/conversations` endpoint — new route, no existing code changed.
3. Add citation enrichment method to `RAGOrchestrator` — new method, orchestrator.execute calls it before returning.
4. Update SQL generator prompt — modified system prompt string.
5. Replace `SourceCitation` with `CitationCard` in `MessageThread.tsx` — component replacement.
6. Update chat page render logic and button handler — minimal changes to `page.tsx`.
7. Add tests for new endpoint, enrichment, and citation model.

**Rollback:** The new endpoint can be removed without breaking the existing chat flow. The frontend can fall back to the old button behavior (local state clear) by reverting `page.tsx` and `ChatSidebar.tsx`.

## Open Questions

- Should citations include a confidence threshold filter? (e.g., only show entities with confidence > 0.7) — defer for now; show all, let the frontend decide formatting.
- The `entity_definitions.name` lookup across schemas — should we add a `entity_type_name` column to `extracted_entities` for performance? No — the enrichment layer query is fast enough; denormalization adds migration complexity.
