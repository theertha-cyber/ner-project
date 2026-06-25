## 1. Dashboard Page Structural Changes

- [x] 1.1 Update `dashboard/page.tsx` — change page `maxWidth` from 1280 → 1240 and add bottom padding 60px
- [x] 1.2 Update `dashboard/page.tsx` — replace stat strip `display: flex; flex-wrap: wrap` with `display: grid; grid-template-columns: repeat(4, 1fr)`
- [x] 1.3 Update `dashboard/page.tsx` — add breadcrumb line (`"DASHBOARD ◦ {roleLabel}"`) above the hero section using formatted role label
- [x] 1.4 Update `dashboard/page.tsx` — remove `SegmentControl` import, JSX, and `useLayoutPreference` hook; change panels gap from 14 → 16px

## 2. DashboardHero Visual Alignment

- [x] 2.1 Update `DashboardHero.tsx` — increase title font-size from 30 → 38px and weight from 700 → 800
- [x] 2.2 Update `DashboardHero.tsx` — increase line font-size from 14 → 15px and max-width from 72ch → 560px
- [x] 2.3 Update `DashboardHero.tsx` — increase Variant B border-radius from 16 → 24px
- [x] 2.4 Update `DashboardHero.tsx` — remove Command layout variants (keep only large typographic style); Variant B always shows full title+line

## 3. StatCard Layout Changes

- [x] 3.1 Update `StatCard.tsx` — restructure DOM: label + delta pill on same row (flex space-between)
- [x] 3.2 Update `StatCard.tsx` — change hover effect from box-shadow to border-color (`var(--primary-line)`)
- [x] 3.3 Update `StatCardSkeleton.tsx` — adjust skeleton dimensions if padding changed

## 4. ActivityPanel Row Style Changes

- [x] 4.1 Update `ActivityPanel.tsx` — add colored dot indicator (small `<div>` with `border-radius: 50%`) to left of each row
- [x] 4.2 Update `ActivityPanel.tsx` — move status tag badge to right-aligned position (after title/sub text)
- [x] 4.3 Update `ActivityPanel.tsx` — increase row padding from `9px 10px` to `12px`

## 5. MetricsPanel Layout Changes

- [x] 5.1 Update `MetricsPanel.tsx` — change title/meta layout from flex space-between to stacked (title above meta, 4px margin bottom title, 16px margin bottom meta)
- [x] 5.2 Update `MetricsPanel.tsx` — increase progress bar (`GrowBar`) height from 6px → 8px
- [x] 5.3 Update `MetricsPanel.tsx` — change sideMetrics from stacked column to inline flex row with space-between
- [x] 5.4 Update `MetricsPanel.tsx` — adjust side bottom section title margin to 14px bottom

## 6. Update Component Tests

- [x] 6.1 Update `DashboardHero.test.tsx` — assert new font sizes (38px title), remove Command layout tests, add breadcrumb test
- [x] 6.2 Update `StatCard.test.tsx` — assert delta pill inline with label (same row), new hover effect style
- [x] 6.3 Update `ActivityPanel.test.tsx` — assert dot indicator + right-aligned tag, new row padding
- [x] 6.4 Update `MetricsPanel.test.tsx` — assert inline sideMetrics row, bar height 8px, stacked header
- [x] 6.5 Update `dashboard/lib/dashboard.test.ts` — confirm heroVariant tests still pass

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [x] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [x] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 7.6 Run `openspec validate align-dashboard-to-mockup --type change --strict` and confirm it exits clean before archive
