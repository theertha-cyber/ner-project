## 1. Schema Reconciliation Migration

- [x] 1.1 Create Alembic migration `012_reconcile_training_jobs_columns.py` that adds missing columns (`metrics` JSONB, `hyperparams` JSONB, `current_epoch`, `current_loss`, `celery_task_id`, `model_version_id`) to `tenant_template.training_jobs` using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- [x] 1.2 Extend migration 012 to add missing columns (`metrics` JSONB) to `tenant_template.model_versions` using `IF NOT EXISTS`
- [x] 1.3 Extend migration 012 to iterate over all existing `tenant_{id}` schemas and apply the same column additions idempotently
- [x] 1.4 Run `alembic upgrade head` and verify the migration runs cleanly against local DB (ran 012 and created 013 for missing `created_at`/`failed_at` columns)

## 2. Route and Handler Wiring

- [x] 2.1 Add `"extraction"` to the `_null_sources()` dictionary and to the `_ROLE_SERVICES` mappings
- [x] 2.2 Add `tenant_id: str = Depends(get_request_tenant_id)` dependency to `get_dashboard_summary` route handler
- [x] 2.3 Update route dispatch to pass `db` and `tenant_id` to all role handlers (not just system_admin):
      `data, sources = await handler(db, tenant_id)` for all roles
- [x] 2.4 Add `user_id` extraction from `request.state.user_id` to the route handler for annotator role

## 3. Tenant Admin Queries (`_tenant_admin_data`)

- [x] 3.1 Refactor `_tenant_admin_data` signature to accept `db: AsyncSession` and `tenant_id: str`
- [x] 3.2 Write query for document count: `SELECT COUNT(*) FROM tenant_{id}.documents WHERE status != 'error'`
- [x] 3.3 Write query for annotation progress: `SELECT COUNT(*) FILTER (WHERE status = 'annotated')::float / NULLIF(COUNT(*), 0) * 100 FROM tenant_{id}.documents`
- [x] 3.4 Write query for active model F1: `SELECT metrics->>'f1' FROM tenant_{id}.model_versions WHERE status = 'promoted' ORDER BY promoted_at DESC LIMIT 1`
- [x] 3.5 Write query for training count (last 24h): `SELECT COUNT(*) FROM tenant_{id}.training_jobs WHERE created_at >= NOW() - INTERVAL '24 hours'`
- [x] 3.6 Build pipeline activity rows from recent training jobs, document uploads, and model promotions (up to 4 rows with status-aware tag/tk colours)
- [x] 3.7 Build side panel: active model eval F1, precision/recall/loss metrics, and quota usage rows (documents, storage, model versions)

## 4. Annotator Queries (`_annotator_data`)

- [x] 4.1 Refactor `_annotator_data` signature to accept `db: AsyncSession`, `tenant_id: str`, and `user_id: str`
- [x] 4.2 Write query for assigned task count: `SELECT COUNT(*) FROM tenant_{id}.annotation_tasks WHERE annotator_user_id = :user_id`
- [x] 4.3 Write query for confirmed spans: `SELECT COUNT(*) FROM tenant_{id}.spans`
- [x] 4.4 Write query for suggestion count: `SELECT COUNT(*) FROM tenant_{id}.suggested_spans`
- [x] 4.5 Write query for completion %: task completion ratio for the current user
- [x] 4.6 Build task activity rows: recent tasks with document name, status, span/suggestion count
- [x] 4.7 Build side panel: total span count, 500-span threshold bar, doc count, entity type count, today's spans, span-by-entity-type breakdown

## 5. Business User Queries (`_business_user_data`)

- [x] 5.1 Refactor `_business_user_data` signature to accept `db: AsyncSession` and `tenant_id: str`
- [x] 5.2 Write query for extracted document count: `SELECT COUNT(DISTINCT document_id) FROM tenant_{id}.extracted_entities`
- [x] 5.3 Write query for total entity count: `SELECT COUNT(*) FROM tenant_{id}.extracted_entities`
- [x] 5.4 Write query for avg confidence: `SELECT AVG(confidence) FROM tenant_{id}.extracted_entities`
- [x] 5.5 Write query for auto-cleared %: ratio of entities with `review_status = 'auto_cleared'`
- [x] 5.6 Build extraction activity rows: recent extraction runs with document name, entity count, confidence, processing time
- [x] 5.7 Build side panel: active model eval F1, precision/recall/loss, top extracted fields by count

## 6. Tests

- [x] 6.1 Write integration test for `_system_admin_data` confirming tenant count query works and partial failure produces null + sources=false
- [x] 6.2 Write integration test for `_tenant_admin_data` with seeded tenant schema: verify all 4 stats return expected values
- [x] 6.3 Write integration test for `_tenant_admin_data` graceful degradation: mock query failure and verify null + sources=false
- [x] 6.4 Write integration test for `_annotator_data` with seeded tasks/spans: verify task count, span count, completion %
- [x] 6.5 Write integration test for `_business_user_data` with seeded extractions: verify doc count, entity count, avg confidence, auto-cleared %
- [x] 6.6 Write integration test confirming route dispatch passes `db`+`tenant_id` to all handlers
- [x] 6.7 Verify all existing dashboard tests still pass after handler signature changes
- [x] 6.8 Fill in Verification Artifact column in `verification.md` § Spec Alignment for every row

## 7. Demo Seed Data

- [x] 7.1 Extend existing seed script (or create new) to create a demo tenant with an active tenant_admin user
- [x] 7.2 Seed demo documents (5-10) with various statuses (uploaded, processing, annotated)
- [x] 7.3 Seed demo annotation tasks assigned to the tenant_admin user with completed spans
- [x] 7.4 Seed a promoted model version with realistic metrics (F1, precision, recall, loss)
- [x] 7.5 Seed demo training jobs with varied statuses (completed, running, queued)
- [x] 7.6 Seed demo extraction runs and extracted entities with varied confidence scores
- [ ] 7.7 Verify dashboard shows non-placeholder data for all three roles after seeding (manual)

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [x] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 8.6 Run `openspec validate fix-dashboard-queries --type change --strict` and confirm it exits clean before archive

## 9. Runtime Dashboard Defect Fixes

### 9.1 Business user — avg confidence + auto-cleared show '-' / 'service unavailable'

Root cause: `AVG(confidence)` returns SQL `NULL` when `extracted_entities` is empty (no extractions run yet). The backend sets `avg_conf = None` and `auto_cleared_pct = None`, which the stat builder maps to `sub = "service unavailable"`. Additionally, the "Avg confidence" stat has `unit=""` even though the value is already formatted as `f"{val * 100:.0f}"`, so it would display as a bare number (e.g. "85") with no `%` sign.

- [x] 9.1.1 In `_business_user_data` (`dashboard.py:511`), when `AVG(confidence)` returns `None` (empty table), set `avg_conf = "0"` rather than leaving it `None` — and set the accompanying sub-label to `"no extractions yet"` instead of `"service unavailable"`. Same pattern for `auto_cleared_pct` at line 521.
- [x] 9.1.2 Fix the unit field for the "Avg confidence" stat at line 543: change `unit=""` → `unit="%"` so the value renders as "85%" not "85".
- [x] 9.1.3 Seed a `business_user` account for `demo-tenant` in `seed.py` (email `bizuser@democorp.io`, password `Demo123!`) so the role can be logged in against the seeded extraction data.

### 9.2 Tenant admin — annotation progress stuck at 0%

Root cause: The annotation progress query at `dashboard.py:154` checks `documents.status = 'annotated'`, but the annotation workflow (per the portal-annotation spec) updates `annotation_tasks.status` to `'completed'` — it never writes `'annotated'` back to `documents.status`. So the query always returns 0 for real tenants. The seed also uses the wrong status values (`'annotated'` / `'open'`) for annotation tasks rather than the real values (`'completed'` / `'pending'`).

- [x] 9.2.1 Replace the `ann_pct` query in `_tenant_admin_data` (`dashboard.py:153-159`) with a query against `annotation_tasks`: `SELECT COUNT(DISTINCT document_id) FILTER (WHERE status = 'completed')::float / NULLIF(COUNT(DISTINCT document_id), 0) * 100 FROM {schema}.annotation_tasks`
- [x] 9.2.2 In `seed.py`, update the seeded annotation task statuses from `'annotated'` / `'open'` → `'completed'` / `'pending'` to match the real status values the annotation workflow writes.

### 9.3 Annotator — suggestions card shows 0 and completion shows 0

Root cause (suggestions): The seed never inserts any rows into `suggested_spans` (the pre-label feature populates this table at runtime, but it hasn't been run against demo docs). `COUNT(*) FROM suggested_spans` returns `0`.

Root cause (completion): The completion query at `dashboard.py:337` checks `annotation_tasks.status = 'annotated'`, but the real status for a finished task is `'completed'` (per the portal-annotation spec). The seed also assigns all tasks to `tenant_admin_id`, not to any annotator user — so a manually-created annotator sees 0 tasks and a `NULL` completion ratio.

- [x] 9.3.1 Fix the completion query in `_annotator_data` (`dashboard.py:337`): change `status = 'annotated'` → `status = 'completed'`.
- [x] 9.3.2 Seed an annotator user for `demo-tenant` in `seed.py` (email `annotator@democorp.io`, password `Demo123!`, role `annotator`). Assign the 5 seeded annotation tasks to this annotator's user ID (not `tenant_admin_id`), with 3 tasks having `status = 'completed'` and 2 having `status = 'pending'`.
- [x] 9.3.3 Seed ~20 `suggested_spans` rows across the first 5 demo documents in `seed.py` (reuse the `entity_types` list, vary confidence 0.55–0.80) so the suggestions card shows a non-zero count.

### 9.4 System admin — 3 cards hardcoded as '-' / 'service unavailable'

Root cause: `_system_admin_data` (`dashboard.py:106-109`) hardcodes `None` for "Documents (all)", "Pending approvals", and "Avg model F1" — no queries are implemented for these three cards.

- [x] 9.4.1 Implement the "Documents (all)" query: fetch all active tenant IDs from `public.tenants`, then run `SELECT SUM(cnt) FROM (SELECT COUNT(*) AS cnt FROM tenant_{id}.documents UNION ALL ...) t` built dynamically from the tenant list. Set `sources["documents"] = True` on success; display `"-"` with sub `"no tenants"` if the tenant list is empty.
- [x] 9.4.2 Implement the "Pending approvals" query: same dynamic-schema approach, summing `COUNT(*) FROM tenant_{id}.training_jobs WHERE status = 'pending_approval'` across all tenant schemas.
- [x] 9.4.3 Implement the "Avg model F1" query: for each tenant schema, select `metrics->>'f1'` from the most recently promoted model version; average the non-null values in Python and format as `f"{avg * 100:.1f}"`. Set `sources["models"] = True` on success.
- [x] 9.4.4 Extract a helper `_all_tenant_schemas(db) -> list[str]` in `dashboard.py` that queries `SELECT id FROM public.tenants WHERE status = 'active'` and returns `[_tenant_schema(t) for t in ids]` — reuse it across 9.4.1, 9.4.2, and 9.4.3 to avoid duplicating the tenant-listing query.
