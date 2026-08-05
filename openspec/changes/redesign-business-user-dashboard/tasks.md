## 1. Backend: business_user data sourcing

- [x] 1.1 Add `_business_conversation_activity(db, schema, user_id)` in [dashboard.py](../../../src/gateway/api/v1/dashboard.py) querying `{schema}.conversations` joined to `{schema}.chat_messages`, scoped to `user_id`, returning up to 4 `ActivityRow`s (title = conversation title, sub = last interaction time + message count, `go: "chat"`).
- [x] 1.2 Add `_business_topic_frequency(db, schema, user_id)` replacing `_business_top_fields`: tokenize + lowercase + stopword-filter the user's own `conversations.title` values, group by token, return top 5 as `SideRow`s with `pct` computed the same way as the existing implementation.
- [x] 1.3 Add `_fetch_assistant_health(auth_header)` mirroring `_fetch_active_model`'s HTTP pattern — short-timeout call to chat-api `/health`, returns online/offline + last-checked timestamp, wrapped in try/except so failures never raise.
- [x] 1.4 Rewrite `_business_user_data` to: query `Conversations` count, `Messages Sent` count (`role='user'` in `chat_messages`), `Helpful Responses` count (`rating='up'` in `chat_message_feedback`) — all scoped to `user_id`; call `_business_conversation_activity`, `_business_topic_frequency`, `_fetch_assistant_health`; set `kicker`/`title`/`line` to assistant-workspace copy; set `pTitle: "Recent Conversations"`, `sideTop: "AI Assistant Status"`, `sideBot: "Frequently Asked Topics"`.
- [x] 1.5 Remove now-unused `_business_extraction_activity` and `_business_top_fields` once no longer referenced.
- [x] 1.6 Update `_null_sources()` and `_ROLE_SERVICES["business_user"]` to `["conversations", "feedback", "assistant_health"]`, removing `"extraction"`/`"models"` from this role's expected set.

## 2. Frontend: navigation wiring

- [x] 2.1 Add a `"chat"` entry to the `navFor` href mapping (wherever `"extractions"`/`"training"`/etc. are mapped to routes) resolving to `/chat?conversation={id}` using the row's conversation id.
- [x] 2.2 Verify `DashboardHero`, `StatCard`, `ActivityPanel`, `MetricsPanel` render correctly with the new `business_user` content without any component code changes (confirm no role-specific branching exists in these components that assumes extraction-shaped data).

## 3. Spec verification tasks

- [x] 3.1 Scenario "system_admin data shape" — confirm no regression via existing coverage in `tests/test_dashboard_summary_roles.py`.
- [x] 3.2 Scenario "tenant_admin data shape" — confirm no regression via existing coverage in `tests/test_dashboard_summary_roles.py`.
- [x] 3.3 Scenario "annotator data shape" — confirm no regression via existing coverage in `tests/test_dashboard_summary_roles.py`.
- [x] 3.4 Scenario "business_user data shape" — add/update a test in `tests/test_dashboard_summary_roles.py` asserting `kicker`, 3 stat labels, `pTitle`, `sideTop`, `sideBot` for the `business_user` role.
- [x] 3.5 Scenario "partial service failure degrades gracefully" — add/update a test in `tests/test_dashboard_summary.py` forcing a query failure and asserting `—`/`null` fields with a 200 response.
- [x] 3.6 Scenario "system_admin summary returns real data" — confirm no regression via existing coverage in `tests/test_dashboard_summary_roles.py`.
- [x] 3.7 Scenario "tenant_admin summary returns real data" — confirm no regression via existing coverage in `tests/test_dashboard_summary_roles.py`.
- [x] 3.8 Scenario "annotator summary returns real task data" — confirm no regression via existing coverage in `tests/test_dashboard_summary_roles.py`.
- [x] 3.9 Scenario "business_user summary returns real conversation and feedback data" — add a test in `tests/test_dashboard_summary_roles.py` seeding two users' conversations/messages/feedback and asserting the caller only sees their own counts.
- [x] 3.10 Scenario "business_user summary includes assistant status" — add a test in `tests/test_dashboard_summary_roles.py` (or a new `tests/test_dashboard_assistant_health.py`) mocking a successful chat-api `/health` call and asserting `sources.assistant_health: true` and "Online" status.
- [x] 3.11 Scenario "business_user summary shows offline status when chat-api health check fails" — add a test alongside 3.10 mocking a timeout/error/non-200 response and asserting "Offline", `sources.assistant_health: false`, and HTTP 200.
- [x] 3.12 Scenario "sources map includes all data domains" — add/update a test in `tests/test_dashboard_summary_roles.py` asserting the `business_user` `sources` keys match `["conversations", "feedback", "assistant_health"]`.
- [x] 3.13 Scenario "unauthenticated request rejected" — confirm no regression via existing coverage in `tests/test_dashboard_summary.py`.
- [x] 3.14 Scenario "activity row navigates on click" (non-business roles) — confirm no regression via existing coverage in `src/portal/src/components/dashboard/ActivityPanel.test.tsx`.
- [x] 3.15 Scenario "business_user conversation row navigates to chat" — add a test in `src/portal/src/components/dashboard/ActivityPanel.test.tsx` asserting a `go: "chat"` row navigates to `/chat?conversation={id}`.
- [x] 3.16 Scenario "status dot and tag render correct colours" — confirm no regression via existing coverage in `src/portal/src/components/dashboard/ActivityPanel.test.tsx`.

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 4.6 Run `openspec validate redesign-business-user-dashboard --type change --strict` and confirm it exits clean before archive.
