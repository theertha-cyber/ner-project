## Why

The current SP-04 dashboard UI diverges from the NER Platform mockup (`docs/NER Platform.html`) in several visual and structural ways: hero sizing, stat card layout, activity row indicator style, metrics panel spacing, breadcrumb presence, and overall page dimensions. Aligning the implementation to the mockup ensures design consistency across the platform before new screens are built on top of the same design system.

## What Changes

- Add a **breadcrumb** line (`"DASHBOARD ◦ {roleLabel}"`) above the hero section
- Increase **hero title** font-size from 30px → 38px and weight from 700 → 800
- Increase **hero line** font-size from 14px → 15px
- Change **hero border-radius** from 16px → 24px for Variant B
- Change **stat card grid** from `flex-wrap` to `grid-template-columns: repeat(4, 1fr)`
- Move **delta pill** on stat cards from below sub text to top-right (inline with label)
- Change **activity row indicator** from left-aligned tag badge → right-aligned tag badge with dot indicator on the left
- Adjust **metrics panel**:
  - Title/meta layout from flex space-between to stacked (title above meta)
  - Progress bar height from 6px → 8px
  - Side metrics from stacked column to inline flex row
- Change **panel gap** from 14px → 16px
- Change **page bottom padding** from none → 60px
- Change **page max-width** from 1280px → 1240px
- Remove **SegmentControl** (Editorial/Command layout toggle) from dashboard page
- Adjust **stat card hover** from box-shadow → border-color transition

## Capabilities

### New Capabilities

*(none — all changes are modifications to existing dashboard capability)*

### Modified Capabilities

- `portal-dashboard`: Stat card layout (label+delta inline, grid layout), hero sizing/fonts, activity panel row style (dot indicator + right-aligned tags), metrics panel layout and spacing, breadcrumb addition, SegmentControl removal, overall page dimensions

## Impact

- **Frontend components**: `dashboard/page.tsx`, `DashboardHero.tsx`, `StatCard.tsx`, `ActivityPanel.tsx`, `MetricsPanel.tsx`, `StatCardSkeleton.tsx` — layout, spacing, and visual style changes only (no data shape changes)
- **Types**: No changes — `DashboardData` shape remains identical
- **Backend API**: No changes — the endpoint response is unaffected
- **Tests**: Component tests for `StatCard`, `ActivityPanel`, `DashboardHero`, `MetricsPanel` need snapshot/style updates
- **No breaking changes**

## Open Questions

- Is the `heroVariant(role)` function still needed after removing the SegmentControl? (Hero variant B for system_admin should be determined by role, not user toggle.) — **Assumption**: Yes, keep hero variant by role, remove the SegmentControl entirely.
- Should the breadcrumb show the localized role label (e.g. "System Admin" vs "system_admin")? — **Assumption**: Use the same `roleLabel` format as the sidebar (capitalized, underscore → space).
