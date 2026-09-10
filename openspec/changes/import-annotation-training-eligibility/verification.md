# Verification Plan

**Change:** import-annotation-training-eligibility
**Generated:** 2026-09-09
**Status:** 🔴 NOT VERIFIED — implementation not started.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-import-ui | Unmapped Entity Types Are Held, Not Dropped | Import surfaces unmapped types instead of skipping rows | Given tenant types `person`,`org`, when 100 rows with 12 `JOB_TITLE` are imported, then 201, all 100 stored, `unmapped_types` has `{JOB_TITLE, 12}`, no `JOB_TITLE` type created | `tests/test_annotation_import.py::test_unmapped_types_held_not_dropped` | - [ ] |
| 2 | annotation-import-ui | Unmapped Entity Types Are Held, Not Dropped | A fully-known file reports no unmapped types | Given every tag known, when imported, then `unmapped_types` empty and the `annotation_imports` row has `training_eligible_at` set | `tests/test_annotation_import.py::test_known_file_is_eligible` | - [ ] |
| 3 | annotation-import-ui | Entity Type Mapping | Map an unknown type to an existing entity type | Given unmapped `JOB_TITLE` on 12 rows and active `job_title`, when mapped, then those rows' tags reference `job_title`, header `type_map` records it, file becomes eligible | `tests/test_annotation_import.py::test_map_unknown_to_existing` | - [ ] |
| 4 | annotation-import-ui | Entity Type Mapping | Map an unknown type by creating a new entity type | Given unmapped `contract_id`, when mapped via "create new", then a `contract_id` entity type exists at v1 with import provenance and the rows reference it | `tests/test_annotation_import.py::test_map_unknown_creates_type` | - [ ] |
| 5 | annotation-import-ui | Entity Type Mapping | Mapping never creates a type implicitly | Given an unmapped type and no type-map submitted, then no entity type created and file not eligible | `tests/test_annotation_import.py::test_no_implicit_type_creation` | - [ ] |
| 6 | annotation-import-ui | Entity Type Mapping | Type mapping requires tenant_admin | Given an unmapped type, when an `annotator` calls type-map, then 403 | `tests/test_annotation_import.py::test_type_map_requires_tenant_admin` | - [ ] |
| 7 | annotation-import-ui | Imported Files Are Training Data | Eligible imported rows appear in the export | Given a training-eligible 40-row file, when export runs, then 40 rows from it with equal-length tokens/tags | `tests/test_annotation_export_offsets.py::test_export_includes_eligible_imports` | - [ ] |
| 8 | annotation-import-ui | Imported Files Are Training Data | A file pending mapping contributes nothing | Given a file with an unresolved unmapped type, when export runs, then no row from it appears | `tests/test_annotation_export_offsets.py::test_export_excludes_pending_import` | - [ ] |
| 9 | annotation-import-ui | Request Training From an Import | Request training from an eligible import | Given a training-eligible file, when a Tenant Admin clicks "Request training", then a job is created in `pending_approval` with no review step required first | `tests/test_retrain_request.py::test_request_training_from_import` | - [ ] |
| 10 | annotation-import-ui | Backend Partial Import Support (MODIFIED) | Backend response remains backward-compatible for imported_count | Given a caller reading only `imported_count`, when the modified endpoint returns the new shape, then `imported_count` is the count of immediately-usable rows | `tests/test_annotation_import.py::test_imported_count_backward_compatible` | - [ ] |
| 11 | annotation-import-ui | Backend Partial Import Support (MODIFIED) | Backend holds rows with unknown entity types | Given 3 rows, row 2 uses `FOO`, when imported, then all 3 inserted, row 2 pending, response `imported_count:2 pending_count:1 unmapped_types:[FOO]` | `tests/test_annotation_import.py::test_backend_holds_unknown_type_rows` | - [ ] |
| 12 | annotation-import-ui | Backend Partial Import Support (MODIFIED) | Backend returns entity type breakdown | Given rows with PER/ORG/DATE all known, when imported, then `entity_type_counts` per type | `tests/test_annotation_import.py::test_entity_type_counts` | - [ ] |
| 13 | annotation-import-ui | Backend Partial Import Support (MODIFIED) | Import requires tenant_admin | Given a valid file, when an `annotator` calls `annotation-import`, then 403 | `tests/test_annotation_import.py::test_import_requires_tenant_admin` | - [ ] |
| 14 | annotation-import-ui | Entity Type Mapping | Tag rewrite preserves BIO prefix and only the mapped base type | Given rows with `B-JOB_TITLE`,`I-JOB_TITLE`,`B-PERSON`, when `JOB_TITLE→job_title`, then `B-job_title`,`I-job_title`,`B-PERSON` unchanged | `tests/test_bio_tags.py::test_type_map_rewrite_preserves_bio` | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Hold vs skip (Decision 1) | Implementer keeps the old skip path and only *also* returns `unmapped_types`, so rows are still lost | Confirm every parsed row is inserted; `pending_count + imported_count` equals total parsed rows. Execute Scenarios 1, 11. |
| 2 | Implicit type creation (Decision 3) | Implementer auto-creates an entity type for an unknown tag during import "to make it eligible" | Grep the import path for any `entity_definitions` INSERT or entity-config create call. Execute Scenario 5. |
| 3 | Direct table write on "create new" (Decision 3) | The type-map endpoint inserts into `entity_definitions` directly instead of calling the entity-config create API | Trace the "create new" branch to the shared create path; confirm versioning/validation inherited. Execute Scenario 4. |
| 4 | Tag rewrite (Decision 2) | Rewrite strips or mangles the `B-`/`I-` prefix, or rewrites a substring match (`JOB_TITLE` inside `SUBJOB_TITLE`) | Read the rewrite; it must split base type from prefix and match the whole base. Execute Scenario 14. |
| 5 | Export filter (Decision 5) | Export includes rows from files without `training_eligible_at`, or from `pending_mapping` rows | Confirm the export query joins `annotation_imports` on `training_eligible_at IS NOT NULL` and filters `pending_mapping = false`. Execute Scenarios 7, 8. |
| 6 | Eligibility conflated with review (Decision 4) | Implementer requires `reviewed = true` on every row before eligibility, contradicting the brief | Confirm eligibility is `pending_count = 0` only. Execute Scenario 9 (no review step). |
| 7 | Idempotency (ADR-011) | Re-running a type-map double-rewrites already-correct tags or writes a second header | Execute a repeated type-map; confirm tags and header unchanged on the second call. |

---

## 3. Pattern & ADR Compliance

| ADR | Constraint | Verification Step |
|-----|-----------|-------------------|
| ADR-001 tenant-data-isolation | New column + header table in the tenant schema; entity types scoped by `tenant_id` | Trace `_schema(tenant_id)` use in the new endpoints and migration `043`. |
| ADR-011 annotation-idempotency-enforcement | Re-import / re-map is a no-op | Execute Risk 7 check. |
| ADR-012 annotation-fix-deployment-topology | New endpoints in `annotation_service`; training via `training_service` | Confirm no new gateway route; the "Request training" action calls `POST /api/v1/training-retrain-requests`. |

---

## 4. Evidence Requirements

### Functional Evidence
- [ ] One test-output item per row 1–14 in Section 1.

### Structural Evidence
- [ ] Code review — matches design.md; no undocumented deviation
- [ ] `git diff` shows only additive schema (`imported_annotations.pending_mapping`, header table)
- [ ] "Map to new" goes through the entity-config create API — no direct `entity_definitions` INSERT in the import/type-map path
- [ ] Export query filters on `training_eligible_at` and `pending_mapping = false`
- [ ] `notify.py` reused if any notification is emitted; no second writer

### Edge Case Evidence
- [ ] Risk 1 — every parsed row is stored
- [ ] Risk 2/3 — no implicit or direct-write type creation
- [ ] Risk 4 — BIO-safe, whole-base-type rewrite
- [ ] Risk 5 — export excludes ineligible/pending rows
- [ ] Risk 6 — eligibility is `pending_count = 0`, not review-gated
- [ ] Risk 7 — repeated type-map is a no-op

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: signed by a human reviewer before archive.**

**Change slug:** import-annotation-training-eligibility
**Spec files reviewed:** specs/annotation-import-ui/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items checked | - [ ] |
| All structural evidence items checked | - [ ] |
| All edge case evidence items checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**

- Depends on nav-restructure Phase 3 (`annotation_imports` table, migration 041) and the
  `entity-type-provenance` change (for the `provenance = 'imported'` value used when
  mapping-to-new).
- Backward-compat note: `skipped_count` drops toward zero as rows are held not skipped;
  `warnings` retained for unparseable rows only.

---

## 7. Agent Verification Record

### Backend (executed)

Implemented: migration `045` (`imported_annotations.pending_mapping` + header backfill);
`import_.py` — `require_tenant_admin`, store-all-rows / hold-unmapped, `unmapped_types` +
`pending_count` response, `annotation_imports` header upsert, `_refresh_import_header`
eligibility; new `POST /api/v1/annotation-imports/{source_file}/type-map` (map-to-existing
rewrites tags; map-to-new goes through `EntityService.create_entity_type` with
`provenance='imported'`); `export.py` — LEFT JOIN the header, include only
`pending_mapping = FALSE` rows of eligible (or headerless-legacy) files, tag lines
`"source": "import"`.

Run in the `annotation_service` container against `ner_test`:

```
tests/test_annotation_import.py                                  34 passed
  (6 new: RBAC, eligibility, type-map to-existing / create-new / RBAC, export-exclusion)
tests/test_annotation_export_offsets.py + _windowing + workspace  74 passed  (no regression)
tests/test_bio_tags.py + test_imported_annotations_list           green
```

`py_compile` clean. Migration `045` needs `alembic upgrade head` in the deployment DB.

**Pre-existing, not caused by this change:** `test_review_queue.py::TestLLMReviewRoute` (4)
and `test_imported_annotations_update.py` (2) fail when certain other test files run before
them in an ad-hoc multi-file invocation — a cross-file DB-isolation issue reproducible on
clean HEAD with `test_seed_bootstrap_proposal.py` first. Each file passes standalone
(`test_review_queue.py` 20/20, `test_annotation_import.py` 34/34).

### Portal (partial, executed)

- `use-annotation-import` `ImportResult` gains `pending_count` / `unmapped_types` / `source_file`.
- New `use-import-type-map` hook → `POST /api/v1/annotation-imports/{file}/type-map`.
- `AnnotationImportResult` renders the unmapped-type list with a per-type
  "map to existing / create new" selector and a "Map types" action.

```
src/portal use-import-type-map.test.tsx        2 passed
src/portal AnnotationImportResult.test.tsx     7 passed (mapping form + updated held-not-dropped copy)
```

### Portal completion (executed)

- `GET /api/v1/annotation-imports` (new, `require_tenant_admin`) — one row per file with
  `training_eligible`, `pending_count`, `type_map`; `use-import-files` hook.
- `/imported-documents`: an **Imported files** panel — per file, "N rows need a type
  mapping" or "Training: Eligible" + a "Request training" button (`useRequestRetrain`).
  The import button is now `tenant_admin`-only.
- `/imported-documents/[id]` route (annotator + tenant_admin) renders the exported
  `ImportedDocumentReview`.
- `/annotate/import` landing stats read `use-import-files`.

```
tests/test_annotation_import.py                     36 passed  (+2 list-endpoint tests)
src/portal use-import-files / use-import-type-map / AnnotationImportResult /
           AnnotationImportFlow                     25 passed
```

### Not yet implemented
- Migration `045` guard test.
- A dedicated `/imported-documents` "Unmapped Types" tab (the mapping form is on the
  import-result slide-over; the file panel shows the pending count).

---

## 8. Outstanding Items

- Tasks 6.1, 7.x, 2.3; §4/§5 evidence; §6 sign-off.
