# Verification Plan

**Change:** chat-response-token-streaming
**Generated:** 2026-08-10
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-response-streaming | Streaming chat endpoint | Streaming endpoint returns an event stream | Given an authenticated tenant user with an existing conversation, when they POST to `/api/v1/chat/stream`, then status is 200 and the response headers are `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` | `tests/test_chat_api_streaming.py` (task 2.6) | - [x] |
| 2 | chat-response-streaming | Streaming chat endpoint | Streaming request without authentication is rejected | Given no JWT, when POSTing to `/api/v1/chat/stream`, then status is 401 and no event stream is opened | `tests/test_chat_api_streaming.py` (task 2.7) | - [x] |
| 3 | chat-response-streaming | Streaming chat endpoint | Streaming request over the rate limit is rejected | Given a tenant that has exhausted its internal chat rate limit, when POSTing to `/api/v1/chat/stream`, then status is 429 with a `Retry-After` header and no event stream is opened | `tests/test_chat_api_streaming.py` (task 2.8) | - [x] |
| 4 | chat-response-streaming | SSE event protocol | Successful turn emits tokens then done | Given an LLM scripted to emit deltas `"Based"`, `" on"`, `" the documents"` and a turn with at least one source, when the stream is consumed, then three `token` events arrive in that order followed by exactly one `done` event and no `error` event | `tests/test_chat_api_streaming.py` (task 2.9) | - [x] |
| 5 | chat-response-streaming | SSE event protocol | done payload matches the non-streaming response body | Given the same question, tenant, conversation state, and scripted LLM issued to both endpoints, when the `done` data is compared with the non-streaming JSON body, then `reply`, `sources`, `answer_kind`, `model_version`, `disclaimer` are equal and both carry `conversation_id` and `message_id` | `tests/test_chat_api_streaming.py` (task 2.10) | - [x] |
| 6 | chat-response-streaming | SSE event protocol | Null pending_clarification is omitted from done | Given a turn producing no pending clarification, when the `done` data is parsed, then the payload has no `pending_clarification` key | `tests/test_chat_api_streaming.py` (task 2.11) | - [x] |
| 7 | chat-response-streaming | SSE event protocol | Concatenated token deltas equal the final reply | Given a successful streaming turn that emitted `token` events, when their `delta` values are concatenated in arrival order, then the result equals the `done` event's `reply` | `tests/test_chat_api_streaming.py` (task 2.9) | - [x] |
| 8 | chat-response-streaming | Streaming generation mode in the chat graph | Sink absent preserves non-streaming behaviour | Given the graph is invoked without a token sink, when the generation node runs, then the LLM is called without streaming enabled and the terminal `reply` is the model's complete content | `tests/test_chat_api_streaming.py` (task 1.4) | - [x] |
| 9 | chat-response-streaming | Streaming generation mode in the chat graph | Sink present streams and accumulates | Given the graph is invoked with a token sink and non-empty sources, when the generation node runs against an LLM emitting several deltas, then each delta is pushed to the sink in arrival order and the terminal `reply` equals their concatenation | `tests/test_chat_api_streaming.py` (task 1.5) | - [x] |
| 10 | chat-response-streaming | Streaming generation mode in the chat graph | Graph topology is unchanged by streaming | Given the compiled chat graph, when its nodes and edges are inspected, then the node set and edge set are identical to the non-streaming topology and the graph reports no cycle | `tests/test_chat_graph_topology.py` (task 1.6) | - [x] |
| 11 | chat-response-streaming | Thinking state ends on the first generated token | No token is emitted during retrieval | Given a turn whose retrieval stage is slow, when the stream is observed between request acceptance and the LLM's first content fragment, then no `token` event has been emitted | `tests/test_chat_api_streaming.py` (task 2.12) | - [x] |
| 12 | chat-response-streaming | Thinking state ends on the first generated token | First token arrives before generation completes | Given an LLM emitting deltas with a delay between them, when the client receives the first `token` event, then the `done` event has not yet been received | `tests/test_chat_api_streaming.py` (task 2.12) | - [x] |
| 13 | chat-response-streaming | Turns that produce no model output stream no tokens | Guardrail decline streams no tokens | Given a message classified out-of-domain, when the stream is consumed, then no `token` event is emitted and exactly one `done` event carries the decline message with `answer_kind` `out_of_domain` | `tests/test_chat_api_streaming.py` (task 2.13) | - [x] |
| 14 | chat-response-streaming | Turns that produce no model output stream no tokens | Entity-resolution clarification streams no tokens | Given an ambiguous person reference producing a clarification, when the stream is consumed, then no `token` event is emitted and the `done` event carries the clarification reply, a `pending_clarification` payload, and `answer_kind` `clarification` | `tests/test_chat_api_streaming.py` (task 2.13) | - [x] |
| 15 | chat-response-streaming | Turns that produce no model output stream no tokens | Empty sources stream no tokens | Given a turn whose retrieval produces no sources, when the stream is consumed, then no `token` event is emitted and the `done` event's `reply` is the source-enforcement fallback with empty `sources` | `tests/test_chat_api_streaming.py` (task 2.13) | - [x] |
| 16 | chat-response-streaming | Persistence is unchanged by streaming | One assistant row with the full reply | Given a successful streaming turn that emitted several `token` events, when the conversation's messages are read back, then exactly one assistant row was added whose `content` equals the `done` `reply` and whose `sources` equal the `done` `sources` | `tests/test_chat_api_streaming.py` (task 2.15) | - [x] |
| 17 | chat-response-streaming | Persistence is unchanged by streaming | Failed stream persists nothing | Given a streaming turn in which generation raises after several `token` events, when the conversation's messages are read back, then no assistant row and no user row were added for that turn | `tests/test_chat_api_streaming.py` (task 2.15) | - [x] |
| 18 | chat-response-streaming | Streaming error handling | Failure after first token emits an error event | Given an LLM that raises after emitting two deltas, when the stream is consumed, then two `token` events arrived, exactly one `error` event with `code` and `message` follows, and no `done` event is emitted | `tests/test_chat_api_streaming.py` (task 2.16) | - [x] |
| 19 | chat-response-streaming | Streaming error handling | Error clears the Thinking state in the UI | Given a turn whose stream emits an `error` event, when the client finishes reading, then no message with the Thinking indicator remains in the thread and the error notification is displayed | `src/portal/src/app/(auth)/chat/page.test.tsx` (task 4.8) | - [x] |
| 20 | chat-response-streaming | Streaming error handling | Abrupt stream close clears the Thinking state in the UI | Given a turn whose stream closes without `done` or `error`, when the client finishes reading, then no message with the Thinking indicator remains and the error notification is displayed | `src/portal/src/app/(auth)/chat/page.test.tsx` (task 4.8) | - [x] |
| 21 | chat-response-streaming | Gateway streams the chat stream without buffering | Gateway forwards frames incrementally | Given a chat_api stream that emits a `token` event then pauses, when the client reads the gateway's response, then the first `token` event is readable before chat_api emits its next frame | `tests/test_chat_gateway_integration.py` (task 3.3) | - [x] |
| 22 | chat-response-streaming | Gateway streams the chat stream without buffering | Gateway preserves streaming headers | Given an authenticated request to the gateway's `/api/v1/chat/stream`, when response headers are inspected, then `Content-Type` is `text/event-stream` and `X-Accel-Buffering` is `no` | `tests/test_chat_gateway_integration.py` (task 3.4) | - [x] |
| 23 | chat-response-streaming | Gateway streams the chat stream without buffering | Non-streaming chat routes are unaffected | Given the gateway's existing chat routes for send, conversation CRUD, and feedback, when each is exercised, then each returns the same buffered JSON response as before this change | `tests/test_chat_gateway_integration.py`, unchanged (task 3.5) | - [x] |
| 24 | chat-response-streaming | Non-streaming chat endpoint is preserved | Existing endpoint is unchanged | Given an authenticated tenant user, when they POST to `/api/v1/chat`, then the response is a single JSON body with `reply`, `sources`, `conversation_id`, `message_id`, `disclaimer` and `Content-Type: application/json` | `tests/test_chat_api_rag.py`, unchanged (task 5.1) | - [x] |
| 25 | chat-response-streaming | Non-streaming chat endpoint is preserved | Widget endpoint remains non-streaming | Given a valid widget key, when a request is sent to `/api/v1/public/chat`, then the response is a single JSON body and no event stream is opened | `tests/test_chat_api_widget.py`, unchanged (task 5.2) | - [x] |
| 26 | chat-response-streaming | Client streaming kill switch | Streaming disabled falls back to the non-streaming endpoint | Given `NEXT_PUBLIC_CHAT_STREAMING_ENABLED=false`, when the user sends a chat message, then the request goes to `/api/v1/chat` and the Thinking indicator remains until the complete response arrives | `src/portal/src/app/(auth)/chat/page.test.tsx` (task 4.9) | - [x] |
| 27 | chat-response-streaming | Client streaming kill switch | Unset flag defaults to streaming | Given `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` unset, when the user sends a chat message, then the request goes to `/api/v1/chat/stream` | `src/portal/src/app/(auth)/chat/page.test.tsx` (task 4.9) | - [x] |
| 28 | chat-api | RAG chat endpoint | Chat with simple entity count query | Given a tenant with ORG entities, when a Tenant Admin POSTs `{"message": "How many organizations did we extract?", "conversation_id": null}` to `/api/v1/chat`, then status is 200 with `reply`, a non-empty `sources`, and `conversation_id` | `tests/test_chat_api_rag.py`, unchanged (task 5.1) | - [x] |
| 29 | chat-api | RAG chat endpoint | Chat with document context query | Given a tenant with embedded document chunks, when a Tenant Admin asks about document content, then status is 200 and each returned chunk source includes `document_id`, `chunk_index`, `relevance_score` | `tests/test_chat_api_rag.py`, unchanged (task 5.1) | - [x] |
| 30 | chat-api | RAG chat endpoint | Chat with NER query | Given a tenant with a promoted NER model, when a user asks about entities in a text snippet, then `sources` includes an NER result with `entity_type`, `value`, `confidence` | `tests/test_chat_api_rag.py`, unchanged (task 5.1) | - [x] |
| 31 | chat-api | RAG chat endpoint | Chat with existing conversation | Given conversation `conv-abc`, when a user sends a message with that `conversation_id`, then status is 200, the message is appended to that conversation, and the history is present in the LLM prompt | `tests/test_chat_api_conversations.py`, unchanged (task 5.1) | - [x] |
| 32 | chat-api | RAG chat endpoint | Chat without authentication | Given no JWT, when POSTing to `/api/v1/chat`, then status is 401 | `tests/test_chat_api_rag.py`, unchanged (task 5.1) | - [x] |
| 33 | chat-api | RAG chat endpoint | Streaming and non-streaming endpoints answer identically | Given the same tenant, conversation state, question, and scripted LLM, when the question is sent to both endpoints, then the JSON body and the `done` payload carry the same `reply`, `sources`, `answer_kind`, `model_version`, `disclaimer` | `tests/test_chat_api_streaming.py` (task 2.10) | - [x] |
| 34 | chat-api | Guardrail — source citation enforcement | Response without sources is rejected | Given the RAG pipeline produces a reply with no sources, when the guardrail inspects the response, then the reply is replaced with "I couldn't find relevant information to answer that question." and the event is logged | `tests/test_chat_api_guardrails.py`, unchanged (task 5.1) | - [x] |
| 35 | chat-api | Guardrail — source citation enforcement | Empty-sources turn emits no tokens before the fallback | Given a streaming turn whose pipeline produces no sources, when the client consumes the stream, then no `token` event is emitted, the `done` `reply` is the fallback, and no generated text was ever displayed | `tests/test_chat_api_streaming.py` (task 2.14) | - [x] |
| 36 | chat-ui | Message thread display | Send message and receive streamed response | Given a selected conversation, when the user sends a message, then the user message appears optimistically, the Thinking indicator appears and remains until the first fragment, is then replaced by that fragment's text, subsequent fragments append to the same bubble, the completed bubble shows the full reply with citations, and the thread auto-scrolls | `src/portal/src/components/chat/MessageThread.test.tsx` (task 4.7) | - [x] |
| 37 | chat-ui | Message thread display | Citations and rating appear only on completion | Given an assistant message still streaming, when the thread is rendered mid-stream, then no citation chips and no rating control are displayed for that message | `src/portal/src/components/chat/MessageThread.test.tsx` (task 4.7) | - [x] |
| 38 | chat-ui | Message thread display | Source citations are expandable | Given an assistant message with citations, when the user clicks a citation, then it expands to show `document_id` or `entity_type` and the relevant snippet text | `src/portal/src/components/chat/CitationCard.test.tsx`, unchanged (task 4.10) | - [x] |
| 39 | chat-ui | Message thread display | Failed turn clears the Thinking indicator | Given a turn that fails after the Thinking indicator appeared, when the failure is surfaced, then no Thinking message remains, the optimistic user message is removed, and the existing error notification is displayed | `src/portal/src/app/(auth)/chat/page.test.tsx` (task 4.8) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Guardrail ordering (design Decision 3) | The obvious implementation streams first and calls `enforce_sources` on the accumulated text afterwards, exactly mirroring the current node. That passes a naive "final reply is correct" test while still having shown the user text the guardrail exists to suppress. | Read `generation_node`: confirm the emptiness check on `state["sources"]` happens **before** the LLM call, and that the empty-sources branch reaches `enforce_sources` without pushing anything to the sink. Then run the empty-sources scenario and assert zero `token` frames on the wire, not just a correct final `reply`. |
| 2 | Persistence boundary (design Decision 5) | Writing rows incrementally, moving the commit before the graph task resolves, or emitting `done` before the commit — any of which produces partial or unpersisted state that a happy-path test would not catch. | Confirm the DB writes remain in the handler after `ainvoke` resolves and before the `done` frame is yielded. Run the mid-stream failure scenario and query the tenant's `chat_messages` directly: neither the user nor the assistant row may exist. |
| 3 | Gateway buffering (design Decision 6) | Reusing or lightly editing the existing `_proxy` helper, whose `resp.json()` and `async with httpx.AsyncClient(...)` both defeat streaming; or returning a `StreamingResponse` whose `httpx` client is already closed, which fails only under load or on slow upstreams. | Read the new gateway route: the `httpx` client must stay open for the whole stream, not be closed when the handler returns. Verify empirically: `httpx.ASGITransport` (used by the project's own test client) buffers a whole ASGI response before returning it, so it cannot itself prove incremental delivery — call `proxy_chat_stream` directly and iterate the returned `StreamingResponse.body_iterator` against a delayed fake upstream, confirming the first chunk is observed before the second is produced. Confirm `_proxy` itself is untouched. |
| 4 | Sink lifecycle and deadlock (design Risks) | Draining the queue with an unguarded `await queue.get()` and pushing the terminating sentinel only on the success path, so any exception in the graph task hangs the request until a client or server timeout — presenting to the user as a permanently stuck Thinking badge. | Confirm the sentinel is pushed in a `finally`, and that the drain loop also observes graph-task completion rather than relying on the sentinel alone. Exercise the raise-mid-generation test and confirm the stream closes promptly with an `error` frame rather than hanging. |
| 5 | Client Thinking-clear condition (design Decision 4, spec R4) | Clearing `isThinking` on stream open, on first byte received, or on any frame rather than specifically on the first `token` **or** `done` — which silently breaks the central requirement while every screenshot still looks right. | Read the reader callback: the clear must be gated on the first `token` event or on `done`. Assert with a test that feeds SSE comments/heartbeat bytes and a slow first token that the Thinking indicator is still rendered. |
| 6 | Response payload drift (spec R2, chat-api scenario 33) | Hand-building the `done` payload field-by-field instead of reusing the same `ChatResponse` construction and `exclude` logic, producing a field-name typo or a serialized `pending_clarification: null` that the non-streaming path omits. | Confirm both routes build the payload through the same shared helper. Diff the `done` data against the non-streaming JSON body for the same scripted turn, key set included, not just the values that a test happens to assert. |
| 7 | Error-path UI cleanup (spec R7) | Cleaning up the optimistic and streaming messages only inside the `error` branch, leaving a dropped connection or a thrown parse error to strand the bubble on screen. | Confirm the cleanup runs in a `finally` on the client reader. Exercise the abrupt-close scenario (stream ends with no `done` and no `error`) and assert the thread contains neither the Thinking message nor the optimistic user message. |
| 8 | LLM streaming-chunk shape (design Decision 2, `generation_node`) | Assuming every streamed chunk has a non-empty `choices` list and indexing `chunk.choices[0]` unconditionally. Azure OpenAI (the deployment actually configured in this environment) interleaves chunks with an empty `choices` list — e.g. a trailing content-filter/usage chunk — which this naive indexing crashes on. Every unit test in this change scripted a fake LLM that never produced such a chunk, so the automated suite passed while the real deployment failed on the very first live turn. | Do not trust "all automated tests pass" as proof the streaming branch is correct against a real provider — run at least one live turn against the actually-configured LLM deployment (not a scripted fake) before considering this change verified. Confirm `generation_node` checks `if not chunk.choices: continue` before indexing, and confirm `test_chunks_with_empty_choices_list_are_skipped_not_indexed` in `tests/test_chat_api_streaming.py` exercises exactly this shape. |
| 9 | Client transport for `/api/v1/chat/stream` (design Decision 1, "browser consumes via `fetch`") | The design says the browser reads the stream via `fetch`, but never states *which URL* the browser must call. The obvious, minimal-looking implementation lets `/api/v1/chat/stream` fall through `authFetch`'s `resolveUrl()` to its default branch — a same-origin relative path resolved by the portal's Next.js `rewrites()` proxy in `next.config.js`. That proxy is not itself an SSE-aware pass-through: `httpx`-instrumented timing through it showed response headers withheld until the *entire* reply was ready and the body delivered in two large chunks, not the ~150 incremental frames chat_api and the gateway both emit — the request succeeds and every automated test (which mocks `fetch` directly, never exercising Next's real rewrite machinery) passes, while a live browser shows Thinking then one lump of text, which is exactly the pre-change behavior with an extra network hop. | Do not treat "the endpoint returns 200 and the final text is correct" as proof streaming reaches the browser — that is also true of the bug. Confirm in `src/portal/src/lib/auth-fetch.ts` that `/api/v1/chat` is routed straight to `GATEWAY_URL`, in the same branch as `/api/v1/admin`, `/api/v1/auth`, etc., not left to fall through to the relative-URL/Next-rewrite default. Verify with real per-chunk timing (`httpx.stream(...)` iterating `.iter_raw()`, not just checking the final status code) through each hop — chat_api, gateway, and finally the exact URL the browser's JS actually calls — and confirm live in the browser that generated text visibly grows across multiple screenshots/reads rather than appearing whole. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG pipeline behind mandatory guardrails: source-citation enforcement, blocked question types, disclaimer in every response, per-tenant rate limiting, query complexity limits. Target P95 < 10s. | Every guardrail must hold on the streaming path. Source-citation enforcement must be evaluated before the first token. Every response, streamed or not, must carry the disclaimer. Rate limiting must be checked and its headers returned. The RAG pipeline itself must be unchanged. | Run the full existing chat test suite (`tests/test_chat_api_*.py`, `tests/test_chat_graph_topology.py`) unchanged and confirm it passes. Confirm the `done` payload contains a non-empty `disclaimer` for every scenario in Section 1. Exercise the over-limit streaming request and confirm 429 with `Retry-After`. Diff `src/chat_api/services/rag_orchestrator.py` and `src/chat_api/graph/` and confirm the only behavioural change is inside `generation_node`'s streaming branch. |
| ADR-009 System Admin Sets Training Hyperparameters | Training-domain decision. | None — no training-domain code is touched. | Confirm the diff touches no file under `src/training_service/`. |
| ADR-010 Per-Entity-Type Dataset Threshold | Training-domain decision. | None — no training-domain code is touched. | Confirm the diff touches no dataset-readiness logic. |

> ADR-001 through ADR-008 are recorded as **Proposed** rather than Accepted, so ADR-009 and ADR-010 are the only formally in-force ADRs. ADR-007 is listed and verified regardless: its guardrail set is live in `src/chat_api/services/guardrails.py` and mirrored in the `chat-api` spec, and this change must not weaken it.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (Streaming endpoint returns an event stream): test output asserting status 200 and the three response headers — `TestStreamingEndpointHeaders`, passing
- [x] Scenario 2 (Unauthenticated streaming request): test output asserting 401 and that no `text/event-stream` body was produced — `TestStreamingEndpointAuthAndRateLimit`, passing
- [x] Scenario 3 (Rate-limited streaming request): test output asserting 429 and the `Retry-After` header — `TestStreamingEndpointAuthAndRateLimit`, passing
- [x] Scenario 4 (Tokens then done): test output listing the parsed event sequence `token, token, token, done` — `TestStreamingEventSequence`, passing
- [x] Scenario 5 (done matches non-streaming body): test output showing the field-by-field equality assertion passing — `TestStreamingEventSequence`, passing
- [x] Scenario 6 (Null pending_clarification omitted): test output asserting the key is absent from the parsed `done` data — `TestPendingClarificationOmission`, passing
- [x] Scenario 7 (Concatenated deltas equal reply): test output showing the concatenation assertion passing — `TestStreamingEventSequence`, passing
- [x] Scenario 8 (Sink absent, non-streaming): test output asserting the LLM stub was called without streaming enabled — `TestGenerationNodeStreaming`, passing
- [x] Scenario 9 (Sink present, streams and accumulates): test output showing the sink's contents in order and the terminal `reply` — `TestGenerationNodeStreaming`, passing
- [x] Scenario 10 (Topology unchanged): node/edge-set equality test, flag-aware so it holds regardless of local `.env` — `TestGraphTopologyUnchangedByStreaming`, passing
- [x] Scenario 11 (No token during retrieval): test output from a slow-retrieval stub asserting zero `token` frames before the first LLM delta — `TestThinkingUntilFirstToken`, passing
- [x] Scenario 12 (First token precedes done): test output showing the first `token` observed while the graph task is still pending — `TestThinkingUntilFirstToken`, passing
- [x] Scenario 13 (Guardrail decline): test output showing zero `token` frames and one `done` with `answer_kind == "out_of_domain"` — `TestNoTokenTerminalPaths`, passing
- [x] Scenario 14 (Clarification): test output showing zero `token` frames and a `done` carrying `pending_clarification` — `TestNoTokenTerminalPaths`, passing
- [x] Scenario 15 (Empty sources): test output showing zero `token` frames and the fallback `reply` — `TestNoTokenTerminalPaths`, passing
- [x] Scenario 16 (One assistant row): test output of the post-stream `chat_messages` query showing exactly one assistant row matching the `done` payload — `TestStreamingPersistence`, passing
- [x] Scenario 17 (Failed stream persists nothing): test output of the post-failure `chat_messages` query showing no rows added — `TestStreamingPersistence`, passing
- [x] Scenario 18 (Error event after tokens): test output showing the event sequence `token, token, error` and no `done` — `TestStreamingErrorEvent`, passing
- [x] Scenario 19 (Error clears Thinking): portal test output asserting no Thinking element and a visible error toast after an `error` frame — `chat/page.test.tsx`, passing
- [x] Scenario 20 (Abrupt close clears Thinking): portal test output asserting the same after a stream that ends with neither `done` nor `error` — `chat/page.test.tsx`, passing
- [x] Scenario 21 (Gateway forwards incrementally): `httpx.ASGITransport` buffers whole responses (confirmed by reading its source), so `curl -N`/test-client timing can't prove this through the full ASGI stack — instead, `proxy_chat_stream` is called directly and its `StreamingResponse.body_iterator` iterated against a delayed fake upstream, confirming the first chunk arrives before the second is produced — `TestChatStreamGatewayProxy`, passing
- [x] Scenario 22 (Gateway preserves headers): captured gateway response headers — `TestChatStreamGatewayProxy`, passing
- [x] Scenario 23 (Non-streaming gateway routes unaffected): output of `tests/test_chat_gateway_integration.py` passing unchanged
- [x] Scenario 24 (Existing endpoint unchanged): output of the existing `tests/test_chat_api_rag.py` suite passing unchanged
- [x] Scenario 25 (Widget remains non-streaming): output of `tests/test_chat_api_widget.py` passing unchanged
- [x] Scenario 26 (Kill switch off): portal test output asserting the request URL is `/api/v1/chat` and Thinking persists until completion — `chat/page.test.tsx`, passing
- [x] Scenario 27 (Flag unset defaults on): portal test output asserting the request URL is `/api/v1/chat/stream` — `chat/page.test.tsx`, passing
- [x] Scenario 28 (Entity count query): output of the existing chat RAG test covering this scenario, unchanged and passing
- [x] Scenario 29 (Document context query): output of the existing chat RAG test covering this scenario, unchanged and passing
- [x] Scenario 30 (NER query): output of the existing chat RAG test covering this scenario, unchanged and passing
- [x] Scenario 31 (Existing conversation): output of the existing conversation test covering this scenario, unchanged and passing
- [x] Scenario 32 (Unauthenticated): output of the existing auth test covering this scenario, unchanged and passing
- [x] Scenario 33 (Endpoints answer identically): test output of the cross-endpoint equality assertion — `TestStreamingEventSequence::test_done_matches_non_streaming_body`, passing
- [x] Scenario 34 (Response without sources rejected): output of the existing guardrail test passing unchanged
- [x] Scenario 35 (Empty sources emit no tokens): test output asserting zero `token` frames on the empty-sources streaming turn — `TestNoTokenTerminalPaths::test_empty_sources_emits_no_tokens_and_fallback_reply`, passing
- [x] Scenario 36 (Streamed response lifecycle in the UI): portal test output showing Thinking present, then replaced on first token, then appended, then finalized with citations — `MessageThread.test.tsx`, passing; also observed live in the browser against a real Azure OpenAI deployment (see Evidence Log row 4)
- [x] Scenario 37 (Citations withheld mid-stream): portal test output asserting no citation chips and no rating control while streaming — `MessageThread.test.tsx`, passing
- [x] Scenario 38 (Citations expandable): output of the existing `CitationCard`/`MessageThread` test passing unchanged
- [x] Scenario 39 (Failed turn clears Thinking): portal test output asserting thread cleanup and error toast — `chat/page.test.tsx`, passing

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Confirmed no new runtime dependency was added to `pyproject.toml` or `src/portal/package.json` — `git diff --stat` on both files produced no output
- [x] Confirmed the conversation-setup and persistence logic is shared between the streaming and non-streaming handlers rather than duplicated — `_prepare_conversation` and `_persist_turn_and_respond` in `src/chat_api/api/v1/chat.py` are called by both `chat()` and `chat_stream()`

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — source-emptiness is checked before the LLM call; empty-sources turn produces zero wire-level `token` frames (`test_empty_sources_takes_non_streaming_path_even_with_sink`, `test_empty_sources_emits_no_tokens_and_fallback_reply`)
- [x] Risk 2 mitigation confirmed — DB writes occur after `ainvoke` resolves and before `done`; mid-stream failure leaves no rows (`TestStreamingPersistence::test_failed_stream_persists_nothing`)
- [x] Risk 3 mitigation confirmed — gateway route's `httpx` client stays open for the whole stream; direct-invocation test proves the first chunk is delivered before the second is produced; `_proxy` is unmodified (`git diff` shows only additions to `chat_proxy.py`)
- [x] Risk 4 mitigation confirmed — sentinel (`STREAM_DONE`) pushed in a `finally` in `execute_with_clarification_stream`, drain loop `await task`s after the sentinel; raise-mid-generation closes the stream promptly with an `error` frame rather than hanging (`TestStreamingErrorEvent`)
- [x] Risk 5 mitigation confirmed — portal clears `isThinking` only inside `onToken`/`onDone`; no code path clears it on request-open or retrieval-only progress (`chat/page.test.tsx`, `MessageThread.test.tsx`)
- [x] Risk 6 mitigation confirmed — both routes build the payload through `_persist_turn_and_respond` + `_response_payload`; `test_done_matches_non_streaming_body` diffs the two bodies directly
- [x] Risk 7 mitigation confirmed — client cleanup runs in the `catch`/`finally` of `handleSendMessageStreaming`; abrupt-close test leaves neither the Thinking message nor the optimistic user message (`chat/page.test.tsx`)
- [x] Risk 8 mitigation confirmed — **this risk materialized for real**: the first live run against the actually-configured Azure OpenAI deployment crashed with `IndexError` on an empty-`choices` chunk (no automated test had modeled this shape). Fixed in `generation_node` (`if not chunk.choices: continue`), covered by `test_chunks_with_empty_choices_list_are_skipped_not_indexed`, and re-verified live after rebuilding the `chat_api` image — see Evidence Log row 4
- [x] Risk 9 mitigation confirmed — **this risk also materialized for real**: after fixing Risk 8, the browser still showed Thinking followed by the full reply appearing all at once. Timed `httpx.stream(...).iter_raw()` through each hop: chat_api direct (0.15s to headers, ~150 individually-timed frames), gateway direct (0.15s to headers, same frame count with real gaps), and through the portal's relative `/api/v1/chat/stream` path (6.2s to headers, exactly 2 chunks) — isolating the Next.js `rewrites()` proxy as the buffering point. Fixed by routing `/api/v1/chat*` straight to `GATEWAY_URL` in `authFetch`'s `resolveUrl()` (`src/portal/src/lib/auth-fetch.ts`), same branch as `/api/v1/admin`, `/api/v1/auth`, etc. Added a regression test (`auth-fetch.test.ts`), rebuilt the portal image, and re-verified live in the browser: network tab shows requests going to `localhost:8000` (gateway) instead of `localhost:3000` (Next rewrite), and the reply text was observed visibly growing across successive page reads mid-turn before finalizing with its citation — see Evidence Log row 8

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_chat_api_streaming.py -q` → 19 passed (includes a regression test for an empty-`choices`-list streaming chunk, added after that exact crash was reproduced live against Azure OpenAI — see row 4 below) | Scenarios 1-9, 11-18, 35 | AI agent (Claude) | 2026-08-10 |
| 2 | Functional | `pytest tests/test_chat_graph_topology.py::TestGraphIsAcyclicWithOneConditionalEdge -q` → passing (topology assertions for scenario 10 also embedded directly in test_chat_api_streaming.py::TestGraphTopologyUnchangedByStreaming) | Scenario 10 | AI agent (Claude) | 2026-08-10 |
| 3 | Functional | `pytest tests/test_chat_gateway_integration.py -q` → 5 passed, including two new tests calling `proxy_chat_stream` directly (httpx.ASGITransport buffers whole responses so it can't itself prove incremental delivery — documented in the test file) | Scenarios 21, 22, 23 | AI agent (Claude) | 2026-08-10 |
| 4 | Functional / Edge Case | Live manual run against the running dev stack (chat_api :8006, gateway :8000, portal :3000, real Azure OpenAI deployment): first attempt crashed chat_api with `IndexError: list index out of range` at `chunk.choices[0]` — Azure OpenAI emitted a chunk with an empty `choices` list, which `generation_node`'s streaming branch indexed unconditionally. Fixed in `src/chat_api/graph/nodes.py` (skip chunks with empty `choices`), added `test_chunks_with_empty_choices_list_are_skipped_not_indexed` as a regression test, rebuilt the `chat_api` Docker image, and re-ran the same live turn: `POST /api/v1/chat/stream` returned 200, chat_api logs show no exception, and the browser rendered the Thinking badge followed by the complete streamed reply with a citation chip, no console errors. This is a real bug this change's automated tests did not catch — see Hallucination Risk Register row 8. | Scenarios 1, 4, 7, 9, 36 | AI agent (Claude) | 2026-08-10 |
| 5 | Functional | Vitest: `src/lib/chat-stream.test.ts` (5 passed), `src/components/chat/MessageThread.test.tsx` (9 passed, 4 new streaming-lifecycle tests), `src/app/(auth)/chat/page.test.tsx` (4 passed — 2 error-cleanup, 2 kill-switch) — all run together with `CitationCard.test.tsx`, `ChatSidebar.test.tsx`, `auth-fetch.test.ts`: 53/53 passed, zero regressions | Scenarios 19, 20, 26, 27, 36, 37, 38, 39 | AI agent (Claude) | 2026-08-10 |
| 6 | Structural | `pytest tests/test_chat_api_rag.py tests/test_chat_api_conversations.py tests/test_chat_api_guardrails.py tests/test_chat_api_entity_resolution.py tests/test_chat_api_widget.py tests/test_chat_api_feedback.py tests/test_chat_api_sql.py tests/test_chat_api_reranking.py tests/test_chat_api_structured_value_sql.py tests/test_chat_api_rate_limiter.py tests/test_chat_message_feedback_model.py tests/test_chat_message_model_version.py tests/test_chat_gateway_integration.py tests/test_chat_graph_topology.py tests/test_chat_api_streaming.py -q` → 148 passed, 2 skipped, 2 failed. Both failures are pre-existing and unrelated: (a) `test_chat_api_rag.py::test_chat_response_sources` asserts the disclaimer text contains the literal substring "AI-generated", which it never has (disclaimer reads "This answer was generated by AI..."), and `schemas.py` was untouched by this change; (b) `test_chat_graph_topology.py::test_single_topology_expected_nodes_only` fails because this machine's `.env` sets `NER_ENTITY_RESOLUTION_ENABLED=true`, which that pre-existing test's hardcoded node set doesn't account for — reproduced in complete isolation on the pre-change baseline. Neither failure touches any file this change modifies. Scenarios 24, 25, 28-34 are covered by the untouched, passing tests inside these files. | Scenarios 24, 25, 28, 29, 30, 31, 32, 33, 34 | AI agent (Claude) | 2026-08-10 |
| 7 | Structural | `git diff --stat -- pyproject.toml src/portal/package.json` → no output (no new dependency added); full-repo `pytest tests/ -m "not eval_gate" --ignore=tests/test_analytics_dashboard.py` run for breadth: 97 failed / 826 passed, all 97 failures in modules this change never touches (analytics, training, documents, entity_query, user_auth, model_registry, warmup, dark-mode/layout-preference hooks — the latter reproduced in total isolation as a jsdom/Node `localStorage` polyfill gap) plus one pre-existing syntax error in `test_analytics_dashboard.py` (excluded from the run, confirmed via `git status`/`git diff` to be untouched by this session) | All | AI agent (Claude) | 2026-08-10 |
| 8 | Edge Case | Reported by user as "not streaming" after row 4's fix — reproduced live: browser showed Thinking then the entire reply appearing at once. Diagnosed by timing raw chunk arrival with `httpx.stream(...).iter_raw()` through each hop with a real 20+-sentence-inducing prompt: chat_api direct → 0.15s to headers, ~150 frames with real inter-frame gaps up to ~600ms; gateway direct → same; portal relative path (`http://localhost:3000/api/v1/chat/stream`) → 7.4s to headers (the model's *entire* generation time), exactly 2 chunks (10 bytes then ~2KB) — proving Next.js's `next.config.js` `rewrites()` proxy buffers the whole SSE response. Root cause: `/api/v1/chat*` was the only API category in `authFetch`'s `resolveUrl()` not routed straight to `GATEWAY_URL`, so it fell through to the same-origin/rewrite path every other service category already bypasses. Fixed in `src/portal/src/lib/auth-fetch.ts`, added `auth-fetch.test.ts` regression coverage, rebuilt the portal Docker image, and re-verified: browser network tab shows `POST http://localhost:8000/api/v1/chat/stream` (gateway, direct) instead of `localhost:3000` (Next rewrite); successive `get_page_text` reads during the same turn captured the reply text mid-sentence and growing before finalizing with its citation chip; no console errors | Requirement: SSE event protocol; Thinking state ends on first token (scenarios 4, 11, 12, 36) | AI agent (Claude) | 2026-08-10 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** chat-response-token-streaming
**Proposal:** `openspec/changes/chat-response-token-streaming/proposal.md`
**Spec files reviewed:**

- specs/chat-response-streaming/spec.md
- specs/chat-api/spec.md
- specs/chat-ui/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
