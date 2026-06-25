# Verification Plan

**Change:** sp-09-entity-types
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-types-screen | Entity Types List Page | Page renders header and card grid for tenant admin | Given an authenticated tenant_admin, when they navigate to `/entity-types`, then the "Entity Types" h1, `/api/v1/entity-types` moniker, active-count summary, and "+ Define entity type" button are all visible | | - [ ] |
| 2 | entity-types-screen | Entity Types List Page | Card grid shows skeleton while fetching | Given the API call is pending, when the page first mounts, then 6 skeleton placeholder cards are visible | | - [ ] |
| 3 | entity-types-screen | Entity Types List Page | Empty state when no entity types exist | Given the API returns an empty array, when the page renders, then an empty-state message appears and the "+ Define entity type" button is still visible | | - [ ] |
| 4 | entity-types-screen | Entity Type Card | Card displays all fields for an active required entity type | Given entity type "vendor_name" (version 2, mapping ORG, required, active) at index 0, when the card renders, then name "vendor_name", "v2", "Required", "Active", "ORG → vendor_name", example text, and orange-hued dot are all visible | | - [ ] |
| 5 | entity-types-screen | Entity Type Card | Card shows Deactivate button for active entity type | Given active entity type, when card renders, then toggle button label is "Deactivate" | | - [ ] |
| 6 | entity-types-screen | Entity Type Card | Card shows Reactivate button for inactive entity type | Given inactive entity type, when card renders, then toggle button label is "Reactivate" and "Inactive" pill is visible | | - [ ] |
| 7 | entity-types-screen | Entity Type Card | Card hover lift | Given the card is rendered, when the user hovers, then `transform: translateY(-2px)` and `border-color: var(--primary-line)` are applied | | - [ ] |
| 8 | entity-types-screen | Define / Edit Entity Type Slide-Over | Slide-over opens in create mode from header button | Given the page is rendered, when the user clicks "+ Define entity type", then the slide-over opens with title "Create entity type" and all fields empty with the NAME field editable | | - [ ] |
| 9 | entity-types-screen | Define / Edit Entity Type Slide-Over | Slide-over opens in edit mode from card | Given entity type "vendor_name" exists, when the user clicks "Edit", then the slide-over title is "Edit entity type", NAME shows "vendor_name" (disabled), description is pre-filled, ORG chip is selected, and Required toggle is on | | - [ ] |
| 10 | entity-types-screen | Define / Edit Entity Type Slide-Over | BASE MODEL LABEL chip selection is single-select | Given the slide-over is open, when the user clicks "LOC", then LOC chip is active and any previously selected chip becomes unselected | | - [ ] |
| 11 | entity-types-screen | Define / Edit Entity Type Slide-Over | Create submits POST and shows success toast | Given valid fields in create mode, when the user clicks "Create entity type", then a POST is sent to `/api/v1/tenants/acme-corp/entity-types`, a success toast appears, and the slide-over closes | | - [ ] |
| 12 | entity-types-screen | Define / Edit Entity Type Slide-Over | Edit submits PUT and increments version | Given edit mode for "customer_name" at v1, when the user updates description and saves, then a PUT is sent and the card shows v2 | | - [ ] |
| 13 | entity-types-screen | Define / Edit Entity Type Slide-Over | Escape key closes the slide-over | Given the slide-over is open, when the user presses Escape, then the slide-over closes without saving | | - [ ] |
| 14 | entity-types-screen | Define / Edit Entity Type Slide-Over | API error shows error toast | Given the API returns 422 or 500, when the user submits, then an error toast is shown and the slide-over remains open | | - [ ] |
| 15 | entity-types-screen | Activate / Deactivate Entity Type | Deactivate changes card to inactive state | Given active "ship_to_location", when user clicks "Deactivate", then PATCH is sent with `{"is_active": false}`, card shows "Inactive" pill, button changes to "Reactivate", and active-count decrements | | - [ ] |
| 16 | entity-types-screen | Activate / Deactivate Entity Type | Reactivate restores active state | Given inactive entity type, when user clicks "Reactivate", then PATCH is sent with `{"is_active": true}`, card shows "Active" pill, button changes to "Deactivate" | | - [ ] |
| 17 | entity-types-screen | Activate / Deactivate Entity Type | Toggle error shows toast and refetches | Given PATCH fails with 500, when toggle completes, then an error toast appears and the list refetches | | - [ ] |
| 18 | entity-types-screen | Entity Types API Hooks | useEntityTypes fetches tenant-scoped list | Given user authenticated as "acme-corp", when `useEntityTypes()` is called, then it fetches `GET /api/v1/tenants/acme-corp/entity-types` with query key `["entity-types", "acme-corp"]` | | - [ ] |
| 19 | entity-types-screen | Entity Types API Hooks | useCreateEntityType invalidates list on success | Given the mutation is called with valid data, when POST returns 201, then `["entity-types", tenantSlug]` query is invalidated and the list re-fetches | | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Tenant-scoped API URL | AI may call `/api/v1/entity-types` (unscoped) instead of `/api/v1/tenants/{slug}/entity-types` | Grep hooks for `authFetch` call — confirm URL includes `tenantSlug` from `useAuth()` |
| 2 | Hue/color derivation | AI may attempt to store or fetch `hue` from the server instead of computing it client-side from `index % 7` | Check `EntityTypeCard` — hue must be computed from the array index, not from any API field |
| 3 | BASE MODEL LABEL chips | AI may allow multi-select or support labels beyond PER/ORG/LOC/MISC | Check `DefineEntityTypeSlideOver` — exactly four chips, single-select enforced |
| 4 | NAME field in edit mode | AI may leave the NAME field editable during edit, allowing the user to rename an entity type (API does not support this) | Check that the NAME input has `disabled` attribute when `slideOverMode === "edit"` |
| 5 | Mutation body mapping | AI may send `description` as `desc` or `required` as `required_flag`, mismatching the backend field names from `entity-config` spec | Compare mutation payload keys against `entity-config` spec (§Requirement: Entity Type Definition): `name`, `description`, `examples`, `base_label_mapping`, `required_flag`, `is_active` |
| 6 | Query invalidation scope | AI may invalidate the entire query cache rather than the specific `["entity-types", tenantSlug]` key | Inspect `useCreateEntityType`, `useUpdateEntityType`, `useToggleEntityType` — each must call `queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] })` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation | All data scoped to tenant; API endpoints include tenant slug | Entity types API calls MUST include `tenantSlug` in the URL path | Search `src/portal/src/hooks/use-entity*.ts` — every `authFetch` URL must contain the tenantSlug variable |
| ADR-002: Single Base Model (in force; partially superseded by ADR-008 for serving, not labels) | Base model uses CoNLL labels PER/ORG/LOC/MISC only | Chip row in slide-over must offer exactly PER, ORG, LOC, MISC — no custom labels | Inspect `DefineEntityTypeSlideOver` chip list — must be a hard-coded array `["PER", "ORG", "LOC", "MISC"]`, not dynamic |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Screenshot or test showing "Entity Types" heading, path moniker, active-count, and "+ Define entity type" button visible for a tenant_admin user
- [ ] Scenario 2: Screenshot showing 6 skeleton cards visible during loading state
- [ ] Scenario 3: Screenshot showing empty-state message when no entity types exist
- [ ] Scenario 4: Test or screenshot confirming all card fields (name, version, pills, BASE LABEL MAPPING, EXAMPLES, colored dot) render correctly for vendor_name at index 0
- [ ] Scenario 5: Test confirming "Deactivate" label shown for active entity type card
- [ ] Scenario 6: Test confirming "Reactivate" label and "Inactive" pill shown for inactive entity type card
- [ ] Scenario 7: Test or screenshot showing translateY(-2px) lift effect on card hover
- [ ] Scenario 8: Test confirming slide-over opens with empty fields and editable NAME in create mode
- [ ] Scenario 9: Test confirming slide-over pre-fills all fields and disables NAME in edit mode
- [ ] Scenario 10: Test confirming clicking LOC deselects the previously active chip
- [ ] Scenario 11: Test confirming POST is called and success toast appears on create
- [ ] Scenario 12: Test confirming PUT is called and version increments on edit
- [ ] Scenario 13: Test confirming Escape key closes slide-over (from existing SlideOver behavior)
- [ ] Scenario 14: Test confirming error toast shown and slide-over remains open on API error
- [ ] Scenario 15: Test confirming PATCH with `{"is_active": false}` and card state update
- [ ] Scenario 16: Test confirming PATCH with `{"is_active": true}` and card state update
- [ ] Scenario 17: Test confirming error toast and query refetch on toggle failure
- [ ] Scenario 18: Unit test for `useEntityTypes` — verify URL and query key
- [ ] Scenario 19: Unit test for `useCreateEntityType` — verify invalidation on success

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (tenant-scoped URL): Grep result confirming all `authFetch` calls in entity-types hooks include `tenantSlug`
- [ ] Risk 2 (hue derivation): Code inspection showing hue computed from array index, not fetched from API
- [ ] Risk 3 (chip multi-select): Test confirming only one BASE MODEL LABEL chip can be active at a time
- [ ] Risk 4 (NAME disabled in edit): Test confirming NAME input has `disabled` attribute when editing
- [ ] Risk 5 (mutation field names): API request body inspection confirming `description`, `required_flag`, `base_label_mapping` (not `desc`, `required`, `mapping`)
- [ ] Risk 6 (query invalidation scope): Code inspection confirming targeted `queryKey: ["entity-types", tenantSlug]` invalidation

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching entry.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** sp-09-entity-types
**Proposal:** `openspec/changes/sp-09-entity-types/proposal.md`
**Spec files reviewed:**
- specs/entity-types-screen/spec.md

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
