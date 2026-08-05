## Why

The `business_user` dashboard currently mirrors the technical roles (`tenant_admin`, `system_admin`) by surfacing extraction/ML internals — docs extracted, entity counts, avg confidence, model F1/precision/recall/loss, top extracted fields. Business Users interact with the platform exclusively through the AI chat assistant (`chat-api`/`chat-ui`), not the extraction pipeline, so none of these metrics reflect their actual usage or answer their real question: "is my assistant working, and what have I been doing with it?" This creates confusion and hides genuinely useful data — conversation history and their own feedback — that already exists in the system but isn't surfaced.

## What Changes

- Hero copy (`kicker`/`title`/`line`) for `business_user` rewritten to frame the page as "your AI assistant workspace" instead of "extraction intelligence".
- Stat strip replaced: `Docs extracted` / `Entities found` / `Avg confidence` → `Conversations`, `Messages Sent`, `Helpful Responses` (derived from existing `chat_message_feedback.rating` thumbs up/down, which already exists in `chat-api`).
- `Active model` side panel (F1/precision/recall/loss) replaced with an `AI Assistant Status` panel: assistant online/offline, last updated, average response time.
- `pTitle: "Recent extractions"` → `"Recent Conversations"`; rows now list the user's own conversations (title, last interaction time, message count) sourced from `chat-api`'s `conversations`/`messages` tables, linking to `/chat?conversation={id}` instead of `/extractions`.
- `sideBot: "Top extracted fields"` chart → `"Frequently Asked Topics"`, derived from the user's own conversation titles (keyword frequency) rather than `extracted_entities`.
- **BREAKING**: `business_user` dashboard summary response no longer includes extraction- or model-eval-derived fields (`doc_count`, `entity_count`, `avg_conf`, F1/precision/recall/loss, top extracted fields). Any client code reading those fields for this role must be updated.
- Gateway's `business_user` handler (`_business_user_data` in [dashboard.py](../../../src/gateway/api/v1/dashboard.py)) queries chat-api's tenant-schema `conversations`, `chat_messages`, and `chat_message_feedback` tables directly (same pattern as existing handlers query `documents`/`extracted_entities`), plus a lightweight call to chat-api `/health` for assistant status.
- `sources` map for `business_user` changes from `["extraction", "models"]` to `["conversations", "feedback", "assistant_health"]`.

## Capabilities

### New Capabilities

(none — this is a scoped modification of the existing `portal-dashboard` capability's `business_user` behavior)

### Modified Capabilities

- `portal-dashboard`: the `business_user` data-shape scenario, the `business_user` summary-endpoint scenario, and the "Top Extracted Fields"/"Recent extractions" panel content change from extraction/ML metrics to conversation/usage metrics. Hero copy for this role also changes. Panel *structure* (stat strip, activity panel, secondary metrics panel, hero) is unchanged — only the `business_user` content populating those structures changes.

## Impact

- Backend: [src/gateway/api/v1/dashboard.py](../../../src/gateway/api/v1/dashboard.py) — `_business_user_data`, `_business_extraction_activity` (replaced by a conversations-activity equivalent), `_business_top_fields` (replaced by a topics equivalent), `_ROLE_SERVICES["business_user"]`, `_null_sources`/`sources` keys.
- Backend: new read-only queries against chat-api's tenant schema tables `conversations`, `chat_messages`, `chat_message_feedback` (already defined and populated by [src/chat_api/api/v1/chat.py](../../../src/chat_api/api/v1/chat.py)); a lightweight call to chat-api's `/health` endpoint for assistant status.
- Frontend: [src/portal/src/app/(auth)/dashboard/page.tsx](../../../src/portal/src/app/(auth)/dashboard/page.tsx) reuses existing generic components (`DashboardHero`, `StatCard`, `ActivityPanel`, `MetricsPanel`) unchanged — no component structure changes needed since `DashboardData` shape is unchanged, only its `business_user` content.
- Navigation: activity rows for this role now link to `/chat?conversation={id}` instead of `/extractions`; `navFor` mapping in the frontend needs a `"chat"` entry (or reuse of an existing chat route mapping) if one doesn't already exist.
- Spec: `openspec/specs/portal-dashboard/spec.md` — `business_user` scenarios under "Dashboard Data Shape" and "Dashboard Summary Endpoint" requirements need updated scenario text.
- No changes to `system_admin`, `tenant_admin`, or `annotator` dashboard behavior.

## Open Questions

- Average response time: chat-api does not currently record per-message latency. This proposal treats it as best-effort/optional — omit the field (render `—`) if no timing data is available, rather than adding new instrumentation in this change.
- "Frequently Asked Topics": no topic/category classification exists on messages or conversations. This proposal uses a lightweight keyword-frequency heuristic over conversation titles (already generated by `derive_conversation_title`) rather than introducing a new classification pipeline. Confirm this lightweight approach is acceptable versus deferring the panel.
- Assistant "Online/Offline" status: proposal treats a successful `chat-api` `/health` response as "Online" and any failure/timeout as "Offline". Confirm no additional health signal (e.g., LLM provider reachability) is expected for v1.
