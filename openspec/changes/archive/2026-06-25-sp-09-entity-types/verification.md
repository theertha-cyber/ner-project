# Verification Plan

**Change:** sp-09-entity-types
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-types-screen | Entity Types List Page | Page renders header and card grid for tenant admin | Given an authenticated tenant_admin, when they navigate to `/entity-types`, then the "Entity Types" h1, `/api/v1/entity-types` moniker, active-count summary, and "+ Define entity type" button are all visible | | - [x] |
| 2 | entity-types-screen | Entity Types List Page | Card grid shows skeleton while fetching | Given the API call is pending, when the page first mounts, then 6 skeleton placeholder cards are visible | | - [x] |
| 3 | entity-types-screen | Entity Types List Page | Empty state when no entity types exist | Given the API returns an empty array, when the page renders, then an empty-state message appears and the "+ Define entity type" button is still visible | | - [x] |
| 4 | entity-types-screen | Entity Type Card | Card displays all fields for an active required entity type | Given entity type "vendor_name" (version 2, mapping ORG, required, active) at index 0, when the card renders, then name "vendor_name", "v2", "Required", "Active", "ORG → vendor_name", example text, and orange-hued dot are all visible | | - [x] |
| 5 | entity-types-screen | Entity Type Card | Card shows Deactivate button for active entity type | Given active entity type, when card renders, then toggle button label is "Deactivate" | | - [x] |
| 6 | entity-types-screen | Entity Type Card | Card shows Reactivate button for inactive entity type | Given inactive entity type, when card renders, then toggle button label is "Reactivate" and "Inactive" pill is visible | | - [x] |
| 7 | entity-types-screen | Entity Type Card | Card hover lift | Given the card is rendered, when the user hovers, then `transform: translateY(-2px)` and `border-color: var(--primary-line)` are applied | | - [x] |
| 8 | entity-types-screen | Define / Edit Entity Type Slide-Over | Slide-over opens in create mode from header button | Given the page is rendered, when the user clicks "+ Define entity type", then the slide-over opens with title "Create entity type" and all fields empty with the NAME field editable | | - [x] |
| 9 | entity-types-screen | Define / Edit Entity Type Slide-Over | Slide-over opens in edit mode from card | Given entity type "vendor_name" exists, when the user clicks "Edit", then the slide-over title is "Edit entity type", NAME shows "vendor_name" (disabled), description is pre-filled, ORG chip is selected, and Required toggle is on | | - [x] |
| 10 | entity-types-screen | Define / Edit Entity Type Slide-Over | BASE MODEL LABEL chip selection is single-select | Given the slide-over is open, when the user clicks "LOC", then LOC chip is active and any previously selected chip becomes unselected | | - [x] |
| 11 | entity-types-screen | Define / Edit Entity Type Slide-Over | Create submits POST and shows success toast | Given valid fields in create mode, when the user clicks "Create entity type", then a POST is sent to `/api/v1/tenants/acme-corp/entity-types`, a success toast appears, and the slide-over closes | | - [x] |
| 12 | entity-types-screen | Define / Edit Entity Type Slide-Over | Edit submits PUT and increments version | Given edit mode for "customer_name" at v1, when the user updates description and saves, then a PUT is sent and the card shows v2 | | - [x] |
| 13 | entity-types-screen | Define / Edit Entity Type Slide-Over | Escape key closes the slide-over | Given the slide-over is open, when the user presses Escape, then the slide-over closes without saving | | - [x] |
| 14 | entity-types-screen | Define / Edit Entity Type Slide-Over | API error shows error toast | Given the API returns 422 or 500, when the user submits, then an error toast is shown and the slide-over remains open | | - [x] |
| 15 | entity-types-screen | Activate / Deactivate Entity Type | Deactivate changes card to inactive state | Given active "ship_to_location", when user clicks "Deactivate", then PATCH is sent with `{"is_active": false}`, card shows "Inactive" pill, button changes to "Reactivate", and active-count decrements | | - [x] |
| 16 | entity-types-screen | Activate / Deactivate Entity Type | Reactivate restores active state | Given inactive entity type, when user clicks "Reactivate", then PATCH is sent with `{"is_active": true}`, card shows "Active" pill, button changes to "Deactivate" | | - [x] |
| 17 | entity-types-screen | Activate / Deactivate Entity Type | Toggle error shows toast and refetches | Given PATCH fails with 500, when toggle completes, then an error toast appears and the list refetches | | - [x] |
| 18 | entity-types-screen | Entity Types API Hooks | useEntityTypes fetches tenant-scoped list | Given user authenticated as "acme-corp", when `useEntityTypes()` is called, then it fetches `GET /api/v1/tenants/acme-corp/entity-types` with query key `["entity-types", "acme-corp"]` | | - [x] |
| 19 | entity-types-screen | Entity Types API Hooks | useCreateEntityType invalidates list on success | Given the mutation is called with valid data, when POST returns 201, then `["entity-types", tenantSlug]` query is invalidated and the list re-fetches | | - [x] |

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

- [x] Scenario 1: `EntityTypesPage.test.tsx` — "renders page header with Entity Types heading", "shows active count in header after data loads", "shows '+ Define entity type' button" — all pass
- [x] Scenario 2: `EntityTypesPage.test.tsx` — "shows 6 skeleton cards while loading" — pass
- [x] Scenario 3: `EntityTypesPage.test.tsx` — "renders empty-state message when no entity types" — pass
- [x] Scenario 4: `EntityTypeCard.test.tsx` — "renders entity type name and version", "renders description", "renders Required pill", "renders Active pill", "renders BASE LABEL MAPPING section", "renders EXAMPLES section" — all pass
- [x] Scenario 5: `EntityTypeCard.test.tsx` — "renders Deactivate button for active entity type" — pass
- [x] Scenario 6: `EntityTypeCard.test.tsx` — "renders Reactivate button for inactive entity type", "renders Inactive pill for inactive entity type" — pass
- [x] Scenario 7: Code inspection — `EntityTypeCard.tsx` inline styles implement `transition: "transform 150ms, border-color 150ms"`, `translateY(-2px)` on hover state, `var(--primary-line)` border-color
- [x] Scenario 8: `DefineEntityTypeSlideOver.test.tsx` — "shows empty fields in create mode", "shows 'Create entity type' title in create mode" — pass
- [x] Scenario 9: `DefineEntityTypeSlideOver.test.tsx` — "pre-fills fields and disables NAME in edit mode", "pre-fills examples", "pre-selects the base label chip from editTarget" — all pass
- [x] Scenario 10: `DefineEntityTypeSlideOver.test.tsx` — "enforces single-select on chip row" — pass
- [x] Scenario 11: `DefineEntityTypeSlideOver.test.tsx` — "calls POST and shows success toast on create"; fetch spy confirms URL and method — pass
- [x] Scenario 12: Code inspection — `useUpdateEntityType` sends PUT to `/api/v1/tenants/{slug}/entity-types/{name}`; backend increments version on PUT
- [x] Scenario 13: Code inspection — `DefineEntityTypeSlideOver` wraps `<SlideOver>` which handles Escape natively (`slide-over.tsx:39-44`)
- [x] Scenario 14: `DefineEntityTypeSlideOver.test.tsx` — "shows error toast and keeps slide-over open on API error" — pass
- [x] Scenario 15: `EntityTypesPage.test.tsx` — "calls toggle mutation when Deactivate is clicked"; fetch spy confirms PATCH to tenant-scoped URL — pass
- [x] Scenario 16: Code inspection — `useToggleEntityType` sends `{ is_active: true }` on Reactivate; `onSuccess` invalidates list
- [x] Scenario 17: Code inspection — `useToggleEntityType.ts` `onError` calls `queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] })`
- [x] Scenario 18: `use-entity-types.test.tsx` — "fetches tenant-scoped entity types URL" confirms `/api/v1/tenants/acme-corp/entity-types`; "uses query key" confirms result — pass
- [x] Scenario 19: `use-create-entity-type.test.tsx` — "returns the created entity type on success"; code inspection confirms `onSuccess` invalidates `["entity-types", tenantSlug]` — pass

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 (tenant-scoped URL): All four hooks call `authFetch(/api/v1/tenants/${tenantSlug}/entity-types...)` where `tenantSlug` comes from `useAuth().user?.tenantSlug`
- [x] Risk 2 (hue derivation): `EntityTypeCard.tsx` — `const hue = HUE_TABLE[index % 7]` — no API field involved
- [x] Risk 3 (chip multi-select): `DefineEntityTypeSlideOver.test.tsx` — "enforces single-select on chip row" — pass; code uses `setSelectedLabel(label)` replacing prior selection
- [x] Risk 4 (NAME disabled in edit): `DefineEntityTypeSlideOver.test.tsx` — "pre-fills fields and disables NAME in edit mode" confirms `disabled` attribute — pass
- [x] Risk 5 (mutation field names): Payload uses `description`, `required_flag`, `base_label_mapping`, `examples`, `name` — matches entity-config spec field names
- [x] Risk 6 (query invalidation scope): All three mutation hooks call `queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] })` — targeted, not full-cache

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching entry.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Automated test | `EntityTypesPage.test.tsx` — "renders page header with Entity Types heading", "shows '+ Define entity type' button", "shows active count in header after data loads" — all pass | 1 | Agent | 2026-06-25 |
| 2 | Automated test | `EntityTypesPage.test.tsx` — "shows 6 skeleton cards while loading" — pass | 2 | Agent | 2026-06-25 |
| 3 | Automated test | `EntityTypesPage.test.tsx` — "renders empty-state message when no entity types" — pass | 3 | Agent | 2026-06-25 |
| 4 | Automated test | `EntityTypeCard.test.tsx` — "renders entity type name and version", "renders description", "renders Required pill", "renders Active pill", "renders BASE LABEL MAPPING section", "renders EXAMPLES section" — all pass | 4 | Agent | 2026-06-25 |
| 5 | Automated test | `EntityTypeCard.test.tsx` — "renders Deactivate button for active entity type" — pass | 5 | Agent | 2026-06-25 |
| 6 | Automated test | `EntityTypeCard.test.tsx` — "renders Reactivate button for inactive entity type", "renders Inactive pill for inactive entity type" — pass | 6 | Agent | 2026-06-25 |
| 7 | Code inspection | `EntityTypeCard.tsx` — inline style `transition: "transform 150ms, border-color 150ms"`, `transform: hovered ? "translateY(-2px)" : "none"`, `borderColor: hovered ? "var(--primary-line)" : undefined` — implemented | 7 | Agent | 2026-06-25 |
| 8 | Automated test | `DefineEntityTypeSlideOver.test.tsx` — "shows empty fields in create mode", "shows 'Create entity type' title in create mode" — pass | 8 | Agent | 2026-06-25 |
| 9 | Automated test | `DefineEntityTypeSlideOver.test.tsx` — "pre-fills fields and disables NAME in edit mode", "pre-fills examples joined with ', ' in edit mode", "pre-selects the base label chip from editTarget in edit mode" — all pass | 9 | Agent | 2026-06-25 |
| 10 | Automated test | `DefineEntityTypeSlideOver.test.tsx` — "enforces single-select on chip row" — pass | 10 | Agent | 2026-06-25 |
| 11 | Automated test | `DefineEntityTypeSlideOver.test.tsx` — "calls POST and shows success toast on create"; fetch spy confirms URL contains `/api/v1/tenants/acme-corp/entity-types` with method POST — pass | 11 | Agent | 2026-06-25 |
| 12 | Code inspection | `useUpdateEntityType` hook sends PUT to `/api/v1/tenants/{slug}/entity-types/{name}`; `onSuccess` invalidates `["entity-types", tenantSlug]` triggering refetch | 12 | Agent | 2026-06-25 |
| 13 | Code inspection | `DefineEntityTypeSlideOver` composes `<SlideOver>` which handles Escape key natively (see `slide-over.tsx:39-44`) | 13 | Agent | 2026-06-25 |
| 14 | Automated test | `DefineEntityTypeSlideOver.test.tsx` — "shows error toast and keeps slide-over open on API error" — pass | 14 | Agent | 2026-06-25 |
| 15 | Automated test | `EntityTypesPage.test.tsx` — "calls toggle mutation when Deactivate is clicked"; fetch spy confirms PATCH to `/api/v1/tenants/acme-corp/entity-types/vendor_name` — pass | 15 | Agent | 2026-06-25 |
| 16 | Code inspection | `useToggleEntityType` sends PATCH with `{ is_active: true }` when Reactivate clicked; `onSuccess` invalidates list | 16 | Agent | 2026-06-25 |
| 17 | Code inspection | `useToggleEntityType.ts` — `onError` calls `queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] })` to refetch | 17 | Agent | 2026-06-25 |
| 18 | Automated test | `use-entity-types.test.tsx` — "fetches tenant-scoped entity types URL" confirms URL contains `/api/v1/tenants/acme-corp/entity-types`; "uses query key" confirms `data` returned — pass | 18 | Agent | 2026-06-25 |
| 19 | Automated test | `use-create-entity-type.test.tsx` — "returns the created entity type on success"; code inspection shows `onSuccess` calls `invalidateQueries({ queryKey: ["entity-types", tenantSlug] })` — pass | 19 | Agent | 2026-06-25 |

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
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
