# Verification Plan

**Change:** fix-entity-types-api-alignment
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-types-backend | Entity Types API Tenant-Scoped Routes | List entity types returns 200 for authenticated tenant admin | Given an authenticated tenant admin for `acme-corp`, when `GET /api/v1/tenants/acme-corp/entity-types` is called, then status 200 and `{"entity_types": [...]}` is returned | Integration test or API trace | - [ ] |
| 2 | entity-types-backend | Entity Types API Tenant-Scoped Routes | Old URL returns 404 | Given any authenticated user, when `GET /api/v1/entity-types` is called, then status 404 is returned | API trace / curl | - [ ] |
| 3 | entity-types-backend | Entity Type Routes Use Name Identifier | GET by name returns correct entity | Given entity `vendor_name` exists for `acme-corp`, when `GET /api/v1/tenants/acme-corp/entity-types/vendor_name` is called, then status 200 and entity with `"name": "vendor_name"` is returned | Integration test or API trace | - [ ] |
| 4 | entity-types-backend | Entity Type Routes Use Name Identifier | GET by name returns 404 when not found | Given no entity named `nonexistent` exists for `acme-corp`, when `GET /api/v1/tenants/acme-corp/entity-types/nonexistent` is called, then status 404 is returned | Integration test or API trace | - [ ] |
| 5 | entity-types-backend | Entity Type Routes Use Name Identifier | PUT by name updates and returns updated entity | Given entity `vendor_name` at version 1 exists, when `PUT /api/v1/tenants/acme-corp/entity-types/vendor_name` with updated description is sent, then status 200 and entity with `"version": 2` and updated description is returned | Integration test or API trace | - [ ] |
| 6 | entity-types-backend | PATCH Endpoint for Toggling Active Status | Deactivate sets is_active to false | Given `ship_to_location` with `is_active = true`, when `PATCH .../ship_to_location` with `{"is_active": false}` is sent, then status 200 and `"is_active": false` in response | Integration test or API trace | - [ ] |
| 7 | entity-types-backend | PATCH Endpoint for Toggling Active Status | Reactivate sets is_active to true | Given `ship_to_location` with `is_active = false`, when `PATCH .../ship_to_location` with `{"is_active": true}` is sent, then status 200 and `"is_active": true` in response | Integration test or API trace | - [ ] |
| 8 | entity-types-backend | PATCH Endpoint for Toggling Active Status | PATCH on nonexistent name returns 404 | Given no entity named `ghost` exists, when `PATCH .../ghost` is sent, then status 404 is returned | Integration test or API trace | - [ ] |
| 9 | entity-types-backend | Entity Type Read Responses Deserialize JSON Columns | List response has parsed examples array | Given an entity created with `examples = ["Acme Supplies", "Global Tech Ltd"]`, when list endpoint is called, then `examples` in response is a JSON array, not a string | API response inspection | - [ ] |
| 10 | entity-types-backend | Entity Type Read Responses Deserialize JSON Columns | List response has parsed base_label_mapping object | Given an entity created with `base_label_mapping = {"ORG": []}`, when list endpoint is called, then `base_label_mapping` in response is a JSON object, not a string | API response inspection | - [ ] |
| 11 | entity-types-backend | Create and Update Endpoints Return Flat Entity Object | POST returns flat entity on success | Given a valid create payload, when `POST /api/v1/tenants/acme-corp/entity-types` is sent, then response body is a flat JSON object with `id`, `name`, etc. at the top level (no `entity_type` wrapper key) | API response inspection | - [ ] |
| 12 | entity-types-backend | Create and Update Endpoints Return Flat Entity Object | PUT returns flat entity on success | Given an existing `vendor_name`, when `PUT .../vendor_name` with valid payload is sent, then response body is a flat JSON object with updated fields at the top level | API response inspection | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Route prefix wiring | Agent may register router at correct prefix but forget to remove the old `/api/v1/entity-types` prefix, leaving both active and masking the 404 test | Confirm `grep -r "api/v1/entity-types" src/gateway` returns only the new tenant-scoped prefix |
| 2 | Identifier change (id → name) | Agent may change the path param name but still query the DB by `id = :name`, silently returning no results | Inspect the SQL in `_get_by_name` to confirm the WHERE clause uses `name = :name`, not `id = :name` |
| 3 | PATCH endpoint scope | Agent may implement PATCH to accept arbitrary fields (not just `is_active`), unintentionally allowing partial updates beyond spec | Confirm PATCH handler extracts only `is_active` from the payload and calls a purpose-built `toggle_entity_type` method |
| 4 | JSON deserialization guard | Agent may call `json.loads()` unconditionally, crashing when a value is already parsed (e.g., from a future ORM change) or is `None` | Check `_row_to_dict` for `None` guard and isinstance-string guard before calling `json.loads` |
| 5 | Response shape for create/update | Agent may strip the `{"entity_type": ...}` wrapper from `_get_by_id` globally, breaking any other callers of that internal method | Confirm `_get_by_id` (if kept) still returns the wrapped shape for internal use, and only the service's public `create_entity_type` / `update_entity_type` methods return the flat dict |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation — all queries must filter by `tenant_id` | Every DB query in `entity_service.py` must include `tenant_id = :tid` in WHERE clause | `grep -n "tenant_id" src/gateway/services/entity_service.py` — confirm every SELECT/UPDATE has the filter |
| ADR-004 | All changes must trace to an OpenSpec spec artifact | This change has a spec artifact at `specs/entity-types-backend/spec.md` | Confirm change is applied via `/opsx:apply` referencing this change |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: API trace or test showing `GET /api/v1/tenants/acme-corp/entity-types` returns 200 with `entity_types` array
- [ ] Scenario 2: API trace showing `GET /api/v1/entity-types` returns 404
- [ ] Scenario 3: API trace or test showing `GET .../entity-types/vendor_name` returns entity with correct name
- [ ] Scenario 4: API trace showing `GET .../entity-types/nonexistent` returns 404
- [ ] Scenario 5: API trace or test showing PUT increments version to 2
- [ ] Scenario 6: API trace showing PATCH deactivates entity (is_active: false)
- [ ] Scenario 7: API trace showing PATCH reactivates entity (is_active: true)
- [ ] Scenario 8: API trace showing PATCH on unknown name returns 404
- [ ] Scenario 9: API response shows `examples` is a parsed array, not a string
- [ ] Scenario 10: API response shows `base_label_mapping` is a parsed object, not a string
- [ ] Scenario 11: API response from POST has no `entity_type` wrapper key
- [ ] Scenario 12: API response from PUT has no `entity_type` wrapper key
- [ ] UI smoke test: navigate to `/entity-types` in the frontend — previously-created entity now appears in the card grid

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1: grep confirms no old `/api/v1/entity-types` prefix exists in gateway code
- [ ] Risk 2: `_get_by_name` SQL confirmed to use `WHERE name = :name AND tenant_id = :tid`
- [ ] Risk 3: PATCH handler confirmed to extract only `is_active` field from payload
- [ ] Risk 4: `_row_to_dict` confirmed to have None + isinstance guards before json.loads
- [ ] Risk 5: `_get_by_id` internal behaviour (if retained) confirmed unchanged for any other callers

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Structural | `grep -rn "api/v1/entity-types" src/gateway/` returns no results — old flat prefix removed | Scenario 2 (old URL 404) | agent | 2026-06-25 |
| 2 | Structural | All queries in `entity_service.py` include `tenant_id = :tid` in WHERE — ADR-001 compliant | All scenarios | agent | 2026-06-25 |
| 3 | Structural | `_get_by_name` uses `WHERE name = :name AND tenant_id = :tid` — name-based lookup confirmed | Scenarios 3–12 | agent | 2026-06-25 |
| 4 | Structural | PATCH handler passes only `payload["is_active"]` to `toggle_entity_type` — scope confirmed | Scenarios 6–8 | agent | 2026-06-25 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.**

**Change slug:** fix-entity-types-api-alignment
**Proposal:** `openspec/changes/fix-entity-types-api-alignment/proposal.md`
**Spec files reviewed:**
- specs/entity-types-backend/spec.md

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
