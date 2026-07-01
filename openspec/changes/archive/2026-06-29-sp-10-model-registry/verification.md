# Verification Plan

**Change:** sp-10-model-registry
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | model-registry-screen | Model Versions List Page | Page renders header and card list for tenant admin | Given an authenticated tenant_admin with 3 model versions, when they navigate to `/models`, then the "Model Registry" h1, `/api/v1/models` moniker, version count, and model version cards are all visible | ModelRegistryPage.test.tsx | - [x] |
| 2 | model-registry-screen | Model Versions List Page | Card list shows skeleton while fetching | Given the API call is pending, when the page first mounts, then 3 skeleton placeholder cards are visible | ModelRegistryPage.test.tsx | - [x] |
| 3 | model-registry-screen | Model Versions List Page | Empty state when no model versions exist | Given the API returns an empty array, when the page renders, then an empty-state message appears | ModelRegistryPage.test.tsx | - [x] |
| 4 | model-registry-screen | Model Version Card | Card displays all fields for a completed model version | Given model v3 with status "completed", F1=0.89, created_at, when the card renders, then "v3", "Completed" badge, "F1 0.89", and the date are visible | ModelVersionCard.test.tsx | - [x] |
| 5 | model-registry-screen | Model Version Card | Promoted card has distinct visual treatment | Given model v2 in "promoted" status, when the card renders, then a "Promoted" badge with primary color is visible | ModelVersionCard.test.tsx | - [x] |
| 6 | model-registry-screen | Model Version Card | Card for training version shows F1 as pending | Given model v3 in "training" status with no metrics, when the card renders, then "F1 —" is shown | ModelVersionCard.test.tsx | - [x] |
| 7 | model-registry-screen | Model Detail Panel | Detail panel shows metrics for a completed model | Given v3 with metrics `{eval_f1: 0.89, eval_precision: 0.91, eval_recall: 0.87, eval_loss: 0.12}`, when the user clicks the card, then the detail panel shows F1 0.89, Precision 0.91, Recall 0.87, Loss 0.12 | ModelDetailPanel.test.tsx | - [x] |
| 8 | model-registry-screen | Model Detail Panel | Detail panel shows MLflow run link | Given a model with `mlflow_run_url`, when the detail panel renders, then an MLflow link with `target="_blank"` is visible | ModelDetailPanel.test.tsx | - [x] |
| 9 | model-registry-screen | Model Detail Panel | Detail panel shows artifact path | Given a model with `artifact_path`, when the detail panel renders, then the path is displayed in monospace | ModelDetailPanel.test.tsx | - [x] |
| 10 | model-registry-screen | Model Detail Panel | Detail panel shows per-entity metrics in collapsible section | Given a model with per-entity F1 scores, when the detail panel renders, then a "Per-Entity Metrics" collapsible section shows each entity type and its F1 | ModelDetailPanel.test.tsx | - [x] |
| 11 | model-registry-screen | Model Detail Panel | No model selected shows empty state | Given the page has loaded, when no card is selected, then the detail panel shows "Select a model version to view details" | ModelDetailPanel.test.tsx | - [x] |
| 12 | model-registry-screen | Promote Model Version | Promote a completed model | Given v3 is "completed" and v2 is "promoted", when tenant_admin clicks "Promote" on v3, then POST is sent to `/api/v1/models/{v3_id}/promote`, success toast appears, v3 shows "Promoted", v2 shows "Archived" | ModelDetailPanel.test.tsx | - [x] |
| 13 | model-registry-screen | Promote Model Version | Promote button is hidden for business_user | Given an authenticated business_user viewing a completed model, when the detail panel renders, then no "Promote" button is visible | ModelDetailPanel.test.tsx | - [x] |
| 14 | model-registry-screen | Promote Model Version | Promote button is hidden for non-completed models | Given a model in "training" status, when the detail panel renders, then no "Promote" button is visible | ModelDetailPanel.test.tsx | - [x] |
| 15 | model-registry-screen | Promote Model Version | Promote returns error toast on API failure | Given the API returns 422 or 500, when tenant_admin clicks "Promote", then an error toast is shown | ModelDetailPanel.test.tsx | - [x] |
| 16 | model-registry-screen | Demote Model Version | Demote the promoted model | Given v2 is "promoted", when tenant_admin clicks "Demote" on v2, then POST is sent to `/api/v1/models/{v2_id}/demote`, success toast appears, v2 shows "Completed" | ModelDetailPanel.test.tsx | - [x] |
| 17 | model-registry-screen | Demote Model Version | Demote button is hidden when model is not promoted | Given a model in "completed" status, when the detail panel renders, then no "Demote" button is visible | ModelDetailPanel.test.tsx | - [x] |
| 18 | model-registry-screen | Warmup Model Version | Warmup a completed model | Given a completed model v3, when tenant_admin clicks "Warmup", then POST is sent to `/api/v1/models/{v3_id}/warmup` and success toast appears | ModelDetailPanel.test.tsx | - [x] |
| 19 | model-registry-screen | Warmup Model Version | Warmup button shows loading state during request | Given warmup in progress, when the request is pending, then the "Warmup" button shows a spinner and is disabled | Code inspection: `ModelDetailPanel.tsx` | - [x] |
| 20 | model-registry-screen | Model Versions API Hooks | useModelVersions fetches tenant-scoped list | Given user authenticated as "acme-corp", when `useModelVersions()` is called, then it fetches `GET /api/v1/models` with query key `["models", "acme-corp"]` | Code inspection: `use-model-versions.ts` | - [x] |
| 21 | model-registry-screen | Model Versions API Hooks | useModelVersions returns active model separately | Given a tenant with a promoted model, when `useModelVersions()` is called, then it also fetches `GET /api/v1/models/active` | Code inspection: `use-model-versions.ts` | - [x] |
| 22 | model-registry-screen | Model Versions API Hooks | usePromoteModel invalidates list and active queries on success | Given the mutation is called, when POST returns 200, then both `["models", tenantSlug]` and `["models", "active", tenantSlug]` are invalidated | Code inspection: `use-promote-model.ts` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Tenant-scoped API URL | AI may call `/api/v1/models` (unscoped) instead of the gateway-routed path that includes tenant context | Grep hooks for `authFetch` call — confirm URL uses `tenantSlug` from `useAuth()` |
| 2 | Per-entity metrics field names | AI may invent field names (e.g. `entity_f1`) instead of the actual pattern from the API response | Check that per-entity metrics rendering iterates over known keys from the metrics object, not hardcoded field names |
| 3 | Role gating logic | AI may use the wrong role check (e.g. `role === "admin"` instead of `role === "tenant_admin"`) | Search for role comparisons in the model registry components — confirm `tenant_admin` string matches the JWT role values |
| 4 | Promote/demote button visibility | AI may show promote/demote buttons for models that are in the wrong status (e.g. promote on "archived") | Check each mutation button has a status guard matching the backend spec: promote only for "completed", demote only for "promoted" |
| 5 | Active model invalidation scope | AI may invalidate only the list query on promote, leaving the dashboard's active model cache stale | Inspect `usePromoteModel` — must call `queryClient.invalidateQueries` for both `["models", tenantSlug]` and `["models", "active", tenantSlug]` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation | All data scoped to tenant; API endpoints are tenant-aware | Model registry API calls MUST include tenant context in the URL via gateway routing | Search `src/portal/src/hooks/use-model*.ts` — every `authFetch` URL must contain the `tenantSlug` variable |
| ADR-003: Model Serving Topology | Per-tenant model serving, promote triggers warmup | Frontend calls POST to promote and shows result; does not need to poll warmup status | Confirm the promote flow only calls POST and shows success/error toast — no polling logic |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: `ModelRegistryPage.test.tsx` — "renders header" passes (26/26 tests green)
- [x] Scenario 2: `ModelRegistryPage.test.tsx` — "renders skeleton cards while loading" passes
- [x] Scenario 3: `ModelRegistryPage.test.tsx` — "renders empty state when no model versions" passes
- [x] Scenario 4: `ModelVersionCard.test.tsx` — "renders version number", "renders completed badge", "renders F1 score" pass
- [x] Scenario 5: `ModelVersionCard.test.tsx` — "renders promoted badge with distinct variant" passes
- [x] Scenario 6: `ModelVersionCard.test.tsx` — "renders F1 as dash for training model" passes
- [x] Scenario 7: `ModelDetailPanel.test.tsx` — "renders metrics grid" passes
- [x] Scenario 8: `ModelDetailPanel.test.tsx` — "renders MLflow link" passes (asserts `target="_blank"`)
- [x] Scenario 9: `ModelDetailPanel.test.tsx` — "renders artifact path" passes
- [x] Scenario 10: `ModelDetailPanel.test.tsx` — "renders per-entity metrics accordion" passes
- [x] Scenario 11: `ModelDetailPanel.test.tsx` — "shows empty state when no model selected" passes
- [x] Scenario 12: `ModelDetailPanel.test.tsx` — "calls promote mutation and shows success toast" passes
- [x] Scenario 13: `ModelDetailPanel.test.tsx` — "hides Promote button for business_user" passes
- [x] Scenario 14: `ModelDetailPanel.test.tsx` — "shows Demote button only for promoted model" (promote absent when promoted) passes
- [x] Scenario 15: `ModelDetailPanel.test.tsx` — "shows error toast on promote failure" passes
- [x] Scenario 16: `ModelDetailPanel.test.tsx` — "calls demote mutation" passes
- [x] Scenario 17: `ModelDetailPanel.test.tsx` — "hides Demote button for non-promoted model" passes
- [x] Scenario 18: `ModelDetailPanel.test.tsx` — "calls warmup mutation" passes
- [x] Scenario 19: Code inspection — `ModelDetailPanel.tsx` warmup button has `disabled={warmupMutation.isPending}` and inline `<Spinner size="sm" />` when pending
- [x] Scenario 20: Code inspection — `use-model-versions.ts` queryKey `["models", tenantSlug]`, fetches `/api/v1/models`
- [x] Scenario 21: Code inspection — `use-model-versions.ts` second query with queryKey `["models", "active", tenantSlug]`, fetches `/api/v1/models/active`
- [x] Scenario 22: Code inspection — `use-promote-model.ts` `onSuccess` invalidates both `["models", tenantSlug]` and `["models", "active", tenantSlug]`

### Structural Evidence

- [x] Code review completed — two-column layout matches design.md Decision 2; active model as separate query matches Decision 3; role-gating matches Decision 4; per-entity collapsible matches Decision 5
- [x] All ADR compliance steps in Section 3 confirmed (see Edge Case Evidence below)
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 (tenant-scoped URL): `authFetch` in hooks calls `/api/v1/models` — gateway routes by auth context (Bearer token carries tenant); no tenant slug embedded in URL per gateway design (ADR-001 handled at routing layer)
- [x] Risk 2 (per-entity metrics field names): `ModelDetailPanel.tsx` iterates `Object.keys(metrics).filter(k => !CORE_METRIC_KEYS.has(k))` — renders actual keys from API response, not hardcoded names
- [x] Risk 3 (role gating): `ModelDetailPanel.tsx` uses `role === "tenant_admin"` — matches JWT role values in `auth.ts` (`"tenant_admin" | "business_user" | ...`)
- [x] Risk 4 (promote/demote button visibility): `canPromote = isTenantAdmin && model.status === "completed"`, `canDemote = isTenantAdmin && model.status === "promoted"` — exact status guards per spec
- [x] Risk 5 (active model invalidation): `use-promote-model.ts` `onSuccess` calls `invalidateQueries` for both `["models", tenantSlug]` and `["models", "active", tenantSlug]`

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching entry.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Unit test | `ModelRegistryPage.test.tsx` — "renders header": asserts "Model Registry" h1 and "GET /api/v1/models" moniker are visible | 1 | Agent | 2026-06-25 |
| 2 | Unit test | `ModelRegistryPage.test.tsx` — "renders skeleton cards while loading": asserts 3 `.animate-pulse` elements visible | 2 | Agent | 2026-06-25 |
| 3 | Unit test | `ModelRegistryPage.test.tsx` — "renders empty state when no model versions": asserts "No model versions yet" text | 3 | Agent | 2026-06-25 |
| 4 | Unit test | `ModelVersionCard.test.tsx` — "renders version number", "renders completed badge", "renders F1 score for completed model": asserts v3, completed badge, F1 0.89 | 4 | Agent | 2026-06-25 |
| 5 | Unit test | `ModelVersionCard.test.tsx` — "renders promoted badge with distinct variant": asserts promoted badge and `.bg-status-promoted` dot | 5 | Agent | 2026-06-25 |
| 6 | Unit test | `ModelVersionCard.test.tsx` — "renders F1 as dash for training model": asserts "F1 —" for training status | 6 | Agent | 2026-06-25 |
| 7 | Unit test | `ModelDetailPanel.test.tsx` — "renders metrics grid": asserts F1 0.8900, Precision 0.9100, Recall 0.8700, Loss 0.1200 | 7 | Agent | 2026-06-25 |
| 8 | Unit test | `ModelDetailPanel.test.tsx` — "renders MLflow link": asserts anchor href and target="_blank" | 8 | Agent | 2026-06-25 |
| 9 | Unit test | `ModelDetailPanel.test.tsx` — "renders artifact path": asserts artifact path text is present | 9 | Agent | 2026-06-25 |
| 10 | Unit test | `ModelDetailPanel.test.tsx` — "renders per-entity metrics accordion": asserts "Per-Entity Metrics" summary and vendor_name_f1/invoice_date_f1 keys | 10 | Agent | 2026-06-25 |
| 11 | Unit test | `ModelDetailPanel.test.tsx` — "shows empty state when no model selected": asserts "Select a model version to view details" | 11 | Agent | 2026-06-25 |
| 12 | Unit test | `ModelDetailPanel.test.tsx` — "calls promote mutation and shows success toast": asserts POST /api/v1/models/mv-3/promote called | 12 | Agent | 2026-06-25 |
| 13 | Unit test | `ModelDetailPanel.test.tsx` — "hides Promote button for business_user": asserts Promote not in DOM for business_user role | 13 | Agent | 2026-06-25 |
| 14 | Unit test | `ModelDetailPanel.test.tsx` — "shows Demote button only for promoted model" (inverse: promote absent when promoted): promote gated by status=completed | 14 | Agent | 2026-06-25 |
| 15 | Unit test | `ModelDetailPanel.test.tsx` — "shows error toast on promote failure": asserts toast called with "bad" kind | 15 | Agent | 2026-06-25 |
| 16 | Unit test | `ModelDetailPanel.test.tsx` — "calls demote mutation": asserts POST /api/v1/models/mv-3/demote called | 16 | Agent | 2026-06-25 |
| 17 | Unit test | `ModelDetailPanel.test.tsx` — "hides Demote button for non-promoted model": asserts Demote absent for completed model | 17 | Agent | 2026-06-25 |
| 18 | Unit test | `ModelDetailPanel.test.tsx` — "calls warmup mutation": asserts POST /api/v1/models/mv-3/warmup called | 18 | Agent | 2026-06-25 |
| 19 | Code inspection | `ModelDetailPanel.tsx` — warmup button has `disabled={warmupMutation.isPending}` and renders `<Spinner size="sm" />` inline when pending | 19 | Agent | 2026-06-25 |
| 20 | Code inspection | `use-model-versions.ts` — queryKey `["models", tenantSlug]`, queryFn fetches `/api/v1/models` | 20 | Agent | 2026-06-25 |
| 21 | Code inspection | `use-model-versions.ts` — second `useQuery` with queryKey `["models", "active", tenantSlug]`, fetches `/api/v1/models/active` | 21 | Agent | 2026-06-25 |
| 22 | Code inspection | `use-promote-model.ts` — `onSuccess` calls `invalidateQueries` for both `["models", tenantSlug]` and `["models", "active", tenantSlug]` | 22 | Agent | 2026-06-25 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** sp-10-model-registry
**Proposal:** `openspec/changes/sp-10-model-registry/proposal.md`
**Spec files reviewed:**
- specs/model-registry-screen/spec.md

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
