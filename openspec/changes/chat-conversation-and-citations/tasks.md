## 1. Backend: Citation model and schemas

- [x] 1.1 Add `Citation` model to `src/chat_api/api/v1/schemas.py` with fields: `document_name`, `document_id`, `entity_type`, `entity_value`, `confidence`, `context_snippet`, `page_number`, `source_type` (internal). Keep existing `Source` model unchanged.
- [x] 1.2 Update `ChatResponse` to return list of `Citation` union — frontend renders both `Source` and `Citation` interchangeably via shared field names.

## 2. Backend: Conversation creation endpoint

- [x] 2.1 Add `POST /api/v1/chat/conversations` route in `src/chat_api/api/v1/chat.py` that creates an empty conversation row (id, tenant_id, user_id) and returns 201 with `{id, title, created_at}`.
- [x] 2.2 Add rate limiting to the new endpoint (reuse existing per-tenant rate limiter).

## 3. Backend: Citation enrichment layer

- [x] 3.1 Add `_enrich_citations()` method to `RAGOrchestrator` that collects all `document_id` values from sources, runs a single batch query joining `documents` and `entity_definitions` to resolve `document_name` and `entity_type_name`, and attaches them to each source.
- [x] 3.2 Wire `_enrich_citations()` into `execute()` after collecting all three source types but before building LLM context.
- [x] 3.3 Ensure enrichment handles edge cases: null document_id, missing entity_definitions row, empty sources list.

## 4. Backend: SQL generator prompt enhancement

- [x] 4.1 Update SQL generator system prompt in `src/chat_api/services/sql_generator.py` to instruct the LLM that when querying `extracted_entities`, it SHOULD JOIN with `documents` and return `d.filename AS document_name`.
- [x] 4.2 Verify the JOIN instruction uses SHOULD (not MUST) so non-entity queries remain unaffected.

## 5. Frontend: Unified CitationCard component

- [x] 5.1 Create `CitationCard` component in `src/portal/src/components/chat/CitationCard.tsx` that renders document_name as the primary heading, followed by entity_type / entity_value / confidence on a single line, with an optional expandable `context_snippet`.
- [x] 5.2 Replace `SourceCitation` in `MessageThread.tsx` with `CitationCard` — conditionally render `CitationCard` for `Citation` objects and fall back to old `SourceCitation` for legacy `Source` objects.
- [x] 5.3 Add loading/empty states to the citation area.

## 6. Frontend: New conversation button API integration

- [x] 6.1 Update `ChatSidebar.tsx` to call `onNew` asynchronously — add `loading` prop for disabled state during API call.
- [x] 6.2 Add `handleNewConversation` in `chat/page.tsx` that calls `POST /api/v1/chat/conversations`, appends result to conversation list, sets it active, and handles errors.

## 7. Frontend: Chat page input visibility fix

- [x] 7.1 Change render guard in `chat/page.tsx` from `{activeConvId || messages.length > 0}` to `{activeConvId}` — always show ChatInput when a conversation is active.
- [x] 7.2 Add "Send a message to start" placeholder text in the message area when conversation is empty.
- [x] 7.3 Auto-focus the ChatInput when a new conversation is created.

## 8. Tests

- [x] 8.1 Add tests for conversation creation endpoint: success, unauthorized, rate limited (`test_chat_api_conversations.py`).
- [x] 8.2 Add tests for Citation enrichment: document_name resolved, missing document handled, cross-schema entity type name (`test_chat_api_rag.py`).
- [x] 8.3 Add test for SQL generator prompt: entity query includes d.filename (`test_chat_api_sql.py`).
- [x] 8.4 Add component tests for CitationCard: renders document name, expands context, no toggle without context.
- [x] 8.5 Add component tests for ChatSidebar: loading state, API error handling.
- [x] 8.6 Retrieve and run existing test suite to confirm no regressions.

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record ⚠️ (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate chat-conversation-and-citations --type change --strict` and confirm it exits clean before archive.
