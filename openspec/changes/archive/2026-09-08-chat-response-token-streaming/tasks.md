## 1. Graph streaming mode

- [x] 1.1 Add an optional `token_sink: asyncio.Queue | None` field to `ChatState` in `src/chat_api/graph/state.py`, documented alongside `session` as non-serializable runtime context.
- [x] 1.2 In `src/chat_api/graph/nodes.py`, add the streaming branch to `generation_node`: when `state.get("token_sink")` is set **and** `state.get("sources")` is non-empty, call the LLM with `stream=True`, push each non-empty content delta onto the sink, accumulate the deltas, and return `{"reply": <accumulated>, "sources": ...}` after `enforce_sources`. When the sink is absent or sources are empty, take the existing buffered path unchanged.
- [x] 1.3 Add a streaming entry point on `RAGOrchestrator` in `src/chat_api/services/rag_orchestrator.py` that accepts a token sink and threads it into `_run_graph`'s initial state. Return the same 5-tuple as `execute_with_clarification` so the response-assembly code is shared.
- [x] 1.4 Verifies scenario 8 — unit test in `tests/test_chat_api_streaming.py` asserting the LLM stub is called without `stream=True` when no sink is present and the terminal `reply` is the full content.
- [x] 1.5 Verifies scenario 9 — unit test in `tests/test_chat_api_streaming.py` asserting deltas land on the sink in order and the terminal `reply` equals their concatenation.
- [x] 1.6 Verifies scenario 10 — extend `tests/test_chat_graph_topology.py` to assert the node and edge sets are unchanged and the graph is acyclic with streaming available.

## 2. Streaming endpoint on chat_api

- [x] 2.1 Extract the conversation-setup block (existence check, history load, title derivation, new-conversation insert) from `chat()` in `src/chat_api/api/v1/chat.py` into a shared helper, and re-point the existing `chat()` handler at it with no behaviour change.
- [x] 2.2 Extract the persistence-and-response block (user row insert, assistant row insert, `updated_at` bump, commit, `ChatResponse` construction with the `pending_clarification` exclude) into a second shared helper, and re-point `chat()` at it with no behaviour change.
- [x] 2.3 Add `POST /api/v1/chat/stream` to `src/chat_api/api/v1/chat.py`: perform the tenant-context and rate-limit checks up front (returning 403/429 before any stream opens), then return a `StreamingResponse` with `media_type="text/event-stream"` and headers `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`, plus the existing rate-limit headers.
- [x] 2.4 Implement the stream generator: create the `asyncio.Queue`, launch `ainvoke` as a task, drain the queue into `event: token` frames, push the terminating sentinel in a `finally`, and have the drain loop also observe task completion so a raise cannot hang it.
- [x] 2.5 On successful task completion, persist via the 2.2 helper and emit exactly one `event: done` frame carrying the same payload the non-streaming endpoint returns (`pending_clarification` omitted when null). On exception, emit exactly one `event: error` frame with `code` and `message`, persist nothing, and close.
- [x] 2.6 Verifies scenario 1 — test in `tests/test_chat_api_streaming.py` asserting status 200 and the `Content-Type`, `Cache-Control`, and `X-Accel-Buffering` headers.
- [x] 2.7 Verifies scenario 2 — test asserting an unauthenticated `POST /api/v1/chat/stream` returns 401 with no event-stream body.
- [x] 2.8 Verifies scenario 3 — test asserting a rate-limited request returns 429 with `Retry-After` and no event-stream body.
- [x] 2.9 Verifies scenarios 4 and 7 — test with a scripted delta LLM asserting the event sequence is `token, token, token, done`, no `error`, and that the concatenated deltas equal the `done` `reply`.
- [x] 2.10 Verifies scenarios 5 and 33 — test issuing the same question to both endpoints with one scripted LLM and asserting `reply`, `sources`, `answer_kind`, `model_version`, `disclaimer` are equal and the payload key sets match.
- [x] 2.11 Verifies scenario 6 — test asserting the parsed `done` data has no `pending_clarification` key on a turn that produces none.
- [x] 2.12 Verifies scenarios 11 and 12 — test with a slow-retrieval stub and delayed deltas asserting zero `token` frames before the first LLM delta, and that `done` has not arrived when the first `token` is observed.
- [x] 2.13 Verifies scenarios 13, 14, and 15 — tests for the out-of-domain decline, the entity-resolution clarification, and the empty-sources turn, each asserting zero `token` frames and the expected `done` `reply` / `answer_kind` / `pending_clarification`.
- [x] 2.14 Verifies scenario 35 — test asserting the empty-sources streaming turn produces zero wire-level `token` frames and the guardrail fallback `reply`.
- [x] 2.15 Verifies scenarios 16 and 17 — tests querying `chat_messages` after a successful stream (exactly one assistant row matching `done`) and after a mid-stream raise (no rows added).
- [x] 2.16 Verifies scenario 18 — test with an LLM that raises after two deltas asserting the sequence `token, token, error` with no `done`.

## 3. Gateway pass-through

- [x] 3.1 Add `POST /api/v1/chat/stream` to `src/gateway/api/v1/chat_proxy.py` as a dedicated route that opens `httpx.AsyncClient` **inside** an async generator, uses `client.stream(...)`, and yields raw bytes as they arrive. Leave the shared `_proxy` helper untouched.
- [x] 3.2 Return the proxied stream as a `StreamingResponse` with `media_type="text/event-stream"` and `Cache-Control: no-cache`, `X-Accel-Buffering: no`, forwarding the upstream status code for non-200 responses.
- [x] 3.3 Verifies scenario 21 — test in `tests/test_chat_gateway_integration.py` with an upstream that pauses between frames, asserting the first frame is readable before the upstream completes.
- [x] 3.4 Verifies scenario 22 — test asserting the gateway response carries `Content-Type: text/event-stream` and `X-Accel-Buffering: no`.
- [x] 3.5 Verifies scenario 23 — run the existing gateway chat integration tests unchanged and confirm all pass.

## 4. Portal streaming client

- [x] 4.1 Add an SSE reader in `src/portal/src/lib/` that takes a `Response`, reads `response.body` with `getReader()`, buffers partial frames across chunk boundaries, parses `event:` / `data:` pairs, ignores comment lines, and invokes typed callbacks for `token`, `done`, and `error`.
- [x] 4.2 Add the `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` flag read (default enabled) and branch `handleSendMessage` in `src/portal/src/app/(auth)/chat/page.tsx`: streaming path posts to `/api/v1/chat/stream`, non-streaming path is the existing code unchanged.
- [x] 4.3 In the streaming path, on the first `token` clear `isThinking` and set `isStreaming` on the same placeholder message, then append each subsequent delta to that message's `content` in place.
- [x] 4.4 On `done`, replace the message's `content` with the authoritative `reply`, clear `isStreaming`, and attach `id` (`message_id`), `sources`, `answer_kind`, `model_version`; keep the existing new-conversation and `loadConversations()` follow-ups.
- [x] 4.5 Handle failure in a `finally` on the reader: on `error`, on an abrupt close with neither `done` nor `error`, or on a thrown parse error, remove the optimistic user message and the placeholder assistant message and show the existing error toast.
- [x] 4.6 Add `isStreaming?: boolean` to the `Message` interface in `src/portal/src/components/chat/MessageThread.tsx` and gate the citation chips and `MessageFeedback` on `!msg.isStreaming` in addition to the existing `!msg.isThinking` check. No other visual change.
- [x] 4.7 Verifies scenarios 36 and 37 — test in `src/portal/src/components/chat/MessageThread.test.tsx` (or a new streaming test alongside it) asserting: Thinking rendered before the first token; Thinking gone and first fragment shown on the first `token`; text appended on subsequent tokens; no citation chips and no rating control while `isStreaming`; full reply plus citations after `done`.
- [x] 4.8 Verifies scenarios 19, 20, and 39 — tests feeding an `error` frame and, separately, a stream that closes with neither `done` nor `error`, asserting no Thinking element remains, the optimistic user message is removed, and the error toast is shown.
- [x] 4.9 Verifies scenarios 26 and 27 — tests asserting the request URL is `/api/v1/chat/stream` with the flag unset, and `/api/v1/chat` with the flag set to `false` (Thinking persisting until the complete response).
- [x] 4.10 Verifies scenario 38 — run the existing `CitationCard.test.tsx` and `MessageThread.test.tsx` citation cases unchanged and confirm they pass.
- [x] 4.11 Bug found during live verification: `/api/v1/chat*` was the only API category `authFetch`'s `resolveUrl()` (`src/portal/src/lib/auth-fetch.ts`) left to fall through to the relative-URL default, which the portal's Next.js `rewrites()` proxy resolves — and that proxy buffers the entire SSE response before forwarding it (confirmed by timing raw chunk arrival with `httpx.stream(...).iter_raw()`: 0.15s to headers direct to chat_api/gateway vs. 7.4s to headers and exactly 2 chunks through the rewrite). Routed `/api/v1/chat*` straight to `GATEWAY_URL`, in the same branch as `/api/v1/admin`, `/api/v1/auth`, etc. Added a regression test to `auth-fetch.test.ts`, rebuilt and restarted the portal container, and re-verified live: browser network tab shows `POST http://localhost:8000/api/v1/chat/stream`, and the reply text was observed growing mid-turn across successive reads before finalizing.

## 5. Regression sweep

- [x] 5.1 Verifies scenarios 24, 28, 29, 30, 31, 32, and 34 — run `tests/test_chat_api_rag.py`, `tests/test_chat_api_conversations.py`, `tests/test_chat_api_guardrails.py`, and `tests/test_chat_api_entity_resolution.py` unchanged and confirm all pass.
- [x] 5.2 Verifies scenario 25 — run `tests/test_chat_api_widget.py` unchanged and confirm the widget endpoint still returns a single JSON body.
- [x] 5.3 Run the full Python suite (`pytest`) and the portal suite (`npm test --prefix src/portal`) and confirm no pre-existing test was modified to accommodate this change.
- [x] 5.4 Confirm no new runtime dependency was added to `pyproject.toml` or `src/portal/package.json`.
- [x] 5.5 Manually exercise the endpoint through the gateway with `curl -N` and record the inter-frame timing, confirming the first `token` frame arrives materially before the response completes.

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 6.6 Run `openspec validate chat-response-token-streaming --type change --strict` and confirm it exits clean before archive.
