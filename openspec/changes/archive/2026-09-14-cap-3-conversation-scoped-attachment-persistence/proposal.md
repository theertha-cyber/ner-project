## Why

Chat attachments need a backend contract that keeps uploaded files tied to exactly one conversation and keeps them out of the tenant-wide Documents library. The current chat and document flows already exist separately; this change closes the gap for conversation-scoped persistence and retrieval without altering existing non-chat document behavior.

## What Changes

- Persist chat attachments as conversation-owned document rows linked by `conversation_id`.
- Retrieve attachments only for the active conversation.
- Preserve existing text-only chat sends when no attachments are present.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `chat-api`: attachment-bearing turn contract, conversation-linked persistence, and conversation-scoped retrieval behavior.

## Impact

- `src/chat_api/api/v1/chat.py`
- `src/chat_api/api/v1/schemas.py`
- `src/chat_api/services/context_assembler.py` and adjacent retrieval glue
- database migration for `documents.conversation_id`

## Open Questions

- None. The decomposition and ADRs already define conversation ownership and hard-delete expectations.
