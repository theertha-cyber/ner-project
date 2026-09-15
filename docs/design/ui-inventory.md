# UI Inventory — Tenant Self-Service Data Sources

## Source
Generated mockups: `docs/design/mockup/data-sources.html`, `docs/design/mockup/connection-detail.html`, and `docs/design/mockup/schema-contracts.html`. The human reconfirmed the Clean structural foundation with the existing portal override after the approved CAP-2 API update.

## Codebase Discovery Findings

- Tenant-admin navigation currently exposes document upload but no data-source or connection-management route; the sidebar renders those role-derived links (`src/portal/src/lib/nav-config.ts:27-60`; `src/portal/src/components/app-shell/Sidebar.tsx:35-36,117-124`). SCR-1 adds the approved entry point without changing current routes.
- Existing intake is browser-file upload only: the portal posts authenticated multipart files to `POST /api/v1/documents`, which normalizes them as human-originated `platform_upload` (`src/portal/src/hooks/use-upload.ts:16-70`; `src/document_service/api/v1/documents.py:64-109`). The new screens must not replace this workflow.
- Integration profiles are tenant-bound control-plane records, but the current service explicitly prohibits tenant-admin create, edit, activate, and retire actions (`src/shared/integration_profile/store.py:21-65`; `src/shared/integration_profile/service.py:1-5`). SCR-2 defines the approved new lifecycle while retaining safe display of non-sensitive configuration and outcome classes only.
- Azure Blob is a declared configuration shape, but only platform-default adapters are executable and activation rejects non-executable selections (`src/shared/integration_profile/adapters.py:11-28,38-44`; `src/shared/integration_profile/service.py:161-175`). No tenant-facing source-management UI was found; SCR-1 through SCR-3 describe additions, not current behaviour.
- Current chat SQL is tenant-schema scoped, read-only, relation/column-whitelisted, and time-limited (`src/chat_api/services/sql_generator.py:1107-1144,1146-1219`; `src/chat_api/api/v1/chat.py:183-194`). SCR-3 must not expose database rows, SQL text, credentials, or provider error payloads.

## Navigation Model
Authenticated tenant administrators enter from the existing portal sidebar at `/settings/data-sources`; browser history, deep links, and browser Back are supported. The data-sources list links to source detail and creation. Source detail links to schema-contract management for PostgreSQL connections. Unauthenticated users land on `/login`; non-administrators cannot enter administration routes and receive the portal's existing safe authorization state. At narrow widths, the existing navigation collapses and collection controls remain available without horizontal loss.

## Screens

### SCR-1 — Data Sources
- **Route:** `/settings/data-sources`
- **Purpose:** Lets tenant administrators list, search, filter, and start management of the two approved Azure provider connections.
- **Source reference:** `docs/design/mockup/data-sources.html`
- **Components:** CMP-1, CMP-2, CMP-3, CMP-4, CMP-5
- **States:** Loading reserves table rows; empty state invites configuration; filtered-empty state distinguishes no matches; safe error state offers retry; the returned `draft`, `validated`, `active`, `paused`, `error`, and `retired` statuses are labelled without sensitive details.
- **Collection controls:** Server-backed numbered pagination, 20 per page (`page_size` 1–100); default sort is Last activity descending with ascending `id` as the deterministic tie-breaker; search, provider, and status filters reset to page 1; query, filters, sort, and page are URL-backed; an out-of-range valid page returns an empty list.
- **Data:** Reads `GET /api/v1/data-sources` safe `ConnectionPage` metadata; URL maps only to the allowlisted query parameters; begins `POST /api/v1/data-sources` creation.

### SCR-2 — Data Source Connection
- **Route:** `/settings/data-sources/[connectionId]`
- **Purpose:** Lets a tenant administrator perform the approved create/update/test/activate/pause/replace/retire lifecycle for an Azure Blob Storage or Azure PostgreSQL connection.
- **Source reference:** `docs/design/mockup/connection-detail.html`
- **Components:** CMP-1, CMP-3, CMP-6, CMP-7, CMP-8, CMP-9
- **States:** Draft, validated, test-in-progress, test-failed-safe, activation-blocked, active, paused, error, retired, replacement confirmation, retirement confirmation, idempotent replay, and safe request error. PostgreSQL drift-blocked state links to SCR-3.
- **Collection controls:** Not applicable.
- **Data:** Reads the safe `Connection` shape; writes closed provider configuration and secret-reference fields only through CAP-2 mutation routes with an `Idempotency-Key` (1–128 printable ASCII, scoped to tenant/method/path/body digest, 24-hour replay). Values are write-only; detail reads configured/secret field names, finite outcomes, evidence status, lifecycle state, schedule, replacement links, and safe aggregate sync outcomes. Errors render finite safe codes with the request ID.

### SCR-3 — Schema Contracts
- **Route:** `/settings/data-sources/[connectionId]/schema-contracts`
- **Purpose:** Lets a tenant administrator upload, validate, publish, and inspect a versioned JSON schema contract required for direct PostgreSQL chat; this is the companion flow and not a CAP-2 lifecycle API surface.
- **Source reference:** `docs/design/mockup/schema-contracts.html`
- **Components:** CMP-1, CMP-3, CMP-5, CMP-8, CMP-10
- **States:** Loading, no-published-contract, validation-in-progress, valid draft, invalid contract with field-level safe errors, published, drift-blocked, and request error.
- **Collection controls:** Contract-history table uses numbered pagination, 20 per page; default sort Published at descending; version search resets to page 1 and URL retains sort and paging.
- **Data:** Reads and writes canonical version metadata, validation outcome, published state, and safe drift status; no database rows or SQL text are displayed.

## Components

### CMP-1 — Authenticated Admin Shell
- **Used on:** SCR-1, SCR-2, SCR-3
- **Variants:** Desktop sidebar, collapsed responsive navigation, light, dark.
- **States:** Current route, keyboard focus, expanded/collapsed navigation.
- **Source reference:** Existing portal app shell and mockups.

### CMP-2 — Source Table
- **Used on:** SCR-1
- **Variants:** Full results, loading skeleton, empty, filtered-empty, error.
- **States:** Sortable headers, pagination, safe status cells, keyboard-operable row actions.
- **Source reference:** `data-sources.html`.

### CMP-3 — Safe Status Badge
- **Used on:** SCR-1, SCR-2, SCR-3
- **Variants:** Draft, testing, active, paused, failed, blocked, drift detected.
- **States:** Default and accessible text equivalent; colour is never the sole signal.
- **Source reference:** Mockups.

### CMP-4 — Source Filters
- **Used on:** SCR-1
- **Variants:** Search field, provider select, status select, clear filters.
- **States:** Focus, populated, disabled during refresh, no-results announcement.
- **Source reference:** `data-sources.html`.

### CMP-5 — Pagination
- **Used on:** SCR-1, SCR-3
- **Variants:** First, middle, last, single-page.
- **States:** Current, enabled, disabled, loading with stable layout.
- **Source reference:** Mockups.

### CMP-6 — Provider Configuration Form
- **Used on:** SCR-2
- **Variants:** Azure Blob Storage, Azure Database for PostgreSQL.
- **States:** Draft, field focus, inline validation, submit error, test-in-progress, write-only saved values, and locked while active or retired.
- **Source reference:** `connection-detail.html`.

### CMP-7 — Connection Lifecycle Panel
- **Used on:** SCR-2
- **Variants:** Test, activate, pause, replace, retire.
- **States:** Disabled until prerequisites pass, activation-evidence checklist, confirmation modal, action loading, idempotent replay, and finite safe result.
- **Source reference:** `connection-detail.html`.

### CMP-8 — Safe Outcome Notice
- **Used on:** SCR-2, SCR-3
- **Variants:** Success, warning, blocked, error.
- **States:** Dismissible only when it does not hide an activation or drift block.
- **Source reference:** Mockups.

### CMP-9 — Sync Activity Summary
- **Used on:** SCR-2
- **Variants:** Active schedule, paused schedule, no run yet, safe failure.
- **States:** Loading and error retain the panel layout.
- **Source reference:** `connection-detail.html`.

### CMP-10 — Schema Contract Upload and History
- **Used on:** SCR-3
- **Variants:** JSON file picker, validation results, publish control, version-history table.
- **States:** File selected, invalid JSON, semantic validation failure, valid draft, publishing, published, drift block.
- **Source reference:** `schema-contracts.html`.

## Standard-Rules Additions
| Item | Screen | Why it was added |
| --- | --- | --- |
| URL-backed search, filters, sort, page size, range, and total | SCR-1, SCR-3 | Required for shareable, stable administration collections. |
| Loading, empty, filtered-empty, and safe error states | SCR-1, SCR-3 | Requirement names safe status but not complete data-view states. |
| Inline validation and summary linked to invalid fields | SCR-2, SCR-3 | Connection and contract forms require recoverable validation. |
| Explicit keyboard focus order and visible focus ring | SCR-1, SCR-2, SCR-3 | Required accessibility coverage. |
| Confirmation for destructive lifecycle actions | SCR-2 | Prevents accidental retirement or replacement of an active source. |
| Provider-specific closed configuration fields and write-only saved values | SCR-2 | CAP-2 rejects arbitrary fields and never returns values or secret references. |
| Idempotency-key action treatment and replay notice | SCR-2 | Every CAP-2 mutation requires the key and may safely replay a prior result. |

## Gaps
Secret-reference picker implementation, browser support, localisation, and tenant-specific approval workflow wording remain implementation-contract decisions. They must preserve the CAP-2 closed-schema and safe-display boundaries.

## Revision History

- 2026-09-10 (redo after wind-back): Re-saved with approved `## Codebase Discovery Findings` retained; SCR-1–SCR-3, CMP-1–CMP-10, Clean existing-portal override, and CAP-2 collection/lifecycle bindings unchanged. Human authorization to supersede obsolete feature-specific specs retained. Re-saved so the Design-gate artifact postdates the 2026-09-10 wind-back.
- 2026-09-10 (re-save after rewritten CAP-2 contract): Rewritten TDD `docs/design/tenant-self-service-data-sources.md` re-verified as the explanatory authority (normative authority: `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md`). `## Codebase Discovery Findings` retained verbatim; SCR-1–SCR-3 and CMP-1–CMP-10 identifiers unchanged; Clean existing-portal override and no-asset scope unchanged. Tightened rewritten-contract bindings only: `page_size` 1–100 with ascending-`id` tie-breaker and out-of-range empty page (SCR-1), tenant/method/path/body-scoped 24-hour idempotency replay plus finite safe error codes with request ID (SCR-2). Visual direction untouched; no functionality implemented.
