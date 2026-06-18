# Verification Plan

**Change:** fix-batch-extraction-worker
**Generated:** 2026-06-17
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | Batch extraction | Trigger batch extraction | Given a tenant with a promoted model and documents in `processed` status, when a POST to `/api/v1/extract-batch?documentIds=doc1`, then response is 202 with `run_id` and `status: "queued"` | — | - [ ] |
| 2 | extraction-service | Batch extraction | Batch extraction persists extracted entities with document linkage | Given a tenant with a promoted model and one processed document, when batch extraction completes, then `processed_count=1`, `failed_count=0`, rows exist in `extracted_entities` with non-null `entity_id`, `value`, `confidence`, and `document_id` matching the source document | — | - [ ] |
| 3 | extraction-service | Batch extraction | Batch extraction skips already-extracted documents | Given a document already present in `extracted_entities` for the current model version, when batch extraction is triggered for that document, then `skipped_count=1` and no new entity rows are inserted | — | - [ ] |
| 4 | extraction-service | Batch extraction | Batch extraction for tenant with no promoted model | Given a tenant with no promoted model, when POST to `/api/v1/extract-batch`, then response is 202 and run eventually reaches `status: "failed"` | — | - [ ] |
| 5 | extraction-service | Query extracted entities | Query entities by document after batch extraction | Given a document processed by batch extraction, when GET `/api/v1/entities?documentId=<id>`, then response is 200 with entities belonging to that document and pagination metadata | — | - [ ] |
| 6 | extraction-service | Query extracted entities | Query entities by type | Given extracted entities of various types, when GET `/api/v1/entities?type=ORG`, then response contains only entities with `entity_type: "ORG"` | — | - [ ] |
| 7 | extraction-service | Query extracted entities | Query entities by confidence threshold | Given entities with varying confidence, when GET `/api/v1/entities?minConfidence=0.8`, then response contains only entities with `confidence >= 0.8` | — | - [ ] |
| 8 | extraction-service | Query extracted entities | Query entities unreviewed | Given entities with different review statuses, when GET `/api/v1/entities?reviewStatus=unreviewed`, then response contains only `review_status: "unreviewed"` entities | — | - [ ] |
| 9 | extraction-service | Query extracted entities | Query entities as annotator | Given an authenticated annotator, when GET `/api/v1/entities`, then response is 200 | — | - [ ] |
| 10 | extraction-service | Query extracted entities | Query entities cross-tenant 404 | Given entities for tenant A, when tenant B requests entities for a document belonging to tenant A, then response is 404 | — | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Alembic migration scope | Agent may only update `tenant_template` and forget to loop over existing tenant schemas, leaving live tenants without the `document_id` column | Confirm migration contains the `DO $$ ... FOR EACH schema LIKE 'tenant\_%'` loop identical to migrations 003 and 007 |
| 2 | Idempotency query target | Agent may fix the column name but still query `extraction_runs` instead of `extracted_entities`, leaving idempotency broken | Read `_get_already_extracted` (or its replacement) in `worker.py` — confirm it queries `extracted_entities WHERE document_id IN (...)` not `extraction_runs` |
| 3 | `document_id` populated on INSERT | Agent may add the column to the migration but forget to include `document_id` in the worker's `INSERT INTO extracted_entities` statement | Grep `worker.py` for the INSERT — confirm `document_id` appears in the column list and in the params dict |
| 4 | `query_entities` filter path | Agent may update the migration and worker but forget to update `entity_store.py`, leaving the subquery-via-`extraction_runs` path in place | Read `entity_store.py query_entities` — confirm `document_id` condition is `e.document_id = :document_id` not the old subquery |
| 5 | span ordering | Agent may query `document_text_spans` without an ORDER BY, producing tokens in arbitrary order | Confirm SQL includes `ORDER BY span_index NULLS LAST` (or equivalent) |
| 6 | Empty span guard | Agent may pass an empty token list to inference when a document has no text spans, causing inference to error or return unexpected results | Confirm worker has an `if not tokens: failed += 1; continue` guard after the span query |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | All tenant data lives in per-tenant schemas | All SQL must use `{schema}.table` — no bare table names, no cross-tenant joins | Grep `worker.py` and new migration for any table reference not prefixed with the schema variable |
| ADR-003-model-serving-topology | Worker communicates with model serving via internal HTTP | The inference POST to `/internal/v1/infer` must remain; only the document text fetch moves to DB | Confirm `infer_url` and `infer_resp = requests.post(...)` are unchanged in the worker |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 2 (entity persistence + document linkage): Trigger batch extraction; confirm via `SELECT * FROM tenant_<id>.extracted_entities WHERE run_id = '<run_id>'` that rows exist with non-null `document_id` matching the submitted document, and that `processed_count=1`, `failed_count=0`
- [ ] Scenario 3 (idempotency): Re-run batch extraction on same document; confirm `skipped_count=1` and no new rows inserted into `extracted_entities`
- [ ] Scenario 5 (query by document): After extraction, GET `/api/v1/entities?documentId=<id>` and confirm non-empty response with matching entities
- [ ] Scenario 1 (trigger): Confirm 202 response with `run_id` and `status: "queued"`
- [ ] Scenario 4 (no model): Confirm run reaches `status: "failed"` for tenant with no promoted model
- [ ] Scenarios 6–10 (entity filters): Confirm each filter returns only matching entities (type, confidence, review status, annotator access, cross-tenant 404)

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 confirmed: Alembic migration loop over existing schemas present and correct
- [ ] Risk 2 confirmed: Idempotency check queries `extracted_entities`, not `extraction_runs`
- [ ] Risk 3 confirmed: `document_id` present in worker INSERT column list and params
- [ ] Risk 4 confirmed: `query_entities` uses direct `e.document_id = :document_id` filter
- [ ] Risk 5 confirmed: span query includes ORDER BY
- [ ] Risk 6 confirmed: empty tokens guard present

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-batch-extraction-worker
**Proposal:** `openspec/changes/fix-batch-extraction-worker/proposal.md`
**Spec files reviewed:**
- specs/extraction-service/spec.md

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
