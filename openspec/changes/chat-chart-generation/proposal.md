## Why

When a chat question resolves to aggregate numeric data — "how much profit did we make last quarter", "how many contracts per vendor" — the chatbot answers with a paragraph of prose even though the answer is inherently a shape: a trend, a comparison, a breakdown. Users have to reconstruct that shape in their heads from a sentence. The pipeline already produces the structured rows a chart needs (`sql_results` from controlled SQL generation), and the generation LLM already sees them in the prompt; nothing consumes them as anything but text.

## What Changes

- The answer-generation step gains a `render_chart` tool the LLM may call when the data it has been given is genuinely chartable. Calling it is the model's judgment, not a keyword trigger.
- Generation becomes **two-stage** for eligible turns only: a non-streaming decision call that exposes the tool, then the existing (streaming) narrative call. Turns where the model declines to chart, and all turns with no SQL results, take today's single-call path with no behavioural change.
- Chart eligibility is gated: attempted only when `sql_results` is non-empty **and** the turn's outcome is an ordinary answer. Clarification requests, guardrail-blocked replies, and out-of-domain replies are never charted.
- A validation guardrail cross-checks every number in the proposed chart against `sql_results` before the chart is accepted. A chart that fails validation is dropped; the text answer is still delivered.
- If `enforce_sources` replaces the reply with a fallback (empty or untrusted sources), the chart is suppressed alongside it.
- `ChatResponse` gains an optional `chart` object, omitted entirely when absent. The SSE stream gains a `chart` event emitted before the first `token` event.
- The chart is persisted with the assistant's turn, so reopening a past conversation still renders it.
- The portal chat UI renders the chart as an interactive Recharts bar/line/pie beneath the answer text, sourced by the citation chips already shown for that message.

Sample documents carrying amounts with a date dimension are seeded as part of this change, so the feature can be verified end to end against a query that genuinely produces a chart.

Non-goals for this change: the embeddable widget (vanilla JS, no build step, non-streaming — charting it is a separate change), and any new data source. Charts are only possible where ingested entities already carry numeric values and a period/category dimension.

## Capabilities

### New Capabilities

- `chat-chart-generation`: the `render_chart` tool contract, when the model is offered it, the `ChartPayload` shape, the numeric-grounding validation guardrail, and the rules for dropping a chart while keeping the answer.

### Modified Capabilities

- `chat-orchestration-graph`: the generation node becomes conditionally two-stage and carries a `chart` value in graph state.
- `chat-api`: `ChatResponse` gains an additive optional `chart`; the SSE contract gains a `chart` event; the chart is persisted with the assistant message and returned on conversation reload.
- `chat-ui`: the message thread renders an interactive chart for assistant messages that carry one.

## Impact

- **Backend**: `src/chat_api/graph/nodes.py` (`generation_node`), `src/chat_api/graph/state.py`, `src/chat_api/api/v1/schemas.py`, `src/chat_api/api/v1/chat.py`, plus a new chart tool/validation module under `src/chat_api/services/`.
- **Database**: one Alembic migration adding a nullable JSONB `chart` column to `chat_messages`, applied to `tenant_template` and every existing tenant schema via `apply_to_all_tenant_schemas` (precedent: `alembic/versions/033_chat_messages_response_time_ms.py`).
- **Frontend**: `src/portal/package.json` gains `recharts`; `src/portal/src/lib/chat-stream.ts` handles a new event; `src/portal/src/components/chat/MessageThread.tsx` plus a new `ChartRenderer.tsx`.
- **Cost/latency**: one extra non-streaming LLM round-trip on every answer-kind turn that produced SQL results, including those that end up without a chart. Accepted deliberately in exchange for not having to accumulate tool-call deltas mid-stream.
- **Compatibility**: every wire change is additive and omitted-when-absent. Existing clients, the widget response schema, and the non-streaming `POST /api/v1/chat` contract are unaffected for turns without a chart.
- **Out of scope, tracked separately**: the widget's unsanitized `innerHTML` message rendering (`public.py:92-98`).

## Open Questions

Resolved during requirements review (2026-09-15):

- **How exact must a chart's numbers be?** Near-exact — a relative tolerance of 1e-6, which absorbs decimal-to-float representation but rejects a value restated as a rounder figure. A row value of 143,217 drawn as 143,000 is a rejection.
- **Will there be data to chart?** This change seeds sample documents carrying amounts with a date dimension, so the feature can be demonstrated end to end rather than only unit-tested.
- **What context does the decision call get?** The full assembled prompt, the same one the answer call receives — deciding whether a chart belongs is a question about the user's intent, not only about the shape of the rows.
- **Optimise the extra round trip now?** No. Instrument it, measure it, and add a pre-filter only if the measurement justifies one.

Still open:

- Whether the tight tolerance rejects charts in practice for tidying rather than invention. Rejections are logged with the unmatched value so this is observable; the remedy would be a firmer tool description, not a looser tolerance.
- The measured cost of the extra decision call against ADR-007's P95 budget, which determines whether a cheaper trimmed prompt or a pre-filter is worth building later.
