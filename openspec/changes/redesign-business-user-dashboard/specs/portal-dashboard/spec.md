## MODIFIED Requirements

### Requirement: Dashboard Data Shape

The system SHALL define a `DashboardData` TypeScript type that mirrors the mockup's `dashData(role)` shape. Every role's dashboard SHALL include: `kicker` (string), `title` (string), `line` (string), `stats` (array of 4 `StatItem`), `pTitle` (string), `pMeta` (string), `pRows` (array of 4 `ActivityRow`), `sideTop` (string), `sideMeta` (string), `big` (string), `bigUnit` (string), `bar` (number 0–100), `sideMetrics` (array of 3 `{k, v}`), `sideBot` (string), `sideRows` (array of `{label, val, pct, c}`). Numeric values that cannot be fetched from an unavailable service SHALL be `null`; the component SHALL render `—` in place of `null`.

#### Scenario: system_admin data shape

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Platform control plane"`, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, and a side panel titled "Platform health" with SLA, latency, error rate, and GPU metrics
- **AND** the `sideRows` section contains storage usage by tenant (label, val, pct, colour)

#### Scenario: tenant_admin data shape

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training count), `pTitle: "Pipeline activity"` with 4 activity rows (training run, dataset approval, document processing, model promotion), and a side panel titled "Active model" with eval F1, precision, recall, loss, and quota usage rows (Documents, Storage, Model versions)

#### Scenario: annotator data shape

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Assigned tasks, Spans confirmed, Suggestions, Completion %), `pTitle: "My tasks"` with 4 task rows (showing document name, status, span/suggestion count), and a side panel titled "Dataset readiness" with span progress bar toward 500-span threshold, doc/type/today metrics, and span-by-entity-type breakdown

#### Scenario: business_user data shape

- **GIVEN** the authenticated user has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Your AI assistant workspace"`, `title` and `line` copy describing the user's assistant usage rather than document extraction
- **AND** `stats` contains exactly 3 items: "Conversations" (total conversations started by this user), "Messages Sent" (total user-authored messages), and "Helpful Responses" (count derived from this user's `up` ratings in `chat_message_feedback`)
- **AND** `pTitle: "Recent Conversations"` with up to 4 rows, each row showing the conversation title (or generated summary), last interaction time, and message count, linking to the conversation in chat
- **AND** the side panel is titled `sideTop: "AI Assistant Status"` showing assistant online/offline status, last updated time, and average response time (or `—` if unavailable) — it SHALL NOT show F1, precision, recall, or loss
- **AND** `sideBot: "Frequently Asked Topics"` with `sideRows` populated from keyword frequency over this user's own conversation titles

#### Scenario: partial service failure degrades gracefully

- **GIVEN** the training service is unavailable when the dashboard is fetched
- **WHEN** the dashboard renders
- **THEN** stat cards whose values depend on the training service show `—` instead of a number
- **AND** stat cards that depend only on available services show their real values
- **AND** no full-page error screen is shown

---

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL return a role-appropriate `DashboardData` JSON object assembled from the tenant's database tables directly (gateway queries tenant schema tables rather than calling downstream services for MVP). The response SHALL include a top-level `sources` object mapping each data domain (`"tenants"`, `"training"`, `"documents"`, `"annotations"`, `"models"`, `"extraction"`, `"conversations"`, `"feedback"`, `"assistant_health"`) to `true` (data retrieved) or `false` (query failed or not applicable for this role).

Each role handler SHALL accept the `db` session and `tenant_id` parameters and execute real SQL queries against the tenant's schema. Every query SHALL be wrapped in try/catch with independent error handling — a failed query SHALL set the affected fields to `null`, the corresponding `sources.*` flag to `false`, and SHALL NOT fail the entire request.

#### Scenario: system_admin summary returns real data from wired sources

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response includes the real tenant count in `stats[0].value`
- **AND** `sources.tenants` is `true`
- **AND** training-dependent fields (pending approvals count, avg F1) are fetched from the training service

#### Scenario: tenant_admin summary returns real data from wired sources

- **GIVEN** the caller has role `tenant_admin` and the tenant has documents, annotations, model versions, and training jobs
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` SHALL contain the real document count from the tenant's `documents` table
- **AND** `stats[1].value` SHALL contain the annotation completion percentage
- **AND** `stats[2].value` SHALL contain the promoted model's F1 score
- **AND** `stats[3].value` SHALL contain the training job count

#### Scenario: annotator summary returns real task data

- **GIVEN** the caller has role `annotator` and has assigned annotation tasks
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` SHALL contain the count of assigned tasks
- **AND** `stats[1].value` SHALL contain the count of confirmed spans
- **AND** `stats[3].value` SHALL contain the task completion percentage

#### Scenario: business_user summary returns real conversation and feedback data

- **GIVEN** the caller has role `business_user` and has started conversations with the assistant
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` ("Conversations") SHALL contain the count of conversations in `{schema}.conversations` where `user_id` matches the caller
- **AND** `stats[1].value` ("Messages Sent") SHALL contain the count of `role = 'user'` rows in `{schema}.chat_messages` belonging to the caller's conversations
- **AND** `stats[2].value` ("Helpful Responses") SHALL contain the count of `rating = 'up'` rows in `{schema}.chat_message_feedback` belonging to the caller
- **AND** the query SHALL scope every row to the caller's own `user_id`, not the whole tenant

#### Scenario: business_user summary includes assistant status

- **GIVEN** the caller has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called and `chat-api`'s `/health` endpoint responds successfully within the configured timeout
- **THEN** the `AI Assistant Status` panel SHALL show "Online" and `sources.assistant_health` SHALL be `true`

#### Scenario: business_user summary shows offline status when chat-api health check fails

- **GIVEN** the caller has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called and the call to `chat-api`'s `/health` endpoint times out, errors, or returns a non-200 status
- **THEN** the `AI Assistant Status` panel SHALL show "Offline"
- **AND** `sources.assistant_health` SHALL be `false`
- **AND** the overall request SHALL still succeed (no 500 error)

#### Scenario: sources map includes all data domains

- **GIVEN** the dashboard summary is generated for any role
- **WHEN** the response is inspected
- **THEN** the `sources` object SHALL contain keys for all data domains relevant to that role
- **AND** each key SHALL be `true` if the query succeeded, `false` otherwise

#### Scenario: unauthenticated request rejected

- **GIVEN** the request carries no valid JWT
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Activity Panel

The dashboard page SHALL render a primary activity panel displaying `pTitle` and `pMeta` as the panel header, followed by a list of exactly 4 `ActivityRow` items. Each row SHALL show: a coloured dot indicator (left side), `title` (primary text), `sub` (secondary text), and a coloured status `tag` pill (right-aligned). The dot indicator SHALL be a small `<div>` with `border-radius: 50%` coloured according to the row's `tk` status key (same colour mapping as the existing tag colours).

Each row SHALL be clickable and navigate to the screen identified by `row.go` (mapped via `navFor` hrefs — `"training"` → `/training-jobs`, `"annotation"` → `/annotation`, `"documents"` → `/documents`, `"extractions"` → `/extractions`, `"models"` → `/models`, `"chat"` → `/chat`).

#### Scenario: activity row navigates on click

- **GIVEN** a `system_admin` activity row has `go: "training"`
- **WHEN** the user clicks the row
- **THEN** the router navigates to `/training-jobs`

#### Scenario: business_user conversation row navigates to chat

- **GIVEN** a `business_user` activity row has `go: "chat"` and represents a conversation with id `conv-123`
- **WHEN** the user clicks the row
- **THEN** the router navigates to `/chat?conversation=conv-123`

#### Scenario: status dot and tag render correct colours

- **GIVEN** a row has `tk: "pending_approval"`
- **WHEN** the row renders
- **THEN** the dot indicator and tag use the amber/warn colour (`var(--warn-soft)` background, `var(--warn)` text)
- **AND** the tag is positioned to the right of the title/sub text
- **AND** a row with `tk: "completed"` uses the green/good colour (`var(--good-soft)` background, `var(--good)` text)
- **AND** a row with `tk: "running"` shows a pulsing dot animation
