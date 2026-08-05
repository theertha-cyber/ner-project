## Context

The annotator dashboard's Dataset Readiness card is powered by `_annotator_data`/`_annotator_side_panel` in [src/gateway/api/v1/dashboard.py](src/gateway/api/v1/dashboard.py:594), which populates the shared `DashboardData` shape (`sideTop`, `sideMeta`, `big`, `bigUnit`, `bar`, `sideMetrics`, `sideBot`, `sideRows`). This shape is rendered generically by `MetricsPanel` ([src/portal/src/components/dashboard/MetricsPanel.tsx](src/portal/src/components/dashboard/MetricsPanel.tsx)) and is shared across all four roles (system_admin, tenant_admin, annotator, business_user) — the component has no role-specific branches.

While reading the current implementation, `_annotator_side_panel` already computes `bar_pct = min(total_spans / 500 * 100, 100)` but its return tuple drops that value; the caller hardcodes `bar=0` in the `DashboardData` returned to the annotator role. The progress bar has therefore never visually filled. This is in scope to fix as part of "make progress obvious," since it directly serves the stated goal and touches the same lines.

## Goals / Non-Goals

**Goals:**

- Rename the annotator "Spans confirmed" stat label to "Entities Annotated" (copy-only).
- Make the Dataset Readiness card explain the 500-entity threshold's purpose and show actionable progress (remaining count, percent complete).
- Fix the dead `bar` field so the progress bar visually reflects real progress.
- Keep the change confined to the annotator role's data assembly and copy — no shared-component or type-contract changes.

**Non-Goals:**

- Changing the 500-entity threshold value or how entities/spans are counted.
- Changing the Dataset Readiness card's visual layout, card position, or the overall dashboard grid.
- Changing any other role's dashboard (system_admin, tenant_admin, business_user).
- Adding new fields to the `DashboardData` type — the redesigned copy must fit within `sideTop`/`sideMeta`/`big`/`bigUnit`/`sideMetrics`/`sideBot`.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|----------------------------|
| None | This is a copy/data-value change within an existing endpoint and component; no ADR in `docs/adr/` (tenant isolation, model strategy, serving topology, OpenSpec governance, agent boundaries, training infra, chat architecture, base-model default, training hyperparameters) governs dashboard copy or this data shape. | N/A |

## Decisions

### Decision 1: Reuse existing `DashboardData` fields for the richer copy, no new fields

**Choice:** Map the new information onto existing fields:
- `sideTop`: `"Dataset readiness"` (unchanged)
- `sideMeta`: changes from `"toward training"` to a dynamic remaining-count string, e.g. `"387 more entities needed"` (or `"Training unlocks — 500 / 500 entities"` once the threshold is met)
- `big` / `bigUnit`: changes from `<count>` / `"/ 500 spans"` to `<percent>` / `"% to training-ready"` — leading with percent-complete is more immediately actionable than a raw fraction, and the raw count/threshold is still visible in `sideMeta` and `sideBot`
- `sideBot`: changes from `"Spans by entity type"` to a two-line-equivalent single string carrying the "why" — e.g. `"500 entities unlocks training · Spans by entity type"` — kept short since `sideBot` is rendered as a single uppercase label above the breakdown rows

**Rationale:** `MetricsPanel` is a shared, generic component used by all four roles. Adding annotator-only fields to `DashboardData` would either force every role to populate them or require conditional rendering in a component that is currently role-agnostic — both increase coupling for a copy-only change. Reusing existing string fields keeps the blast radius to `_annotator_data`/`_annotator_side_panel` and the `portal-dashboard`/`dashboard-summary-endpoint` delta specs.

**Alternatives considered:**
- Add a new `sideSubtext` or `progressLabel` field to `DashboardData` — ruled out: touches the shared type and all four role handlers (even if only annotator populates it), and `MetricsPanel` would need a new optional render branch, for a benefit (one more line of copy) achievable by repurposing `sideBot`.
- Build a bespoke `DatasetReadinessCard` component separate from `MetricsPanel` — ruled out: the proposal explicitly keeps layout and visual design unchanged, and forking a new component for one role's card duplicates the styling `MetricsPanel` already provides.

### Decision 2: Fix `bar` by threading `bar_pct` out of `_annotator_side_panel`

**Choice:** Change `_annotator_side_panel`'s return tuple to include `bar_pct`, and use it (not a hardcoded `0`) for `DashboardData.bar` in `_annotator_data`.

**Rationale:** The value is already computed; discarding it is very likely an oversight (progress bar in `MetricsPanel` has been rendering at 0% width regardless of actual progress). Fixing it directly serves "make it immediately obvious how much more work remains" from the proposal and needs no new computation.

**Alternatives considered:**
- Leave `bar` at 0 and rely only on copy — ruled out: the visual bar is the clearest "actionable progress" signal called out in the proposal, and it's a one-line fix already computed in the same function.

## Risks / Trade-offs

- [Reusing `sideBot` for both "why" copy and the section label above `sideRows` may read as cluttered in a single short string] → Keep the combined string terse (e.g. `"500 entities unlocks training"`) and drop the redundant "Spans by entity type" segment since the rows below are self-explanatory as an entity-type breakdown; verify visually against the existing card padding/font-size before finalizing wording.
- [Percent-complete in `big`/`bigUnit` changes the primary number an annotator sees from an absolute count to a percentage, which existing users may not expect] → `sideMeta` and `sideBot` retain the absolute numbers ("387 more entities needed", entity count breakdown), so the raw count is still visible, just not in the largest-font position.
- [`bar_pct` fix changes visible behavior after being effectively dead code] → Low risk: bar was already computed correctly, just not wired up; no data changes, only a rendering fix.

## Migration Plan

- Single backend change to `src/gateway/api/v1/dashboard.py` (`_annotator_data`, `_annotator_side_panel`) plus the stat label change — no schema migration, no feature flag needed since this only affects display copy for the annotator role.
- Deploy as a normal code change. Rollback is a straightforward revert of the same file since no data or contract changes are involved.

## Open Questions

- Exact wording for `sideMeta`/`sideBot` once the 500-entity threshold is reached (e.g. `"Training unlocks — 500 / 500 entities"` vs. `"Threshold met"`) — left to implementation, constrained only by keeping it truthful and terse; not a blocking unknown.
