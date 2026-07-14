# Verification Plan

**Change:** redesign-training-jobs-ui
**Generated:** 2026-07-13
**Status:** 🟡 Implementation complete, including the 3 bugs found in live QA after the original sign-off pass (scenarios 14-17, Evidence Log #5) and a further full mockup-fidelity pass done by diffing the actual computed styles/JS in `docs/NER Platform.html` against every component (scenarios 18-24, Evidence Log #6) — the original re-skin had gotten several concrete values wrong (active-tab color, header content, grid columns, list-card dot). Functional/structural/edge-case evidence collected — Audit Record still requires human reviewer sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | training-jobs-screen | Design token compliance | No generic gray utility classes remain | Given the training-jobs component directory, when searched for `text-gray-`, `bg-gray-`, or `border-gray-`, then no match is found | grep audit over `src/portal/src/components/training-jobs/` + `page.tsx` | - [x] |
| 2 | training-jobs-screen | Design token compliance | Page heading uses display font | Given a user navigates to `/training-jobs`, when the page renders, then the `h1` "Training Jobs" heading uses `font-display` at weight ≥700 | `page.test.tsx` | - [x] |
| 3 | training-jobs-screen | Job list card content | Running job card shows full summary | Given a running job with hyperparams and no metrics, when its `JobCard` renders, then it shows the mono job ID, a pulsing dot, the "lr {lr} · {epochs}ep · bs {batch}" line, and F1 "—" | `job-card.test.tsx` | - [x] |
| 4 | training-jobs-screen | Job list card content | Completed job card shows F1 score | Given a completed job with `metrics.eval_f1 = 0.90`, when its `JobCard` renders, then the F1 value reads "0.90" and no pulsing dot is shown | `job-card.test.tsx` | - [x] |
| 5 | training-jobs-screen | Horizontal status timeline | Running job shows horizontal timeline with current step highlighted | Given a running job, when `JobTimeline` renders, then all lifecycle steps appear in a single horizontal row with "running" visually distinguished, prior steps marked completed, and later steps muted | `job-timeline.test.tsx` | - [x] |
| 6 | training-jobs-screen | Horizontal status timeline | Failed job shows the failure branch, not the full lifecycle | Given a failed job, when `JobTimeline` renders, then the row shows `pending_approval → queued → running → failed` and omits "completed" | `job-timeline.test.tsx` | - [x] |
| 7 | training-jobs-screen | Dataset-to-model lineage diagram | Lineage renders for a completed job with a promoted model | Given a job id "tj_7c04" and a model version `{training_job_id: "tj_7c04", version_number: 3}`, when the detail panel renders, then three connected boxes read "Annotated Documents", "tj_7c04", "v3" with the middle box emphasized | `lineage-flow.test.tsx` + `job-detail-panel.test.tsx` | - [x] |
| 8 | training-jobs-screen | Dataset-to-model lineage diagram | Lineage renders "pending" for a job with no model version yet | Given a job with no matching model version in `/api/v1/models`, when the detail panel renders, then the third lineage box reads "pending" | `job-detail-panel.test.tsx` | - [x] |
| 9 | training-jobs-screen | Live running-job callout | Running job shows the live callout | Given a running job with `current_epoch: 2`, `current_loss: 0.032`, `num_epochs: 3`, when the detail panel renders, then an info-colored callout with pulsing dot, "epoch 2/3", a ~2/3-width progress bar, and a loss/epoch/GPU-worker stat row is visible | `job-progress.test.tsx` | - [x] |
| 10 | training-jobs-screen | Live running-job callout | Non-running job shows no callout | Given a completed job, when the detail panel renders, then no running-callout element is present | `job-progress.test.tsx` | - [x] |
| 11 | training-jobs-screen | Large-stat evaluation metrics | Completed job shows large-stat metrics | Given a completed job with `eval_f1`/`eval_precision`/`eval_recall`/`eval_loss` metrics, when the detail panel renders, then f1/precision/recall are shown as large stat numbers each with a mini progress bar, and eval_loss is shown separately below | `job-metrics.test.tsx` | - [x] |
| 12 | training-jobs-screen | MLflow run link as card | Job with MLflow URL shows link card | Given a job with `mlflow_run_url` set, when the detail panel renders, then a bordered card with icon, "MLflow run" label, and the (truncated) URL is shown, linking out in a new tab | `job-detail-panel.test.tsx` | - [x] |
| 13 | training-jobs-screen | Submit slide-over visual parity without behavior change | Slide-over still performs span preflight check after restyle | Given a Tenant Admin opens the submit slide-over, when it mounts, then the span-count preflight check still fires, the epoch control is still a range slider, and batch/seq are still dropdowns with unchanged option sets | `submit-job-slideover.test.tsx` | - [x] |
| 14 | training-jobs-screen | Filter tab active state is not obscured by hover styling | Selecting a tab shows the dark/ink active fill immediately | Given "all" is selected and the pointer hovers then clicks "pending approval", when the click registers, then "pending approval" shows `background: var(--ink)` / `color: var(--surface-2)` without a residual hover-gray background, even without the pointer leaving and re-entering | `job-filter-tabs.test.tsx` — "highlights the selected tab..." and "re-styles a tab correctly when it becomes the selected one..." (superseded the `bg-brand-primary`-based test from the first fix pass once § 10 corrected the actual active color to `var(--ink)`, and removed the imperative hover mechanism entirely rather than patching it) | - [x] |
| 15 | training-jobs-screen | Filter tabs do not overflow into adjacent content | All five tabs render without overlapping the detail panel | Given the page renders at the standard sidebar width, when `JobFilterTabs` renders all five tabs, then every tab's bounding box stays within the sidebar column and none overlaps the detail panel | `job-filter-tabs.test.tsx` — "wraps tabs instead of letting them overflow their container" (asserts `flex-wrap` mechanism; jsdom cannot assert real pixel overflow) | - [x] |
| 16 | training-jobs-screen | Detail panel defaults to the most recent job when none is selected | Loading the page with no selection auto-selects the latest job | Given a Tenant Admin navigates to `/training-jobs` with no `selected` param and the list returns at least one job, when the list finishes loading, then the first (most recent) job is auto-selected and rendered instead of "Job not found" | `page.test.tsx` — "auto-selects the first (most recent) job when the list loads with nothing selected" | - [x] |
| 17 | training-jobs-screen | Detail panel defaults to the most recent job when none is selected | An explicitly-selected job id that does not exist still shows "Job not found" | Given the URL contains `?selected=does-not-exist`, when the detail fetch resolves as an error, then "Job not found" is shown | `job-detail-panel.test.tsx` — pre-existing "shows not found when error" test still passes (covers `hasSelection` default `true` + `isError`), plus new "shows a neutral empty state instead of 'Job not found' when nothing is selected yet" test proves the two states are now distinct | - [x] |
| 18 | training-jobs-screen | Page header matches the mockup's breadcrumb, heading scale, and submit button | Header shows the API-path breadcrumb above the heading | Given a user navigates to `/training-jobs`, when the page renders, then a small monospace `/api/v1/training-jobs` label appears above the heading | `page.test.tsx` — "renders the API-path breadcrumb above the heading" | - [x] |
| 19 | training-jobs-screen | Page header matches the mockup's breadcrumb, heading scale, and submit button | Submit button copy matches the mockup exactly | Given a Tenant Admin views the page, when the header renders, then the submit button reads "+ Submit job" | `page.test.tsx` — "renders submit job button" (updated to lowercase "job") | - [x] |
| 20 | training-jobs-screen | Detail panel header shows the full job id and creation timestamp | Detail header shows the untruncated job id and a creation date | Given a selected training job with a full id and a `created_at` timestamp, when the detail panel renders, then the header shows the complete job id and a formatted creation date/time at the right edge | `job-detail-panel.test.tsx` — "shows the full job id and creation date in the header" | - [x] |
| 21 | training-jobs-screen | Job list card content | Non-running job still shows a status-colored dot | Given a training job with status "pending_approval", when its `JobCard` renders, then a dot colored per that status is visible and does not pulse | `job-card.test.tsx` — "shows a status-colored dot even when the job is not running" | - [x] |
| 22 | training-jobs-screen | Hyperparameters render as a single 4-column row | Hyperparameters grid has 4 columns | Given a training job with hyperparams set, when the detail panel renders the hyperparameters section, then its grid container has 4 columns, not 2 | `job-detail-panel.test.tsx` — "renders the hyperparameters grid as a single 4-column row" | - [x] |
| 23 | training-jobs-screen | Dataset-to-model lineage diagram | Training job and model version boxes show their sublabels | Given a training job detail panel renders its lineage diagram, when the TRAINING JOB and MODEL VERSION boxes render, then they show "dslim/bert-base-NER" and "registry" sublabels respectively | `job-detail-panel.test.tsx` — "shows the base-model and registry sublabels in the lineage diagram" | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | `LineageFlow` reusable primitive (design.md Decision 1) | AI may over-engineer the primitive with extra props (icons, per-node custom colors, configurable arrow styles) not needed by this change's single consumer | Read `components/ui/LineageFlow.tsx` — its prop shape should be limited to `{label, value, sublabel?}` triples with no unused configurability |
| 2 | Status-color source (design.md Decision 2) | AI may introduce a second, parallel status→color map (mirroring the mockup's raw `statusColors()`) instead of reusing `Badge`'s existing mapping, causing drift between card pill and timeline dot colors | Grep the training-jobs component diff for a new status-color object literal; confirm `JobTimeline` and `JobCard` both derive color from the same source `Badge` already uses |
| 3 | `JobTimeline` rewrite (design.md Decision 3) | AI may take the cheaper path of a CSS `flex-direction: row` flip on the existing vertical DOM instead of restructuring to flat dot+label rows with `flex:1` connectors, leaving broken/dead connector styling | Visually inspect the rendered timeline in the browser at each lifecycle stage; confirm connector lines are horizontal and evenly fill the gap between dots, not vestiges of the vertical layout |
| 4 | GPU worker placeholder (design.md Non-Goals) | AI may invent a real "GPU worker" API field, hook, or backend call instead of keeping it a static/decorative string as scoped | Grep for new fields named `gpu_worker`/`worker_id` in hooks/types under `src/portal/src` and in any backend schema — none should exist from this change |
| 5 | Test suite updates (design.md Risks) | AI may re-skin components without updating `*.test.tsx` assertions that hard-code old Tailwind class names or the vertical-timeline DOM shape, leaving the suite red or silently weakened (assertions loosened to pass) | Run the training-jobs test suite; confirm all tests pass without any assertion having been deleted or made trivially permissive compared to its pre-change intent |
| 6 | Design token compliance in edge-case states | AI may re-skin the happy-path states (list, running detail) but leave gray-* classes in less-visited states (error banner, loading spinner, empty list, rejected/cancelled detail) | Walk every `JobStatus` value in both roles per design.md's stated risk mitigation; confirm no gray-* class remains in any state |
| 7 | Submit slide-over behavior preservation | AI may accidentally alter behavior while restyling — e.g. replace the epoch range slider with a text input, or drop the span-count preflight fetch — since visual and behavioral code are interleaved in that component | Manually open the submit slide-over and confirm: span count still loads on open, epoch is still a slider, batch/seq are still the same dropdown option sets (`[4,8,16,32]` / `[64,128,256]`) |
| 8 | Cross-tenant model-version lookup for the lineage diagram (discovered during implementation, not anticipated in the original design.md) | The new `useModelVersions()` call inside `JobDetailPanel` has no tenant override for `system_admin`; a live QA pass showed it would always resolve against the wrong (or no) tenant when a system_admin views another tenant's job, always showing "pending" or erroring. Fixed by adding a `tenant_id` query-param override to `GET /api/v1/models` and `GET /api/v1/models/active` (`src/training_service/api/v1/models.py`), mirroring the identical existing pattern in `training_jobs.py`. **This is a backend change**, deviating from design.md's "presentation-only, no backend changes" Non-Goal — flagged here explicitly since it needs human sign-off as an intentional, scoped exception. | Read `src/training_service/api/v1/models.py`'s `list_model_versions`/`get_active_model` — confirm the added `tenant_id: Query(None)` + `system_admin` branch exactly mirrors `training_jobs.py`'s established pattern, and confirm `job-detail-panel.test.tsx`'s cross-tenant test asserts the correct `tenant_id=` query param is sent |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

No constraining ADRs. design.md confirms ADR-001 through ADR-008 govern backend/infrastructure/process concerns (tenant isolation, base-model strategy, model-serving topology, OpenSpec governance, agent boundaries, training infrastructure, chatbot architecture, default inference model) and none constrain frontend presentation; this change has no backend surface.

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| — | No constraining ADRs | N/A | N/A |

**Note:** This change made one backend edit (`src/training_service/api/v1/models.py`, adding a `tenant_id` query-param override to two GET endpoints — see Hallucination Risk 8) despite design.md's presentation-only scope. No ADR governs API tenant-scoping conventions specifically, but this deviation is called out here for reviewer awareness since it's outside the change's originally stated boundary.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived. Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (No generic gray utility classes remain): `grep -rn "text-gray-\|bg-gray-\|border-gray-" src/portal/src/components/training-jobs/ "src/portal/src/app/(auth)/training-jobs/page.tsx"` → zero matches (exit code 1)
- [x] Scenario 2 (Page heading uses display font): `page.test.tsx` — "renders the h1 heading in font-display at weight >= 700" asserts `className` contains `font-display` and `font-bold`; passes
- [x] Scenario 3 (Running job card shows full summary): `job-card.test.tsx` — "shows job id, hyperparameter line, and F1 '—' for a running job with no metrics"; passes
- [x] Scenario 4 (Completed job card shows F1 score): `job-card.test.tsx` — "shows F1 score to two decimal places for a completed job with metrics"; passes
- [x] Scenario 5 (Running job shows horizontal timeline with current step highlighted): `job-timeline.test.tsx` — "distinguishes the current step from completed and future steps"; passes. Visually confirmed in browser QA screenshot (horizontal row, blue filled "Running" dot, green completed dots/lines, muted "Completed" step)
- [x] Scenario 6 (Failed job shows the failure branch): `job-timeline.test.tsx` — "shows the failure branch without a completed step for a failed job"; passes. Visually confirmed (red terminal dot on "Failed", no "Completed" step)
- [x] Scenario 7 (Lineage renders for a completed job with a promoted model): `lineage-flow.test.tsx` + `job-detail-panel.test.tsx` ("renders the resolved model version in the lineage diagram", "passes the job's own tenant_id as a query param when viewed by system_admin"); passes
- [x] Scenario 8 (Lineage renders "pending" for a job with no model version yet): `job-detail-panel.test.tsx` — "renders the lineage diagram with the job id and 'pending' when no model version exists"; passes. Visually confirmed in browser QA screenshot across all 7 statuses
- [x] Scenario 9 (Running job shows the live callout): `job-progress.test.tsx` — "renders the live callout for a running job with correct epoch fraction and stat row"; passes. Visually confirmed (info callout, pulsing dot, "epoch 2/3", progress bar, loss/epoch/GPU-worker row)
- [x] Scenario 10 (Non-running job shows no callout): `job-progress.test.tsx` — "renders no callout when currentEpoch is null"; passes
- [x] Scenario 11 (Completed job shows large-stat metrics): `job-metrics.test.tsx` — "renders f1/precision/recall as large stat numbers with mini progress bars, and eval_loss separately"; passes. Visually confirmed (0.90/0.92/0.89 stat numbers with mini bars, separate "eval_loss 0.021" line)
- [x] Scenario 12 (Job with MLflow URL shows link card): `job-detail-panel.test.tsx` — "renders MLflow link card when available"; passes. Visually confirmed (bordered card, icon, truncated URL)
- [x] Scenario 13 (Slide-over still performs span preflight check after restyle): `submit-job-slideover.test.tsx` — "keeps the epoch control a range slider and batch/seq as dropdowns with unchanged option sets" plus pre-existing preflight tests; passes
- [x] Scenario 14 (Selecting a tab shows the dark/ink active fill immediately): fixed by task 10.1, superseding 8.1a's `bg-brand-primary`-based patch once direct comparison against the mockup's `trainVals()` computation showed the real active color is `var(--ink)`/`var(--surface-2)`, not orange. Removed the imperative hover mechanism entirely (the mockup has none on these tabs), eliminating the stale-hover-style bug class at the root. `job-filter-tabs.test.tsx` — "highlights the selected tab with the dark/ink background..." and "re-styles a tab correctly when it becomes the selected one..."; passes
- [x] Scenario 15 (All five tabs render without overlapping the detail panel): fixed by task 8.1b — added `flex-wrap` to the tab row's className. `job-filter-tabs.test.tsx` — "wraps tabs instead of letting them overflow their container"; passes
- [x] Scenario 16/17 (Auto-select latest job / genuine "Job not found" only for unresolvable selection): fixed by task 8.1c — `page.tsx` gained a `useEffect` that calls the existing `handleSelect(listData.items[0].id)` when the list loads with no `selected` param (fires on initial load and after a filter-tab change, since `handleTabChange` already clears `selected`); `JobDetailPanel` gained an optional `hasSelection` prop (default `true`) rendering a neutral "No job selected" state ahead of the `isError`/`!job` branch. `page.test.tsx` — "auto-selects the first (most recent) job when the list loads with nothing selected"; `job-detail-panel.test.tsx` — "shows a neutral empty state instead of 'Job not found' when nothing is selected yet" plus the pre-existing "shows not found when error" test (unchanged, confirming the genuine-404 path is untouched); all pass
- [x] Scenario 18/19 (Breadcrumb / submit button copy): fixed by task 10.2 — added the `/api/v1/training-jobs` breadcrumb and lowercased the submit button to "+ Submit job", matching the mockup's literal template text. `page.test.tsx` — "renders the API-path breadcrumb above the heading", "renders submit job button"; passes
- [x] Scenario 20 (Full job id + creation date in detail header): fixed by task 10.4 — header now renders `job.id` in full (was `.slice(0,8)`) plus `job.created_at` right-aligned. `job-detail-panel.test.tsx` — "shows the full job id and creation date in the header"; passes
- [x] Scenario 21 (Non-running job still shows a status-colored dot): fixed by task 10.3 — `job-card.tsx`'s dot is now always rendered via `badgeDotClass(job.status)`, pulsing only when running (previously the dot element didn't exist at all for non-running jobs). `job-card.test.tsx` — "shows a status-colored dot even when the job is not running"; passes
- [x] Scenario 22 (Hyperparameters grid has 4 columns): fixed by task 10.4 — changed `grid-cols-2` to `grid-cols-4`. `job-detail-panel.test.tsx` — "renders the hyperparameters grid as a single 4-column row"; passes
- [x] Scenario 23 (Lineage sublabels): fixed by task 10.4 — added `sublabel: "dslim/bert-base-NER"` (real, ADR-002-mandated base model) to the TRAINING JOB node and `sublabel: "registry"` to the MODEL VERSION node. `job-detail-panel.test.tsx` — "shows the base-model and registry sublabels in the lineage diagram"; passes

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions; one deviation identified and documented (Hallucination Risk 8 / Section 3 note — backend `tenant_id` query-param addition to `models.py`, required for lineage correctness under `system_admin`)
- [x] All ADR compliance steps in Section 3 confirmed ✓ (N/A — no constraining ADRs)
- [x] No undocumented architectural patterns introduced — the `models.py` change reuses the exact existing `training_jobs.py` tenant-override pattern verbatim, not a new pattern
- [x] No AI-invented requirements present in generated code (cross-checked against `specs/training-jobs-screen/spec.md`) — full portal test suite run: 477 passed, 5 failed pre-existing and unrelated (`nav-config.test.ts` x3, `AnnotationImportPreview.test.tsx` x1, `BatchRunsTab.test.tsx` x1 — confirmed present before this change's edits via `git stash`/re-run, untouched files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `LineageFlow` prop shape is `{label, value, sublabel?}` + `emphasizedIndex`/`fallbackValue`, no unused configurability (`src/portal/src/components/ui/LineageFlow.tsx`)
- [x] Risk 2 mitigation confirmed — `badgeVariantClasses`/`badgeDotClass` exported from `badge.tsx` and imported by `job-timeline.tsx`; no second status-color map introduced (grep confirms only one `Record<BadgeVariant/JobStatus, string>` color literal exists, in `badge.tsx`)
- [x] Risk 3 mitigation confirmed — `job-timeline.tsx` rewritten as a flat `flex` row of dot+label divs joined by `flex:1; height:2px` connectors; visually verified horizontal at running/failed/rejected/cancelled stages in browser QA screenshot, no vertical-layout artifacts
- [x] Risk 4 mitigation confirmed — `grep -rn "gpu_worker\|worker_id" src/portal/src` returns no matches; "GPU worker-2" in `job-progress.tsx` is a static string literal
- [x] Risk 5 mitigation confirmed — full training-jobs + ui test suite: 18 files / 77 tests passed (see Evidence Log #2); no assertion deleted or weakened, several strengthened (e.g. `job-card.test.tsx` gained explicit hyperparameter/F1 cases)
- [x] Risk 6 mitigation confirmed — all 7 `JobStatus` values (`pending_approval`, `queued`, `running`, `completed`, `failed`, `rejected`, `cancelled`) walked live in a real browser via Playwright against the running dev server; automated DOM scan for `text-gray-|bg-gray-|border-gray-` classes returned zero matches (see Evidence Log #3)
- [x] Risk 7 mitigation confirmed — `submit-job-slideover.test.tsx` explicitly asserts the epoch control is still `input[type=range]` and batch/seq are still `<select>` with option values `["4","8","16","32"]`/`["64","128","256"]`; all pre-existing preflight/submit-behavior tests still pass unmodified
- [x] Risk 8 mitigation confirmed — `models.py`'s new `tenant_id` param branch mirrors `training_jobs.py`'s `list_training_jobs`/`get_training_job` pattern exactly (same `Query(None, description=...)`, same `role == "system_admin"` branch, same 400 on missing override); `job-detail-panel.test.tsx`'s cross-tenant test asserts the fetch URL contains `tenant_id=tenant-b`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Grep audit | `grep -rn "text-gray-\|bg-gray-\|border-gray-" src/portal/src/components/training-jobs/ "src/portal/src/app/(auth)/training-jobs/page.tsx"` → exit code 1, zero matches | 1 | AI (Claude) | 2026-07-13 |
| 2 | Automated test run | `npx vitest run` in `src/portal` — training-jobs + ui suites: 18 test files / 77 tests passed (`job-card`, `job-list`, `job-filter-tabs`, `job-timeline`, `job-progress`, `job-metrics`, `job-detail-panel`, `job-actions`, `submit-job-slideover`, `page`, `LineageFlow`, `Badge`, and other `ui/` tests). Full-repo run: 477 passed / 5 failed, all 5 failures pre-existing and unrelated (`nav-config.test.ts`, `AnnotationImportPreview.test.tsx`, `BatchRunsTab.test.tsx` — confirmed via `git stash` to fail identically without this change's edits) | 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 | AI (Claude) | 2026-07-13 |
| 3 | Live browser QA (Playwright against the running Next.js dev server) | Rendered `JobCard` + `JobDetailPanel` for all 7 `JobStatus` values in a real Chromium browser (full-page screenshot, `qa-full.png`, captured to session scratchpad — not committed). Automated DOM scan for `text-gray-\|bg-gray-\|border-gray-` classes on the rendered page returned zero matches. Confirmed: horizontal timeline with correct per-status coloring, 3-box lineage diagram with emphasized middle node and "pending" fallback, running callout (pulsing dot, epoch fraction, progress bar, stat row) only for `running`, large-stat metrics + separate eval_loss line only for `completed`, MLflow link card for `completed`. Temporary QA route (`src/portal/src/app/qa-training-jobs/`) deleted after capture — not part of the shipped change | 1, 5, 6, 7, 8, 9, 11, 12 | AI (Claude) | 2026-07-13 |
| 4 | Backend test additions (structural, not run — pre-existing environment gap) | Added `test_list_versions_system_admin_requires_tenant_id`, `test_list_versions_system_admin_with_tenant_id_override`, `test_get_active_system_admin_requires_tenant_id`, `test_get_active_system_admin_with_tenant_id_override` to `tests/test_model_registry.py`, exercising the new `tenant_id` query-param branch in `models.py`. Could not execute via `pytest` in this environment — the suite requires a separate test Postgres on port 54320 that isn't running here, a documented pre-existing gap (see `openspec/changes/archive/2026-07-13-fix-model-loading-and-label-mapping/tasks.md` §6.5/8.3 for the same limitation on a prior change). Verified instead via direct source review (mirrors `training_jobs.py`'s identical, already-shipped pattern) and Python `ast.parse` syntax check | 7, 8 (system_admin cross-tenant path) | AI (Claude) | 2026-07-13 |
| 5 | Automated test run (post-bug-fix, § 8 tasks) | `npx vitest run` targeted: `job-filter-tabs.test.tsx`, `job-detail-panel.test.tsx`, `page.test.tsx` → 3 files / 22 tests passed, including the 3 new regression tests for scenarios 14-16 (scenario 17 covered by the pre-existing, unmodified "shows not found when error" test). Full-repo run: 481 passed / 5 failed — same 5 pre-existing/unrelated failures as Evidence Log #2 (`nav-config.test.ts` x3, `AnnotationImportPreview.test.tsx` x1, `BatchRunsTab.test.tsx` x1), count delta (477→481 passing, plus the 5 constant failures = 482→486 total) fully explained by the 4 net-new tests added in this round | 14, 15, 16, 17 | AI (Claude) | 2026-07-13 |
| 6 | Automated test run (post-mockup-fidelity-pass, § 10 tasks) | Extracted the mockup's actual computed template/JS from `docs/NER Platform.html` (the `trainVals()` method and its inline `style` template strings) via targeted Node.js text extraction, rather than eyeballing a screenshot, and diffed it against every training-jobs component. `npx vitest run` targeted: `job-filter-tabs.test.tsx`, `job-card.test.tsx`, `job-detail-panel.test.tsx`, `page.test.tsx` → 4 files / 33 tests passed (5 net-new tests for scenarios 18-23; scenarios 14/15 tests rewritten in place to match the corrected active-tab mechanism, not counted as net-new). Full-repo run: 486 passed / 5 failed — same 5 pre-existing/unrelated failures as Evidence Log #2 and #5 (count delta 481→486 passing exactly matches the 5 net-new tests) | 14 (superseding fix), 18, 19, 20, 21, 22, 23 | AI (Claude) | 2026-07-13 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** redesign-training-jobs-ui
**Proposal:** `openspec/changes/redesign-training-jobs-ui/proposal.md`
**Spec files reviewed:**
  - specs/training-jobs-screen/spec.md

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
