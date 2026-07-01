# Verification Plan

**Change:** annotation-file-upload
**Generated:** 2026-06-30
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-import | Accept JSONL annotation file uploads | Upload valid JSONL file | Given a tenant with entity types PER, ORG, LOC configured, when a Tenant Admin uploads a valid JSONL file with 2 lines, then the response has status 201 and `imported_count: 2` | Task 4.4 — integration test | - [ ] |
| 2 | annotation-import | Accept JSONL annotation file uploads | Upload JSONL with invalid entity type | Given a tenant with entity types PER, ORG configured, when a Tenant Admin uploads a JSONL file containing tag "B-PRODUCT", then the response has status 422 and the error lists PRODUCT as unrecognized | Task 4.3 — unit test | - [ ] |
| 3 | annotation-import | Accept JSONL annotation file uploads | Upload JSONL with malformed JSON | Given a tenant with any entity types, when a Tenant Admin uploads a file with invalid JSON, then the response has status 422 and the error indicates the parse failure and line number | Task 4.1 — unit test | - [ ] |
| 4 | annotation-import | Accept JSONL annotation file uploads | Upload empty file | Given a tenant with any entity types, when a Tenant Admin uploads an empty file, then the response has status 422 and the error indicates the file contains no valid annotation rows | Task 4.1 — unit test | - [ ] |
| 5 | annotation-import | Accept CoNLL TXT annotation file uploads | Upload valid CoNLL file | Given a tenant with entity types PER, ORG, LOC configured, when a Tenant Admin uploads a valid CoNLL TXT file, then the response has status 201 and `imported_count: 2` | Task 4.8 — integration test | - [ ] |
| 6 | annotation-import | Store imported annotations in tenant-isolated table | Table exists in tenant schema | Given a tenant schema `tenant_{tid}`, when inspecting the schema, then the `imported_annotations` table exists with columns `id`, `tokens`, `tags`, `source_file`, `row_index`, `created_at` | Task 1.2 — migration verification | - [ ] |
| 7 | annotation-import | Export endpoint includes imported annotations | Export includes both sources | Given a tenant with 1 annotated document and 2 imported annotation rows, when GET `/api/v1/annotation-export`, then the response contains 3 JSONL lines and the last 2 match the imported rows | Task 4.5 — integration test | - [ ] |
| 8 | annotation-import | Export endpoint includes imported annotations | Export with entity type filter applies to both sources | Given a tenant with imported rows containing PER, ORG, and LOC tags, when GET `/api/v1/annotation-export?entity_types=PER`, then rows with non-PER tags have those tags replaced with O | Task 4.6 — integration test | - [ ] |
| 9 | annotation-import | Export endpoint includes imported annotations | Export with no document annotations and no imported annotations | Given a tenant with zero spans and zero imported_annotations rows, when GET `/api/v1/annotation-export`, then the response has status 200 and body is empty string | Task 4.5 — integration test edge case | - [ ] |
| 10 | annotation-import | Validate file size and content type | Upload exceeds size limit | Given a file larger than 50MB, when a Tenant Admin uploads it to `POST /api/v1/annotation-import`, then the response has status 413 and the error indicates the file exceeds maximum size | Task 4.7 — integration test | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Entity type validation | AI may validate entity types case-sensitively against the DB values, but the spec doesn't specify case handling. May introduce case folding without specification, or may reject valid entity types due to case mismatch | Verify entity type comparison is consistent with how the spans endpoint validates entity types (`validate_entity_type` in spans.py) — either both are case-sensitive or both are case-insensitive |
| 2 | Token/tag array length mismatch | AI may not validate that `tokens` and `tags` arrays have equal length in each JSONL line, silently producing misaligned training data | Check that the import parser validates `len(tokens) == len(tags)` for every row and rejects mismatched rows with a 422 |
| 3 | CoNLL parser edge cases | AI may not handle trailing blank lines, mixed tabs/spaces, or Unicode whitespace in CoNLL files, causing silent data loss or parse errors | Test CoNLL parsing with trailing newline, tab-separated vs space-separated tokens, and non-ASCII characters |
| 4 | Export merge ordering | AI may interleave imported rows with document rows rather than appending them, changing the export contract for consumers that rely on document-based ordering | Verify that imported rows are appended after all document-derived rows in the export output |
| 5 | Entity type filter on imported rows | AI may skip entity type filtering on imported rows entirely (since they store tokens/tags directly rather than char spans), or may filter incorrectly by modifying the in-memory tags array while leaving the DB row untouched | Verify that the export endpoint's `entity_types` query param replaces non-matching tags with O in imported rows' output, and that the DB rows are not mutated |
| 6 | MIME type validation | AI may reject `application/octet-stream` or `text/plain` uploads that are actually valid JSONL/CoNLL files, or may accept arbitrary binary data | Verify the MIME type whitelist matches spec and that format detection (parsing) is the real gate, not MIME type |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Separate PostgreSQL schemas per tenant | `imported_annotations` table MUST be created in tenant schema, not public schema | Check the Alembic migration creates the table in the template schema that gets cloned per tenant |
| ADR-004 | OpenSpec spec-driven governance | Implementation must follow tasks.md; no code before spec | Verify all implementation is gated behind the approved tasks |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing `POST /api/v1/annotation-import` with valid JSONL returns 201 and `imported_count: 2`
- [ ] Scenario 2: Test output showing upload with unknown entity tag returns 422 with error listing PRODUCT
- [ ] Scenario 3: Test output showing malformed JSON upload returns 422 with parse error and line number
- [ ] Scenario 4: Test output showing empty file upload returns 422 with appropriate error
- [ ] Scenario 5: Test output showing valid CoNLL upload returns 201 and `imported_count: 2`
- [ ] Scenario 6: Migration test or schema inspection confirming `imported_annotations` table with all columns
- [ ] Scenario 7: Test output showing export returns 3 lines when 1 document + 2 imported rows exist
- [ ] Scenario 8: Test output showing `entity_types=PER` filter replaces non-PER tags with O in imported rows
- [ ] Scenario 9: Test output showing export returns empty string when no annotations exist
- [ ] Scenario 10: Test output showing 50MB+ file upload returns 413

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 — Entity type validation consistency: verify the import endpoint uses the same validation logic as `validate_entity_type` in spans.py
- [ ] Risk 2 — Token/tag array length mismatch: verify `len(tokens) == len(tags)` validation rejects mismatched rows
- [ ] Risk 3 — CoNLL parser edge cases: verify parsing handles trailing newlines, tabs vs spaces, and non-ASCII
- [ ] Risk 4 — Export merge ordering: verify imported rows appear after document-derived rows in output
- [ ] Risk 5 — Entity type filter on imported rows: verify filter applies to imported rows without mutating DB
- [ ] Risk 6 — MIME type validation: verify format detection via parsing, not MIME type alone

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** annotation-file-upload
**Proposal:** `openspec/changes/annotation-file-upload/proposal.md`
**Spec files reviewed:**
- specs/annotation-import/spec.md

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
