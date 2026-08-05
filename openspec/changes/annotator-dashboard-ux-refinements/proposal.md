## Why

The annotator dashboard uses ML-internal terminology ("Spans Confirmed") that doesn't match how annotators think about their work, and the Dataset Readiness card shows a raw fraction (`113 / 500 spans`) without explaining why 500 is the target or how much work remains. Annotators can't tell at a glance how close the team is to unlocking model training, or why the threshold exists.

## What Changes

- Rename the "Spans Confirmed" stat card label to "Entities Annotated" on the annotator dashboard. Pure copy change — the underlying count (`COUNT(*) FROM spans`) is unchanged.
- Rewrite the Dataset Readiness card copy to state the purpose of the 500-entity threshold ("minimum before training can begin") and surface actionable progress: entities remaining, percent complete, and the "training unlocks at 500" framing.
- Fix the Dataset Readiness progress bar, which is currently always rendered at 0% — the `bar` field is hardcoded to `0` in the gateway response instead of using the already-computed `bar_pct` — so the visual fill now reflects real progress toward the 500-entity threshold.
- No changes to data collection, span/entity counting logic, or the 500-entity threshold value itself.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dashboard-summary-endpoint`: the annotator role's `StatItem` label for the spans stat changes from `"Spans confirmed"` to `"Entities Annotated"`; the `sideMeta`/messaging fields for the Dataset Readiness panel change to convey remaining-count and percent-complete; the `bar` field is now computed from actual progress instead of hardcoded to `0`.
- `portal-dashboard`: the annotator dashboard's stat card and Dataset Readiness card scenarios update to reflect the new label and copy; no layout or component structure changes.

## Impact

- Backend: [src/gateway/api/v1/dashboard.py](src/gateway/api/v1/dashboard.py) — `_annotator_data` (stat label, `sideMeta`), `_annotator_side_panel` (return and use `bar_pct` instead of discarding it).
- Frontend: no component changes expected — `StatCard` and `MetricsPanel` already render whatever labels/copy the API sends. If the richer copy (e.g. "387 more entities needed") doesn't fit existing fields, `MetricsPanel`/`DashboardData` may need a small additional text field — resolved in design.md.
- No database schema changes, no changes to the 500-entity threshold, no changes to other roles' dashboards.

## Open Questions

- Where should "X more entities needed" / "Training unlocks at 500" copy live given the existing `DashboardData` shape (`sideTop`, `sideMeta`, `big`, `bigUnit`, `sideMetrics`)? Resolved in design.md by reusing/relabeling existing fields rather than adding new ones, to keep the change additive-free on the type contract.
