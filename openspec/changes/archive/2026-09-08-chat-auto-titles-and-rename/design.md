## Context

Today `conversations.title` exists in the schema and is plumbed all the way through `ConversationSummary`/`ConversationDetail`/`ConversationCreateResponse` and into `ChatSidebar.tsx`, but nothing ever writes a non-null value — every conversation is created with `title=NULL` (`chat.py:158`) and never updated. The sidebar falls back to the literal string `"New conversation"` (`ChatSidebar.tsx:80`) for every item, so users cannot distinguish or find past chats. There is no rename endpoint at all.

The chat POST handler (`chat.py:49-124`) already has both branches needed to detect "this is the first message of a conversation": the `if conversation_id: ... else: conversation_id = uuid4(); INSERT INTO conversations ...` split at `chat.py:74-92`. The `else` branch is exactly the point where a title should be generated, since it only runs once per conversation.

## Goals / Non-Goals

**Goals:**

- Auto-generate a reasonable, short title from the user's first message with no added latency or external API cost on the chat request path.
- Let a user rename any of their own conversations via the UI.
- Reuse the existing `title` column and existing response schemas — no DB migration.

**Non-Goals:**

- LLM-generated/summarized titles (out of scope; see Open Questions for future revisit).
- Automatically re-titling a conversation after it already has a title (auto-title only fires once, on first message).
- Renaming another user's conversation, or any cross-tenant behavior.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-007-chatbot-architecture | Chat responses are a 3-source RAG pipeline; latency (P95 <10s) and LLM API cost are explicit concerns; every response must include guardrail/disclaimer machinery unchanged. | Title generation MUST NOT add a model call or meaningful latency to the `/api/v1/chat` request path, and MUST NOT interfere with the existing sources/guardrail/disclaimer response contract. This directly motivates the truncation-based (non-LLM) title strategy. |
| ADR-008-base-model-as-default | Governs NER model version fallback (version 0 base model). | Not applicable to this change — no NER inference involved in titling. Listed only to confirm no conflict. |

## Decisions

### Decision 1: Generate the title synchronously, in-process, from the first user message text

**Choice:** In the `chat()` handler's "new conversation" branch (`chat.py:87-92`), derive a title from `body.message` using a small pure function (e.g. `derive_conversation_title(message: str) -> str`) and pass it into the existing `INSERT INTO conversations (...)` statement instead of leaving `title` unset. No new async call, no new service dependency.

**Rationale:** The message text is already in hand at that point in the request; this is the cheapest possible place to compute a title, with zero added I/O.

**Alternatives considered:**
- Generate title via an LLM call (either dedicated or piggybacked on the RAG orchestrator's existing LLM client) — ruled out because it adds latency/cost to every first message and is unnecessary given ADR-007's explicit latency/cost concerns; revisit later if truncation proves too low-quality.
- Generate the title asynchronously (fire-and-forget after response) — ruled out as unnecessary complexity for a synchronous, cheap string operation; also would introduce a race with `list_conversations` reading a still-null title.

### Decision 2: Title derivation algorithm

**Choice:** Collapse whitespace in the first user message, strip leading/trailing punctuation, then truncate to a max of 60 characters at the nearest word boundary, appending `…` if truncated. If the resulting string is empty (e.g., message was only whitespace/punctuation), fall back to `"New conversation"`.

**Rationale:** Deterministic, fast, and produces a recognizable title for the overwhelming majority of real questions (which are naturally phrased and under 60 chars, or truncate sensibly).

**Alternatives considered:**
- Fixed hard character cutoff (no word boundary) — ruled out, produces mid-word truncation that looks broken.
- No truncation (store full message as title) — ruled out, sidebar layout assumes a short single-line title (existing `text-overflow: ellipsis` CSS already assumes this).

### Decision 3: Rename endpoint shape

**Choice:** `PATCH /api/v1/chat/conversations/{conv_id}` with body `{"title": "<1-100 chars>"}`, scoped by `user_id` exactly like the existing DELETE endpoint (`chat.py:233-260`): 404 if the conversation doesn't belong to the caller. Returns the updated `ConversationSummary`-shaped object (or 204 — see Open Questions).

**Rationale:** Mirrors the existing DELETE endpoint's ownership-check pattern exactly, minimizing new code paths and keeping the tenant/user scoping model consistent.

**Alternatives considered:**
- `PUT` full conversation replace — ruled out, overkill for a single-field update and inconsistent with typical REST usage for partial updates.
- Reusing the `POST /conversations` route with an id param — ruled out, conflates create and update semantics.

## Risks / Trade-offs

- [Truncation-based titles can be low-quality for very short or non-descriptive first messages (e.g., "hi", "?")] → Fallback to `"New conversation"` when the derived title is empty after stripping; acceptable since this matches current behavior for that edge case rather than regressing it.
- [Renaming a conversation to an empty or whitespace-only string] → Validate `title` server-side (min length 1 after trim, max 100 chars) and reject with 422, mirroring `ChatRequest.message`'s existing `Field(min_length=1, max_length=4000)` pattern.
- [Frontend rename UI must not clobber an in-flight message send for the same conversation] → Rename is a separate PATCH call updating only `conversations.title`; it doesn't touch `chat_messages` or the send-message flow, so no interaction is possible.

## Migration Plan

No DB migration required — `conversations.title` already exists and is nullable. Rollout is a single coordinated backend+frontend deploy:

1. Deploy backend change (title generation + PATCH endpoint). Backward compatible: existing conversations with `title=NULL` continue to render as "New conversation" in the (still-unchanged) old frontend.
2. Deploy frontend change (rename UI, PATCH call wiring).
3. No data backfill planned — pre-existing conversations keep `title=NULL` and display the placeholder until the user manually renames them. (Optional future backfill considered out of scope; see Open Questions.)

Rollback: revert both deploys independently; no schema change to undo.

## Open Questions

- Should existing (pre-change) conversations with `NULL` title be backfilled with a derived title from their first stored message? Proposing no (simpler, and titles for old conversations are lower value), but flagging for confirmation.
- Should the PATCH rename endpoint return `200` with the updated resource, or `204 No Content` like DELETE? Proposing `200` with the updated `ConversationSummary` fields so the frontend can trivially update local state without a second fetch.
- Revisit LLM-generated titles later if truncation-based titles prove insufficiently descriptive in practice — would need to reopen ADR-007's latency/cost trade-off discussion.
