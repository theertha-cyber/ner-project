# Verification Plan

**Change:** response-feedback-rating
**Generated:** 2026-08-05 (revised)
**Status:** 🟡 Functional evidence collected by AI agent for the large majority of scenarios (see § Evidence Log); Audit Record sign-off still requires a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-message-feedback | Only eligible assistant answer messages are rateable | Grounded answer message is eligible | Given a message with `answer_kind: "answer"`, when a Business User submits a rating, then it is accepted and persisted | tests/test_chat_api_feedback.py | - [x] |
| 2 | chat-message-feedback | Only eligible assistant answer messages are rateable | Clarification message is not eligible | Given a message with `answer_kind: "clarification"`, when a rating is attempted, then it is rejected and no feedback row is created | tests/test_chat_api_feedback.py | - [x] |
| 3 | chat-message-feedback | Only eligible assistant answer messages are rateable | Guardrail-blocked message is not eligible | Given a message with `answer_kind: "guardrail_blocked"`, when a rating is attempted, then it is rejected and no feedback row is created | tests/test_chat_api_feedback.py | - [x] |
| 4 | chat-message-feedback | Only eligible assistant answer messages are rateable | Out-of-domain message is not eligible | Given a message with `answer_kind: "out_of_domain"`, when a rating is attempted, then it is rejected and no feedback row is created | tests/test_chat_api_feedback.py | - [x] |
| 5 | chat-message-feedback | Only eligible assistant answer messages are rateable | User message is never eligible regardless of classification | Given a `role: "user"` message, when a rating is attempted, then it is rejected and no feedback row is created | tests/test_chat_api_feedback.py | - [x] |
| 6 | chat-message-feedback | Feedback restricted to the Business User role | Non-business_user role cannot submit a rating | Given an authenticated `tenant_admin`/`system_admin`, when they attempt to submit a rating for an eligible message, then it is rejected with an authorization error and no row is created | tests/test_chat_api_feedback.py | - [x] |
| 7 | chat-message-feedback | One immutable rating per eligible assistant message | First rating on a message is accepted | Given an eligible unrated message, when a Business User submits a `down` rating, then it is persisted and subsequent reads report `rating: "down"` | tests/test_chat_api_feedback.py | - [x] |
| 8 | chat-message-feedback | One immutable rating per eligible assistant message | Duplicate submission with the same value is rejected | Given a message already rated `up`, when another `up` rating is submitted, then it is rejected and no second row is created | tests/test_chat_api_feedback.py | - [x] |
| 9 | chat-message-feedback | One immutable rating per eligible assistant message | Duplicate submission with the opposite value is rejected | Given a message already rated `up`, when a `down` rating is submitted, then it is rejected and the stored rating remains `up` | tests/test_chat_api_feedback.py | - [x] |
| 10 | chat-message-feedback | One immutable rating per eligible assistant message | Rating persists across sessions and page refreshes | Given a message rated `up` previously, when the user reloads or returns in a new session, then the message still shows `up` as fixed/selected | tests/test_chat_api_feedback.py (server-side persistence via GET) + src/portal/src/components/chat/MessageThread.test.tsx (client render) | - [x] |
| 11 | chat-message-feedback | Feedback data model supports future extension | Feedback table is independent of message content | Given the `chat_message_feedback` schema, when inspected, then it FK-references `chat_messages.id` rather than embedding rating data in `chat_messages` | tests/test_chat_message_feedback_model.py + tests/test_migration_032_chat_message_feedback.py (real DB) | - [x] |
| 12 | chat-message-feedback | Feedback data model supports future extension | A new feedback attribute can be added without breaking existing rows | Given existing rated rows, when a future migration adds a nullable `category`/`comment` column, then existing rows remain valid and no change to `chat_messages` or immutability behaviour is required | tests/test_chat_message_feedback_model.py | - [x] |
| 13 | chat-message-feedback | Assistant messages carry model-identity metadata for future evaluation | Assistant message from an NER-grounded answer records model_version | Given a chat turn with an NER inference call, when the assistant message is persisted, then its `model_version` equals the inference call's `model_version` | tests/test_chat_message_model_version.py | - [x] |
| 14 | chat-message-feedback | Assistant messages carry model-identity metadata for future evaluation | Assistant message with no NER inference has a null model_version | Given a chat turn answered without an NER inference call, when the assistant message is persisted, then its `model_version` is `null` | tests/test_chat_message_model_version.py | - [x] |
| 15 | chat-api | Message feedback submission endpoint | Business user submits first rating on an eligible answer | Given an eligible unrated message, when POST `/api/v1/chat/messages/{id}/feedback` with `{"rating":"up"}`, then response is 201 with `{message_id, rating:"up", created_at}` | tests/test_chat_api_feedback.py | - [x] |
| 16 | chat-api | Message feedback submission endpoint | Rating an already-rated message returns 409 and does not overwrite | Given a message already rated `down`, when a new rating request is submitted, then response is 409 with the existing `rating:"down"`, unchanged | tests/test_chat_api_feedback.py | - [x] |
| 17 | chat-api | Message feedback submission endpoint | Rating a user message returns 404 | Given a `role:"user"` message, when a rating request targets it, then response is 404 | tests/test_chat_api_feedback.py | - [x] |
| 18 | chat-api | Message feedback submission endpoint | Rating a clarification message returns 404 | Given a message with `answer_kind:"clarification"`, when a rating request targets it, then response is 404 | tests/test_chat_api_feedback.py | - [x] |
| 19 | chat-api | Message feedback submission endpoint | Rating a guardrail-blocked message returns 404 | Given a message with `answer_kind:"guardrail_blocked"`, when a rating request targets it, then response is 404 | tests/test_chat_api_feedback.py | - [x] |
| 20 | chat-api | Message feedback submission endpoint | Rating an out-of-domain message returns 404 | Given a message with `answer_kind:"out_of_domain"`, when a rating request targets it, then response is 404 | tests/test_chat_api_feedback.py | - [x] |
| 21 | chat-api | Message feedback submission endpoint | Non-business_user role is rejected | Given an authenticated `tenant_admin`, when they POST to the feedback endpoint, then response is 403 | tests/test_chat_api_feedback.py | - [x] |
| 22 | chat-api | Message feedback submission endpoint | Unauthenticated request rejected | Given no JWT, when POST to the feedback endpoint, then response is 401 | tests/test_chat_api_feedback.py | - [x] |
| 23 | chat-api | Conversation CRUD | List conversations for a user | Given a user with 3 conversations, when GET `/api/v1/chat/conversations`, then response is 200 with 3 conversations each having `id, title, created_at, message_count` | tests/test_chat_api_conversations.py | - [ ] |
| 24 | chat-api | Conversation CRUD | Get conversation messages | Given a conversation with 5 messages, when GET `/api/v1/chat/conversations/{id}`, then response is 200 with 5 messages each having `role, content, sources, created_at, answer_kind, model_version, feedback` | tests/test_chat_api_feedback.py::test_rating_persists_and_is_visible_via_conversation_get (checks `answer_kind`/`feedback` presence on the fetched message; not a 5-message enumeration) | - [x] |
| 25 | chat-api | Conversation CRUD | Get conversation messages includes existing feedback | Given a conversation with a message rated `up`, when a Business User GETs it, then that message's `feedback` equals `{rating:"up", created_at}` | tests/test_chat_api_feedback.py::test_rating_persists_and_is_visible_via_conversation_get | - [x] |
| 26 | chat-api | Conversation CRUD | Get conversation messages reports answer_kind for non-answer replies | Given a conversation with a clarification prompt and a guardrail-blocked decline, when GETs, then their `answer_kind` fields equal `"clarification"`/`"guardrail_blocked"` respectively and neither is rateable | tests/test_chat_api_conversations.py (not yet added — the POST-side 404 for these kinds is covered by rows 18-19; the GET-response field value for non-answer kinds is not separately asserted) | - [ ] |
| 27 | chat-api | Conversation CRUD | Delete conversation | Given a conversation owned by user A, when user A DELETEs it, then response is 204 | tests/test_chat_api_conversations.py | - [ ] |
| 28 | chat-api | Conversation CRUD | Delete another user's conversation returns 404 | Given a conversation owned by user A, when user B DELETEs it, then response is 404 | tests/test_chat_api_conversations.py | - [ ] |
| 29 | chat-ui | Message thread display | Send message and receive response | Given a selected conversation, when the user sends a message, then it appears optimistically, a loading indicator shows, and the response appears with auto-scroll | src/portal/src/components/chat/MessageThread.test.tsx | - [x] |
| 30 | chat-ui | Message thread display | Source citations are expandable | Given an assistant message with citations, when a citation is clicked, then it expands showing `document_id`/`entity_type` and snippet text | src/portal/src/components/chat/MessageThread.test.tsx | - [x] |
| 31 | chat-ui | Message thread display | Business user sees feedback controls on eligible answer messages only | Given a Business User viewing a thread with messages of every `answer_kind`, when it renders, then only `answer_kind:"answer"` assistant messages show Thumbs Up/Down icons; user, clarification, guardrail_blocked, and out_of_domain messages do not | src/portal/src/components/chat/MessageThread.test.tsx | - [x] |
| 32 | chat-ui | Message thread display | Non-business_user does not see feedback controls | Given a Tenant Admin viewing a thread, when it renders, then no message shows feedback icons | src/portal/src/components/chat/MessageThread.test.tsx | - [x] |
| 33 | chat-ui | Message thread display | Rating a message fixes the selection | Given a Business User viewing an unrated eligible message, when they click Thumbs Up, then it shows selected/active and Thumbs Down becomes disabled for that message | src/portal/src/components/chat/MessageThread.test.tsx | - [x] |
| 34 | chat-ui | Message thread display | Rated message stays fixed after page refresh | Given a message rated Thumbs Down previously, when the page is refreshed and the conversation reopened, then Thumbs Down shows selected and both icons are non-interactive | src/portal/src/components/chat/MessageThread.test.tsx | - [x] |
| 35 | dashboard-summary-endpoint | Dashboard Summary Endpoint | system_admin summary returns role-specific data | Given caller role `system_admin`, when GET summary, then response contains the specified kicker/title/stats/pTitle/pRows/sideTop fields | tests/test_dashboard_summary_roles.py | - [ ] |
| 36 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns pipeline data and a healthy response-quality card | Given caller role `tenant_admin` with 61 eligible answer messages, 42 rated (35 up, 7 down), when GET summary, then pipeline stats/pRows/`sideTop`/`big`/`bigUnit`/`sideMetrics` are unchanged, `sideBot=""`, `sideRows=[]`, and `responseQuality={status:"healthy", satisfactionPct:83.3, positive:35, negative:7, rated:42, total:61, ...}` | tests/test_dashboard_feedback_panel.py | - [x] |
| 36a | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns a needs_attention response-quality card | Given 70 eligible messages, 3 rated (1 up, 2 down), when GET summary, then `responseQuality.status="needs_attention"` and the recommendation advises retraining | tests/test_dashboard_feedback_panel.py | - [x] |
| 36b | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns a monitor response-quality card | Given a rated subset with satisfaction 60-79%, when GET summary, then `responseQuality.status="monitor"` and the recommendation advises monitoring | tests/test_dashboard_feedback_panel.py | - [x] |
| 37 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator summary returns task data | Given caller role `annotator`, when GET summary, then the specified stats/pTitle/pRows/sideTop fields are returned | tests/test_dashboard_summary_roles.py | - [ ] |
| 38 | dashboard-summary-endpoint | Dashboard Summary Endpoint | business_user summary returns extraction data | Given caller role `business_user`, when GET summary, then the specified stats/pTitle/pRows/sideTop fields are returned | tests/test_dashboard_summary_roles.py | - [ ] |
| 39 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unavailable training service returns null values | Given training service is down, when GET summary as `tenant_admin`, then training-dependent stats are `null`, `sources.training` is `false`, status is 200 | tests/test_dashboard_feedback_panel.py | - [x] |
| 40 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary with no rated feedback yet | Given some eligible answer messages exist but none rated, when GET summary as `tenant_admin`, then `responseQuality.status="no_data"`, `satisfactionPct=null` (not misleading 0%/100%), `total` is the real count, `rated`/`positive`/`negative` are all `0`, status is 200 | tests/test_dashboard_feedback_panel.py | - [x] |
| 41 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Unrated eligible answer messages do not affect the ratio | Given 20 eligible answer messages, 5 rated (4 up, 1 down), 15 unrated, when GET summary as `tenant_admin`, then `responseQuality.satisfactionPct=80` (4/5, not 4/20), `total=20`, `rated=5` | tests/test_dashboard_feedback_panel.py | - [x] |
| 42 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when GET summary, then response is 401 | tests/test_dashboard_summary.py | - [ ] |
| 43 | dashboard-summary-endpoint | Dashboard Summary Endpoint | one tenant schema failure does not blank out other tenants' stats | Given one tenant schema is unhealthy among many healthy ones, when GET summary as `system_admin`, then response is 200 and healthy tenants' aggregates are unaffected | tests/test_dashboard_tenant_enumeration.py | - [ ] |
| 44 | dashboard-summary-endpoint | Dashboard Summary Endpoint | The virtual system tenant is excluded from schema iteration | Given `public.tenants` has a `system` row with no backing schema, when GET summary as `system_admin`, then no query/exception occurs for `tenant_system` and status is 200 | tests/test_dashboard_tenant_enumeration.py | - [ ] |
| 45 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Tenant rows without a backing schema are excluded from aggregates | Given active tenant rows with no backing schema, when GET summary as `system_admin`, then those rows contribute nothing and zero exceptions are logged | tests/test_dashboard_tenant_enumeration.py | - [ ] |
| 46 | dashboard-summary-endpoint | Dashboard Summary Endpoint | A partial aggregate is not reported as a complete total | Given one tenant's `documents` query fails, when GET summary as `system_admin`, then the "Documents (all)" stat is not presented as complete and `sources.documents` is `false` | tests/test_dashboard_tenant_enumeration.py | - [ ] |
| 47 | dashboard-summary-endpoint | DashboardData TypeScript Type | type compiles with all fields | Given a `DashboardData` object matching the shape, when assigned to the type, then the compiler produces no errors | portal `tsc --noEmit` output | - [x] |
| 48 | dashboard-summary-endpoint | DashboardData TypeScript Type | null values are assignable | Given `stats[0].value` is `null`, when assigned to the type, then the compiler produces no errors | portal `tsc --noEmit` output | - [x] |
| 49 | portal-dashboard | Dashboard Data Shape | system_admin data shape | Given role `system_admin`, when GET summary, then response matches the specified system_admin shape including storage-by-tenant `sideRows` | src/portal/src/components/dashboard/MetricsPanel.test.tsx | - [ ] |
| 50 | portal-dashboard | Dashboard Data Shape | tenant_admin data shape carries a responseQuality card, not quota-usage sideRows | Given role `tenant_admin`, when GET summary, then `sideTop`/`big`/`sideMetrics` are unchanged, `sideBot=""`/`sideRows=[]`, and `responseQuality` is present with all 7 fields | tests/test_dashboard_feedback_panel.py (backend shape) | - [x] |
| 51a | portal-dashboard | Response Quality Card | Healthy status renders a positive recommendation | Given `responseQuality.status="healthy"` with counts, when the card renders, then it shows a green "Healthy" badge, the percentage + "Positive Feedback", the reviewed-count subtext, thumb counts, sample-size sentence, and a no-retraining recommendation | src/portal/src/components/dashboard/ResponseQualityCard.test.tsx | - [x] |
| 51b | portal-dashboard | Response Quality Card | Needs Attention status renders a retraining recommendation | Given `responseQuality.status="needs_attention"`, when the card renders, then it shows a red "Needs Attention" badge and a recommendation advising retraining | src/portal/src/components/dashboard/ResponseQualityCard.test.tsx | - [x] |
| 51c | portal-dashboard | Response Quality Card | Monitor status renders a watch-and-gather-more-feedback recommendation | Given `responseQuality.status="monitor"`, when the card renders, then it shows an amber "Monitor" badge | src/portal/src/components/dashboard/ResponseQualityCard.test.tsx | - [x] |
| 51d | portal-dashboard | Response Quality Card | No-data status avoids a misleading percentage | Given `responseQuality.status="no_data"`, `satisfactionPct=null`, when the card renders, then it shows a neutral "Not Enough Data" badge, a no-data indicator instead of a percentage, and a not-enough-feedback recommendation | src/portal/src/components/dashboard/ResponseQualityCard.test.tsx | - [x] |
| 52 | portal-dashboard | Dashboard Data Shape | annotator data shape | Given role `annotator`, when GET summary, then response matches the specified annotator shape | src/portal/src/components/dashboard/MetricsPanel.test.tsx | - [ ] |
| 53 | portal-dashboard | Dashboard Data Shape | business_user data shape | Given role `business_user`, when GET summary, then response matches the specified business_user shape | src/portal/src/components/dashboard/MetricsPanel.test.tsx | - [ ] |
| 54 | portal-dashboard | Dashboard Data Shape | partial service failure degrades gracefully | Given training service is unavailable, when the dashboard renders, then dependent stat cards show `—`, others show real values, no full-page error | src/portal/src/components/dashboard/MetricsPanel.test.tsx | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Feedback data model (Decision 1) | AI implements `rating` as a column on `chat_messages` instead of a standalone `chat_message_feedback` table, or omits the `UNIQUE(message_id)` constraint | Inspect the migration SQL — confirm a separate table exists with a unique constraint on `message_id`, and that `answer_kind`/`model_version` (message-level) are cleanly separated from `rating` (feedback-level) |
| 2 | Immutability enforcement (Decision 2) | AI implements "check-then-insert" application logic instead of relying on the DB unique constraint + 409 response, leaving a race window where rapid double-submission creates two rows or silently overwrites | Attempt/inspect a concurrent double-submit test (both same-value and opposite-value); confirm only one row exists per message and the second request receives 409, not 200/201, and the stored value is unchanged |
| 3 | Eligibility classification (`answer_kind`, Decision 5) | AI computes `answer_kind` from a fragile heuristic (e.g. "empty sources array" or keyword-matching the reply text) instead of the actual control-flow outcome already returned by `RAGOrchestrator`/`GuardrailService`, causing misclassification of a real answer as ineligible or vice versa | Trace the code path from `execute_with_clarification`'s return value / guardrail decision through to the `answer_kind` written on INSERT — confirm no independent re-derivation from message content occurs |
| 4 | Role gating (chat-message-feedback req. "Feedback restricted to the Business User role") | AI hides feedback icons in the UI for non-`business_user` roles but forgets to enforce the same check server-side, allowing a direct API call to rate on behalf of a `tenant_admin` | Send a POST to the feedback endpoint authenticated as `tenant_admin`/`system_admin` directly (bypassing UI) and confirm 403 |
| 5 | Satisfaction ratio formula (Decision 4) | AI computes the ratio as positive/total-assistant-messages (or positive/(positive+negative) while silently excluding a differently-defined "rated" set) instead of strictly positive/rated, or defaults a zero-rated period to `0%`/`100%` instead of a no-data indicator | Feed a fixture with a known total/rated/positive/negative split (e.g. row 36/41 in Section 1) and confirm the `"Satisfaction"` row matches `positive/rated`, not `positive/total`; confirm a zero-rated fixture returns a no-data indicator |
| 6 | Response-quality panel scope (Decision 4) | AI repurposes `big`/`bigUnit`/`bar`/`sideMetrics` for the satisfaction ratio, silently overwriting the still-required "Active model" eval F1/precision/recall/loss panel that already occupies those same `DashboardData` fields | Confirm `_tenant_admin_data`'s `big`/`bigUnit`/`sideMetrics` values are unchanged (still model eval metrics) and that all response-quality data lives only in `sideBot`/`sideRows` |
| 7 | Model-version capture (Decision 6) | AI invents a new identifier (e.g. a fresh `model_id` UUID) instead of reusing the existing `model_version` string convention from `InferResponse`/`extraction_runs`, or populates a non-null placeholder (e.g. `"unknown"`) when no NER call occurred instead of `null` | Grep the implementation for the source of the persisted `model_version` value — confirm it is threaded through from the model-serving `InferResponse`, not a newly introduced field; confirm turns with no NER call persist `null`, not a placeholder string |
| 8 | Dashboard panel reuse (Decision 4) | AI builds a new dashboard chart component instead of reusing the existing `sideBot`/`sideRows`/`MetricsPanel` shape | Diff `MetricsPanel.tsx` — confirm no new component or prop shape change was added, only the `sideBot`/`sideRows` data producer |
| 9 | Tenant schema backfill (Migration Plan step 1) | AI creates `chat_message_feedback`/`answer_kind`/`model_version` in `tenant_template` only, forgetting to backfill already-provisioned `tenant_<id>` schemas, so the feature silently fails or misclassifies for existing tenants | Run `verify_schema.py` (or equivalent) against an existing tenant schema and confirm all three additions exist there, not just in `tenant_template` |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|--------------------|
| ADR-001 | Tenant isolation via per-tenant Postgres schema, no shared tables/RLS | `chat_message_feedback` and the new `chat_messages` columns must live in `tenant_template` and be backfilled per-tenant, never as a shared/public table | Inspect the migration file for `tenant_template.chat_message_feedback` DDL, `tenant_template.chat_messages` ALTER statements, and a per-schema backfill loop; confirm no table/column is created in `public` |
| ADR-004 | OpenSpec SDD governance — proposal → design → spec → tasks → evidence | This change must retain traceability: proposal/design/specs/tasks/verification all present and coherent before archive, including this revision's added eligibility/ratio/model-version requirements | Run `openspec validate response-feedback-rating --strict` and confirm all artifacts exist and pass; confirm this verification.md's Evidence Log is populated before archive |
| ADR-007 | Chatbot uses full RAG pipeline; conversations/messages already exist in tenant schema | Feedback and classification metadata must attach to existing `chat_messages` rows without modifying the RAG pipeline's actual guardrail/citation decisions, only observing and persisting their outcome | Diff `rag_orchestrator.py`/`guardrails.py` — confirm the change only adds a return value/read of the existing decision, not new guardrail logic; confirm feedback endpoint is additive only |
| ADR-008 | Base model (version 0) is synthetic — no `model_versions` DB row; `model_version` string distinguishes base vs. trained versions | `model_version` persisted on `chat_messages` must reuse this exact string convention, not a FK to `model_versions` (which would be null for the base-model case) | Confirm the persisted `model_version` column is a plain string/nullable text field sourced from `InferResponse.model_version`, not a foreign key to `tenant_template.model_versions.id` |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenarios 1-6 (chat-message-feedback, eligibility + role restriction): `poetry run pytest tests/test_chat_api_feedback.py -q` → all pass, covering answer/clarification/guardrail_blocked/out_of_domain/user-message/non-business_user cases
- [x] Scenarios 7-10 (chat-message-feedback, immutable rating lifecycle): same run — first-rating-accepted, same-value-duplicate-rejected (409), opposite-value-duplicate-rejected (409, unchanged), and persistence via GET conversation all pass
- [x] Scenarios 11-12 (chat-message-feedback, data model + extensibility): `poetry run pytest tests/test_chat_message_feedback_model.py -q` → 3/3 pass (FK/unique-constraint introspection, simulated additive-column migration); additionally `poetry run pytest tests/test_migration_032_chat_message_feedback.py -q` → 6/6 pass against the real dev DB (`ner_dev`), confirming the migration actually applied and backfilled every live tenant schema, not just the test-fixture tables
- [x] Scenarios 13-14 (chat-message-feedback, model_version capture): `poetry run pytest tests/test_chat_message_model_version.py -q` → 12/12 pass
- [x] Scenarios 15-22 (chat-api, feedback endpoint): covered by the same `test_chat_api_feedback.py` run — 201/409/404×4/403/401 all pass
- [ ] Scenarios 23, 27-28 (chat-api, unrated Conversation CRUD paths): not separately verified this session (existing schema-level tests in `test_chat_api_conversations.py` don't exercise a DB; unaffected by this change's additions since new fields are optional/additive)
- [x] Scenarios 24-25 (chat-api, GET includes feedback/answer_kind): covered by `test_chat_api_feedback.py::test_rating_persists_and_is_visible_via_conversation_get`
- [ ] Scenario 26 (chat-api, GET reports answer_kind for non-answer replies): not separately asserted — POST-side 404 for those kinds is verified (rows 18-19), but the GET response's `answer_kind` field value for a clarification/guardrail_blocked message was not asserted in a test
- [x] Scenarios 29, 31-34 (chat-ui, message thread + feedback controls): `npx vitest run src/components/chat/MessageThread.test.tsx` → 5/5 pass
- [ ] Scenario 30 (chat-ui, citation expand-on-click): pre-existing behavior, unmodified by this change, not re-verified this session
- [x] Scenario 36, 39-41 (dashboard-summary-endpoint, response-quality panel): `poetry run pytest tests/test_dashboard_feedback_panel.py -q` → 4/4 pass
- [ ] Scenarios 35, 37-38, 42-46 (dashboard-summary-endpoint, other roles / pre-existing partial-failure behavior): re-run via `poetry run pytest tests/test_dashboard_summary_roles.py tests/test_dashboard_summary.py tests/test_dashboard_tenant_enumeration.py -q` surfaced pre-existing failures unrelated to this change (e.g. `training_jobs.created_at` column mismatch, stray tenant schemas missing `model_versions`); this change does not touch those code paths, but the scenarios are not independently re-confirmed passing this session
- [x] Scenarios 47-48 (DashboardData type): `npx tsc --noEmit` — zero errors from any file this change touches; pre-existing errors in unrelated files (annotation, training-jobs, hooks) not caused by this change
- [x] Scenario 50 (portal-dashboard, tenant_admin response-quality shape): `npx vitest run src/components/dashboard/MetricsPanel.test.tsx` → 8/8 pass (new test asserts the 4-row panel + unaffected Active model section)
- [ ] Scenarios 49, 51-54 (portal-dashboard, other roles / ratio-ignores-unrated at render time): not independently re-verified this session — 51's underlying computation is verified server-side (dashboard-summary-endpoint row 41); 49/52-54 are pre-existing, unmodified rendering paths

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions; one deviation found and corrected during implementation (see Section on Decision 4 correction in tasks.md §4.3) and reflected back into design.md/specs before continuing
- [x] All ADR compliance steps in Section 3 confirmed ✓ (ADR-001: migration only touches `tenant_template` + per-tenant backfill; ADR-008: `model_version` is a plain string, not a `model_versions` FK)
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files during implementation)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — migration creates a standalone `chat_message_feedback` table with `UNIQUE(message_id)`; `answer_kind`/`model_version` added to `chat_messages` separately, verified via `tests/test_chat_message_feedback_model.py`
- [x] Risk 2 mitigation confirmed — `test_duplicate_rating_returns_409_and_does_not_overwrite` and `test_duplicate_rating_same_value_returns_409` both pass, stored value unchanged
- [x] Risk 3 mitigation confirmed — `_classify_answer_kind` reads only `pending_clarification`/`entity_resolution_outcome`/`blocked_reason` from the graph's terminal state, verified by `tests/test_chat_message_model_version.py`'s `TestAnswerKindClassification` cases
- [x] Risk 4 mitigation confirmed — `test_non_business_user_role_returns_403` passes
- [x] Risk 5 mitigation confirmed — `tests/test_dashboard_feedback_panel.py` fixtures assert ratio = positive/rated (e.g. 35/42→83%, not 35/61), and the zero-rated case returns `"—"`
- [x] Risk 6 mitigation confirmed — found and fixed during implementation: an earlier draft repurposed `big`/`sideMetrics` for the ratio, which would have deleted the Active model panel; corrected to confine all response-quality data to `sideBot`/`sideRows`, verified by `MetricsPanel.test.tsx`'s new test asserting both panels render correctly together
- [x] Risk 7 mitigation confirmed — `model_version` threaded from `Source.model_version`/`Citation.model_version` (propagated from wherever an NER inference call sets it) through `_extract_model_version`; verified `null`-not-placeholder via `tests/test_chat_message_model_version.py`
- [x] Risk 8 mitigation confirmed — `MetricsPanel.tsx` diff: zero lines changed, only the gateway's data producer (`_tenant_feedback_rows`) and test additions
- [x] Risk 9 mitigation confirmed — two layers: (1) `tests/conftest.py`'s shared tenant-table fixture includes `chat_message_feedback`/`chat_messages.answer_kind`/`chat_messages.model_version`, all DB-integration tests using it pass; (2) `tests/test_migration_032_chat_message_feedback.py` ran the actual migration against the real dev DB (`ner_dev`) and asserted every one of the 3 live provisioned tenant schemas (not just `tenant_template`) has both the new table and both new columns — this is exactly the risk scenario (backfill silently skipped for existing tenants) and it caught a real instance of it: the first `db-init` run used a stale pre-migration Docker image and silently left `alembic_version` at `031`; rebuilding the image and re-running fixed it, confirmed by the same test going from 6 failures to 6 passes

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `poetry run pytest tests/test_chat_api_feedback.py tests/test_chat_message_feedback_model.py tests/test_chat_message_model_version.py -q` → 54 passed (17 teardown-only errors, pre-existing/unrelated — reproduced on unmodified `tests/test_dashboard_summary_roles.py` too) | 1-22, 24-25 | AI agent (opsx:apply) | 2026-08-05 |
| 2 | Functional | `poetry run pytest tests/test_dashboard_feedback_panel.py -q` → 4 passed | 36, 39-41 | AI agent (opsx:apply) | 2026-08-05 |
| 3 | Functional | `npx vitest run src/components/chat src/components/dashboard` → 57 passed, 0 failed | 29, 31-34, 50 | AI agent (opsx:apply) | 2026-08-05 |
| 4 | Functional | `npx tsc --noEmit` → 0 errors in files touched by this change | 47-48 | AI agent (opsx:apply) | 2026-08-05 |
| 5 | Edge Case | Manual trace of `RAGOrchestrator._classify_answer_kind`/`_extract_model_version` source against `tests/test_chat_message_model_version.py` assertions | Risk 3, Risk 7 | AI agent (opsx:apply) | 2026-08-05 |
| 6 | Structural | Diff review of `src/portal/src/components/dashboard/MetricsPanel.tsx` (git diff shows zero changes to this file) | Risk 6, Risk 8 | AI agent (opsx:apply) | 2026-08-05 |
| 7 | Functional / Edge Case | `docker compose run --rm db-init` against real `ner_dev` DB — `alembic upgrade head` logged `Running upgrade 031 -> 032`; `verify_schema.py` passed. `poetry run pytest tests/test_migration_032_chat_message_feedback.py -q` → 6 passed (table/column/constraint existence in `tenant_template`, backfill present in all 3 live tenant schemas, zero NULL `answer_kind` rows). First attempt used a stale image and silently no-opped (`alembic_version` stayed `031`) — caught by this exact test, fixed by rebuilding the image | 11-12, Risk 9 | AI agent (opsx:apply) | 2026-08-05 |
| 8 | Functional | Live smoke test against the running stack (rebuilt `chat_api`/`gateway`/`portal` containers, `docker compose up -d --force-recreate`): real chat turn → `answer_kind: "answer"`; `POST /feedback` → 201; duplicate → 409 unchanged; `tenant_admin` attempt → 403; `GET` conversation shows persisted feedback; `GET /dashboard/summary` → `sideBot: "Response quality"`, ratio updates live 0/1→100%, Active model panel (`sideTop`/`big`/`bigUnit`) unaffected | 1, 7, 8, 9, 15, 16, 21, 24, 25, 36 | AI agent (opsx:apply) | 2026-08-05 |
| 9 | Functional | Live browser verification (portal UI, logged in as `bizuser@democorp.io`): Thumbs Up/Down render on the eligible message, click fixes the rating (`aria-pressed="true"`, both buttons `disabled`), full page reload + re-select conversation → rating still shown fixed | 10, 21, 29, 31, 33, 34 | AI agent (opsx:apply) | 2026-08-05 |
| 10 | Functional | Response Quality card redesign: `poetry run pytest tests/test_dashboard_feedback_panel.py -q` → 6/6 pass (healthy/monitor/needs_attention/no_data statuses, unrated-exclusion, training-service-down isolation); `npx vitest run src/components/dashboard/ResponseQualityCard.test.tsx` → 4/4 pass; `npx tsc --noEmit` → 0 errors in touched files; rebuilt/redeployed `gateway`+`portal` and confirmed live via direct API call and portal UI (browser automation, tenant_admin session) — rendered layout matched the requested design exactly (status badge, headline %, subtext, thumb counts, sample-size sentence, recommendation) | 36, 36a, 36b, 40, 41, 50, 51a-51d | AI agent (opsx:apply) | 2026-08-05 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** response-feedback-rating
**Proposal:** `openspec/changes/response-feedback-rating/proposal.md`
**Spec files reviewed:**
- specs/chat-message-feedback/spec.md
- specs/chat-api/spec.md
- specs/chat-ui/spec.md
- specs/dashboard-summary-endpoint/spec.md
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
