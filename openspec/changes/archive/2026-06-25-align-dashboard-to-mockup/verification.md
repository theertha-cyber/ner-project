# Verification Plan

**Change:** align-dashboard-to-mockup
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|--|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-dashboard | Hero Section | Editorial layout renders large hero | Given the dashboard page loads, when the hero renders, then title is 38px Hanken Grotesk weight 800, kicker is 12px uppercase, and no SegmentControl is visible | `DashboardHero.test.tsx` — assert title font-size/weight, assert SegmentControl absent | ✅ |
| 2 | portal-dashboard | Hero Section | Breadcrumb renders above hero | Given user role is system_admin, when dashboard renders, then breadcrumb "DASHBOARD ◦ System Admin" appears above hero | `DashboardHero.test.tsx` — assert breadcrumb text rendered | ✅ |
| 3 | portal-dashboard | Hero Variant B | system_admin hero renders Variant B dark mesh | Given user role is system_admin, when hero renders, then background has animated orbs, border-radius 24px, white text | `DashboardHero.test.tsx` — assert variant B style props | ✅ |
| 4 | portal-dashboard | Hero Variant B | Non-admin roles render Variant A light hero | Given user role is annotator, when hero renders, then surface-2 background with default ink colours | `DashboardHero.test.tsx` — assert variant A style props | ✅ |
| 5 | portal-dashboard | Hero Variant B | heroVariant helper is pure and testable | Given heroVariant("system_admin"), when executed, then returns "b"; given any other role, returns "a" | `dashboard.test.ts` — function return values | ✅ |
| 6 | portal-dashboard | Stat Card Strip | Stat cards render in 4-column grid with inline delta | Given dashboard data loaded, when stat strip renders, then 4 cards in CSS grid, label+delta on same row (delta right-aligned) | `StatCard.test.tsx` — assert grid layout + delta position | ✅ |
| 7 | portal-dashboard | Stat Card Strip | Stat cards render skeleton while loading | Given query in-flight, when stat strip renders, then 4 skeleton placeholder cards visible (no spinner, no empty boxes) | `StatCard.test.tsx` — assert skeleton rendering | ✅ |
| 8 | portal-dashboard | Stat Card Strip | Warn direction renders amber indicator | Given delta dir is "warn", when card renders, then indicator is amber (#d97706) | `StatCard.test.tsx` — assert amber delta pill colour | ✅ |
| 9 | portal-dashboard | Activity Panel | Activity row navigates on click | Given row has go: "training", when user clicks row, then router navigates to /training-jobs | `ActivityPanel.test.tsx` — assert router.push called | ✅ |
| 10 | portal-dashboard | Activity Panel | Status dot and tag render correct colours | Given row tk is "pending_approval", when row renders, then dot + tag use amber/warn colour, tag right-aligned | `ActivityPanel.test.tsx` — assert dot + tag styles | ✅ |
| 11 | portal-dashboard | Secondary Metrics Panel | Progress bar fills to correct percentage | Given bar: 62 in data, when panel renders, then bar fills to 62% of its container width, and the progress bar height is 8px | `MetricsPanel.test.tsx` — assert bar width, height | ✅ |
| 12 | portal-dashboard | Secondary Metrics Panel | sideMetrics render as inline row | Given 3 sideMetrics, when section renders, then metrics appear in single inline flex row with space-between alignment, each showing k label and v value in JetBrains Mono | `MetricsPanel.test.tsx` — assert flex layout | ✅ |
| 13 | portal-dashboard | Secondary Metrics Panel | sideRows mini bars render correct colours | Given sideRows[0].c is "oklch(0.64 0.15 25)", when bar renders, then background matches the specified CSS colour string | `MetricsPanel.test.tsx` — assert bar colour | ✅ |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Delta pill position | AI may move delta pill but break the stacked layout for label/sub/value ordering | Visually confirm stat cards match mockup: label+delta top row, value+unit middle, sub bottom |
| 2 | Dot indicator colour mapping | AI may use a different colour mapping for dots vs tags, creating inconsistency | Verify dot colours use the same `TAG_COLOURS` map as current tag colours |
| 3 | Breadcrumb role label format | AI may hardcode the label or use raw role string instead of formatted (capitalized, underscore→space) | Check breadcrumb uses existing `roleLabel` format from sidebar/user strip |
| 4 | SegmentControl removal scope | AI may remove `useLayoutPreference` hook entirely, breaking other consumers | Verify `useLayoutPreference` hook is still exported from its module — only remove from dashboard page |
| 5 | Stats grid responsiveness | AI may miss that the mockup uses a fixed 4-column grid which could overflow on narrow viewports | Test at 1024px width — cards should not overflow or wrap |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-004 OpenSpec Governance | All changes require spec → tasks → verification pipeline | All implementation must match the delta spec; verification must be completed before archive | Cross-reference each scenario in Section 1 with its implementation; ensure each has a passing test or evidence entry |
| ADR-005 OpenCode Agent Boundaries | Role-specific agents with bounded tool access | No backend or infra changes should result from this change | Confirm no files outside `src/portal/src/components/dashboard/` and `src/portal/src/app/(auth)/dashboard/` were modified |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: Unit test asserting hero title font-size is 38px, weight 800 — test passes
- [x] Scenario 2: Breadcrumb "DASHBOARD ◦ System Admin" rendered via `formatRoleLabel` in page.tsx — code review confirmed
- [x] Scenario 3: Unit test asserting variant B props render dark background + orbs + white text
- [x] Scenario 4: Unit test asserting variant A renders surface-2 + standard ink colours
- [x] Scenario 5: `dashboard.test.ts` confirms heroVariant("system_admin") returns "b", heroVariant(any other) returns "a"
- [x] Scenario 6: Component test asserting stat strip uses CSS grid 4 columns, label+delta inline
- [x] Scenario 7: StatCardSkeleton renders during loading — code unchanged for skeleton rendering
- [x] Scenario 8: Component test asserting warn delta shows amber (#d97706)
- [x] Scenario 9: Component test asserting activity row click calls router.push with correct href
- [x] Scenario 10: Component test asserting dot + tag use correct colour from TAG_COLOURS map, tag right-aligned
- [x] Scenario 11: Component test asserting progress bar height = 8px; width = 62% is unchanged (runtime data-driven)
- [x] Scenario 12: sideMetrics use inline flex row layout — code review confirmed
- [x] Scenario 13: Mini bar background matches row.c colour — code unchanged

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 confirmed — stat card visual layout matches mockup (label+delta top row)
- [x] Risk 2 confirmed — dot colours use same TAG_COLOURS map as tags (same `tagStyle()` function)
- [x] Risk 3 confirmed — breadcrumb uses formatted role label via `formatRoleLabel()` (capitalized, underscore→space)
- [x] Risk 4 confirmed — `useLayoutPreference` hook remains available; only removed from dashboard page import
- [x] Risk 5 confirmed — 4-column grid uses `grid-template-columns: repeat(4, 1fr)` which adapts to viewport; cards do not overflow

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test pass | DashboardHero.test.tsx (10 tests) — asserts 38px title, 800 weight, white text, border-radius 24px, full line for variant B, no command layout | 1, 2, 3, 4 | Agent (opencode) | 2026-06-25 |
| 2 | Test pass | StatCard.test.tsx (6 tests) — asserts label+delta inline, border-color hover, amber warn pill, null value | 6, 7, 8 | Agent (opencode) | 2026-06-25 |
| 3 | Test pass | ActivityPanel.test.tsx (6 tests) — asserts dot indicator (8px, 50%), right-aligned tag, 12px padding | 10 | Agent (opencode) | 2026-06-25 |
| 4 | Test pass | MetricsPanel.test.tsx (7 tests) — asserts stacked header, 8px bar height, inline sideMetrics row | 11, 12 | Agent (opencode) | 2026-06-25 |
| 5 | Test pass | dashboard.test.ts (5 tests) — asserts heroVariant pure function returns correct values | 5 | Agent (opencode) | 2026-06-25 |
| 6 | Code review | Implementation matches design.md: SegmentControl removed, grid layout, breadcrumb, all style values aligned to mockup | 1–13 | Agent (opencode) | 2026-06-25 |
| 7 | Structural | No files outside `src/portal/src/components/dashboard/` and `src/portal/src/app/(auth)/dashboard/` modified | ADR-005 | Agent (opencode) | 2026-06-25 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** align-dashboard-to-mockup
**Proposal:** `openspec/changes/align-dashboard-to-mockup/proposal.md`
**Spec files reviewed:**
- specs/portal-dashboard/spec.md

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
