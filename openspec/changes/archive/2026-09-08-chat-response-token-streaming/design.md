## Context

A chat turn today is a single request/response round trip with four independent buffering points between the LLM and the browser:

| # | Buffer | Location |
|---|--------|----------|
| 1 | Non-streaming completion call — `await client.chat.completions.create(...)` returns only when the model has finished | `src/chat_api/graph/nodes.py:381` (`generation_node`) |
| 2 | `graph.ainvoke(state)` — LangGraph returns only the terminal state, so nothing inside a node is observable while the graph runs | `src/chat_api/services/rag_orchestrator.py:107` |
| 3 | `JSONResponse(content=response.model_dump(), ...)` — the whole body is serialized at once, twice: chat_api emits it, then the gateway re-buffers it with `resp.json()` | `src/chat_api/api/v1/chat.py:148`, `src/gateway/api/v1/chat_proxy.py:39` |
| 4 | `const data = await resp.json()` — the portal waits for the complete body before touching React state | `src/portal/src/app/(auth)/chat/page.tsx:204` |

The model's response first exists as a Python value at `response.choices[0].message.content` (`nodes.py:388`). It then travels: OpenAI/Azure client → `generation_node` → LangGraph state `reply` → `_run_graph` → `execute_with_clarification` → the `chat()` handler (which persists it and builds `ChatResponse`) → `JSONResponse` → gateway `_proxy` → gateway `JSONResponse` → Next.js `/api/:path*` rewrite → browser `fetch` → `setMessages`.

The UI's Thinking badge is a synthetic assistant message with `isThinking: true` pushed optimistically at send time (`page.tsx:183-190`) and replaced wholesale when the response lands. It is not driven by any signal from the model.

Constraints shaping this design:

- The graph must stay acyclic and its topology unchanged — the `chat-orchestration-graph` capability requires routing to be a pure function of state, never model-decided.
- Guardrails must keep their current authority. In particular `GuardrailService.enforce_sources` can replace the model's reply with a fallback string; that decision cannot be made after tokens have already been shown to the user.
- The embeddable widget (`/api/v1/public/chat`) and any non-browser consumer must keep working against the existing non-streaming endpoint.
- The stack uses the raw `AsyncOpenAI` / `AsyncAzureOpenAI` clients, not LangChain chat models. LangGraph's `astream_events` therefore has no LLM token events to surface.

## Goals / Non-Goals

**Goals:**

- The Thinking badge disappears on the first generated content token, not before.
- Content deltas reach the browser incrementally and are appended to the assistant bubble as they arrive.
- The final rendered message — text, citations, `answer_kind`, `model_version`, `message_id`, disclaimer — is identical to what the non-streaming path produces for the same turn.
- Exactly one assistant row is persisted, after generation completes, containing the full reply.
- A generation failure mid-stream ends the Thinking state and surfaces the existing error toast.
- The existing `POST /api/v1/chat` endpoint and its behaviour are untouched.

**Non-Goals:**

- Redesigning retrieval, orchestration, guardrails, entity resolution, or the graph topology.
- Streaming anything other than generated content — retrieval progress, plan traces, and tool activity are not surfaced.
- Streaming the widget endpoint.
- Persisting or resuming partial responses across a dropped connection.
- Client-side cancellation / stop-generation controls.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG pipeline (controlled SQL, pgvector search, NER inference) behind mandatory guardrails: source-citation enforcement, blocked question types, disclaimer in every response, per-tenant rate limiting, complexity limits. Target P95 < 10s. | Every guardrail must still hold on the streaming path. Source-citation enforcement in particular must be evaluated *before* the first token is emitted, since it can replace the reply entirely. The disclaimer must still accompany every response. Rate limiting must still be checked and its headers still returned. |
| ADR-009 System Admin Sets Training Hyperparameters | Training-domain only. | None. |
| ADR-010 Per-Entity-Type Dataset Threshold | Training-domain only. | None. |

ADR-001 through ADR-008 are all recorded as **Proposed**, not Accepted, so only ADR-009 and ADR-010 are formally in force. ADR-007 is nonetheless treated as binding here: its guardrail set is implemented in `src/chat_api/services/guardrails.py` and mirrored in the `chat-api` spec, and this change must not weaken it. No ADR needs revisiting.

## Decisions

### Decision 1: Server-Sent Events over a POST request, as a new sibling endpoint

**Choice:** Add `POST /api/v1/chat/stream` returning `text/event-stream` via FastAPI's `StreamingResponse`. Keep `POST /api/v1/chat` exactly as it is. The browser consumes the stream with `fetch` + `response.body.getReader()`, not the `EventSource` API.

**Rationale:** SSE is a one-way server-to-client text protocol, which is precisely the shape of this problem, and it needs no new infrastructure — `StreamingResponse` is already used in `src/analytics_service/api/v1/query.py`, and `httpx` already supports streaming responses on the gateway side. `EventSource` is ruled out despite being the canonical SSE client because it is GET-only and cannot set an `Authorization: Bearer` header, which every chat request needs; reading the SSE frames off a `fetch` body keeps the existing `authFetch` token/refresh path intact. Adding a sibling endpoint rather than content-negotiating on the existing one keeps the widget, existing tests, and any external consumer on a byte-identical contract and makes rollback a one-line client change.

**Alternatives considered:**

- WebSockets — bidirectional, needs connection lifecycle management, sticky sessions, and separate auth handling at the gateway. All cost, no benefit for a one-way stream.
- Chunked newline-delimited JSON (NDJSON) on the existing endpoint, negotiated by `Accept` — plausible, but overloading one route with two response shapes puts the widget and every existing test one header away from a different code path, and SSE's named events give a cleaner `token` / `done` / `error` split than positional JSON lines.
- LangGraph `astream` / `astream_events` — surfaces node-level state updates, not LLM tokens, because the stack calls the OpenAI client directly instead of through a LangChain `ChatModel`. Getting token events would mean adopting LangChain chat-model wrappers, which the `agentic-retrieval` spec explicitly forbids.

### Decision 2: Token sink in `ChatState`, drained by the endpoint

**Choice:** Add an optional `token_sink: asyncio.Queue | None` field to `ChatState`. The `/stream` handler creates a queue, launches `graph.ainvoke(state)` as an `asyncio.Task`, and drains the queue into SSE `token` frames while the task runs. `generation_node` reads `state.get("token_sink")`: when present it calls the LLM with `stream=True`, pushes each content delta onto the queue, and accumulates the full text; when absent it takes the existing non-streaming path unchanged. The node still returns `{"reply": ..., "sources": ...}` exactly as before, so every downstream consumer of the terminal state — persistence, `answer_kind` classification, `model_version` extraction — is untouched.

**Rationale:** This is the smallest change that makes an in-flight node observable without altering graph topology or node contracts. `ainvoke` still returns the same terminal state, so `execute_with_clarification`, the persistence block, and the response assembly in `chat.py` need no rework. Nodes other than `generation` never look at the field. With the sink absent, the node is byte-for-byte its current self, which is what keeps the non-streaming endpoint honest rather than merely "probably still fine".

**Alternatives considered:**

- Move generation out of the graph and have the endpoint call the LLM directly after running a truncated graph — splits the pipeline across two owners, duplicates the guardrail call, and breaks the "generation is a graph node" invariant the topology tests assert.
- A module-level callback registry keyed by conversation id — global mutable state, racy under concurrent turns, harder to test.
- Have `generation_node` return an async iterator as its `reply` — changes the node's contract and forces every state consumer to know whether the reply is a string or a stream.

### Decision 3: Guardrail source enforcement decided before the first token

**Choice:** In streaming mode, `generation_node` inspects `state["sources"]` before issuing the LLM call. If sources are empty, it does not stream at all: it takes the existing non-streaming branch, lets `enforce_sources` substitute the fallback reply, and returns. Tokens are emitted only when sources are non-empty, i.e. only when `enforce_sources` is guaranteed to pass the model's text through unchanged.

**Rationale:** `enforce_sources` (`src/chat_api/services/guardrails.py:97`) discards the model's reply and substitutes `FALLBACK_REPLY` when sources are empty. Streaming first and enforcing afterwards would show the user text that is then replaced — a visible contradiction and a direct violation of the "final rendered message is identical to the non-streaming result" requirement. The guardrail's only input is `state["sources"]`, which is already fully determined by `source_assembly_node` before `generation_node` runs, so the decision can simply be made earlier with no change in outcome. Users on this path see the Thinking badge until the `done` event — identical to today's behaviour, and correct: no generated tokens were ever going to be shown.

**Alternatives considered:**

- Stream regardless and overwrite the bubble on `done` — user-visible flicker, and text the guardrail exists to suppress would have been displayed.
- Buffer the first N tokens and decide then — the guardrail's input does not change during generation, so the buffering buys nothing.

### Decision 4: Terminal short-circuit paths emit no tokens and go straight to `done`

**Choice:** Guardrail declines (blocked question type, out-of-domain) and entity-resolution clarifications route to `END` before `generation_node` and therefore produce zero `token` events. The stream emits a single `done` event carrying the full `ChatResponse`, including `pending_clarification` when present. The client removes the Thinking badge on `done` just as it does on the first `token`.

**Rationale:** These replies are template strings, not model output; there is nothing to stream. The client's Thinking-clearing logic keys on "first `token` **or** `done`", which makes it structurally impossible to stay stuck in Thinking on any successful stream, regardless of which path the graph took.

**Alternatives considered:**

- Fake token frames by chunking the template reply — a cosmetic lie about where the text came from, and it would make "first token" a meaningless signal for tests.

### Decision 5: `done` carries the complete response payload; persistence stays where it is

**Choice:** The `done` event's data is the exact JSON body the non-streaming endpoint returns — `reply`, `sources`, `conversation_id`, `message_id`, `disclaimer`, `answer_kind`, `model_version`, and `pending_clarification` when non-null (omitted otherwise, matching the existing `exclude` behaviour). The handler persists the user and assistant rows and commits *before* emitting `done`, using the accumulated full reply, exactly as the non-streaming handler does. The client replaces its accumulated text with `done.reply` on receipt.

**Rationale:** Shipping the full reply in `done` rather than trusting the client's concatenation gives a single authoritative source for the rendered text and a natural assertion point for the "streamed text equals final text" test. Keeping persistence in the handler, after `ainvoke` resolves, means the write path is character-for-character the existing one: one user row, one assistant row, one commit, no partial state. Token frames are pure delivery and never touch the database.

**Alternatives considered:**

- Persist incrementally as tokens arrive — produces partial rows visible to concurrent readers and to conversation reload, and is explicitly out of scope.
- Omit `reply` from `done` and rely on the client's concatenation — saves a few hundred bytes and gives up the ability to detect a delivery gap.

### Decision 6: Gateway proxies the stream without buffering

**Choice:** Add a dedicated `/api/v1/chat/stream` route to `src/gateway/api/v1/chat_proxy.py` that uses `httpx.AsyncClient.stream(...)` inside an async generator and returns a `StreamingResponse` with `media_type="text/event-stream"`. The `httpx` client is created inside the generator so its lifetime spans the whole stream rather than being closed when the handler returns. Response headers set `Cache-Control: no-cache`, `Connection: keep-alive`, and `X-Accel-Buffering: no`. The generic `_proxy` helper, which calls `resp.json()`, is left alone and keeps serving every other chat route.

**Rationale:** The existing `_proxy` buffers by construction — `resp.json()` cannot return before the body is complete, and its `async with httpx.AsyncClient(...)` block closes the client before the response is consumed downstream. A separate route is a dozen lines and leaves the shared helper's behaviour unchanged for the seven routes that depend on it. `X-Accel-Buffering: no` is the standard opt-out for nginx-class proxies that would otherwise coalesce the stream and defeat the whole change.

**Alternatives considered:**

- Teach `_proxy` to detect streaming responses — one function serving two response models, with every existing chat route riding on the branch.
- Bypass the gateway from the browser — breaks the single-origin auth model the portal's `authFetch` and Next.js rewrites depend on.

### Decision 7: Client-side kill switch, server-side endpoint always available

**Choice:** The portal reads `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` (default: enabled). When disabled, `handleSendMessage` uses the existing non-streaming `POST /api/v1/chat` path, unchanged. The streaming endpoint itself is always mounted on chat_api and the gateway.

**Rationale:** Streaming has more failure modes in the network path than a JSON POST — intermediate buffering, idle timeouts, proxies that mishandle `text/event-stream`. A client-side flag makes rollback a portal env change rather than a backend redeploy, and it keeps the non-streaming code path exercised rather than dead. Gating the server endpoint too would add a flag with no rollback value, since a disabled client never calls it.

**Alternatives considered:**

- A server-side feature flag in `src/shared/config.py` — the client still needs to know, so this ends up being two flags to keep in sync.
- No flag — leaves no recovery short of a code change if an environment's ingress turns out to buffer.

### Decision 8: UI reuses the existing bubble; a `isStreaming` flag gates trailing chrome

**Choice:** `MessageThread` renders a message with `isThinking: true` as the existing Thinking badge, and any assistant message with content through the existing `ReactMarkdown` bubble. A new `isStreaming?: boolean` field suppresses the citation chips and the feedback control until `done` lands. On the first `token`, the page clears `isThinking` and sets `isStreaming` on the same message object, so the bubble is never unmounted and remounted.

**Rationale:** Requirement: no new visual design. Mutating one message in place means the badge-to-text transition is a content swap inside a bubble that is already on screen, which is what makes it read as seamless. Citations and the thumbs control are gated because their data (`sources`, `answer_kind`, `message_id`) does not exist until `done`; rendering them empty and then populating them would flicker. Markdown re-parsing on every delta is acceptable — replies are ~1KB and deltas arrive at human reading speed.

**Alternatives considered:**

- Keep the Thinking message and append a second bubble for streamed text — two bubbles for one turn, and the badge would have to be removed separately anyway.
- Render streamed text as plain text and switch to markdown on `done` — layout shift at the moment of completion, on every single turn.

### Decision 9: Errors after first token end the stream with an `error` event

**Choice:** The handler wraps the drain loop in `try/except`. On an exception from the graph task it emits `event: error` with `{"code", "message"}` and closes the stream; nothing is persisted. The client's reader treats `error`, and equally an unexpected stream close, as a failure: it removes the optimistic user message and the streaming assistant message and shows the existing error toast — identical to today's `else` and `catch` branches in `handleSendMessage`.

**Rationale:** Preserving the current error UX means the user sees the same toast and the same cleared thread regardless of protocol. The critical property is that the Thinking/streaming placeholder is removed on *every* stream termination — normal, errored, or abrupt — which is guaranteed by doing the cleanup in a `finally` on the client reader rather than only in the `error` branch. Since persistence happens only after a successful `ainvoke`, a mid-stream failure cannot leave a partial row.

**Alternatives considered:**

- Keep the partial text and mark it "incomplete" — introduces new UI states and diverges from the established error behaviour for no clear gain.
- Retry transparently — re-runs the whole RAG pipeline including retrieval, doubling cost and latency on a path the user can retry themselves.

## Risks / Trade-offs

- [An ingress or reverse proxy in a deployed environment buffers `text/event-stream`, so the browser sees the whole stream at once and the change is invisible in production while passing locally] → Emit `X-Accel-Buffering: no` and `Cache-Control: no-cache` from both chat_api and the gateway; verify first-token latency in each environment as an explicit acceptance step, not by inference from local behaviour.
- [The Azure OpenAI deployment rejects or ignores `stream=True`] → The streaming branch is entered only on the `/stream` route; a failure there surfaces as an `error` event and the flag reverts the portal to the non-streaming endpoint. Verified against the configured deployment before rollout.
- [Long-lived SSE connections hit an idle timeout when retrieval is slow, since no bytes flow between request start and first token] → Retrieval is bounded by `settings.retrieval_deadline_seconds` and the P95 target is under 10s, well inside default proxy idle timeouts. If an environment proves tighter, a periodic SSE comment heartbeat (`: ping`) is a contained follow-up that needs no protocol change.
- [Divergence between the streaming and non-streaming handlers as the endpoint evolves] → The conversation-setup and persistence blocks are extracted into shared helpers called by both routes, so the two handlers differ only in how they deliver the response.
- [`asyncio.Queue` drain and the graph task deadlock if the task raises before the sentinel is pushed] → The graph task is awaited with the drain loop watching for task completion, and the sentinel is pushed in a `finally`; the failure mode is covered by a test that raises from the generation node mid-stream.
- [Markdown re-parse on every token delta on a slow client] → Replies are small (~1KB, `max_tokens=1000`); if profiling shows cost, coalescing deltas on an animation frame is a client-only change.

## Migration Plan

1. Ship the backend first: `ChatState.token_sink`, the `generation_node` streaming branch, the orchestrator entry point, the `/api/v1/chat/stream` route, and the gateway proxy route. At this point nothing calls the new endpoint and behaviour is unchanged.
2. Verify the endpoint independently of the UI — `curl -N` against the gateway to confirm frames arrive incrementally and that the `done` payload matches the non-streaming endpoint's body for the same question.
3. Ship the portal changes behind `NEXT_PUBLIC_CHAT_STREAMING_ENABLED`, enabled by default.
4. Confirm in each deployed environment that first-token latency is materially below full-response latency; if not, the ingress is buffering and must be configured before the flag stays on.

**Rollback:** set `NEXT_PUBLIC_CHAT_STREAMING_ENABLED=false` and redeploy the portal. The non-streaming path is unchanged and fully exercised by the existing test suite. No database migration, no schema change, no persisted-data compatibility concern — a rollback affects delivery only.

## Open Questions

- Does any deployed environment place a buffering reverse proxy between the browser and the gateway? Determines whether step 4 of the migration plan is a formality or requires ingress configuration.
- Is a heartbeat needed for the pre-first-token window? Deferred until a real idle-timeout is observed rather than pre-emptively added.
- Should the embeddable widget eventually stream too? Out of scope here; the sink mechanism would extend to it unchanged if wanted later.
- No in-force ADR needs revisiting. ADR-007 remains accurate: this change alters response delivery, not the RAG architecture or its guardrails.
