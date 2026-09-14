## Context

Chat already has a conversation lifecycle, a first-send create/adopt flow, and a text-only send contract. The new requirement is to let users send attachments with chat turns, persist those attachments against exactly one conversation, and keep retrieval scoped to the owning conversation.

## Goals / Non-Goals

**Goals:**

- Accept attachment-bearing chat turns without adding a separate upload flow.
- Persist attachment metadata with the conversation created or selected by that send.
- Preserve existing text-only send behavior.

**Non-Goals:**

- CSV ingestion.
- Documents-library filtering.
- Hard-delete cleanup of derived artefacts.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-011 | Conversation-scoped chat attachments in the existing document model | Attachments belong to exactly one conversation and retrieval must stay conversation-scoped. |

## Decisions

### Decision 1: Keep attachments on the existing chat send path

**Choice:** Extend the chat API so a single send request can carry message text and staged attachment payloads.

**Rationale:** The requirement specifically avoids reserving a conversation during staging. A single send request keeps the conversation lifecycle and attachment persistence atomic.

**Alternatives considered:**
- Separate upload endpoint before send — ruled out because it would create server-side attachment state before the user commits the message.
- Client-only staging with a second persistence call — ruled out because it splits one logical send into two failure points.

### Decision 2: Use conversation-owned document rows

**Choice:** Store attachments as document rows tied to the conversation identifier already used by chat turns.

**Rationale:** ADR-011 already establishes conversation-scoped document ownership. Reusing the existing document model avoids a parallel attachment table and keeps retrieval and deletion aligned with chat ownership.

**Alternatives considered:**
- Separate attachment table — ruled out because it duplicates lifecycle logic.
- Ephemeral attachment storage only — ruled out because attachments must be retrievable later in the owning conversation.

### Decision 3: Preserve text-only requests unchanged

**Choice:** Keep the existing text-only chat request path valid when no attachments are present.

**Rationale:** This keeps current clients working while the new attachment path is introduced incrementally.

**Alternatives considered:**
- Replace the JSON request entirely — ruled out because it would force all callers to upgrade at once.

## Risks / Trade-offs

- [Multipart turn handling adds request-shape complexity] → Keep the JSON path for text-only sends and add tests for both shapes.
- [Conversation ownership checks could be bypassed when loading attachments] → Enforce ownership before attachment rows are loaded and verify cross-conversation fetches stay empty.
- [Existing chat regressions could be introduced by the new attachment branch] → Add explicit regression coverage for send-without-attachments.

## Migration Plan

1. Add attachment-aware request/response handling to the chat API.
2. Persist attachment metadata only after the conversation id is known.
3. Add tests covering first send, cross-conversation retrieval, and the unchanged text-only path.
4. Roll back by reverting the API and schema changes; no data migration is required for this capability.

## Open Questions

- None. ADR-011 already resolves the ownership model this change needs.
