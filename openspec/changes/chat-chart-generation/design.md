## Context

The chat pipeline is a fixed LangGraph DAG — `guardrail → orchestrator → entity_resolution → retrieval_execution → prompt_assembly → source_assembly → generation` — compiled once at import. The structured half of retrieval already produces `sql_results` as a `list[dict]` (`SQLGenerator.generate_and_execute`), and `ContextAssembler` folds those rows into the prompt as text. The generation node then makes a single `chat.completions.create` call, with no `tools=` parameter, and either streams deltas into an `asyncio.Queue` token sink or returns the whole reply.

So the rows a chart needs already exist in state and already reach the model — they are simply never consumed as anything but prose. What is missing is a way for the model to hand back structure, a way to trust that structure, and a way to carry it to the client.

Two existing constraints shape the design more than anything else. First, `enforce_sources` can replace a reply *after* generation, which is why the streaming path only opens a stream when sources are already non-empty — a user must never see text the guardrail later retracts. A chart is subject to the same reasoning. Second, the `chat-orchestration-graph` spec states the graph contains no tool-calling nodes and no LLM-decided routing; that constraint was written during the LangGraph migration to keep behaviour identical to the pre-migration code, and this change narrows rather than removes it.

The frontend renders assistant messages as markdown (`react-markdown` + `remark-gfm`) with citation chips below. There is no chart library in the portal and no polymorphic content-block model on `Message` — messages are strings plus optional sources.

## Goals / Non-Goals

**Goals:**

- Let the generation model decide, per turn, whether the data it was given is worth drawing, and hand back a structured chart when it is.
- Never render a number the retrieved rows do not contain.
- Keep every wire change additive, so existing clients and the widget are untouched.
- Leave the non-chart path — the overwhelming majority of turns — byte-identical in behaviour and unchanged in latency.

**Non-Goals:**

- Charting in the embeddable widget. It is vanilla JS in a Python f-string with no build step and no SSE; it needs its own renderer and its own change.
- Any new data source, warehouse connector, or finance-specific modelling. Charts are drawn from rows the existing SQL path already returns. Sample documents are seeded for verification, but they are fixtures ingested through the ordinary pipeline, not a new source.
- User-driven chart controls — switching chart type, re-pivoting, drilling in, exporting. This change renders what the model proposed, nothing more.
- Fixing the widget's unsanitized `innerHTML` message rendering. Tracked separately.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated via separate Postgres schemas | The new `chart` column must be added to `tenant_template` and every existing tenant schema; the chart tool must take no tenancy parameter and derive nothing from outside the turn's own state |
| ADR-004-openspec-governance | Changes are spec-driven, specs precede implementation | This change ships as an OpenSpec change with delta specs; the `chat-orchestration-graph` topology requirement is amended rather than quietly contradicted |
| ADR-007-chatbot-architecture | Full RAG pipeline with guardrails; every response carries citations; responses without citations are rejected; P95 < 10s | A chart is evidence-bearing and inherits the citation requirement — it cannot accompany a fallback reply; the extra decision call must be weighed against the P95 budget |
| ADR-005-opencode-agent-boundaries | Agent permission boundaries | The chart tool performs no retrieval and no side effect; it is a return channel, not an action |

ADR-002 and ADR-006 are partially superseded by ADR-008 / ADR-009 / ADR-010 and concern model training and serving, not the chat path. ADR-003 and ADR-013 likewise do not constrain this design.

## Decisions

### Decision 1: Two-stage generation rather than tool-calling inside the stream

**Choice:** For chart-eligible turns, run a non-streaming decision call that offers `render_chart`, then run the existing generation call — streaming or not, unchanged — to produce the reply, with the tool call and a synthetic tool result appended to the messages. When the decision call returns no tool call, fall straight through to the existing path.

**Rationale:** Tool-call arguments arrive over a stream as fragments that must be accumulated by index and re-assembled into JSON before they can be parsed. Doing that inside the token loop means the loop is simultaneously forwarding user-visible deltas and buffering a partial tool call, with no clean way to know whether the model is producing prose, a chart, or both until it is well underway. Splitting the two removes that ambiguity entirely: stage one produces structure and no user-visible output, stage two produces prose exactly as it does today. The streaming contract — no token until sources are known non-empty — survives untouched, because stage two is the same call it always was.

**Alternatives considered:**
- *Single streaming call with `tools=` and delta accumulation* — ruled out: it entangles chart assembly with the token loop, and the guardrail's "no token before the reply is trusted" rule becomes much harder to reason about when the same stream carries both.
- *A separate graph node after generation that re-reads the reply and decides on a chart* — ruled out: it needs a second model call anyway, and the node would be inferring structure from prose the model already had the structured rows to produce directly.
- *Deterministic charting with no model involvement — inspect `sql_results` shape and chart anything two-column-numeric* — ruled out: it cannot tell a chartable breakdown from a coincidentally-two-column result, cannot title or label the chart, and would chart things nobody asked to see.

### Decision 2: Validate every chart number against the retrieved rows

**Choice:** Before a chart is accepted, flatten the turn's `sql_results` into a multiset of numeric values and require every value in every series to match one within a relative tolerance of 1e-6. Any unmatched value rejects the whole chart. Rejection drops the chart only — the reply, sources, and status are delivered as if no chart had been proposed — and is logged with the offending value.

The tolerance is deliberately near-exact. It exists to absorb `Decimal`-to-float representation and truncated trailing precision, nothing more: on a value of 143,217 it permits a discrepancy of about 0.14. Restating that value as 143,000 — the tidying a model does to make a number read nicely — is a rejection. The model is transcribing figures it was shown, so any difference large enough to be visible on an axis is a transcription error, and a bar drawn at a tidied number misstates the data it claims to depict.

**Rationale:** A chart reads as more authoritative than a sentence: a bar of the wrong height is a claim the user is unlikely to double-check against the citations. The model is being asked to transcribe numbers it was shown, which is exactly the operation where a fluent model quietly interpolates. Validation makes transcription errors non-events rather than silent misinformation, and it costs one pass over data already in memory. Dropping only the chart, rather than the whole answer, keeps a transcription slip from degrading a turn that is otherwise correct.

**Alternatives considered:**
- *Trust the tool call* — ruled out: it makes the most visually authoritative element of the answer the least verified, which inverts the guardrail posture ADR-007 sets for everything else.
- *Have the tool reference row indices instead of values, and let the backend read the numbers out* — genuinely appealing, and eliminates transcription error by construction. Ruled out for this change because it forces the model to reason about row ordinals rather than the values it was shown as text, which is a harder task and a more brittle prompt. Worth revisiting if validation rejects charts often in practice.
- *Warn but render* — ruled out: showing a chart the system knows is ungrounded is worse than showing none.

### Decision 3: Chart is bound to the same trust decision as the reply

**Choice:** When `enforce_sources` replaces the reply, clear the chart in the same step. A chart never accompanies a fallback, and the streaming path emits no `chart` event for such a turn.

**Rationale:** The chart and the reply are drawn from one body of evidence. If that evidence was judged too thin to support a sentence, it cannot support a graph of the same data — and a fallback message sitting above a confident-looking chart is a worse artifact than either alone. Clearing both at one point in the code also means there is a single place where "this turn is not trusted" is expressed, rather than two rules that can drift apart.

**Alternatives considered:**
- *Keep the chart, replace only the text* — ruled out on the reasoning above.
- *Evaluate chart trust independently of `enforce_sources`* — ruled out: two trust gates over the same evidence is a bug waiting to happen.

### Decision 4: Additive wire contract, with the chart as its own SSE event

**Choice:** Add optional `chart` to `ChatResponse`, omitted when absent via the existing `_response_payload` exclude set. On the stream, emit a `chart` event after the decision stage and before the first `token`, and continue to include the chart in the `done` payload.

**Rationale:** The exclude-when-None pattern is already the house convention for `pending_clarification` and `retrieval_status`, and it means clients that never look for a chart see a byte-identical payload. A distinct event, rather than folding the chart into `done`, lets the UI put the chart on screen while the answer is still being typed out — which is the right ordering, since the chart is the answer's shape and the prose is the commentary. Repeating it in `done` keeps clients that ignore the new event correct, and `chat-stream.ts` already ignores unrecognised event names without error, so the addition is safe for any client not updated in lockstep.

**Alternatives considered:**
- *Chart only in the `done` payload* — ruled out: the chart would pop in after the text finished streaming, which reads as a glitch.
- *Encode the chart into the markdown reply as a fenced block* — ruled out: it makes the chart a parsing problem for every consumer, and puts model-authored content on a path the renderer would have to interpret rather than validate.

### Decision 5: Recharts in the portal, persisted as JSONB

**Choice:** Add `recharts` to the portal and render bar/line/pie from the payload in a new `ChartRenderer` component, drawing colours from existing design tokens. Persist the chart as a nullable JSONB column on `chat_messages`, written in the same statement as `sources`.

**Rationale:** Recharts is React-native, composable, and needs no imperative canvas handling, which suits a component that renders inside an existing message list. `sources` already establishes the pattern for a structured payload on a chat message — same column type, same serialization, same tolerant read-back — so persistence adds a column rather than a mechanism. Design tokens rather than hardcoded colours is required by the `dark-theme-consistency` spec, and a chart is exactly the kind of component that tends to violate it.

**Alternatives considered:**
- *Chart.js or a canvas library* — ruled out: imperative lifecycle management inside a React list, and harder to theme from CSS custom properties.
- *Hand-rolled SVG* — ruled out for the portal, where a dependency is cheap; it is the likely approach for the widget precisely because a dependency there is not.
- *A separate `chat_message_charts` table* — ruled out: one chart per message at most, no independent lifecycle, no query pattern that wants it separate.

### Decision 6: Stage A receives the full assembled prompt

**Choice:** The decision call is made with the same `prompt_messages` the answer call uses — documents, structured rows, and conversation history — rather than a trimmed variant carrying only the rows.

**Rationale:** Deciding *whether* a chart belongs is a question about the user's intent, not just about the shape of the data. The same four rows warrant a chart for "how did profit move across the quarters" and do not for "was Q3 profitable" — only the question distinguishes them, and the conversation history sometimes carries the rest of the intent. Sending both stages the same context also means the reply written in stage B cannot contradict a chart decided in stage A on the basis of something stage A could not see. The token cost is real but bounded: the prompt is already assembled and already under a token budget, and the decision call's output is a small tool call rather than a full answer.

**Alternatives considered:**
- *Question plus rows only* — cheaper, and sufficient to build the chart once the decision is made. Ruled out for this change because it degrades the judgment half of the call, which is the half that matters; revisit if the measured cost of the full prompt proves significant.
- *A non-LLM heuristic on row shape* — already ruled out under Decision 1 for the same reason: shape does not reveal intent.

## Risks / Trade-offs

- [Every answer-kind turn with SQL rows pays an extra non-streaming model call, even when no chart results — against ADR-007's P95 < 10s budget] → No pre-filter is built up front: a heuristic that guesses which questions "aren't asking for a shape" would suppress valid charts on exactly the judgment call Decision 1 hands to the model. Instead the decision call is instrumented as its own measured LLM call (label `chart_decision`) from day one, so the added latency is attributable rather than inferred, and eligibility gating already keeps it off turns with no structured rows. A pre-filter remains the escape hatch if the measurement is bad — built against real numbers rather than an assumption.
- [Grounding validation is too strict and silently suppresses legitimate charts] → Tolerance is relative rather than absolute so magnitude does not skew it; every rejection is logged with the unmatched value, so over-rejection shows up as a log pattern rather than as user-invisible absence.
- [Grounding validation is too loose — a value coincidentally present in an unrelated column matches] → Accepted for this change. The check is a transcription guard, not a semantic one; it catches invented magnitudes, which is the failure mode that matters. Decision 2's row-index alternative is the upgrade path if coincidental matching proves real.
- [The model charts things nobody wanted, adding noise to answers] → Eligibility gating keeps the offer off clarifications, declines, and document-only turns; the tool description asks for restraint. If over-charting shows up in feedback, the lever is the tool description, not new code.
- [Charts render badly in dark theme or at narrow widths — the usual failure mode for a first chart component] → Specced explicitly as scenarios in `chat-ui`, tokens-only colours, and responsive-width verification.
- [Two renderers eventually — Recharts in the portal, something hand-rolled in the widget — drift apart] → The `ChartPayload` contract is defined once in the backend spec, so both renderers consume the same shape; drift would be visual, not semantic.

## Migration Plan

1. Ship the Alembic migration adding nullable JSONB `chart` to `chat_messages`, applied to `tenant_template` and fanned out to existing tenant schemas via `apply_to_all_tenant_schemas` (precedent: `033_chat_messages_response_time_ms.py`). The column is nullable with no backfill — pre-existing rows read back as chart-less, which is correct.
2. Ship the backend: chart tool, validation, two-stage generation, response field, SSE event, persistence. At this point charts are produced and delivered but nothing renders them; every existing client keeps working because the field and event are additive.
3. Ship the portal: `recharts`, stream handling, `ChartRenderer`.

**Rollback:** The backend is safe to revert independently of the migration — reverting it simply stops writing the column. The migration itself need not be reverted; a nullable unused column is inert. The portal can be reverted independently of both; it would ignore a `chart` event and an unread field. There is no ordering hazard in either direction.

## Open Questions

Resolved during requirements review (2026-09-15):

- **Grounding tolerance** — settled at a relative 1e-6, near-exact. See Decision 2: the check admits representation artifacts only, and rejects a value restated as a rounder figure.
- **Stage A context** — the decision call gets the full assembled prompt. See Decision 6.
- **Pre-filter for the extra round trip** — not built now. Instrument and measure first; see Risks.
- **Chartable data** — not left to chance. This change seeds sample documents carrying amounts with a date dimension, so the end-to-end check runs against a query that genuinely produces a chart rather than against fixtures alone.

Still open:

- Whether the tolerance holds up against real model behaviour. It is deliberately tight, so the failure mode to watch is charts being dropped for tidying rather than for invention. Every rejection is logged with the unmatched value; if the log fills with near-misses, the answer is a firmer instruction in the tool description, not a looser tolerance.
- What the measured cost of the full-prompt decision call actually is, which determines whether Decision 6's trimmed-prompt alternative is worth revisiting.
- None of the in-force ADRs need revisiting. ADR-007's guardrail posture is extended by this change rather than contradicted, and the topology constraint being amended lives in the `chat-orchestration-graph` spec, not in an ADR.
