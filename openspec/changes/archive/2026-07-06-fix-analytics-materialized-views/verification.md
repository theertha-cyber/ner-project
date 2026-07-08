# Verification Plan

**Change:** fix-analytics-materialized-views
**Generated:** 2026-07-06
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | analytics-materialized-views | Create Materialized Views for New Tenants | Seed script creates MVs for demo tenant | Given seed script runs with no tenant_demo_tenant schema, when it finishes, then mv_entity_coverage exists in the schema and is populated | - [ ] |
| 2 | analytics-materialized-views | Create Materialized Views for New Tenants | Seed script is idempotent for MVs | Given seed script runs and MVs already exist, when it runs again, then no error occurs | - [ ] |
| 3 | analytics-materialized-views | Backfill Missing MVs for Existing Tenants | Migration backfills a tenant missing MVs | Given a tenant_* schema with tables but no MVs, when migration 015 is applied, then all four MVs exist with unique indexes | - [ ] |
| 4 | analytics-materialized-views | Backfill Missing MVs for Existing Tenants | Migration skips tenants that already have MVs | Given a tenant_* schema with all four MVs, when migration 015 is applied, then no error and existing data preserved | - [ ] |
| 5 | analytics-materialized-views | Refresh MVs After Creation | MVs reflect existing data after creation | Given a tenant with 75 entities across 5 docs and 4 extraction runs, when MVs are created and refreshed, then all four return non-empty data | - [ ] |
| 6 | analytics-materialized-views | Refresh MVs After Creation | Analytics dashboard shows populated widgets after backfill | Given a tenant with extracted entities but no MVs, when migration 015 completes, then GET /api/v1/analytics/dashboard returns non-empty widget arrays | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | MV SQL definitions drift | AI may copy MV definitions incorrectly from migration 011, introducing subtle differences in column names, types, or join logic | Compare the CREATE MATERIALIZED VIEW statements in migration 015 and seed.py against migration 011 verbatim — every column, join, and WHERE clause must match |
| 2 | Concurrent refresh without unique index | AI may add REFRESH MATERIALIZED VIEW CONCURRENTLY before the unique index is created, which causes a PostgreSQL error | Verify the unique index CREATE statement precedes the REFRESH call in both migration and seed |
| 3 | Missing schema-qualified names | AI may reference tables without schema qualification inside the PL/pgSQL block, causing "relation not found" errors | Every table reference in the dynamic SQL inside migration 015 must use %I.schema_name pattern — grep for bare table names |
| 4 | Seed script not updated | AI may create the migration but forget to update seed.py, leaving the demo tenant broken in dev | Confirm seed.py contains the same MV creation logic before marking task complete |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation via separate PostgreSQL schemas with search_path enforcement | Materialized views must be created per tenant schema, not in a shared schema. The tenant_<id> naming convention must be preserved. | Confirm migration 015 uses FOR loop over pg_namespace WHERE nspname LIKE 'tenant\_%' and creates MVs in each schema individually |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Seed output showing mv_entity_coverage created in tenant_demo_tenant schema
- [ ] Scenario 2: Seed re-run exits 0 with no MV-related errors
- [ ] Scenario 3: Migration output showing MVs created in tenant_demo_tenant schema
- [ ] Scenario 4: Migration re-run exits 0 with no MV-related errors
- [ ] Scenario 5: SELECT * FROM mv_entity_coverage returns rows with real data
- [ ] Scenario 6: curl GET /api/v1/analytics/dashboard returns non-empty widget arrays

### Structural Evidence

- [ ] Code review completed — migration and seed changes match design.md decisions
- [ ] ADR-001 compliance confirmed — MVs created per-tenant-schema, not shared
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code

### Edge Case Evidence

- [ ] Risk 1: MV SQL definitions match migration 011 verbatim
- [ ] Risk 2: Unique index created before REFRESH MATERIALIZED VIEW CONCURRENTLY
- [ ] Risk 3: All table references in dynamic SQL use %I schema qualification
- [ ] Risk 4: seed.py updated with MV creation logic

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

**Change slug:** fix-analytics-materialized-views
**Proposal:** openspec/changes/fix-analytics-materialized-views/proposal.md
**Spec files reviewed:**
  - specs/analytics-materialized-views/spec.md

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

<!-- Any observations, caveats, or follow-up items for future changes. -->
