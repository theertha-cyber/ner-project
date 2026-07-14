## 1. Shared Primitive: LineageFlow

- [x] 1.1 Create `src/portal/src/components/ui/LineageFlow.tsx` accepting an ordered list of `{ label, value, sublabel? }` nodes, rendering connected boxes with arrows, and an `emphasizedIndex` prop to highlight one node (used for the training-job box).
- [x] 1.2 Export `LineageFlow` from `src/portal/src/components/ui/index.ts` (or equivalent barrel) alongside `Badge`, `Spinner`, `SlideOver`.
- [x] 1.3 Write `lineage-flow.test.tsx` covering: renders N boxes with labels/values, renders arrows between boxes, applies emphasis styling to the specified index, renders a fallback value (e.g. "pending") when a node's `value` is null/undefined. (Covers scenarios 7, 8.)

## 2. Job List & Filter Tabs Re-skin

- [x] 2.1 Re-skin `job-filter-tabs.tsx` to use `--surface-2`/`--surface-3`/`--primary`/`--ink-2` tokens and `font-body`/`font-mono` in place of gray-* Tailwind classes; preserve existing tab values and `onChange` behavior.
- [x] 2.2 Rewrite `job-card.tsx` to add: job ID in `font-mono`, hyperparameter summary line (`lr {lr} · {epochs}ep · bs {batch}`), and F1 score (2 decimals, or "—"), reading from `TrainingJob.hyperparams` and `TrainingJob.metrics`. Re-skin card container/pill/dot to tokens.
- [x] 2.3 Update `job-card.test.tsx`: add cases for the hyperparameter line and F1 display (running-with-no-metrics → "—"; completed-with-metrics → "0.90"), update any existing class-name assertions to the new tokens. (Covers scenarios 3, 4.)
- [x] 2.4 Re-skin `job-list.tsx` empty-state and loading-state text/containers to tokens (no structural change).

## 3. Horizontal Status Timeline

- [x] 3.1 Rewrite `job-timeline.tsx` as a horizontal flex row: dot+label groups joined by `flex:1; height:2px` connector lines, per design.md Decision 3. Source dot/connector colors from the same status-color mapping `Badge` uses (no new parallel color map), per design.md Decision 2.
- [x] 3.2 Distinguish the current step (filled dot, bold label) from completed (filled, non-bold) and future (muted/outline) steps.
- [x] 3.3 Rewrite `job-timeline.test.tsx` for the new horizontal DOM shape: verify horizontal layout, current-step distinction, and that failed/rejected/cancelled jobs render their failure-branch chain without a "completed" step. (Covers scenarios 5, 6.)

## 4. Detail Panel: Running Callout, Metrics, MLflow Card, Lineage

- [x] 4.1 Rewrite `job-progress.tsx` as the highlighted info-colored callout: pulsing status dot + "Fine-tuning in progress" label, "epoch {n}/{total}" header, larger animated progress bar, and a stat row (loss, epoch decimal, static/placeholder GPU worker string per design.md Non-Goals).
- [x] 4.2 Write/update `job-progress.test.tsx`: callout renders for `status: "running"` with correct epoch fraction and stat row; no callout renders for non-running statuses. (Covers scenarios 9, 10.)
- [x] 4.3 Rewrite `job-metrics.tsx` to render f1/precision/recall as large stat numbers with individual mini progress bars, plus a separate `eval_loss` line below the group.
- [x] 4.4 Update `job-metrics.test.tsx` for the large-stat layout and the separated eval_loss line. (Covers scenario 11.)
- [x] 4.5 In `job-detail-panel.tsx`: replace the plain-text MLflow link with a bordered card (icon + "MLflow run" label + truncated URL, opens in new tab); integrate `LineageFlow` using a static "Annotated Documents" dataset label, `job.id`, and the model version resolved via `useModelVersions` matching `training_job_id === job.id` (or "pending" if none), per design.md Decision 4, with the middle (job) node emphasized.
- [x] 4.6 Update `job-detail-panel.test.tsx`: MLflow card rendering, lineage diagram rendering (including the "pending" no-version case), and re-skin assertions for header/hyperparameters/error sections to tokens. (Covers scenarios 7, 8, 12.)

## 5. Submit Slide-over & Actions Re-skin

- [x] 5.1 Re-skin `submit-job-slideover.tsx` chrome (header, borders, input/select/slider styling, buttons, error/preflight banner) to tokens and fonts, without changing the span-count preflight fetch, the epoch range slider, or the batch/seq dropdown option sets (`[4,8,16,32]` / `[64,128,256]`).
- [x] 5.2 Update `submit-job-slideover.test.tsx` to confirm behavior is unchanged post-restyle: preflight fetch still runs on open, epoch is still a range input, batch/seq are still selects with the same options. (Covers scenario 13.)
- [x] 5.3 Re-skin `job-actions.tsx` buttons (approve/reject/cancel, reject-reason textarea) to tokens; preserve existing role-gating logic (`canCancel`/`canApprove`/`canReject`) and mutation wiring unchanged.
- [x] 5.4 Update `job-actions.test.tsx` only for class-name/token assertions if any exist; do not change assertions on role-gating behavior.

## 6. Page Shell

- [x] 6.1 Re-skin `page.tsx`: header (`h1` in `font-display` weight ≥700, "+ Submit Job" button styling), two-column layout spacing/borders, to tokens.
- [x] 6.2 Update `page.test.tsx` for the `font-display` heading assertion and any container class-name assertions. (Covers scenario 2.)

## 7. Design Token Compliance Sweep

- [x] 7.1 Grep `src/portal/src/components/training-jobs/` and `page.tsx` for `text-gray-`, `bg-gray-`, `border-gray-`, and any hardcoded hex colors; replace all remaining matches with the appropriate token/utility. Confirm zero matches remain. (Covers scenario 1.)
- [x] 7.2 Manually walk every `JobStatus` value (`pending_approval`, `queued`, `running`, `completed`, `failed`, `rejected`, `cancelled`) in both `system_admin` and `tenant_admin` roles in the running dev app, confirming no gray-* class or unstyled element remains in any state (per design.md Risks and Hallucination Risk 6).

## 8. Post-Verification Bug Fixes (found in live QA after initial sign-off pass)

- [x] 8.1a Fix `job-filter-tabs.tsx`'s active/hover interaction. **Deviation from original task wording:** rather than removing the imperative `onMouseEnter`/`onMouseLeave` mutation entirely, changed `style={active ? undefined : {color:...}}` to `style={active ? {background: ""} : {color:...}}`. Root cause was that `background` was never a key in the style object React tracked in *either* branch, so React's own diffing never reset the raw DOM value the hover handlers wrote — it only touches properties it previously set through the `style` prop. Explicitly asserting `background: ""` on the active branch is a real prop change every time (`undefined`→`""`), so React always re-executes `element.style.background = ''` on that transition, clearing any stale hover value and letting the `bg-brand-primary` class show through. This mirrors the identical, already-shipped, non-buggy pattern in `Sidebar.tsx`'s nav items, which works precisely because its style object always explicitly sets `background` on every render (never omits it) — kept the same imperative-hover mechanism rather than introducing a first-in-codebase Tailwind `hover:` CSS pattern. Covers the new "Filter tab active state is not obscured by hover styling" requirement.
- [x] 8.1b Fixed `job-filter-tabs.tsx` overflow: added `flex-wrap` to the tab row's className so all five tabs stay within the 320px (`w-80`) sidebar (wrapping to a second row) instead of "Failed" spilling into the detail panel. Covers the new "Filter tabs do not overflow into adjacent content" requirement.
- [x] 8.1c In `page.tsx`, added a `useEffect` that calls the existing `handleSelect(listData.items[0].id)` (reusing the existing URL-param-setting logic) whenever the list finishes loading with no `selected` param — fires on initial load and after a filter-tab change (since `handleTabChange` already deletes `selected`). Added an optional `hasSelection` prop (default `true`, to avoid touching any existing call site/test) to `JobDetailPanel`; when `false`, renders a neutral "No job selected" state (surface-3/ink-3, not the red bad-soft/bad "Job not found" styling) before the `isError`/`!job` branch, so "Job not found" is now reserved for a `selected` id that actually fails to resolve. `page.tsx` passes `hasSelection={!!selectedJobId}`. Covers the new "Detail panel defaults to the most recent job when none is selected" requirement.
- [x] 8.1d Added/updated tests: `job-filter-tabs.test.tsx` (stale-hover-then-click regression test, flex-wrap class present), `job-detail-panel.test.tsx` (`hasSelection={false}` renders "No job selected" and not "Job not found"), `page.test.tsx` (auto-selects the first job on load when nothing is selected).

## 10. Full Mockup Fidelity Pass (found via direct visual comparison against `docs/NER Platform.html`'s actual computed template/JS, not just the earlier eyeballed re-skin)

- [x] 10.1 `job-filter-tabs.tsx`: corrected the active-tab color. The mockup's `tFilterTabs` computation (`trainVals()` in the mockup's JS) sets active tab `background: var(--ink)` / `color: var(--surface-2)`, not orange — the original task 2.1/8.1a work had assumed `--primary`/`bg-brand-primary`, which does not match the mockup. Also fixed label casing (lowercase, `_` → space) and order (all, running, pending_approval, completed, failed — running comes before pending_approval in the mockup). Removed the imperative hover mechanism entirely (the mockup's tab template has no hover interaction at all), which also fully eliminates the stale-hover-style bug class from task 8.1a at its root rather than working around it.
- [x] 10.2 `page.tsx`: added the `/api/v1/training-jobs` monospace breadcrumb above the `h1`; resized the `h1` to 34px/font-extrabold/-0.03em letter-spacing (was `text-xl font-bold`, ~20px); restyled the submit button to match the mockup's padding/radius/shadow and lowercased its copy to "+ Submit job".
- [x] 10.3 `job-card.tsx`: added a status-colored dot (via the existing `badgeDotClass`, no new color map) before the job id on every card, pulsing only when running — previously the dot only existed for `status === "running"` and was otherwise absent. Removed the per-card creation-date line, since the mockup does not show one on list cards (the date moved to the detail header instead, see 10.4). Changed the selected-card border/background to use `var(--primary-line)` inline (matching the mockup) instead of the `border-brand-primary` Tailwind class.
- [x] 10.4 `job-detail-panel.tsx`: header now shows the full job id (was truncated to 8 characters) at a larger monospace weight, plus the job's `created_at` right-aligned in the same row — both present in the mockup's `dJobId`/`dCreated` header but absent from the original implementation. Changed the hyperparameters grid from `grid-cols-2` to `grid-cols-4` (mockup lays all four out in one row). Added `sublabel`s to the lineage diagram's TRAINING JOB ("dslim/bert-base-NER", the real ADR-002-mandated base model, not the mockup's shortened decorative text) and MODEL VERSION ("registry") boxes; deliberately left the DATASET box's sublabel (mockup shows a span count) out, since no per-job confirmed-span-count field exists on `TrainingJob` — inventing one would violate this change's Non-Goals.
- [x] 10.5 Added/updated tests across `job-filter-tabs.test.tsx`, `job-card.test.tsx`, `job-detail-panel.test.tsx`, `page.test.tsx` for all of the above (tab colors/labels/order, status dot on non-running jobs, breadcrumb, 4-column grid, full id + date in header, lineage sublabels); updated pre-existing tests whose literal assertions (old tab labels, `border-brand-primary` class, "+ Submit Job" casing) no longer matched the corrected markup.

## 11. Verification & Evidence

- [x] 11.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 11.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 11.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 11.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (N/A — no constraining ADRs; confirm this remains true).
- [x] 11.5 Re-ran acceptance criteria for the 4 scenarios (14-17) added in § 8 — all pass, logged as verification.md scenarios 14-17 and Evidence Log #5.
- [x] 11.6 Re-ran acceptance criteria for the scenarios added in § 10 (filter-tab colors, breadcrumb/heading/button, card status dot, detail-header id/date, hyperparameters grid, lineage sublabels) — all pass, logged as verification.md scenarios 18-24 and Evidence Log #6.
- [ ] 11.7 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 11.8 Ran `openspec validate redesign-training-jobs-ui --type change --strict` — "Change 'redesign-training-jobs-ui' is valid".
