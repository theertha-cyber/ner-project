## Context

Chat messages (`tenant_template.chat_messages`) and conversations live in per-tenant Postgres schemas, provisioned via Alembic migrations that DDL against `tenant_template` and backfill live `tenant_<id>` schemas (`alembic/versions/010_chatbot_infrastructure.py`). No SQLAlchemy ORM models exist for tenant-scoped tables anywhere in the codebase (chat_api, gateway) — all access is raw `text()` SQL. The gateway's dashboard endpoint (`src/gateway/api/v1/dashboard.py`) already assembles a role-specific `DashboardData` payload per request by querying tenant tables directly; the tenant_admin variant currently includes a "Quota usage" side panel (`_tenant_quota_rows`) built from a generic `SideRow(label, val, pct, c)` shape rendered by `MetricsPanel.tsx`. Portal → gateway → chat_api chat traffic is a thin reverse-proxy (`chat_proxy.py`), so any new chat_api endpoint needs one matching proxy stub. `lucide-react` is already a portal dependency but not yet used inside chat components.

## Goals / Non-Goals

**Goals:**
- Persist one immutable rating (up/down) per eligible assistant message — no overwrite, no soft-update, duplicate submissions rejected — scoped to the rating business user, following existing tenant-schema/raw-SQL conventions.
- Explicitly define and enforce which assistant messages are eligible for feedback (`answer_kind = "answer"` only), so clarification prompts, guardrail declines, and out-of-domain replies are structurally excluded, not merely undocumented.
- Persist enough model-identity metadata on each assistant message (`model_version`, reusing the identifier already returned by model-serving/`extraction_runs`) that future analytics can attribute ratings to the model version that produced the response.
- Surface the rating control in chat UI, gated to `business_user` role and message eligibility, disabled after rating.
- Replace the tenant_admin "Quota usage" dashboard panel with a dedicated Response Quality card — a status (`healthy`/`monitor`/`needs_attention`/`no_data`), satisfaction percentage, positive/negative/rated/total counts, and a plain-language retraining recommendation — leaving the top `big`/`sideMetrics` panel (active-model eval F1/precision/recall/loss) untouched, and expose the underlying counts alongside the satisfaction percentage so sample size is judgeable, not just a bare percentage.
- Explicitly define satisfaction ratio as `positive ratings / total rated messages`; unrated assistant messages contribute to neither the numerator nor the denominator.
- Model feedback as a standalone table (not a column bag on `chat_messages`) so future categories/comments/retraining annotations are additive migrations, not breaking ones.

**Non-Goals:**
- Free-text comments, multi-category feedback, or per-user (vs per-message) rating history — explicitly deferred per the proposal's future-extension list.
- A dedicated retraining-dataset export pipeline, or a per-model-version breakdown surfaced in the dashboard UI — this change only lays the data foundation (`model_version` is persisted, not yet visualized).
- Real-time/streaming dashboard updates — the analytics panel loads with the rest of `GET /api/v1/dashboard/summary`, same freshness model as every other panel today.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|---------------------------|
| ADR-001 | Tenant isolation via per-tenant Postgres schema, no shared tables/RLS | `chat_message_feedback` MUST live in `tenant_template` (schema-per-tenant), not a shared/public table |
| ADR-004 | OpenSpec SDD governance — proposal → design → spec → tasks → evidence | This design + downstream specs/tasks/verification must satisfy the pipeline gates |
| ADR-007 | Chatbot uses full RAG pipeline; conversations/messages already exist in tenant schema | Feedback attaches to the existing `chat_messages.id`; no changes to the RAG pipeline itself |

## Decisions

### Decision 1: Separate `chat_message_feedback` table, not a column on `chat_messages`

**Choice:** New table `tenant_template.chat_message_feedback(id, message_id UNIQUE FK -> chat_messages.id, tenant_id, user_id, rating, created_at)`, one row per rated message.

**Rationale:** Keeps `chat_messages` free of *rating* data and append-only for that concern — `answer_kind` and `model_version` (Decisions 5 and 6) are properties of the message itself (what kind of reply it is, which model produced it), not judgments about it, so they belong on `chat_messages`; the human judgment (`rating`) belongs on a separate table. This split means future rating-side fields (category, comment, superseded_by) are additive to `chat_message_feedback` only, never touching the message read path, and the `UNIQUE(message_id)` constraint gives immutability-per-message for free at the DB layer rather than relying purely on application logic.

**Alternatives considered:**
- Add `rating` column directly to `chat_messages` — ruled out: cheapest short-term, but conflates "message content" with "human judgment about the message," and any richer feedback (comments, categories) would mean repeated schema churn on a table already read on every conversation load.
- JSONB `feedback` blob on `chat_messages` — ruled out: defeats indexing/aggregation for the dashboard query, and immutability would need an application-level check-then-write race instead of a DB constraint.

### Decision 2: Immutability enforced by a DB unique constraint + explicit conflict response

**Choice:** `POST /api/v1/chat/messages/{message_id}/feedback` attempts an insert; a unique-violation on `message_id` is caught and returned as `409 Conflict` with the existing rating in the body. No update/delete endpoint is exposed.

**Rationale:** Matches the requirement literally ("the rating becomes fixed") and avoids a class of race conditions from double-click/multi-tab submission — the constraint is the source of truth, not a pre-check-then-insert that can still race.

**Alternatives considered:**
- Application-level "check if exists, then insert" — ruled out: race-prone under concurrent requests (e.g., double-click), and duplicates a guarantee the DB gives for free.
- Allow overwriting the rating (mutable) — ruled out: explicitly against the stated requirement.

### Decision 3: Feedback owned by chat_api, aggregation exposed by gateway

**Choice:** chat_api owns the `chat_message_feedback` table and the write/read endpoints (submission, and including feedback state in `MessageResponse`). The gateway computes tenant-wide aggregates (counts, ratio) directly against the tenant schema for the dashboard, following the existing pattern where `dashboard.py` queries tenant tables directly rather than calling chat_api for aggregates.

**Rationale:** Per-message feedback is chat data — it belongs with the service that owns conversations/messages and enforces the RAG/guardrail context. Dashboard aggregation is cross-cutting, role-gated (`tenant_admin`), and already follows a direct-tenant-schema-query pattern in the gateway for every other panel; going through a chat_api aggregate endpoint would be an unnecessary hop inconsistent with that existing pattern.

**Alternatives considered:**
- Gateway calls a chat_api `/feedback/stats` endpoint and relays it — ruled out: inconsistent with how every other dashboard panel (documents, training, models) is already sourced (direct SQL against tenant schema in `dashboard.py`), and adds a synchronous cross-service call to a request path that already tolerates partial failure via the `sources` map.

### Decision 4: Response Quality is a dedicated interpreted card, not a generic row list, and never touches the Active model panel

**Choice (revised twice):** The first draft repurposed `big`/`bigUnit`/`sideMetrics` for the satisfaction ratio — discovered during implementation to conflict with the still-required "Active model" eval F1/precision/recall/loss panel, which occupies those exact fields (see the original Decision 4 text, preserved in git history). The second draft confined the ratio to a generic 4-row `sideBot`/`sideRows` list (`Satisfaction`, `Total responses`, `Rated`, `Positive`) reusing `MetricsPanel.tsx` as-is. User feedback on that version identified it as raw-metrics dumping rather than decision support: ambiguous labels ("Total Responses"/"Rated" don't say responses *to what*, rated *by whom*), four independent bars requiring the reader to mentally connect them, and no interpretation or recommended action. The final design replaces the generic row list with a dedicated `ResponseQualityCard` component and a `responseQuality` object on `DashboardData`: `{status, satisfactionPct, positive, negative, rated, total, recommendation}`. `status` (`healthy`/`monitor`/`needs_attention`/`no_data`) and `recommendation` (a fixed sentence per status) are computed server-side, not left for the client or the reader to derive. `sideBot`/`sideRows` are now unused for `tenant_admin` (`""`/`[]`); `sideTop`/`big`/`bigUnit`/`bar`/`sideMetrics` remain the Active model panel, untouched by any of these three drafts.

**Rationale:** The card's purpose (per the user) is not to display statistics but to answer "should I retrain?" — that requires an interpreted status and an explicit recommendation, which a generic label/value row list structurally cannot express well. A dedicated component is justified here (breaking the earlier "no new component" preference from the first pass) because the visualization need materially changed: a single stacked positive/negative bar tied directly to the two thumbs-up/down counts below it replaces four independent bars, and "Business User Feedback" / "N of M AI responses reviewed" name the actors and the denominator explicitly instead of the ambiguous "Rated"/"Total responses" labels.

**Alternatives considered:**
- Keep the generic `sideBot`/`sideRows` 4-row version — ruled out: this is exactly what the user identified as unclear (ambiguous labels, disconnected bars, no interpretation), which is the reason for this revision.
- Compute `status`/`recommendation` client-side from the raw counts — ruled out: the thresholds and wording are a single source of truth better owned by the backend (same place the ratio math already lives), and keeps the component a pure renderer, consistent with how `_tenant_admin_data` already owns all other interpreted labels (e.g. `doc_sub`, `train_sub`).
- A donut chart or fully segmented multi-color progress indicator — considered per the user's suggestion; a two-segment (positive/negative) stacked bar was chosen instead as the simplest visualization that still visually ties the two counts together, consistent with the existing design system's flat bar idiom (`GrowBar`/`MiniGrowBar`) rather than introducing a charting dependency for one card.

### Decision 5: Explicit `answer_kind` discriminator gates feedback eligibility

**Choice:** Add a nullable `answer_kind` column to `tenant_template.chat_messages` (`'answer' | 'clarification' | 'guardrail_blocked' | 'out_of_domain'`, defaulting to `'answer'` on backfill for historical rows), populated at message-insert time in `src/chat_api/api/v1/chat.py` from the outcome already computed by `RAGOrchestrator.execute_with_clarification` and `GuardrailService` (`pending_clarification` truthy → `clarification`; `check_blocked_question_type`/domain-classification decline → `guardrail_blocked` or `out_of_domain`; otherwise → `answer`). The feedback-submission endpoint rejects (404) any target message whose `answer_kind != "answer"`, in addition to rejecting non-assistant messages.

**Rationale:** Today nothing distinguishes a grounded answer from a clarification prompt or a guardrail decline in storage — all are `role='assistant'` rows with only `content`/`sources` — so "only assistant answers are rateable" cannot be enforced without a stored discriminator; inferring it at read-time from heuristics (e.g. "empty sources" for a decline) is fragile and duplicates logic that already exists in `guardrails.py`/`rag_orchestrator.py`. Persisting the classification once, at the point where the orchestrator already knows the answer, is the smallest correct fix and keeps the eligibility check in the feedback endpoint a single column comparison.

**Alternatives considered:**
- Infer eligibility at feedback-submission time by re-running guardrail heuristics against the stored `content`/`sources` — ruled out: duplicates classification logic, and some heuristics (e.g. the LLM-based domain classification) are not cheaply re-runnable or deterministic after the fact.
- Store eligibility as a boolean `is_rateable` instead of a typed `answer_kind` — ruled out: a boolean would lose the "why not rateable" information that a future analytics/debugging view would want (e.g. "how many guardrail declines vs. clarifications per week"), for the same storage cost as a short enum string.

### Decision 6: Reuse the existing `model_version` identifier instead of inventing a new one

**Choice:** Add a nullable `model_version` (string) column to `tenant_template.chat_messages`, populated from the same `model_version` value already returned by model-serving's `InferResponse` (`src/model_serving/api/v1/schemas.py`) whenever a chat turn's RAG pipeline performs NER inference on a retrieved snippet (per the existing "NER inference for chat context" chat-api requirement). This is the identical identifier already used by `extraction_runs.model_version` and the `X-Model-Source`/version-0-base-model convention from ADR-008 — not a new concept. When a turn's answer is produced without any NER inference call (pure SQL or document-context answer), `model_version` is left `null`.

**Rationale:** The proposal explicitly asks to reuse an existing identifier rather than invent one, and `model_version` (distinguishing base model `"0"` from trained versions `"1"`, `"2"`, ...) is already the platform's standard answer to "which model produced this" for extraction/inference responses. Capturing it on the message at creation time (not on the feedback row) is correct because it describes what generated the *response*, independent of whether or when it gets rated — a later rating on an already-created message doesn't change which model produced it.

**Alternatives considered:**
- Add a new `mlflow_run_id`/`model_version_id` FK to `tenant_template.model_versions` — ruled out: the base model (version 0, per ADR-008) has no `model_versions` row ("version 0 is synthetic — it has no database row"), so a FK would be null for exactly the case that needs distinguishing most (base vs. fine-tuned); the string `model_version` already handles this correctly across the codebase.
- Store model identity on `chat_message_feedback` instead of `chat_messages` — ruled out: model identity is a property of how the *response* was generated, not of the *rating*; storing it on the message means it's available for analytics even on unrated messages (e.g. "what fraction of base-model answers get rated at all").

## Risks / Trade-offs

- [Rating tied to `(tenant_id, message_id)`, not `(tenant_id, message_id, user_id)`] → Acceptable because a conversation and its messages already belong to a single user; flagged as an Open Question if shared/multi-user conversations are ever introduced.
- [Dashboard satisfaction percentage is meaningless with very few ratings (e.g., 1 rating = 100% or 0%)] → Mitigation: the card's "N of M AI responses reviewed" sentence and thumbs-up/down counts (Decision 4) expose the rated count and total alongside the percentage so a Tenant Admin doesn't over-read a tiny sample; no statistical suppression (e.g. forcing `no_data` below some minimum sample size) is added in this change — the status thresholds apply to the ratio itself regardless of sample size, matching the mockup exactly.
- [New migration must backfill `tenant_template.chat_message_feedback` into every already-provisioned tenant schema] → Mitigation: follow the exact `DO $$ ... FOR schema_name IN ...` backfill block used by `010_chatbot_infrastructure.py`; `verify_schema.py` will catch any schema left behind.
- [Removing the Quota Usage panel is a visible, BREAKING change to the tenant_admin dashboard] → Mitigation: called out explicitly in the proposal; no migration path needed since it's a display-only removal (underlying `tenants.max_documents` etc. columns are untouched and could resurface elsewhere later).
- [Backfilled `answer_kind` defaults to `'answer'` for all historical assistant messages] → Mitigation: this is an accepted approximation, not silently wrong going forward — every message created after this migration ships gets a correctly computed `answer_kind` at insert time; only pre-migration clarification/guardrail messages are misclassified as rateable, a bounded and shrinking set. Called out as an Open Question in the proposal.
- [`model_version` is null whenever a chat turn doesn't invoke NER inference] → Mitigation: this is intentional (Decision 6) — null means "not applicable to this answer path," not "unknown model." Any future model-attribution analytics must treat null as excluded from the analysis, not as an error.
- [Eligibility classification (`answer_kind`) depends on `RAGOrchestrator`/`GuardrailService` correctly signaling which branch produced the reply] → Mitigation: classification is computed from the same control-flow outcomes those services already return (`pending_clarification`, blocked-question/domain-classification results) rather than re-derived from message text, so it cannot drift from the guardrail logic that actually ran.

## Migration Plan

1. Add Alembic migration `031_chat_message_feedback.py`: `CREATE TABLE IF NOT EXISTS tenant_template.chat_message_feedback (...)`, plus `ALTER TABLE tenant_template.chat_messages ADD COLUMN IF NOT EXISTS answer_kind TEXT NOT NULL DEFAULT 'answer'` and `ADD COLUMN IF NOT EXISTS model_version TEXT NULL`, + backfill loop into existing `tenant_<id>` schemas, mirroring `010_chatbot_infrastructure.py`.
2. Ship chat_api changes: classify `answer_kind` and capture `model_version` at message-insert time in `chat.py`; add the feedback-submission endpoint (rejecting non-`answer` and non-assistant targets); extend `MessageResponse` with `feedback`, `answer_kind`, `model_version` fields — behind the same deploy as the migration, so chat_api only reads/writes the new columns/table after migration runs.
3. Add gateway proxy route for the feedback-submission endpoint; replace `_tenant_quota_rows` with `_tenant_feedback_rows` in `dashboard.py`, computing the explicit ratio/counts (Decision 4), and update `_tenant_admin_data`'s panel fields.
4. Ship portal changes: extend `MessageResponse`/chat types with `feedback`/`answer_kind`, add rating controls to `MessageThread.tsx` gated to `business_user` AND `answer_kind === "answer"`, update `src/portal/src/types/dashboard.ts` / `src/portal/src/lib/dashboard.ts` labels/counts if needed (panel shape unchanged).
5. Rollback: the migration is additive (new table + new nullable/defaulted columns) — rollback is drop-table plus drop-column in a down-migration; no destructive change to existing `chat_messages` data. Reverting portal/gateway/chat_api code is a normal redeploy since no other feature depends on the new fields/table yet.

## Open Questions

- Should feedback be scoped `(message_id, user_id)` instead of `message_id` alone, to support future multi-user shared conversations? Deferred — no current multi-user conversation feature exists.
- Exact satisfaction-ratio color thresholds (80/60 proposed) are placeholder defaults pending product input; they're a data-only constant, not schema, so they're cheap to tune post-launch.
- Historical assistant messages backfilled with `answer_kind = 'answer'` may include a small number of pre-migration clarification/guardrail messages that appear rateable; no reclassification pass is proposed for this change (see Risks).
- No in-force ADR requires revisiting.
