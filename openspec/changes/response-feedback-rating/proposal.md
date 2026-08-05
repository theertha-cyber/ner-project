## Why

Business Users currently have no way to signal whether an assistant response was useful, and Tenant Admins have no signal for whether the deployed model is performing well or needs retraining. A lightweight thumbs up/down on each assistant message closes that loop cheaply, and — if modeled as real data rather than throwaway UI state — becomes the seed of a retraining-evaluation pipeline later.

## What Changes

- Add a `chat_message_feedback` table (tenant-schema, one row per eligible assistant message) recording a `rating` (`up`/`down`), the rating user, and timestamps — designed to extend later with categories/comments/retraining annotations without a breaking migration.
- Add an `answer_kind` discriminator to assistant messages (`answer`, `clarification`, `guardrail_blocked`, `out_of_domain`) so feedback eligibility is explicit and enforced, not inferred. **Only `answer_kind = "answer"` messages are rateable.**
- Add a chat_api endpoint to submit feedback for an eligible assistant message, immutable by construction: once a message has a rating, further attempts to rate it — same value or opposite — are rejected outright (409), never overwritten, never soft-updated.
- Extend the chat message response payload to include the message's current feedback state so the portal can render the fixed rating after reload, and persist `model_version` (the same identifier already returned by model-serving's `InferResponse.model_version` / used by `extraction_runs.model_version`, per ADR-008) on each assistant message so feedback can later be joined back to the model that produced it.
- Add Thumbs Up / Thumbs Down (Lucide `ThumbsUp`/`ThumbsDown`) controls beside each eligible assistant message in the chat UI, visible only to `business_user` role. Once rated, the selected icon is visually fixed and the opposite icon becomes non-interactive. Non-eligible assistant messages (clarifications, guardrail declines, out-of-domain replies) render no feedback controls at all.
- Add a tenant-scoped feedback aggregation endpoint on the gateway that explicitly computes **satisfaction ratio = positive ratings / total rated messages** (unrated assistant messages contribute to neither the numerator nor the denominator), and exposes the underlying counts — total assistant messages, total rated messages, positive ratings, negative ratings, satisfaction ratio — so a Tenant Admin can judge sample-size reliability, not just see a bare percentage.
- **BREAKING**: Remove the "Quota usage" card from the Tenant Admin dashboard side panel and replace it with a "Response Quality" card visualizing the counts and ratio above (a color-coded trend so declining satisfaction is visually obvious, plus the rated/total context so a 100% ratio on 2 responses doesn't read the same as 100% on 200).

## Capabilities

### New Capabilities

- `chat-message-feedback`: Data model, eligibility rules, and access rules for one-rating-per-eligible-assistant-message thumbs up/down feedback (role-gated to `business_user`, restricted to `answer_kind = "answer"` messages, immutable once set — no overwrite, duplicate submissions rejected — extensible for future categories/comments/retraining annotations, and carrying the producing model's `model_version` for future evaluation).

### Modified Capabilities

- `chat-api`: message response schema gains `feedback` and `answer_kind`/`model_version` fields; new feedback-submission endpoint with explicit eligibility validation (rejects non-`answer` message kinds) and immutability rules.
- `chat-ui`: assistant message rendering gains rating controls with fixed/disabled-after-rate behavior, gated to `business_user`, shown only for `answer_kind = "answer"` messages.
- `dashboard-summary-endpoint`: tenant_admin summary response replaces the quota-usage panel fields with response-quality/feedback-analytics fields, using the explicit positive/rated ratio formula and exposing total/rated/positive/negative counts.
- `portal-dashboard`: tenant_admin dashboard side panel content changes from quota usage to a response-quality visualization built from the counts and ratio, not a bare percentage.

## Impact

- **DB**: new Alembic migration (chat_api's tenant-schema migration path) adding `tenant_template.chat_message_feedback`, plus an `answer_kind` and `model_version` column on `tenant_template.chat_messages`, backfilled into existing tenant schemas per the existing per-migration pattern (see `alembic/versions/010_chatbot_infrastructure.py`).
- **chat_api**: `src/chat_api/api/v1/chat.py`, `src/chat_api/api/v1/schemas.py`, `src/chat_api/services/rag_orchestrator.py`, `src/chat_api/services/guardrails.py` — classify and persist `answer_kind`/`model_version` at message-creation time, new feedback endpoint, schema fields, role and eligibility checks.
- **gateway**: `src/gateway/api/v1/chat_proxy.py` — new proxy route; `src/gateway/api/v1/dashboard.py` — `_tenant_quota_rows` replaced by a feedback-analytics query function computing the explicit ratio and counts; `_tenant_admin_data` panel fields updated.
- **portal**: `src/portal/src/components/chat/MessageThread.tsx` (+ new feedback control component, eligibility-aware), `src/portal/src/types/dashboard.ts`, `src/portal/src/lib/dashboard.ts`, `src/portal/src/components/dashboard/MetricsPanel.tsx` (label/behavior only, shape unchanged), dashboard hook/types for the new panel data including counts.
- **Removed**: quota-usage computation (`_tenant_quota_rows`) and its consumption by the dashboard card.

## Open Questions

- Rating is modeled as one-per-message (not one-per-message-per-user); since a conversation is already scoped to a single user, this is equivalent in practice — flagging in case multi-user shared conversations are planned.
- Trend granularity for the dashboard (daily vs weekly buckets, and how many buckets) is not specified by the user — proposing daily buckets over the last 14 days, adjustable later.
- Satisfaction-ratio thresholds for "healthy" vs "needs attention" coloring are not specified — proposing ≥80% green, 60–79% amber, <60% red, tunable later without a schema change.
- Historical (pre-migration) assistant messages have no reliable way to be reclassified into `answer_kind` values; they will backfill to `"answer"` by default, which may make a small number of historical clarification/guardrail messages appear rateable until naturally aged out of active conversations — flagged as an accepted, low-impact gap rather than a blocker.
- `model_version` is only populated when a chat turn actually invokes NER inference on a retrieved snippet (per the existing "NER inference for chat context" requirement); turns answered purely from SQL or document context without an NER call will have `model_version = null`, meaning "not applicable" rather than "unknown."
