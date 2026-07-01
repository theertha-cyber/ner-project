## Why

The chatbot UI has a critical UX bug: clicking "New conversation" hides the message input instead of starting a new conversation, making it impossible to send the first message. Separately, source citations currently show raw SQL JSON and internal source type names (`sql`, `ner`, `document_chunk`) instead of human-readable document references, undermining the trust and traceability that the chatbot architecture (ADR-007) was designed to provide.

## What Changes

- **Fix "New conversation" button**: The button will immediately create a conversation via a new backend endpoint and show the input ready for typing, instead of clearing local state and hiding the input.
- **Unified citations**: Replace the three-way source-type display (`sql`, `ner`, `document_chunk`) with a single `Citation` model that always includes `document_name`, `entity_type`, `entity_value`, `confidence`, and optional context snippet. The frontend renders all citations uniformly.
- **Citation enrichment layer**: A new post-processing step in the RAG orchestrator that resolves `document_id → filename` for all sources via a batch query, so every citation has a document name.
- **SQL generator prompt update**: Instruct the LLM to include `d.filename` when generating queries against `extracted_entities`.
- **Always-visible input**: The chat input will always be rendered when a conversation is active (including newly created empty conversations).

## Capabilities

### New Capabilities

- (none — all changes modify existing capabilities)

### Modified Capabilities

- `chat-api`: new `POST /api/v1/chat/conversations` endpoint for empty conversation creation; `Source` model refactored to `Citation` with `document_name`, `entity_type`, `entity_value`, `confidence`, `context`, `page_number`; SQL generator prompt enhanced to join with `documents` table; orchestrator enriched with citation enrichment batch query; `ChatResponse.sources` remains backwards-compatible.
- `chat-ui`: "New conversation" button calls backend API instead of clearing local state; `ChatInput` always rendered when active conversation exists; `SourceCitation` component replaced with unified `CitationCard` that prominently shows document name; empty conversation state shows "Send a message to start" prompt.

## Impact

| Area | Impact |
|---|---|
| `src/chat_api/api/v1/schemas.py` | Add `Citation` model, deprecate `Source.source_type` display fields |
| `src/chat_api/api/v1/chat.py` | Add `POST /api/v1/chat/conversations` endpoint |
| `src/chat_api/services/sql_generator.py` | Update LLM prompt to include `d.filename` in entity queries |
| `src/chat_api/services/rag_orchestrator.py` | Add citation enrichment step after source collection |
| `src/portal/src/components/chat/MessageThread.tsx` | Replace `SourceCitation` with `CitationCard` |
| `src/portal/src/components/chat/ChatSidebar.tsx` | Add loading state for new conversation creation |
| `src/portal/src/app/(auth)/chat/page.tsx` | Wire button to API call, always show input when active |
| `tests/test_chat_api_conversations.py` | Add tests for new endpoint and Citation model |
| `tests/test_chat_api_rag.py` | Update for citation enrichment |
| ADR-007 | No changes needed — citations were already mandated |

## Open Questions

1. Should citations be clickable links to view the source document? (Future scope — requires document viewer route)
2. For aggregate queries (e.g., `COUNT(*)`), should we run a second detail query just for citations? (Decision: yes — the enrichment layer will fetch top-K entity-document pairs when SQL results lack per-row document data)
3. Entity type names (`organization`, `person`) are stored in `entity_definitions.name` (public schema) while `extracted_entities.entity_id` is a UUID — should we denormalize the type name into `extracted_entities`? (Decision: resolve via JOIN in enrichment layer for now)
