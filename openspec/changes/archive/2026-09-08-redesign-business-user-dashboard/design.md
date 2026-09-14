## Context

`GET /api/v1/dashboard/summary` in [src/gateway/api/v1/dashboard.py](../../../src/gateway/api/v1/dashboard.py) dispatches to one of four role handlers (`_system_admin_data`, `_tenant_admin_data`, `_annotator_data`, `_business_user_data`) that each build a shared `DashboardData` shape by querying the tenant's Postgres schema directly (`tenant_<id>` schema, no cross-service HTTP calls except one best-effort call to fetch the active model for the "Active model" panel). The frontend (`app/(auth)/dashboard/page.tsx`) is entirely data-driven off this shape — no per-role branching in components.

Today `_business_user_data` queries `{schema}.extracted_entities` and `{schema}.extraction_runs`, tables owned by `extraction-service`. Chat usage data (`conversations`, `chat_messages`, `chat_message_feedback`) already exists in the same tenant schema, owned by `chat-api` (see [src/chat_api/api/v1/chat.py](../../../src/chat_api/api/v1/chat.py)). Both services write into the same per-tenant Postgres schema, so the gateway reading `chat-api`'s tables directly is the same pattern already used for `extraction-service`'s and `document-service`'s tables elsewhere in this file — not a new architectural pattern.

## Goals / Non-Goals

**Goals:**

- Replace `business_user` dashboard content (hero copy, stats, activity panel, secondary panel) with conversation/usage/feedback data, using the existing `DashboardData` shape unchanged.
- Reuse the existing "query tenant schema directly" pattern for the new data.
- Keep `system_admin`, `tenant_admin`, `annotator` dashboards, and all shared frontend components, untouched.

**Non-Goals:**

- No new database tables or migrations — `conversations`, `chat_messages`, `chat_message_feedback` already exist and are populated by `chat-api`.
- No new message-level latency instrumentation for "Average Response Time" — best-effort/omitted if unavailable (see Open Questions).
- No new topic-classification ML/NLP pipeline for "Frequently Asked Topics" — a lightweight keyword-frequency heuristic over existing conversation titles only.
- No change to the `DashboardData` Pydantic/TypeScript shape itself, `StatCard`/`ActivityPanel`/`MetricsPanel` components, or the 30s polling/staleTime behavior.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|---------------------------|
| ADR-001: Tenant Data Isolation via Separate DB Schemas | Each tenant's data lives in its own `tenant_<id>` schema; all queries must be schema-scoped | New queries against `conversations`/`messages`/`chat_message_feedback` MUST use `{schema}.` prefix and filter to the current tenant (and, for feedback, the requesting user) exactly as the existing `_business_user_data` extraction queries do |
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | Chat responses are tenant-scoped; `chat-api` owns conversation/message persistence | This design reads `chat-api`'s tables from the gateway (read-only, same DB) rather than adding a new HTTP dependency on `chat-api` for conversation listing, consistent with how other dashboard handlers already read other services' tables directly for MVP |

No other ADR (002, 003, 004, 005, 006, 008, 009) concerns this surface (model strategy, serving topology, governance process, agent boundaries, training infra/hyperparameters) and none are revisited by this design.

## Decisions

### Decision 1: Query chat-api's tenant-schema tables directly from the gateway, matching the existing per-role handler pattern

**Choice:** `_business_user_data` is rewritten to run `SELECT` queries against `{schema}.conversations`, `{schema}.chat_messages`, and `{schema}.chat_message_feedback`, scoped to `user_id` (a Business User should only see their own conversations, not the whole tenant's), the same way it currently queries `{schema}.extracted_entities` scoped to the tenant.

**Rationale:** Every other role handler in this file already reads another service's tables directly (system_admin reads training-service tables, tenant_admin reads documents/annotations/training/models tables). This keeps the dashboard's data-access pattern uniform and avoids introducing a new inter-service HTTP dependency (with its own auth, timeout, and failure-mode concerns) purely for read-only aggregate stats.

**Alternatives considered:**
- Call `chat-api`'s `/api/v1/chat/conversations` HTTP endpoint instead — ruled out because it doesn't support the aggregate stats needed (total message count, feedback rating counts) without N+1 calls, and every other handler already bypasses HTTP in favor of direct schema queries.
- Add a new `chat-api` internal aggregation endpoint (`/internal/dashboard-stats`) — ruled out as unnecessary service-boundary ceremony for a same-database read; can be revisited later if chat-api's schema ownership becomes stricter.

### Decision 2: Assistant status via a single call to chat-api's existing `/health` endpoint

**Choice:** `_business_user_data` makes one lightweight `httpx` call to `chat-api`'s existing `/health` endpoint (mirroring the existing `_fetch_active_model` pattern that already calls out over HTTP with a short timeout and graceful fallback). A 200 response within the timeout maps to "Online"; a timeout, non-200, or connection error maps to "Offline". `sources["assistant_health"]` is set accordingly.

**Rationale:** `chat-api/main.py` already exposes `/health`; reusing it avoids adding new endpoints. This is the one place where an HTTP call (rather than a schema read) is appropriate, because "is the service up" is inherently a liveness check, not a data query — a DB row can't tell you the process is responding.

**Alternatives considered:**
- Infer "online" from recent successful message rows (e.g., a message inserted in the last N minutes) — ruled out because a quiet-but-healthy assistant (no recent messages) would incorrectly show "Offline".
- Add a dedicated `/health/dashboard` endpoint with richer status — ruled out as premature; plain `/health` is sufficient for Online/Offline.

### Decision 3: "Average Response Time" is best-effort and omitted when no data exists

**Choice:** No new latency instrumentation is added in this change. The `AI Assistant Status` panel's response-time field renders `—` (using the existing `DashboardData` null-handling convention already specified in the "Dashboard Data Shape" requirement) when no timing signal is available.

**Rationale:** Keeps this change scoped to reusing existing data. Matches the existing convention (`avg_conf`, F1, etc. already render `—` when a source is unavailable).

**Alternatives considered:**
- Add `response_time_ms` column to `messages` and populate it in `chat-api`'s message-write path — ruled out as scope creep on a UI-focused change; flagged as an Open Question for a possible follow-up change.

### Decision 4: "Frequently Asked Topics" via keyword frequency over conversation titles

**Choice:** Reuse the existing `sideRows`/mini-bar-chart structure. Instead of `_business_top_fields` grouping `extracted_entities.entity_id`, a new `_business_topic_frequency` groups tokenized words (lowercased, stopwords removed) from the user's own `conversations.title` values (already populated by `derive_conversation_title`), taking the top 5 by frequency, with `pct` computed the same way (`count / total * 100`).

**Rationale:** No topic/category field exists anywhere in the schema; titles are the only structured-enough text available without adding a classification pipeline. This is explicitly called out as an approximation in the proposal's Open Questions.

**Alternatives considered:**
- Classify each user message via an LLM call at read time — ruled out: expensive per dashboard load, and conflicts with the 30s polling interval (would hammer the LLM provider).
- Store a `topic` field on `messages` at write time (chat-api) — ruled out as scope creep; flagged as an Open Question / possible follow-up.

## Risks / Trade-offs

- [Reading `chat-api`'s tables directly from the gateway couples the two services' schemas — a future `chat-api` migration that renames/drops `conversations`/`messages`/`chat_message_feedback` will silently break the dashboard] → Mitigation: every query is already wrapped in try/except per the existing `Dashboard Summary Endpoint` requirement (failed query → field `null`, `sources.*` → `false`, request still succeeds), so a schema drift degrades gracefully (fields show `—`) rather than 500ing.
- [Keyword-frequency "Frequently Asked Topics" may produce low-quality or noisy topics for a low-volume user (few conversations)] → Mitigation: same graceful-degradation pattern — empty/sparse `sideRows` renders an empty section, not an error; proposal explicitly frames this as a v1 approximation.
- [Assistant status check adds one more outbound HTTP call (to `chat-api` `/health`) on every dashboard load / 30s poll] → Mitigation: reuse the existing short-timeout, best-effort pattern already used by `_fetch_active_model`; a slow/failed health check degrades to "Offline" rather than blocking the response.
- [Business Users seeing only their *own* conversations (not tenant-wide) is a scope decision not explicit in the requested changes] → Mitigation: called out explicitly in Decision 1 rationale and reflected in the spec scenarios below; matches the general principle that a Business User's dashboard should reflect *their* usage, not the whole tenant's.

## Migration Plan

1. Update `_business_user_data`, add `_business_conversation_activity` (replaces `_business_extraction_activity`) and `_business_topic_frequency` (replaces `_business_top_fields`) in `dashboard.py`.
2. Add `_fetch_assistant_health` (new, mirrors `_fetch_active_model`'s HTTP pattern) and wire it into `_business_user_data`.
3. Update `_ROLE_SERVICES["business_user"]` and `_null_sources()` sources keys (`extraction`, `models` → `conversations`, `feedback`, `assistant_health`).
4. Update `sideRows` mini-bar-chart rendering unaffected (frontend is data-driven, no component changes required).
5. Update `openspec/specs/portal-dashboard/spec.md` business_user scenarios (delta spec in this change).
6. No data migration or backfill needed — all source tables already populated.
7. Rollback: revert the `dashboard.py` handler changes; no schema/data changes to roll back.

## Open Questions

- Should Business Users see tenant-wide conversation stats (all users' conversations) or only their own? This design assumes **own conversations only** (Decision 1) — confirm before implementation.
- Should "Average Response Time" instrumentation (Decision 3 alternative) be scoped as a fast-follow change once this ships, or left indefinitely as `—`?
- No in-force ADR needs revisiting for this change.
