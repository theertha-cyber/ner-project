# Verification Plan

**Change:** redesign-business-user-dashboard
**Generated:** 2026-08-05
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-dashboard | Dashboard Data Shape | system_admin data shape | Given a `system_admin` caller, when `GET /api/v1/dashboard/summary` is called, then the response contains `kicker: "Platform control plane"`, 4 stats, `pTitle: "Approval queue"` with 4 rows, and a "Platform health" side panel with SLA/latency/error rate/GPU metrics and storage-by-tenant `sideRows` | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 2 | portal-dashboard | Dashboard Data Shape | tenant_admin data shape | Given a `tenant_admin` caller, when the endpoint is called, then the response contains 4 pipeline stats, `pTitle: "Pipeline activity"` with 4 rows, and an "Active model" side panel with F1/precision/recall/loss and quota rows | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 3 | portal-dashboard | Dashboard Data Shape | annotator data shape | Given an `annotator` caller, when the endpoint is called, then the response contains 4 task stats, `pTitle: "My tasks"` with 4 rows, and a "Dataset readiness" side panel with a 500-span progress bar and entity-type breakdown | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 4 | portal-dashboard | Dashboard Data Shape | business_user data shape | Given a `business_user` caller, when the endpoint is called, then `kicker` is `"Your AI assistant workspace"`, `stats` is exactly `["Conversations", "Messages Sent", "Helpful Responses"]`, `pTitle` is `"Recent Conversations"` with up to 4 conversation rows (title, last interaction time, message count), `sideTop` is `"AI Assistant Status"` with no F1/precision/recall/loss fields present, and `sideBot`/`sideRows` are empty | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 5 | portal-dashboard | Dashboard Data Shape | partial service failure degrades gracefully | Given the training service is unavailable, when the dashboard renders, then only the affected stat cards show `—`, unaffected cards show real values, and no full-page error is shown | `tests/test_dashboard_summary.py` | - [ ] |
| 6 | portal-dashboard | Dashboard Summary Endpoint | system_admin summary returns real data from wired sources | Given a `system_admin` caller, when the endpoint is called, then `stats[0].value` is the real tenant count, `sources.tenants` is `true`, and training-dependent fields come from the training service | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 7 | portal-dashboard | Dashboard Summary Endpoint | tenant_admin summary returns real data from wired sources | Given a `tenant_admin` caller with documents/annotations/models/training data, when the endpoint is called, then `stats[0..3].value` reflect real document count, annotation completion %, promoted model F1, and training job count respectively | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 8 | portal-dashboard | Dashboard Summary Endpoint | annotator summary returns real task data | Given an `annotator` caller with assigned tasks, when the endpoint is called, then `stats[0].value` is assigned-task count, `stats[1].value` is confirmed-span count, `stats[3].value` is completion % | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 9 | portal-dashboard | Dashboard Summary Endpoint | business_user summary returns real conversation and feedback data | Given a `business_user` caller with conversation history, when the endpoint is called, then `stats[0].value` is the count of `{schema}.conversations` rows where `user_id` matches the caller, `stats[1].value` is the count of `role='user'` rows in `{schema}.chat_messages` for the caller's conversations, `stats[2].value` is the count of `rating='up'` rows in `{schema}.chat_message_feedback` for the caller, and every query is scoped to the caller's own `user_id` | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 10 | portal-dashboard | Dashboard Summary Endpoint | business_user summary includes assistant status | Given a `business_user` caller and `chat-api`'s `/health` responds successfully within timeout, when the endpoint is called, then the `AI Assistant Status` panel shows "Online" and `sources.assistant_health` is `true` | `tests/test_dashboard_summary_roles.py` (or `tests/test_dashboard_assistant_health.py`) | - [ ] |
| 11 | portal-dashboard | Dashboard Summary Endpoint | business_user summary shows offline status when chat-api health check fails | Given a `business_user` caller and the `chat-api` `/health` call times out, errors, or returns non-200, when the endpoint is called, then the panel shows "Offline", `sources.assistant_health` is `false`, and the overall request still returns 200 (no 500) | `tests/test_dashboard_summary_roles.py` (or `tests/test_dashboard_assistant_health.py`) | - [ ] |
| 12 | portal-dashboard | Dashboard Summary Endpoint | sources map includes all data domains | Given the summary is generated for any role, when the response is inspected, then `sources` contains a key for every data domain relevant to that role, each `true`/`false` per query success | `tests/test_dashboard_summary_roles.py` | - [ ] |
| 13 | portal-dashboard | Dashboard Summary Endpoint | unauthenticated request rejected | Given a request with no valid JWT, when `GET /api/v1/dashboard/summary` is called, then the response is `401 Unauthorized` | `tests/test_dashboard_summary.py` | - [ ] |
| 14 | portal-dashboard | Activity Panel | activity row navigates on click | Given a `system_admin` row with `go: "training"`, when the user clicks it, then the router navigates to `/training-jobs` | `src/portal/src/components/dashboard/ActivityPanel.test.tsx` | - [ ] |
| 15 | portal-dashboard | Activity Panel | business_user conversation row navigates to chat | Given a `business_user` row with `go: "chat"` for conversation `conv-123`, when the user clicks it, then the router navigates to `/chat?conversation=conv-123` | `src/portal/src/components/dashboard/ActivityPanel.test.tsx` | - [ ] |
| 16 | portal-dashboard | Activity Panel | status dot and tag render correct colours | Given a row with `tk: "pending_approval"`, when it renders, then the dot/tag use the amber/warn colour tokens; a `tk: "completed"` row uses green/good tokens; a `tk: "running"` row shows a pulsing dot | `src/portal/src/components/dashboard/ActivityPanel.test.tsx` | - [ ] |
| 17 | portal-dashboard | Dashboard Summary Endpoint | business_user summary computes average response time from recorded assistant messages | Given a `business_user` caller with at least one assistant `chat_messages` row carrying a non-null `response_time_ms`, when the endpoint is called, then the `resp time` side metric shows the average of the caller's own assistant messages' `response_time_ms`, formatted as `"Nms"` (<1000ms) or `"N.Ns"` (>=1000ms) | `tests/test_dashboard_summary.py` | - [ ] |
| 18 | portal-dashboard | Dashboard Summary Endpoint | business_user summary shows dash for response time when no timed messages exist | Given a `business_user` caller with no assistant messages carrying a `response_time_ms`, when the endpoint is called, then the `resp time` side metric shows `—` | `tests/test_dashboard_summary.py` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Table/column names for chat data | AI may invent or misremember column names (e.g., assuming a `messages` table instead of the actual `chat_messages` table, or a `topic`/`category` column that doesn't exist) when writing `_business_conversation_activity`/`_business_topic_frequency` | Diff the implemented SQL against `src/chat_api/api/v1/chat.py`'s actual `INSERT`/`SELECT` statements — every column referenced must already exist in that file's queries |
| 2 | Scoping to the caller vs. the tenant | AI may write conversation/message/feedback queries scoped only to `tenant_id` (matching the pattern of other dashboard handlers) instead of `user_id`, leaking other users' conversations into a Business User's dashboard | Read the implemented SQL WHERE clauses for `_business_user_data` — each of `conversations`, `chat_messages`, `chat_message_feedback` queries must filter on the requesting `user_id`, not just `tenant_id` |
| 3 | `sources` dict key drift | AI may forget to update `_null_sources()` and `_ROLE_SERVICES["business_user"]` consistently, leaving stale `"extraction"`/`"models"` keys or missing new `"conversations"`/`"feedback"`/`"assistant_health"` keys, which would break the "sources map includes all data domains" scenario for this role | Inspect `_null_sources()` and `_ROLE_SERVICES["business_user"]` in `dashboard.py` — confirm they list exactly `conversations`, `feedback`, `assistant_health` (plus any shared keys) and no leftover extraction/model keys are asserted `true` for this role |
| 4 | Assistant health check failure handling | AI may let an unhandled exception from the `chat-api` `/health` HTTP call propagate and crash the whole `/api/v1/dashboard/summary` request instead of degrading to "Offline" | Verify the health-check call is wrapped in try/except (mirroring `_fetch_active_model`) and confirm via a forced-failure test (e.g., point at an unreachable host) that the endpoint still returns 200 with `sources.assistant_health: false` |
| 5 | Response-time field correctness (superseded — instrumentation was added on request) | AI may compute the average incorrectly (e.g. average across all tenant users instead of the caller, include `NULL` rows as zero instead of excluding them, or measure the wrong span of code) | Confirm `_business_avg_response_time`'s SQL filters `c.user_id = :user_id` and `cm.response_time_ms IS NOT NULL`, and confirm `chat.py` starts the timer immediately before `execute_with_clarification` and stops it immediately after, not including the two `INSERT`s or the commit |
| 6 | Frontend nav mapping omission | AI may add the `"chat"` → `/chat` entry to `navFor` but forget the `conversation` query param, or hardcode a wrong route, breaking scenario 15 | Read the updated `navFor`/row-click handler in the frontend and confirm it builds `/chat?conversation={id}` using the row's actual conversation id, not a static path |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-001: Tenant Data Isolation via Separate DB Schemas | Each tenant's data lives in its own `tenant_<id>` schema; all queries must be schema-scoped | New `conversations`/`chat_messages`/`chat_message_feedback` queries must use the `{schema}.` prefix (via `_tenant_schema(tenant_id)`) exactly like existing handlers | Grep `dashboard.py` for the new queries and confirm each uses an f-string with `{schema}.` prefix and no query references a schema other than the caller's own tenant schema |
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | `chat-api` owns conversation/message persistence; responses are tenant-scoped | The gateway must read `chat-api`'s tables read-only (no writes) and must not bypass tenant scoping when aggregating stats | Confirm no `INSERT`/`UPDATE`/`DELETE` statements were added to `dashboard.py` against chat tables, and confirm every new query includes a tenant/user scoping predicate |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (system_admin data shape): confirmed via `test_system_admin_summary_returns_role_specific_data` — unchanged, not touched by this change
- [x] Scenario 2 (tenant_admin data shape): confirmed via `test_tenant_admin_summary_returns_pipeline_data` — unchanged
- [x] Scenario 3 (annotator data shape): confirmed via `test_annotator_summary_returns_task_data` — unchanged
- [x] Scenario 4 (business_user data shape): `test_business_user_summary_returns_conversation_data` and `test_business_user_returns_correct_shape` pass — kicker, 3 stats, pTitle/sideTop/sideBot all match new copy
- [x] Scenario 5 (partial service failure): `test_unavailable_training_service_returns_null_values` and `test_graceful_degradation_when_training_unavailable` pass — 200 with `—`/null fields on query failure (general pattern shared by all role handlers including business_user's try/except blocks)
- [x] Scenario 6 (system_admin summary real data): confirmed via existing coverage, unchanged
- [x] Scenario 7 (tenant_admin summary real data): confirmed via existing coverage, unchanged
- [x] Scenario 8 (annotator summary real data): confirmed via existing coverage, unchanged
- [x] Scenario 9 (business_user conversation/feedback data): `test_business_user_summary_scopes_to_own_conversations` — seeded two users, caller's stats reflect only their own conversation/message/feedback rows
- [x] Scenario 10 (assistant online): `test_business_user_summary_shows_online_when_chat_api_healthy` — mocked healthy `/health`, asserts `sources.assistant_health: true` and sideMeta "Online"
- [x] Scenario 11 (assistant offline): `test_business_user_summary_shows_offline_when_chat_api_unreachable` — mocked failure, asserts `sources.assistant_health: false`, "Offline", status 200
- [x] Scenario 12 (sources map completeness): asserted in `test_business_user_summary_returns_conversation_data` — `sources` keys superset-match `{conversations, feedback, assistant_health}`
- [x] Scenario 13 (unauthenticated rejected): confirmed via existing `test_unauthenticated_request_rejected`/`test_unauthenticated_returns_401`, unchanged
- [x] Scenario 14 (activity row navigation, non-business roles): confirmed via existing `ActivityPanel.test.tsx` cases, unchanged
- [x] Scenario 15 (business_user conversation row → /chat): new `ActivityPanel.test.tsx` test — click navigates to `/chat?conversation=conv-123`, verified via `npx vitest run` (9/9 passed)
- [x] Scenario 16 (status dot/tag colours): confirmed via existing `ActivityPanel.test.tsx` cases, unchanged
- [x] Scenario 17 (average response time computed): `test_avg_response_time_shows_milliseconds` and `test_avg_response_time_shows_seconds_above_1000ms` — seed `response_time_ms` rows, assert `"300ms"` and `"2.5s"` formatting
- [x] Scenario 18 (response time dash when no data): `test_avg_response_time_dash_when_no_data` — no timed messages, asserts `"—"`

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (Decisions 1–4 all reflected in `_business_user_data`, `_business_conversation_activity`, `_business_topic_frequency`, `_fetch_assistant_health`)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `conversations`, `chat_messages`, `chat_message_feedback` column names in `dashboard.py` verified against `src/chat_api/api/v1/chat.py`'s actual INSERT/SELECT statements
- [x] Risk 2 mitigation confirmed — all three new queries (`Conversations`, `Messages Sent`, `Helpful Responses`, plus activity/topic queries) filter on `user_id`, verified by `test_business_user_summary_scopes_to_own_conversations` seeding a second user and asserting their data is excluded
- [x] Risk 3 mitigation confirmed — `_null_sources()` and `_ROLE_SERVICES["business_user"]` both updated to `["conversations", "feedback", "assistant_health"]`, no leftover `extraction`/`models` keys asserted true for this role
- [x] Risk 4 mitigation confirmed — `_fetch_assistant_health` wraps the httpx call in try/except; `test_business_user_summary_shows_offline_when_chat_api_unreachable` confirms graceful "Offline" degradation with HTTP 200
- [x] Risk 5 mitigation confirmed — `_business_avg_response_time` filters on `c.user_id = :user_id AND cm.role = 'assistant' AND cm.response_time_ms IS NOT NULL`; `chat.py`'s `time.monotonic()` window wraps only `execute_with_clarification`, verified by reading the diff
- [x] Risk 6 mitigation confirmed — `goToHref(go, id)` builds `/chat?conversation={id}` from the row's actual `id` field, verified by the new ActivityPanel test using `conv-123`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|---------------------|-----------------------|----------------|------|
| 1 | Functional | `poetry run pytest tests/test_dashboard_summary_roles.py -k business_user -q` → `5 passed` (kicker/stats/pTitle/sideTop/sideBot shape, own-conversation scoping, assistant online/offline mocked) | Scenarios 4, 9, 10, 11, 12 | AI agent (Claude) | 2026-08-05 |
| 2 | Functional | `poetry run pytest tests/test_dashboard_summary.py -k "business_user or BusinessUser" -q` → `4 passed` (stat counts, activity rows go=chat with id, no eval-metric fields in side panel) | Scenarios 4, 9 | AI agent (Claude) | 2026-08-05 |
| 3 | Functional | `npx vitest run src/components/dashboard/ActivityPanel.test.tsx` → `9 passed` including new `/chat?conversation={id}` navigation test | Scenario 15 | AI agent (Claude) | 2026-08-05 |
| 4 | Structural | `openspec validate redesign-business-user-dashboard --type change --strict` → `Change 'redesign-business-user-dashboard' is valid` | N/A (gate check) | AI agent (Claude) | 2026-08-05 |
| 5 | Functional | Regression run `poetry run pytest tests/test_dashboard_summary_roles.py tests/test_dashboard_summary.py -q` (standalone per-file, DB cleaned of pre-existing orphaned-tenant pollution) — system_admin/tenant_admin/annotator/unauthenticated scenarios unaffected by this change | Scenarios 1, 2, 3, 5, 6, 7, 8, 13, 14, 16 | AI agent (Claude) | 2026-08-05 |
| 6 | Functional | `poetry run pytest tests/test_dashboard_summary.py -k "business_user or BusinessUser" -q` → `8 passed` (adds `test_avg_response_time_shows_milliseconds`, `test_avg_response_time_shows_seconds_above_1000ms`, `test_avg_response_time_dash_when_no_data`, `test_frequently_asked_topics_block_removed`) | Scenarios 4, 17, 18 | AI agent (Claude) | 2026-08-05 |
| 7 | Structural | Alembic migration `033_chat_messages_response_time_ms` applied via `docker compose run --rm db-init` → `Running upgrade 032 -> 033` and `Schema verification passed: no drift detected` against the dev DB | Scenario 17 (migration/data-availability precondition) | AI agent (Claude) | 2026-08-05 |
| 8 | Structural | `gateway`, `chat_api`, `portal` containers rebuilt (`docker compose build`) and force-recreated; post-restart `/api/v1/dashboard/summary` returned `200 OK` in gateway logs | N/A (deployment verification) | AI agent (Claude) | 2026-08-05 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** redesign-business-user-dashboard
**Proposal:** `openspec/changes/redesign-business-user-dashboard/proposal.md`
**Spec files reviewed:**
  - specs/portal-dashboard/spec.md

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
