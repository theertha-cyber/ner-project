## Why

Every chat turn today blocks the user behind a fully-buffered LLM response: the portal shows the "Thinking..." badge from the moment the request is sent until the entire answer has been generated, serialized as JSON, proxied, and parsed. On multi-source RAG turns this is several seconds of a static placeholder with no evidence of progress, which reads as a hang. The generation LLM already emits tokens incrementally — the pipeline simply discards that incrementality at four separate buffering points. Delivering those tokens to the client is a delivery-layer change, not a pipeline redesign.

## What Changes

- Add a streaming chat endpoint `POST /api/v1/chat/stream` on chat_api that returns Server-Sent Events (`text/event-stream`) instead of a single JSON body. The existing `POST /api/v1/chat` endpoint is retained unchanged for the embeddable widget, non-browser API consumers, and rollback.
- `generation_node` gains a streaming mode: when the graph is invoked with a token sink present in state, the node calls the LLM with `stream=True`, forwards each content delta to the sink, and accumulates the full text. When no sink is present it behaves exactly as today. Guardrails, retrieval, orchestration, entity resolution, and graph topology are unchanged.
- The SSE stream carries three event types: `token` (one content delta), `done` (the complete `ChatResponse` payload — `reply`, `sources`, `conversation_id`, `message_id`, `disclaimer`, `answer_kind`, `model_version`, optional `pending_clarification`), and `error`.
- The gateway proxies `/api/v1/chat/stream` as a pass-through stream (`httpx` streaming request + `StreamingResponse`) rather than buffering with `resp.json()` like the other chat routes.
- The portal consumes the stream with `fetch` + `ReadableStream`, removing the Thinking badge on the first `token` event and appending subsequent deltas to the assistant message in place. Citations, feedback controls, and metadata attach on `done`.
- Persistence is unchanged: the assistant message row is written once, after generation completes, from the accumulated full reply. No partial rows are ever written.
- **Not breaking**: no existing endpoint, response shape, or persisted column changes.

## Capabilities

### New Capabilities

- `chat-response-streaming`: the end-to-end token-streaming delivery path — the SSE event protocol and its ordering guarantees, the streaming generation mode inside the chat graph, the gateway pass-through requirement, and the rule that streamed content must be byte-identical to the non-streamed reply.

### Modified Capabilities

- `chat-api`: the "RAG chat endpoint" requirement gains a streaming sibling endpoint; the "Guardrail — source citation enforcement" requirement must state that the empty-sources fallback is decided before any token is emitted, so a fallback reply is never contradicted by already-streamed text.
- `chat-ui`: the "Message thread display" requirement changes from "loading indicator until the response arrives" to "loading indicator until the first token, then progressive rendering".

## Impact

Code:

- `src/chat_api/graph/state.py` — additive `token_sink` field on `ChatState`.
- `src/chat_api/graph/nodes.py` — `generation_node` streaming branch.
- `src/chat_api/services/rag_orchestrator.py` — a streaming entry point that threads the sink into `_run_graph`.
- `src/chat_api/api/v1/chat.py` — new `/stream` route; the conversation-setup and persistence blocks in the existing `chat()` handler are extracted into shared helpers so both routes run identical logic.
- `src/gateway/api/v1/chat_proxy.py` — new streaming proxy route.
- `src/portal/src/lib/` — new SSE frame reader over `fetch`.
- `src/portal/src/app/(auth)/chat/page.tsx`, `src/portal/src/components/chat/MessageThread.tsx` — progressive rendering.

APIs: one added endpoint on chat_api and one on the gateway. No changes to existing contracts.

Dependencies: none added. FastAPI `StreamingResponse` is already used in `src/analytics_service/api/v1/query.py`; `httpx` streaming and the browser `ReadableStream` API are already available.

Systems: any reverse proxy or ingress in front of the gateway must not buffer `text/event-stream` responses.

Downstream consumers: the embeddable widget (`/api/v1/public/chat`) is untouched and stays non-streaming.

## Open Questions

- Whether an intermediate ingress (nginx / Azure Front Door) sits in front of the gateway in the deployed environments and buffers responses. Mitigated by emitting `X-Accel-Buffering: no`, but needs confirmation per environment. Tracked as a risk in verification.md.
- Assumption: the Azure OpenAI deployment in use supports `stream=True` on the chat completions API. Standard for all current chat deployments, but unverified against this tenant's specific deployment.
- Assumption: a client-side kill switch is wanted. This proposal includes an env-driven flag so the portal can fall back to the non-streaming endpoint without a redeploy of chat_api.
