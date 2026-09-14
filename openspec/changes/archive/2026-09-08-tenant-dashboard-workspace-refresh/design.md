## Context

Today `_tenant_admin_data` (in [dashboard.py](src/gateway/api/v1/dashboard.py)) sets the hero to `kicker="Good morning"`, `title="Pipeline overview."`, `line="document processing and training pipeline at a glance."`, and `pTitle="Pipeline activity"`. The row list comes from `_tenant_pipeline_activity` → `_tenant_activity_rows`, which does a `UNION ALL` across `training_jobs`, `documents`, `annotation_tasks`, and `extraction_runs`, ordered by timestamp, and labels each row from its raw `status` column (e.g. "Training running", "Status: uploaded"). The same function backs `GET /api/v1/dashboard/activity` (the "View all" slide-over), capped at 200 rows. `ActivityRow` (Pydantic model and matching `ActivityRow` TS type) currently has `title`, `sub`, `tag`, `tk`, `go` — no icon, no timestamp field; the timestamp is discarded after ordering.

There is no dedicated audit-log table. Everything the new event catalogue needs must be derived from existing columns: `training_jobs.status` transitions, `model_versions.status`/`promoted_at`, `documents` row counts/`created_at`, `annotation_tasks` completion counts, `extraction_runs.status`, and `public.tenant_users.role`/`created_at` filtered by `tenant_id`.

## Goals / Non-Goals

**Goals:**

- Reword the `tenant_admin` hero (`title`, `line`) to describe the workspace, not the pipeline. Backend-only string change.
- Rename `pTitle` from "Pipeline activity" to "Recent Activity" for `tenant_admin`.
- Replace `_tenant_activity_rows`'s raw-row selection (for the `tenant_admin` path only) with a curated event query that emits only the operationally meaningful event kinds listed in the proposal, each carrying an `icon` key and a relative-time string.
- Keep `GET /api/v1/dashboard/activity` (the expanded history) sourced from the same event catalogue so "View all" doesn't regress to raw rows.
- Extend `ActivityRow` (Pydantic + TS) with `icon: str` and `time: str` (relative), and render both in `ActivityPanel`.

**Non-Goals:**

- No new audit-log table, no new event-sourcing infrastructure. Events are derived from existing state at query time.
- No change to `system_admin`, `annotator`, or `business_user` hero copy, `pTitle`, or activity sourcing — they keep their existing `_tenant_activity_rows`-independent logic (annotator/business_user already have their own row builders; only `system_admin`'s approval queue and `tenant_admin`'s pipeline rows currently share `_tenant_activity_rows`, and system_admin's approval queue is untouched — see Decision 3).
- No pixel-level restyle of `ActivityPanel`; only adding an icon glyph and a timestamp string into the existing row layout.
- No retroactive backfill: events surfaced are whatever the underlying tables already contain (e.g., a job already completed before this ships still shows as "Model training completed", not two rows for "requested" then "completed").

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 tenant-data-isolation | All tenant data lives in per-tenant `tenant_<id>` schemas, queried via schema-qualified SQL | New event queries must stay schema-scoped (`{schema}.training_jobs`, etc.) exactly like the existing code; `public.tenant_users` queries must filter by `tenant_id` |
| ADR-004 openspec-governance | Spec-driven workflow governs behaviour changes | This change goes through proposal → design → specs → tasks as followed here |

No other ADR in `docs/adr/` touches dashboard rendering, event modelling, or the gateway's role-based data assembly, so no other ADR constrains this design.

## Decisions

### Decision 1: Derive events from existing columns via a UNION query, not a new audit table

**Choice:** Extend the existing `UNION ALL` pattern in `_tenant_activity_rows` (tenant_admin branch) to pull from `training_jobs`, `model_versions`, `documents`, `extraction_runs`, and `public.tenant_users`, mapping each source row to one of the ten curated event kinds via its `status` value (and, for `documents`, a size/row-count threshold for "large upload"; for `annotation_tasks`, a completion-count threshold for "dataset reached training readiness").

**Rationale:** No audit log exists; building one is a much larger change (schema migration, write-path instrumentation across every service) than this UX-focused proposal warrants. Existing columns already carry enough state (status enums, `promoted_at`, `created_at`) to classify events after the fact.

**Alternatives considered:**
- New `activity_log` table written by every service on state change — most accurate and extensible, but requires migrations and write-path changes in training_service, extraction_service, document_service, and gateway; deferred as a future capability if the derived approach proves too lossy.
- Keep the raw union and just relabel titles — rejected because it doesn't satisfy the requirement to *filter out* low-level noise (e.g. every document upload, every annotation task status flip); the ask is fewer, more meaningful rows, not just prettier labels on the same rows.

### Decision 2: One curated event kind per underlying status transition, computed per-row (no delta/diff tracking)

**Choice:** Each event kind maps to a specific `(source_table, status_value)` pair read directly off the row (e.g. `model_versions.status == 'promoted'` → "Model deployment"; `training_jobs.status == 'failed'` → "Training failure"). "Model training requested" = `training_jobs.status == 'pending_approval'`; "Model training approved" = `training_jobs.status == 'queued'` AND the job has left `pending_approval` (inferred by `started_at IS NULL AND status = 'queued'`, since a fresh `queued` job created directly, without approval, doesn't apply to tenant-triggered training — confirmed in design review, tenant admins request training via the same approval flow per `training-approval` spec).

**Rationale:** Avoids needing to store or diff previous status per row; the UNION already scans current state, so classification stays a pure per-row function of the columns that exist today.

**Alternatives considered:**
- Track status transitions explicitly (store "previous status" somewhere) to distinguish "requested" from "approved" more robustly — rejected as more mechanism than the proposal's UX goal justifies; current-state inference is good enough and the two events differ enough by `status` value alone.

### Decision 3: `system_admin`'s approval queue stays on the old raw builder

**Choice:** Only the `tenant_admin` branch's call into `_tenant_activity_rows`/`_tenant_pipeline_activity` is replaced. `system_admin`'s approval queue (lines ~193-199, a separate hardcoded/placeholder list, not fed by `_tenant_activity_rows`) is untouched, and `annotator`/`business_user` already have independent row builders (`_annotator_data`, `_business_user_data`).

**Rationale:** Proposal explicitly scopes to tenant_admin; `_tenant_activity_rows` is already only invoked from the tenant_admin path today, so no other role is affected by the query rewrite.

**Alternatives considered:**
- Generalize the curated-event catalogue to all roles — out of scope per proposal; would also require redesigning each role's distinct panel semantics (approval queue, task list, extraction list), which the proposal does not ask for.

### Decision 4: Icon field is a string key resolved client-side, not a URL or raw SVG

**Choice:** `ActivityRow.icon` is a small string enum (e.g. `"training"`, `"approval"`, `"deploy"`, `"failure"`, `"batch"`, `"dataset"`, `"upload"`, `"user"`) resolved to a `lucide-react` icon component in `ActivityPanel.tsx` via a lookup map, mirroring the existing `TAG_COLOURS` lookup pattern in that file.

**Rationale:** `lucide-react` is already a portal dependency (used in `Sidebar.tsx`, `Topbar.tsx`, `nav-config.ts`); a string-key lookup keeps the backend free of any rendering concern and matches the existing `tk` → colour lookup convention in the same component.

**Alternatives considered:**
- Emoji or literal icon glyphs from the backend — rejected, inconsistent with the rest of the portal's icon system and harder to theme.

### Decision 5: Relative timestamp formatted server-side as a plain string

**Choice:** Add `time: str` to `ActivityRow`, computed server-side from the row's timestamp against `now()` at request time (e.g. "2 hours ago", "Yesterday", "3 days ago"), rather than sending an ISO timestamp and formatting client-side.

**Rationale:** Matches the existing pattern where the backend already fully formats display strings (`doc_sub`, `tag`, etc.); avoids adding a date-formatting dependency to the portal for a single field. `refetchInterval: 30_000` in `use-dashboard-data` keeps the string acceptably fresh.

**Alternatives considered:**
- Send raw ISO timestamp, format client-side with a relative-time library — more "correct" (updates between refetches without a network round trip) but adds a new frontend dependency for one field; rejected as unnecessary given the 30s refetch cadence.

## Risks / Trade-offs

- [Threshold-based events ("large document upload", "dataset reached training readiness") need a concrete numeric cutoff that doesn't exist in code today] → Pick explicit constants in tasks.md (e.g. large upload = file size or page count above existing per-request limits already enforced elsewhere; dataset readiness reuses the 500-span threshold already defined for the annotator's "Dataset readiness" panel per `portal-dashboard` spec) and document them as scenario-level requirements in specs.md so they're testable, not just tuned ad hoc.
- [Curated catalogue may surface fewer than 4-5 rows for a quiet tenant, leaving gaps] → Reuse the existing placeholder-padding pattern (`_tenant_pipeline_activity` already pads to 5 rows with `"—"` placeholders) unchanged.
- [`public.tenant_users` query for "added" events crosses from tenant schema into the shared `public` schema] → Already an established pattern elsewhere in this file (`_all_tenant_schemas`, tenant lookups in `_tenant_admin_data`'s quota check both hit `public.tenants`), and ADR-001 permits `public` schema reads scoped by `tenant_id`.
- [Existing tests assert on "Pipeline overview." / "Pipeline activity" strings and raw-row shapes] → Enumerated in proposal's Impact section; update alongside the implementation, not a follow-up.

## Migration Plan

No data migration required — this is a query-and-copy change only, backward compatible at the schema level (new `icon`/`time` fields are additive to `ActivityRow`). Deploy as a normal gateway + portal release. Rollback is a plain revert (no state to unwind).

## Open Questions

- Exact numeric thresholds for "large document upload" and reuse of the 500-span dataset-readiness threshold — to be finalized as testable scenarios in specs.md rather than left as design prose.
- Whether "Model training requested" should be attributed to a specific requester (needs `training_jobs` to carry a `requested_by`/`created_by` user reference) or stay unattributed — check if that column exists; if not, ship without an attributed actor and note as a future enhancement rather than adding a migration to this change.
- None of the currently-in-force ADRs need revisiting for this change.
