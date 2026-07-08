# Verification Plan

**Change:** fix-tenant-schema-drift-and-training-worker-config
**Generated:** 2026-07-08
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | tenant-schema-migrations | Tenant-scoped migrations propagate to existing tenant schemas | A new column is added to a tenant-scoped table | Given an existing tenant schema and a migration that adds column `foo` to `tenant_template.some_table`, when the migration is applied, then both `tenant_template.some_table` and the existing tenant's `some_table` have column `foo` | tests/test_tenant_schema_migrations.py | - [x] |
| 2 | tenant-schema-migrations | Tenant-scoped migrations propagate to existing tenant schemas | An inactive tenant's schema is still updated | Given a tenant with `status: "inactive"` and a migration that changes a tenant-scoped table, when the migration is applied, then the inactive tenant's schema receives the same DDL as active tenants | tests/test_tenant_schema_migrations.py | - [x] |
| 3 | tenant-schema-migrations | Tenant-scoped migrations propagate to existing tenant schemas | Re-running the migration DDL is a no-op | Given a tenant schema that already has the shape a migration's DDL would produce, when that DDL is executed again, then no error occurs and the schema is unchanged | tests/test_tenant_schema_migrations.py | - [x] |
| 4 | tenant-schema-migrations | The `training_jobs.error_message` column is backfilled onto the template and every existing tenant schema | `tenant_template` and existing tenants gain the missing column | Given `tenant_template.training_jobs` and every existing tenant's `training_jobs` table lack `error_message`, when the remediation migration is applied, then `tenant_template` and every tenant schema's `training_jobs` table has `error_message`, with existing rows preserved and `NULL` for that column | tests/test_tenant_schema_migrations.py | - [x] |
| 5 | tenant-schema-migrations | The `training_jobs.error_message` column is backfilled onto the template and every existing tenant schema | A schema that already has the column is unaffected | Given a tenant schema (or `tenant_template`) whose `training_jobs` table already has `error_message`, when the remediation migration is applied, then it completes without error and the schema/data are unchanged | tests/test_tenant_schema_migrations.py | - [x] |
| 6 | training-worker | Load annotated dataset | Dataset loads successfully | Given a tenant with annotated documents and a running annotation service, when the worker calls the annotation export endpoint, then it receives JSONL with `tokens`/`tags` and constructs a `datasets.Dataset` | tests/test_training_worker.py | - [ ] |
| 7 | training-worker | Load annotated dataset | Export returns no data | Given a tenant with no annotated documents, when the worker calls the annotation export endpoint, then the job is failed with a clear error message | tests/test_training_worker.py | - [ ] |
| 8 | training-worker | Load annotated dataset | Annotation service URL defaults to the correct internal port | Given `ANNOTATION_SERVICE_URL` is unset, when the worker calls the annotation export endpoint, then the request is sent to `http://annotation_service:8000/api/v1/annotation-export` | tests/test_training_worker.py | - [x] |
| 9 | training-worker | Load annotated dataset | Annotation service URL is overridable via environment variable | Given `ANNOTATION_SERVICE_URL=http://custom-host:9999`, when the worker calls the annotation export endpoint, then the request is sent to `http://custom-host:9999/api/v1/annotation-export` | tests/test_training_worker.py | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row above. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | DDL idempotency in the new helper | An implementation might write `apply_to_all_tenant_schemas` DDL templates without `IF NOT EXISTS`/`ADD COLUMN IF NOT EXISTS`, making a second run (or a run against a tenant that already has the change) fail instead of no-op, contradicting scenario 3 and the Migration Plan's "safe to retry" claim | Inspect every DDL string passed through the helper (in the remediation migration and any future migration using it) — confirm every `CREATE TABLE`/`CREATE INDEX` uses `IF NOT EXISTS` and every `ALTER TABLE ... ADD COLUMN` uses `IF NOT EXISTS` |
| 2 | Active-only vs. all-tenants scoping | An implementation might copy the `WHERE status = 'active'` filter from `dashboard.py`'s reporting loop (an existing, superficially similar pattern) instead of querying all tenants regardless of status, silently breaking scenario 2 (inactive tenants must still be updated) | Read the actual SQL in the new helper — confirm it queries `SELECT id FROM public.tenants` with no `status` filter, not a copy of the active-tenant reporting pattern |
| 3 | Remediation migration revision chaining | An implementation might pick a `down_revision` that doesn't match the actual current head, or reuse an existing revision id, breaking `alembic upgrade head` for anyone with a different migration history | Run `alembic heads` and `alembic history` before and after adding the new migration file — confirm exactly one head and a correct linear `down_revision` chain |
| 4 | Partial fix of the annotation service URL | An implementation might fix only the default in `worker.py` (satisfying scenario 8 in isolation) but skip adding the explicit `ANNOTATION_SERVICE_URL` env var to `docker-compose.yml` for `training_service`/`celery_worker`, leaving Decision 3 half-done and the dependency invisible in the compose file the way every other inter-service URL is documented | Diff `docker-compose.yml` — confirm `ANNOTATION_SERVICE_URL` (or equivalent) is explicitly set under both `training_service` and `celery_worker` environment blocks, not just left to the code default |
| 5 | seed.py reconciliation regresses to hand-maintained DDL | An implementation might "fix" `seed.py` by patching its inline `CREATE TABLE` column list to match today's shape (fixing the symptom) instead of switching it to clone from `tenant_template` via `LIKE ... INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES` (fixing the pattern), leaving the same two-source-of-truth problem that caused this incident | Read the modified `seed.py` — confirm the demo tenant's tenant-scoped tables are created via `LIKE tenant_template.<table>`, not a second hand-written column list |
| 6 | Destructive downgrade() | An implementation might write the remediation migration's `downgrade()` to `DROP COLUMN`/`DROP TABLE` the backfilled columns, which would destroy any real data written to those columns after the migration ran, contradicting design.md's explicit "downgrade is a no-op" decision | Read the remediation migration's `downgrade()` function — confirm it does not drop any column or table that could contain post-migration data (a no-op or a comment-only downgrade is expected) |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant isolation via per-tenant Postgres schemas; Compliance section explicitly states migration scripts MUST be applied to the `public` schema and each tenant schema | The new migration-propagation helper and remediation migration must apply DDL to `tenant_template` and every existing tenant schema, explicitly scoped per schema (no implicit cross-schema queries) | Review the helper's implementation — confirm it loops and issues one schema-qualified DDL statement per tenant (matching the existing per-schema-loop pattern already used in `dashboard.py`/`training_jobs.py`), never a single statement spanning multiple schemas |
| ADR-006 | Training runs asynchronously via Celery GPU workers; dependent-service URLs are environment-variable-configured | The `ANNOTATION_SERVICE_URL` fix must remain environment-variable-driven and must not alter the async Celery execution model | Confirm the worker still resolves the URL via `os.getenv("ANNOTATION_SERVICE_URL", ...)` (not a hardcoded value) and that no change was made to how `fine_tune_model` is dispatched via Celery |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (new column propagates to existing tenant schema): test output showing a migration adds a column to both `tenant_template` and a pre-existing tenant fixture's schema
- [ ] Scenario 2 (inactive tenant schema still updated): test output showing an inactive-status tenant's schema receives the same DDL as an active one
- [ ] Scenario 3 (re-running DDL is a no-op): test output showing the helper's DDL executed twice against the same schema without error
- [ ] Scenario 4 (backfill adds missing columns): test output or `\d` schema dump showing the previously-drifted tenant schema now has all `training_jobs` columns, with existing rows intact
- [ ] Scenario 5 (already-matching tenant unaffected): test output showing the remediation migration is a no-op against an up-to-date tenant schema
- [ ] Scenario 6 (dataset loads successfully): existing/updated worker test output for the happy-path annotation export flow
- [ ] Scenario 7 (export returns no data): existing/updated worker test output for the empty-dataset failure path
- [ ] Scenario 8 (correct default port): test output or log/trace showing a request to `http://annotation_service:8000/...` with `ANNOTATION_SERVICE_URL` unset
- [ ] Scenario 9 (env var override): test output showing a request to the overridden URL when `ANNOTATION_SERVICE_URL` is set

### Structural Evidence

- [ ] Code review completed — implementation matches design.md Decisions 1–4 (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — every DDL string in the helper/migration uses `IF NOT EXISTS` styling
- [ ] Risk 2 mitigation confirmed — helper's tenant query has no `status` filter
- [ ] Risk 3 mitigation confirmed — `alembic heads`/`alembic history` show a single clean chain after the new migration is added
- [ ] Risk 4 mitigation confirmed — `docker-compose.yml` explicitly sets the annotation service URL for both `training_service` and `celery_worker`
- [ ] Risk 5 mitigation confirmed — `seed.py` clones tenant-scoped tables from `tenant_template` instead of hand-writing column lists
- [ ] Risk 6 mitigation confirmed — remediation migration's `downgrade()` is non-destructive

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-tenant-schema-drift-and-training-worker-config
**Proposal:** `openspec/changes/fix-tenant-schema-drift-and-training-worker-config/proposal.md`
**Spec files reviewed:**
  - specs/tenant-schema-migrations/spec.md
  - specs/training-worker/spec.md

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
