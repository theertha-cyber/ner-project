## 1. Chart contract and validation

- [x] 1.1 Add `ChartPayload` and `ChartSeries` pydantic models to `src/chat_api/api/v1/schemas.py`: `chart_type` (Literal `bar`/`line`/`pie`), `title`, optional `x_label`/`y_label`, `categories: list[str]`, `series: list[ChartSeries]` where each series is `name` + `data: list[float]`. Reject empty `categories`, empty `series`, and any series whose `data` length differs from `categories` length via a model validator.
- [x] 1.2 Create `src/chat_api/services/chart_tool.py` exporting `RENDER_CHART_SCHEMA` in the OpenAI function-calling shape used by `ToolRegistry.export_schemas()` (`src/shared/retrieval/tools/registry.py:33-44`). The description must tell the model to call it only for a small set of categories or a series over a period, and to use values from the supplied data rather than composing its own. No tenant/schema parameter.
- [x] 1.3 In the same module, add `validate_chart_grounding(payload, sql_results)`: flatten every numeric value in `sql_results` (a `list[dict]` from `SQLGenerator.generate_and_execute`, values may be `Decimal`) into a candidate set, and require every value of every series to match one within a relative tolerance of 1e-6 (`math.isclose(rel_tol=1e-6)`), declared as a named module constant. The tolerance absorbs Decimal-to-float representation only — a value restated as a rounder figure must not match. Return the payload on success; on failure log the unmatched value and return `None`.
- [x] 1.4 Add `parse_chart_tool_call(tool_call, sql_results)` that parses the tool call's JSON arguments, builds `ChartPayload` (structural validation), then applies grounding validation. Any parse or validation failure returns `None` and logs — it must never raise into the generation path.
- [x] 1.5 Unit-test the tool contract and validation in `tests/test_chat_chart_tool.py`: well-formed payload accepted (scenario 5); length mismatch rejected (6); unknown `chart_type` rejected (7); all-values-present accepted (9); invented value rejected with the value logged (10); `Decimal` precision artifact accepted within tolerance — 120000.004 matched by 120000.0 (11); value restated as a rounder figure rejected — 143217 proposed as 143000 (12).

## 2. Two-stage generation in the graph

- [x] 2.1 Add `chart: dict | None` to `ChatState` in `src/chat_api/graph/state.py`.
- [x] 2.2 Add a chart-eligibility helper used by `generation_node`: eligible only when `state.get("sql_results")` is non-empty and the turn is an ordinary answer (not blocked, declined, or a clarification — turns that short-circuit never reach generation, so the check is on `sql_results` plus the absence of `pending_clarification`).
- [x] 2.3 Restructure `generation_node` in `src/chat_api/graph/nodes.py:483-545` into stage A / stage B. Stage A runs only for eligible turns: a non-streaming `chat.completions.create` with `tools=[RENDER_CHART_SCHEMA]`, `tool_choice="auto"`, wrapped in `measure_llm_call` under its own label (e.g. `chart_decision`) so its latency is attributable. Stage B is the existing streaming/non-streaming call, unchanged, with the stage A tool call and a synthetic tool-result message appended to `llm_messages` when a chart was produced.
- [x] 2.4 Ensure the non-eligible and declined paths reach the pre-change call with identical messages, `temperature`, `max_tokens`, `langsmith_extra`, and identical token-sink gating on non-empty sources. Any stage A exception or malformed tool call falls back to this path and logs.
- [x] 2.5 Clear the chart when `enforce_sources` replaces the reply, in the same step, and return `{"reply": ..., "sources": ..., "chart": ...}` from the node.
- [x] 2.6 Thread the chart through `RAGOrchestrator.execute` / `execute_with_clarification` / `execute_with_clarification_stream` return values so `src/chat_api/api/v1/chat.py` receives it. Leave `orchestrator.execute`'s widget call path returning no chart.
- [x] 2.7 Test generation behaviour in `tests/test_chat_chart_generation.py` with a mocked `llm_client`: tool offered for a turn with SQL rows (scenario 1); not offered and exactly one call made for a document-only turn (2); not offered for a clarification turn (3); not offered for a blocked turn (4); model declines and reply is identical to single-stage (8, 18); charted turn's stage B messages contain the tool call and result (19); stage A failure degrades to a text answer with a log (21); state chart absent for an ordinary turn (22) and present for a validated one (23); chart cleared on empty-sources fallback (13) and on retrieval-failure fallback (14).
- [x] 2.8 Extend `tests/test_chat_graph_topology.py`: the two existing short-circuit scenarios still pass unchanged (15, 16), and a charted turn executes the same node sequence in the same order as an uncharted one with no generation-node re-entry (17).

## 3. API contract and persistence

- [x] 3.1 Add `chart: ChartPayload | None = None` to `ChatResponse` in `src/chat_api/api/v1/schemas.py`, and add `chart` to the exclude set in `_response_payload` (`src/chat_api/api/v1/chat.py:164-174`) when None, following the `pending_clarification` precedent. Leave `WidgetChatResponse` untouched.
- [x] 3.2 Write Alembic migration `alembic/versions/048_chat_message_chart.py` (`down_revision = "047"`) adding nullable JSONB `chart` to `chat_messages`, applied to `tenant_template` and every existing tenant schema via `apply_to_all_tenant_schemas` — follow `033_chat_messages_response_time_ms.py`.
- [x] 3.3 Persist the chart in `_persist_turn_and_respond` (`chat.py:113-161`) on the assistant row only, serialized with `json.dumps` exactly as `sources` is; write null when absent.
- [x] 3.4 Add `chart` to the conversation detail SELECT and to `MessageResponse` (`schemas.py:120-128`), parsed tolerantly so rows written before the column existed return without a chart. Null the chart for user rows.
- [x] 3.5 Emit the chart as an SSE `chart` frame in `event_stream()` (`chat.py:230-257`) after the chart is known and before the first `token` frame, at most once per turn, and never for a turn whose reply the guardrail replaces. Keep the chart in the `done` payload.
- [x] 3.6 Test the response and persistence contract in `tests/test_chat_api_chart_response.py`: no-chart response omits the key entirely and is otherwise unchanged (scenario 24); charted response carries the payload with at least one citation (25); widget response carries no chart (26); chart survives conversation reload (31); chart-less conversations reload unchanged (32); pre-column rows read back cleanly (34).
- [x] 3.7 Extend `tests/test_chat_api_streaming.py`: no `token` event is emitted for the duration of the stage A call and the first `token` corresponds to stage B content (scenario 20); exactly one `chart` event before the first `token` (27); no `chart` event for an uncharted turn with unchanged `token`/`done` sequence (28); `done` repeats the chart (29); guardrail-replaced turn emits no `chart` event and no `chart` key in `done` (30).
- [x] 3.8 Add `tests/test_migration_048_chat_message_chart.py` following `test_migration_032_chat_message_feedback.py`: the column exists in `tenant_template` and in pre-existing tenant schemas after migration (scenario 33).

## 4. Portal rendering

- [x] 4.1 Add `recharts` to `src/portal/package.json` and install.
- [x] 4.2 Create `src/portal/src/components/chat/ChartRenderer.tsx`: a `ChartPayload` TypeScript type matching the backend field names exactly, and a component rendering `BarChart`/`LineChart`/`PieChart` inside Recharts' `ResponsiveContainer`. Colours must come from design tokens (`var(--...)`), never hex literals or Tailwind colour classes, per the `dark-theme-consistency` spec. An unrecognised `chart_type` or a series/category mismatch renders nothing, with no user-facing error.
- [x] 4.3 Add `chart?: ChartPayload` to the `Message` interface in `MessageThread.tsx:32-43` and render `<ChartRenderer>` between the markdown content and the citation section (near line 186-190). Render no container at all when the message has no chart.
- [x] 4.4 Add a `chart` branch to `dispatchFrame` in `src/portal/src/lib/chat-stream.ts:48-80` with an `onChart(payload)` callback, leaving unrecognised events silently ignored as today.
- [x] 4.5 Wire `onChart` in the chat page (`src/portal/src/app/(auth)/chat/page.tsx`) to attach the chart to the streaming assistant message, and take the chart from the `done` payload as authoritative on completion. Include the persisted `chart` when mapping messages from a reloaded conversation.
- [x] 4.6 Test the renderer in `src/portal/src/components/chat/ChartRenderer.test.tsx`: bar chart shows title and four category labels (scenario 38); line and pie payloads render their respective chart (39); colours resolve from design tokens in both themes (40); responsive at the narrowest supported width with no horizontal overflow (41); unrecognised `chart_type` renders nothing with text and citations intact and no error (43).
- [x] 4.7 Extend `src/portal/src/components/chat/MessageThread.test.tsx`: existing send/receive and citation-expansion scenarios still pass (35, 36); a charted message renders the chart between text and citations (37); a chart-less message renders no chart container (42).
- [x] 4.8 Extend `src/portal/src/lib/chat-stream.test.ts`: a `chart` event invokes `onChart` and attaches to the in-flight message (scenario 44); the completion payload's chart is authoritative (45). Extend `src/portal/src/app/(auth)/chat/page.test.tsx` for a reloaded conversation rendering its persisted chart (46).

## 5. Sample data for verification

- [x] 5.1 Add a seed script or fixture set under the existing test/seed data location that ingests a handful of finance-style documents through the ordinary extraction pipeline — invoices or statements carrying an amount and a date each, spread across at least four periods so an aggregate query returns a chartable series.
- [x] 5.2 Confirm extraction populates `value_number` and `value_date` on the resulting `document_entities` rows, and that a question like "how much did we bill per quarter" produces a non-empty `sql_results` through the existing SQL path. This is the precondition for any chart to be possible at all — if it fails, the seed data is wrong, not the chart code.

## 6. Manual end-to-end check

- [x] 6.1 Run the chat API and portal against the seeded tenant from group 5, ask the question that resolves to the chartable aggregate, and confirm a chart renders with the text answer and citations.
- [x] 6.2 Capture light and dark screenshots of the rendered chart, and one at the narrowest supported width.
- [x] 6.3 Capture the raw SSE transcript for that turn showing the `chart` event ahead of the first `token`, and the `done` payload carrying the same chart.
- [x] 6.4 Reload the conversation and confirm the persisted chart renders identically.
- [x] 6.5 Record observed P95 latency for chart-eligible turns from the `chart_decision` measurement and compare against ADR-007's 10s budget. Note whether a pre-filter or a trimmed stage A prompt looks warranted — both were deferred pending this number.

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (`pytest tests/test_chat_*.py tests/test_migration_048_chat_message_chart.py` and `npm test` in `src/portal`).
- [x] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 7.6 Run `openspec validate chat-chart-generation --type change --strict` and confirm it exits clean before archive.
