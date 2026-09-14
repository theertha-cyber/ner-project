## Why

Every chat conversation in the portal displays as "New conversation" forever, with no way to tell them apart or rename them. Once a user has more than a couple of conversations, the sidebar becomes useless for finding past chats. Auto-generating a title from the first message, plus letting users rename conversations, is table-stakes for any multi-conversation chat UI.

## What Changes

- Backend: when the first user message is sent in a conversation (i.e. `conversation_id` was `null` on the request), automatically derive a short, human-readable title from that message and persist it to `conversations.title`.
- Backend: add `PATCH /api/v1/chat/conversations/{conv_id}` to let the owning user rename a conversation to an arbitrary (length-limited) title.
- Frontend: sidebar shows the auto-generated title once available (already wired to read `title`, currently always `null`).
- Frontend: add a rename affordance (edit icon) per conversation in `ChatSidebar`, opening an inline text input that calls the new PATCH endpoint and updates local state on success.
- Frontend: conversations created via "New conversation" still show a "New conversation" placeholder until the first message is sent and a title is generated.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `chat-api`: adds automatic title generation on first message and a rename (PATCH) endpoint for conversations.
- `chat-ui`: sidebar conversation items gain a rename control; title display now reflects the actual generated/renamed title instead of always falling back to a placeholder.

## Impact

- `src/chat_api/api/v1/chat.py` — title generation on first message, new PATCH route.
- `src/chat_api/api/v1/schemas.py` — new request/response models for rename.
- `src/chat_api/services/` — small helper to derive a title from a message (truncation-based, no new external LLM call required, since we already have the user's message text in hand).
- `src/portal/src/components/chat/ChatSidebar.tsx` — rename UI (edit icon, inline input).
- `src/portal/src/app/(auth)/chat/page.tsx` — wire rename handler, call PATCH, update conversations state.
- DB: no migration needed — `conversations.title` column already exists and is already nullable.

## Open Questions

- Title generation approach: simple truncation/cleanup of the first message (fast, free, deterministic) vs. an LLM-generated summary (better quality, adds latency/cost to the first turn). Proposal defaults to truncation-based generation for reliability and zero added latency; revisit if title quality proves insufficient.
- Max title length: proposing 60 characters, truncated at a word boundary with an ellipsis.
