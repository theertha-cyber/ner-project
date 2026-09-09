# Verification Plan

**Change:** entity-type-provenance
**Generated:** 2026-09-09
**Status:** 🔴 NOT VERIFIED — implementation not started.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-config | Entity Type Provenance | A hand-created entity type is manual | Given a Tenant Admin, when they POST a new entity type, then `provenance: "manual"` | `tests/test_entity_config.py::test_manual_create_provenance` | - [ ] |
| 2 | entity-config | Entity Type Provenance | An approved schema-proposal candidate is suggested | Given a pending candidate `contract_id`, when approved, then the created type has `provenance: "suggested"` | `tests/test_seed_bootstrap_proposal.py::test_approved_candidate_is_suggested_provenance` | - [ ] |
| 3 | entity-config | Entity Type Provenance | A type created while mapping an import is imported | Given an import with unmapped `party_name`, when mapped via "create new", then the type has `provenance: "imported"` and `provenance_ref` = source filename | `tests/test_annotation_import.py::test_map_create_new_is_imported_provenance` | - [ ] |
| 4 | entity-config | Entity Type Provenance | Provenance is immutable across updates | Given `provenance: "suggested"` at v1, when the description is updated, then version increments and `provenance` stays `"suggested"` | `tests/test_entity_config.py::test_provenance_immutable_on_update` | - [ ] |
| 5 | entity-types-backend | Entity Type Responses Include Provenance | List response includes provenance | Given types of each provenance, when listed, then each carries `provenance` + `provenance_ref` | `tests/test_entity_type_view_metadata_api.py::test_list_includes_provenance` | - [ ] |
| 6 | entity-types-backend | Entity Type Responses Include Provenance | Create response includes provenance | Given a create payload with no `provenance`, when POSTed, then flat response has `provenance: "manual"`, `provenance_ref: null` | `tests/test_entity_config.py::test_create_response_includes_provenance` | - [ ] |
| 7 | entity-types-backend | Entity Type Responses Include Provenance | A client-supplied provenance on create is ignored | Given a create payload setting `provenance: "suggested"`, when POSTed, then the created type is `manual` | `tests/test_entity_config.py::test_client_provenance_ignored` | - [ ] |
| 8 | entity-types-screen | Entity Type Card | Card displays all fields for an active required entity type | Given a `manual` type, when rendered, then all existing fields plus a chip reading "manual" are visible | `src/portal/src/components/entity-types/EntityTypeCard.test.tsx` | - [ ] |
| 9 | entity-types-screen | Entity Type Card | Card shows a suggested provenance chip with reference | Given `provenance: "suggested"`, `provenance_ref: "schema v3"`, when rendered, then a chip reads "suggested · schema v3" | `src/portal/src/components/entity-types/EntityTypeCard.test.tsx` | - [ ] |
| 10 | entity-types-screen | Entity Type Card | Card shows an imported provenance chip | Given `provenance: "imported"`, `provenance_ref: "hr_gold_set.jsonl"`, when rendered, then a chip reads "imported · hr_gold_set.jsonl" | `src/portal/src/components/entity-types/EntityTypeCard.test.tsx` | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Column default (Decision 1) | Implementer uses a Python-side `default` only; `entity_service.create`'s explicit column-list insert then omits it and violates NOT NULL | Confirm the migration sets `server_default 'manual'`. Run `test_manual_create_provenance` against a migration-built schema. |
| 2 | Body-controlled provenance (Decision 2) | The `POST` endpoint reads `provenance` from the request body | Read the create endpoint / schema; there must be no `provenance` request field. Execute Scenario 7. |
| 3 | Provenance mutation (Decision 3) | An `update` code path carries `provenance` through and overwrites it | Grep `entity_service.update` and the PUT handler for `provenance`. Execute Scenario 4. |
| 4 | Writer boundary | The schema-proposal or import path writes `entity_definitions.provenance` directly instead of passing it to `entity_service.create` | Trace both paths to the shared create function. |

---

## 3. Pattern & ADR Compliance

| ADR | Constraint | Verification Step |
|-----|-----------|-------------------|
| ADR-001 tenant-data-isolation | `provenance` on the existing tenant-scoped table; scoping unchanged | Read the migration and the list query's `WHERE tenant_id`. |
| entity-config single-writer | Only `entity_service` writes `entity_definitions` | Grep the schema-proposal and import type-map paths for direct INSERT/UPDATE of `entity_definitions`. |

---

## 4. Evidence Requirements

### Functional Evidence
- [ ] One test-output item per row 1–10.

### Structural Evidence
- [ ] Migration `044` sets `server_default 'manual'`; additive only
- [ ] `POST` create endpoint has no `provenance` request field
- [ ] `entity_service.update` does not touch `provenance` / `provenance_ref`
- [ ] Schema-proposal and import type-map paths call `entity_service.create` with provenance, never write the column

### Edge Case Evidence
- [ ] Risk 1 — create works against a migration-built schema
- [ ] Risk 2 — client-supplied provenance ignored
- [ ] Risk 3 — update leaves provenance unchanged
- [ ] Risk 4 — no direct column writes outside `entity_service`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: signed by a human reviewer before archive.**

**Change slug:** entity-type-provenance
**Spec files reviewed:** specs/entity-config/spec.md, specs/entity-types-backend/spec.md, specs/entity-types-screen/spec.md

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

- `import-annotation-training-eligibility` depends on this change for the `'imported'`
  provenance value; land this first or together.

---

## 7. Agent Verification Record

*(To be written by the implementing agent after `/opsx:apply`.)*

---

## 8. Outstanding Items

- Implementation not started.
